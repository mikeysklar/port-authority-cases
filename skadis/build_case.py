# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
Skeleton SKADIS frame for the Smart HIL Hub Rev C.

Run headless:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_case.py

Writes next to this file:
    skadis_case.FCStd          parametric model, every dimension in the Params sheet
    skadis_frame.step          the printable frame, world frame
    skadis_frame_print.stl     same frame laid on its back face for printing

World frame, as hung on the pegboard:
    X  along the board's long edge (board x from the Rev C gerbers)
    Z  up (board y). USB-C, DC jack and terminal block on top, USB-A pointing down
    Y  out of the wall is -Y. The SKADIS face is Y=0, the hub sits in front of it

Frame: two horizontal rails through the mount-hole rows, two ties at the
mount-hole columns, a standoff boss with a heat-set insert pocket at each hole.
The top rail runs past both board edges and hangs on two stock SKADIS hooks
sitting in notches on its underside. Hanging from the top keeps the bottom rail
pressed against the board.

Board facts come from the Rev C drill and outline files (no Rev C KiCad source
exists). The hub model is a stand-in: board, holes and connector blocks at the
Rev C pick-and-place positions. Connector sizes are approximate.
"""

import os
import struct
import zipfile

import FreeCAD as App
import Part

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()

DOC_PATH = os.path.join(HERE, "skadis_case.FCStd")
STEP_PATH = os.path.join(HERE, "skadis_frame.step")
STL_PATH = os.path.join(HERE, "skadis_frame_print.stl")

# name, value or formula, note. Formulas start with "=".
PARAMS = [
    ("# board, Rev C gerbers. Facts, not design choices", None, ""),
    ("board_w", 91.44, "outline X"),
    ("board_h", 35.56, "outline Y (world Z)"),
    ("board_t", 1.6, "PCB thickness"),
    ("board_r", 2.54, "outline corner radius"),
    ("hole_inset", 2.54, "mount hole centre from left and bottom edge"),
    ("hole_dx", 86.36, "mount hole pitch along X"),
    ("hole_dz", 30.48, "mount hole pitch along Z"),
    ("hole_d", 2.5, "PCB mount hole drill"),
    ("# frame", None, ""),
    ("rail_w", 8.0, "rail height (Z)"),
    ("rail_t", 4.0, "rail thickness, wall to boss base (Y)"),
    ("tie_w", 6.0, "vertical tie width (X)"),
    ("standoff", 4.0, "boss height, rail face to PCB back. Clears THT leads"),
    ("boss_d", 6.5, "boss diameter"),
    ("insert_d", 3.3, "heat-set insert pocket diameter"),
    ("insert_depth", 3.3, "heat-set insert pocket depth"),
    ("screw_clear_d", 2.8, "M2.5 clearance past the insert, through to the wall"),
    ("# SKADIS hooks. Holes repeat every 40 mm along a row", None, ""),
    ("hook_pitch", 120.0, "hook spacing, keep a multiple of 40"),
    ("hook_land", 10.0, "rail length past each hook centre"),
    ("notch_w", 6.0, "hook notch width on the top rail underside"),
    ("notch_depth", 1.5, "hook notch depth"),
    ("# derived, do not edit", None, ""),
    ("hook_x_l", "=board_w / 2 - hook_pitch / 2", "left hook centre X"),
    ("hook_x_r", "=board_w / 2 + hook_pitch / 2", "right hook centre X"),
    ("rail_x0", "=hook_x_l - hook_land", "rail start X"),
    ("rail_len", "=hook_pitch + 2 * hook_land", "rail length"),
    ("rail_z_bot", "=hole_inset - rail_w / 2", "bottom rail lower face Z"),
    ("rail_z_top", "=hole_inset + hole_dz - rail_w / 2", "top rail lower face Z"),
    ("hole_x_l", "=hole_inset", "left hole column X"),
    ("hole_x_r", "=hole_inset + hole_dx", "right hole column X"),
    ("hole_z_b", "=hole_inset", "bottom hole row Z"),
    ("hole_z_t", "=hole_inset + hole_dz", "top hole row Z"),
    ("boss_face_y", "=-(rail_t + standoff)", "PCB back face Y"),
]

# Hub stand-in, PCB-local mm (x, y from the Rev C CPL), h = height off the
# top face. (name, x0, x1, y0, y1, h). Sizes are approximate.
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
    ("X9_usbC", 9.50, 18.44, 28.60, 35.95, 3.26),
    ("X11_dcjack", 61.61, 70.61, 22.06, 36.06, 11.0),
    ("J1_term", 72.95, 79.95, 28.28, 35.48, 8.5),
    ("STEMMA1", -0.3, 4.2, 11.48, 17.48, 2.9),
    ("STEMMA2", -0.3, 4.2, 20.88, 26.88, 2.9),
    ("SW1_slide", 88.11, 92.4, 6.05, 12.75, 1.5),
    ("SW2_dip", 85.65, 89.35, 24.31, 27.51, 1.5),
]

# Through-hole parts whose leads poke out the back. (x0, x1, y0, y1) reuse the
# body footprint, a conservative stand-in for the pin field.
THT = ["X1_usbA", "X3_usbA", "X5_usbA", "X7_usbA", "X2_xh4", "X4_xh4",
       "X6_xh4", "X8_xh4", "X10_xh4", "X11_dcjack", "J1_term"]
LEAD_LEN = 2.5

EPS = 0.1


def build_sheet(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "parameter")
    sheet.set("B1", "value")
    sheet.set("C1", "note")
    row = 2
    for name, value, note in PARAMS:
        if value is None:
            sheet.set("A%d" % row, name)
        else:
            sheet.set("A%d" % row, name)
            sheet.set("B%d" % row, str(value))
            sheet.setAlias("B%d" % row, name)
            sheet.set("C%d" % row, note)
        row += 1
    sheet.setColumnWidth("A", 130)
    sheet.setColumnWidth("C", 380)
    doc.recompute()
    return sheet


def bind(obj, prop, expr):
    obj.setExpression(prop, expr)


def box(doc, name, length, width, height, x, y, z):
    o = doc.addObject("Part::Box", name)
    bind(o, "Length", length)
    bind(o, "Width", width)
    bind(o, "Height", height)
    bind(o, "Placement.Base.x", x)
    bind(o, "Placement.Base.y", y)
    bind(o, "Placement.Base.z", z)
    return o


def cyl_y(doc, name, radius, height, x, y, z, toward_wall):
    """Cylinder with its axis on Y. toward_wall grows +Y from y, else -Y."""
    o = doc.addObject("Part::Cylinder", name)
    bind(o, "Radius", radius)
    bind(o, "Height", height)
    o.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0),
                                        -90 if toward_wall else 90)
    bind(o, "Placement.Base.x", x)
    bind(o, "Placement.Base.y", y)
    bind(o, "Placement.Base.z", z)
    return o


def build_frame(doc):
    P = "Params."
    adds = [
        box(doc, "RailBottom", P + "rail_len", P + "rail_t", P + "rail_w",
            P + "rail_x0", "-" + P + "rail_t", P + "rail_z_bot"),
        box(doc, "RailTop", P + "rail_len", P + "rail_t", P + "rail_w",
            P + "rail_x0", "-" + P + "rail_t", P + "rail_z_top"),
    ]
    for side in ("l", "r"):
        adds.append(box(doc, "Tie_" + side, P + "tie_w", P + "rail_t",
                        P + "hole_dz",
                        "%shole_x_%s - %stie_w / 2" % (P, side, P),
                        "-" + P + "rail_t", P + "hole_z_b"))

    cuts = []
    for sx in ("l", "r"):
        for sz in ("b", "t"):
            tag = sx + sz
            hx, hz = P + "hole_x_" + sx, P + "hole_z_" + sz
            adds.append(cyl_y(doc, "Boss_" + tag, P + "boss_d / 2",
                              P + "standoff", hx, "-" + P + "rail_t", hz,
                              toward_wall=False))
            cuts.append(cyl_y(doc, "Insert_" + tag, P + "insert_d / 2",
                              P + "insert_depth + %g" % EPS, hx,
                              P + "boss_face_y - %g" % EPS, hz,
                              toward_wall=True))
            cuts.append(cyl_y(doc, "ScrewClear_" + tag, P + "screw_clear_d / 2",
                              "%srail_t + %sstandoff + %g" % (P, P, 2 * EPS),
                              hx, P + "boss_face_y - %g" % EPS, hz,
                              toward_wall=True))
    for side in ("l", "r"):
        cuts.append(box(doc, "HookNotch_" + side, P + "notch_w",
                        P + "rail_t + %g" % (2 * EPS),
                        P + "notch_depth + %g" % EPS,
                        "%shook_x_%s - %snotch_w / 2" % (P, side, P),
                        "-" + P + "rail_t - %g" % EPS,
                        P + "rail_z_top - %g" % EPS))

    body = doc.addObject("Part::MultiFuse", "FrameBody")
    body.Shapes = adds
    body.Refine = True
    holes = doc.addObject("Part::MultiFuse", "FrameCuts")
    holes.Shapes = cuts
    frame = doc.addObject("Part::Cut", "Frame")
    frame.Base = body
    frame.Tool = holes
    frame.Refine = True
    for o in adds + cuts + [body, holes]:
        o.Visibility = False
    return frame


def hub_shapes():
    """Board, top-side parts and back-side leads, PCB back face at local y=0."""
    bw, bh, bt, r = 91.44, 35.56, 1.6, 2.54
    plate = Part.makeBox(bw - 2 * r, bh, bt, App.Vector(r, 0, 0))
    plate = plate.fuse(Part.makeBox(bw, bh - 2 * r, bt, App.Vector(0, r, 0)))
    for cx, cy in ((r, r), (bw - r, r), (r, bh - r), (bw - r, bh - r)):
        plate = plate.fuse(Part.makeCylinder(r, bt, App.Vector(cx, cy, 0)))
    for cx, cy in ((2.54, 2.54), (88.9, 2.54), (2.54, 33.02), (88.9, 33.02)):
        plate = plate.cut(Part.makeCylinder(1.25, bt + 1, App.Vector(cx, cy, -0.5)))
    plate = plate.removeSplitter()

    parts, leads = [], []
    for name, x0, x1, y0, y1, h in PARTS:
        parts.append(Part.makeBox(x1 - x0, y1 - y0, h, App.Vector(x0, y0, bt)))
        if name in THT:
            leads.append(Part.makeBox(x1 - x0, y1 - y0, LEAD_LEN,
                                      App.Vector(x0, y0, -LEAD_LEN)))

    # PCB-local (x, y, up) to world (X, Z, -Y) with the back face on y=0.
    out = []
    for s in (plate, Part.makeCompound(parts), Part.makeCompound(leads)):
        s = s.copy()
        s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
        out.append(s)
    return out


def build_hub(doc):
    objs = []
    for name, shape in zip(("HubPCB", "HubParts", "HubLeads"), hub_shapes()):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        bind(o, "Placement.Base.y", "Params.boss_face_y")
        objs.append(o)
    return objs


# View state. FreeCAD 1.1 has no ViewObject headless, so GuiDocument.xml is
# written into the saved FCStd directly. Layout copied from
# kicad2freecad-enclosures/assemble.py, plus Visibility.

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


def check(frame, hub):
    s = frame.Shape
    pcb, parts, leads = (o.Shape for o in hub)
    ok = True

    def report(label, good, detail):
        nonlocal ok
        ok = ok and good
        print("%-5s %-18s %s" % ("ok" if good else "FAIL", label, detail))

    report("valid", s.isValid(), "")
    report("solids", len(s.Solids) == 1, "%d" % len(s.Solids))
    report("volume", s.Volume > 0, "%.1f mm3" % s.Volume)
    for label, other in (("pcb clash", pcb), ("parts clash", parts),
                         ("leads clash", leads)):
        v = s.common(other).Volume
        report(label, v < 1e-3, "%.4f mm3" % v)
    gap = s.distToShape(pcb)[0]
    report("boss touches pcb", gap < 1e-3, "gap %.4f mm" % gap)
    bb = s.BoundBox
    report("back on wall", abs(bb.YMax) < 1e-6, "YMax %.4f" % bb.YMax)
    print("frame bbox X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f"
          % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    return ok


doc = App.newDocument("skadis_case")
build_sheet(doc)
frame = build_frame(doc)
hub = build_hub(doc)
doc.recompute()

ok = check(frame, hub)

doc.saveAs(DOC_PATH)
hidden = [o.Name for o in doc.Objects
          if hasattr(o, "Visibility") and not o.Visibility
          and o.TypeId != "Spreadsheet::Sheet"]
write_view_state(DOC_PATH, {
    "Frame": ("#1A1A1F", "#D9FF00", 0),
    "HubPCB": ("#0E3A2C", "#00E5C7", 40),
    "HubParts": ("#B0B0B8", "#404040", 40),
    "HubLeads": ("#FF8C00", "#FF8C00", 20),
}, hidden)

frame.Shape.exportStep(STEP_PATH)
printable = frame.Shape.copy()
printable.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
printable.exportStl(STL_PATH)

print("wrote", DOC_PATH)
print("wrote", STEP_PATH)
print("wrote", STL_PATH)
print("CHECKS PASS" if ok else "CHECKS FAIL")
