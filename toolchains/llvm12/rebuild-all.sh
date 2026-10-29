#!/bin/sh
# Optional full rebuild into a NEW CMake directory; bootstrap cache is not reused.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH= cd -- "$base/../.." && pwd)
test -f "$root/third_party/darm/llvm/CMakeLists.txt" || {
  echo "Initialize dependency: git submodule update --init --recursive" >&2
  exit 1
}
cmake -S "$root/third_party/darm/llvm" -B "$base/full-build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_ENABLE_PROJECTS=clang '-DLLVM_TARGETS_TO_BUILD=X86;NVPTX' \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$base/full-build" --target opt clang llc llvm-link --parallel 2
