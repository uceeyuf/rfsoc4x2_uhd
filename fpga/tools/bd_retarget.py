#!/usr/bin/env python3
"""Retarget an upstream (Vivado 2021.1) block-design Tcl script to another Vivado
version and part: replace the version guard and the project part, and drop the
version from every xilinx.com IP VLNV so the installed IP revision is used."""
import argparse
import re

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--version", default="2023.2")
ap.add_argument("--part", default=None)
ap.add_argument("--rfsoc4x2", action="store_true",
                help="X440 PS/RFDC BD for xczu48dr: append $::rfsoc4x2_rfdc_cfg to the "
                     "RFDC configuration and drop the RFDC DAC data / DAC output / "
                     "converter clock connections (rebuilt by rfsoc4x2_ps_rfdc_bd.tcl), and the "
                     "final validate/save")
a = ap.parse_args()

s = open(a.src).read()
s = re.sub(r"set scripts_vivado_version \S+", f"set scripts_vivado_version {a.version}", s)
s = re.sub(r"(xilinx\.com:ip:[A-Za-z0-9_]+):[0-9.]+", r"\1", s)
s = s.replace("get_ipdefs -all $ip_vlnv]", "get_ipdefs -all ${ip_vlnv}:*]")
if a.part:
    s = re.sub(r"(create_project \S+ \S+ -part )\S+", rf"\g<1>{a.part}", s)
if a.rfsoc4x2:
    # RFDC configuration: the X440 settings first, then the RFSoC 4x2 overrides
    m = re.search(r"(set_property -dict \[ ?list \\\n(?:.*\\\n)*?)(\s*\] \$rf_data_converter)", s)
    if not m:
        raise SystemExit("RFDC configuration not found")
    s = s[:m.start()] + m.group(1) + "    {*}$::rfsoc4x2_rfdc_cfg \\\n" + m.group(2) + s[m.end():]
    drop = re.compile(r"^\s*connect_bd_intf_net .*rf_data_converter/"
                      r"(s\d\d_axis|vout\d\d|adc\d_clk|dac\d_clk)\]")
    lines = s.split("\n")
    kept = [l for l in lines if not drop.match(l)]
    if len(lines) - len(kept) != 8 + 8 + 6:
        raise SystemExit(f"expected 22 RFDC connections, dropped {len(lines) - len(kept)}")
    # validated and saved after the RFSoC 4x2 changes, not before
    kept = [l for l in kept if l.strip() not in ("validate_bd_design", "save_bd_design")]
    s = "\n".join(kept)
open(a.dst, "w").write(s)
