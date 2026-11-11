"""Generate the KiCad 9 schematic of the ESP32 Ethernet UART TTL module from the netlist that built the PCB.

The netlist is the PARTS table in netlist.py. Every label, power symbol and pin order below is taken
from that table, so the drawing cannot name a net differently from the board; check_sch.py then compares
the netlist KiCad exports from these files with the board file, pin by pin.

Usage: gen_sch.py <netlist.py> <output dir> [footprint library dir]
Output: esp32-eth-uart-module.kicad_sch (cover) + nguon / esp32 / ethernet / uart-cach-ly .kicad_sch,
        the symbol library module.kicad_sym, sym-lib-table, fp-lib-table and a minimal .kicad_pro;
        with a footprint library dir, also lcsc.pretty with the footprints the board takes from it
"""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisch  # noqa: E402

PROJECT = "esp32-eth-uart-module"
TITLE = "Module ESP32 Ethernet UART TTL công nghiệp"
REV, DATE = "B", "2026-11-11"
PAPER = (420, 230)            # mm; as wide as A3, cut to the height the drawings need
GNDS = {"GND": "gnd", "GND_ISO": "gnd_iso"}
RAILS = {"+3V3", "+3V3A", "VISO"}
# schematic reference: (text printed next to the pad on the board, net)
TESTPOINTS = {"TP1": ("3V3", "+3V3"), "TP2": ("GND", "GND"), "TP3": ("TXD", "UART_TX"), "TP4": ("RXD", "UART_RX"),
              "TP5": ("VISO", "VISO"), "TP6": ("GISO", "GND_ISO")}


def load_parts(path):
    g = {}
    exec(open(path).read(), g)
    return g["PARTS"]


PARTS = load_parts(sys.argv[1])
OUT = sys.argv[2]
NET, VALUE, FIELDS, DNP = {}, {}, {}, {}
for ref, (fp, value, lcsc, _x, _y, _r, padnets, dnp) in PARTS.items():
    VALUE[ref] = value
    FIELDS[ref] = {"Footprint": fp, "LCSC": lcsc}
    DNP[ref] = dnp
    for pad, net in padnets.items():
        NET[(ref, pad)] = net
for ref, (label, net) in TESTPOINTS.items():
    VALUE[ref], FIELDS[ref], DNP[ref] = label, {"Footprint": "TestPoint:TestPoint_Pad_D1.5mm"}, False
    NET[(ref, "1")] = net
# values that read better on a drawing than the working notes kept in PARTS
VALUE.update({
    "U1": "LMR36520FADDAR", "J1": "KF128-5.08-2P", "J5": "1x5 2,54 mm (không lắp)", "J6": "TYPE-C-31-M-12",
    "SW1": "TS-1187A (RESET)", "SW2": "TS-1187A (BOOT)", "LED1": "LED đỏ", "LED2": "LED trắng",
})

LIB = kisch.Lib()
ROOT = kisch.uid("root", PROJECT)
SHEETS = []
DONE = set()          # (ref, pin) already connected or marked unconnected


def kind_of(ref):
    if ref.startswith("LED"):
        return "LED"
    if ref.startswith("FB"):
        return "FB"
    if ref == "D1":
        return "SK"
    if ref == "D2":
        return "TVS"
    if ref[0] == "C":
        return "CP" if PARTS[ref][0].split(":")[1].startswith("CP_") else "C"
    return {"R": "R", "L": "L", "F": "F"}[ref[0]]


def orient(ref, first_net):
    first = "1"
    if first_net is not None:
        cands = [p for p in ("1", "2") if NET[(ref, p)] == first_net]
        assert cands, f"{ref} has no pad on {first_net}: {NET[(ref, '1')]}, {NET[(ref, '2')]}"
        first = cands[0]
    second = "2" if first == "1" else "1"
    kind = kind_of(ref)
    rev = False
    if kind in ("SK", "TVS", "LED"):
        rev = first == "1"            # pad 1 is the cathode; the symbol draws the anode on the first side
    if kind == "CP":
        rev = first == "2"            # pad 1 is the plus plate
    return first, second, kind, rev


