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
a = ap.parse_args()

s = open(a.src).read()
s = re.sub(r"set scripts_vivado_version \S+", f"set scripts_vivado_version {a.version}", s)
s = re.sub(r"(xilinx\.com:ip:[A-Za-z0-9_]+):[0-9.]+", r"\1", s)
s = s.replace("get_ipdefs -all $ip_vlnv]", "get_ipdefs -all ${ip_vlnv}:*]")
if a.part:
    s = re.sub(r"(create_project \S+ \S+ -part )\S+", rf"\g<1>{a.part}", s)
open(a.dst, "w").write(s)
