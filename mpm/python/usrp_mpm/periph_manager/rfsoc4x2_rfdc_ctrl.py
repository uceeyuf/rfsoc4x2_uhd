#
# Copyright 2026 Yijie Yu
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""RFSoC 4x2 RFDC control.

The RFDC clocking of the RFSoC 4x2 image is fixed in the IP: the PLLs of ADC
tile 226 and DAC tile 230 generate 4.0 GS/s from 500 MHz and distribute it to
the other tiles. Reprogramming a PLL per tile (X4xxRfdcCtrl.configure calls
XRFdc_DynamicPLLConfig on every converter) would break that distribution, so
configure() here only sets the mixers, the decimation/interpolation and the NCO
event source.
"""

import itertools

from usrp_mpm.periph_manager.x4xx_rfdc_ctrl import CONV_OPTIONS, X4xxRfdcCtrl
from usrp_mpm.rpc_utils import no_rpc


class Rfsoc4x2RfdcCtrl(X4xxRfdcCtrl):
    """X4xxRfdcCtrl without RFDC PLL reconfiguration."""

    @no_rpc
    def configure(self, ref_freq, rfdc_configs):
        """Configure the converters (no PLL changes, see module docstring)."""
        converter_list = list(
            itertools.chain(
                map(lambda x: (x[1], x[0], CONV_OPTIONS["DAC"]), enumerate(self._dac_convs)),
                map(lambda x: (x[1], x[0], CONV_OPTIONS["ADC"]), enumerate(self._adc_convs)),
            )
        )
        for conv, _, conv_direction in converter_list:
            rfdc_config = rfdc_configs[conv.db]
            self._rfdc_ctrl.reset_mixer_settings(
                conv.tile, conv.block, conv_direction, conv.mode.value
            )
            fab_words = self._rfdc_regs.get_rfdc_info(conv.db).get(
                "spc_tx" if conv_direction is CONV_OPTIONS["DAC"] else "spc_rx"
            )
            self._set_interpolation_decimation(
                conv.tile, conv.block, conv_direction, rfdc_config.resampling, fab_words
            )
        self._rfdc_regs.log_status()
        for conv, _, conv_direction in converter_list:
            # RFDC NCO reset event source: analog SYSREF
            self._rfdc_ctrl.set_nco_event_src(conv.tile, conv.block, conv_direction)
        self._rfdc_regs.reset()