class S(kisch.Sheet):
    def __init__(self, key, title, filename, page):
        super().__init__(LIB, PROJECT, ROOT, key, title, filename, page, paper=PAPER)
        self.sides, self.nflag = {}, 0
        SHEETS.append(self)

    def put(self, ref, sym, x, y, **kw):
        self.place(ref, sym, x, y, VALUE[ref], fields=FIELDS[ref], dnp=DNP[ref], **kw)

    def vpart(self, ref, x, ytop, top_net=None):
        """Vertical two-pin part with its top pin end at (x, ytop). Returns the bottom pin end."""
        first, second, kind, rev = orient(ref, top_net)
        kw = {}
        if kind == "LED":             # the light arrows are drawn where the texts normally go
            kw = dict(ref_at=(x + 4.3, ytop + 2.81, "left"), val_at=(x + 4.3, ytop + 5.11, "left"))
        self.put(ref, LIB.two(kind, "V", first, second, rev), x, ytop + 3.81, **kw)
        DONE.update({(ref, "1"), (ref, "2")})
        return self.P(ref, second)

    def hpart(self, ref, xleft, y, left_net=None):
        """Horizontal two-pin part with its left pin end at (xleft, y). Returns the right pin end."""
        first, second, kind, rev = orient(ref, left_net)
        kw = {}
        if kind == "LED":
            kw = dict(ref_at=(xleft + 3.81, y - 4.4, None))
        elif kind in ("C", "CP"):
            kw = dict(ref_at=(xleft + 3.81, y - 3.6, None), val_at=(xleft + 3.81, y + 3.7, None))
        self.put(ref, LIB.two(kind, "H", first, second, rev), xleft + 3.81, y, **kw)
        DONE.update({(ref, "1"), (ref, "2")})
        return self.P(ref, second)

    def term(self, pt, net, d="R"):
        """End a wire at pt with the right thing for the net: ground or rail symbol, or a global label."""
        if net in GNDS:
            self.power(net, pt, GNDS[net])
        elif net in RAILS:
            self.power(net, pt, "rail")
        else:
            self.glabel(net, pt, d)

    def flag(self, pt):
        x, y = self._pt(pt)
        self.nflag += 1
        self.place(f"#FLG{self.page}{self.nflag:02d}", LIB.flag(), x, y, "PWR_FLAG")

    def down(self, x, y, refs, top_net, end_dir="D"):
        """Chain of vertical parts hanging from (x, y); the net between two parts gets a local label."""
        net, pt = top_net, (x, y)
        for i, ref in enumerate(refs):
            if i:
                self.llabel(net, (x, pt[1] + 2.54))
            top = self.w(pt, (x, pt[1] + (5.08 if i else 2.54)))
            pt = self.vpart(ref, x, top[1], net)
            first = orient(ref, net)[0]
            net = NET[(ref, "2" if first == "1" else "1")]
        if net in GNDS:
            self.term(pt, net)
        else:
            end = self.w(pt, (pt[0], pt[1] + 2.54))
            self.term(end, net, end_dir)
        return pt

    def rail(self, x, y, net, groups, pitch=10.16):
        """Horizontal rail of `net`, its symbol at the left end, with one hanging chain per entry of groups."""
        xs = [round(x + pitch * i, 2) for i in range(len(groups))]
        self.w((x - 5.08, y), (xs[-1], y))
        self.term((x - 5.08, y), net, "L")
        for xi, refs in zip(xs, groups):
            self.down(xi, y, refs if isinstance(refs, (list, tuple)) else [refs], net)
        return xs

    def stub(self, ref, pin, length=7.62):
        """Connect one pin of a box symbol by its net: stub + label / power symbol, or a no-connect mark."""
        key = (ref, str(pin))
        pt = self.P(ref, pin)
        DONE.add(key)
        net = NET.get(key)
        if net is None:
            self.nc(pt)
            return
        side = "L" if str(pin) in self.sides[ref]["left"] else "R"
        end = (pt[0] - length, pt[1]) if side == "L" else (pt[0] + length, pt[1])
        self.w(pt, end)
        self.term(end, net, side)

    def box(self, ref, name, left, right, width, x, y, prefix="U", extra=None, top=(), bottom=(), **kw):
        sym = LIB.box(name, left, right, width, ref=prefix, extra=extra, top=top, bottom=bottom)
        self.put(ref, sym, x, y, **kw)
        self.sides[ref] = LIB.meta[sym]
        want = {k[1] for k in NET if k[0] == ref}
        have = set(LIB.pins[sym])
        assert want <= have, f"{ref}: symbol lacks pins {sorted(want - have)}"

    def auto(self, ref, length=7.62):
        """Stub every left / right pin of a box that has not been wired by hand."""
        pins = self.sides[ref]["left"] | self.sides[ref]["right"]
        for pin in sorted(pins, key=lambda p: (self.P(ref, p)[0], self.P(ref, p)[1])):
            if (ref, pin) not in DONE:
                self.stub(ref, pin, length)

    def bus(self, ref, pins, dx, end="down", extra=2.54):
        """Join pins of one side that share a net with a vertical wire dx away from the pin ends, then terminate it."""
        pts = sorted((self.P(ref, p) for p in pins), key=lambda p: p[1])
        nets = {NET[(ref, str(p))] for p in pins}
        assert len(nets) == 1, (ref, pins, nets)
        net = nets.pop()
        xb = pts[0][0] + dx
        for p in pts:
            self.w(p, (xb, p[1]))
        for p in pins:
            DONE.add((ref, str(p)))
        if end == "down":
            e = self.w((xb, pts[0][1]), (xb, pts[-1][1] + extra))
        else:
            e = self.w((xb, pts[-1][1]), (xb, pts[0][1] - extra))
        self.term(e, net)
        return xb

    def tp(self, ref, x, y):
        self.put(ref, LIB.testpoint(), x, y)
        DONE.add((ref, "1"))
        return (x, y)

    def heading(self, text, x=20.32, y=22.86):
        self.text(text, x, y, size=3.0, bold=True)

    def sub(self, text, x, y):
        self.text(text, x, y, size=1.6, bold=True)

    def notes(self, x, y, lines, title="Ghi chú", wrap=0):
        """Bulleted note lines under a bold title; wrap = characters per line (0: no wrapping). Returns the next y."""
        self.text(title, x, y, size=1.6, bold=True)
        i = 0
        for line in lines:
            parts = textwrap.wrap(line, wrap) if wrap else [line]
            for j, part in enumerate(parts):
                i += 1
                self.text(("•  " if j == 0 else "    ") + part, x, round(y + 3.81 * i, 2), size=1.4)
        return round(y + 3.81 * (i + 2), 2)


def tact(lib, w, h):
    """Push button: pads 1 and 2 are one terminal, pads 3 and 4 the other (TS-1187A datasheet: A-B, C-D)."""
    y1, y2, ym = -2.54, -5.08, -3.81
    return [
        lib._poly([(0, y1), (1.27, y1), (1.27, y2), (0, y2)], width=0.15),
        lib._poly([(w, y1), (w - 1.27, y1), (w - 1.27, y2), (w, y2)], width=0.15),
        lib._poly([(1.27, ym), (3.0, ym)], width=0.15), lib._poly([(w - 1.27, ym), (w - 3.0, ym)], width=0.15),
        lib._circle((3.4, ym), 0.4, width=0.15), lib._circle((w - 3.4, ym), 0.4, width=0.15),
        lib._poly([(3.0, ym + 1.0), (w - 3.0, ym + 1.0)], width=0.15), lib._poly([(w / 2, ym + 1.0), (w / 2, ym + 2.0)], width=0.15),
        lib._poly([(w / 2 - 0.8, ym + 2.0), (w / 2 + 0.8, ym + 2.0)], width=0.15),
    ]


TACT = ([("1", "~"), ("2", "~")], [("3", "~"), ("4", "~")])


