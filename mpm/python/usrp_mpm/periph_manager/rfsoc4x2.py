#
# Copyright 2026 Yijie Yu
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""RFSoC 4x2 motherboard class for MPM.

The FPGA image keeps the X440 register map and RFNoC device type, so this is
the X4xx periph manager with the board-specific parts replaced:

- No motherboard EEPROM: synthetic EEPROM data (product "x440", so the X440
  device tree overlay name and host-side X4xx code apply). The serial number is
  read from /etc/uhd/rfsoc4x2_serial if present.
- No motherboard / daughterboard CPLDs, clocking aux board, GPS, DIO, QSFP
  management: not initialized.
- Clocking: LMK04828 + 2x LMX2594 with fixed settings (rfsoc4x2_clocking),
  one master clock rate (500 MS/s).
- RFDC: no per-tile PLL reprogramming (rfsoc4x2_rfdc_ctrl).
- Two direct-sampling "daughterboards" (rfsoc4x2_db), one per radio, reported
  to the host with RFSOC4X2_DB_PID.
"""

import threading
from pathlib import Path

from usrp_mpm.dboard_manager.rfsoc4x2_db import Rfsoc4x2Dboard
from usrp_mpm.periph_manager.rfsoc4x2_clocking import Rfsoc4x2ClockManager
from usrp_mpm.periph_manager.rfsoc4x2_rfdc_ctrl import Rfsoc4x2RfdcCtrl
from usrp_mpm.periph_manager.x4xx import X400XportMgrUDP, x4xx
from usrp_mpm.periph_manager.x4xx_periphs import CtrlportRegs, MboardRegsControl

# PID reported for the two front ends, handled by the RFSoC 4x2 front end of the
# host patch (host/patches: 4 channels per radio as in the X440 image, RFDC NCO
# tuning). An unmodified UHD host does not know this PID; the X4xx debug
# daughterboard PID (0x4001) does not work either, as that front end has only 2
# of the 4 channels per radio.
RFSOC4X2_DB_PID = 0x4F42
RFSOC4X2_SERIAL_FILE = "/etc/uhd/rfsoc4x2_serial"


class Rfsoc4x2CtrlportRegs(CtrlportRegs):
    """Ctrlport endpoint without the motherboard PL CPLD behind it."""

    class MbPlCpldIface(CtrlportRegs.MbPlCpldIface):
        """No CPLD on the RFSoC 4x2: skip the signature and revision checks."""

        def check_signature(self):
            pass

        def check_revision(self):
            pass


class rfsoc4x2(x4xx):
    """RFSoC 4x2 running the X440-compatible UHD FPGA image."""

    pids = {0x0440: "x440"}
    description = "RFSoC 4x2 (X440-compatible UHD image)"
    mboard_max_rev = 1
    mboard_sensor_callback_map = {
        "ref_locked": "get_ref_lock_sensor",
        "ref_stable": "get_ref_stable_sensor",
    }
    db_iface = None
    max_num_dboards = 2

    ###########################################################################
    # EEPROMs: none on this board
    ###########################################################################
    def _read_mboard_eeprom(self):
        serial = b"RFSOC4X2"
        try:
            serial = Path(RFSOC4X2_SERIAL_FILE).read_text().strip().encode("ascii")[:7]
        except (FileNotFoundError, UnicodeError):
            pass
        self._eeprom_head = {
            "pid": 0x0440,
            "rev": 1,
            "rev_compat": 1,
            "serial": serial,
            "module_serial": serial,
            "eeprom_version": 0,
        }
        self._eeprom_rawdata = b""
        self.log.info("No motherboard EEPROM on the RFSoC 4x2: using serial %s", serial)

    def _get_dboard_info(self):
        return [
            {
                "pid": RFSOC4X2_DB_PID,
                "rev": 1,
                "eeprom_md": {
                    "pid": RFSOC4X2_DB_PID,
                    "rev": 1,
                    "rev_compat": 1,
                    "serial": f"FE{idx}",
                    "eeprom_version": 0,
                },
                "eeprom_rawdata": b"",
            }
            for idx in range(self.max_num_dboards)
        ]

    def _get_aux_board_info(self):
        return {}

    def _init_dboards(self, dboard_infos, override_dboard_pids, default_args):
        for idx, dboard_info in enumerate(dboard_infos):
            self.dboards.append(
                Rfsoc4x2Dboard(
                    idx, mboard=self, default_args=default_args, **dboard_info
                )
            )
        self.log.info("Initialized %d direct-sampling front end(s).", len(self.dboards))

    ###########################################################################
    # Peripherals
    ###########################################################################
    def _init_peripherals(self, args):
        """Subset of x4xx._init_peripherals() for the RFSoC 4x2."""
        assert self.mboard_info.get("product") in self.pids.values()
        self.init_rpu()
        self._clocking_auxbrd = None
        self.cpld_control = None

        # Clocks first: the FPGA needs FPGA_REFCLK before the bitfile is loaded
        self.clk_mgr = Rfsoc4x2ClockManager(args, self.log)
        self._add_public_methods(
            self.clk_mgr,
            prefix="",
            filter_cb=lambda name, method: not hasattr(method, "_norpc"),
            allow_overwrite=True,
        )

        # Load the bitfile through the device tree overlay
        self.overlay_apply()

        self.log.trace("Initializing MBoard reg controls...")
        serial_number = self._get_serial_number()
        self.mboard_regs_control = MboardRegsControl(self.mboard_regs_label, self.log)
        self._check_fpga_compat()
        self.mboard_regs_control.set_serial_number(serial_number)
        self.mboard_regs_control.get_git_hash()
        self.mboard_regs_control.get_build_timestamp()
        if "device_dna" in self.fpga_features:
            self._device_dna = self.mboard_regs_control.get_device_dna()

        self.rfdc = Rfsoc4x2RfdcCtrl(self.log)
        self._add_public_methods(
            self.rfdc, prefix="", filter_cb=lambda name, method: not hasattr(method, "_norpc")
        )
        self._update_fpga_type()
        self._update_fpga_supported_file_extensions()

        self.clk_mgr.finalize_init(args, self.mboard_regs_control, self.rfdc)

        self.ctrlport_regs = Rfsoc4x2CtrlportRegs(self.ctrlport_regs_label, self.log)

        self._xport_mgrs = {
            "udp": X400XportMgrUDP(self.log, args),
        }
        self._status_monitor_thread = threading.Thread(
            target=self._monitor_status,
            name="Rfsoc4x2StatusMonitorThread",
            daemon=True,
        )
        self._status_monitor_thread.start()
        self.log.debug("Device info: {}".format(self.device_info))

    def _init_dio_control(self, _):
        """No DIO on the RFSoC 4x2."""
        self.dio_control = None

    def get_db_eeprom(self, dboard_idx):
        info = super().get_db_eeprom(dboard_idx)
        info.setdefault("rev_compat", "1")
        return info
