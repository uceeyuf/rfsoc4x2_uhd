#!/usr/bin/env python3
"""Run UHD's rfnoc_image_builder from the uhd/ submodule (no UHD install needed)
with the RFSoC 4x2 BSP added: a package-data overlay holds the upstream RFNoC
YAML (core, blocks, modules, transport adapters) plus fpga/rfnoc/core/*_bsp.yml,
and the device is registered in the builder's tables at run time.

Example (generate the image core only):
  fpga/tools/rfnoc_image_builder.py -y fpga/rfsoc4x2_CG_400_rfnoc_image_core.yml \\
      -F uhd/fpga -B build/image_core -G
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
UHD_HOST = os.path.join(ROOT, "uhd", "host")
UPSTREAM_RFNOC = os.path.join(UHD_HOST, "include", "uhd", "rfnoc")
OVERLAY = os.path.join(ROOT, "build", "pkgdata")


def make_overlay():
    """build/pkgdata/rfnoc/{blocks,modules,transport_adapters} -> upstream;
    build/pkgdata/rfnoc/core/* -> upstream core files + this repo's BSPs."""
    rfnoc = os.path.join(OVERLAY, "rfnoc")
    core = os.path.join(rfnoc, "core")
    os.makedirs(core, exist_ok=True)

    def link(src, dst):
        if os.path.islink(dst) or os.path.exists(dst):
            os.remove(dst)
        os.symlink(src, dst)

    for d in ("blocks", "modules", "transport_adapters"):
        link(os.path.join(UPSTREAM_RFNOC, d), os.path.join(rfnoc, d))
    for f in os.listdir(os.path.join(UPSTREAM_RFNOC, "core")):
        link(os.path.join(UPSTREAM_RFNOC, "core", f), os.path.join(core, f))
    own = os.path.join(ROOT, "fpga", "rfnoc", "core")
    for f in os.listdir(own):
        link(os.path.join(own, f), os.path.join(core, f))


def main():
    make_overlay()
    # 'uhd' package shim: get_pkg_data_path() + the upstream rfnoc_utils
    uhd = types.ModuleType("uhd")
    uhd.__path__ = [os.path.join(UHD_HOST, "python", "uhd")]
    uhd.get_pkg_data_path = lambda: OVERLAY
    sys.modules["uhd"] = uhd
    from uhd.rfnoc_utils import image_builder
    # top directory = this repository's fpga/ (relative to usrp3/top)
    image_builder.DEVICE_DIR_MAP["rfsoc4x2"] = os.path.relpath(
        os.path.join(ROOT, "fpga"), os.path.join(ROOT, "uhd", "fpga", "usrp3", "top"))
    image_builder.DEVICE_DEFAULTTARGET_MAP["rfsoc4x2"] = "RFSOC4X2"
    image_builder.SECURE_CORE_INST_PATH["rfsoc4x2"] = \
        "x4xx_core_i/rfnoc_image_core_i/secure_image_core_i"
    sys.argv[0] = "rfnoc_image_builder"
    tool = os.path.join(UHD_HOST, "utils", "rfnoc_image_builder.py")
    code = compile(open(tool).read(), tool, "exec")
    g = {"__name__": "__main__", "__file__": tool}
    exec(code, g)


if __name__ == "__main__":
    main()
