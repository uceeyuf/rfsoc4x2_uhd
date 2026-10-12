# gevent.events (imported by gevent.monkey.patch_all) needs zope.interface and
# zope.event; the meta-python recipe does not list them.
RDEPENDS:${PN} += "${PYTHON_PN}-zopeinterface ${PYTHON_PN}-zope-event"
