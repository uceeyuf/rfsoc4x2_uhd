#!/usr/bin/env python3
"""XRFdc_Config "param-list" for the RFDC device-tree node, in the layout of the
xrfdc driver bundled with UHD's MPM (v6.0, uhd/mpm/include/mpm/rfdc/xrfdc.h:
packed structs, metal_phys_addr_t = 64 bit on aarch64).

  rfdc_param_list.py decode <dtsi>             print a v6.0 param-list (.dtsi)
  rfdc_param_list.py decode-v12 <dtsi>         print a v12.1 param-list (Vivado/DTG)
  rfdc_param_list.py from-dtg <pl.dtsi> <out>  convert the PetaLinux DTG (v12.1)
                                               param-list of this design to v6.0
  rfdc_param_list.py rfsoc4x2 <out>            hand-written RFSoC 4x2 values (v6.0)
"""
import re
import struct
import sys

HDR = "<IQIIIIII"            # DeviceId BaseAddr ADCType MasterADC MasterDAC ADCSysRef DACSysRef IPType
TILE = "<IIdddIIIIdI"        # Enable PLLEnable SamplingRate RefClkFreq FabClkFreq FeedbackDiv OutputDiv RefClkDiv MultibandConfig MaxSampleRate NumSlices
DAC_AN = "<IIII"             # BlockAvailable InvSyncEnable MixMode DecoderMode
DAC_DIG = "<IIIIII"          # MixerInputDataType DataWidth InterpolationMode FifoEnable AdderEnable MixerType
ADC_AN = "<II"               # BlockAvailable MixMode
ADC_DIG = "<IIIII"           # MixerInputDataType DataWidth DecimationMode FifoEnable MixerType
TILE_KEYS = ["Enable", "PLLEnable", "SamplingRate", "RefClkFreq", "FabClkFreq", "FeedbackDiv",
             "OutputDiv", "RefClkDiv", "MultibandConfig", "MaxSampleRate", "NumSlices"]
SIZE = (struct.calcsize(HDR)
        + 4 * (struct.calcsize(TILE) + 4 * struct.calcsize(DAC_AN) + 4 * struct.calcsize(DAC_DIG))
        + 4 * (struct.calcsize(TILE) + 4 * struct.calcsize(ADC_AN) + 4 * struct.calcsize(ADC_DIG)))


def decode(blob):
    assert len(blob) == SIZE, f"{len(blob)} bytes, expected {SIZE}"
    off = 0

    def take(fmt):
        nonlocal off
        v = struct.unpack_from(fmt, blob, off)
        off += struct.calcsize(fmt)
        return v
    cfg = dict(zip(["DeviceId", "BaseAddr", "ADCType", "MasterADCTile", "MasterDACTile",
                    "ADCSysRefSource", "DACSysRefSource", "IPType"], take(HDR)))
    for kind, an, dig in (("DAC", DAC_AN, DAC_DIG), ("ADC", ADC_AN, ADC_DIG)):
        tiles = []
        for _ in range(4):
            t = dict(zip(TILE_KEYS, take(TILE)))
            t["Analog"] = [take(an) for _ in range(4)]
            t["Digital"] = [take(dig) for _ in range(4)]
            tiles.append(t)
        cfg[kind] = tiles
    return cfg


# rfdc v12.1 (Vivado/PetaLinux 2023.2): extra NCOFreq per digital block,
# LinkCoupling per DAC tile, SiRevision in the header
HDR12 = "<IQIIIIIII"
DAC_TILE12 = "<IIdddIIIIdII"
DAC_DIG12 = "<IIIIIId"
ADC_DIG12 = "<IIIIId"
SIZE12 = (struct.calcsize(HDR12)
          + 4 * (struct.calcsize(DAC_TILE12) + 4 * struct.calcsize(DAC_AN) + 4 * struct.calcsize(DAC_DIG12))
          + 4 * (struct.calcsize(TILE) + 4 * struct.calcsize(ADC_AN) + 4 * struct.calcsize(ADC_DIG12)))


def decode_v12(blob):
    """Decode a v12.1 param-list into the v6.0 dict (extra fields kept under _v12)."""
    assert len(blob) == SIZE12, f"{len(blob)} bytes, expected {SIZE12} (v12.1)"
    off = 0

    def take(fmt):
        nonlocal off
        v = struct.unpack_from(fmt, blob, off)
        off += struct.calcsize(fmt)
        return v
    h = take(HDR12)
    cfg = dict(zip(["DeviceId", "BaseAddr", "ADCType", "MasterADCTile", "MasterDACTile",
                    "ADCSysRefSource", "DACSysRefSource", "IPType"], h[:8]))
    cfg["_v12"] = {"SiRevision": h[8]}
    tiles = []
    for _ in range(4):
        v = take(DAC_TILE12)
        t = dict(zip(TILE_KEYS, v[:11]))
        t["_LinkCoupling"] = v[11]
        t["Analog"] = [take(DAC_AN) for _ in range(4)]
        dig = [take(DAC_DIG12) for _ in range(4)]
        t["Digital"] = [d[:6] for d in dig]
        t["_NCOFreq"] = [d[6] for d in dig]
        tiles.append(t)
    cfg["DAC"] = tiles
    tiles = []
    for _ in range(4):
        t = dict(zip(TILE_KEYS, take(TILE)))
        t["Analog"] = [take(ADC_AN) for _ in range(4)]
        dig = [take(ADC_DIG12) for _ in range(4)]
        t["Digital"] = [d[:5] for d in dig]
        t["_NCOFreq"] = [d[5] for d in dig]
        tiles.append(t)
    cfg["ADC"] = tiles
    return cfg


