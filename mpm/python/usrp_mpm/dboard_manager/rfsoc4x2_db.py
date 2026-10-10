#
# Copyright 2026 Yijie Yu
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""RFSoC 4x2 direct-sampling front end.

The RFSoC 4x2 has no daughterboards: the converters connect to the SMA ports
through baluns. Each X4xx radio (two per image) is represented by one of these
"daughterboards", which has no hardware of its own (no EEPROM, CPLD, power
switch or LOs). It provides the X4xx daughterboard RPC calls that relate to the
RFDC (rates, IQ swap, data path); tuning is the RFDC NCO on the host side.
"""

from usrp_mpm.dboard_manager import DboardManagerBase
from usrp_mpm.mpmlog import get_logger
from usrp_mpm.rpc_utils import no_rpc


class Rfsoc4x2Dboard(DboardManagerBase):
    """Direct-sampling front end of the RFSoC 4x2 (one per radio)."""

    # Not looked up by PID: rfsoc4x2.py instantiates this class directly. The PID
    # reported to the host is rfsoc4x2.RFSOC4X2_DB_PID.
    pids = []
    rx_sensor_callback_map = {"rfdc_rate": "get_rfdc_rate_sensor"}
    tx_sensor_callback_map = {"rfdc_rate": "get_rfdc_rate_sensor"}

    def __init__(self, slot_idx, **kwargs):
        super().__init__(slot_idx, **kwargs)
        self.log = get_logger(f"RFSoC4x2-FE-{slot_idx}")
        self.mboard = kwargs["mboard"]

    @no_rpc
    def init(self, args):
        return True

    @no_rpc
    def deinit(self):
        pass

    @no_rpc
    def tear_down(self):
        pass

    @no_rpc
    def reset_clock(self, value):
        """No daughterboard clocks."""

    def get_master_clock_rate(self):
        return self.mboard.clk_mgr.get_master_clock_rate(self.slot_idx)

    def get_dboard_sample_rate(self):
        """RFDC converter rate."""
        return self.mboard.clk_mgr.get_converter_rate(self.slot_idx)

    def get_dboard_prc_rate(self):
        return self.mboard.clk_mgr.get_prc_rate()

    def enable_iq_swap(self, enable, trx, channel):
        self.mboard.rfdc.enable_iq_swap(enable, self.slot_idx, channel, trx == "tx")

    def set_data_path(self, mode, direction):
        return self.mboard.rfdc.set_data_path(self.slot_idx, mode, direction == "tx")

    def get_rfdc_rate_sensor(self, _):
        return {
            "name": "rfdc_rate",
            "type": "REALNUM",
            "unit": "Hz",
            "value": str(self.get_dboard_sample_rate()),
        }