# =============================== page 2: power ===============================
def sheet_power():
    s = S("nguon", "Nguồn 9-36 V sang 3,3 V", "nguon.kicad_sch", 2)
    s.heading("NGUỒN VÀO 9–36 V  →  3,3 V")
    R = 93.98                                    # y of the main line: input on the left, +3V3 on the right

    def Y(d):
        return round(R + d, 2)

    s.box("J1", "KF128_2P", [], [("1", "+"), ("2", "-")], 10.16, 22.86, Y(-2.54), prefix="J")
    DONE.update({("J1", "1"), ("J1", "2")})
    s.w(("J1", "1"), (44.45, R)); s.llabel("VIN_RAW", (36.83, R))
    s.w(("J1", "2"), (38.1, Y(2.54)), (38.1, Y(7.62))); s.term((38.1, Y(7.62)), "GND")
    p = s.hpart("F1", 44.45, R, "VIN_RAW")
    s.w(p, (59.69, R)); s.llabel("VIN_F", (53.34, R))
    p = s.hpart("D1", 59.69, R, "VIN_F")
    s.w(p, (81.28, R), (96.52, R), (104.14, R)); s.llabel("VIN_P", (68.58, R))
    s.down(81.28, R, ["D2"], "VIN_P")
    s.down(96.52, R, ["C1"], "VIN_P")
    p = s.hpart("L1", 104.14, R, "VIN_P")
    left = [None, None, None, ("2", "VIN"), ("3", "EN"), None, ("4", "PG"), None, ("1", "PGND"), ("9", "EP")]
    right = [("7", "BOOT"), None, None, ("8", "SW"), None, ("5", "FB"), None, ("6", "VCC")]
    s.box("U1", "LMR36520", left, right, 22.86, 205.74, Y(-10.16))
    caps = [124.46, 142.24, 160.02, 177.8]
    s.w(p, *[(x, R) for x in caps], (198.12, R), ("U1", "2")); s.llabel("VIN_FLT", (113.03, R))
    for x, ref in zip(caps, ["C5", "C2", "C3", "C4"]):
        s.down(x, R, [ref], "VIN_FLT")
    s.w(("U1", "3"), (198.12, Y(2.54)), (198.12, R))
    s.nc(s.P("U1", "4"))
    s.w(("U1", "1"), (195.58, Y(12.7)), (195.58, Y(15.24)), (195.58, Y(20.32))); s.term((195.58, Y(20.32)), "GND")
    s.w(("U1", "9"), (195.58, Y(15.24)))
    DONE.update({("U1", str(i)) for i in range(1, 10)})
    xr = s.P("U1", "8")[0]
    s.w(("U1", "7"), (241.3, Y(-7.62))); s.llabel("BOOT", (xr + 1.27, Y(-7.62)))
    s.vpart("C6", 241.3, Y(-7.62), "BOOT")
    s.w(("U1", "8"), (241.3, R), (251.46, R)); s.llabel("SW", (xr + 1.27, R))
    p = s.hpart("L2", 251.46, R, "SW")
    xs = [269.24, 284.48, 299.72, 314.96, 330.2, 345.44, 358.14, 370.84]
    s.w(p, *[(x, R) for x in xs])
    s.w((269.24, R), (269.24, Y(2.54)))
    b = s.vpart("R1", 269.24, Y(2.54), "+3V3")
    s.w(b, (269.24, Y(12.7)), (269.24, Y(15.24)))
    b = s.vpart("R2", 269.24, Y(15.24), "FB"); s.term(b, "GND")
    s.w((269.24, Y(12.7)), (246.38, Y(12.7)), (246.38, Y(5.08)), ("U1", "5")); s.llabel("FB", (248.92, Y(12.7)))
    s.w(("U1", "6"), (236.22, Y(10.16)), (236.22, Y(15.24))); s.llabel("VCC_BUCK", (xr + 1.27, Y(10.16)))
    b = s.vpart("C7", 236.22, Y(15.24), "VCC_BUCK"); s.term(b, "GND")
    for x, ref in zip(xs[1:4], ["C8", "C9", "C10"]):
        s.down(x, R, [ref], "+3V3")
    s.down(330.2, R, ["R3", "LED1"], "+3V3")
    s.tp("TP1", 345.44, R)
    s.flag((358.14, R))
    s.term((370.84, R), "+3V3")
    t = s.tp("TP2", 345.44, Y(22.86)); s.w(t, (345.44, Y(27.94)), (358.14, Y(27.94)))
    s.term((345.44, Y(27.94)), "GND"); s.flag((358.14, Y(27.94)))
    for text, x in (("Bảo vệ đầu vào", 44.45), ("Lọc đầu vào", 104.14), ("Buck 3,3 V", 205.74), ("Đầu ra +3V3", 269.24)):
        s.sub(text, x, Y(-25.4))
    s.notes(22.86, Y(48.26), [
        "J1: cọc vít bước 5,08 mm. F1: cầu chì tự phục hồi 0,5 A. D1: diode Schottky 2 A / 100 V chống đấu ngược cực.",
        "D2: TVS 36 V, kẹp xung ở tối đa 58,1 V, dưới mức chịu 65 V của U1. L1 cùng tụ hai phía làm bộ lọc nhiễu đầu vào.",
        "U1: buck đồng bộ 2 A, 400 kHz, điện áp vào 4,2–65 V. EN nối thẳng VIN nên chạy ngay khi có nguồn. PG không dùng.",
        "Điện áp ra = 1 V × (1 + R1 / R2) = 1 × (1 + 51k / 22k) = 3,32 V.",
        "LED1 báo có 3,3 V. TP1, TP2 là pad trần để đo.",
        "Bốn lỗ bắt vít M3 (H1–H4) không mạ, không nối điện nên không vẽ trong sơ đồ.",
    ])
    return s


