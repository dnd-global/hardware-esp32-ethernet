"""Check the CPL file in fab/ against the JLCPCB library footprint of every part (run after fab.sh).

JLCPCB puts its own footprint of each LCSC part at the CPL position with the CPL rotation. This
script does the same on paper and measures how far each library pad lands from the pads of that part
on the board, and whether it lands on the pad with the same pin. It catches a wrong rotation, a wrong
polarity and an origin that differs between the KiCad and the JLCPCB footprint.

Library footprints are read from jlc-lib/<LCSC>.json; a missing one is downloaded from the
JLCEDA/EasyEDA official library (https://lceda.cn/api/products/<LCSC>/components).

Run: python3 check_cpl.py        (exit code 1 if any part fails)
Needs the pcbnew Python module of KiCad 9. BOARD and FAB can be set in the environment.
"""
import csv
import json
import math
import os
import sys
import urllib.request

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "gateway-s3-revb"
BOARD = os.environ.get("BOARD", os.path.join(HERE, "..", "..", "kicad", "esp32-eth-uart-module.kicad_pcb"))
FAB = os.environ.get("FAB", os.path.join(HERE, "..", "..", "fab"))
LIB = os.path.join(HERE, "jlc-lib")
TOL = 0.35           # mm; pad pitch differs by up to 0.25 mm between the KiCad and JLCPCB diode footprints
UNIT = 0.254         # EasyEDA footprint unit (10 mil) in mm


def rot(x, y, deg):
    """Rotate counter-clockwise on screen (y axis points down), as KiCad and JLCPCB do."""
    r = math.radians(deg)
    return x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r)


def library(part):
    path = os.path.join(LIB, part + ".json")
    if not os.path.exists(path):
        os.makedirs(LIB, exist_ok=True)
        req = urllib.request.Request(f"https://lceda.cn/api/products/{part}/components?version=6.4.19.5",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r, open(path, "wb") as f:
            f.write(r.read())
    d = json.load(open(path))["result"]
    fp = d["packageDetail"]["dataStr"]
    ox, oy = float(fp["head"]["x"]), float(fp["head"]["y"])
    pads = []
    for s in fp["shape"]:
        if s.startswith("PAD~"):
            f = s.split("~")
            pads.append((f[8], (float(f[2]) - ox) * UNIT, (float(f[3]) - oy) * UNIT))
    names = {}
    for s in d["dataStr"]["shape"]:
        if s.startswith("P~"):
            seg = s.split("^^")
            names[seg[0].split("~")[3]] = seg[3].split("~")[4] if len(seg) > 3 else ""
    return fp["head"]["c_para"].get("package", ""), pads, names


def same_pin(lib_num, lib_name, board_num, kicad_fp):
    if kicad_fp.startswith(("D_", "LED_")):          # KiCad: pad 1 = cathode, pad 2 = anode
        if lib_name.upper() in ("K", "C"):
            return board_num == "1"
        if lib_name.upper() == "A":
            return board_num == "2"
    if lib_num == board_num:
        return True
    if board_num.startswith("S"):                    # shell / shield pads
        return True
    return len(board_num) > 1 and board_num in lib_num   # USB-C: library pad "A1B12" covers KiCad pads A1 and B12


board = pcbnew.LoadBoard(BOARD)
board_pads, kicad_fp = {}, {}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    kicad_fp[ref] = fp.GetFPID().GetLibItemName().wx_str()
    board_pads[ref] = [(p.GetNumber(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetNetname())
                       for p in fp.Pads() if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]

lcsc = {}
for row in csv.DictReader(open(os.path.join(FAB, NAME + "-bom.csv"))):
    for ref in row["Designator"].split(","):
        lcsc[ref.strip()] = row["LCSC Part #"].strip()

failed = []
rows = list(csv.DictReader(open(os.path.join(FAB, NAME + "-cpl.csv"))))
for row in rows:
    ref = row["Designator"]
    cx, cy, angle = float(row["Mid X"].replace("mm", "")), -float(row["Mid Y"].replace("mm", "")), float(row["Rotation"])
    package, pads, names = library(lcsc[ref])
    result = {}
    for psi in (0, 90, 180, 270):
        worst, landing = 0.0, []
        for num, x, y in pads:
            rx, ry = rot(x, y, psi)
            d, b = min(((math.hypot(cx + rx - bx, cy + ry - by), (bn, net)) for bn, bx, by, net in board_pads[ref]),
                       key=lambda t: t[0])
            worst = max(worst, d)
            landing.append((num, names.get(num, ""), b[0], b[1]))
        result[psi] = (worst, landing)
    worst, landing = result[int(angle) % 360]
    pins_ok = all(same_pin(n, nm, bn, kicad_fp[ref]) for n, nm, bn, _ in landing)
    ok = worst < TOL and pins_ok
    if not ok:
        failed.append(ref)
    fits = [psi for psi in result if result[psi][0] < TOL]
    print(f"{'ok ' if ok else 'BAD'} {ref:5} {lcsc[ref]:10} {package[:38]:38} rot {int(angle):3}  off {worst:.2f} mm  "
          f"fits at {fits}{'' if pins_ok else '  WRONG PINS'}")
    named = any(nm and nm != n for n, nm, _, _ in landing)
    if not ok or (named and len(pads) <= 6):
        for n, nm, bn, net in sorted(set(landing)):
            print(f"          library pad {n:5} {nm:5} -> board pad {bn:4} {net}")
print(f"\n{len(rows)} parts checked, {len(failed)} failed: {failed}")
sys.exit(1 if failed else 0)
