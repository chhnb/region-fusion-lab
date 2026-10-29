Region Fusion Lab
=================

Research framework for greedy region fusion and exhaustive adjacent-merge search.
Compiler dependency: the pinned ``third_party/darm`` submodule, a fork of the
DaRM author's LLVM12 tree. BF and automatic DaRM use that engine in distinct modes.

Structure and semantics
-----------------------

* The region tree is multiway: if/else-if/else are sibling options; nested ifs
  form child choices. It is not a balanced binary decision tree.
* Pair candidates are adjacent options within the same choice. All depths compete
  by score in one priority queue; depth does not affect priority.
* Binary parentheses in logs represent pair-operation history, not region depth.
* The reference scheduler refreshes all candidates after every commit.
* Exhaustive search partitions contiguous intervals, then enumerates chronological
  adjacent merge schedules. Every interval must fully merge; failures are infeasible.
* Legality belongs to the generator; high scores cannot override generation failure.

Modules
-------

cases/                   Program preparation, input generation and correctness oracle.
backends/                DaRM pair generator and automatic BF/DaRM comparison modes.
fusion/tree.py           Multiway structure and adjacent pairs.
fusion/session.py        Connect case, generator and scorer.
fusion/scoring.py        Replaceable score functions; similarity is the default.
fusion/search.py         Global score-priority greedy reference scheduler.
fusion/enumeration.py    Strict interval/order enumeration.
experiments/             Common IR pipeline, validation and measurement.
third_party/darm/        Compiler source and compiler regression fixtures (submodule).
toolchains/llvm12/       Build scripts; binary/build directories are ignored.

Clone and build
--------------

    git clone --recurse-submodules https://github.com/chhnb/region-fusion-lab.git
    cd region-fusion-lab
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    sh toolchains/llvm12/rebuild-all.sh
    cc -shared -fPIC -O2 cases/srad/seed.c -o cases/srad/seed.so -lm

Requires CMake, Ninja, a C/C++ compiler and CUDA12.8 (default /usr/local/cuda-12.8).
The example configuration uses the fresh full-build output. Optional config.json
is ignored and can override local paths. FUSION_LLVM_BIN, FUSION_CUDA_BIN and
FUSION_OPT also override them. Paths in config are relative to the framework root.
No generated artifacts or experiment results are committed.

The existing local installation also supports incremental CFMelder rebuilding via
``python3 toolchains/llvm12/build.py`` using ignored bootstrap libraries/recipe.
That command is NOT the clean-clone build route.

Run
---

    python3 check.py
    python3 run.py count 4
    python3 run.py build --case srad4 --generator darm --baselines bf,darm \
        --score similarity --out runs/my-srad4
    .venv/bin/python compare.py runs/my-srad4 --contexts 1 --validate-only

For timing, run compare.py without --validate-only on an experiment whose comparison
output does not yet exist. All output directories must be new. Full compiler tests
are explicit, not part of the default lightweight check:

    python3 check.py llvm --out runs/new-regression

BF/DaRM from one input IR, without a case adapter:

    python3 transform.py --input input.ll --function kernel_name \
        --methods bf,darm --out runs/new-transform

Common preparation runs once. Methods receive equal copies and share O3+verify
cleanup. No input hash manifests are used. Failed transformations are not replaced
by a supposedly successful baseline result.

Scope and limitations
---------------------

The executable GPU adapter currently supports SRAD kernel2's four-way choice.
Nested multiway representation and depth-independent scheduling have tests, but
arbitrary nested LLVM transformation, RegionInfo discovery and TPACF integration
are not yet implemented. New cases need legality-preserving adapters and oracles.

The current session composes extracted helpers; it is not full-function contextual
trial generation. Original and matched-helper controls remain separate comparisons.
Legacy generator bindings require one session per process, not concurrent threads.

The optional net-cost scorer is an uncalibrated acyclic IR issue-cost prototype,
not a model of machine cycles, transactions or occupancy. No profile integration
or incremental dependency updater is implemented. A scorer can be supplied with
--score module:factory without changing search code.

Automatic BF/DaRM use threshold0.2. Our pair generator uses threshold0, entry-only
and once, leaving selection to the external policy. BF is the author's BF-only
mode, not a separate third-party compiler. Compiler fixes and guards can change
candidate behavior relative to upstream; see the audit in the submodule.

Tests and preserved local evidence validate the migrated CFMelder build. They do
not establish correctness for every CFG or a performance advantage. The known
SRAD nine-way full automatic DaRM PHI assertion is not fixed by this migration.
