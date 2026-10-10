SUMMARY = "RFSoC 4x2 UHD FPGA image and device tree overlay for MPM"
DESCRIPTION = "Installs build/firmware/rfsoc4x2.bin and x440.dtbo of this repository \
(fpga/build.sh impl, then fpga/tools/make_firmware.sh) into /lib/firmware, where \
MPM applies the overlay (product x440) and the FPGA manager loads the bitfile."
LICENSE = "LGPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/LGPL-3.0-or-later;md5=c51d3eef3be114124d11349ca0d7e117"

RFSOC4X2_FIRMWARE = "${TOPDIR}/../../../build/firmware"
SRC_URI = "file://${RFSOC4X2_FIRMWARE}/rfsoc4x2.bin \
           file://${RFSOC4X2_FIRMWARE}/x440.dtbo"
S = "${WORKDIR}"

do_install() {
    install -d ${D}${nonarch_base_libdir}/firmware
    install -m 0644 ${RFSOC4X2_FIRMWARE}/rfsoc4x2.bin ${D}${nonarch_base_libdir}/firmware/
    install -m 0644 ${RFSOC4X2_FIRMWARE}/x440.dtbo ${D}${nonarch_base_libdir}/firmware/
}
FILES:${PN} = "${nonarch_base_libdir}/firmware"
