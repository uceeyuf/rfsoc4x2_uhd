#
# Copyright 2026 Yijie Yu
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""RFSoC 4x2 clocking for the X4xx MPM.

The X4xx clock manager (X4xxClockManager) sequences the clocks through two
objects: a clock control (the clock chips) and a clock policy (which master
clock rates exist and how to get there). The RFSoC 4x2 provides its own:

- Rfsoc4x2ClockCtrl: LMK04828 + 2x LMX2594 on PS SPI0, loaded with fixed
  register sets (rfsoc4x2_clock_regs). No reference PLL (RPLL), no base
  reference clock switch, no CPLD.
- Rfsoc4x2ClockPolicy: one master clock rate, 500 MS/s (converters at
  4.0 GS/s, x8 DDC/DUC), as built into the FPGA image; the data clock MMCM
  keeps its bitfile configuration.
"""

import time

from usrp_mpm import lib  # Pulls in everything from C++-land
from usrp_mpm.periph_manager import x4xx_clock_mgr
from usrp_mpm.periph_manager.rfsoc4x2_clock_regs import (
    FPGA_REFCLK_FREQ,
    LMK04828_REGS,
    LMX2594_OUT_FREQ,
    LMX2594_REGS,
    SYSREF_FREQ,
)
from usrp_mpm.periph_manager.x4xx_clock_ctrl import X4xxClockCtrl
from usrp_mpm.periph_manager.x4xx_clock_policy import (
    RfdcConfig,
    SpllConfig,
    X4xxClockConfig,
    X4xxClockPolicy,
)
from usrp_mpm.periph_manager.x4xx_clock_types import Spll1Vco
from usrp_mpm.periph_manager.x4xx_periphs import MboardRegsControl
from usrp_mpm.sys_utils.gpio import Gpio
from usrp_mpm.sys_utils.udev import dt_symbol_get_spidev

# Device tree labels of the spidev nodes (linux/petalinux .../system-user.dtsi)
LMK04828_LABEL = "lmk04828"
LMX2594_LABELS = ("lmx2594_adc", "lmx2594_dac")

MCR = 500e6  # Master clock rate (MS/s) of the FPGA image
CONVERTER_RATE = 4.0e9
RESAMPLING = 8  # RFDC DDC/DUC factor
RADIO_SPC = 8  # Samples per radio clock cycle
PRC_RATE = FPGA_REFCLK_FREQ  # PLL reference clock (pll_ref_clk) into the FPGA


class Rfsoc4x2ClockCtrl(X4xxClockCtrl):
    """Clock chips of the RFSoC 4x2.

    Keeps the X4xxClockCtrl interface (as used by X4xxClockManager); the
    motherboard-register functions (PPS forwarding, PLL sync trigger) are
    inherited unchanged.
    """

    # LMK04828 readback registers: [1] = PLLx lock detect
    LMK_RB_PLL1_LD = 0x182
    LMK_RB_PLL2_LD = 0x183

    def __init__(self, log):  # pylint: disable=super-init-not-called
        self.log = log.getChild("ClkCtrl")
        self._cpld_control = None
        self.mboard_regs_control = None  # Set from outside (finalize_init)
        self.spll_unlock_event = False
        self._lmk = None
        self._lmx = []
        self._lmk_rst = None
        self._lmk_clk_in_sel = []
        self._lock_readback_ok = None
        self._init_clk_peripherals()

    def _init_clk_peripherals(self):
        """SPI register interfaces of the clock chips and the LMK control GPIOs."""
        # LMK04828: 24-bit words [23] R/W, [20:8] address, [7:0] data, SPI mode 0
        self._lmk = lib.spi.make_spidev_regs_iface(
            dt_symbol_get_spidev(LMK04828_LABEL),
            1000000,  # Speed (Hz)
            0x0,  # SPI mode
            8,  # Addr shift
            0,  # Data shift
            1 << 23,  # Read flag
            0,  # Write flag
        )
        # LMX2594: 24-bit words [23] R/W, [22:16] address, [15:0] data
        self._lmx = [
            lib.spi.make_spidev_regs_iface(
                dt_symbol_get_spidev(label), 1000000, 0x0, 16, 0, 1 << 23, 0
            )
            for label in LMX2594_LABELS
        ]
        self._lmk_rst = Gpio("LMK_RST", Gpio.OUTPUT, 0)
        # CLKin select 0/0, as in the RFSoC 4x2 reference designs
        self._lmk_clk_in_sel = [
            Gpio("LMK_CLK_IN_SEL0", Gpio.OUTPUT, 0),
            Gpio("LMK_CLK_IN_SEL1", Gpio.OUTPUT, 0),
        ]

    def _program_lmk(self):
        self._lmk_rst.set(1)
        time.sleep(0.001)
        self._lmk_rst.set(0)
        time.sleep(0.001)
        for word in LMK04828_REGS:
            self._lmk.poke8((word >> 8) & 0x1FFF, word & 0xFF)

    def _program_lmx(self, lmx):
        lmx.poke16(0x00, 0x0002)  # RESET
        lmx.poke16(0x00, 0x0000)
        for word in LMX2594_REGS:
            lmx.poke16((word >> 16) & 0x7F, word & 0xFFFF)
        # R0 again after the VCO has settled: FCAL
        time.sleep(0.01)
        r0 = LMX2594_REGS[-1]
        lmx.poke16((r0 >> 16) & 0x7F, r0 & 0xFFFF)

    def reset_clock(self, value, clock_to_reset):
        """No-op: the LMK04828 is reset only right before it is programmed.

        X4xxClockManager.set_sync_source() asserts the "spll" reset and leaves
        it to a later config_spll(), which does not come when the clock
        settings are unchanged. LMK_RST clears every LMK04828 register, so
        holding or pulsing it here would leave the LMK in its power-on state
        (PLL1/PLL2 unlocked, PLL1/PLL2 LEDs off).
        """

    def config_rpll(self, internal_brc_source, ref_rate, internal_brc_rate, usr_clk_rate):
        """No reference PLL on the RFSoC 4x2."""

    def config_spll(self, pll_settings):
        """Program the LMK04828 (FPGA_REFCLK, SYSREF, LMX references) and both
        LMX2594s (RFDC reference clocks). The settings are fixed."""
        self.log.debug(
            "Programming LMK04828 (FPGA_REFCLK %.2f MHz, SYSREF %.4f MHz) and LMX2594 "
            "(%.1f MHz)",
            FPGA_REFCLK_FREQ / 1e6,
            SYSREF_FREQ / 1e6,
            LMX2594_OUT_FREQ / 1e6,
        )
        self._program_lmk()
        time.sleep(0.1)  # LMK PLL1/PLL2 lock
        for lmx in self._lmx:
            self._program_lmx(lmx)
        time.sleep(0.05)
        if not self.get_ref_locked():
            self.log.warning("LMK04828 reports no lock after programming.")

    def get_spll_freq(self):
        """RFDC PLL reference frequency (LMX2594 output)."""
        return LMX2594_OUT_FREQ

    def get_prc_rate(self):
        """PLL reference clock (FPGA_REFCLK) rate."""
        return PRC_RATE

    def select_brc_source(self, brc_src):
        """The base reference clock is derived in the FPGA (pll_ref_clk / 5)."""

    def sync_spll_clocks(self, pps_source, ref_clock_freq):
        """Select the internal 25 MHz PPS in the FPGA and run the PLL sync
        sequence of the motherboard registers. There is no LMK SYNC pin wired
        from the FPGA, so the LMK dividers are not touched."""
        if pps_source != "internal_pps":
            self.log.warning("Only the internal PPS exists on the RFSoC 4x2.")
        return self.mboard_regs_control.pll_sync_trigger(
            MboardRegsControl.CLOCK_CTRL_PPS_INT_25MHz
        )

    def _lmk_lock_bits(self):
        return (
            self._lmk.peek8(self.LMK_RB_PLL1_LD) & 0x2,
            self._lmk.peek8(self.LMK_RB_PLL2_LD) & 0x2,
        )

    def get_ref_locked(self):
        """LMK04828 PLL1 and PLL2 lock, if SPI readback works on this board.

        The LMX2594s report lock only on their MUXOUT pins (no readback here).
        """
        try:
            pll1, pll2 = self._lmk_lock_bits()
        except RuntimeError as ex:
            self.log.debug(f"LMK04828 readback failed: {ex}")
            return True
        if self._lock_readback_ok is None:
            # Readback disabled (SDO not driven) reads all 0 or all 1: report
            # locked, but say so once.
            raw = (self._lmk.peek8(self.LMK_RB_PLL1_LD), self._lmk.peek8(self.LMK_RB_PLL2_LD))
            self._lock_readback_ok = raw not in ((0x00, 0x00), (0xFF, 0xFF))
            if not self._lock_readback_ok:
                self.log.warning(
                    "LMK04828 lock readback not available (read %s); assuming locked.",
                    str(raw),
                )
        if not self._lock_readback_ok:
            return True
        return bool(pll1) and bool(pll2)

    def get_ref_stable(self):
        locked = self.get_ref_locked()
        self.spll_unlock_event = self.spll_unlock_event or not locked
        return locked

    def enable_ecpri_clocks(self, enable=True, clock="both"):
        """No eCPRI clock outputs."""

    def get_fpga_aux_ref_freq(self):
        """No FPGA_AUX_REF input."""
        return 0


class Rfsoc4x2ClockPolicy(X4xxClockPolicy):
    """One master clock rate: 500 MS/s at 4.0 GS/s, x8 DDC/DUC."""

    def __init__(self, args, log):
        super().__init__(args, log)
        self.log = log.getChild("ClkPolicy")
        self._dsp_info = None

    def set_dsp_info(self, dsp_info):
        self._dsp_info = dsp_info
        for idx, info in enumerate(dsp_info):
            if int(info.get("bw", 400)) != 400:
                self.log.warning(f"DSP {idx}: unexpected bandwidth {info.get('bw')} MHz")

    def get_default_mcr(self):
        return MCR

    def get_radio_clock_rate(self, mcr):
        return mcr / RADIO_SPC

    def get_num_rates(self):
        return 1

    def validate_ref_clock_freq(self, ref_clock_freq, master_clock_rates):
        """The LMK04828 runs from its on-board reference; nothing to check."""

    def get_intermediate_clk_settings(self, ref_clk_freq, old_mcrs, new_mcrs):
        return None

    def coerce_mcr(self, master_clock_rates):
        for mcr in master_clock_rates:
            if abs(mcr - MCR) > 1.0:
                raise ValueError(
                    f"Master clock rate {mcr / 1e6} MHz is not supported "
                    f"(RFSoC 4x2 image: {MCR / 1e6} MHz)."
                )
        return [MCR] * len(master_clock_rates)

    def get_config(self, ref_clock_freq, master_clock_rates):
        spll = SpllConfig(
            ref_freq=ref_clock_freq,
            output_freq=LMX2594_OUT_FREQ,
            output_divider=6,
            prc_divider=24,
            vcxo_freq=Spll1Vco.VCO100MHz,
            sysref_div=1200,
            clkin0_r_div=4,
            pll1_n_div=0,
            pll2_prescaler=0,
            pll2_n_cal_div=0,
            pll2_n_div=0,
            prc_to_db=False,
        )
        return X4xxClockConfig(
            spll_config=spll,
            rfdc_configs=[RfdcConfig(conv_rate=CONVERTER_RATE, resampling=RESAMPLING)] * 2,
            mmcm_use_defaults=True,
        )

    def should_reboot_on_reconfiguration(self):
        return False


class Rfsoc4x2ClockManager(x4xx_clock_mgr.X4xxClockManager):
    """X4xxClockManager with the RFSoC 4x2 clock control and policy."""

    def __init__(self, args, log):
        # X4xxClockManager.__init__ instantiates X4xxClockCtrl(cpld_control, log)
        # from its module namespace: substitute ours for the duration of the call.
        orig_ctrl = x4xx_clock_mgr.X4xxClockCtrl
        x4xx_clock_mgr.X4xxClockCtrl = lambda _cpld, log_: Rfsoc4x2ClockCtrl(log_)
        try:
            super().__init__(
                args,
                clk_policy=Rfsoc4x2ClockPolicy(args, log),
                clk_aux_board=None,
                cpld_control=None,
                log=log,
            )
        finally:
            x4xx_clock_mgr.X4xxClockCtrl = orig_ctrl

    # No clocking aux board: "mboard" (LMK04828 from the on-board TCXO) is the
    # only clock. "internal" (the X4xx default, and what hosts may ask for) is
    # accepted as the same thing.
    X400_DEFAULT_CLOCK_SOURCE = x4xx_clock_mgr.X4xxClockManager.CLOCK_SOURCE_MBOARD

    def _init_available_srcs(self):
        self._avail_clk_sources = [self.CLOCK_SOURCE_MBOARD, self.CLOCK_SOURCE_INTERNAL]
        self._avail_time_sources = [self.TIME_SOURCE_INTERNAL]

    def _config_rpll(self, usr_clk_rate, internal_brc_rate, internal_brc_source):
        """No reference PLL; the internal base reference is 25 MHz (FPGA)."""
        self._int_clock_freq = 25e6

    def get_ref_clock_freq(self):
        """Base reference clock: pll_ref_clk / 5 in the FPGA."""
        return 25e6