# =============================== page 3: ESP32 ===============================
def sheet_mcu():
    s = S("esp32", "Vi điều khiển ESP32-S3", "esp32.kicad_sch", 3)
    s.heading("VI ĐIỀU KHIỂN ESP32-S3")
    left = [("2", "3V3"), None, ("3", "EN"), None, ("27", "IO0"), None, ("31", "IO38"), None, ("13", "IO19/USB_D-"),
            ("14", "IO20/USB_D+"), ("37", "TXD0"), ("36", "RXD0"), None, ("1", "GND"), ("40", "GND"), ("41", "EP")]
    unused = [("4", "IO4"), ("5", "IO5"), ("6", "IO6"), ("7", "IO7"), ("12", "IO8"), ("17", "IO9"), ("18", "IO10"), ("19", "IO11"),
              ("23", "IO21"), ("15", "IO3"), ("16", "IO46"), ("24", "IO47"), ("25", "IO48"), ("26", "IO45"), ("28", "IO35"),
              ("29", "IO36"), ("30", "IO37"), ("33", "IO40"), ("34", "IO41"), ("35", "IO42"), ("38", "IO2"), ("39", "IO1")]
    right = [("8", "IO15"), ("21", "IO13"), ("22", "IO14"), ("9", "IO16"), ("20", "IO12"), ("32", "IO39"), None,
             ("10", "IO17"), ("11", "IO18"), None] + unused
    s.box("U2", "ESP32-S3-WROOM-1", left, right, 40.64, 177.8, 45.72)
    s.bus("U2", ["1", "40", "41"], -5.08)
    s.auto("U2")
    s.text("SPI, ngắt và reset tới W5500 (trang 4)", 248.92, 55.25, size=1.4)
    s.text("UART tới IC cách ly (trang 5)", 248.92, 67.95, size=1.4)
    s.text("22 chân IO còn lại để hở", 233.68, 100.33, size=1.4)
    # decoupling
    s.rail(55.88, 48.26, "+3V3", ["C12", "C11"], pitch=12.7)
    s.sub("Tụ lọc nguồn, đặt sát chân 3V3 của U2", 45.72, 39.37)
    # reset
    s.term((55.88, 81.28), "+3V3")
    b = s.vpart("R9", 55.88, 81.28, "+3V3")
    s.w(b, (55.88, 91.44), (55.88, 93.98))
    b = s.vpart("C13", 55.88, 93.98, "EN"); s.term(b, "GND")
    s.box("SW1", "TACT_SW", *TACT, 10.16, 78.74, 88.9, prefix="SW", extra=tact)
    s.w((43.18, 91.44), (55.88, 91.44), (73.66, 91.44), ("SW1", "1")); s.glabel("EN", (43.18, 91.44), "L")
    s.w(("SW1", "2"), (73.66, 93.98), (73.66, 91.44))
    s.w(("SW1", "3"), (96.52, 91.44), (96.52, 93.98), (96.52, 99.06)); s.w(("SW1", "4"), (96.52, 93.98)); s.term((96.52, 99.06), "GND")
    DONE.update({("SW1", str(i)) for i in range(1, 5)})
    s.sub("Reset: R9 kéo EN lên, C13 tạo trễ khi cấp nguồn, SW1 kéo EN xuống GND", 45.72, 72.39)
    # boot
    s.box("SW2", "TACT_SW", *TACT, 10.16, 78.74, 121.92, prefix="SW", extra=tact)
    s.w((60.96, 124.46), (73.66, 124.46), ("SW2", "1")); s.glabel("IO0", (60.96, 124.46), "L")
    s.w(("SW2", "2"), (73.66, 127.0), (73.66, 124.46))
    s.w(("SW2", "3"), (96.52, 124.46), (96.52, 127.0), (96.52, 132.08)); s.w(("SW2", "4"), (96.52, 127.0)); s.term((96.52, 132.08), "GND")
    DONE.update({("SW2", str(i)) for i in range(1, 5)})
    s.sub("Boot: giữ SW2 rồi nhấn SW1 để vào chế độ nạp. Khi chạy, SW2 là nút bấm trên IO0", 45.72, 114.3)
    # status LED
    s.glabel("STATUS", (53.34, 152.4), "L")
    s.w((53.34, 152.4), (58.42, 152.4))
    p = s.hpart("R4", 58.42, 152.4, "STATUS")
    s.w(p, (76.2, 152.4)); s.llabel("LED2_A", (67.31, 152.4))
    p = s.hpart("LED2", 76.2, 152.4, "LED2_A")
    s.w(p, (88.9, 152.4), (88.9, 157.48)); s.term((88.9, 157.48), "GND")
    s.sub("Đèn trạng thái trên IO38, sáng khi IO38 ở mức cao", 45.72, 143.51)
    # programming header
    s.box("J5", "HDR_1x5", [], [("1", "GND"), ("2", "TXD0"), ("3", "RXD0"), ("4", "D-"), ("5", "D+")], 12.7, 45.72, 180.34, prefix="J")
    s.stub("J5", "1", 25.4)
    s.auto("J5")
    s.sub("Cổng nạp: UART0 và USB của ESP32. Hàng lỗ 2,54 mm để trống, không lắp chân", 45.72, 172.72)
    # test points
    for ref, y in (("TP3", 187.96), ("TP4", 198.12)):
        t = s.tp(ref, 119.38, y); e = s.w(t, (132.08, y)); s.term(e, NET[(ref, "1")], "R")
    s.sub("Điểm đo UART phía ESP32", 114.3, 180.34)
    s.notes(233.68, 144.78, [
        "U2: ESP32-S3-WROOM-1-N8, flash 8 MB, anten mạch in. Thay được bằng bản N16 cùng chân.",
        "IO15 / IO13 / IO14 / IO16: SPI tới W5500. IO12: ngắt. IO39: reset W5500.",
        "IO17 phát, IO18 thu: UART đi qua IC cách ly ra cổng ngoài.",
        "IO19 / IO20 là USB gốc của ESP32, chỉ đưa ra hàng lỗ J5.",
        "IO0, IO3, IO45, IO46 là chân strapping. IO0 có nút BOOT; ba chân còn lại để hở, dùng mức mặc định trong chip.",
    ])
    return s


