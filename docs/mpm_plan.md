# MPM on the RFSoC 4x2: plan

Survey of UHD v4.11.0.0 MPM (`uhd/mpm`) for running the X4xx MPM on the RFSoC 4x2. Paths are
relative to `uhd/mpm/python/usrp_mpm/` unless noted.

## Keep `MPM_DEVICE=x4xx`

Discovery reports `type=<MPM_DEVICE>` (`discovery.py:58-69`) and the host accepts only
`n3xx`, `e3xx`, `x4xx` (`host/lib/usrp/mpmd/mpmd_devices.hpp:19`). The 4x2 periph manager is a
subclass of `x4xx` selected inside the x4xx build.

## Blockers found

| Area | X440 behaviour | RFSoC 4x2 | Plan |
|---|---|---|---|
| MB EEPROM | TLV via DT symbol `mb_eeprom`; product from PID (`x4xx.py:249,454`) | none | synthetic `_eeprom_head` (PID of the X440 so `product="x440"`), serial from DNA / mpm.conf |
| MB CPLD | spidev `mb_cpld` signature check (`x4xx_mb_cpld.py:242-275`); ctrlport CPLD signature in `CtrlportRegs` (`x4xx_periphs.py:451-506`) | none | stub CPLD control; `CtrlportRegs` without the signature check |
| Clock chips | LMK04832 (spidev `spll`), LMK03328 (I2C `rpll_i2c`), aux board LMK05318 | LMK04828 + 2x LMX2594 on PS SPI0 SS0..2 | fixed register-file loader (`rfsoc4x2_mts` sets; SYSREF_DIV 384) |
| Clock policy | `X440ClockPolicy` computes LMK/MMCM per MCR; `MMCM_INPUT_MAX = 64e6` | MMCM input 500 MHz, one MCR (500e6) | fixed table policy like `X410ClockPolicy`, `mmcm_use_defaults=True` (keeps the bitfile MMCM) |
| RFDC PLL | `configure_pll` per converter (`XRFdc_DynamicPLLConfig`) | PLLs only on ADC 226 / DAC 230, distributed | override `configure` to skip `configure_pll` (keep the IP's power-on clocking) |
| RFDC driver | bundled xrfdc v6.0 (embeddedsw 2019.1); `param-list` in the v6.0 `XRFdc_Config` layout (`mpm/include/mpm/rfdc/xrfdc.h:498-547`) | PetaLinux 2023.2 DTG emits the newer layout | build the `param-list` for v6.0 ourselves (or update the bundled driver); verify Gen3 support |
| MTS | requires ADC 0/0 and DAC 0/0 enabled (`x4xx_rfdc_ctrl.py:247-250`) | all tiles enabled | OK |
| Dboards | PID from `db[01]_eeprom`; FBX host code talks to FBX CPLD via ctrlport | no dboards | new MPM dboard class (from `EmptySlot`) with the mixin RPCs; host dboard class via `patches/` |
| Host with 0 dboards | `null_dboard`, returns before tick-rate setup (`host/lib/usrp/x400/x400_radio_control.cpp:58-65`) | | must report two dboards |
| QSFP | GPIO `QSFPn_MODPRS`/`MODSEL_n`, I2C `qsfpN_i2c` 0x50 | QSFP0 only; sideband driven by the PL | drop QSFP management or only read the module EEPROM |
| GPIO lines | `RFDC_POWERED`, `DB{n}_PWR_*`, `CLKAUX_*`, ... by line name | none | drop |

## Board image (PetaLinux 2023.2) must provide

1. Base device tree built with `-@` (`__symbols__`), an fpga-region labelled `fpga_full`,
   `CONFIG_OF_OVERLAY` and the Xilinx overlay configfs.
2. `/lib/firmware/x440.dtbo` (from the image builder `device_tree.dts`) and the bitfile named by
   `firmware-name` (`fpga/dts/rfsoc4x2-fpga.dtsi`: `rfsoc4x2.bin`; keep in sync with the
   overlay name MPM applies, `<product>.dtbo`).
3. UIOs `compatible = "usrp-uio"` bound to `uio_pdrv_genirq` (e.g. `uio_pdrv_genirq.of_id=usrp-uio`)
   with `reg-names` `mboard-regs`, `ctrlport-mboard-regs`, `rfdc-regs`, `misc-enet-regs0`,
   `misc-enet-int-regs`.
4. RFDC node `usp_rf_data_converter@1000100000`, not claimed by another driver (libmetal).
5. `nixge` driver (`ni,xge-enet-3.00`) for the 100 GbE and internal (DMA) netdevs, renamed to
   `sfp0` / `int0` (`mpm/systemd/udev/x4xx/70-sfp-net.rules`), `local-mac-address` instead of the
   EEPROM nvmem cell, `nft`.
6. spidev for SPI0 SS0..2 (LMK04828, LMX2594 x2).
7. Python 3 with pyudev, gpiod, grpcio/protobuf, pyroute2, mako (build); libmetal, Boost, udev;
   `usrp-hwd.service`, `/etc/uhd/mpm.conf`.

## New files

- `mpm/periph_manager/rfsoc4x2.py`: `x4xx` subclass (EEPROM, peripherals, dboard infos, sensors).
- `mpm/periph_manager/rfsoc4x2_clock.py`: LMK04828/LMX2594 loader + fixed clock policy.
- `mpm/dboard_manager/rfsoc4x2_db.py`: direct-sampling dboard (no hardware): MCR, sample rate,
  PRC rate, IQ swap, data path, RFDC rate sensor, NCO via the MB RFDC control.
- `patches/`: host dboard for that PID in `x400_radio_control.cpp` (NCO tuning, DSA/VOP gain).
