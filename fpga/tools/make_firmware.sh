#!/bin/bash
#
# Package the FPGA image for MPM: build/firmware/rfsoc4x2.bin (bitstream for
# the Linux FPGA manager) and build/firmware/x440.dtbo (device tree overlay that
# MPM applies: product "x440"; it names rfsoc4x2.bin as firmware).
#   fpga/tools/make_firmware.sh   (after fpga/build.sh impl and petalinux-config
#                                  --get-hw-description with its XSA)
#
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
VIVADO_SETTINGS=${VIVADO_SETTINGS:-/tools/Xilinx/Vivado/2023.2/settings64.sh}
X400=$ROOT/uhd/fpga/usrp3/top/x400
BIT=$ROOT/build/rfsoc4x2/rfsoc4x2.bit
OUT=$ROOT/build/firmware
mkdir -p "$OUT"
cd "$OUT"

# 1. Bitstream -> .bin for the ZynqMP FPGA manager
source "$VIVADO_SETTINGS"
cat > rfsoc4x2.bif <<BIF
all:
{
  [destination_device = pl] $BIT
}
BIF
bootgen -arch zynqmp -image rfsoc4x2.bif -process_bitstream bin -w > bootgen.log
mv -f "$BIT.bin" rfsoc4x2.bin

# 2. Generated device tree includes
python3 "$X400/tools/parse_versions_for_dts.py" \
  --input "$X400/regmap/x440/versioning_regs_regmap_utils.vh" \
  --output rfsoc4x2-version-info.dtsi \
  --components fpga,cpld_ifc,db_gpio_ifc,rf_core_full,rf_core_200m
# RFDC driver configuration: the PetaLinux device-tree generator writes it for
# this XSA (rfdc v12.1 layout); MPM's bundled xrfdc driver needs the v6.0 layout.
PL_DTSI=${PL_DTSI:-$ROOT/linux/petalinux/components/plnx_workspace/device-tree/device-tree/pl.dtsi}
python3 "$ROOT/mpm/tools/rfdc_param_list.py" from-dtg "$PL_DTSI" rfsoc4x2-rfdc-params.dtsi

# 3. Overlay
# The fragment with firmware-name (rfsoc4x2-fpga.dtsi) goes last: the Xilinx
# kernel's fpga-region accepts fragments without firmware-name, but rejects
# every fragment after the one that programs the FPGA ("Region already has
# overlay applied"). NI's kernel does not have this limit, so the upstream X4xx
# overlays put it first.
grep -v 'rfsoc4x2-fpga.dtsi' "$ROOT/build/image_core/device_tree.dts" > x440.top.dts
echo '#include "rfsoc4x2-fpga.dtsi"' >> x440.top.dts
cpp -nostdinc -undef -x assembler-with-cpp -D__DTS__ \
  -I "$OUT" -I "$ROOT/fpga/dts" -I "$X400/dts" \
  x440.top.dts -o x440.pp.dts
dtc -@ -I dts -O dtb -o x440.dtbo x440.pp.dts
ls -l rfsoc4x2.bin x440.dtbo
