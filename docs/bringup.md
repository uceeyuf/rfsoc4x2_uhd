# RFSoC 4x2 UHD: board bring-up

Order of the build products and the first steps on the board. Nothing below has
been run on hardware yet (status in `docs/plan.md`).

## 1. Build

```sh
fpga/build.sh impl 2                       # Vivado 2023.2, ~2.5 h, peak ~23 GB
cd linux/petalinux
petalinux-config --get-hw-description ../../build/rfsoc4x2/rfsoc4x2.xsa --silentconfig
cd ../..
fpga/tools/make_firmware.sh                # build/firmware/rfsoc4x2.bin, x440.dtbo
cd linux/petalinux
petalinux-build                            # kernel, rootfs with MPM and the firmware
petalinux-package --boot --fsbl images/linux/zynqmp_fsbl.elf --u-boot \
    --pmufw images/linux/pmufw.elf --force # BOOT.BIN without bitstream
```

Run long builds in a memory-limited scope, one at a time (Vivado and bitbake
together exceed 30 GB):

```sh
systemd-run --user --scope -p MemoryMax=24G fpga/build.sh impl 2
```

`make_firmware.sh` reads the RFDC driver configuration that the PetaLinux
device-tree generator writes for the XSA (`pl.dtsi`), so `petalinux-config` with
the new XSA comes first.

## 2. SD card

Two partitions: FAT32 `BOOT` (~512 MB) and ext4 `rootfs`.

```sh
cp images/linux/{BOOT.BIN,boot.scr,Image,system.dtb} /media/$USER/BOOT/
sudo dd if=images/linux/rootfs.ext4 of=/dev/sdX2 bs=4M conv=fsync   # check sdX first
```

## 3. First boot (serial console, UART1, 115200)

Expected: Linux with root on `/dev/mmcblk0p2`, `usrp-hwd` (MPM) starts.

| Check | Command | Expect |
|---|---|---|
| clock chips | `ls /dev/spidev*` | three spidev nodes (LMK04828, 2x LMX2594) |
| LMK GPIOs | `gpioinfo \| grep LMK` | `LMK_RST`, `LMK_CLK_IN_SEL0/1` |
| firmware | `ls /lib/firmware` | `rfsoc4x2.bin`, `x440.dtbo` |
| MPM | `journalctl -u usrp-hwd -b` | clocks programmed, overlay `x440` applied, FPGA `operating` |
| UIOs | `cat /sys/class/uio/uio*/maps/map0/name` | `mboard-regs`, `ctrlport-mboard-regs`, `rfdc-regs`, `misc-enet-*` |
| network | `ip link` | `eth0` (GEM1, 1 GbE), `sfp0` (100 GbE), `int0` (DMA) |

The LMK04828 must be programmed before the overlay is applied: FPGA_REFCLK
(125 MHz) clocks the data clock MMCM. MPM does this in `Rfsoc4x2ClockCtrl`.

Things most likely to need fixing on the first boot:
- `nixge` netdev names: `mpm/systemd/udev/x4xx/70-sfp-net.rules` matches the X4xx
  addresses, which the overlay keeps.
- LMK04828 lock readback (`ref_locked` sensor): if SPI readback is not available
  on this board, MPM reports locked and logs a warning once.
- RFDC MTS (`sync_tiles`): SYSREF 7.8125 MHz from LMK OUT3 / OUT9.

## 4. Host

UHD 4.11 (unmodified) on the host; the front ends report the X4xx debug
daughterboard PID, so the host drives them as inert front ends (streaming and
timed commands; no frequency/gain control until the host patch is in).

```sh
uhd_find_devices --args type=x4xx
uhd_usrp_probe --args addr=<eth0 IP>
uhd_rx_cfile -A RX1 ...                       # radio0 port 0 = ADC_D
```

Bonded converters (identity RFDC mapping): radio0 RX ports 0/1 = ADC_D/ADC_C,
TX port 0 = DAC_B; radio1 RX 0/1 = ADC_B/ADC_A, TX 0 = DAC_A. Master clock rate
500 MS/s (400 MHz bandwidth image), 100 GbE on the QSFP28 (host: ConnectX-4,
MTU 9000, DPDK for high rates).
