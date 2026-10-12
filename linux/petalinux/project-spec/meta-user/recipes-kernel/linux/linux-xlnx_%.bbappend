FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append = " file://bsp.cfg"
KERNEL_FEATURES:append = " bsp.cfg"

# nixge: deregister the fixed-link PHYs when the X4xx overlay is removed
# (every MPM restart leaked two fixed PHY addresses)
SRC_URI:append = " file://0001-net-nixge-deregister-the-fixed-link-PHY-on-overlay-removal.patch"
