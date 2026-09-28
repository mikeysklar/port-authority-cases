# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
Two-plate sandwich case for the Smart HIL Hub Rev C.

Run headless:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_case.py

Writes next to this file:
    sandwich_case.FCStd        parametric model, every setting in the Params sheet
    top_plate.step/.stl        STL laid outer face down for printing
    bottom_plate.step/.stl     STL laid outer face down for printing

Frame: PCB coordinates from the Rev C gerbers, board back face on Z=0,
components up. Each plate carries its own bosses at the four mount holes, so
the stack needs no spacers: M2.5 screws go straight through plate, boss, PCB,
boss, plate.

The top plate sits top_gap above the board, which is the STEMMA QT height
(2.9 mm, DEALON 1.0-4PWB drawing) so the plate also rests on both ports.
Everything taller pokes through snug cutouts. Cutouts on the board edge run
out through the plate edge. Webs under min 3 mm between neighbours are filled
in rather than left as flakes, which is why the four USB-A / JST XH / 100 uF
cap stacks share one notch along the bottom edge.

PORT AUTHORITY is engraved on the outer face of both plates, mirrored on the
bottom one so it reads from underneath.
"""

import os
import struct
import zipfile

import Draft
import FreeCAD as App
import Part

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()

DOC_PATH = os.path.join(HERE, "sandwich_case.FCStd")
FONT = os.path.expanduser("~/Library/Fonts/Data70.ttf")

PARAMS = [
    ("# board, Rev C gerbers. Facts, not design choices", None, ""),
    ("board_w", 91.44, "outline X"),
    ("board_h", 35.56, "outline Y"),
    ("board_t", 1.6, "PCB thickness"),
    ("board_r", 2.54, "outline corner radius"),
    ("hole_inset", 2.54, "mount hole centre from left and bottom edge"),
    ("hole_dx", 86.36, "mount hole pitch X"),
    ("hole_dy", 30.48, "mount hole pitch Y"),
    ("# stack", None, ""),
    ("plate_t", 2.0, "plate thickness"),
    ("border", 1.5, "plate overhang past the board outline"),
    ("top_gap", 2.9, "PCB top to top plate underside. STEMMA QT body height"),
    ("bot_gap", 3.0, "PCB back to bottom plate. Clears THT leads (~2.5)"),
    ("boss_d", 5.0, "boss diameter at the mount holes"),
    ("screw_d", 2.7, "M2.5 clearance hole"),
    ("# cutouts", None, ""),
    ("cut_margin", 0.5, "clearance around each part poking through"),
    ("# text", None, ""),
    ("font", "'%s" % FONT, "TTF for the engraving"),
    ("text_depth", 0.6, "engrave depth"),
    ("text_top", "'PORT AUTHORITY", "top plate string, one line"),
    ("text_top_size", 6.6, "top plate letter height"),
    ("text_top_x", "=board_w / 2", "top plate text centre X"),
    ("text_top_y", 17.56, "top plate text centre Y, strip under the DC jack"),
    ("text_bot_1", "'PORT", "bottom plate first line"),
    ("text_bot_2", "'AUTHORITY", "bottom plate second line"),
    ("text_bot_size", 11.0, "bottom plate letter height"),
    ("text_bot_gap", 3.0, "bottom plate gap between lines"),
    ("text_bot_x", "=board_w / 2", "bottom plate text centre X"),
    ("text_bot_y", "=board_h / 2", "bottom plate text block centre Y"),
    ("# derived, do not edit", None, ""),
    ("plate_w", "=board_w + 2 * border", "plate outline X"),
    ("plate_h", "=board_h + 2 * border", "plate outline Y"),
    ("plate_r", "=board_r + border", "plate corner radius"),
    ("top_z0", "=board_t + top_gap", "top plate underside Z"),
    ("top_z1", "=board_t + top_gap + plate_t", "top plate outer face Z"),
    ("bot_z1", "=-bot_gap", "bottom plate inner face Z"),
    ("bot_z0", "=-bot_gap - plate_t", "bottom plate outer face Z"),
    ("stack_h", "=plate_t * 2 + top_gap + bot_gap + board_t", "overall height"),
]

# Top plate cutouts: (name, x0, x1, y0, y1) in PCB mm at the part bodies.
# cut_margin is added on every closed side. None = open through that plate edge.
CUTS = [
    # X1-X8 USB-A + JST XH stacks and caps C24 C27 C30: webs between them are
    # all under 3 mm, so one notch.
    ("usbA_band", 7.31, 84.02, None, 13.06),
    ("cap_C3", 1.16, 6.46, 5.48, 10.78),
    ("usbC_X9_X10", 9.50, 31.60, 28.60, None),
    ("dcjack_X11", 61.61, 70.61, 22.06, None),
    ("term_J1", 72.95, 79.95, 28.28, None),
    # SW2 body (6.66 x 5.4, DSHP 1.27-4P drawing) so the switches can be set
    # with the case closed.
    ("dip_SW2", 84.17, 90.83, 23.21, 28.61),
]
# Body-to-body fills where the web between two cuts is too thin to print.
WEBS = [
    ("web_X11_J1", 70.61, 72.95, 28.28, None),
]

# Hub stand-in, PCB mm. (name, x0, x1, y0, y1, h above the top face).
PARTS = [
    ("X1_usbA", 7.31, 20.41, -0.2, 9.8, 6.5),
    ("X3_usbA", 29.01, 42.11, -0.2, 9.8, 6.5),
    ("X5_usbA", 49.33, 62.43, -0.2, 9.8, 6.5),
    ("X7_usbA", 70.92, 84.02, -0.2, 9.8, 6.5),
    ("X2_xh4", 7.77, 20.17, 6.53, 12.28, 7.0),
    ("X4_xh4", 29.36, 41.76, 6.40, 12.15, 7.0),
    ("X6_xh4", 49.68, 62.08, 6.40, 12.15, 7.0),
    ("X8_xh4", 71.27, 83.67, 6.40, 12.15, 7.0),
    ("X10_xh4", 19.20, 31.60, 30.02, 35.77, 7.0),
    ("C3_100u", 1.16, 6.46, 5.48, 10.78, 5.8),
    ("C24_100u", 23.51, 28.81, 7.76, 13.06, 5.8),
    ("C27_100u", 43.96, 49.26, 7.38, 12.68, 5.8),
    ("C30_100u", 65.80, 71.10, 7.76, 13.06, 5.8),
    ("X9_usbC", 9.50, 18.44, 28.60, 35.95, 3.26),
    ("X11_dcjack", 61.61, 70.61, 22.06, 36.06, 11.0),
    ("J1_term", 72.95, 79.95, 28.28, 35.48, 8.5),
    ("D1_sma", 65.09, 70.29, 18.89, 21.49, 2.3),
    ("STEMMA1", -0.3, 4.0, 11.48, 17.48, 2.9),
    ("STEMMA2", -0.3, 4.0, 20.88, 26.88, 2.9),
    ("SW1_slide", 88.01, 92.4, 5.40, 13.40, 1.4),
    ("SW2_dip4", 84.17, 90.83, 23.21, 28.61, 2.3),
]
THT = ["X1_usbA", "X3_usbA", "X5_usbA", "X7_usbA", "X2_xh4", "X4_xh4",
       "X6_xh4", "X8_xh4", "X10_xh4", "X11_dcjack", "J1_term"]
LEAD_LEN = 2.5
SMD_FLOOR = 1.5      # tallest ordinary SMD part (SOT-23), for the clash check

EPS = 0.1
P = "Params."


def build_sheet(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "parameter")
    sheet.set("B1", "value")
    sheet.set("C1", "note")
    for row, (name, value, note) in enumerate(PARAMS, start=2):
        sheet.set("A%d" % row, name)
        if value is not None:
            sheet.set("B%d" % row, str(value))
            sheet.setAlias("B%d" % row, name)
            sheet.set("C%d" % row, note)
    sheet.setColumnWidth("A", 130)
    sheet.setColumnWidth("B", 130)
    sheet.setColumnWidth("C", 400)
    doc.recompute()
    return sheet


def bind(obj, prop, expr):
    obj.setExpression(prop, expr)


def box(doc, name, x, y, z, length, width, height):
    o = doc.addObject("Part::Box", name)
    for prop, expr in (("Length", length), ("Width", width), ("Height", height),
                       ("Placement.Base.x", x), ("Placement.Base.y", y),
                       ("Placement.Base.z", z)):
        bind(o, prop, expr)
    return o


def cyl(doc, name, x, y, z, radius, height):
    o = doc.addObject("Part::Cylinder", name)
    for prop, expr in (("Radius", radius), ("Height", height),
                       ("Placement.Base.x", x), ("Placement.Base.y", y),
                       ("Placement.Base.z", z)):
        bind(o, prop, expr)
    return o


def rounded_plate(doc, prefix, z):
    """Board outline grown by border, as 2 boxes + 4 corner cylinders."""
    x0, y0 = "-" + P + "border", "-" + P + "border"
    r = P + "plate_r"
    objs = [
        box(doc, prefix + "_spanX", "%s + %s" % (x0, r), y0, z,
            "%splate_w - 2 * %s" % (P, r), P + "plate_h", P + "plate_t"),
        box(doc, prefix + "_spanY", x0, "%s + %s" % (y0, r), z,
            P + "plate_w", "%splate_h - 2 * %s" % (P, r), P + "plate_t"),
    ]
    for tag, cx, cy in (("bl", "0", "0"), ("br", "1", "0"),
                        ("tl", "0", "1"), ("tr", "1", "1")):
        objs.append(cyl(
            doc, "%s_corner_%s" % (prefix, tag),
            "%s + %s + %s * (%splate_w - 2 * %s)" % (x0, r, cx, P, r),
            "%s + %s + %s * (%splate_h - 2 * %s)" % (y0, r, cy, P, r),
            z, r, P + "plate_t"))
    return objs


HOLES = (("bl", "0", "0"), ("br", "1", "0"), ("tl", "0", "1"), ("tr", "1", "1"))


def hole_xy(ix, iy):
    return ("%shole_inset + %s * %shole_dx" % (P, ix, P),
            "%shole_inset + %s * %shole_dy" % (P, iy, P))


def cut_box(doc, name, x0, x1, y0, y1, z0, z1, margin=True):
    m = " - %scut_margin" % P if margin else ""
    mp = " + %scut_margin" % P if margin else ""
    far = "%sborder + 1" % P
    xa = "%g%s" % (x0, m)
    xb = "%g%s" % (x1, mp)
    ya = "-(%s)" % far if y0 is None else "%g%s" % (y0, m)
    yb = "%sboard_h + %s" % (P, far) if y1 is None else "%g%s" % (y1, mp)
    return box(doc, name, xa, ya, z0, "(%s) - (%s)" % (xb, xa),
               "(%s) - (%s)" % (yb, ya), "(%s) - (%s)" % (z1, z0))


def engraving(doc, name, string, size, x, y, z_face, mirrored):
    """ShapeString extruded text_depth into the plate from its outer face."""
    ss = Draft.make_shapestring("PORT AUTHORITY", FONT, 7.0)
    ss.Label = name + "_string"
    ss.Justification = "Middle-Center"
    bind(ss, "FontFile", P + "font")
    bind(ss, "String", string)
    bind(ss, "Size", size)
    if mirrored:
        ss.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 180)
    bind(ss, "Placement.Base.x", x)
    bind(ss, "Placement.Base.y", y)
    if mirrored:
        bind(ss, "Placement.Base.z", "%s - %g" % (z_face, EPS))
    else:
        bind(ss, "Placement.Base.z", "%s - %stext_depth" % (z_face, P))
    ex = doc.addObject("Part::Extrusion", name)
    ex.Base = ss
    ex.DirMode = "Custom"
    ex.Dir = App.Vector(0, 0, 1)
    ex.Solid = True
    bind(ex, "LengthFwd", "%stext_depth + %g" % (P, EPS))
    ss.Visibility = False
    return ex


def build_top(doc):
    z0, z1 = P + "top_z0", P + "top_z1"
    adds = rounded_plate(doc, "Top", z0)
    cuts = []
    for tag, ix, iy in HOLES:
        hx, hy = hole_xy(ix, iy)
        adds.append(cyl(doc, "TopBoss_" + tag, hx, hy, P + "board_t",
                        P + "boss_d / 2", P + "top_gap"))
        cuts.append(cyl(doc, "TopScrew_" + tag, hx, hy,
                        "%sboard_t - %g" % (P, EPS), P + "screw_d / 2",
                        "%stop_gap + %splate_t + %g" % (P, P, 2 * EPS)))
    # Cutouts go through the plate only, never the bosses.
    za, zb = "%s - %g" % (z0, EPS), "%s + %g" % (z1, EPS)
    for name, x0, x1, y0, y1 in CUTS:
        cuts.append(cut_box(doc, "TopCut_" + name, x0, x1, y0, y1, za, zb))
    for name, x0, x1, y0, y1 in WEBS:
        cuts.append(cut_box(doc, "TopCut_" + name, x0, x1, y0, y1, za, zb,
                            margin=False))
    cuts.append(engraving(doc, "TopText", P + "text_top", P + "text_top_size",
                          P + "text_top_x", P + "text_top_y", z1, False))
    return finish(doc, "TopPlate", adds, cuts)


def build_bottom(doc):
    z0 = P + "bot_z0"
    adds = rounded_plate(doc, "Bot", z0)
    cuts = []
    for tag, ix, iy in HOLES:
        hx, hy = hole_xy(ix, iy)
        adds.append(cyl(doc, "BotBoss_" + tag, hx, hy, P + "bot_z1",
                        P + "boss_d / 2", P + "bot_gap"))
        cuts.append(cyl(doc, "BotScrew_" + tag, hx, hy,
                        "%s - %g" % (z0, EPS), P + "screw_d / 2",
                        "%splate_t + %sbot_gap + %g" % (P, P, 2 * EPS)))
    # Mirrored about X, so the first line sits at low Y to read on top once
    # the case is rolled over its long edge.
    offset = "(%stext_bot_size + %stext_bot_gap) / 2" % (P, P)
    for i, sign in ((1, "-"), (2, "+")):
        cuts.append(engraving(doc, "BotText%d" % i, P + "text_bot_%d" % i,
                              P + "text_bot_size", P + "text_bot_x",
                              "%stext_bot_y %s %s" % (P, sign, offset),
                              z0, True))
    return finish(doc, "BottomPlate", adds, cuts)


def finish(doc, name, adds, cuts):
    body = doc.addObject("Part::MultiFuse", name + "_body")
    body.Shapes = adds
    body.Refine = True
    tool = doc.addObject("Part::MultiFuse", name + "_cuts")
    tool.Shapes = cuts
    out = doc.addObject("Part::Cut", name)
    out.Base = body
    out.Tool = tool
    out.Refine = True
    for o in adds + cuts + [body, tool]:
        o.Visibility = False
    return out


def build_hub(doc):
    bw, bh, bt, r = 91.44, 35.56, 1.6, 2.54
    plate = Part.makeBox(bw - 2 * r, bh, bt, App.Vector(r, 0, 0))
    plate = plate.fuse(Part.makeBox(bw, bh - 2 * r, bt, App.Vector(0, r, 0)))
    for cx, cy in ((r, r), (bw - r, r), (r, bh - r), (bw - r, bh - r)):
        plate = plate.fuse(Part.makeCylinder(r, bt, App.Vector(cx, cy, 0)))
    for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02), (88.9, 33.02)):
        plate = plate.cut(Part.makeCylinder(1.25, bt + 1, App.Vector(cx, cy, -0.5)))
    parts, leads = [], []
    for name, x0, x1, y0, y1, h in PARTS:
        parts.append(Part.makeBox(x1 - x0, y1 - y0, h, App.Vector(x0, y0, bt)))
        if name in THT:
            leads.append(Part.makeBox(x1 - x0, y1 - y0, LEAD_LEN,
                                      App.Vector(x0, y0, -LEAD_LEN)))
    objs = []
    for name, shape in (("HubPCB", plate.removeSplitter()),
                        ("HubParts", Part.makeCompound(parts)),
                        ("HubLeads", Part.makeCompound(leads))):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        objs.append(o)
    return objs


# View state. FreeCAD 1.1 has no ViewObject headless, so GuiDocument.xml is
# written into the saved FCStd directly. Layout from kicad2freecad-enclosures.

VIEW_PROP = """        <ViewProvider name="%s" expanded="0">
            <Properties Count="6" TransientCount="0">
                <Property name="LineColor" type="App::PropertyColor" status="1">
                    <PropertyColor value="%d"/>
                </Property>
                <Property name="LineWidth" type="App::PropertyFloatConstraint" status="1">
                    <Float value="%.4f"/>
                </Property>
                <Property name="PointColor" type="App::PropertyColor" status="1">
                    <PropertyColor value="%d"/>
                </Property>
                <Property name="ShapeAppearance" type="App::PropertyMaterialList" status="1">
                    <MaterialList file="%s" version="3"/>
                </Property>
                <Property name="Transparency" type="App::PropertyPercent" status="1">
                    <Integer value="%d"/>
                </Property>
                <Property name="Visibility" type="App::PropertyBool" status="1">
                    <Bool value="%s"/>
                </Property>
            </Properties>
        </ViewProvider>
