SUMMARY = "UHD Module Peripheral Manager (MPM, X4xx) for the RFSoC 4x2"
DESCRIPTION = "MPM from the UHD v4.11.0.0 submodule of this repository, built for \
MPM_DEVICE=x4xx with the RFSoC 4x2 motherboard, clocking, RFDC and front-end \
classes from mpm/ of this repository."
LICENSE = "GPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://${WORKDIR}/git/host/LICENSE;md5=8255adf1069294c928e0e18b01a16282"

# Repository root (linux/petalinux/build -> ../../..)
RFSOC4X2_REPO = "${TOPDIR}/../../.."

SRC_URI = "git://${RFSOC4X2_REPO}/uhd;protocol=file;nobranch=1 \
           file://${RFSOC4X2_REPO}/mpm/patches/0001-mpm-periph-manager-rfsoc4x2.patch;patchdir=${WORKDIR}/git \
           file://${RFSOC4X2_REPO}/mpm/patches/0002-mpm-rfdc-mts-ref-tile.patch;patchdir=${WORKDIR}/git \
           file://${RFSOC4X2_REPO}/mpm/patches/0003-mpm-rfdc-mts-driver-v12.patch;patchdir=${WORKDIR}/git \
          "
# UHD v4.11.0.0
SRCREV = "0d7ed3b1a4e301032b0c6b04799d7631c5098528"
S = "${WORKDIR}/git/mpm"

inherit cmake pkgconfig python3native systemd

DEPENDS = "boost libmetal udev systemd python3 protobuf-native grpc-native \
           python3-mako-native python3-setuptools-native"

RDEPENDS:${PN} = "python3-core python3-modules python3-pyudev python3-grpcio \
                  python3-netaddr python3-gevent python3-systemd \
                  python3-protobuf python3-pyroute2 libgpiod-python nftables \
                  libmetal boost-system bash"

EXTRA_OECMAKE = " \
    -DMPM_DEVICE=x4xx \
    -DPYTHON_EXECUTABLE=${PYTHON} \
    -DPYTHON_INCLUDE_DIRS=${STAGING_INCDIR}/${PYTHON_DIR} \
    -DUSRP_MPM_PYTHON_DIR=${PYTHON_SITEPACKAGES_DIR} \
    -DENABLE_TESTS=OFF \
"

# The RFSoC 4x2 Python classes (mpm/python/usrp_mpm in this repository)
do_configure:prepend() {
    for d in periph_manager dboard_manager; do
        cp ${RFSOC4X2_REPO}/mpm/python/usrp_mpm/$d/rfsoc4x2*.py ${S}/python/usrp_mpm/$d/
    done
}
do_configure[file-checksums] += "${@' '.join('%s:True' % f for f in __import__('glob').glob(d.getVar('RFSOC4X2_REPO') + '/mpm/python/usrp_mpm/*/rfsoc4x2*.py'))}"

SYSTEMD_SERVICE:${PN} = "usrp-hwd.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR} ${systemd_unitdir} ${nonarch_base_libdir}/udev \
                ${sysconfdir} ${libdir}/sysctl.d ${base_libdir}/systemd"
INSANE_SKIP:${PN} += "dev-so"
