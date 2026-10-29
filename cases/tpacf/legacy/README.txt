group2_max.cu is the archived unrolled group2/pairs-max source from the previous
TPACF study (2026-10-21), not a binary artifact. It preserves the original source
license. The audit reconstructs this source from ACF_kernel.cu and asserts equality
apart from whitespace, then recompiles with the current common compiler flags.

The old group entrance uses precomputed adjacent-pair maxima (15 doubles), and
within each pair chooses the first original predicate's code. The last pair is
an unconditional fallback group with an internal binbounds[0] test.

Source-style comparison is explicitly separate from the matched-helper comparison.
Identical unroll pragmas do not guarantee identical actual LLVM unrolling after
changing the frontend shape.
