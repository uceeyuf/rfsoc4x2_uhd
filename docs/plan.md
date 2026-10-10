# RFSoC 4x2 UHD Port: Plan

Goal: run the RFSoC 4x2 as a UHD device (`uhd_usrp_probe`, `multi_usrp`, GNU Radio) over
100 GbE, following the USRP X410 / X420 / X440 architecture of UHD 4.11.

* UHD: `uhd/` submodule, tag `v4.11.0.0` (0d7ed3b). Nothing in it is modified; any change
  that cannot live outside goes to `patches/`.
* Tools: Vivado 2023.2 (upstream X4xx uses 2021.1), PetaLinux 2023.2 on the board.

## Architecture

```text
host: UHD 4.11 (mpmd, DPDK) + rfsoc4x2 plugin (radio control)
  | 100 GbE (CHDR / UDP)                          | 1 GbE (MPM RPC)
  v                                               v
PL: CMAC -> rfnoc_ta_x4xx_eth -> RFNoC image core <- DMA (chdr_dma) <- PS: PetaLinux + MPM
        radio block x2 -> rfsoc4x2 RF core -> RFDC (ADC 224/226, DAC 228/230)
```

| | X410 / X440 | RFSoC 4x2 | Port |
|---|---|---|---|
| Device | xczu28dr-ffvg1517 (RFDC Gen1) | xczu48dr-ffvg1517-2-e (Gen3) | same PL resources; MPM's xrfdc handles IPType >= 2 |
| RF front end | ZBX (LO) / FBX (direct) | baluns, direct sampling | as X440: tune = RFDC NCO, gain = ADC DSA / DAC VOP |
| Channels | 8 RX / 8 TX | 4 RX (`vin0_01/23`, `vin2_01/23`) / 2 TX (`vout00`, `vout20`) | own image-core YAML (based on `x440_CG_400`) |
| Network | 2x QSFP28 | 1x QSFP28 (CMACE4_X0Y0, GT X0Y4..X0Y7, 156.25 MHz) | reuse `rfnoc_ta_x4xx_eth`; `eth_100g_bd` regenerated |
| Clocks | LMK04832 + LMK05318 | LMK04828 + 2x LMX2594 (SPI SS0..SS2) | MPM clock manager from `rfsoc4x2_mts` register sets |
| CPLDs, GPS, DIO, EEPROM | yes | no | register stubs in PL, removed from MPM |
| RFNoC device type | `X400` = 0xA400 | new type ID | own radio control registered for it (OOT plugin) |

Rates: start with a 400 MHz bandwidth image (master clock ~500 MS/s, RFDC internal DDC/DUC).
Four RX channels in `sc16` are ~64 Gbit/s, so the host uses DPDK (ConnectX-4).

## Repository layout (planned)

```text
uhd/          UHD v4.11.0.0 (submodule, unmodified)
fpga/         Vivado 2023.2: top, RF core, IP/BD Tcl for xczu48dr, image-core YAML, constraints
mpm/          periph_manager (rfsoc4x2.py), clocking, direct-sampling dboard
host/         out-of-tree UHD module: rfsoc4x2 radio control
linux/        PetaLinux 2023.2 project config, device tree, MPM recipe
docs/         notes and results
```

## Phases

0. Tool check: UHD RFNoC library under Vivado 2023.2. **Done** (2026-10-10):
   `fpga/tools/elab_check.sh` elaborates `chdr_stream_endpoint`, `rfnoc_block_radio`,
   `chdr_crossbar_nxn`, `eth_ipv4_interface_wrapper` (100 GbE widths) and
   `rfnoc_core_kernel` on xczu48dr without errors. Upstream X4xx BD scripts refuse to run
   outside 2021.1 (`scripts_vivado_version`), so all BD/IP are regenerated here.
   X440 PS+RFDC BD: upstream Tcl retargeted by `fpga/tools/bd_retarget.py` sources, validates
   and generates in 2023.2 on xczu28dr (IP upgrades fine).
1. FPGA: `rfsoc4x2.sv` with PS + RFDC BD, `eth_100g_bd`, `axi_eth_dma_bd`, radio/timekeeper
   from `x4xx_core`, image core from `rfnoc_image_builder`.
2. PetaLinux + MPM: periph manager (clocks, RFDC init and MTS, time sync), device tree.
3. Host plugin: radio control; `uhd_usrp_probe`, `rx/tx_samples_to_file`, `benchmark_rate`.
4. Results, README (EN + CN), citation.

## Status of phase 1 (2026-10-10)

* `fpga/ip/rfsoc4x2_ps_rfdc_bd/`: X440 BD + RFSoC 4x2 PS preset (`gen_ps_preset.py` from the
  board files: GEM1, SD0, UART1, SPI0 SS0..2 = LMK04828 / LMX2594). PS part applies.
* RFDC done (validates and generates on xczu48dr): 4.0 GS/s, x8 DDC/DUC, MCR 500 MS/s, fabric
  62.5 MHz; 500 MHz refclk on ADC 226 / DAC 230 only, PLLs distribute; all tiles enabled (SYSREF
  chain). ZU48DR DAC tiles 228..231 are dual (slices 0/2), so the X440 radio structure is kept:
  radio0 = ADC 224/225 + DAC 228/229, radio1 = ADC 226/227 + DAC 230/231, 4 ports each.
  Bonded: radio0 RX ports 0/1 = ADC_C/ADC_D, TX port 0 = DAC_A; radio1 RX 0/1 = ADC_A/ADC_B,
  TX 0 = DAC_B. Data clock MMCM input (pll_ref_clk) 125 MHz: LMK04828 output dividers (max 32)
  cannot make MCR/8 = 62.5 MHz.
* `bd_retarget.py --rfsoc4x2` appends the 4x2 RFDC settings to the X440 RFDC configuration and
  drops the 22 RFDC connections that do not exist on xczu48dr (rebuilt by the overlay).
* Next: the remaining X4xx IP (eth_100g_bd for the 4x2 QSFP28, DMA, AXI interconnects) in
  2023.2, then `rfsoc4x2.sv` (from `x4xx.sv`, X440 path, without CPLD / dboard / DIO / GPS).

## Prerequisites on the build host

* Python for `rfnoc_image_builder`: `python3-ruamel.yaml python3-mako python3-numpy`.
* UHD host build: `cmake libboost-all-dev libusb-1.0-0-dev pybind11-dev python3-dev`; DPDK
  (`libdpdk-dev` 23.11 present).
* PetaLinux 2023.2 installer only (no Yocto downloads / sstate needed online). Ubuntu 24.04 is
  not an official host: set `kernel.apparmor_restrict_unprivileged_userns=0` for bitbake.
