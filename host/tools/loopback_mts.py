#!/usr/bin/env python3
#
# Copyright 2026 Yijie Yu
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""RFSoC 4x2 loopback: DAC_B -> ADC_D (radio0 port 0), DAC_A -> ADC_B (radio1 port 0).

Both DACs send the same timed burst, both ADCs capture from the same time; the
delay and phase of each loop are estimated against the sent waveform. With
multi-tile sync, the difference between the two loops stays the same from one
device initialization to the next.

Cables: DAC_B -> ADC_D, DAC_A -> ADC_B (SMA). Kernel UDP is enough: the
bursts fit the device buffers. Example:
    loopback_mts.py --args addr=192.168.10.2 --freq 1e9 --reps 2
"""
import argparse
import numpy as np
import uhd

p = argparse.ArgumentParser()
p.add_argument("--args", default="addr=192.168.10.2")
p.add_argument("--chans", default="0,4")
p.add_argument("--freq", type=float, default=1e9)
p.add_argument("--rate", type=float, default=0, help="host sample rate (DDC/DUC image); 0: leave as is")
p.add_argument("--nsend", type=int, default=4096)
p.add_argument("--nrecv", type=int, default=16384)
p.add_argument("--reps", type=int, default=2)
p.add_argument("--save", default="", help="save the first capture (.npy)")
a = p.parse_args()
chans = [int(c) for c in a.chans.split(",")]

usrp = uhd.usrp.MultiUSRP(a.args)
if a.rate:
    for c in chans:
        usrp.set_rx_rate(a.rate, c)
        usrp.set_tx_rate(a.rate, c)
rate = usrp.get_rx_rate(chans[0])
for c in chans:
    usrp.set_tx_freq(uhd.types.TuneRequest(a.freq), c)
    usrp.set_rx_freq(uhd.types.TuneRequest(a.freq), c)
print("rate %.1f MS/s, rx freq %s, tx freq %s" % (rate / 1e6,
      [usrp.get_rx_freq(c) / 1e6 for c in chans], [usrp.get_tx_freq(c) / 1e6 for c in chans]))
print("rx antennas", [usrp.get_rx_antenna(c) for c in chans], "tx antennas", [usrp.get_tx_antenna(c) for c in chans])

rng = np.random.default_rng(1)
sym = (rng.integers(0, 2, a.nsend) * 2 - 1 + 1j * (rng.integers(0, 2, a.nsend) * 2 - 1)) / np.sqrt(2)
burst = (0.5 * sym).astype(np.complex64)

st_args = uhd.usrp.StreamArgs("fc32", "sc16")
st_args.channels = chans
tx = usrp.get_tx_stream(st_args)
rx = usrp.get_rx_stream(st_args)


def run(t0):
    cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    cmd.num_samps = a.nrecv
    cmd.stream_now = False
    cmd.time_spec = uhd.types.TimeSpec(t0)
    rx.issue_stream_cmd(cmd)
    md = uhd.types.TXMetadata()
    md.start_of_burst = True
    md.end_of_burst = True
    md.has_time_spec = True
    md.time_spec = uhd.types.TimeSpec(t0)
    buf = np.tile(burst, (len(chans), 1))
    sent = tx.send(buf, md, timeout=2.0)
    out = np.zeros((len(chans), a.nrecv), dtype=np.complex64)
    got = 0
    rmd = uhd.types.RXMetadata()
    while got < a.nrecv:
        n = rx.recv(out[:, got:], rmd, timeout=3.0)
        if rmd.error_code != uhd.types.RXMetadataErrorCode.none:
            print("  rx error:", rmd.strerror())
            break
        got += n
    return sent, got, out


def delay(x, ref):
    """Integer + parabolic delay (samples) and phase (deg) of ref in x."""
    n = len(x) + len(ref)
    c = np.fft.ifft(np.fft.fft(x, n) * np.conj(np.fft.fft(ref, n)))
    k = int(np.argmax(np.abs(c[: len(x)])))
    y0, y1, y2 = np.abs(c[k - 1]), np.abs(c[k]), np.abs(c[k + 1])
    frac = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
    peak = y1 / (np.linalg.norm(ref) * np.linalg.norm(x[k:k + len(ref)]) + 1e-12)
    return k + frac, np.degrees(np.angle(c[k])), peak


usrp.set_time_now(uhd.types.TimeSpec(0.0))
for r in range(a.reps):
    t0 = 1.0 + r * 0.5
    sent, got, out = run(t0)
    res = []
    for i in range(len(chans)):
        d0, d1 = delay(out[i], burst), delay(out[i], np.conj(burst))
        res.append(d0 if d0[2] >= d1[2] else d1)
        if r == 0:
            print("  ch%d corr direct %.2f, conjugate %.2f" % (chans[i], d0[2], d1[2]))
    rms = [float(np.sqrt(np.mean(np.abs(out[i]) ** 2))) for i in range(len(chans))]
    line = "  ".join("ch%d: delay %9.3f phase %7.1f corr %.2f rms %.4f" % (c, d, ph, pk, rr)
                     for c, (d, ph, pk), rr in zip(chans, res, rms))
    if len(chans) == 2:
        dd = res[1][0] - res[0][0]
        dp = (res[1][1] - res[0][1] + 180) % 360 - 180
        line += "  | diff delay %+.3f samples (%+.1f ps), phase %+.1f deg" % (dd, dd / rate * 1e12, dp)
    print("rep %d sent %d recv %d  %s" % (r, sent, got, line))
    if a.save and r == 0:
        np.save(a.save, out)
