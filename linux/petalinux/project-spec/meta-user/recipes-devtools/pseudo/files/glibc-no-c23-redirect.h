/*
 * Build pseudo-native without glibc >= 2.38's C23 redirects (strtol/sscanf/
 * fscanf -> __isoc23_*@GLIBC_2.38). Otherwise libpseudo.so, built against the
 * host glibc (2.39 on Ubuntu 24.04; uninative is disabled because it is older),
 * cannot be preloaded into PetaLinux's buildtools python (glibc 2.36) and every
 * fakeroot task fails with "Failed to spawn fakeroot worker ... Broken pipe".
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE   /* pseudo builds with it; features.h is evaluated once */
#endif
#include <features.h>
#undef __GLIBC_USE_C2X_STRTOL
#define __GLIBC_USE_C2X_STRTOL 0
#undef __GLIBC_USE_C23_STRTOL
#define __GLIBC_USE_C23_STRTOL 0
