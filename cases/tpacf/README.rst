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

Cumulative OR of original predicates preserves first-match behavior even for
unordered boundaries and NaN. We do not assume monotonic data or build a balanced
comparison tree. The compiler may of course simplify the resulting control flow.

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

Initial migration validation
----------------------------

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
