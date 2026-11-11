#!/bin/bash
# Export the JLCPCB fabrication and assembly files from the board into ../../fab
#   gateway-s3-revb-gerber.zip   Gerbers + drill files (upload as the PCB)
#   gateway-s3-revb-bom.csv      BOM for assembly (Comment, Designator, Footprint, LCSC Part #)
#   gateway-s3-revb-cpl.csv      component positions (Designator, Mid X, Mid Y, Layer, Rotation)
#
# ./fab.sh                   export everything
# ./fab.sh --assembly-only   rewrite BOM + CPL only, leave the Gerber zip as it is
# Afterwards run: python3 check_cpl.py   (compares every CPL line with the JLCPCB library footprint)
# Needs KiCad 9 (kicad-cli and the pcbnew Python module). BOARD and FAB can be set in the environment.
set -e
cd "$(dirname "$0")"
BOARD=${BOARD:-../../kicad/esp32-eth-uart-module.kicad_pcb}
FAB=${FAB:-../../fab}
N=gateway-s3-revb
mkdir -p "$FAB"
FAB=$(cd "$FAB" && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
B=$T/gateway-s3.kicad_pcb          # Gerber file names follow the board file name; keep the names of Rev B
cp "$BOARD" "$B"
if [ "$1" = "--assembly-only" ]; then
  rm -f "$FAB"/$N-*.csv
else
  rm -f "$FAB"/$N-*.zip "$FAB"/$N-*.csv && mkdir -p "$T/gerber"
  kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
    --subtract-soldermask --no-x2 -o "$T/gerber/" "$B" >/dev/null
  kicad-cli pcb export drill --format excellon --drill-origin absolute --excellon-units mm --excellon-separate-th -o "$T/gerber/" "$B" >/dev/null
  (cd "$T/gerber" && zip -q "$FAB/$N-gerber.zip" *)
fi
python3 - "$N" "$B" "$FAB" <<'PY' 2>&1 | grep -v -e Font -e "SetWidth called" -e "Debug:" -e "memory leak"
import csv, math, os, sys
import pcbnew
sys.path.insert(0, os.path.abspath('..'))
import netlist
name, board_path, fab = sys.argv[1:4]
# JLCPCB places its own library footprint of each part at the CPL position and rotation. Three KiCad
# footprints used here differ from the JLCPCB one; check_cpl.py measures this for every part.
# Degrees to add to the KiCad angle, per footprint:
JLC_ROTATION = {'LQFP-48_7x7mm_P0.5mm': -90, 'SOT-23': 180}
# Position shift in footprint-local mm (KiCad axes, before rotation), per footprint. KiCad puts the
# origin of this USB-C receptacle at the body centre, JLCPCB at the centre of the pads, 1.41 mm
# further from the board edge (measured on the locating pegs and shell legs).
JLC_OFFSET = {'USB_C_Receptacle_HRO_TYPE-C-31-M-12': (0.0, -1.41)}
# Degrees to add for one LCSC part whose JLCPCB footprint is drawn differently from the footprint the
# board uses. U4: the pads are the Diodes SOT-25 footprint; JLCPCB draws the TI SOT-23-5 a quarter turn from it.
JLC_ROTATION_BY_PART = {'C7836': 270}
b = pcbnew.LoadBoard(board_path)
fps = {f.GetReference(): f for f in b.GetFootprints()}
parts = {r: v for r, v in netlist.PARTS.items() if not v[-1]}          # parts that are not fitted are left out
missing = [r for r in parts if r not in fps]
extra = [r for r, f in fps.items() if r not in netlist.PARTS and not r.startswith('H') and 'TestPoint' not in f.GetFPID().GetLibItemName().wx_str()]
assert not missing and not extra, (missing, extra)
with open(os.path.join(fab, f'{name}-cpl.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in sorted(parts, key=lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0))):
        fp = fps[r]
        p = fp.GetPosition()
        lib = fp.GetFPID().GetLibItemName().wx_str()
        a = math.radians(fp.GetOrientationDegrees())
        ox, oy = JLC_OFFSET.get(lib, (0.0, 0.0))
        x = p.x / 1e6 + ox * math.cos(a) + oy * math.sin(a)      # KiCad: y down, positive angle = counter-clockwise on screen
        y = p.y / 1e6 - ox * math.sin(a) + oy * math.cos(a)
        rot = (fp.GetOrientationDegrees() + JLC_ROTATION.get(lib, 0) + JLC_ROTATION_BY_PART.get(parts[r][2], 0)) % 360
        w.writerow([r, f'{x:.4f}mm', f'{-y:.4f}mm', 'Top', f'{rot:g}'])
groups = {}          # one BOM line per LCSC part: JLCPCB deselects parts that appear on two lines
for r, (fpid, value, lcsc, *_rest) in parts.items():
    g = groups.setdefault((fpid.split(':')[1], lcsc), {'refs': [], 'values': []})
    g['refs'].append(r)
    if value not in g['values']:
        g['values'].append(value)
with open(os.path.join(fab, f'{name}-bom.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for (fp, lcsc), g in sorted(groups.items(), key=lambda kv: kv[1]['refs'][0]):
        w.writerow([' / '.join(g['values']), ','.join(g['refs']), fp, lcsc])
print('bom lines', len(groups), '| placed parts', len(parts), '| not fitted:', [r for r, v in netlist.PARTS.items() if v[-1]])
PY
ls -la "$FAB"
