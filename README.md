![语言](https://img.shields.io/badge/语言-SystemVerilog_+_Python_+_C%2B%2B-9A90FD.svg) ![接口](https://img.shields.io/badge/接口-UHD_4.11_/_100GbE-orange.svg) ![部署](https://img.shields.io/badge/部署-Vivado_/_PetaLinux_2023.2-FF1010.svg) ![板卡](https://img.shields.io/badge/板卡-RFSoC_4x2-blue.svg)

[English](#en) | [中文](#cn)

　

<span id="en">UHD for the RFSoC 4x2</span>
===========================

A UHD port for the RealDigital **RFSoC 4x2** (xczu48dr), modelled on the Ettus USRP **X410 / X420 / X440** architecture of UHD 4.11: an RFNoC FPGA image with 100 GbE (QSFP28) and DMA, the Module Peripheral Manager (MPM) on PetaLinux, and the standard `mpmd` host driver. The FPGA keeps the X440 register map and RFNoC device type, so UHD's X4xx code applies; the board-specific parts (RFDC on a Gen3 device, LMK04828 / LMX2594 clocking, no CPLDs or daughterboards) are replaced.

**Status (2026-10-13): running on the board.** Vivado 2023.2, all timing constraints met; PetaLinux 2023.2 with MPM; clocks locked (LMK04828 PLL1/PLL2, both LMX2594). Loopbacks DAC_B -> ADC_D and DAC_A -> ADC_B with multi-tile sync and NCO reset: delay difference below 1 ps, phase difference about 1 deg, the same after every boot.

Streaming over 100 GbE with the default image (DDC / DUC), 2 x RX + 2 x TX, 10 s each:

| Rate per channel | Host network stack | Result |
| :-- | :-- | :-- |
| up to 125 MS/s | kernel UDP, normal user | no drops, overruns or underruns |
| 250 MS/s | kernel UDP | no RX drops, a few TX underruns |
| 500 MS/s (64 Gb/s in total) | DPDK, as root | no drops, overruns or underruns |

Notes and open points: [docs/bringup.md](./docs/bringup.md).

　

## Quick start

Board: SD card from `tools/make_sd.sh` (PetaLinux image with MPM and the FPGA firmware). Cables: QSFP28 to the host's 100 GbE NIC, RJ45 (1 GbE) to the host for management.

| | host | board |
|---|---|---|
| data, 100 GbE | 192.168.10.1/24, MTU 9000 | sfp0 192.168.10.2 |
| management, 1 GbE | 192.168.30.1/24 | eth0 192.168.30.2 |

```sh
host/build.sh                                     # UHD 4.11 + host/patches -> ~/uhd-rfsoc4x2
export LD_LIBRARY_PATH=~/uhd-rfsoc4x2/lib PATH=~/uhd-rfsoc4x2/bin:$PATH
uhd_usrp_probe --args addr=192.168.10.2,mgmt_addr=192.168.30.2
~/uhd-rfsoc4x2/lib/uhd/examples/benchmark_rate --args addr=192.168.10.2,mgmt_addr=192.168.30.2 \
    --rx_rate 125e6 --rx_channels 0,4 --tx_rate 125e6 --tx_channels 0,4
host/tools/loopback_mts.py --args addr=192.168.10.2   # SMA DAC_B->ADC_D, DAC_A->ADC_B
```

multi_usrp channels: RX 0/1 = ADC_D/ADC_C, RX 4/5 = ADC_B/ADC_A, TX 0 = DAC_B, TX 4 = DAC_A. Sample rates: 500 MS/s / N (DDC / DUC). Tuning sets the RFDC NCO (and the Nyquist zone); there is no gain control (direct sampling). 500 MS/s per channel needs DPDK: `host/uhd-dpdk.conf`. Details: [docs/bringup.md](./docs/bringup.md).

　

## Design

| | X440 | RFSoC 4x2 |
| :-- | :-- | :-- |
| Device | xczu28dr (RFDC Gen1) | xczu48dr (RFDC Gen3) |
| Front end | FBX daughterboards | baluns, direct sampling |
| Image | 2 radios x 4 ports, 400 MHz | same structure; bonded: RX ports 0/1, TX port 0 of each radio, with RFNoC DDC / DUC on them (default image) |
| Converters | 4.096 GS/s, PLL per tile | 4.0 GS/s, x8 DDC/DUC, MCR 500 MS/s; PLLs of ADC 226 / DAC 230 distribute the clock |
| Network | 2x QSFP28 | 1x QSFP28, 100 GbE (CMAC X0Y0, GTY X0Y4..X0Y7) |
| Clocks | LMK04832, LMK03328, aux board | LMK04828 (FPGA_REFCLK 125 MHz, SYSREF 2.5 MHz), 2x LMX2594 (500 MHz) |
| MPM | x4xx | x4xx subclass `rfsoc4x2` (no EEPROM, CPLD, aux board; fixed clocking) |

Bonded converters: radio0 RX 0/1 = ADC_D/ADC_C, TX 0 = DAC_B; radio1 RX 0/1 = ADC_B/ADC_A, TX 0 = DAC_A.

* [fpga](./fpga): top level generated from the X440 path of `x4xx.sv` ([make_top.py](./fpga/tools/make_top.py)), PS + RFDC block design on top of the X440 one, RFNoC images ([rfsoc4x2_CG_400_DDC](./fpga/rfsoc4x2_CG_400_DDC_rfnoc_image_core.yml), default, and [rfsoc4x2_CG_400](./fpga/rfsoc4x2_CG_400_rfnoc_image_core.yml) without DDC / DUC), constraints, build ([build.sh](./fpga/build.sh)), patches for Vivado 2023.2 ([patches/uhd](./fpga/patches/uhd)).
* [mpm](./mpm): RFSoC 4x2 motherboard, clocking (LMK04828 / LMX2594 register sets), RFDC and front-end classes for the X4xx MPM; [patches](./mpm/patches) to the MPM in the submodule (multi-tile sync from the RFDC driver v12.1, settable MTS reference tile and NCO phase offset); RFDC driver configuration tool.
* [host](./host): [patches](./host/patches) for UHD on the host (RFSoC 4x2 front end: 4 ports per radio, NCO tuning and reset, I/Q orientation), [build.sh](./host/build.sh), DPDK configuration ([uhd-dpdk.conf](./host/uhd-dpdk.conf)), loopback test ([tools/loopback_mts.py](./host/tools/loopback_mts.py)).
* [linux/petalinux](./linux/petalinux): PetaLinux 2023.2 project (board device tree, kernel options and a nixge fix, MPM and its Python dependencies, firmware and network recipes); [tools/make_sd.sh](./tools/make_sd.sh) writes the SD card.
* [uhd](https://github.com/EttusResearch/uhd/tree/v4.11.0.0): UHD v4.11.0.0, unmodified submodule.
* [Plan](./docs/plan.md), [MPM notes](./docs/mpm_plan.md), [bring-up](./docs/bringup.md).

　

## Citation

If this work helps your research, please cite it:

```bibtex
@misc{yu2026rfsoc4x2_uhd,
    author = {Yijie Yu},
    title = {{UHD for the RFSoC 4x2}},
    year = {2026},
    howpublished = {\url{https://github.com/uceeyuf/rfsoc4x2_uhd}},
    note = {GitHub repository},
}
```

GitHub also offers the citation under **Cite this repository** (from [CITATION.cff](CITATION.cff)).

　

## Credits

* UHD, the X4xx FPGA, MPM and host code: [Ettus Research / NI](https://github.com/EttusResearch/uhd) (submodule, v4.11.0.0).
* RFSoC 4x2 board facts: RealDigital RFSoC 4x2 reference manual and [RFSoC4x2-BSP](https://github.com/RealDigitalOrg/RFSoC4x2-BSP); PS configuration from the RFSoC 4x2 board files (Xilinx, Apache-2.0).
* Clock register values: PYNQ RFSoC4x2 `LMK04828_500.0` / `LMX2594_500.0`, as used in [rfsoc4x2_mts](https://github.com/uceeyuf/rfsoc4x2_mts).
* 100 GbE settings: [rfsoc4x2_100g_udp](https://github.com/uceeyuf/rfsoc4x2_100g_udp).

　

## License

GPL-3.0-or-later ([LICENSE](LICENSE)); files derived from UHD keep their notices (FPGA sources LGPL-3.0-or-later, MPM GPL-3.0-or-later). UHD itself is a submodule under its own licenses.

This is an independent project, not affiliated with or endorsed by NI / Ettus Research, AMD / Xilinx or RealDigital. USRP, UHD and Ettus Research are trademarks of NI; RFSoC is a trademark of AMD; they are used here only to describe compatibility. No bitstreams are distributed: building the FPGA image needs Vivado and the (free) AMD license for the 100G Ethernet subsystem (CMAC).

　

　

<span id="cn">RFSoC 4x2 的 UHD</span>
===========================

为 RealDigital **RFSoC 4x2**（xczu48dr）移植 UHD，架构参照 UHD 4.11 中 Ettus USRP **X410 / X420 / X440**：RFNoC FPGA 镜像（100 GbE QSFP28 + DMA）、PetaLinux 上的 MPM，以及标准的 `mpmd` 主机驱动。FPGA 保留 X440 的寄存器映射和 RFNoC 设备类型，UHD 的 X4xx 代码可以直接复用；板级差异（第三代 RFDC、LMK04828 / LMX2594 时钟、没有 CPLD 和子板）单独替换。

**状态（2026-10-13）：已在板上运行。** Vivado 2023.2，时序全部满足；PetaLinux 2023.2 + MPM；时钟锁定（LMK04828 PLL1/PLL2 与两片 LMX2594）。DAC_B → ADC_D、DAC_A → ADC_B 两路回环在多 tile 同步与 NCO 复位后，时延差小于 1 ps，相位差约 1°，每次开机都一致。

默认镜像（带 DDC / DUC）经 100 GbE 收发，2 路 RX + 2 路 TX，每项 10 秒：

| 每路速率 | 主机网络 | 结果 |
| :-- | :-- | :-- |
| 125 MS/s 及以下 | 内核 UDP，普通用户 | 无丢包、溢出、欠载 |
| 250 MS/s | 内核 UDP | RX 无丢包，TX 少量欠载 |
| 500 MS/s（合计 64 Gb/s） | DPDK，root | 无丢包、溢出、欠载 |

上板记录与待办见 [docs/bringup.md](./docs/bringup.md)。

　

## 快速上手

板子：用 `tools/make_sd.sh` 写 SD 卡（含 MPM 与 FPGA 固件的 PetaLinux 镜像）。连线：QSFP28 接主机的 100 GbE 网卡，RJ45（1 GbE）接主机作管理口。

| | 主机 | 板子 |
|---|---|---|
| 数据，100 GbE | 192.168.10.1/24，MTU 9000 | sfp0 192.168.10.2 |
| 管理，1 GbE | 192.168.30.1/24 | eth0 192.168.30.2 |

```sh
host/build.sh                                     # UHD 4.11 + host/patches -> ~/uhd-rfsoc4x2
export LD_LIBRARY_PATH=~/uhd-rfsoc4x2/lib PATH=~/uhd-rfsoc4x2/bin:$PATH
uhd_usrp_probe --args addr=192.168.10.2,mgmt_addr=192.168.30.2
~/uhd-rfsoc4x2/lib/uhd/examples/benchmark_rate --args addr=192.168.10.2,mgmt_addr=192.168.30.2 \
    --rx_rate 125e6 --rx_channels 0,4 --tx_rate 125e6 --tx_channels 0,4
host/tools/loopback_mts.py --args addr=192.168.10.2   # SMA 回环 DAC_B->ADC_D、DAC_A->ADC_B
```

multi_usrp 通道：RX 0/1 = ADC_D/ADC_C，RX 4/5 = ADC_B/ADC_A，TX 0 = DAC_B，TX 4 = DAC_A。采样率：500 MS/s / N（DDC / DUC）。调频即设置 RFDC 的 NCO（及奈奎斯特区）；直采没有增益控制。每路 500 MS/s 需要 DPDK：见 `host/uhd-dpdk.conf`。详细说明见 [docs/bringup.md](./docs/bringup.md)。

　

## 设计

| | X440 | RFSoC 4x2 |
| :-- | :-- | :-- |
| 器件 | xczu28dr（第一代 RFDC） | xczu48dr（第三代 RFDC） |
| 前端 | FBX 子板 | 巴伦直采 |
| 镜像 | 2 个 radio × 4 口，400 MHz | 结构相同；引出的是每个 radio 的 RX 口 0/1、TX 口 0，其上接 RFNoC DDC / DUC（默认镜像） |
| 转换器 | 4.096 GS/s，每个 tile 单独 PLL | 4.0 GS/s，8 倍 DDC/DUC，MCR 500 MS/s；ADC 226 / DAC 230 的 PLL 分发时钟 |
| 网络 | 2 个 QSFP28 | 1 个 QSFP28，100 GbE（CMAC X0Y0，GTY X0Y4..X0Y7） |
| 时钟 | LMK04832、LMK03328、扩展板 | LMK04828（FPGA_REFCLK 125 MHz，SYSREF 2.5 MHz），2 片 LMX2594（500 MHz） |
| MPM | x4xx | x4xx 子类 `rfsoc4x2`（无 EEPROM、CPLD、扩展板；固定时钟） |

引出的转换器：radio0 RX 0/1 = ADC_D/ADC_C，TX 0 = DAC_B；radio1 RX 0/1 = ADC_B/ADC_A，TX 0 = DAC_A。

* [fpga](./fpga)：由 `x4xx.sv` 的 X440 路径生成的顶层（[make_top.py](./fpga/tools/make_top.py)）、基于 X440 的 PS + RFDC block design、RFNoC 镜像（默认 [rfsoc4x2_CG_400_DDC](./fpga/rfsoc4x2_CG_400_DDC_rfnoc_image_core.yml)，以及不带 DDC / DUC 的 [rfsoc4x2_CG_400](./fpga/rfsoc4x2_CG_400_rfnoc_image_core.yml)）、约束、构建脚本（[build.sh](./fpga/build.sh)）、Vivado 2023.2 所需补丁（[patches/uhd](./fpga/patches/uhd)）。
* [mpm](./mpm)：X4xx MPM 的 RFSoC 4x2 主板、时钟（LMK04828 / LMX2594 寄存器表）、RFDC 和前端类；对子模块中 MPM 的[补丁](./mpm/patches)（采用 RFDC 驱动 v12.1 的多 tile 同步、可设置的 MTS 参考 tile 与 NCO 相位偏移）；RFDC 驱动配置工具。
* [host](./host)：主机端 UHD 的[补丁](./host/patches)（RFSoC 4x2 前端：每个 radio 4 口、NCO 调频与复位、I/Q 方向）、[build.sh](./host/build.sh)、DPDK 配置（[uhd-dpdk.conf](./host/uhd-dpdk.conf)）、回环测试（[tools/loopback_mts.py](./host/tools/loopback_mts.py)）。
* [linux/petalinux](./linux/petalinux)：PetaLinux 2023.2 工程（板级设备树、内核选项与 nixge 修复、MPM 及其 Python 依赖、固件与网络配方）；[tools/make_sd.sh](./tools/make_sd.sh) 写 SD 卡。
* [uhd](https://github.com/EttusResearch/uhd/tree/v4.11.0.0)：UHD v4.11.0.0，未修改的子模块。
* [计划](./docs/plan.md)、[MPM 说明](./docs/mpm_plan.md)、[上板步骤](./docs/bringup.md)。

　

## 引用

如果这个项目对你的研究有帮助，请引用：

```bibtex
@misc{yu2026rfsoc4x2_uhd,
    author = {Yijie Yu},
    title = {{UHD for the RFSoC 4x2}},
    year = {2026},
    howpublished = {\url{https://github.com/uceeyuf/rfsoc4x2_uhd}},
    note = {GitHub repository},
}
```

GitHub 仓库页的 **Cite this repository** 也提供同样的引用（来自 [CITATION.cff](CITATION.cff)）。

　

## 致谢

* UHD、X4xx FPGA、MPM 与主机代码：[Ettus Research / NI](https://github.com/EttusResearch/uhd)（子模块 v4.11.0.0）。
* RFSoC 4x2 板级信息：RealDigital RFSoC 4x2 参考手册与 [RFSoC4x2-BSP](https://github.com/RealDigitalOrg/RFSoC4x2-BSP)；PS 配置来自 RFSoC 4x2 板卡文件（Xilinx，Apache-2.0）。
* 时钟寄存器值：PYNQ RFSoC4x2 `LMK04828_500.0` / `LMX2594_500.0`，经 [rfsoc4x2_mts](https://github.com/uceeyuf/rfsoc4x2_mts) 验证。
* 100 GbE 设置：[rfsoc4x2_100g_udp](https://github.com/uceeyuf/rfsoc4x2_100g_udp)。

　

## 许可证

GPL-3.0-or-later（[LICENSE](LICENSE)）；源自 UHD 的文件保留原有声明（FPGA 源码 LGPL-3.0-or-later，MPM GPL-3.0-or-later）。UHD 本身以子模块形式引入，遵循其自身许可证。

本项目为独立项目，与 NI / Ettus Research、AMD / Xilinx、RealDigital 均无关联，也未获其认可。USRP、UHD、Ettus Research 是 NI 的商标，RFSoC 是 AMD 的商标，此处仅用于说明兼容性。仓库不发布 bitstream：编译 FPGA 镜像需要 Vivado 以及 AMD 100G 以太网子系统（CMAC）的（免费）许可证。