"""


def _rgb(spec):
    h = spec.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (r << 24) | (g << 16) | (b << 8) | 0xFF


def _material_blob(diffuse, transparency):
    return (struct.pack("<I", 1)
            + struct.pack("<I", _rgb("#333333"))
            + struct.pack("<I", diffuse)
            + struct.pack("<I", 0x000000FF)
            + struct.pack("<I", 0x000000FF)
            + struct.pack("<ff", 0.2, transparency / 100.0)
            + struct.pack("<III", 0, 0, 0))


def write_view_state(doc_path, styles, hidden):
    entries, blobs = [], {}
    for i, name in enumerate(list(styles) + hidden):
        color, line, transp = styles.get(name, ("#808080", "#000000", 0))
        blob = "ShapeAppearance" if i == 0 else "ShapeAppearance%d" % i
        blobs[blob] = _material_blob(_rgb(color), transp)
        entries.append(VIEW_PROP % (name, _rgb(line), 2.0, _rgb(line), blob,
                                    transp, "false" if name in hidden else "true"))
    xml = ("<?xml version='1.0' encoding='utf-8'?>\n"
           '<Document SchemaVersion="1">\n'
           '    <ViewProviderData Count="%d">\n%s    </ViewProviderData>\n'
           "</Document>\n" % (len(entries), "".join(entries)))
    with zipfile.ZipFile(doc_path, "r") as z:
        keep = [(n, z.read(n)) for n in z.namelist()
                if n != "GuiDocument.xml" and n not in blobs]
    with zipfile.ZipFile(doc_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in keep:
            z.writestr(n, data)
        z.writestr("GuiDocument.xml", xml)
        for n, data in blobs.items():
            z.writestr(n, data)


def check(top, bot, hub, sheet):
    pcb, parts, leads = (o.Shape for o in hub)
    t, b = top.Shape, bot.Shape
    ok = True

    def report(label, good, detail=""):
        nonlocal ok
        ok = ok and good
        print("%-5s %-24s %s" % ("ok" if good else "FAIL", label, detail))

    for label, s in (("top", t), ("bottom", b)):
        report(label + " valid", s.isValid())
        report(label + " solids", len(s.Solids) == 1, "%d" % len(s.Solids))
    for label, s, other in (("top vs pcb", t, pcb), ("top vs parts", t, parts),
                            ("bottom vs pcb", b, pcb),
                            ("bottom vs leads", b, leads)):
        v = s.common(other).Volume
        report(label + " clash", v < 1e-3, "%.4f mm3" % v)
    smd = Part.makeBox(91.44, 35.56, SMD_FLOOR, App.Vector(0, 0, 1.6))
    for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02), (88.9, 33.02)):
        smd = smd.cut(Part.makeCylinder(sheet.boss_d / 2 + 0.01, SMD_FLOOR,
                                        App.Vector(cx, cy, 1.6)))
    v = t.common(smd).Volume
    report("top vs SMD floor clash", v < 1e-3, "%.4f mm3" % v)
    report("top bosses on pcb", t.distToShape(pcb)[0] < 1e-3)
    report("bottom bosses on pcb", b.distToShape(pcb)[0] < 1e-3)
    stemma = [Part.makeBox(4.3, 6.0, 2.9, App.Vector(-0.3, y, 1.6))
              for y in (11.48, 20.88)]
    for i, s in enumerate(stemma, 1):
        report("top rests on STEMMA%d" % i, t.distToShape(s)[0] < 1e-3)
    through = [n for n, *_r, h in PARTS if h > sheet.top_gap]
    print("parts through the top plate:", ", ".join(through))
    print("stack height %.2f mm, M2.5 screw + nut" % sheet.stack_h)
    return ok


doc = App.newDocument("sandwich_case")
sheet = build_sheet(doc)
top = build_top(doc)
bot = build_bottom(doc)
hub = build_hub(doc)
doc.recompute()

ok = check(top, bot, hub, sheet)

doc.saveAs(DOC_PATH)
hidden = [o.Name for o in doc.Objects
          if hasattr(o, "Visibility") and not o.Visibility
          and o.TypeId != "Spreadsheet::Sheet"]
write_view_state(DOC_PATH, {
    "TopPlate": ("#1A1A1F", "#D9FF00", 45),
    "BottomPlate": ("#1A1A1F", "#FF2D9B", 45),
    "HubPCB": ("#0E3A2C", "#00E5C7", 0),
    "HubParts": ("#B0B0B8", "#404040", 0),
    "HubLeads": ("#FF8C00", "#FF8C00", 0),
}, hidden)

for obj, stem in ((top, "top_plate"), (bot, "bottom_plate")):
    obj.Shape.exportStep(os.path.join(HERE, stem + ".step"))
    s = obj.Shape.copy()
    if obj is top:
        s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.translate(App.Vector(0, 0, -s.BoundBox.ZMin))
    s.exportStl(os.path.join(HERE, stem + ".stl"))

print("wrote", DOC_PATH)
print("CHECKS PASS" if ok else "CHECKS FAIL")
