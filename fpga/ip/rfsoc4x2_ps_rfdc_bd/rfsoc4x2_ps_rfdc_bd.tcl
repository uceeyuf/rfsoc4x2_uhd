#
# RFSoC 4x2 PS + RFDC block design.
#
# Built on top of the upstream X440 block design (uhd/fpga/usrp3/top/x400/ip/
# x4xx_ps_rfdc_bd/x440_ps_rfdc_bd), retargeted to this Vivado by
# fpga/tools/bd_retarget.py, so the PL-facing interfaces, register blocks and RF
# reset/clocking logic stay identical to the X440. This script then applies the
# RFSoC 4x2 differences:
#   1. PS: DDR, MIO, peripherals and PS clocks from the RFSoC 4x2 board preset.
#
# Expects: env X440_BD_TCL = retargeted X440 BD script; an open project with the
# X440 HDL sources (hdl_sources.tcl) and an empty current BD design.
#

set script_dir [file dirname [file normalize [info script]]]

# ---------------------------------------------------------------------------
# X440 base design
# ---------------------------------------------------------------------------
source $::env(X440_BD_TCL)

# ---------------------------------------------------------------------------
# 1. PS: board preset
# ---------------------------------------------------------------------------
set ps [get_bd_cells inst_zynq_ps]

# X440 MIO peripherals that the RFSoC 4x2 does not have (or has elsewhere):
# GEM3 (4x2: GEM1), SD1 (4x2: SD0), UART0 (4x2: UART1), SPI1 SS1/SS2.
set_property -dict [list \
  CONFIG.PSU__ENET3__PERIPHERAL__ENABLE {0} \
  CONFIG.PSU__SD1__PERIPHERAL__ENABLE   {0} \
  CONFIG.PSU__UART0__PERIPHERAL__ENABLE {0} \
  CONFIG.PSU__SPI1__GRP_SS1__ENABLE     {0} \
  CONFIG.PSU__SPI1__GRP_SS2__ENABLE     {0} \
] $ps

source $script_dir/ps_preset_rfsoc4x2.tcl
set_property -dict $rfsoc4x2_ps_preset $ps
