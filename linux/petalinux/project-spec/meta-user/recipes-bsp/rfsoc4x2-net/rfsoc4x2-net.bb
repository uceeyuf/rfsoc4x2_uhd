SUMMARY = "Network port setup of the RFSoC 4x2 (MAC addresses, networkd)"
DESCRIPTION = "systemd .link files for eth0 (GEM1), sfp0 (100 GbE) and int0 (DMA), \
and 80-wired.network (DHCP on every Ethernet port) masked so that the MPM \
.network files (sfp0 192.168.10.2, int0 169.254.0.1, eth0 DHCP) apply; \
eth0 also gets the static management address 192.168.30.2/24. \
The interface names come from the MPM udev rules."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://10-rfsoc4x2-eth0.link \
           file://10-rfsoc4x2-sfp0.link \
           file://10-rfsoc4x2-int0.link \
           file://10-rfsoc4x2-eth0-mgmt.conf"
S = "${WORKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/systemd/network
    install -m 0644 ${WORKDIR}/10-rfsoc4x2-*.link ${D}${sysconfdir}/systemd/network/
    # Static management address on eth0 next to DHCP (drop-in for MPM eth0.network)
    install -d ${D}${sysconfdir}/systemd/network/eth0.network.d
    install -m 0644 ${WORKDIR}/10-rfsoc4x2-eth0-mgmt.conf ${D}${sysconfdir}/systemd/network/eth0.network.d/
    # 80-wired.network sorts before eth0/int0/sfp0.network and would win
    ln -sf /dev/null ${D}${sysconfdir}/systemd/network/80-wired.network
}
FILES:${PN} = "${sysconfdir}/systemd/network"