# =============================== page 4: Ethernet ===============================
def sheet_eth():
    s = S("ethernet", "Ethernet W5500", "ethernet.kicad_sch", 4)
    s.heading("ETHERNET W5500")
    left = [("32", "SCSn"), ("33", "SCLK"), ("34", "MISO"), ("35", "MOSI"), ("36", "INTn"), ("37", "RSTn"), None,
            ("30", "XI/CLKIN"), ("31", "XO"), None, ("10", "EXRES1"), ("20", "TOCAP"), ("22", "1V2O"), None,
            ("43", "PMODE2"), ("44", "PMODE1"), ("45", "PMODE0"), None, ("23", "RSVD"), ("38", "RSVD"), ("39", "RSVD"),
            ("40", "RSVD"), ("41", "RSVD"), ("42", "RSVD")]
    right = [("2", "TXP"), ("1", "TXN"), None, ("6", "RXP"), ("5", "RXN"), None, ("25", "LINKLED"), ("27", "ACTLED"),
             ("24", "SPDLED"), ("26", "DUPLED"), None, ("28", "VDD"), ("4", "AVDD"), ("8", "AVDD"), ("11", "AVDD"),
             ("15", "AVDD"), ("17", "AVDD"), ("21", "AVDD"), None, ("29", "GND"), ("3", "AGND"), ("9", "AGND"),
             ("14", "AGND"), ("16", "AGND"), ("19", "AGND"), ("48", "AGND"), None, ("7", "DNC"), ("12", "NC"), ("13", "NC"),
             ("18", "VBG"), ("46", "NC"), ("47", "NC")]
    s.box("U5", "W5500", left, right, 40.64, 139.7, 40.64)
    av = ["4", "8", "11", "15", "17", "21"]                   # AVDD pins on one wire
    xb = s.P("U5", "4")[0] + 5.08
    for p in av:
        s.w(("U5", p), (xb, s.P("U5", p)[1])); DONE.add(("U5", p))
    s.w((xb, s.P("U5", "21")[1]), (xb, s.P("U5", "4")[1]), (200.66, s.P("U5", "4")[1])); s.term((200.66, s.P("U5", "4")[1]), "+3V3A")
    s.stub("U5", "28", 7.62)
    s.bus("U5", ["29", "3", "9", "14", "16", "19", "48"], 5.08)
    s.stub("U5", "23", 5.08)
    s.auto("U5")
    # pull-ups
    s.rail(40.64, 43.18, "+3V3", ["R19", "R20", "R21"], pitch=12.7)
    s.sub("Điện trở kéo lên", 30.48, 34.29)
    # crystal
    s.box("Y1", "XTAL_3225_4P", [("1", "OSC1"), ("2", "GND")], [("3", "OSC2"), ("4", "GND")], 17.78, 55.88, 91.44, prefix="Y")
    s.w((35.56, 93.98), (43.18, 93.98), (48.26, 93.98), ("Y1", "1")); s.glabel("XI", (35.56, 93.98), "L")
    s.w(("Y1", "3"), (81.28, 93.98), (86.36, 93.98), (93.98, 93.98)); s.glabel("XO", (93.98, 93.98), "R")
    s.down(43.18, 93.98, ["C34"], "XI"); s.down(86.36, 93.98, ["C35"], "XO")
    p = s.hpart("R10", 60.96, 83.82, "XI")
    s.w((60.96, 83.82), (48.26, 83.82), (48.26, 93.98)); s.w(p, (81.28, 83.82), (81.28, 93.98))
    s.w(("Y1", "2"), (50.8, 96.52), (50.8, 101.6)); s.term((50.8, 101.6), "GND")
    s.w(("Y1", "4"), (78.74, 96.52), (78.74, 101.6)); s.term((78.74, 101.6), "GND")
    DONE.update({("Y1", str(i)) for i in range(1, 5)})
    s.sub("Thạch anh 25 MHz, tụ tải 12 pF", 30.48, 76.2)
    # bias parts
    for x, net, ref in ((38.1, "EXRES", "R18"), (53.34, "TOCAP", "C26"), (68.58, "V1V2", "C27")):
        s.glabel(net, (x, 127.0), "U"); s.down(x, 127.0, [ref], net)
    # supply
    s.term((30.48, 165.1), "+3V3"); s.w((30.48, 165.1), (38.1, 165.1), (45.72, 165.1))
    p = s.hpart("FB1", 45.72, 165.1, "+3V3")
    xs = [60.96, 73.66, 86.36, 99.06, 111.76]
    s.w(p, *[(x, 165.1) for x in xs], (123.19, 165.1), (134.62, 165.1)); s.flag((123.19, 165.1)); s.term((134.62, 165.1), "+3V3A")
    for x, ref in zip(xs, ["C32", "C28", "C29", "C30", "C31"]):
        s.down(x, 165.1, [ref], "+3V3A")
    s.down(38.1, 165.1, ["C33"], "+3V3")
    s.sub("Nguồn analog +3V3A lọc qua hạt ferrite FB1; tụ 100 nF đặt sát từng nhóm chân AVDD", 30.48, 153.67)
    # TX termination
    s.w((231.14, 43.18), (238.76, 43.18), (254.0, 43.18), (269.24, 43.18)); s.term((231.14, 43.18), "+3V3A")
    for x, ref in ((238.76, "R11"), (254.0, "R12"), (269.24, "R13")):
        s.w((x, 43.18), (x, 45.72)); s.vpart(ref, x, 45.72, "+3V3A")
    s.w((220.98, 58.42), (238.76, 58.42), (238.76, 53.34)); s.glabel("ETH_TXP", (220.98, 58.42), "L")
    s.w((220.98, 63.5), (254.0, 63.5), (254.0, 53.34)); s.glabel("ETH_TXN", (220.98, 63.5), "L")
    s.w((269.24, 53.34), (269.24, 55.88), (269.24, 58.42)); s.w((269.24, 55.88), (279.4, 55.88)); s.glabel("TCT", (279.4, 55.88), "R")
    b = s.vpart("C22", 269.24, 58.42, "TCT"); s.term(b, "GND")
    s.sub("Đầu cuối phát", 220.98, 34.29)
    # RX termination
    y1, yr, y2 = 86.36, 96.52, 106.68
    s.glabel("ETH_RXP", (220.98, y1), "L"); s.w((220.98, y1), (233.68, y1), (243.84, y1))
    p = s.hpart("C23", 243.84, y1, "ETH_RXP"); s.w(p, (261.62, y1)); s.glabel("MAG_RDP", (261.62, y1), "R")
    s.w((233.68, y1), (233.68, y1 + 2.54)); s.vpart("R14", 233.68, y1 + 2.54, "ETH_RXP")
    b = s.vpart("R15", 233.68, yr, "RCT"); s.w(b, (233.68, y2))
    s.glabel("ETH_RXN", (220.98, y2), "L"); s.w((220.98, y2), (233.68, y2), (243.84, y2))
    p = s.hpart("C24", 243.84, y2, "ETH_RXN"); s.w(p, (261.62, y2)); s.glabel("MAG_RDN", (261.62, y2), "R")
    s.glabel("RCT", (220.98, yr), "L"); s.w((220.98, yr), (233.68, yr), (248.92, yr))
    p = s.hpart("C25", 248.92, yr, "RCT"); s.w(p, (261.62, yr), (261.62, yr + 2.54)); s.term((261.62, yr + 2.54), "GND")
    s.sub("Đầu cuối thu", 220.98, 78.74)
    # LED resistors
    for y, a, ref, k in ((127.0, "ACTLED", "R16", "LED_ACT_K"), (137.16, "LINKLED", "R17", "LED_LINK_K")):
        s.glabel(a, (220.98, y), "L"); s.w((220.98, y), (233.68, y))
        p = s.hpart(ref, 233.68, y, a); s.w(p, (251.46, y)); s.glabel(k, (251.46, y), "R")
    s.sub("Điện trở hạn dòng cho hai LED của cổng RJ45", 220.98, 119.38)
    # RJ45
    jl = [("1", "TD+"), ("2", "TD-"), ("4", "TCT"), None, ("3", "RD+"), ("6", "RD-"), ("5", "RCT"), None, None,
          ("9", "LED_XANH_A"), ("12", "LED_VÀNG_A"), None, ("10", "LED_XANH_K"), ("11", "LED_VÀNG_K"), None, ("7", "NC"), None,
          ("8", "CHS_GND"), ("SH1", "VỎ"), ("SH2", "VỎ")]
    s.box("J3", "HR911105A", jl, [], 30.48, 335.28, 38.1, prefix="J")
    s.bus("J3", ["9", "12"], -5.08, end="up", extra=0)
    s.bus("J3", ["8", "SH1", "SH2"], -5.08)
    s.auto("J3")
    s.notes(220.98, 149.86, [
        "U5: W5500, Ethernet 10/100 qua SPI. Mạch đầu cuối theo sơ đồ mẫu của WIZnet cho cổng RJ45 có sẵn biến áp.",
        "Phát: R11, R12 = 49,9 Ω kéo lên +3V3A; điểm giữa biến áp (TCT) nối +3V3A qua R13 = 10 Ω, lọc bằng C22.",
        "Thu: C23, C24 = 6,8 nF nối tiếp; R14, R15 = 49,9 Ω về điểm giữa RCT, lọc bằng C25.",
        "R18 = 12,4 kΩ 1 % đặt dòng chuẩn. C26, C27 là tụ của mạch ổn áp 1,2 V trong chip.",
        "PMODE[2:0] để hở (có kéo lên trong chip): tự dò tốc độ và song công.",
        "RSVD chân 23 nối GND; RSVD chân 38–42 để hở theo datasheet.",
        "R21 giữ SCSn ở mức cao để W5500 không nhận lệnh khi ESP32 đang khởi động; R19, R20 giữ RSTn, INTn ở mức xác định.",
        "J3: HR911105A có biến áp và hai LED bên trong. LED xanh báo hoạt động (ACT), LED vàng báo kết nối (LINK). Vỏ nối GND.",
    ])
    return s


