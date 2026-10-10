# See files/glibc-no-c23-redirect.h
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append:class-native = " file://glibc-no-c23-redirect.h"
CFLAGS:append:class-native = " -include ${WORKDIR}/glibc-no-c23-redirect.h"
