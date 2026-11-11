"""Small writer for KiCad 9 schematics (.kicad_sch): symbols, wires, labels, power symbols, sheets.

Conventions used by this writer
- Schematic coordinates are mm, y pointing down. Symbol library coordinates have y pointing up.
- Symbols are never rotated or mirrored: every orientation is its own library symbol, so a pin of a
  symbol placed at (X, Y) sits at (X + px, Y - py).
- Wires are axis-aligned. finish() splits them at every pin, wire end and label that touches them and
  adds a junction wherever three or more connections meet, so all connections happen at wire ends.
"""
import uuid

NS = uuid.UUID("5d0f6e52-3a41-4c8e-9b6e-2f1a7c1b9d10")
FONT = "(effects (font (size 1.27 1.27)))"


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def n(v):
    s = "%.4f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def stroke(width=0.254, kind="default"):
    return f"(stroke (width {n(width)}) (type {kind}))"


def paper_expr(paper):
    """A standard size name such as "A3", or (width, height) in mm for a custom page."""
    if isinstance(paper, str):
        return f'(paper "{paper}")'
    return f'(paper "User" {n(paper[0])} {n(paper[1])})'


class Lib:
    """Library symbols, created on demand and embedded in each sheet that uses them."""

    def __init__(self, nick="module"):
        self.nick = nick
        self.text = {}      # symbol name -> s-expression
        self.pins = {}      # symbol name -> {pin number: (x, y)} in library coordinates
        self.meta = {}      # symbol name -> dict(kind=..., orient=...)

    # ---- drawing helpers (library coordinates) ----
    @staticmethod
    def _poly(pts, fill="none", width=0.254):
        return "(polyline (pts %s) %s (fill (type %s)))" % (" ".join(f"(xy {n(x)} {n(y)})" for x, y in pts), stroke(width), fill)

    @staticmethod
    def _rect(a, b, fill="none", width=0.254):
        return f"(rectangle (start {n(a[0])} {n(a[1])}) (end {n(b[0])} {n(b[1])}) {stroke(width)} (fill (type {fill})))"

    @staticmethod
    def _arc(s, m, e, width=0.254):
        return f"(arc (start {n(s[0])} {n(s[1])}) (mid {n(m[0])} {n(m[1])}) (end {n(e[0])} {n(e[1])}) {stroke(width)} (fill (type none)))"

    @staticmethod
    def _circle(c, r, fill="none", width=0.254):
        return f"(circle (center {n(c[0])} {n(c[1])}) (radius {n(r)}) {stroke(width)} (fill (type {fill})))"

    @staticmethod
    def _pin(num, name, x, y, angle, length, etype="passive", hide=False):
        h = " (hide yes)" if hide else ""
        return (f'(pin {etype} line (at {n(x)} {n(y)} {angle}) (length {n(length)}){h} '
                f'(name "{esc(name)}" {FONT}) (number "{esc(num)}" {FONT}))')

    def _emit(self, name, ref, graphics, pins, hide_names, power=False, name_offset=1.016):
        head = [f'(symbol "{self.nick}:{name}"']
        if power:
            head.append("(power)")
        if hide_names:
            head.append("(pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))")
        else:
            head.append(f"(pin_names (offset {n(name_offset)}))")
        head.append("(exclude_from_sim no) (in_bom yes) (on_board yes)")
        hide = " (hide yes)" if power else ""
        head.append(f'(property "Reference" "{ref}" (at 0 2.54 0) (effects (font (size 1.27 1.27)){hide}))')
        head.append(f'(property "Value" "{esc(name)}" (at 0 -2.54 0) {FONT})')
        for p in ("Footprint", "Datasheet", "Description"):
            head.append(f'(property "{p}" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        body = f'(symbol "{name}_0_1" {" ".join(graphics)})' if graphics else ""
        pin_block = f'(symbol "{name}_1_1" {" ".join(pins)})'
        self.text[name] = "\n".join(head) + "\n" + body + "\n" + pin_block + "\n(embedded_fonts no))"

    # ---- two-pin parts ----
    def two(self, kind, orient, first, second, rev=False):
        """kind: R C CP L FB F D SK TVS LED. orient: H (first pin left) or V (first pin top).
        Polar parts draw anode / plus on the first side unless rev."""
        name = f"{kind}_{orient}_{first}{second}{'r' if rev else ''}"
        if name in self.text:
            return name
        g, plen = [], 1.27
        m = -1 if rev else 1

        def tr(p):
            x, y = p[0] * m, p[1]
            return (x, y) if orient == "H" else (y, -x)

        def poly(pts, fill="none", width=0.254):
            g.append(self._poly([tr(p) for p in pts], fill, width))

        if kind in ("R", "F", "FB"):
            a, b = tr((-2.54, 1.016)), tr((2.54, -1.016))
            g.append(self._rect(a, b))
            if kind == "F":
                poly([(-2.54, 0), (2.54, 0)])
            if kind == "FB":
                poly([(-1.5, -1.016), (-0.5, 1.016)]); poly([(0.5, -1.016), (1.5, 1.016)])
        elif kind in ("C", "CP"):
            plen = 3.302
            poly([(-0.508, 2.032), (-0.508, -2.032)], width=0.508)
            poly([(0.508, 2.032), (0.508, -2.032)], width=0.508)
            if kind == "CP":
                poly([(-2.3, 1.3), (-1.3, 1.3)]); poly([(-1.8, 1.8), (-1.8, 0.8)])
        elif kind == "L":
            for i in range(4):
                x0 = -2.54 + 1.27 * i
                g.append(self._arc(tr((x0, 0)), tr((x0 + 0.635, 0.635)), tr((x0 + 1.27, 0))))
        elif kind in ("D", "SK", "TVS", "LED"):
            plen = 2.54
            poly([(-1.27, 1.27), (-1.27, -1.27), (1.27, 0), (-1.27, 1.27)])
            if kind == "SK":
                poly([(0.77, 0.77), (0.77, 1.27), (1.27, 1.27), (1.27, -1.27), (1.77, -1.27), (1.77, -0.77)])
            elif kind == "TVS":
                poly([(0.77, 1.77), (1.27, 1.27), (1.27, -1.27), (1.77, -1.77)])
            else:
                poly([(1.27, 1.27), (1.27, -1.27)])
            if kind == "LED":
                for dx in (0.0, 1.0):
                    poly([(-0.4 + dx, 1.6), (0.5 + dx, 2.6)])
                    poly([(0.0 + dx, 2.6), (0.5 + dx, 2.6), (0.5 + dx, 2.1)])
        else:
            raise ValueError(kind)
        if orient == "H":
            pins = [self._pin(first, "~", -3.81, 0, 0, plen), self._pin(second, "~", 3.81, 0, 180, plen)]
            self.pins[name] = {first: (-3.81, 0.0), second: (3.81, 0.0)}
        else:
            pins = [self._pin(first, "~", 0, 3.81, 270, plen), self._pin(second, "~", 0, -3.81, 90, plen)]
            self.pins[name] = {first: (0.0, 3.81), second: (0.0, -3.81)}
        self._emit(name, kind[0], g, pins, hide_names=True)
        self.meta[name] = dict(kind="two", orient=orient)
        return name

    # ---- box symbols: origin at the top-left corner of the body ----
    def box(self, name, left, right, width, ref="U", extra=None, top=(), bottom=()):
        """left / right: lists of None (spacer) or (pin number, pin name). top / bottom: (pin number, pin name, x)."""
        if name in self.text:
            return name
        rows = max(len(left), len(right))
        height = 2.54 * (rows + 1)
        g = [self._rect((0, 0), (width, -height), fill="background")]
        if extra:
            g += extra(self, width, height)
        pins, pos = [], {}
        for i, p in enumerate(left):
            if p:
                y = -2.54 * (i + 1)
                pins.append(self._pin(p[0], p[1], -2.54, y, 0, 2.54)); pos[p[0]] = (-2.54, y)
        for i, p in enumerate(right):
            if p:
                y = -2.54 * (i + 1)
                pins.append(self._pin(p[0], p[1], width + 2.54, y, 180, 2.54)); pos[p[0]] = (width + 2.54, y)
        for num, pname, x in top:
            pins.append(self._pin(num, pname, x, 2.54, 270, 2.54)); pos[num] = (x, 2.54)
        for num, pname, x in bottom:
            pins.append(self._pin(num, pname, x, -height - 2.54, 90, 2.54)); pos[num] = (x, -height - 2.54)
        self.pins[name] = pos
        self._emit(name, ref, g, pins, hide_names=False)
        self.meta[name] = dict(kind="box", width=width, height=height,
                               left={p[0] for p in left if p}, right={p[0] for p in right if p})
        return name

    # ---- power symbols and test point ----
    def power(self, net, style):
        name = "PWR_" + net.replace("+", "P")
        if name in self.text:
            return name
        if style == "gnd":
            g = [self._poly([(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)], width=0)]
            angle = 270
        elif style == "gnd_iso":
            g = [self._poly([(0, 0), (0, -1.27)], width=0), self._poly([(-1.524, -1.27), (1.524, -1.27)]),
                 self._poly([(-0.9, -1.905), (0.9, -1.905)]), self._poly([(-0.3, -2.54), (0.3, -2.54)])]
            angle = 270
        else:
            g = [self._poly([(0, 0), (0, 1.524)], width=0), self._poly([(-0.762, 1.27), (0, 2.54), (0.762, 1.27)], width=0),
                 self._poly([(0, 1.524), (0, 2.54)], width=0)]
            angle = 90
        pins = [self._pin("1", "~", 0, 0, angle, 0, etype="power_in", hide=True)]
        self.pins[name] = {"1": (0.0, 0.0)}
        self._emit(name, "#PWR", g, pins, hide_names=True, power=True)
        self.text[name] = self.text[name].replace(f'(property "Value" "{name}"', f'(property "Value" "{esc(net)}"')
        self.meta[name] = dict(kind="power", up=style == "rail")
        return name

    def flag(self):
        """PWR_FLAG as in KiCad's own library: tells the rule check that a supply net is driven."""
        name = "PWR_FLAG"
        if name not in self.text:
            g = [self._poly([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)], width=0)]
            self.pins[name] = {"1": (0.0, 0.0)}
            self._emit(name, "#FLG", g, [self._pin("1", "~", 0, 0, 90, 0, etype="power_out")], hide_names=True, power=True)
            self.meta[name] = dict(kind="power", up=True)
        return name

    def library_file(self):
        """The symbols as a KiCad symbol library (.kicad_sym), so the project can list it in sym-lib-table."""
        o = ['(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") (generator_version "9.0")']
        for name in sorted(self.text):
            o.append(self.text[name].replace(f'(symbol "{self.nick}:{name}"', f'(symbol "{name}"', 1))
        o.append(")")
        return "\n".join(o) + "\n"

    def testpoint(self):
        name = "TestPoint"
        if name not in self.text:
            g = [self._circle((0, 2.032), 0.762), self._poly([(0, 0), (0, 1.27)], width=0)]
            self.pins[name] = {"1": (0.0, 0.0)}
            self._emit(name, "TP", g, [self._pin("1", "~", 0, 0, 90, 0)], hide_names=True)
            self.meta[name] = dict(kind="tp")
        return name


