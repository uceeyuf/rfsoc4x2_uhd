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

Two partitions: FAT32 `BOOT` (512 MB) and ext4 `rootfs`, written by
`tools/make_sd.sh` (checks that the target is a removable card, asks before
erasing):

```sh
sudo tools/make_sd.sh /dev/sdX
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

UHD 4.11 with `host/patches` (RFSoC 4x2 front end, MPM reports its PID 0x4F42):
`host/build.sh` builds it from a worktree of the submodule and installs to
`~/uhd-rfsoc4x2`. An unmodified UHD does not know the front end.

Network (direct cables):

| | host | board |
|---|---|---|
| data, 100 GbE (QSFP28) | 192.168.10.1/24, MTU 9000 | sfp0 192.168.10.2 |
| management, 1 GbE | 192.168.30.1/24 | eth0 192.168.30.2 (and DHCP) |

```sh
export LD_LIBRARY_PATH=~/uhd-rfsoc4x2/lib PATH=~/uhd-rfsoc4x2/bin:$PATH
uhd_find_devices --args addr=192.168.10.2
uhd_usrp_probe --args addr=192.168.10.2,mgmt_addr=192.168.30.2
host/tools/loopback_mts.py --args addr=192.168.10.2   # DAC_B->ADC_D, DAC_A->ADC_B
```

Full rate (500 MS/s per channel) needs DPDK, see section 6 and
`host/uhd-dpdk.conf`.

Channels: the X440 image has 4 ports per radio; the bonded converters
(identity RFDC mapping) are radio0 RX ports 0/1 = ADC_D/ADC_C, TX port 0 =
DAC_B; radio1 RX 0/1 = ADC_B/ADC_A, TX 0 = DAC_A, i.e. multi_usrp channels 0, 1
and 4, 5 (RX), 0 and 4 (TX). The other ports are converters that are not
bonded out ("NC"). Tuning sets the RFDC NCO (and the Nyquist zone); no gain
control. Master clock rate 500 MS/s, 400 MHz bandwidth.

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

- Spectral orientation (DC burst on the DACs at 1.0 GHz, ADC NCOs at 1.01 GHz):
  the ADC path comes out inverted in the first Nyquist zone, the DAC path
  upright. The host front end sets the FPGA I/Q swap from the Nyquist zone of
  the NCO frequency (RX swapped in odd zones counted from 1, TX in even ones).
- ADC_D (inverted balun): 179.999 deg NCO phase offset set by MPM (patch 0004,
  the driver accepts -180 < offset < 180).

Second Nyquist zone (3 GHz, MPM set_if sets the RFDC Nyquist zone): the DC
tone test gives the right orientation (RX not swapped, TX swapped); loopback
delay difference -52 ps, phase -1.9 deg, correlation 0.7 (no filters: the DAC
image at 3 GHz and its fundamental at 1 GHz alias onto each other in the ADC).

Result after a fresh boot: delay difference +0.2 ps, phase difference +0.9 deg,
correlation 0.97 on both loops, same in every session.

Known: every MPM restart (overlay removed and applied again) leaks the two
fixed-link PHYs of the nixge ports; after about 15 restarts in one boot the
nixge probe fails with -ENOSPC (no sfp0). Reboot the board.

## 6. Full-rate streaming (DPDK)

Host UHD built against DPDK 24.11 (`~/dpdk`; Ubuntu's 23.11 gives a
ConnectX-4 without DevX one receive descriptor), configuration in
`host/uhd-dpdk.conf`, run as root with hugepages. DPDK takes over all traffic
of the QSFP28 port, so the MPM RPC goes over the 1 GbE ports: host
192.168.30.1 <-> eth0 192.168.30.2 (rfsoc4x2-net: static address next to DHCP).

- The kernel reports the nixge fixed-link speed (1000) for sfp0; MPM passed it
  on as the link rate, and UHD used 1 GbE frames (1500 bytes, 352 samples) and
  buffers. MPM (Rfsoc4x2XportMgrUDP) reports 100000 Mb/s for sfp0.
  With the 1 GbE rate UHD also capped the MTU discovery at 1500 bytes; now it
  finds 8016 (1984 samples per packet), no `force_mtu` needed.

benchmark_rate, 500 MS/s, 10 s: 1 x RX: 4999912264 samples, no drops; 2 x RX +
2 x TX (64 Gb/s): no drops, no overruns, 6 underruns at the start of TX.

Open: common-mode loop delay toggling by 54 ps between MPM starts, fixed-link
PHY leak.