def encode(cfg):
    out = struct.pack(HDR, *[cfg[k] for k in ["DeviceId", "BaseAddr", "ADCType", "MasterADCTile",
                                              "MasterDACTile", "ADCSysRefSource",
                                              "DACSysRefSource", "IPType"]])
    for kind, an, dig in (("DAC", DAC_AN, DAC_DIG), ("ADC", ADC_AN, ADC_DIG)):
        for t in cfg[kind]:
            out += struct.pack(TILE, *[t[k] for k in TILE_KEYS])
            out += b"".join(struct.pack(an, *a) for a in t["Analog"])
            out += b"".join(struct.pack(dig, *d) for d in t["Digital"])
    assert len(out) == SIZE
    return out


def read_dtsi(path):
    s = open(path).read()
    m = re.search(r"param-list\s*=\s*\[([0-9a-fA-F\s]+)\]", s)
    return bytes(int(b, 16) for b in m.group(1).split())


def rfsoc4x2():
    """Hand-written fallback (from-dtg is authoritative). RFDC IP settings of fpga/ip/rfsoc4x2_ps_rfdc_bd (xczu48dr, Gen3 = IPType 2):
    all ADC/DAC tiles at 4.0 GS/s, PLL on ADC tile 2 (226) and DAC tile 2 (230)
    from 500 MHz, the other tiles get the distributed sample clock; ADC: I/Q,
    x8 decimation, 8 words/cycle on slices 0/1 (dual tile: blocks 0/1);
    DAC: x8 interpolation, 16 words/cycle on blocks 0/2 (vout x0/x2)."""
    cfg = dict(DeviceId=0, BaseAddr=0x1000100000, ADCType=0, MasterADCTile=0,
               MasterDACTile=0, ADCSysRefSource=0, DACSysRefSource=0, IPType=2)
    fab = 62.5
    dac, adc = [], []
    for t in range(4):
        pll = 1 if t == 2 else 0
        ref = 500.0 if pll else 4000.0
        dac.append(dict(Enable=1, PLLEnable=pll, SamplingRate=4.0, RefClkFreq=ref, FabClkFreq=fab,
                        FeedbackDiv=0, OutputDiv=0, RefClkDiv=1, MultibandConfig=0,
                        MaxSampleRate=10.0, NumSlices=4,
                        Analog=[(1 if b in (0, 2) else 0, 0, 0, 0) for b in range(4)],
                        # MixerInputDataType 0 (real?) per IP: complex I/Q interleaved -> 2
                        Digital=[(2, 16, 8, 1, 0, 2) if b in (0, 2) else (0, 0, 0, 0, 0, 0)
                                 for b in range(4)]))
        adc.append(dict(Enable=1, PLLEnable=pll, SamplingRate=4.0, RefClkFreq=ref, FabClkFreq=fab,
                        FeedbackDiv=0, OutputDiv=0, RefClkDiv=1, MultibandConfig=0,
                        MaxSampleRate=5.0, NumSlices=2,
                        Analog=[(1 if b in (0, 1) else 0, 0) for b in range(4)],
                        Digital=[(1, 8, 8, 1, 2) if b in (0, 1) else (0, 0, 0, 0, 0)
                                 for b in range(4)]))
    cfg["DAC"], cfg["ADC"] = dac, adc
    return cfg


def to_dtsi(blob):
    hexs = " ".join(f"{b:02x}" for b in blob)
    return ("/* XRFdc_Config (MPM xrfdc v6.0 layout), generated by mpm/tools/rfdc_param_list.py */\n"
            f"\t\tparam-list = [ {hexs} ];\n")


if __name__ == "__main__":
    if sys.argv[1] == "decode":
        cfg = decode(read_dtsi(sys.argv[2]))
        for k, v in cfg.items():
            if k in ("DAC", "ADC"):
                for i, t in enumerate(v):
                    print(k, i, {kk: vv for kk, vv in t.items() if kk not in ("Analog", "Digital")})
                    print("   analog ", t["Analog"])
                    print("   digital", t["Digital"])
            else:
                print(k, hex(v) if k == "BaseAddr" else v)
    elif sys.argv[1] in ("decode-v12", "from-dtg"):
        cfg = decode_v12(read_dtsi(sys.argv[2]))
        if sys.argv[1] == "from-dtg":
            # The node address is in reg; keep BaseAddr as the DTG wrote it
            open(sys.argv[3], "w").write(to_dtsi(encode(cfg)))
        else:
            for k, v in cfg.items():
                if k in ("DAC", "ADC"):
                    for i, t in enumerate(v):
                        print(k, i, {kk: vv for kk, vv in t.items() if kk not in ("Analog", "Digital")})
                        print("   analog ", t["Analog"])
                        print("   digital", t["Digital"])
                else:
                    print(k, hex(v) if k == "BaseAddr" else v)
    elif sys.argv[1] == "rfsoc4x2":
        open(sys.argv[2], "w").write(to_dtsi(encode(rfsoc4x2())))
