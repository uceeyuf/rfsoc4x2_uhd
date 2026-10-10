#
# RFSoC 4x2 pins (xczu48dr-ffvg1517-2-e). The RFDC analog/refclk/SYSREF pins are
# dedicated and placed by the RFDC IP; the QSFP28 GTY lanes by the CMAC IP.
# Board facts from the RFSoC 4x2 reference manual and the rfsoc4x2_mts /
# rfsoc4x2_100g_udp designs.
#

set_property CFGBVS GND [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.USR_ACCESS TIMESTAMP [current_design]

# LMK04828 -> PL: FPGA_REFCLK_IN (PLL_REFCLK_FPGA) and SYS_REF_FPGA (SYSREF_FABRIC),
# LVDS in HP banks 65/66, terminated on die
set_property PACKAGE_PIN AN11 [get_ports PLL_REFCLK_FPGA_P]
set_property PACKAGE_PIN AP11 [get_ports PLL_REFCLK_FPGA_N]
set_property PACKAGE_PIN AP18 [get_ports SYSREF_FABRIC_P]
set_property PACKAGE_PIN AR18 [get_ports SYSREF_FABRIC_N]
set_property IOSTANDARD LVDS [get_ports {PLL_REFCLK_FPGA_P PLL_REFCLK_FPGA_N SYSREF_FABRIC_P SYSREF_FABRIC_N}]
set_property DIFF_TERM_ADV TERM_100 [get_ports {PLL_REFCLK_FPGA_P PLL_REFCLK_FPGA_N SYSREF_FABRIC_P SYSREF_FABRIC_N}]

# QSFP28 GT reference clock (156.25 MHz)
set_property PACKAGE_PIN AA33 [get_ports QSFP0_REFCLK_P]

# QSFP28 sideband (LVCMOS18)
set_property -dict {PACKAGE_PIN AK22 IOSTANDARD LVCMOS18} [get_ports QSFP0_MODSEL_n]
set_property -dict {PACKAGE_PIN AL21 IOSTANDARD LVCMOS18} [get_ports QSFP0_RESET_n]
set_property -dict {PACKAGE_PIN AL22 IOSTANDARD LVCMOS18} [get_ports QSFP0_MODPRS_n]
set_property -dict {PACKAGE_PIN AN22 IOSTANDARD LVCMOS18} [get_ports QSFP0_LPMODE]

# The CMAC location is in rfsoc4x2_impl.xdc (implementation only).
