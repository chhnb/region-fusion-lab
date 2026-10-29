Shared LLVM12 backend
====================

Compiler source lives ONLY in the pinned workspace/third_party/darm submodule. There is
no tracked local source overlay. See the root README for exact commands.

rebuild-all.sh: clean-clone route, configure the submodule's llvm/ directory and
build opt, clang, llc and llvm-link into full-build/. config.example.json points
there. Both BF and DaRM run the same opt with different flags.

build.py: optional local incremental route. It recompiles CFMelder from the
submodule, using ignored bootstrap libraries and a local migrated recipe. Do not
run Ninja in bootstrap: its historical CMake cache is not relocatable.

Tests: python3 check.py llvm --out runs/new-regression, from workspace root.
Fixtures and change audit are in third_party/darm/cfm_benchmarks/fusion-regressions/.
The author base is recorded in ORIGIN.txt; current revision is the gitlink.

Migration validated 14641 alignment pairs, 8640 CPU cases per mode, convergent
rejection, and SRAD GPU output. BF does not meld the nested-switch fixtures;
actual BF melding was checked on SRAD. This is a locally patched compiler,
not an unmodified upstream binary. Historical local reports are not committed.
