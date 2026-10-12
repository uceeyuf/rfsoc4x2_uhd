SUMMARY = "Very basic event publishing system (zope.event), needed by gevent"
HOMEPAGE = "https://github.com/zopefoundation/zope.event"
LICENSE = "ZPL-2.1"
LIC_FILES_CHKSUM = "file://LICENSE.txt;md5=78ccb3640dc841e1baecb3e27a6966b2"

PYPI_PACKAGE = "zope.event"
SRC_URI[sha256sum] = "81d98813046fc86cc4136e3698fee628a3282f9c320db18658c21749235fce80"

inherit pypi setuptools3

RDEPENDS:${PN} = "${PYTHON_PN}-setuptools"
