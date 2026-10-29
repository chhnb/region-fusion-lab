TPACF (HecBench CUDA)
====================

Source: ORNL/HeCBench, commit6f44356a3ddc6ac7dbf5f626c671ed1638c17374,
src/tpacf-cuda/ACF_kernel.cu. Original Illinois/NCSA license is retained in source.
This is NOT a case from the original DaRM artifact benchmark suite.

Scope
-----

ACFKernel and ACFKernelSymm are retained, including original unroll pragmas,
128x128 grid,128 threads/block,3072 shared bytes,LOG2_GRID_SIZE14 and packed output.
Three identical31-condition/32-option chains are replaced by a common helper.
R0 corresponds to temp<binbounds[30] and code124; R31 is the fallback code0.
One grouping policy is reused at the three sites; this is not cross-kernel fusion.
The rest of each kernel, including synchronization and symmetry guards, is preserved.

Each group tests only the original predicates INSIDE its interval, in order.
Its enclosing first-match dispatch already excludes earlier options. This retains
first-match behavior for unordered boundaries and NaN without importing an
unrelated prefix into the helper. We do not assume monotonic data or build a
balanced comparison tree. The compiler may of course simplify the resulting control flow.

Primary comparison
------------------

original/unmerged = common helper preparation without melding.
bf/darm = automatic modes on that same unmerged helper IR.
greedy/enumeration = adjacent pair generation from the same preserved leaf IR.
All use the same final compile pipeline. Preparation check requires the no-meld
helper control to compile identically to the initial unmerged state.
source_original = untouched source through LLVM, a SEPARATE preparation diagnostic.
native = untouched source through NVCC, independent numerical oracle.

common-initial.ll and baselines/*/input.ll record the actual BF/DaRM start.
This remains the compositional helper prototype, not an arbitrary full-function
contextual region pass. No full-kernel automatic DaRM timing is implied.

Commands
--------

    python3 run.py build --case tpacf --first 0 --last 3 --out runs/tpacf-small
    .venv/bin/python compare.py runs/tpacf-small --validate-only
    python3 run.py build --case tpacf --skip-enumeration --out runs/tpacf-all
    .venv/bin/python compare.py runs/tpacf-all

--first/--last constrain BOTH greedy and enumeration. Outside options remain
singletons. Requested intervals inside the window MUST fully fuse for an enum
history to be feasible.32-way exhaustive search is rejected by the budget gate
BEFORE compilation. Restrict a window or explicitly skip enumeration.

Input and verification
----------------------

Default comparison uses synthetic isotropic points with seed20261021,16384 points
per set. Boundaries reproduce the old study's source-style configuration:
5 bins/decade,1 to10000 arcminutes; unused lower entries and boundary30 are-5.
This is NOT the official sky catalog, which is not included. The source host
program requires explicit dataset/parameter arguments; 'default' here means the
framework's declared fixture, not a claim of an upstream implicit default.

Validation includes small-grid CPU packed-output checks, canaries and untouched
output guards, exact/neighbor thresholds, NaN/Inf, all-bin wide boundaries and
unordered boundaries. Full native-grid output is compared word-for-word with NVCC
for both kernels. Timing is kernel-only, excludes setup/transfers, and does not
include the histogram kernel or full application. Default --size is16384;
other sizes require a separate geometry adapter and are rejected.

Similarity scoring is enabled. The experimental tx/ty integer scenario estimator
is not applicable to double predicates and is explicitly unavailable for TPACF.

Historical migration validation (v1; superseded guard adapter)
-------------------------------------------------------------

R0..R3:8 partitions,16 chronological histories,14 feasible fusion structures.
All options outside this window remained singleton.13 distinct cubins after
aliasing (including controls) passed CPU/NVCC validation for both kernels.
BF/DaRM still optimize the full helper in a scoped run; use the full32-way run
for the main algorithm comparison, and the scoped run to audit enumeration.

Full32-way greedy:17 committed merges, ending with R0..R3 grouped and adjacent
pairs for the rest. It did not fully fuse32 options. BF and DaRM each performed
2 automatic melds on the shared initial helper. The no-meld preparation control
compiled identically to the initial unmerged variant.5 distinct variants passed
all validation fixtures and a100-sample two-context timing screen.

These counts describe the migrated engine and default similarity policy, not a
claim of optimal grouping or stable speedup. Raw local evidence lives under
runs/tpacf-r0-r3-v1 and runs/tpacf-all-v1 and is intentionally excluded from Git.

Interval guard correction
-------------------------

The v1 adapter inserted p0 OR ... OR pk into every helper boundary. Under valid
entry conditions the prefix was false, but isolated helper compilation could not
prove that and retained spurious CFG. This blocked legitimate later pair matching.

For a split [a..k] + [k+1..b], the corrected guard is pa OR ... OR pk. The root
dispatch likewise uses each group's own interval. Guard modules/cache keys include
BOTH endpoints, so [0..5] and [4..5] cannot share a guard by accident.
No llvm.assume, numerical threshold ordering or profile-based exclusions are used.

Entry invariant: a helper [a..b] is reached only after every earlier option failed,
and its interval contains the first true predicate (or includes fallback R31).
The local guard selects the left child exactly when that first match belongs to
the left interval. Recursing preserves the invariant and the original selected
leaf. This reasoning applies because TPACF predicates are pure reads/comparisons
of immutable binbounds; it is not a generic license to reorder side effects.

The original cumulative-guard v1 grouping/timing results must not be used as
representative of the intended path-context-aware adapter. They remain archived.

Cleanup scheduling (current default)
------------------------------------

Per-merge cleanup now defaults to ``minimal``: predicate inlining, simplifycfg,
module pruning and verification. Full O3 is applied at the final shared backend,
not to each intermediate fused group. Initial frontend/leaf preparation remains
unchanged. ``--merge-cleanup o3`` explicitly reproduces the previous policy.
The experimental scoring evaluator may optimize a COPY for estimation; it does
not replace the intermediate group used for the next fusion.

With local guards fixed, a frozen balanced schedule succeeds for all31 merges
under minimal cleanup; per-merge O3 fails at [24..27]+[28..31]. The current greedy
text-ID tie-break is unchanged: it produces2groups under minimal cleanup, versus
3under O3. These are different searches, not a proof of greedy global optimality.

All tested fixed-partition and full balanced/greedy artifacts passed CPU/NVCC
checks. More melding is not a speed guarantee: full balanced fusion was slower
than the unmerged control in the synthetic-input audit. See docs/TPACF-O3-ANALYSIS.txt.

Reproduce the controlled audit after building local-guard runs with the two modes:

    python3 -m cases.tpacf.audit_cleanup --base runs/minimal \
        --o3-base runs/o3 --out runs/cleanup-audit
    .venv/bin/python compare.py runs/cleanup-audit --contexts 2 --blocks 2
