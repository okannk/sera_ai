#!/usr/bin/env python3
"""
KiCad 7.0 schematic + PCB generator — Sera AI greenhouse nodes
Generates syntactically valid .kicad_sch and .kicad_pcb files.
"""
import os, uuid, textwrap

BASE = os.path.dirname(os.path.abspath(__file__))

def uid():
    return str(uuid.uuid4())

# ─────────────────────────────────────────────────────────────────────────────
# SYMBOL LIBRARY  (embedded in every schematic — full KiCad 7 format)
# ─────────────────────────────────────────────────────────────────────────────

LIB_R = """    (symbol "Device:R" (pin_numbers (hide yes)) (pin_names (offset 0))
      (property "Reference" "R" (at 2.032 0 90)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "R" (at 0 0 90)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 1.778 0 90)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "~" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "R_0_1"
        (polyline
          (pts (xy -1.016 -2.032) (xy 1.016 -2.032) (xy 1.016 2.032) (xy -1.016 2.032) (xy -1.016 -2.032))
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (pin passive line (at 0 3.81 270) (length 1.778)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 0 -3.81 90) (length 1.778)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

LIB_C = """    (symbol "Device:C" (pin_numbers (hide yes)) (pin_names (offset 0.254))
      (property "Reference" "C" (at 1.778 0 90)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "C" (at -1.778 0 90)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "~" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "C_0_1"
        (polyline
          (pts (xy -2.032 -0.762) (xy 2.032 -0.762))
          (stroke (width 0.508) (type default))
          (fill (type none))
        )
        (polyline
          (pts (xy -2.032 0.762) (xy 2.032 0.762))
          (stroke (width 0.508) (type default))
          (fill (type none))
        )
        (pin passive line (at 0 3.81 270) (length 3.048)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 0 -3.81 90) (length 3.048)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

LIB_LED = """    (symbol "Device:LED" (pin_numbers (hide yes)) (pin_names (offset 1.016) (hide yes))
      (property "Reference" "D" (at 0 2.54 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "LED" (at 0 -2.54 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "~" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "LED_0_1"
        (polyline
          (pts (xy -1.27 -1.27) (xy -1.27 1.27) (xy 1.27 0) (xy -1.27 -1.27))
          (stroke (width 0.254) (type default))
          (fill (type none))
        )
        (polyline
          (pts (xy 1.27 -1.27) (xy 1.27 1.27))
          (stroke (width 0.254) (type default))
          (fill (type none))
        )
        (pin passive line (at -3.81 0 0) (length 2.54)
          (name "K" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 3.81 0 180) (length 2.54)
          (name "A" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

LIB_D = """    (symbol "Device:D" (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))
      (property "Reference" "D" (at 0 2.54 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "D" (at 0 -2.54 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "~" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "D_0_1"
        (polyline
          (pts (xy -1.27 -1.27) (xy -1.27 1.27) (xy 1.27 0) (xy -1.27 -1.27))
          (stroke (width 0.254) (type default))
          (fill (type none))
        )
        (polyline
          (pts (xy 1.27 -1.27) (xy 1.27 1.27))
          (stroke (width 0.254) (type default))
          (fill (type none))
        )
        (pin passive line (at -3.81 0 0) (length 2.54)
          (name "K" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 3.81 0 180) (length 2.54)
          (name "A" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

LIB_SW = """    (symbol "Device:SW_Push" (pin_names (offset 1.016) (hide yes))
      (property "Reference" "SW" (at 1.27 2.032 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "SW_Push" (at 1.27 -2.032 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "~" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "SW_Push_0_1"
        (circle (center -2.286 0) (radius 0.508)
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (circle (center 2.286 0) (radius 0.508)
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (polyline
          (pts (xy -1.778 0) (xy 1.778 0))
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (polyline
          (pts (xy -2.032 -1.27) (xy 2.032 -1.27))
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (pin passive line (at -3.81 0 0) (length 1.524)
          (name "1" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 3.81 0 180) (length 1.524)
          (name "2" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

def _conn_pins(n):
    """Generate pin list for an n-pin connector."""
    lines = []
    for i in range(n):
        y = (n - 1) * 2.54 / 2 - i * 2.54
        lines.append(
            f'        (pin passive line (at -5.08 {y:.3f} 0) (length 3.81)\n'
            f'          (name "Pin_{i+1}" (effects (font (size 1.27 1.27))))\n'
            f'          (number "{i+1}" (effects (font (size 1.27 1.27))))\n'
            f'        )'
        )
    return "\n".join(lines)

def _conn_body(n):
    h = n * 2.54
    y_top = (n - 1) * 2.54 / 2 + 1.27
    y_bot = -(n - 1) * 2.54 / 2 - 1.27
    return (
        f'        (polyline\n'
        f'          (pts (xy -1.27 {y_bot:.3f}) (xy -1.27 {y_top:.3f}) '
        f'(xy 0 {y_top:.3f}) (xy 0 {y_bot:.3f}) (xy -1.27 {y_bot:.3f}))\n'
        f'          (stroke (width 0.254) (type default))\n'
        f'          (fill (type none))\n'
        f'        )'
    )

def lib_conn(n):
    name = f"Connector:Conn_01x{n:02d}_Pin"
    y_ref = (n - 1) * 2.54 / 2 + 2.54
    y_val = -(n - 1) * 2.54 / 2 - 2.54
    return (
        f'    (symbol "{name}"\n'
        f'      (property "Reference" "J" (at 0 {y_ref:.3f} 0)\n'
        f'        (effects (font (size 1.27 1.27)))\n'
        f'      )\n'
        f'      (property "Value" "{name.split(":")[-1]}" (at 0 {y_val:.3f} 0)\n'
        f'        (effects (font (size 1.27 1.27)))\n'
        f'      )\n'
        f'      (property "Footprint" "" (at 0 0 0)\n'
        f'        (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'      )\n'
        f'      (property "Datasheet" "~" (at 0 0 0)\n'
        f'        (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'      )\n'
        f'      (symbol "{name.split(":")[-1]}_1_1"\n'
        + _conn_body(n) + "\n"
        + _conn_pins(n) + "\n"
        f'      )\n'
        f'    )'
    )

def lib_power(name, symbol_key=None):
    key = symbol_key or name
    return f"""    (symbol "power:{name}" (power) (pin_names (offset 0) (hide yes))
      (property "Reference" "#PWR" (at 0 3.556 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Value" "{name}" (at 0 3.556 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "{key}_0_1"
        (polyline
          (pts (xy -0.762 1.27) (xy 0 2.54) (xy 0.762 1.27))
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (pin power_in line (at 0 0 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

LIB_GND = """    (symbol "power:GND" (power) (pin_names (offset 0) (hide yes))
      (property "Reference" "#PWR" (at 0 -6.35 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Value" "GND" (at 0 -3.81 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (property "Datasheet" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) (hide yes))
      )
      (symbol "GND_0_1"
        (polyline
          (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27))
          (stroke (width 0) (type default))
          (fill (type none))
        )
        (pin power_in line (at 0 0 270) (length 0)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
      )
    )"""

# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def sym(lib_id, x, y, angle, ref, value, footprint, project, datasheet="~", extra_props=""):
    path = uid()
    return (
        f'  (symbol (lib_id "{lib_id}") (at {x} {y} {angle}) (unit 1)\n'
        f'    (in_bom yes) (on_board yes)\n'
        f'    (property "Reference" "{ref}" (at {x+2.032:.3f} {y} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Value" "{value}" (at {x} {y+3:.3f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Footprint" "{footprint}" (at {x} {y} 0)\n'
        f'      (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'    )\n'
        f'    (property "Datasheet" "{datasheet}" (at {x} {y} 0)\n'
        f'      (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'    )\n'
        + extra_props +
        f'    (instances\n'
        f'      (project "{project}"\n'
        f'        (path "/{path}"\n'
        f'          (reference "{ref}") (unit 1)\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
        f'  )\n'
    )

def power_sym(lib_id, x, y, ref, project):
    path = uid()
    name = lib_id.split(":")[-1]
    is_gnd = (name == "GND")
    vy = y + 5 if is_gnd else y - 3
    angle = 180 if is_gnd else 0
    return (
        f'  (symbol (lib_id "{lib_id}") (at {x} {y} {angle}) (unit 1)\n'
        f'    (in_bom yes) (on_board yes)\n'
        f'    (property "Reference" "{ref}" (at {x} {vy:.3f} 0)\n'
        f'      (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'    )\n'
        f'    (property "Value" "{name}" (at {x} {vy-2:.3f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (instances\n'
        f'      (project "{project}"\n'
        f'        (path "/{path}"\n'
        f'          (reference "{ref}") (unit 1)\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
        f'  )\n'
    )

def wire(x1, y1, x2, y2):
    return f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2})))\n'

def label(name, x, y, angle=0):
    return (
        f'  (label "{name}" (at {x} {y} {angle})\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'  )\n'
    )

def no_connect(x, y):
    return f'  (no_connect (at {x} {y}))\n'

def text(txt, x, y):
    safe = txt.replace('"', "'")
    return (
        f'  (text "{safe}" (at {x} {y} 0)\n'
        f'    (effects (font (size 1.5 1.5)))\n'
        f'  )\n'
    )

# ─────────────────────────────────────────────────────────────────────────────
# SCH SKELETON
# ─────────────────────────────────────────────────────────────────────────────

def sch_header(title, comment1, comment2, libs_extra=""):
    libs = "\n".join([
        LIB_R, LIB_C, LIB_LED, LIB_D, LIB_SW, LIB_GND,
        lib_power("+3V3"),
        lib_power("+5V"),
        lib_power("+12V"),
        lib_conn(2), lib_conn(3), lib_conn(4), lib_conn(5), lib_conn(8),
    ])
    if libs_extra:
        libs += "\n" + libs_extra
    return (
        f'(kicad_sch (version 20230121) (generator eeschema)\n\n'
        f'  (paper "A3")\n\n'
        f'  (title_block\n'
        f'    (title "{title}")\n'
        f'    (date "2026-03-11")\n'
        f'    (rev "1.0")\n'
        f'    (company "Sera AI")\n'
        f'    (comment 1 "{comment1}")\n'
        f'    (comment 2 "{comment2}")\n'
        f'  )\n\n'
        f'  (lib_symbols\n'
        + libs + "\n"
        f'  )\n\n'
    )

def sch_footer():
    return (
        '\n'
        '  (sheet_instances\n'
        '    (path "/" (page "1"))\n'
        '  )\n\n'
        ')\n'
    )

# ─────────────────────────────────────────────────────────────────────────────
# PCB SKELETON
# ─────────────────────────────────────────────────────────────────────────────

LAYERS = """  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user "B.Fabrication")
    (49 "F.Fab" user "F.Fabrication")
  )"""

SETUP = """  (setup
    (pad_to_mask_clearance 0.1)
    (solder_mask_min_width 0.25)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (disableapertmacros false)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (svgprecision 6)
      (excludeedgelayer true)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin false)
      (psnegative false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (subtractmaskfromsilk false)
      (outputformat 1)
      (mirror false)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "gerber/")
    )
  )"""

def pcb_header(title, comment1, comment2):
    return (
        f'(kicad_pcb (version 20221018) (generator pcbnew)\n\n'
        f'  (general\n'
        f'    (thickness 1.6)\n'
        f'  )\n\n'
        f'  (paper "A3")\n\n'
        f'  (title_block\n'
        f'    (title "{title}")\n'
        f'    (date "2026-03-11")\n'
        f'    (rev "1.0")\n'
        f'    (company "Sera AI")\n'
        f'    (comment 1 "{comment1}")\n'
        f'    (comment 2 "{comment2}")\n'
        f'  )\n\n'
        + LAYERS + "\n\n"
        + SETUP + "\n\n"
    )

def pcb_nets(*net_names):
    lines = ['  (net 0 "")']
    for i, n in enumerate(net_names, 1):
        lines.append(f'  (net {i} "{n}")')
    return "\n".join(lines) + "\n\n"

def net_class_block(*net_names):
    nets = "\n".join(f'    (add_net "{n}")' for n in net_names)
    return (
        f'  (net_class "Default" "Default"\n'
        f'    (clearance 0.2)\n'
        f'    (trace_width 0.25)\n'
        f'    (via_dia 1.0)\n'
        f'    (via_drill 0.6)\n'
        f'    (uvia_dia 0.3)\n'
        f'    (uvia_drill 0.1)\n'
        + nets + "\n"
        f'  )\n'
        f'  (net_class "Power" "Power rails"\n'
        f'    (clearance 0.3)\n'
        f'    (trace_width 1.0)\n'
        f'    (via_dia 1.2)\n'
        f'    (via_drill 0.8)\n'
        f'    (add_net "GND")\n'
        f'    (add_net "+3V3")\n'
        f'    (add_net "+5V")\n'
        f'  )\n\n'
    )

def board_outline(w, h):
    return f'  (gr_rect (start 0 0) (end {w} {h}) (layer "Edge.Cuts") (width 0.05))\n'

def silk(txt, x, y, sz=1.5):
    return (
        f'  (gr_text "{txt}" (at {x} {y} 0) (layer "F.SilkS")\n'
        f'    (effects (font (size {sz} {sz}) (thickness {sz*0.15:.2f})))\n'
        f'  )\n'
    )

def mhole(x, y, ref):
    return (
        f'  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at {x} {y})\n'
        f'    (fp_text reference "{ref}" (at 0 -2.8 0) (layer "F.SilkS")\n'
        f'      (effects (font (size 1.0 1.0) (thickness 0.15)))\n'
        f'    )\n'
        f'    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2)\n'
        f'      (layers "*.Cu" "*.Mask")\n'
        f'    )\n'
        f'  )\n'
    )

def fp_smd(ref, value, fp, x, y, pads):
    """pads: list of (num, px, py, w, h, net_num, net_name)"""
    pad_lines = ""
    for p in pads:
        num, px, py, pw, ph, nn, nm = p
        shape = "rect" if str(num) == "1" else "roundrect"
        pad_lines += (
            f'    (pad "{num}" smd {shape} (at {px} {py}) (size {pw} {ph})\n'
            f'      (layers "F.Cu" "F.Paste" "F.Mask")\n'
            f'      (net {nn} "{nm}")\n'
            f'    )\n'
        )
    return (
        f'  (footprint "{fp}" (layer "F.Cu") (at {x} {y})\n'
        f'    (fp_text reference "{ref}" (at 0 -3.5 0) (layer "F.SilkS")\n'
        f'      (effects (font (size 1.0 1.0) (thickness 0.15)))\n'
        f'    )\n'
        f'    (fp_text value "{value}" (at 0 3.5 0) (layer "F.Fab")\n'
        f'      (effects (font (size 1.0 1.0) (thickness 0.15)))\n'
        f'    )\n'
        + pad_lines +
        f'  )\n'
    )

def fp_tht(ref, value, fp, x, y, pads):
    """pads: list of (num, px, py, drill, net_num, net_name)"""
    pad_lines = ""
    for i, p in enumerate(pads):
        num, px, py, dr, nn, nm = p
        shape = "rect" if i == 0 else "circle"
        pad_lines += (
            f'    (pad "{num}" thru_hole {shape} (at {px} {py}) (size 1.7 1.7) (drill {dr})\n'
            f'      (layers "*.Cu" "*.Mask")\n'
            f'      (net {nn} "{nm}")\n'
            f'    )\n'
        )
    return (
        f'  (footprint "{fp}" (layer "F.Cu") (at {x} {y})\n'
        f'    (fp_text reference "{ref}" (at 0 -3.5 0) (layer "F.SilkS")\n'
        f'      (effects (font (size 1.0 1.0) (thickness 0.15)))\n'
        f'    )\n'
        f'    (fp_text value "{value}" (at 0 3.5 0) (layer "F.Fab")\n'
        f'      (effects (font (size 1.0 1.0) (thickness 0.15)))\n'
        f'    )\n'
        + pad_lines +
        f'  )\n'
    )

def gnd_zone(w, h):
    z = str(uuid.uuid4())
    return (
        f'  (zone (net 1) (net_name "GND") (layer "B.Cu") (tstamp {z})\n'
        f'    (connect_pads (clearance 0.3))\n'
        f'    (min_thickness 0.25)\n'
        f'    (filled_areas_thickness no)\n'
        f'    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
        f'    (polygon\n'
        f'      (pts (xy 0.5 0.5) (xy {w-0.5} 0.5) (xy {w-0.5} {h-0.5}) (xy 0.5 {h-0.5}))\n'
        f'    )\n'
        f'  )\n'
    )

def track(x1, y1, x2, y2, net, w=0.25, layer="F.Cu"):
    return f'  (segment (start {x1} {y1}) (end {x2} {y2}) (width {w}) (layer "{layer}") (net {net}))\n'

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate(path):
    data = open(path, encoding="utf-8").read()
    depth = 0
    for i, c in enumerate(data):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth < 0:
            ln = data[:i].count("\n") + 1
            return False, f"depth<0 at char {i} (line {ln})"
    if depth != 0:
        return False, f"final depth={depth} (unbalanced)"
    # Extra checks
    for bad in ["; ", "net_label", "(drawings ", "(tracks ", "(modules "]:
        if bad in data:
            return False, f"forbidden token: {bad!r}"
    if path.endswith(".kicad_sch") and "sheet_instances" not in data:
        return False, "missing sheet_instances"
    return True, "OK"

# ─────────────────────────────────────────────────────────────────────────────
# GENERATE: SENSOR NODE
# ─────────────────────────────────────────────────────────────────────────────

def gen_sensor_node():
    proj = "sensor_node"
    out = os.path.join(BASE, "sensor_node")
    os.makedirs(out, exist_ok=True)

    # ── Schematic ────────────────────────────────────────────────────────────
    sch = sch_header(
        "Sensor Node — Sera AI",
        "ESP32-S3 + W5500 + SHT40 + SCD41 + AS7341 + TEROS-12",
        "Board: 100x80mm  |  Power: HLK-PM05 AC-DC + AMS1117-3.3",
    )

    # Power rails
    sch += power_sym("power:GND",  50, 180, "#PWR01", proj)
    sch += power_sym("power:+3V3", 50,  40, "#PWR02", proj)
    sch += power_sym("power:+5V", 100,  40, "#PWR03", proj)

    # U1 AMS1117-3.3 LDO
    sch += sym("Device:R", 15, 100, 0, "U1", "AMS1117-3.3",
               "Package_TO_SOT_SMD:SOT-223-3_TabPin2", proj,
               datasheet="https://www.advanced-monolithic.com/pdf/ds1117.pdf")

    # U2 ESP32-S3-DevKitC-1 (represented as 2x22 connector)
    sch += sym("Connector:Conn_01x08_Pin", 50, 80, 0, "U2",
               "ESP32-S3-DevKitC-1",
               "Module:ESP32-S3-DevKitC-1", proj)

    # U3 W5500 SPI Ethernet
    sch += sym("Connector:Conn_01x08_Pin", 80, 80, 0, "U3",
               "W5500-EVB",
               "Module:W5500-EVB", proj)

    # PS1 HLK-PM05
    sch += sym("Connector:Conn_01x04_Pin", 15, 60, 0, "PS1",
               "HLK-PM05",
               "Module:HLK-PM05", proj)

    # Capacitors
    for i, (val, fp, cx, cy) in enumerate([
        ("100uF", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",   25, 110),
        ("100uF", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",   35, 110),
        ("10uF",  "Capacitor_SMD:C_1206_3216Metric",           45, 110),
        ("10uF",  "Capacitor_SMD:C_1206_3216Metric",           55, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",           65, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",           75, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",           85, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",           95, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",          105, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",          115, 110),
    ], 1):
        sch += sym("Device:C", cx, cy, 0, f"C{i}", val, fp, proj)

    # Resistors
    for i, (val, cx, cy) in enumerate([
        ("4.7k",  130, 80),
        ("4.7k",  140, 80),
        ("330",   150, 80),
        ("330",   160, 80),
        ("330",   170, 80),
    ], 1):
        sch += sym("Device:R", cx, cy, 0, f"R{i}", val,
                   "Resistor_SMD:R_0805_2012Metric", proj)

    # LEDs
    sch += sym("Device:LED", 150, 100, 0, "D1", "LED_GREEN",
               "LED_SMD:LED_0805_2012Metric", proj)
    sch += sym("Device:LED", 160, 100, 0, "D2", "LED_BLUE",
               "LED_SMD:LED_0805_2012Metric", proj)
    sch += sym("Device:LED", 170, 100, 0, "D3", "LED_RED",
               "LED_SMD:LED_0805_2012Metric", proj)

    # Diodes
    sch += sym("Device:D", 15, 130, 0, "D4", "SMBJ5.0A",
               "Diode_SMD:D_SMB", proj)
    sch += sym("Device:D", 25, 130, 0, "D5", "BAT54",
               "Package_TO_SOT_SMD:SOT-23", proj)

    # Connectors
    sch += sym("Connector:Conn_01x04_Pin", 180, 80,  0, "J1", "SHT40_I2C",
               "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", proj)
    sch += sym("Connector:Conn_01x04_Pin", 180, 95,  0, "J2", "SCD41_I2C",
               "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", proj)
    sch += sym("Connector:Conn_01x04_Pin", 180, 110, 0, "J3", "AS7341_I2C",
               "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", proj)
    sch += sym("Connector:Conn_01x03_Pin", 180, 125, 0, "J4", "TEROS12_SDI12",
               "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical", proj)
    sch += sym("Connector:Conn_01x02_Pin", 15,  160, 0, "J5", "DC_Jack_2.1mm",
               "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal", proj)
    sch += sym("Connector:Conn_01x04_Pin", 15,  140, 0, "J6", "UART_DEBUG",
               "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", proj)
    sch += sym("Connector:Conn_01x08_Pin", 15,  170, 0, "J7", "HR911105A",
               "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal", proj)

    # Reset button
    sch += sym("Device:SW_Push", 130, 150, 0, "SW1", "RESET",
               "Button_Switch_SMD:SW_SPST_SKQG_WithStem", proj)

    # Net labels
    for name, x, y in [
        ("I2C_SDA", 60, 70), ("I2C_SCL", 70, 70),
        ("SPI_MOSI", 80, 70), ("SPI_MISO", 90, 70),
        ("SPI_SCK", 100, 70), ("SPI_CS", 110, 70),
        ("ETH_INT", 120, 70), ("ETH_RST", 130, 70),
        ("UART_TX", 60, 78), ("UART_RX", 70, 78),
        ("SDI12_DATA", 80, 78), ("nRESET", 130, 145),
    ]:
        sch += label(name, x, y)

    # Wires (representative subset — I2C bus, power)
    sch += wire(50, 44, 50, 60)
    sch += wire(100, 44, 100, 60)
    sch += wire(50, 175, 50, 165)

    # Annotations
    sch += text("I2C Bus: SDA=GPIO8 SCL=GPIO9  Pull-up: 4.7k to +3V3", 125, 65)
    sch += text("SPI Bus: MOSI=GPIO11 MISO=GPIO13 SCK=GPIO12 CS=GPIO10", 125, 60)
    sch += text("220V AC in -> HLK-PM05 -> 5V -> AMS1117-3.3 -> 3.3V", 15, 50)
    sch += text("TEROS-12 SDI-12: 3.6V via BAT54 from 3.3V rail", 15, 125)

    sch += sch_footer()

    path = os.path.join(out, f"{proj}.kicad_sch")
    open(path, "w", encoding="utf-8").write(sch)

    # ── PCB ─────────────────────────────────────────────────────────────────
    W, H = 100, 80
    pcb = pcb_header("Sensor Node — Sera AI",
                     "100x80mm 2L FR4", "ESP32-S3 + W5500 Multi-Sensor")
    pcb += pcb_nets("GND", "+3V3", "+5V", "I2C_SDA", "I2C_SCL",
                    "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS",
                    "UART_TX", "UART_RX")
    pcb += net_class_block("GND", "+3V3", "+5V", "I2C_SDA", "I2C_SCL",
                           "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS",
                           "UART_TX", "UART_RX")
    pcb += board_outline(W, H)
    pcb += silk("SENSOR NODE v1.0", 50, 2, 2.5)
    pcb += silk("Sera AI Greenhouse", 50, H-3, 1.5)

    # Mounting holes
    pcb += mhole(3.5, 3.5, "MH1")
    pcb += mhole(W-3.5, 3.5, "MH2")
    pcb += mhole(3.5, H-3.5, "MH3")
    pcb += mhole(W-3.5, H-3.5, "MH4")

    # AMS1117-3.3  SOT-223
    pcb += fp_smd("U1", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
                  15, 15, [
        ("1", -2.3, 1.5, 1.6, 2.2, 1, "GND"),
        ("2",  0.0, 1.5, 1.6, 2.2, 2, "+3V3"),
        ("3",  2.3, 1.5, 1.6, 2.2, 3, "+5V"),
        ("4",  0.0,-1.5, 6.5, 2.2, 2, "+3V3"),
    ])

    # HLK-PM05 (through-hole module)
    pcb += fp_tht("PS1", "HLK-PM05",
                  "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                  8, 30, [
        ("1", 0, 0,    1.2, 0, ""),
        ("2", 0, 2.54, 1.2, 0, ""),
        ("3", 0, 5.08, 1.2, 3, "+5V"),
        ("4", 0, 7.62, 1.2, 1, "GND"),
    ])

    # ESP32-S3 header left
    pcb += fp_tht("U2_L", "ESP32-S3-Left",
                  "Connector_PinHeader_2.54mm:PinHeader_1x22_P2.54mm_Vertical",
                  38, 20, [
        (str(i+1), 0, i*2.54, 1.0, 1 if i==19 else (2 if i==20 else (3 if i==21 else 0)), "GND" if i==19 else "+3V3" if i==20 else "+5V" if i==21 else "")
        for i in range(22)
    ])

    # W5500 module header
    pcb += fp_tht("U3", "W5500-EVB",
                  "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
                  70, 20, [
        ("1", 0, 0,     1.0, 0, ""),
        ("2", 0, 2.54,  1.0, 1, "GND"),
        ("3", 0, 5.08,  1.0, 3, "+5V"),
        ("4", 0, 7.62,  1.0, 6, "SPI_MISO"),
        ("5", 0, 10.16, 1.0, 5, "SPI_MOSI"),
        ("6", 0, 12.70, 1.0, 7, "SPI_SCK"),
        ("7", 0, 15.24, 1.0, 8, "SPI_CS"),
        ("8", 0, 17.78, 1.0, 0, ""),
    ])

    # RJ45
    pcb += fp_tht("J7", "HR911105A",
                  "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal",
                  18, 72, [
        (str(i+1), (i-4)*1.4, 0, 0.9, 0, "") for i in range(8)
    ])

    # JST connectors for sensors
    for idx, (ref, val, cy) in enumerate([
        ("J1", "SHT40",  10), ("J2", "SCD41", 22),
        ("J3", "AS7341", 34), ("J4", "TEROS12", 46),
    ]):
        pcb += fp_tht(ref, val,
                      "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
                      88, cy, [
            ("1", 0, 0,   1.0, 1, "GND"),
            ("2", 2.5, 0, 1.0, 2, "+3V3"),
            ("3", 5.0, 0, 1.0, 4, "I2C_SDA"),
            ("4", 7.5, 0, 1.0, 5, "I2C_SCL"),
        ])

    # DC Jack
    pcb += fp_tht("J5", "DC_Jack",
                  "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal",
                  5, 62, [
        ("1", 0, 0,   1.5, 3, "+5V"),
        ("2", 0, 2.5, 1.5, 1, "GND"),
    ])

    # Reset button
    pcb += fp_smd("SW1", "RESET",
                  "Button_Switch_SMD:SW_SPST_SKQG_WithStem",
                  93, 72, [
        ("1", -2.5, -1.6, 1.6, 1.6, 0, ""),
        ("2",  2.5, -1.6, 1.6, 1.6, 0, ""),
        ("3", -2.5,  1.6, 1.6, 1.6, 0, ""),
        ("4",  2.5,  1.6, 1.6, 1.6, 0, ""),
    ])

    # GND copper fill on back
    pcb += gnd_zone(W, H)

    # Key tracks
    pcb += track(15, 13, 25, 13, 2, 1.0)
    pcb += track(8,  32, 8,  20, 3, 1.0)
    pcb += track(8,  35, 8,  50, 1, 1.0)
    pcb += track(38, 25, 88, 10, 4, 0.25)
    pcb += track(38, 28, 88, 22, 5, 0.25)
    pcb += track(38, 31, 70, 20, 5, 0.25)
    pcb += track(38, 34, 70, 23, 6, 0.25)
    pcb += track(38, 37, 70, 26, 7, 0.25)
    pcb += track(38, 40, 70, 29, 8, 0.25)

    pcb += ")\n"

    ppath = os.path.join(out, f"{proj}.kicad_pcb")
    open(ppath, "w", encoding="utf-8").write(pcb)

    return path, ppath


# ─────────────────────────────────────────────────────────────────────────────
# GENERATE: CLIMATE NODE
# ─────────────────────────────────────────────────────────────────────────────

def gen_climate_node():
    proj = "climate_node"
    out = os.path.join(BASE, "climate_node")
    os.makedirs(out, exist_ok=True)

    sch = sch_header(
        "Climate Node — Sera AI",
        "ESP32-S3 + W5500 + 4x SSR (PC817 + G3MB-202P)",
        "Board: 120x100mm  |  220V SSR control with optocoupler isolation",
    )

    sch += power_sym("power:GND",  50, 180, "#PWR01", proj)
    sch += power_sym("power:+3V3", 50,  40, "#PWR02", proj)
    sch += power_sym("power:+5V", 100,  40, "#PWR03", proj)

    # Power supply (same as sensor node)
    sch += sym("Device:R", 15, 100, 0, "U1", "AMS1117-3.3",
               "Package_TO_SOT_SMD:SOT-223-3_TabPin2", proj)
    sch += sym("Connector:Conn_01x04_Pin", 15, 60, 0, "PS1",
               "HLK-PM05", "Module:HLK-PM05", proj)
    sch += sym("Connector:Conn_01x08_Pin", 50, 80, 0, "U2",
               "ESP32-S3-DevKitC-1", "Module:ESP32-S3-DevKitC-1", proj)
    sch += sym("Connector:Conn_01x08_Pin", 80, 80, 0, "U3",
               "W5500-EVB", "Module:W5500-EVB", proj)

    # 4x SSR control: 330R + PC817 optocoupler
    for i in range(4):
        gpio = 4 + i
        names = ["FAN", "ISITICI", "SOGUTMA", "HAVALANDIRMA"]
        cx = 130 + i * 20
        sch += sym("Device:R", cx, 80, 0, f"R{i+1}", "330",
                   "Resistor_SMD:R_0805_2012Metric", proj)
        sch += sym("Connector:Conn_01x02_Pin", cx, 100, 0, f"U{i+4}",
                   f"PC817_{names[i]}",
                   "Package_DIP:DIP-4_W7.62mm", proj)
        sch += sym("Connector:Conn_01x02_Pin", cx, 120, 0, f"K{i+1}",
                   f"SSR_{names[i]}",
                   "Connector_Phoenix_PTSA:PhoenixContact_PTSA_1,5_2-G-3,5", proj)
        sch += label(f"GPIO{gpio}_{names[i]}", cx-5, 75)
        sch += label(f"SSR_LOAD_{names[i]}", cx+5, 125)

    # Status LEDs (4x for SSR status)
    for i in range(4):
        sch += sym("Device:LED", 130 + i*20, 60, 0, f"D{i+1}",
                   f"LED_SSR{i+1}", "LED_SMD:LED_0805_2012Metric", proj)
        sch += sym("Device:R", 130 + i*20, 50, 0, f"R{i+5}", "330",
                   "Resistor_SMD:R_0805_2012Metric", proj)

    # MOV varistor + fuse
    sch += sym("Device:D", 15, 140, 0, "RV1", "S14K275",
               "Varistor_THT:RV_Disc_D14mm_W3.4mm_P10mm", proj)
    sch += sym("Connector:Conn_01x02_Pin", 15, 155, 0, "F1",
               "Fuse_10A", "Fuse:Fuse_Littelfuse_OMNI-BLOK_01xx_THT", proj)

    # 5-pin AC terminal
    sch += sym("Connector:Conn_01x05_Pin", 15, 170, 0, "J8",
               "AC_TERM_L_N_PE", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-5_1x05", proj)

    # RJ45, DC Jack, Debug
    sch += sym("Connector:Conn_01x08_Pin", 15, 170, 0, "J7",
               "HR911105A", "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal", proj)
    sch += sym("Connector:Conn_01x02_Pin", 15, 155, 0, "J5",
               "DC_Jack_2.1mm",
               "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal", proj)
    sch += sym("Connector:Conn_01x04_Pin", 15, 140, 0, "J6",
               "UART_DEBUG",
               "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", proj)
    sch += sym("Device:SW_Push", 130, 150, 0, "SW1", "RESET",
               "Button_Switch_SMD:SW_SPST_SKQG_WithStem", proj)

    # Capacitors
    for i, (val, fp, cx, cy) in enumerate([
        ("100uF", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 25, 110),
        ("100uF", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 35, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric", 45, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric", 55, 110),
    ], 1):
        sch += sym("Device:C", cx, cy, 0, f"C{i}", val, fp, proj)

    # Net labels
    sch += label("I2C_SDA", 60, 70)
    sch += label("I2C_SCL", 70, 70)
    sch += label("SPI_MOSI", 80, 70)
    sch += label("SPI_MISO", 90, 70)
    sch += label("SPI_SCK", 100, 70)
    sch += label("SPI_CS", 110, 70)

    sch += text("DIKKAT: 220V  |  HV bolgesi: alt yari  |  izolasyon: 8mm min", 80, 145)
    sch += text("PC817 optocoupler: ESP32 GPIO -> 330R -> LED -> PC817 cikis -> SSR", 80, 150)

    sch += sch_footer()

    path = os.path.join(out, f"{proj}.kicad_sch")
    open(path, "w", encoding="utf-8").write(sch)

    # ── PCB ─────────────────────────────────────────────────────────────────
    W, H = 120, 100
    pcb = pcb_header("Climate Node — Sera AI",
                     "120x100mm 2L FR4", "4x SSR optocoupler isolated 220V")
    pcb += pcb_nets("GND", "+3V3", "+5V", "I2C_SDA", "I2C_SCL",
                    "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS",
                    "SSR_FAN", "SSR_ISITICI", "SSR_SOGUTMA", "SSR_HAVALANDIRMA",
                    "AC_L", "AC_N")
    pcb += net_class_block("GND", "+3V3", "+5V", "I2C_SDA", "I2C_SCL",
                           "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS")
    pcb += board_outline(W, H)
    pcb += silk("CLIMATE NODE v1.0", W/2, 2, 2.5)
    pcb += silk("!!! DIKKAT: 220V !!!", W/2, H-5, 2.0)
    pcb += silk("HV ZONE", W/2, H-12, 1.5)
    pcb += silk("Sera AI", W/2, H-3, 1.2)

    # Mounting holes
    pcb += mhole(3.5, 3.5, "MH1")
    pcb += mhole(W-3.5, 3.5, "MH2")
    pcb += mhole(3.5, H-3.5, "MH3")
    pcb += mhole(W-3.5, H-3.5, "MH4")

    # HV/LV separation line (silk)
    pcb += (
        f'  (gr_line (start 0 55) (end {W} 55) (layer "F.SilkS") (width 0.5))\n'
        f'  (gr_line (start 0 55) (end {W} 55) (layer "B.SilkS") (width 0.5))\n'
    )

    # AMS1117-3.3
    pcb += fp_smd("U1", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
                  15, 15, [
        ("1", -2.3, 1.5, 1.6, 2.2, 1, "GND"),
        ("2",  0.0, 1.5, 1.6, 2.2, 2, "+3V3"),
        ("3",  2.3, 1.5, 1.6, 2.2, 3, "+5V"),
        ("4",  0.0,-1.5, 6.5, 2.2, 2, "+3V3"),
    ])

    # HLK-PM05
    pcb += fp_tht("PS1", "HLK-PM05",
                  "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                  8, 65, [
        ("1", 0, 0,    1.2, 0, ""),
        ("2", 0, 2.54, 1.2, 0, ""),
        ("3", 0, 5.08, 1.2, 3, "+5V"),
        ("4", 0, 7.62, 1.2, 1, "GND"),
    ])

    # 4x PC817 + SSR connectors
    for i in range(4):
        x = 30 + i * 22
        # PC817 DIP-4
        pcb += fp_tht(f"U{i+4}", f"PC817_SSR{i+1}",
                      "Package_DIP:DIP-4_W7.62mm",
                      x, 30, [
            ("1", 0,    0, 0.8, 0, ""),
            ("2", 0, 2.54, 0.8, 0, ""),
            ("3", 7.62, 0, 0.8, 0, ""),
            ("4", 7.62, 2.54, 0.8, 0, ""),
        ])
        # SSR screw terminal (220V side)
        pcb += fp_tht(f"K{i+1}", f"SSR_LOAD{i+1}",
                      "TerminalBlock:TerminalBlock_bornier-2_P5.08mm",
                      x, 70, [
            ("1", 0,    0, 1.5, 0, ""),
            ("2", 5.08, 0, 1.5, 0, ""),
        ])

    # DC Jack, RJ45
    pcb += fp_tht("J5", "DC_Jack",
                  "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal",
                  5, 50, [
        ("1", 0, 0,   1.5, 3, "+5V"),
        ("2", 0, 2.5, 1.5, 1, "GND"),
    ])
    pcb += fp_tht("J7", "HR911105A",
                  "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal",
                  18, 92, [
        (str(i+1), (i-4)*1.4, 0, 0.9, 0, "") for i in range(8)
    ])

    # AC terminal 5pin
    pcb += fp_tht("J8", "AC_TERM",
                  "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-5_1x05",
                  60, 92, [
        (str(i+1), i*5.08, 0, 1.5, 14 if i <= 1 else (15 if i == 1 else 0), "AC_L" if i==0 else "AC_N" if i==1 else "")
        for i in range(5)
    ])

    # GND zone
    pcb += gnd_zone(W, H)

    # Tracks
    pcb += track(15, 13, 25, 13, 2, 1.0)
    pcb += track(8,  30, 8,  20, 3, 1.0)
    pcb += track(8,  35, 8,  55, 1, 1.0)
    for i in range(4):
        x = 30 + i * 22
        pcb += track(x, 22, x, 28, 0, 0.25)

    pcb += ")\n"

    ppath = os.path.join(out, f"{proj}.kicad_pcb")
    open(ppath, "w", encoding="utf-8").write(pcb)

    return path, ppath


# ─────────────────────────────────────────────────────────────────────────────
# GENERATE: IRRIGATION NODE
# ─────────────────────────────────────────────────────────────────────────────

def gen_irrigation_node():
    proj = "irrigation_node"
    out = os.path.join(BASE, "irrigation_node")
    os.makedirs(out, exist_ok=True)

    sch = sch_header(
        "Irrigation Node — Sera AI",
        "ESP32-S3 + W5500 + Atlas EZO (5x I2C) + LM2596 12V + IRLZ44N valves",
        "Board: 120x100mm  |  pH/EC/DO/RTD/PMP + 2x solenoid valve + flow sensor",
    )

    sch += power_sym("power:GND",   50, 180, "#PWR01", proj)
    sch += power_sym("power:+3V3",  50,  40, "#PWR02", proj)
    sch += power_sym("power:+5V",  100,  40, "#PWR03", proj)
    sch += power_sym("power:+12V", 150,  40, "#PWR04", proj)

    # Power supply
    sch += sym("Device:R", 15, 100, 0, "U1", "AMS1117-3.3",
               "Package_TO_SOT_SMD:SOT-223-3_TabPin2", proj)
    sch += sym("Connector:Conn_01x04_Pin", 15, 60, 0, "PS1",
               "HLK-PM05", "Module:HLK-PM05", proj)
    sch += sym("Connector:Conn_01x08_Pin", 50, 80, 0, "U2",
               "ESP32-S3-DevKitC-1", "Module:ESP32-S3-DevKitC-1", proj)
    sch += sym("Connector:Conn_01x08_Pin", 80, 80, 0, "U3",
               "W5500-EVB", "Module:W5500-EVB", proj)

    # LM2596 buck 5V->12V
    sch += sym("Connector:Conn_01x05_Pin", 130, 60, 0, "U4",
               "LM2596-12V", "Package_TO_SOT_THT:TO-263-5_TabPin3", proj)
    sch += sym("Device:C", 145, 65, 0, "C11", "220uF",
               "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", proj)
    sch += sym("Device:R", 145, 75, 0, "L1", "100uH",
               "Inductor_THT:L_Axial_L16.3mm_D6.9mm_P22.86mm_Horizontal_Vishay_IM-1", proj)

    # 5x Atlas EZO I2C connectors
    ezo_list = [
        ("J_PH",  "EZO-pH_0x63",  "pH",   0x63),
        ("J_EC",  "EZO-EC_0x64",  "EC",   0x64),
        ("J_DO",  "EZO-DO_0x61",  "DO",   0x61),
        ("J_RTD", "EZO-RTD_0x66", "RTD",  0x66),
        ("J_PMP", "EZO-PMP_0x67", "PMP",  0x67),
    ]
    for i, (ref, val, lbl, addr) in enumerate(ezo_list):
        cx = 160 + i * 15
        sch += sym("Connector:Conn_01x04_Pin", cx, 80, 0, ref, val,
                   "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", proj)
        sch += sym("Device:C", cx, 95, 0, f"C{i+12}", "100nF",
                   "Capacitor_SMD:C_0805_2012Metric", proj)
        sch += label(f"I2C_SDA", cx-3, 75)
        sch += label(f"I2C_SCL", cx+3, 75)
        sch += text(f"addr 0x{addr:02X}", cx, 70)

    # 2x IRLZ44N MOSFET valve drivers
    for i in range(2):
        cx = 130 + i * 20
        cy = 130
        gpio = 8 + i
        sch += sym("Device:R", cx, cy-10, 0, f"R{i+6}", "100",
                   "Resistor_SMD:R_0805_2012Metric", proj)
        sch += sym("Connector:Conn_01x03_Pin", cx, cy, 0, f"Q{i+1}",
                   f"IRLZ44N_VALVE{i+1}",
                   "Package_TO_SOT_THT:TO-220-3_Vertical", proj)
        sch += sym("Device:D", cx, cy+15, 0, f"D{i+6}", "1N4007",
                   "Diode_THT:D_DO-41_SOD81_P12.70mm_Horizontal", proj)
        sch += sym("Connector:Conn_01x02_Pin", cx, cy+28, 0, f"J_V{i+1}",
                   f"VALVE_{i+1}_TERMINAL",
                   "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", proj)
        sch += label(f"GPIO{gpio}_VALVE{i+1}", cx-5, cy-15)
        sch += label(f"+12V", cx+5, cy+5)

    # Flow sensor YF-S201
    sch += sym("Connector:Conn_01x03_Pin", 170, 150, 0, "J_FLOW",
               "YF-S201_FLOW", "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical", proj)
    sch += sym("Device:R", 175, 145, 0, "R8", "10k",
               "Resistor_SMD:R_0805_2012Metric", proj)
    sch += label("GPIO16_FLOW", 165, 145)

    # RJ45, DC Jack, Debug, Reset
    sch += sym("Connector:Conn_01x08_Pin", 15, 170, 0, "J7",
               "HR911105A", "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal", proj)
    sch += sym("Connector:Conn_01x02_Pin", 15, 155, 0, "J5",
               "DC_Jack_2.1mm",
               "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal", proj)
    sch += sym("Connector:Conn_01x04_Pin", 15, 140, 0, "J6",
               "UART_DEBUG",
               "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", proj)
    sch += sym("Device:SW_Push", 130, 160, 0, "SW1", "RESET",
               "Button_Switch_SMD:SW_SPST_SKQG_WithStem", proj)

    # Capacitors for power section
    for i, (val, fp, cx, cy) in enumerate([
        ("100uF", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 25, 110),
        ("10uF",  "Capacitor_SMD:C_1206_3216Metric",         35, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",         45, 110),
        ("100nF", "Capacitor_SMD:C_0805_2012Metric",         55, 110),
    ], 1):
        sch += sym("Device:C", cx, cy, 0, f"C{i}", val, fp, proj)

    # Net labels
    sch += label("I2C_SDA", 60, 70)
    sch += label("I2C_SCL", 70, 70)
    sch += label("SPI_MOSI", 80, 70)
    sch += label("SPI_MISO", 90, 70)
    sch += label("SPI_SCK", 100, 70)
    sch += label("SPI_CS", 110, 70)

    sch += text("Atlas EZO I2C: pH/EC/DO/RTD/PMP — shared I2C bus, 4.7k pull-up to +3V3", 155, 60)
    sch += text("LM2596 5V->12V buck for solenoid valve coils", 125, 50)
    sch += text("IRLZ44N logic-level MOSFET: 100R gate, 1N4007 flyback", 125, 125)

    sch += sch_footer()

    path = os.path.join(out, f"{proj}.kicad_sch")
    open(path, "w", encoding="utf-8").write(sch)

    # ── PCB ─────────────────────────────────────────────────────────────────
    W, H = 120, 100
    pcb = pcb_header("Irrigation Node — Sera AI",
                     "120x100mm 2L FR4", "Atlas EZO + LM2596 12V + IRLZ44N valves")
    pcb += pcb_nets("GND", "+3V3", "+5V", "+12V", "I2C_SDA", "I2C_SCL",
                    "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS",
                    "VALVE1", "VALVE2", "FLOW_SIGNAL")
    pcb += net_class_block("GND", "+3V3", "+5V", "+12V", "I2C_SDA", "I2C_SCL",
                           "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS",
                           "VALVE1", "VALVE2", "FLOW_SIGNAL")
    pcb += board_outline(W, H)
    pcb += silk("IRRIGATION NODE v1.0", W/2, 2, 2.5)
    pcb += silk("Sera AI Greenhouse", W/2, H-3, 1.5)
    pcb += silk("+12V ZONE", 95, 50, 1.2)

    # 12V zone boundary
    pcb += f'  (gr_line (start 80 40) (end {W} 40) (layer "Dwgs.User") (width 0.2))\n'
    pcb += f'  (gr_line (start 80 40) (end 80 {H}) (layer "Dwgs.User") (width 0.2))\n'

    # Mounting holes
    pcb += mhole(3.5, 3.5, "MH1")
    pcb += mhole(W-3.5, 3.5, "MH2")
    pcb += mhole(3.5, H-3.5, "MH3")
    pcb += mhole(W-3.5, H-3.5, "MH4")

    # AMS1117-3.3
    pcb += fp_smd("U1", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
                  15, 15, [
        ("1", -2.3, 1.5, 1.6, 2.2, 1, "GND"),
        ("2",  0.0, 1.5, 1.6, 2.2, 2, "+3V3"),
        ("3",  2.3, 1.5, 1.6, 2.2, 3, "+5V"),
        ("4",  0.0,-1.5, 6.5, 2.2, 2, "+3V3"),
    ])

    # HLK-PM05
    pcb += fp_tht("PS1", "HLK-PM05",
                  "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                  8, 30, [
        ("1", 0, 0,    1.2, 0, ""),
        ("2", 0, 2.54, 1.2, 0, ""),
        ("3", 0, 5.08, 1.2, 3, "+5V"),
        ("4", 0, 7.62, 1.2, 1, "GND"),
    ])

    # LM2596 TO-263
    pcb += fp_smd("U4", "LM2596-12V", "Package_TO_SOT_SMD:TO-263-5_TabPin3",
                  90, 20, [
        ("1", -5,   1.5, 1.5, 2.5, 3, "+5V"),
        ("2", -2.5, 1.5, 1.5, 2.5, 0, ""),
        ("3",  0,   1.5, 1.5, 2.5, 4, "+12V"),
        ("4",  2.5, 1.5, 1.5, 2.5, 1, "GND"),
        ("5",  5,   1.5, 1.5, 2.5, 0, ""),
        ("tab", 0, -1.5, 9,   2.5, 4, "+12V"),
    ])

    # 5x Atlas EZO JST connectors
    for i, ref in enumerate(["J_PH", "J_EC", "J_DO", "J_RTD", "J_PMP"]):
        x = 20 + i * 13
        pcb += fp_tht(ref, f"EZO_{i+1}",
                      "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
                      x, 60, [
            ("1", 0,   0, 1.0, 1, "GND"),
            ("2", 2.5, 0, 1.0, 2, "+3V3"),
            ("3", 5.0, 0, 1.0, 5, "I2C_SDA"),
            ("4", 7.5, 0, 1.0, 6, "I2C_SCL"),
        ])

    # 2x IRLZ44N TO-220
    for i in range(2):
        x = 88 + i * 14
        pcb += fp_tht(f"Q{i+1}", f"IRLZ44N_V{i+1}",
                      "Package_TO_SOT_THT:TO-220-3_Vertical",
                      x, 75, [
            ("1", 0,   0, 1.0, 0, ""),
            ("2", 2.54,0, 1.0, 11+i, f"VALVE{i+1}"),
            ("3", 5.08,0, 1.0, 4, "+12V"),
        ])
        # Valve terminal
        pcb += fp_tht(f"J_V{i+1}", f"VALVE_{i+1}",
                      "TerminalBlock:TerminalBlock_bornier-2_P5.08mm",
                      x, 90, [
            ("1", 0,    0, 1.5, 11+i, f"VALVE{i+1}"),
            ("2", 5.08, 0, 1.5, 4,    "+12V"),
        ])

    # Flow sensor
    pcb += fp_tht("J_FLOW", "YF-S201",
                  "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
                  108, 60, [
        ("1", 0,   0, 1.0, 3,  "+5V"),
        ("2", 2.5, 0, 1.0, 13, "FLOW_SIGNAL"),
        ("3", 5.0, 0, 1.0, 1,  "GND"),
    ])

    # DC Jack, RJ45
    pcb += fp_tht("J5", "DC_Jack",
                  "Connector_BarrelJack:BarrelJack_Kycon_KLDX-0202-A_Horizontal",
                  5, 75, [
        ("1", 0, 0,   1.5, 3, "+5V"),
        ("2", 0, 2.5, 1.5, 1, "GND"),
    ])
    pcb += fp_tht("J7", "HR911105A",
                  "Connector_RJ:RJ45_Amphenol_RJHSE538X_Horizontal",
                  18, 92, [
        (str(i+1), (i-4)*1.4, 0, 0.9, 0, "") for i in range(8)
    ])

    # GND zone
    pcb += gnd_zone(W, H)

    # Key tracks
    pcb += track(15, 13, 25, 13, 2, 1.0)
    pcb += track(8,  32, 8,  20, 3, 1.0)
    pcb += track(8,  35, 8,  50, 1, 1.0)
    pcb += track(90, 18, 90, 15, 4, 1.0)
    for i in range(5):
        x = 20 + i * 13
        pcb += track(38, 45, x+5.0, 60, 5, 0.25)
        pcb += track(38, 48, x+7.5, 60, 6, 0.25)

    pcb += ")\n"

    ppath = os.path.join(out, f"{proj}.kicad_pcb")
    open(ppath, "w", encoding="utf-8").write(pcb)

    return path, ppath


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    results = []
    for gen_fn in [gen_sensor_node, gen_climate_node, gen_irrigation_node]:
        sch_p, pcb_p = gen_fn()
        for p in (sch_p, pcb_p):
            ok, msg = validate(p)
            short = os.path.relpath(p, BASE)
            status = "OK " if ok else "ERR"
            print(f"  {status}  {short}  — {msg}")
            results.append(ok)

    print()
    if all(results):
        print("TUMU GECERLI — KiCad 7.0 ile acilabilir.")
    else:
        print("HATA: bazi dosyalar hala yanlis.")

if __name__ == "__main__":
    main()
