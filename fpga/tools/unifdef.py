#!/usr/bin/env python3
"""Resolve Verilog `ifdef/`ifndef/`elsif/`else/`endif blocks for a given set of
defined and undefined macros; directives on other macros are kept as they are.
Usage: unifdef.py -D X440 -D RF_CORE_FULL -U X410 ... < in.sv > out.sv"""
import argparse
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("-D", action="append", default=[])
ap.add_argument("-U", action="append", default=[])
a = ap.parse_args()
known = {m: True for m in a.D}
known.update({m: False for m in a.U})

d = re.compile(r"^\s*`(ifdef|ifndef|elsif|else|endif)\b\s*(\w+)?")
# stack entries: [resolved(bool), emitting(bool), taken(bool), parent_emit(bool)]
stack = []
out = []
emit = True
for line in sys.stdin:
    m = d.match(line)
    if not m:
        if emit:
            out.append(line)
        continue
    kw, mac = m.group(1), m.group(2)
    if kw in ("ifdef", "ifndef"):
        if mac in known:
            cond = known[mac] if kw == "ifdef" else not known[mac]
            stack.append({"res": True, "parent": emit, "taken": cond})
            emit = emit and cond
        else:
            stack.append({"res": False, "parent": emit, "taken": None})
            if emit:
                out.append(line)
    elif kw == "elsif":
        top = stack[-1]
        if top["res"]:
            if mac in known:
                cond = known[mac] and not top["taken"]
                top["taken"] = top["taken"] or known[mac]
                emit = top["parent"] and cond
            else:
                raise SystemExit(f"elsif on unknown macro {mac} after a resolved branch")
        else:
            if mac in known:
                raise SystemExit(f"elsif on known macro {mac} after an unresolved branch")
            if top["parent"]:
                out.append(line)
    elif kw == "else":
        top = stack[-1]
        if top["res"]:
            emit = top["parent"] and not top["taken"]
        elif top["parent"]:
            out.append(line)
    elif kw == "endif":
        top = stack.pop()
        if not top["res"] and top["parent"]:
            out.append(line)
        emit = top["parent"]
sys.stdout.write("".join(out))
