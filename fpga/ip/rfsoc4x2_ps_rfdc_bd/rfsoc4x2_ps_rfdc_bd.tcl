#
# RFSoC 4x2 PS + RFDC block design.
#
# Built on top of the upstream X440 block design (uhd/fpga/usrp3/top/x400/ip/
# x4xx_ps_rfdc_bd/x440_ps_rfdc_bd), retargeted to this Vivado by
# fpga/tools/bd_retarget.py, so the PL-facing interfaces, register blocks and RF
# reset/clocking logic stay identical to the X440. This script then applies the
# RFSoC 4x2 differences:
#   1. PS: DDR, MIO, peripherals and PS clocks from the RFSoC 4x2 board preset.
#   2. RFDC (xczu48dr): 4.0 GS/s, x8 decimation / interpolation (MCR 500 MS/s,
#      fabric 62.5 MHz). Refclk 500 MHz (LMX2594) only on ADC 226 and DAC 230,
#      whose PLLs distribute the sample clock to the other tiles. All tiles stay
#      enabled (the analog SYSREF chain needs them for MTS).
#      Radio mapping (same structure as the X440, 4 ports per radio):
#        radio0: ADC 224 ch0/ch1, 225 ch0/ch1   DAC 228 ch0/ch1, 229 ch0/ch1
#        radio1: ADC 226 ch0/ch1, 227 ch0/ch1   DAC 230 ch0/ch1, 231 ch0/ch1
#      Bonded on the RFSoC 4x2: ADC 224 ch0/ch1 (ADC_C/ADC_D), ADC 226 ch0/ch1
#      (ADC_A/ADC_B), DAC 228 ch0 (DAC_A), DAC 230 ch0 (DAC_B), i.e. ports 0/1
#      (RX) and port 0 (TX) of each radio.
#   3. Data clock MMCM: input = LMK04828 FPGA_REFCLK at 500 MHz (the board's
#      validated LMK setting), pll_ref_clk_out 125 MHz, radio clocks for MCR
#      500 MS/s (62.5 / 125 MHz).
#
# Expects: env X440_BD_TCL = X440 BD script from bd_retarget.py --rfsoc4x2; an open project with the
# X440 HDL sources (hdl_sources.tcl) and an empty current BD design.
#

set script_dir [file dirname [file normalize [info script]]]

# ---------------------------------------------------------------------------
# X440 base design, with the RFSoC 4x2 RFDC settings (section 2) appended to the
# X440 RFDC configuration by bd_retarget.py --rfsoc4x2
# ---------------------------------------------------------------------------
set ::rfsoc4x2_rfdc_cfg [list]
foreach t {0 1 2 3} {
  if {$t == 2} {set pll true; set ref 500.000} else {set pll false; set ref 4000.000}
  foreach type {ADC DAC} {
    lappend ::rfsoc4x2_rfdc_cfg CONFIG.${type}${t}_Enable {1} CONFIG.${type}${t}_Multi_Tile_Sync {true} \
      CONFIG.${type}${t}_Sampling_Rate {4.0} CONFIG.${type}${t}_PLL_Enable $pll \
      CONFIG.${type}${t}_Refclk_Freq $ref CONFIG.${type}${t}_Outclk_Freq {62.500} \
      CONFIG.${type}${t}_Fabric_Freq {62.500}
  }
  lappend ::rfsoc4x2_rfdc_cfg CONFIG.ADC${t}_Clock_Source {2} CONFIG.DAC${t}_Clock_Source {6}
  foreach s {1 3} { lappend ::rfsoc4x2_rfdc_cfg CONFIG.DAC_Slice${t}${s}_Enable {false} }
  foreach s {0 2} {
    lappend ::rfsoc4x2_rfdc_cfg CONFIG.DAC_Slice${t}${s}_Enable {true} CONFIG.DAC_Data_Type${t}${s} {0} \
      CONFIG.DAC_Data_Width${t}${s} {16} CONFIG.DAC_Interpolation_Mode${t}${s} {8} \
      CONFIG.DAC_Mixer_Type${t}${s} {2} CONFIG.DAC_Mixer_Mode${t}${s} {0}
  }
}
lappend ::rfsoc4x2_rfdc_cfg CONFIG.ADC2_Clock_Dist {2} CONFIG.DAC2_Clock_Dist {2}

source $::env(X440_BD_TCL)

# ---------------------------------------------------------------------------
# 1. PS: board preset
# ---------------------------------------------------------------------------
set ps [get_bd_cells ps/inst_zynq_ps]

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

# ---------------------------------------------------------------------------
# 2. RFDC
# ---------------------------------------------------------------------------
set rfdc_hier [get_bd_cells rfdc]
set rf [get_bd_cells rfdc/rf_data_converter]
current_bd_instance $rfdc_hier

# The DAC data, DAC output and converter clock connections were dropped by
# bd_retarget.py --rfsoc4x2; they are rebuilt here for the new tile layout.
set r1_net [get_bd_nets -of [get_bd_pins rf_data_converter/s1_axis_aclk]]
disconnect_bd_net $r1_net [get_bd_pins rf_data_converter/s1_axis_aclk]


# DAC data: calibration mux output m_axis_<port>_<radio> -> DAC tile / slice
foreach {radio port dpin} {
  0 0 s00_axis  0 1 s02_axis  0 2 s10_axis  0 3 s12_axis
  1 0 s20_axis  1 1 s22_axis  1 2 s30_axis  1 3 s32_axis
} {
  connect_bd_intf_net [get_bd_intf_pins calibration_muxes/m_axis_${port}_${radio}] \
                      [get_bd_intf_pins rf_data_converter/$dpin]
}
set r0_net [get_bd_nets -of [get_bd_pins rf_data_converter/s0_axis_aclk]]
connect_bd_net -net $r0_net [get_bd_pins rf_data_converter/s1_axis_aclk]
connect_bd_net -net $r1_net [get_bd_pins rf_data_converter/s2_axis_aclk] \
                            [get_bd_pins rf_data_converter/s3_axis_aclk]

