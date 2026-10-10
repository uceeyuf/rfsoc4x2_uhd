# Print the HDL sources of the usrp3 libraries used by the RFNoC image core.
# make -f print_srcs.mk BASE_DIR=<uhd>/fpga/usrp3/top print
LIB_DIR = $(abspath $(BASE_DIR)/../lib)
include $(LIB_DIR)/control/Makefile.srcs
include $(LIB_DIR)/fifo/Makefile.srcs
include $(LIB_DIR)/axi/Makefile.srcs
include $(LIB_DIR)/packet_proc/Makefile.srcs
include $(LIB_DIR)/dsp/Makefile.srcs
include $(LIB_DIR)/rfnoc/Makefile.srcs
include $(LIB_DIR)/axi4_sv/Makefile.srcs
include $(LIB_DIR)/axi4s_sv/Makefile.srcs
include $(LIB_DIR)/axi4lite_sv/Makefile.srcs
include $(LIB_DIR)/rfnoc/xport_sv/Makefile.srcs
print:
	@$(foreach v,$(filter %_SRCS,$(.VARIABLES)),echo "$(v): $(words $($(v)))";)
include $(LIB_DIR)/rfnoc/blocks/rfnoc_block_radio/Makefile.srcs
include $(LIB_DIR)/rfnoc/transport_adapters/rfnoc_ta_x4xx_eth/Makefile.srcs
# One file per line, for Vivado (excludes the X4xx MGT wrapper, which needs the BD IP)
list:
	@for f in $(sort $(foreach v,$(filter %_SRCS,$(.VARIABLES)),$($(v)))); do echo $$f; done
