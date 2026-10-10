#!/bin/bash
# Retarget the X4xx block designs used by the RFSoC 4x2 image to this Vivado and
# xczu48dr, and check that each one sources, validates and generates.
# Usage: fpga/tools/regen_bds.sh [bd_name ...]
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
IP=$ROOT/uhd/fpga/usrp3/top/x400/ip
PART=${PART:-xczu48dr-ffvg1517-2-e}
VIVADO_SETTINGS=${VIVADO_SETTINGS:-/tools/Xilinx/Vivado/2023.2/settings64.sh}
BDS=${*:-eth_100g_bd axi_eth_dma_bd axi_interconnect_eth_bd axi_interconnect_dma_bd axi_interconnect_app_bd}
source "$VIVADO_SETTINGS"
for bd in $BDS; do
  out=$ROOT/build/bd/$bd; mkdir -p "$out"; cd "$out"
  python3 "$HERE/bd_retarget.py" "$IP/$bd/$bd.tcl" "$out/$bd.tcl" --part "$PART"
  hdl=""; [ -f "$IP/$bd/hdl_sources.tcl" ] && hdl=$IP/$bd/hdl_sources.tcl
  BD_TCL=$out/$bd.tcl BD_HDL=$hdl PART=$PART OUT_TCL=$out/${bd}_flat.tcl \
    vivado -mode batch -nojournal -nolog -source "$HERE/bd_check.tcl" > bd.log 2>&1
  echo "$bd: $(grep -E '^BD_' bd.log | tr '\n' ' ') errors=$(grep -c '^ERROR' bd.log)"
done
