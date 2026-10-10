#!/bin/bash
#
# RFSoC 4x2 UHD FPGA build.
#   fpga/build.sh [rtl|synth|impl] [jobs]   (default: impl 4)
#
# Generates the RFNoC image core and the source lists, then runs fpga/build.tcl.
# Run long builds inside a memory-limited scope, e.g.
#   systemd-run --user --scope -p MemoryMax=24G fpga/build.sh impl 2
#
set -e
STEP=${1:-impl}
JOBS=${2:-4}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
VIVADO_SETTINGS=${VIVADO_SETTINGS:-/tools/Xilinx/Vivado/2023.2/settings64.sh}
YAML=${YAML:-$HERE/rfsoc4x2_CG_400_rfnoc_image_core.yml}
X400=$ROOT/uhd/fpga/usrp3/top/x400

mkdir -p "$ROOT/build"

# UHD stays unmodified: fpga/patches/uhd/*.patch are applied to copies of the
# touched files in build/uhd_patched/, which build.tcl uses instead
rm -rf "$ROOT/build/uhd_patched"
for p in "$HERE"/patches/uhd/*.patch; do
  [ -e "$p" ] || continue
  for f in $(sed -n 's|^+++ b/\([^[:space:]]*\).*|\1|p' "$p"); do
    mkdir -p "$ROOT/build/uhd_patched/$(dirname "$f")"
    [ -e "$ROOT/build/uhd_patched/$f" ] || cp "$ROOT/uhd/$f" "$ROOT/build/uhd_patched/$f"
  done
  patch -s -p1 -d "$ROOT/build/uhd_patched" < "$p"
done
"$HERE/tools/rfnoc_image_builder.py" -y "$YAML" -F "$ROOT/uhd/fpga" -B "$ROOT/build/image_core" -G
source "$VIVADO_SETTINGS"
make -s -f "$HERE/tools/design_srcs.mk" -C "$X400" BUILD_DIR="$ROOT/build/image_core" list \
  > "$ROOT/build/design_srcs.txt"
make -s -f "$HERE/tools/design_srcs.mk" -C "$X400" BUILD_DIR="$ROOT/build/image_core" defs \
  > "$ROOT/build/image_defs.txt"
mkdir -p "$ROOT/build/rfsoc4x2"
cd "$ROOT/build/rfsoc4x2"
vivado -mode batch -nojournal -log build.log -source "$HERE/build.tcl" -tclargs "$STEP" "$JOBS"