class Sheet:
    def __init__(self, lib, project, root_uuid, key, title, filename, page, paper="A3"):
        self.lib, self.project, self.root_uuid = lib, project, root_uuid
        self.key, self.title, self.file, self.page, self.paper = key, title, filename, page, paper
        self.suid = uid("sheet", key)
        self.path = f"/{root_uuid}/{self.suid}"
        self.symbols, self.wires, self.labels, self.extra = [], [], [], []
        self.pinpos = {}        # (ref, pin) -> (x, y)
        self.points = []        # every pin position (incl. power symbols, labels): places where wires must end
        self.used = set()       # symbol names used
        self.npwr = 0

    # ---- placing ----
    def place(self, ref, sym, x, y, value, fields=None, dnp=False, ref_at=None, val_at=None, hide_value=False):
        lib = self.lib
        self.used.add(sym)
        meta = lib.meta[sym]
        if meta["kind"] == "box":
            ra = ref_at or (x, y - 3.3, "left"); va = val_at or (x, y - 1.3, "left")
        elif meta["kind"] == "two" and meta["orient"] == "H":
            ra = ref_at or (x, y - 2.3, None); va = val_at or (x, y + 3.0, None)
        elif meta["kind"] == "two":
            ra = ref_at or (x + 2.0, y - 1.0, "left"); va = val_at or (x + 2.0, y + 1.3, "left")
        elif meta["kind"] == "tp":
            ra = ref_at or (x + 1.6, y - 2.6, "left"); va = val_at or (x + 1.6, y - 0.9, "left")
        else:
            ra = (x, y, None); va = val_at or ((x, y - 3.4, None) if meta.get("up") else (x, y + 4.1, None))
        is_power = meta["kind"] == "power"

        def prop(name, val, at, hide=False):
            j = f" (justify {at[2]})" if at[2] else ""
            h = " (hide yes)" if hide else ""
            return f'(property "{name}" "{esc(val)}" (at {n(at[0])} {n(at[1])} 0) (effects (font (size 1.27 1.27)){j}{h}))'

        s = [f'(symbol (lib_id "{lib.nick}:{sym}") (at {n(x)} {n(y)} 0) (unit 1) (exclude_from_sim no) '
             f'(in_bom {"no" if is_power else "yes"}) (on_board {"no" if is_power else "yes"}) (dnp {"yes" if dnp else "no"}) '
             f'(uuid "{uid(self.key, "sym", ref)}")']
        s.append(prop("Reference", ref, ra, hide=is_power))
        s.append(prop("Value", value, va, hide=hide_value))
        s.append(prop("Footprint", (fields or {}).get("Footprint", ""), (x, y, None), hide=True))
        s.append(prop("Datasheet", "", (x, y, None), hide=True))
        s.append(prop("Description", "", (x, y, None), hide=True))
        for k, v in (fields or {}).items():
            if k != "Footprint" and v:
                s.append(prop(k, v, (x, y, None), hide=True))
        for num, (px, py) in lib.pins[sym].items():
            s.append(f'(pin "{esc(num)}" (uuid "{uid(self.key, "pin", ref, num)}"))')
            pt = (round(x + px, 4), round(y - py, 4))
            self.pinpos[(ref, num)] = pt
            self.points.append(pt)
        s.append(f'(instances (project "{esc(self.project)}" (path "{self.path}" (reference "{esc(ref)}") (unit 1)))))')
        self.symbols.append("\n".join(s))

    def P(self, ref, num):
        return self.pinpos[(ref, str(num))]

    def _pt(self, p):
        if len(p) == 2 and isinstance(p[0], str):
            return self.P(*p)
        return (round(p[0], 4), round(p[1], 4))

    # ---- wiring ----
    def w(self, *pts):
        """Wire through the points; each element is (x, y) or a pin key (ref, pin). Segments must be axis-aligned."""
        pts = [self._pt(p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            assert abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6, f"diagonal wire {a} -> {b} on sheet {self.key}"
            self.wires.append((a, b))
        return pts[-1]

    def hv(self, a, b):
        a, b = self._pt(a), self._pt(b)
        return self.w(a, (b[0], a[1]), b)

    def vh(self, a, b):
        a, b = self._pt(a), self._pt(b)
        return self.w(a, (a[0], b[1]), b)

    def glabel(self, net, pt, d):
        x, y = self._pt(pt)
        angle, just = {"R": (0, "left"), "L": (180, "right"), "U": (90, "left"), "D": (270, "right")}[d]
        self.labels.append(
            f'(global_label "{esc(net)}" (shape passive) (at {n(x)} {n(y)} {angle}) (effects (font (size 1.27 1.27)) (justify {just})) '
            f'(uuid "{uid(self.key, "gl", net, x, y)}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) (hide yes))))')
        self.points.append((x, y))

    def llabel(self, net, pt, dx=0.0):
        x, y = self._pt(pt)
        self.labels.append(f'(label "{esc(net)}" (at {n(x + dx)} {n(y)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) '
                           f'(uuid "{uid(self.key, "ll", net, x + dx, y)}"))')
        self.points.append((round(x + dx, 4), y))

    def power(self, net, pt, style):
        x, y = self._pt(pt)
        self.npwr += 1
        sym = self.lib.power(net, style)
        self.place(f"#PWR{self.page}{self.npwr:02d}", sym, x, y, net)

    def nc(self, pt):
        x, y = self._pt(pt)
        self.extra.append(f'(no_connect (at {n(x)} {n(y)}) (uuid "{uid(self.key, "nc", x, y)}"))')

    def text(self, s, x, y, size=1.27, bold=False):
        b = " (bold yes)" if bold else ""
        self.extra.append(f'(text "{esc(s)}" (exclude_from_sim no) (at {n(x)} {n(y)} 0) (effects (font (size {n(size)} {n(size)}){b}) '
                          f'(justify left bottom)) (uuid "{uid(self.key, "t", s, x, y)}"))')

    def line(self, pts, kind="dash", width=0.2):
        self.extra.append("(polyline (pts %s) %s (uuid \"%s\"))" % (" ".join(f"(xy {n(x)} {n(y)})" for x, y in pts), stroke(width, kind),
                                                                     uid(self.key, "pl", pts)))

    def rect(self, a, b, kind="dash", width=0.15):
        self.extra.append(f'(rectangle (start {n(a[0])} {n(a[1])}) (end {n(b[0])} {n(b[1])}) {stroke(width, kind)} (fill (type none)) '
                          f'(uuid "{uid(self.key, "rc", a, b)}"))')

    # ---- output ----
    def _split(self):
        pts = set(self.points)
        for a, b in self.wires:
            pts.add(a); pts.add(b)
        out = []
        for a, b in self.wires:
            horiz = abs(a[1] - b[1]) < 1e-6
            inner = []
            for p in pts:
                if horiz and abs(p[1] - a[1]) < 1e-6 and min(a[0], b[0]) + 1e-6 < p[0] < max(a[0], b[0]) - 1e-6:
                    inner.append(p)
                if not horiz and abs(p[0] - a[0]) < 1e-6 and min(a[1], b[1]) + 1e-6 < p[1] < max(a[1], b[1]) - 1e-6:
                    inner.append(p)
            chain = sorted({a, b, *inner}, key=lambda p: (p[0], p[1]))
            out += list(zip(chain, chain[1:]))
        return sorted(set(out))

    def render(self, title_block):
        segs = self._split()
        count = {}
        for a, b in segs:
            count[a] = count.get(a, 0) + 1
            count[b] = count.get(b, 0) + 1
        pinset = {}
        for p in self.pinpos.values():
            pinset[p] = pinset.get(p, 0) + 1
        junctions = [p for p, c in count.items() if c + pinset.get(p, 0) >= 3]
        o = [f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "{uid("file", self.key)}") '
             f'{paper_expr(self.paper)}', title_block, "(lib_symbols"]
        o += [self.lib.text[s] for s in sorted(self.used)]
        o.append(")")
        for p in sorted(junctions):
            o.append(f'(junction (at {n(p[0])} {n(p[1])}) (diameter 0) (color 0 0 0 0) (uuid "{uid(self.key, "j", p)}"))')
        o += self.extra
        for a, b in segs:
            o.append(f'(wire (pts (xy {n(a[0])} {n(a[1])}) (xy {n(b[0])} {n(b[1])})) (stroke (width 0) (type default)) '
                     f'(uuid "{uid(self.key, "w", a, b)}"))')
        o += self.labels
        o += self.symbols
        o.append("(embedded_fonts no))")
        return "\n".join(o) + "\n"
