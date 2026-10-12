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

Only ADC tiles 224 / 226 and DAC tiles 228 / 230 are bonded out. All tiles are
enabled (the analog SYSREF is chained through every tile), and the X440 image
maps RX ports 2 / 3 of each radio to ADC tiles 225 / 227, but the ADC startup of
those two tiles stops in the converter calibration (state 0xC). As in the
RFSoC 4x2 MTS reference design, startup is checked and MTS is run on tiles 0
and 2 only.
"""

import contextlib
import itertools

from usrp_mpm.periph_manager.x4xx_rfdc_ctrl import CONV_OPTIONS, X4xxRfdcCtrl
from usrp_mpm.rpc_utils import no_rpc

# RFDC tile indices (ADC 224 / 226, DAC 228 / 230) with converters on the SMAs
BONDED_TILES = (0, 2)
NUM_TILES = 4
# MTS reference tile: tiles 226 / 230 generate the converter clocks and
# distribute them (MPM patch 0002 makes it settable; the X4xx uses tile 0)
MTS_REF_TILE = 2


class Rfsoc4x2RfdcCtrl(X4xxRfdcCtrl):
    """X4xxRfdcCtrl without RFDC PLL reconfiguration, MTS on the bonded tiles."""

    def __init__(self, *args, **kwargs):
        self._bonded_only = False
        super().__init__(*args, **kwargs)
        for conv_type in ("ADC", "DAC"):
            self._rfdc_ctrl.set_sync_ref_tile(MTS_REF_TILE, CONV_OPTIONS[conv_type])

    @contextlib.contextmanager
    def _bonded_tiles_only(self):
        self._bonded_only = True
        try:
            yield
        finally:
            self._bonded_only = False

    def _find_converters(self, db_id, db_channel, direction, mode):
        convs = super()._find_converters(db_id, db_channel, direction, mode)
        if self._bonded_only:
            return [conv for conv in convs if conv[0] in BONDED_TILES]
        return convs

    @no_rpc
    def determine_tile_latencies(self, db_idx):
        with self._bonded_tiles_only():
            return super().determine_tile_latencies(db_idx)

    @no_rpc
    def set_tile_latencies(self, db_idx, adc_latency, dac_latency):
        with self._bonded_tiles_only():
            return super().set_tile_latencies(db_idx, adc_latency, dac_latency)

    @no_rpc
    def startup_tiles(self, quiet=False):
        """Start all tiles; report failures of the bonded ones only."""
        for conv_type in ("ADC", "DAC"):
            for tile in range(NUM_TILES):
                if (
                    not self._rfdc_ctrl.startup_tile(tile, CONV_OPTIONS[conv_type])
                    and tile in BONDED_TILES
                    and not quiet
                ):
                    self.log.warning(f"Error starting up {conv_type} tile {tile}")

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
