#!/bin/sh
# Regenerate the schematic from the netlist table, check it against the board, export PDF and SVG.
# Needs KiCad 9 (kicad-cli and the pcbnew Python module).
#
#   ./build.sh             build into ./out and check
#   ./build.sh --install   also copy the result into ../../kicad and the PDF into ../../docs
#
# NETLIST, BOARD, FOOTPRINTS and OUT can be set in the environment to use other paths.
set -e
cd "$(dirname "$0")"
NAME=esp32-eth-uart-module
NETLIST=${NETLIST:-../netlist.py}
BOARD=${BOARD:-../../kicad/$NAME.kicad_pcb}
FOOTPRINTS=${FOOTPRINTS:-../../kicad/lcsc.pretty}
OUT=${OUT:-out}
rm -rf "$OUT" && mkdir -p "$OUT/svg"
python3 gen_sch.py "$NETLIST" "$OUT" "$FOOTPRINTS"
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/$NAME.net" "$OUT/$NAME.kicad_sch" >/dev/null
python3 check_sch.py "$OUT/$NAME.net" "$BOARD"
rm -f "$OUT/$NAME.net"
kicad-cli sch erc --severity-all --exit-code-violations --format json -o "$OUT/erc.json" "$OUT/$NAME.kicad_sch" >/dev/null 2>&1 || ERC_FAILED=1
python3 - "$OUT/erc.json" <<'PY'
import collections, json, sys
d = json.load(open(sys.argv[1]))
c = collections.Counter((v["severity"], v["type"]) for sh in d["sheets"] for v in sh["violations"])
print("ERC:", sum(c.values()), "violations", dict(c) if c else "")
for sh in d["sheets"]:
    for v in sh["violations"][:40]:
        print("   ", sh["path"], v["severity"], v["type"], "|", v["description"], "|", [i["description"] for i in v["items"]][:2])
PY
[ -z "$ERC_FAILED" ] || { echo "ERC reported violations"; exit 1; }
# no property pop-ups, and no helper script: some readers warn about a PDF that carries JavaScript
kicad-cli sch export pdf --exclude-pdf-property-popups -o "$OUT/so-do-nguyen-ly.pdf" "$OUT/$NAME.kicad_sch" >/dev/null
python3 clean_pdf.py "$OUT/so-do-nguyen-ly.pdf"
kicad-cli sch export svg -o "$OUT/svg" "$OUT/$NAME.kicad_sch" >/dev/null
if [ "$1" = "--install" ]; then
  cp "$OUT"/*.kicad_sch "$OUT/module.kicad_sym" "$OUT/sym-lib-table" "$OUT/fp-lib-table" "$OUT/$NAME.kicad_pro" ../../kicad/
  mkdir -p ../../docs && cp "$OUT/so-do-nguyen-ly.pdf" ../../docs/
  echo "installed into ../../kicad and ../../docs"
fi