# =============================== page 5: isolated UART ===============================
def sheet_uart():
    s = S("uart", "UART TTL cách ly", "uart-cach-ly.kicad_sch", 5)
    s.heading("UART TTL CÁCH LY")
    left = [("1", "VDD"), ("7", "VDDL"), None, ("3", "VI1"), ("5", "VO3"), ("6", "VO4"), None, ("4", "VI2"), ("2", "GNDA"), ("8", "GNDA")]
    right = [("16", "VISO"), None, ("14", "VO1"), ("12", "VI3"), ("13", "VO2"), None, ("10", "SEL"), ("11", "VI4"), ("15", "GNDB"),
             ("9", "GNDB")]
    s.box("U3", "CA-IS3642HVW", left, right, 30.48, 165.1, 71.12)
    # side A supply and decoupling
    s.w(("U3", "1"), (157.48, 73.66)); s.w(("U3", "7"), (157.48, 76.2), (157.48, 73.66), (157.48, 58.42))
    xs = [121.92, 134.62, 147.32]
    s.w((114.3, 58.42), *[(x, 58.42) for x in xs], (157.48, 58.42)); s.term((114.3, 58.42), "+3V3")
    for x, ref in zip(xs, ["C14", "C16", "C17"]):
        s.down(x, 58.42, [ref], "+3V3")
    DONE.update({("U3", "1"), ("U3", "7")})
    s.bus("U3", ["4", "2", "8"], -5.08)
    s.stub("U3", "3"); s.stub("U3", "5"); s.stub("U3", "6")
    # side B supply and decoupling
    s.w(("U3", "16"), (203.2, 73.66), (203.2, 58.42))
    xs = [213.36, 226.06, 238.76, 251.46, 264.16]
    s.w((203.2, 58.42), *[(x, 58.42) for x in xs]); s.term((264.16, 58.42), "VISO")
    for x, ref in zip(xs[:2], ["C18", "C15"]):
        s.down(x, 58.42, [ref], "VISO")
    s.tp("TP5", 238.76, 58.42)
    s.flag((251.46, 58.42))
    DONE.add(("U3", "16"))
    s.bus("U3", ["10", "11", "15", "9"], 5.08)
    s.stub("U3", "13")
    # transmit path: isolator -> R6 -> connector D-
    s.w(("U3", "14"), (264.16, 78.74)); s.llabel("ISO_TX", (205.74, 78.74))
    p = s.hpart("R6", 264.16, 78.74, "ISO_TX")
    DONE.add(("U3", "14"))
    jl = [("A7", "D-"), ("B7", "D-"), None, ("A6", "D+"), ("B6", "D+"), None, ("A4", "VBUS"), ("A9", "VBUS"), ("B4", "VBUS"),
          ("B9", "VBUS"), None, ("A5", "CC1"), ("B5", "CC2"), ("A8", "SBU1"), ("B8", "SBU2"), None, ("A1", "GND"), ("A12", "GND"),
          ("B1", "GND"), ("B12", "GND"), ("S1", "VỎ")]
    s.box("J6", "USB-C_16P", jl, [], 22.86, 314.96, 76.2, prefix="J")
    s.w(p, (284.48, 78.74), (307.34, 78.74), ("J6", "A7"))
    s.w(("J6", "B7"), (307.34, 81.28), (307.34, 78.74))
    s.w((284.48, 78.74), (284.48, 73.66)); s.glabel("PORT_DM", (284.48, 73.66), "U")
    # receive path: connector D+ -> R7 -> Schmitt buffer U4 -> isolator
    s.box("U4", "SN74LVC1G17", [None, ("4", "Y"), None, None], [None, ("2", "A"), None, ("1", "NC")], 15.24, 223.52, 109.22,
          top=[("5", "VCC", 7.62)], bottom=[("3", "GND", 7.62)], ref_at=(236.22, 124.46, "left"), val_at=(236.22, 126.6, "left"))
    s.w(("U3", "12"), (213.36, 81.28), (213.36, 114.3), ("U4", "4")); s.llabel("ISO_RX_BUF", (199.39, 81.28))
    s.w(("U4", "5"), (231.14, 93.98), (243.84, 93.98), (254.0, 93.98), (264.16, 93.98)); s.term((264.16, 93.98), "VISO")
    s.down(243.84, 93.98, ["C21"], "VISO")
    s.w((254.0, 93.98), (254.0, 106.68)); s.vpart("R8", 254.0, 106.68, "VISO")
    s.w(("U4", "2"), (254.0, 114.3), (266.7, 114.3)); s.llabel("ISO_RX_IN", (242.57, 114.3))
    q = s.hpart("R7", 266.7, 114.3, "ISO_RX_IN")
    s.term(s.P("U4", "3"), "GND_ISO")
    s.nc(s.P("U4", "1"))
    DONE.update({("U3", "12"), ("U4", "1"), ("U4", "2"), ("U4", "3"), ("U4", "4"), ("U4", "5")})
    s.w(q, (284.48, 114.3), (294.64, 114.3), (294.64, 86.36), (304.8, 86.36), ("J6", "A6"))
    s.w(("J6", "B6"), (304.8, 88.9), (304.8, 86.36))
    s.w((284.48, 114.3), (284.48, 119.38)); s.glabel("PORT_DP", (284.48, 119.38), "D")
    DONE.update({("J6", k) for k in ("A7", "B7", "A6", "B6")})
    for k in ("A4", "A9", "B4", "B9"):
        s.w(("J6", k), (299.72, s.P("J6", k)[1])); DONE.add(("J6", k))
    s.w((299.72, s.P("J6", "A4")[1]), (299.72, s.P("J6", "B9")[1])); s.llabel("VBUS_NC", (300.99, s.P("J6", "A4")[1]))
    s.bus("J6", ["A1", "A12", "B1", "B12", "S1"], -5.08)
    s.auto("J6")
    # ESD diode
    s.box("D3", "PESD5V0S2BT", [("1", "K1"), ("2", "K2")], [("3", "A")], 15.24, 264.16, 142.24, prefix="D")
    s.auto("D3")
    s.sub("Diode chống tĩnh điện cho hai đường dữ liệu", 243.84, 135.89)
    t = s.tp("TP6", 193.04, 116.84); s.w(t, (193.04, 121.92), (203.2, 121.92)); s.term((193.04, 121.92), "GND_ISO"); s.flag((203.2, 121.92))
    # isolation barrier
    xc = 165.1 + 15.24
    s.line([(xc, 38.1), (xc, 66.04)], width=0.4); s.line([(xc, 99.06), (xc, 142.24)], width=0.4)
    s.sub("KHE CÁCH LY", xc + 2.54, 142.24)
    s.sub("Phía mạch chính, mass GND", 114.3, 45.72)
    s.sub("Phía thiết bị ngoài, mass GND_ISO", 205.74, 45.72)
    y = s.notes(22.86, 45.72, [
        "Phát: ESP32 IO17 → U3 (VI1 → VO1) → R6 → J6 D− → chân RX của thiết bị ngoài.",
        "Thu: chân TX của thiết bị ngoài → J6 D+ → R7 → U4 → U3 (VI3 → VO3) → ESP32 IO18.",
        "Mức logic hai phía đều là 3,3 V. Phía thiết bị ngoài chạy bằng VISO do U3 tạo ra, không lấy nguồn của thiết bị.",
    ], title="Chiều tín hiệu", wrap=64)
    s.notes(22.86, y, [
        "Khe cách ly: trên mạch in, đồng của hai phía cách nhau 7,6 mm và chỉ U3 bắc qua khe.",
        "U3: CA-IS3642HVW, cách ly 5 kV, có sẵn bộ nguồn cách ly cấp cho VISO. SEL nối GND_ISO nên VISO = 3,3 V.",
        "VI2, VI4 không dùng nên nối mass; VO2, VO4 để hở.",
        "Đầu ra của U3 mặc định ở mức cao khi phía bên kia mất nguồn, đúng với mức nghỉ của UART.",
        "R8 giữ đường thu ở mức cao khi chưa cắm cáp. U4 là cổng đệm Schmitt, chân vào chịu được 5,5 V.",
        "R6, R7 hạn dòng nối tiếp. D3 kẹp tĩnh điện về GND_ISO.",
        "J6 dùng đầu USB-C làm đầu cắm UART mức 3,3 V, không phải cổng USB. Bốn chân VBUS chỉ nối với nhau, không nối vào mạch. CC, SBU để hở.",
    ], wrap=64)
    return s


