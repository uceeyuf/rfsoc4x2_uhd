#
# RFSoC 4x2 implementation-only constraints (the CMAC is a black box during
# synthesis: its IP is synthesized out of context).
#

# 100 GbE MAC next to the QSFP28 GTY quad (X0Y4..X0Y7), as in the rfsoc4x2_100g_udp
# design. Replaces the X4xx transport adapter constraint (qsfp_100gbe_port0.xdc:
# CMACE4_X0Y1, not read here). The design has one CMAC.
set_property LOC CMACE4_X0Y0 [get_cells -hierarchical -filter {PRIMITIVE_TYPE == ADVANCED.MAC.CMACE4}]