# DAC outputs: hierarchy pins and top-level ports named by tile / channel
foreach pin [get_bd_intf_pins -quiet dac_tile22*_vout] { delete_bd_objs $pin }
foreach {t c vpin} {
  228 0 vout00  228 1 vout02  229 0 vout10  229 1 vout12
  230 0 vout20  230 1 vout22  231 0 vout30  231 1 vout32
} {
  set pin_name dac_tile${t}_ch${c}_vout
  create_bd_intf_pin -mode Master -vlnv xilinx.com:interface:diff_analog_io_rtl:1.0 $pin_name
  connect_bd_intf_net [get_bd_intf_pins rf_data_converter/$vpin] [get_bd_intf_pins $pin_name]
}

# Converter reference clocks: only ADC 226 and DAC 230
foreach pin_name {adc0_clk adc1_clk adc3_clk dac0_clk dac1_clk} {
  delete_bd_objs [get_bd_intf_pins -quiet $pin_name]
}
create_bd_intf_pin -mode Slave -vlnv xilinx.com:interface:diff_clock_rtl:1.0 dac2_clk
connect_bd_intf_net [get_bd_intf_pins adc2_clk] [get_bd_intf_pins rf_data_converter/adc2_clk]
connect_bd_intf_net [get_bd_intf_pins dac2_clk] [get_bd_intf_pins rf_data_converter/dac2_clk]

# NCO control of the new DAC tiles/slices: same nets as their X440 counterparts
foreach pin [get_bd_pins -of $rf -filter {DIR == I}] {
  if {[get_bd_nets -quiet -of $pin] ne ""} continue
  set n [get_property NAME $pin]
  set ref ""
  if {[regexp {^dac\d\d_(nco_phase_rst|nco_update_en)$} $n -> f]} { set ref dac00_$f }
  if {[regexp {^dac[123]_nco_update_req$} $n]} { set ref adc0_nco_update_req }
  if {$ref ne ""} {
    connect_bd_net -net [get_bd_nets -of [get_bd_pins rf_data_converter/$ref]] $pin
  }
}
current_bd_instance /

foreach pin_name {adc0_clk adc1_clk adc3_clk dac0_clk dac1_clk} {
  delete_bd_objs [get_bd_intf_ports -quiet $pin_name]
}
# X440 DAC output ports (their hierarchy pins are gone)
foreach port [get_bd_intf_ports -quiet dac_tile22*_vout] { delete_bd_objs $port }

# Make a hierarchy pin external under the given top-level port name
proc rfsoc4x2_external {pin port_name} {
  make_bd_intf_pins_external [get_bd_intf_pins $pin]
  set port [get_bd_intf_ports -of_objects [get_bd_intf_nets -of_objects [get_bd_intf_pins $pin]]]
  set_property name $port_name $port
}
rfsoc4x2_external rfdc/dac2_clk dac2_clk
foreach {t c} {228 0 228 1 229 0 229 1 230 0 230 1 231 0 231 1} {
  rfsoc4x2_external rfdc/dac_tile${t}_ch${c}_vout dac_tile${t}_ch${c}_vout
}
set_property CONFIG.FREQ_HZ 500000000 [get_bd_intf_ports adc2_clk]
set_property CONFIG.FREQ_HZ 500000000 [get_bd_intf_ports dac2_clk]

# ---------------------------------------------------------------------------
# 3. Data clock MMCM
# ---------------------------------------------------------------------------
set_property CONFIG.FREQ_HZ 500000000 [get_bd_ports pll_ref_clk_in]
set_property -dict [list \
  CONFIG.PRIM_IN_FREQ {500.000} \
  CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {125.000} \
  CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {62.500} \
  CONFIG.CLKOUT3_REQUESTED_OUT_FREQ {62.500} \
  CONFIG.CLKOUT4_REQUESTED_OUT_FREQ {125.000} \
  CONFIG.CLKOUT5_REQUESTED_OUT_FREQ {125.000} \
  CONFIG.CLKOUT6_REQUESTED_OUT_FREQ {62.500} \
  CONFIG.CLKOUT7_REQUESTED_OUT_FREQ {125.000} \
] [get_bd_cells rfdc/data_clock_mmcm]

# Clock / stream properties fixed in the X440 script (top-level ports and
# module-reference pins): X440 static rates -> MCR 500, X440 clock domain names
# -> this design's
set design [get_property NAME [current_bd_design]]
foreach obj [concat [get_bd_ports] [get_bd_intf_ports] \
                    [get_bd_pins -hierarchical -filter {TYPE == clk}]] {
  if {![catch {get_property CONFIG.FREQ_HZ $obj} f]} {
    switch -- $f {
      256000000 { set_property CONFIG.FREQ_HZ 62500000 $obj }
      512000000 { set_property CONFIG.FREQ_HZ 125000000 $obj }
      64000000  { set_property CONFIG.FREQ_HZ 125000000 $obj }
    }
  }
  if {![catch {get_property CONFIG.CLK_DOMAIN $obj} d] && [string match x440_ps_rfdc_bd_* $d]} {
    set_property CONFIG.CLK_DOMAIN [string map [list x440_ps_rfdc_bd $design] $d] $obj
  }
}