def title_block(sheet_title):
    return (f'(title_block (title "{kisch.esc(TITLE)}") (date "{DATE}") (rev "{REV}") '
            f'(comment 1 "{kisch.esc(sheet_title)}") (comment 2 "Sơ đồ sinh từ danh sách nối dây của mạch in, đã đối chiếu tự động từng chân"))')


def root_sheet(sheets):
    o = [f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "{ROOT}") {kisch.paper_expr(PAPER)}',
         title_block("Trang bìa"), "(lib_symbols)"]

    def text(s, x, y, size=1.27, bold=False):
        b = " (bold yes)" if bold else ""
        o.append(f'(text "{kisch.esc(s)}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}){b}) (justify left bottom)) '
                 f'(uuid "{kisch.uid("root", "t", s, x, y)}"))')

    text(TITLE, 25.4, 38.1, 5.0, True)
    text("Rev B · mạch in 2 lớp 80 × 66 mm · ESP32-S3-WROOM-1 · Ethernet W5500 · UART TTL 3,3 V cách ly 5 kV · nguồn vào 9–36 V", 25.4, 46.99, 2.0)
    inside = {
        "nguon": ["Cọc vít 9–36 V", "Cầu chì, chống ngược cực, TVS, lọc", "Buck LMR36520 ra +3V3"],
        "esp32": ["ESP32-S3-WROOM-1-N8", "Reset, Boot, đèn trạng thái", "Hàng lỗ nạp chương trình"],
        "ethernet": ["W5500 qua SPI", "Thạch anh 25 MHz", "Đầu cuối và cổng RJ45 có biến áp"],
        "uart": ["CA-IS3642HVW cách ly 5 kV", "Cổng đệm Schmitt, chống tĩnh điện", "Đầu cắm UART phía thiết bị ngoài"],
    }
    for i, sh in enumerate(sheets):
        x, y, w, h = round(25.4 + 96.52 * i, 2), 66.04, 81.28, 45.72
        o.append(f'(sheet (at {x} {y}) (size {w} {h}) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) '
                 f'(stroke (width 0.2) (type solid)) (fill (color 255 255 194 1.0)) (uuid "{sh.suid}") '
                 f'(property "Sheetname" "{kisch.esc(sh.title)}" (at {x} {round(y - 0.9, 2)} 0) (effects (font (size 1.8 1.8)) (justify left bottom))) '
                 f'(property "Sheetfile" "{sh.file}" (at {x} {round(y + h + 0.9, 2)} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
                 f'(instances (project "{PROJECT}" (path "/{ROOT}" (page "{sh.page}")))))')
        text(f"Trang {sh.page}", round(x + 3.81, 2), round(y + 10.16, 2), 2.2, True)
        for j, line in enumerate(inside[sh.key]):
            text(line, round(x + 3.81, 2), round(y + 20.32 + 6.35 * j, 2), 1.6)
    notes = ["Đường mạch giữa các trang nối với nhau qua nhãn cùng tên. Tên đường mạch trong sơ đồ trùng với tên trong file mạch in.",
             "Ký hiệu nguồn: +3V3 (nguồn chính), +3V3A (nguồn analog của W5500), VISO (3,3 V phía cách ly). Mass: GND và GND_ISO.",
             "+3V3 cấp cho cả bốn khối. Trang 3 nối trang 4 bằng SPI, ngắt và reset; nối trang 5 bằng UART_TX, UART_RX.",
             "J5 là hàng lỗ không lắp chân. TP1–TP6 là sáu pad đo trần, trên mạch in ghi 3V3, GND, TXD, RXD, VISO, GISO.",
             "Dấu × trên chân linh kiện nghĩa là chân đó để hở có chủ ý.",
             "PWR_FLAG là ký hiệu của KiCad báo đường nguồn đã có nguồn cấp, không phải linh kiện."]
    text("Cách đọc", 25.4, 134.62, 2.2, True)
    for i, line in enumerate(notes):
        text("•  " + line, 25.4, round(143.51 + 6.35 * i, 2), 1.8)
    o.append('(sheet_instances (path "/" (page "1")))')
    o.append("(embedded_fonts no))")
    return "\n".join(o) + "\n"


