# Print the X440 design source list of the upstream X4xx makefiles (no rules run).
# make -f design_srcs.mk -C <uhd>/fpga/usrp3/top/x400 BUILD_DIR=<image core dir> list
X440 = 1
TOP_MODULE = x4xx
include Makefile.x4xx.inc
list:
	@for f in $(DESIGN_SRCS); do echo $$f; done
defs:
	@printf "%s\n" '$(RFNOC_IMAGE_CORE_DEFS)'
