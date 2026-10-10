#!/bin/bash
#
# Build the UHD host library and tools (v4.11.0.0 + host/patches) for use with
# the RFSoC 4x2. The uhd/ submodule stays unmodified: the source is a separate
# worktree in build/uhd-host-src with the patches applied.
#   host/build.sh [install prefix] [jobs]     (default: $HOME/uhd-rfsoc4x2, 8)
#
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
PREFIX=${1:-$HOME/uhd-rfsoc4x2}
JOBS=${2:-8}
SRC=$ROOT/build/uhd-host-src
TAG=v4.11.0.0

if [ ! -d "$SRC" ]; then
  git -C "$ROOT/uhd" worktree add --detach "$SRC" "$TAG"
  for p in "$HERE"/patches/*.patch; do
    git -C "$SRC" apply -p1 "$p"
  done
fi
mkdir -p "$SRC/host/build"
cd "$SRC/host/build"
cmake .. -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_DPDK=ON -DENABLE_PYTHON_API=ON -DENABLE_MANUAL=OFF -DENABLE_DOXYGEN=OFF \
  -DENABLE_USB=OFF -DENABLE_B100=OFF -DENABLE_B200=OFF -DENABLE_USRP1=OFF \
  -DENABLE_USRP2=OFF -DENABLE_X300=OFF -DENABLE_OCTOCLOCK=OFF
make -j"$JOBS"
make install
echo "Installed to $PREFIX: export LD_LIBRARY_PATH=$PREFIX/lib PATH=$PREFIX/bin:\$PATH"
