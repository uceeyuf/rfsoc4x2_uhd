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
  Bonded (RFSoC 4x2 reference manual): radio0 RX ports 0/1 = ADC_D/ADC_C (tile 224 ch0/ch1),
  TX port 0 = DAC_B (228); radio1 RX 0/1 = ADC_B/ADC_A (226 ch0/ch1), TX 0 = DAC_A (230).
* Clocking (RFSoC 4x2 reference manual, Fig. 5): LMK04828 OUT8 = FPGA_REFCLK, OUT9 = PL SYSREF,
  OUT3 = RFDC analog SYSREF (DAC 230), OUT0 / OUT4 = LMX2594 references (ADC LMX: A -> 226,
  B -> 224; DAC LMX: A -> 230, B -> 228), OUT1 / OUT5 = LMX SYNC. Starting from the
  `rfsoc4x2_mts` register set (VCO 3000 MHz, all DCLK dividers 6 = 500 MHz):
  * DCLKout8 divider 6 -> 24 (reg 0x120: 0x66 -> 0x78): FPGA_REFCLK 125 MHz, the data clock MMCM
    input and pll_ref_clk (same frequency, as on the X440, so the PL SYSREF capture phase is fixed).
  * SYSREF_DIV 600 -> 1200 (reg 0x13A/0x13B: 0x02/0x58 -> 0x04/0xB0): 2.5 MHz, divides the
    62.5 MHz RFDC stream clocks (5 MHz does not). PLL1 is a 0-delay loop fed back from the SYSREF
    divider, so the CLKin R dividers go from 2 to 4 with it (reg 0x154/0x156), and CLKin1 (Si5395
    10 MHz) is selected manually (reg 0x147: 0x4A -> 0x1A); Status_LD1/2 (LEDs PLL1/PLL2) show the
    PLL1/PLL2 lock (reg 0x15F/0x16E). A first attempt with SYSREF_DIV 384 alone left PLL1
    unlocked (board bring-up, 2026-10-12).
  Radio clocks 62.5 / 125 MHz; base reference (PPS) = pll_ref_clk / 5 = 25 MHz (BUFGCE_DIV).
  First synthesis with a 500 MHz MMCM input failed timing on SYSREF_FABRIC (2 ns requirement).
* `bd_retarget.py --rfsoc4x2` appends the 4x2 RFDC settings to the X440 RFDC configuration and
  drops the 22 RFDC connections that do not exist on xczu48dr (rebuilt by the overlay).
* Other BDs (eth_100g, axi_eth_dma, axi_interconnect_{eth,dma,app}) regenerate in 2023.2
  (`regen_bds.sh`); the X4xx QSFP0 CMAC/GT settings equal the 4x2's (CMACE4_X0Y0 LOC override).
* RFNoC image: `fpga/rfsoc4x2_CG_400_rfnoc_image_core.yml`, BSP `fpga/rfnoc/core/rfsoc4x2_bsp.yml`
  (X440 I/O ports kept so `x4xx_core.v` is reused), `fpga/tools/rfnoc_image_builder.py` (runs the
  submodule's builder with a package-data overlay).
* Top: `fpga/rfsoc4x2.sv` generated by `fpga/tools/make_top.py` from the X440 path of `x4xx.sv`.
* Build: `fpga/build.sh rtl|synth|impl` (non-project Tcl, X440 source list from the upstream
  makefiles, retargeted BDs, `constraints/{pins,timing}/rfsoc4x2.xdc`).

## FPGA build result (2026-10-10)

`fpga/build.sh impl 2` (Vivado 2023.2, project mode, ~2.5 h, peak 23 GB): `build/rfsoc4x2/rfsoc4x2.bit`
and `rfsoc4x2.xsa`. All timing constraints met: WNS +0.217 ns, WHS +0.010 ns, WPWS +0.448 ns.
Utilization: LUT 56 %, FF 46 %, BRAM 16 %, URAM 45 %, DSP 12 %. CMAC at CMACE4_X0Y0, GTY X0Y4..X0Y7
(QSFP lanes AA38/W38/U38/R38, refclk AA33). Not tested on the board yet.

Vivado 2023.2 issues in the upstream sources, fixed by `fpga/patches/uhd/` (applied to copies):
* 0001 `eth_ipv4_chdr_adapter.sv`: 2023.2 evaluates the `axi4s_fifo` parameter assertions (TKEEP).
* 0002 `eth_100g.sv`: a hierarchical reference into the out-of-context CMAC made synthesis tie the
  GT pins to constants (the MAC was then removed by opt_design without an error; only the
  bitstream DRC on the unplaced QSFP ports caught it).
CMAC "evaluation license" warning: feature cmac_an_lt (AN/LT not included), same as in
`rfsoc4x2_100g_udp`; harmless.

## Status 2026-10-11 (not tested on the board)

* FPGA (identity RFDC mapping, RFDC info memory for xczu48dr): timing met, WNS +0.256 ns,
  WHS +0.009 ns; peak 24 GB in the 24 GB scope (at the limit).
* PetaLinux 2023.2 image: BOOT.BIN, kernel, ext4 rootfs with MPM (x4xx + rfsoc4x2 classes,
  gRPC stubs, pybind module, usrp-hwd service), `/lib/firmware/{rfsoc4x2.bin,x440.dtbo}`, udev
  and networkd files. Target Python 3.10.
* The RFDC param-list in the overlay is converted from the PetaLinux DTG output (v12.1) to the
  v6.0 layout of MPM's xrfdc; the hand-written values had several DAC fields wrong.
* MPM classes import on the host with stubbed target modules; clock policy checked.
* Host: RFSoC 4x2 front-end patch (NCO tuning, PID 0x4F42); MPM still reports 0x4001 (debug
  dboard) so an unmodified UHD 4.11 host can be used first. UHD 4.11 host needs protobuf/gRPC.
* PetaLinux on Ubuntu 24.04: pseudo-native had to be built without glibc 2.38 C23 redirects
  (`meta-user/recipes-devtools/pseudo`), otherwise every fakeroot task fails.

## Prerequisites on the build host

* Python for `rfnoc_image_builder`: `python3-ruamel.yaml python3-mako python3-numpy`.
* UHD host build: `cmake libboost-all-dev libusb-1.0-0-dev pybind11-dev python3-dev libprotobuf-dev
  protobuf-compiler libgrpc++-dev protobuf-compiler-grpc`; DPDK
  (`libdpdk-dev` 23.11 present).
* PetaLinux 2023.2 installer only (no Yocto downloads / sstate needed online). Ubuntu 24.04 is
  not an official host: set `kernel.apparmor_restrict_unprivileged_userns=0` for bitbake.
