# RFSoC 4x2 UHD: board bring-up

Order of the build products and the first steps on the board. First run on the
board: 2026-10-12 (findings at the end).

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
- RFDC MTS (`sync_tiles`): SYSREF 2.5 MHz from LMK OUT3 / OUT9.

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

## 5. First board run (2026-10-12)

Working: boot, MPM init, clocks locked (LEDs PLL1/PLL2, ADC, DAC on), overlay,
`sfp0` 192.168.10.2 (100 GbE link up), `uhd_find_devices`, `uhd_usrp_probe`
(host: `host/build.sh`, MPM front-end PID 0x4F42), RX samples over UDP.

Fixed on the way:
- LMK04828: the RFSoC-MTS 500 MHz register set runs PLL1 as a 0-delay loop fed
  back from the SYSREF divider, so SYSREF_DIV and the CLKin R divider go
  together; CLKin1 (Si5395 10 MHz) is selected manually, Status_LD1/2 show the
  PLL1/PLL2 lock (`rfsoc4x2_clock_regs.py`). PLL1 takes tens of seconds to lock.
- MPM must not touch LMK_RST outside programming (`reset_clock`).
- `base_ref_clk` is divided from the PLL reference before the data clock MMCM:
  MPM runs the PLL sync while the MMCM is in reset.
- Xilinx kernel: the overlay fragment with `firmware-name` goes last; nixge
  ignores `local-mac-address` (MACs from `rfsoc4x2-net` .link files); fixed-link
  speed at most 1000; PetaLinux `80-wired.network` masked.
- MPM runtime: python3-netaddr, -gevent (+ zope.interface, zope.event), -systemd.
- ADC tiles 225 / 227 (not bonded out) stop in calibration: startup checks and
  MTS use tiles 0 / 2, reference tile 2 (MPM patch 0002).

MTS: the RFDC driver v6.0 bundled with MPM predates the Gen3 RFDC (DAC marker
location read without the Gen3 mask, DAC latencies of ~5e5; Gen1/2 delay
registers). MPM patch 0003 takes the MTS code of driver v12.1.

Loopback DAC_B -> ADC_D (radio0 port 0) and DAC_A -> ADC_B (radio1 port 0),
same timed 4096-sample QPSK burst on both DACs, NCOs at 1 GHz, 500 MS/s:
- delay difference between the two loops 0.0 +- 0.001 samples (< 1 ps) after
  every MPM restart (5 restarts) and every host session; correlation 0.97..0.99
  (0.68..0.82 on the DAC_A loop before the MTS fix, delay changing by a DAC
  sample between initializations);
- received spectrum inverted against the sent one (TX/RX NCO conventions);
  ADC_D inverted (balun) as known from rfsoc4x2_mts;
- phase difference between the loops: first one of 5 values 72 deg apart from
  one MPM start to the next. The X4xx daughterboard experts reset the NCOs
  after tuning (FPGA NCO reset on a SYSREF edge, timed); the RFSoC 4x2 front end
  of the host patch now does the same. With it: -178 +- 3 deg after every MPM
  restart (180 deg = ADC_D polarity).
- "Board 0 may not be getting a PPS signal" on host sync, after about half of
  the MPM starts: x4xx_pps_sync hands a one PRC cycle (125 MHz) PPS pulse to the
  62.5 MHz radio clock, which misses it on every other PRC cycle; which one
  depends on the base reference divider phase of each bitfile load. MPM
  (rfsoc4x2_clocking) uses PRC/RC divider 0 and moves the pulse by one PRC
  cycle when a timekeeper sees no PPS.

Open: spectral inversion / ADC_D polarity, common-mode loop delay toggling by
54 ps between MPM starts, DPDK streaming.
