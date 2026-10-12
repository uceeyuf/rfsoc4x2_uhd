#!/bin/bash
#
# Write the RFSoC 4x2 UHD image to an SD card (ERASES THE CARD):
#   partition 1: FAT32 "BOOT" 512 MB  (BOOT.BIN, boot.scr, Image, system.dtb)
#   partition 2: ext4 "rootfs", rest   (rootfs.ext4, grown to the partition)
#
#   sudo tools/make_sd.sh /dev/sdX [image dir]
#   image dir default: linux/petalinux/images/linux
#
set -e
DEV=$1
HERE=$(cd "$(dirname "$0")" && pwd)
IMG=${2:-$HERE/../linux/petalinux/images/linux}

die() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run with sudo"
# One instance at a time (a second one would erase the card being written)
exec 9>/run/rfsoc4x2_make_sd.lock
flock -n 9 || die "another make_sd.sh is running"
[ -b "$DEV" ] || die "usage: sudo $0 /dev/sdX   ($DEV is not a block device)"
[ "$(lsblk -dno TYPE "$DEV")" = disk ] || die "$DEV is not a whole disk"
for f in BOOT.BIN boot.scr Image system.dtb rootfs.ext4; do
  [ -f "$IMG/$f" ] || die "missing $IMG/$f"
done

# Safety: removable USB/MMC card, small, not holding the running system
TRAN=$(lsblk -dno TRAN "$DEV")
SIZE=$(lsblk -dnbo SIZE "$DEV")
case "$TRAN" in usb|mmc) ;; *) die "$DEV transport is '$TRAN', expected usb or mmc" ;; esac
[ "$SIZE" -lt $((128 * 1024 ** 3)) ] || die "$DEV is larger than 128 GB"
ROOTDISK=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" 2>/dev/null)
[ "/dev/$ROOTDISK" != "$DEV" ] || die "$DEV holds the running system"
if lsblk -nro MOUNTPOINTS "$DEV" | grep -qE '^/$|^/boot'; then die "$DEV has system mounts"; fi

echo "Target: $DEV  ($(lsblk -dno MODEL,SIZE,TRAN "$DEV"))"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
read -r -p "All data on $DEV will be erased. Type YES to continue: " ok
[ "$ok" = YES ] || die "aborted"

# Partition names: sda -> sda1, mmcblk0 -> mmcblk0p1
case "$DEV" in *[0-9]) P1=${DEV}p1; P2=${DEV}p2 ;; *) P1=${DEV}1; P2=${DEV}2 ;; esac

for p in $(lsblk -nro NAME "$DEV" | tail -n +2); do umount "/dev/$p" 2>/dev/null || true; done
wipefs -a "$DEV" >/dev/null
sfdisk -q "$DEV" <<EOF
label: dos
,512M,c,*
,,83
EOF
partprobe "$DEV"; udevadm settle; sleep 1

mkfs.vfat -F 32 -n BOOT "$P1" >/dev/null
echo "Writing rootfs ..."
dd if="$IMG/rootfs.ext4" of="$P2" bs=4M conv=fsync status=progress
e2fsck -fy "$P2" >/dev/null || true
resize2fs "$P2" >/dev/null
e2label "$P2" rootfs

MNT=$(mktemp -d)
mount "$P1" "$MNT"
cp "$IMG"/{BOOT.BIN,boot.scr,Image,system.dtb} "$MNT"/
sync
ls -l "$MNT"
umount "$MNT"; rmdir "$MNT"
sync
lsblk -o NAME,SIZE,FSTYPE,LABEL "$DEV"
echo "Done: $DEV is ready for the RFSoC 4x2 (boot mode switch: SD)."
