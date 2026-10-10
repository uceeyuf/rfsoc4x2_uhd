#!/bin/bash
# RTL-elaborate key UHD RFNoC library modules with the installed Vivado
# (RFSoC 4x2 part, 100 GbE parameters). Usage: fpga/tools/elab_check.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
VIVADO_SETTINGS=${VIVADO_SETTINGS:-/tools/Xilinx/Vivado/2023.2/settings64.sh}
OUT=${OUT:-$ROOT/build/elab_check}
mkdir -p "$OUT"
make -s -f "$HERE/print_srcs.mk" BASE_DIR="$ROOT/uhd/fpga/usrp3/top" list > "$OUT/srcs.txt"
source "$VIVADO_SETTINGS"
cd "$OUT"
SRCS="$OUT/srcs.txt" vivado -mode batch -nojournal -nolog -source "$HERE/elab_check.tcl" > elab.log 2>&1 || true
grep -E "ELAB_SUMMARY|^ERROR" elab.log
