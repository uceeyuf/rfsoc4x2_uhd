#
# RFSoC 4x2 timing constraints, adapted from the X4xx constraints
# (constraints/timing/{common,x440,x440_clocks,shared_constants}, Copyright Ettus
# Research, LGPL-3.0-or-later) for the RFSoC 4x2 clocking: PLL_REFCLK_FPGA
# 500 MHz, pll_ref_clk (data clock MMCM) 125 MHz, base reference clock =
# pll_ref_clk / 5 (BUFGCE_DIV), QSFP0
# refclk 156.25 MHz, no CPLD / DB GPIO / DIO / trigger / PPS / LMK sync pins.
#

# Clocks -------------------------------------------------------------------
create_clock -name pll_ref_clk -period 2.000 [get_ports PLL_REFCLK_FPGA_P]
set pll_ref_clk_period 8.000   ;# MMCM pll_ref_clk_out (125 MHz)

set ref_clk_period 40.000
create_generated_clock -name ref_clk -divide_by 5 \
  -source [get_pins bufgce_div_base_ref_clk/I] [get_pins bufgce_div_base_ref_clk/O]

create_clock -name mgt_ref_0 -period 6.400 [get_ports QSFP0_REFCLK_P]

create_clock -name clk100 -period 10.000 \
  [get_pins -of_objects [get_cells -hierarchical {*PS8_i}] -filter {NAME =~ *PLCLK[0]}]
create_clock -name clk40  -period 25.000 \
  [get_pins -of_objects [get_cells -hierarchical {*PS8_i}] -filter {NAME =~ *PLCLK[1]}]
create_clock -name clk166 -period  6.000 \
  [get_pins -of_objects [get_cells -hierarchical {*PS8_i}] -filter {NAME =~ *PLCLK[2]}]
create_clock -name clk200 -period  5.000 \
  [get_pins -of_objects [get_cells -hierarchical {*PS8_i}] -filter {NAME =~ *PLCLK[3]}]

create_generated_clock -name ce_clk [get_pins {ce_clk_gen_i/CLKOUT0}]

# MGT clock crossings (as X4xx) --------------------------------------------
set rxoutclk [get_clocks -quiet -of_objects [get_pins -hierarchical -filter {NAME =~ */channel_inst/*_CHANNEL_PRIM_INST/RXOUTCLK}]]
set txoutclk [get_clocks -quiet -of_objects [get_pins -hierarchical -filter {NAME =~ */channel_inst/*_CHANNEL_PRIM_INST/TXOUTCLK}]]
if {[llength $rxoutclk] && [llength $txoutclk]} {
  set_max_delay -from $rxoutclk -to $txoutclk -datapath_only 6.40
  set_max_delay -from $txoutclk -to $rxoutclk -datapath_only 6.40
  set_max_delay -from $rxoutclk -to [get_clocks clk100] -datapath_only 6.40
  set_max_delay -from $txoutclk -to [get_clocks clk100] -datapath_only 6.40
  set_max_delay -from [get_clocks clk100] -to $txoutclk -datapath_only 10.000
  set_max_delay -from [get_clocks clk100] -to $rxoutclk -datapath_only 10.000
}

# PPS: the delayed PPS crosses from the base reference to the PLL reference
set_max_delay -from [get_cells -hierarchical pps_delayed_brc_reg] \
  -to [get_clocks pll_ref_clk*] [expr {$pll_ref_clk_period/2}]

# RFDC data clocks: keep the BUFGs of the data clock MMCM in one delay group
set rfdc_mmcm [get_cells -hierarchical -filter { PRIMITIVE_TYPE == CLOCK.PLL.MMCME4_ADV && NAME =~ *rfdc/data_clock_mmcm* } ]
set mmcm_clkout_pins [get_pins -of_objects $rfdc_mmcm -regexp -filter {NAME =~ ".*CLKOUT[0-6]"}]
set clkbuf_cells [get_cells -of_objects [get_pins -leaf -of_objects [get_nets -of_objects $mmcm_clkout_pins] -filter {DIRECTION == IN}]]
set_property CLOCK_DELAY_GROUP DataClkGroup [get_nets -of_objects [get_pins -of_objects $clkbuf_cells -filter {DIRECTION == OUT}]]
set_false_path -from [get_cells -hierarchical -regexp -filter {NAME =~ .*/rfdc/clock_gates_0/.*rEnableRfdc\dBufg.*_reg}]

# SYSREF_FABRIC is captured with pll_ref_clk (LMK04828 outputs from one VCO,
# matched board routing assumed; X440 numbers)
set sysref_lmk_delay 0.209
set_input_delay -clock pll_ref_clk -max [expr {$sysref_lmk_delay + 0.985}] [get_ports SYSREF_FABRIC_P]
set_input_delay -clock pll_ref_clk -min [expr {$sysref_lmk_delay - 0.964}] [get_ports SYSREF_FABRIC_P]

# Quasi-static paths (as X4xx)
set gpio_regs [get_pins -of [get_cells -filter {IS_SEQUENTIAL && NAME =~ *rfdc/calibration_muxes/axi_gpio*} -hier] -filter {IS_CLOCK}]
set mux_regs [get_cells -hier -filter {IS_SEQUENTIAL && NAME =~ *rfdc/calibration_muxes/gpio_to_axis_mux*}]
set_false_path -from $gpio_regs -to $mux_regs
set_false_path -to [get_pins -hierarchical -filter {NAME =~ */synchronizer_false_path/stages[0].value_reg[0][*]/D}]
set_false_path -to [get_pins -hierarchical -filter {NAME =~ */rf_reset_controller*/*_ms_reg/D}]

# QSFP sideband: static
set_false_path -to [get_ports {QSFP0_RESET_n QSFP0_LPMODE QSFP0_MODSEL_n}]
set_false_path -from [get_ports QSFP0_MODPRS_n]
