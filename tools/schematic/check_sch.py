"""Compare the schematic with the board: every pad must sit in the same net on both, under the same name.

Usage: check_sch.py <netlist exported by kicad-cli, kicadsexpr format> <board .kicad_pcb>
Exit code 1 on any difference.
"""
import sys

import pcbnew

TP = {"TP1": "3V3", "TP2": "GND", "TP3": "TXD", "TP4": "RXD", "TP5": "VISO", "TP6": "GISO"}   # schematic ref -> board ref


def parse(text):
    """S-expression -> nested lists of strings."""
    stack, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            stack.append(cur); cur = []; i += 1
        elif c == ")":
            done = cur; cur = stack.pop(); cur.append(done); i += 1
        elif c == '"':
            j, s = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                s.append(text[j]); j += 1
            cur.append("".join(s)); i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            cur.append(text[i:j]); i = j
    return cur[0]


def child(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def val(node, name):
    c = child(node, name)
    return c[0][1] if c and len(c[0]) > 1 else ""


tree = parse(open(sys.argv[1]).read())
sch_net, sch_fp, sch_val = {}, {}, {}
for comp in child(child(tree, "components")[0], "comp"):
    ref = TP.get(val(comp, "ref"), val(comp, "ref"))
    sch_fp[ref], sch_val[ref] = val(comp, "footprint"), val(comp, "value")
for net in child(child(tree, "nets")[0], "net"):
    name = val(net, "name")
    for node in child(net, "node"):
        sch_net[(TP.get(val(node, "ref"), val(node, "ref")), val(node, "pin"))] = name

board = pcbnew.LoadBoard(sys.argv[2])
brd_net, brd_fp = {}, {}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    pads = [p for p in fp.Pads() if p.GetNumber() != ""]
    if not pads:
        continue                                   # mounting holes
    brd_fp[ref] = fp.GetFPID().GetLibItemName().wx_str()
    for p in pads:
        brd_net[(ref, p.GetNumber())] = p.GetNetname()


def groups(pin_net, keep):
    g = {}
    for pin, name in pin_net.items():
        if keep(name):
            g.setdefault(name, set()).add(pin)
    return {k: v for k, v in g.items() if len(v) > 1}


sch_groups = groups(sch_net, lambda n: not n.startswith("unconnected-"))
brd_groups = groups(brd_net, lambda n: n != "")
problems = []

only_sch, only_brd = sorted(set(sch_fp) - set(brd_fp)), sorted(set(brd_fp) - set(sch_fp))
if only_sch:
    problems.append(f"parts only in the schematic: {only_sch}")
if only_brd:
    problems.append(f"parts only on the board: {only_brd}")
for ref in sorted(set(sch_fp) & set(brd_fp)):
    if sch_fp[ref].split(":")[-1] != brd_fp[ref]:
        problems.append(f"{ref}: footprint {sch_fp[ref]} in the schematic, {brd_fp[ref]} on the board")

names = 0
for name, pins in sorted(brd_groups.items()):
    first = sorted(pins)[0]
    sname = sch_net.get(first)
    spins = sch_groups.get(sname, set())
    if spins != pins:
        problems.append(f"net {name}: board has {sorted(pins - spins)} that the schematic lacks, "
                        f"schematic has {sorted(spins - pins)} that the board lacks")
    elif sname.split("/")[-1] != name:
        problems.append(f"net {name} is called {sname} in the schematic")
    else:
        names += 1
for sname, spins in sorted(sch_groups.items()):
    if not any(brd_groups.get(brd_net.get(p)) == spins for p in spins):
        if not any(sname in pr or sname.split("/")[-1] in pr for pr in problems):
            problems.append(f"schematic net {sname} {sorted(spins)} has no equal on the board")
for pin, name in sorted(brd_net.items()):
    if pin not in sch_net:
        problems.append(f"pad {pin[0]}.{pin[1]} is on the board (net '{name}') but the schematic has no such pin")

pads_checked = sum(len(v) for v in brd_groups.values())
print(f"board: {len(brd_fp)} parts, {len(brd_groups)} nets with two or more pads, {pads_checked} pads in them")
print(f"schematic: {len(sch_fp)} parts, {len(sch_groups)} nets with two or more pins")
print(f"nets equal pin for pin and by name: {names} of {len(brd_groups)}")
for p in problems:
    print("DIFF", p)
print("RESULT:", "schematic and board agree" if not problems else f"{len(problems)} differences")
sys.exit(1 if problems else 0)