sheets = [sheet_power(), sheet_mcu(), sheet_eth(), sheet_uart()]
missing = sorted(k for k in NET if k not in DONE)
assert not missing, f"pins never connected in the drawing: {missing}"
os.makedirs(OUT, exist_ok=True)


def write(name, text):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(text)


for sh in sheets:
    write(sh.file, sh.render(title_block(sh.title)))
write(PROJECT + ".kicad_sch", root_sheet(sheets))
write(LIB.nick + ".kicad_sym", LIB.library_file())
write("sym-lib-table", f'(sym_lib_table\n  (version 7)\n  (lib (name "{LIB.nick}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB.nick}.kicad_sym")'
                       f'(options "")(descr "Ký hiệu dùng trong sơ đồ này"))\n)\n')
write("fp-lib-table", '(fp_lib_table\n  (version 7)\n  (lib (name "lcsc")(type "KiCad")(uri "${KIPRJMOD}/lcsc.pretty")'
                      '(options "")(descr "Footprint theo thư viện chính thức JLCEDA / EasyEDA"))\n)\n')
write(PROJECT + ".kicad_pro", json.dumps({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3},
                                          "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
                                          "sheets": [], "text_variables": {}}, indent=2) + "\n")

def without_models(text):
    """Drop the (model ...) blocks of a footprint: they point at 3D files on the machine that converted it."""
    while True:
        i = text.find("(model ")
        if i < 0:
            return text
        depth, j = 0, i
        while True:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
            if depth == 0:
                break
        text = text[:i].rstrip(" \t") + text[j:]


# the footprints the board takes from the converted LCSC library, so the project is complete on its own
used = sorted({fp.split(":")[1] for fp in (FIELDS[r]["Footprint"] for r in PARTS) if fp.startswith("lcsc:")})
src = sys.argv[3] if len(sys.argv) > 3 else ""
copied = 0
if src:
    os.makedirs(os.path.join(OUT, "lcsc.pretty"), exist_ok=True)
    for name in used:
        write(os.path.join("lcsc.pretty", name + ".kicad_mod"), without_models(open(os.path.join(src, name + ".kicad_mod")).read()))
        copied += 1
print("written", [sh.file for sh in sheets], "symbols", sum(len(sh.symbols) for sh in sheets), "| lcsc footprints copied", copied, "of", len(used))
