#!/usr/bin/env python3
"""KicadSchematicBuilder — Reusable KiCAD 9 schematic generation engine.

Generates valid .kicad_sch files with:
  - Proper symbol_instances section (eliminates annotation errors)
  - Safe passive wiring (no wire-through-component shorts)
  - Power-aware IC placement (auto power symbols on power pins)
  - Grid-snapped coordinates (2.54mm / 100mil)
  - Auto-incrementing reference designators

Usage:
    from kicad_builder import KicadSchematicBuilder, snap

    sch = KicadSchematicBuilder(
        title="My Project", date="2026-03-03", rev="1.0",
        company="ACME", comments=["Board rev A"],
    )

    # 1. Define symbols (once each)
    sch.define_passive("R")
    sch.define_passive("C")
    ic_id = sch.define_ic("MyLib", "MyChip", "U", "Package:QFN-48",
        pins_left=[("VIN", "1", "power_in"), ("EN", "2", "input")],
        pins_right=[("VOUT", "3", "power_out")],
        pins_bottom=[("GND", "4", "power_in")],
    )

    # 2. Place components
    u1 = sch.place_ic(ic_id, "MyChip", 100, 100, nets={
        "VIN": "+5V", "EN": "ENABLE", "VOUT": "+3V3", "GND": "GND",
    })

    # 3. Add support circuitry (safe wiring — no shorts)
    sch.pull_up_h(u1["EN"], "10k", direction="left")
    sch.decoupling_cap_h(u1["VIN"], "100nF", direction="left")

    # 4. Generate and write
    sch.write("output.kicad_sch")
"""

__all__ = ["KicadSchematicBuilder", "snap"]

import uuid
import math
import os


# ════════════════════════════════════════════════════════════════════
# Module-level utility
# ════════════════════════════════════════════════════════════════════

def snap(v, grid=2.54):
    """Snap a value to the nearest grid point (default 2.54 mm / 100 mil)."""
    return round(v / grid) * grid


# ════════════════════════════════════════════════════════════════════
# Builder class
# ════════════════════════════════════════════════════════════════════

class KicadSchematicBuilder:
    """Reusable KiCAD 9 schematic generation engine.

    Typical flow:
        define symbols → place components → add wiring helpers → generate()
    """

    GRID    = 2.54      # KiCAD standard grid (100 mil)
    STUB    = 3 * 2.54  # wire stub length from IC pin (7.62 mm)
    PIN_LEN = 2.54      # pin length inside symbol body

    # Net names that are automatically recognised as power nets.
    # When a pin maps to one of these in place_ic(), a power symbol is
    # placed instead of a net label — no separate gnd_at() call needed.
    DEFAULT_POWER_NETS = frozenset({
        "GND", "+3V3", "+3.3V", "+5V", "+1V8", "+1.8V", "+1V2", "+1.2V",
        "+12V", "+24V", "VBUS", "VCC", "VDD", "VSS", "VBAT",
    })

    # ── Constructor ─────────────────────────────────────────────────

    def __init__(self, title="", date="", rev="", company="",
                 paper="A1", comments=None, project=""):
        self.title    = title
        self.date     = date
        self.rev      = rev
        self.company  = company
        self.paper    = paper
        self.comments = comments or []
        self.project  = project

        # Root schematic UUID (also the virtual root sheet UUID)
        self._root_uuid = self._uid()

        # Mutable per-instance copy so users can extend
        self.power_nets = set(self.DEFAULT_POWER_NETS)

        # Internal storage
        self._lib_symbols  = {}   # lib_id → {text, hh, bw, ref_prefix, …}
        self._instances    = []   # placed-symbol s-expression strings
        self._wires        = []
        self._labels       = []
        self._no_connects  = []
        self._texts        = []
        self._ref_counters = {}   # prefix → current count
        self._pwr_counter  = 0

    # ── Static / private helpers ────────────────────────────────────

    @staticmethod
    def _uid():
        return str(uuid.uuid4())

    @staticmethod
    def _pin_abs(sx, sy, px, py, angle=0):
        """Convert lib-space pin position to schematic coordinates.

        KiCAD lib symbols use Y-up; schematics use Y-down.
        """
        py = -py  # flip Y
        r = math.radians(angle)
        c, s = math.cos(r), math.sin(r)
        return round(sx + px * c - py * s, 2), round(sy + px * s + py * c, 2)

    def _next_ref(self, prefix):
        self._ref_counters[prefix] = self._ref_counters.get(prefix, 0) + 1
        return f"{prefix}{self._ref_counters[prefix]}"

    def _next_pwr_ref(self):
        self._pwr_counter += 1
        return f"#PWR{self._pwr_counter:04d}"

    # ── Low-level s-expression fragments ────────────────────────────

    @staticmethod
    def _pin_sexpr(name, number, x, y, angle, etype="bidirectional",
                   length=2.54):
        return (
            f'      (pin {etype} line (at {x:.2f} {y:.2f} {angle})'
            f' (length {length})\n'
            f'        (name "{name}"'
            f' (effects (font (size 1.016 1.016))))\n'
            f'        (number "{number}"'
            f' (effects (font (size 1.016 1.016))))\n'
            f'      )'
        )

    @staticmethod
    def _rect_sexpr(x1, y1, x2, y2):
        return (
            f'      (rectangle (start {x1:.2f} {y1:.2f})'
            f' (end {x2:.2f} {y2:.2f})\n'
            f'        (stroke (width 0.254) (type default))\n'
            f'        (fill (type background))\n'
            f'      )'
        )

    def _wire_sexpr(self, x1, y1, x2, y2):
        return (
            f'  (wire (pts (xy {x1:.2f} {y1:.2f})'
            f' (xy {x2:.2f} {y2:.2f}))\n'
            f'    (stroke (width 0) (type default))\n'
            f'    (uuid {self._uid()})\n'
            f'  )'
        )

    def _label_sexpr(self, name, x, y, angle=0):
        return (
            f'  (label "{name}" (at {x:.2f} {y:.2f} {angle})\n'
            f'    (effects (font (size 1.27 1.27))'
            f' (justify left bottom))\n'
            f'    (uuid {self._uid()})\n'
            f'  )'
        )

    def _no_connect_sexpr(self, x, y):
        return (
            f'  (no_connect (at {x:.2f} {y:.2f})\n'
            f'    (uuid {self._uid()})\n'
            f'  )'
        )

    def _text_sexpr(self, txt, x, y, size=3.0):
        return (
            f'  (text "{txt}" (at {x:.2f} {y:.2f} 0)\n'
            f'    (effects (font (size {size} {size}) bold))\n'
            f'    (uuid {self._uid()})\n'
            f'  )'
        )

    # ── Symbol-instance s-expressions ───────────────────────────────

    def _sym_instance_sexpr(self, lib_id, ref, value, footprint, x, y, angle,
                            pin_nums, sym_uuid, in_bom="yes", on_board="yes"):
        """Build a schematic symbol instance.

        KiCad stores annotation per project + sheet instance path in the
        `(instances ...)` block.
        """
        project = self.project or ""
        if not project:
            raise ValueError(
                "KicadSchematicBuilder requires a non-empty project name "
                "(e.g. project='AirBridge_Pro') to emit symbol instances"
            )

        L = []
        L.append(f'  (symbol (lib_id "{lib_id}")')
        L.append(f'    (at {x:.2f} {y:.2f} {angle})')
        L.append(f'    (unit 1)')
        L.append(f'    (in_bom {in_bom})')
        L.append(f'    (on_board {on_board})')
        L.append(f'    (dnp no)')
        L.append(f'    (uuid {sym_uuid})')
        L.append(f'    (property "Reference" "{ref}"'
                 f' (at {x:.2f} {y - 3:.2f} 0)')
        L.append(f'      (effects (font (size 1.27 1.27)))')
        L.append(f'    )')
        L.append(f'    (property "Value" "{value}"'
                 f' (at {x:.2f} {y + 3:.2f} 0)')
        L.append(f'      (effects (font (size 1.27 1.27)))')
        L.append(f'    )')
        L.append(f'    (property "Footprint" "{footprint}" (at 0 0 0)')
        L.append(f'      (effects (font (size 1.27 1.27)) hide)')
        L.append(f'    )')
        L.append(f'    (property "Datasheet" "" (at 0 0 0)')
        L.append(f'      (effects (font (size 1.27 1.27)) hide)')
        L.append(f'    )')
        for pn in pin_nums:
            L.append(f'    (pin "{pn}" (uuid {self._uid()}))')
        L.append(f'    (instances')
        L.append(f'      (project "{project}"')
        L.append(f'        (path "/{self._root_uuid}"')
        L.append(f'          (reference "{ref}")')
        L.append(f'          (unit 1)')
        L.append(f'        )')
        L.append(f'      )')
        L.append(f'    )')
        L.append(f'  )')
        return '\n'.join(L)

    def _pwr_instance_sexpr(self, name, ref, x, y, sym_uuid):
        project = self.project or ""
        if not project:
            raise ValueError(
                "KicadSchematicBuilder requires a non-empty project name "
                "(e.g. project='AirBridge_Pro') to emit symbol instances"
            )

        L = []
        L.append(f'  (symbol (lib_id "power:{name}")')
        L.append(f'    (at {x:.2f} {y:.2f} 0)')
        L.append(f'    (unit 1)')
        L.append(f'    (in_bom no)')
        L.append(f'    (on_board no)')
        L.append(f'    (dnp no)')
        L.append(f'    (uuid {sym_uuid})')
        L.append(f'    (property "Reference" "{ref}"'
                 f' (at {x:.2f} {y - 2.54:.2f} 0)')
        L.append(f'      (effects (font (size 1.27 1.27)) hide)')
        L.append(f'    )')
        L.append(f'    (property "Value" "{name}"'
                 f' (at {x:.2f} {y + 2.54:.2f} 0)')
        L.append(f'      (effects (font (size 1.016 1.016)))')
        L.append(f'    )')
        L.append(f'    (property "Footprint" "" (at 0 0 0)')
        L.append(f'      (effects (font (size 1.27 1.27)) hide)')
        L.append(f'    )')
        L.append(f'    (property "Datasheet" "" (at 0 0 0)')
        L.append(f'      (effects (font (size 1.27 1.27)) hide)')
        L.append(f'    )')
        L.append(f'    (pin "1" (uuid {self._uid()}))')
        L.append(f'    (instances')
        L.append(f'      (project "{project}"')
        L.append(f'        (path "/{self._root_uuid}"')
        L.append(f'          (reference "{ref}")')
        L.append(f'          (unit 1)')
        L.append(f'        )')
        L.append(f'      )')
        L.append(f'    )')
        L.append(f'  )')
        return '\n'.join(L)

    # ── Lib-symbol builders (internal) ──────────────────────────────

    def _build_ic_symbol(self, lib, name, ref_prefix, footprint,
                         pins_left, pins_right, pins_top, pins_bottom,
                         body_w, hh):
        full = f"{lib}:{name}"
        G = self.GRID
        PL = self.PIN_LEN
        L = []
        L.append(f'    (symbol "{full}"')
        L.append(f'      (pin_names (offset 1.016))')
        L.append(f'      (exclude_from_sim no)')
        L.append(f'      (in_bom yes)')
        L.append(f'      (on_board yes)')
        for prop, val, yoff, hide in [
            ("Reference", ref_prefix, hh + G, False),
            ("Value", name, -(hh + G), False),
            ("Footprint", footprint, 0, True),
            ("Datasheet", "", 0, True),
        ]:
            h = " hide" if hide else ""
            L.append(f'      (property "{prop}" "{val}"'
                     f' (at 0 {yoff:.2f} 0)')
            L.append(f'        (effects (font (size 1.27 1.27)){h})')
            L.append(f'      )')
        # Body outline
        L.append(f'      (symbol "{name}_0_1"')
        L.append(self._rect_sexpr(-body_w, hh, body_w, -hh))
        L.append(f'      )')
        # Pins
        L.append(f'      (symbol "{name}_1_1"')
        xl = -(body_w + PL)
        xr = body_w + PL
        for i, (pn, pnum, pt) in enumerate(pins_left):
            L.append(self._pin_sexpr(pn, pnum,
                                     xl, hh - G - i * G, 0, pt))
        for i, (pn, pnum, pt) in enumerate(pins_right):
            L.append(self._pin_sexpr(pn, pnum,
                                     xr, hh - G - i * G, 180, pt))
        if pins_top:
            sx = -((len(pins_top) - 1) * G) / 2
            yt = hh + PL
            for i, (pn, pnum, pt) in enumerate(pins_top):
                L.append(self._pin_sexpr(pn, pnum,
                                         sx + i * G, yt, 270, pt))
        if pins_bottom:
            sx = -((len(pins_bottom) - 1) * G) / 2
            yb = -(hh + PL)
            for i, (pn, pnum, pt) in enumerate(pins_bottom):
                L.append(self._pin_sexpr(pn, pnum,
                                         sx + i * G, yb, 90, pt))
        L.append(f'      )')
        L.append(f'    )')
        return '\n'.join(L)

    def _build_passive_symbol(self, lib, name, ref_prefix, footprint,
                              body_w=2.54, body_h=2.54):
        full = f"{lib}:{name}"
        PL = self.PIN_LEN
        yoff = body_h + self.GRID
        L = []
        L.append(f'    (symbol "{full}"')
        L.append(f'      (pin_names (offset 1.016))')
        L.append(f'      (exclude_from_sim no)')
        L.append(f'      (in_bom yes)')
        L.append(f'      (on_board yes)')
        for prop, val, yy, hide in [
            ("Reference", ref_prefix, yoff, False),
            ("Value", name, -yoff, False),
            ("Footprint", footprint, 0, True),
            ("Datasheet", "", 0, True),
        ]:
            h = " hide" if hide else ""
            L.append(f'      (property "{prop}" "{val}"'
                     f' (at 0 {yy:.2f} 0)')
            L.append(f'        (effects (font (size 1.27 1.27)){h})')
            L.append(f'      )')
        L.append(f'      (symbol "{name}_0_1"')
        L.append(self._rect_sexpr(-body_w, body_h, body_w, -body_h))
        L.append(f'      )')
        L.append(f'      (symbol "{name}_1_1"')
        xl = -(body_w + PL)
        xr = body_w + PL
        L.append(self._pin_sexpr("1", "1", xl, 0, 0, "passive"))
        L.append(self._pin_sexpr("2", "2", xr, 0, 180, "passive"))
        L.append(f'      )')
        L.append(f'    )')
        return '\n'.join(L)

    def _build_power_symbol(self, name):
        full = f"power:{name}"
        L = []
        L.append(f'    (symbol "{full}"')
        L.append(f'      (power)')
        L.append(f'      (pin_names (offset 0))')
        L.append(f'      (exclude_from_sim no)')
        L.append(f'      (in_bom no)')
        L.append(f'      (on_board no)')
        L.append(f'      (property "Reference" "#PWR" (at 0 -2.54 0)')
        L.append(f'        (effects (font (size 1.27 1.27)) hide)')
        L.append(f'      )')
        L.append(f'      (property "Value" "{name}" (at 0 3.81 0)')
        L.append(f'        (effects (font (size 1.016 1.016)))')
        L.append(f'      )')
        L.append(f'      (property "Footprint" "" (at 0 0 0)')
        L.append(f'        (effects (font (size 1.27 1.27)) hide)')
        L.append(f'      )')
        L.append(f'      (property "Datasheet" "" (at 0 0 0)')
        L.append(f'        (effects (font (size 1.27 1.27)) hide)')
        L.append(f'      )')
        # Graphic
        L.append(f'      (symbol "{name}_0_1"')
        if name == "GND":
            L.append(f'        (polyline')
            L.append(f'          (pts (xy 0 0) (xy 0 -1.27)'
                     f' (xy -1.27 -1.27) (xy 0 -2.54)'
                     f' (xy 1.27 -1.27) (xy 0 -1.27))')
            L.append(f'          (stroke (width 0) (type default))')
            L.append(f'          (fill (type none))')
            L.append(f'        )')
        else:
            L.append(f'        (polyline')
            L.append(f'          (pts (xy 0 0) (xy 0 1.27))')
            L.append(f'          (stroke (width 0) (type default))')
            L.append(f'          (fill (type none))')
            L.append(f'        )')
            L.append(f'        (circle (center 0 1.778) (radius 0.508)')
            L.append(f'          (stroke (width 0) (type default))')
            L.append(f'          (fill (type none))')
            L.append(f'        )')
        L.append(f'      )')
        # Pin
        L.append(f'      (symbol "{name}_1_1"')
        if name == "GND":
            L.append(self._pin_sexpr(name, "1", 0, 0, 90,
                                     "power_in", 0))
        else:
            L.append(self._pin_sexpr(name, "1", 0, 0, 270,
                                     "power_in", 0))
        L.append(f'      )')
        L.append(f'    )')
        return '\n'.join(L)

    def _build_pwr_flag_symbol(self):
        """Build PWR_FLAG lib symbol (power_out pin — satisfies ERC)."""
        L = []
        L.append('    (symbol "power:PWR_FLAG"')
        L.append('      (power)')
        L.append('      (pin_names (offset 0))')
        L.append('      (exclude_from_sim no)')
        L.append('      (in_bom no)')
        L.append('      (on_board no)')
        L.append('      (property "Reference" "#FLG" (at 0 -2.54 0)')
        L.append('        (effects (font (size 1.27 1.27)) hide)')
        L.append('      )')
        L.append('      (property "Value" "PWR_FLAG" (at 0 3.81 0)')
        L.append('        (effects (font (size 1.016 1.016)))')
        L.append('      )')
        L.append('      (property "Footprint" "" (at 0 0 0)')
        L.append('        (effects (font (size 1.27 1.27)) hide)')
        L.append('      )')
        L.append('      (property "Datasheet" "" (at 0 0 0)')
        L.append('        (effects (font (size 1.27 1.27)) hide)')
        L.append('      )')
        L.append('      (symbol "PWR_FLAG_0_1"')
        L.append('        (polyline')
        L.append('          (pts (xy 0 0) (xy 0 1.27))')
        L.append('          (stroke (width 0) (type default))')
        L.append('          (fill (type none))')
        L.append('        )')
        L.append('      )')
        L.append('      (symbol "PWR_FLAG_1_1"')
        L.append(self._pin_sexpr("pwr", "1", 0, 0, 270,
                                 "power_out", 0))
        L.append('      )')
        L.append('    )')
        return '\n'.join(L)

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API — Symbol definition
    # ════════════════════════════════════════════════════════════════

    def define_ic(self, lib, name, ref_prefix, footprint,
                  pins_left, pins_right,
                  pins_top=None, pins_bottom=None,
                  body_w=12.7):
        """Register an IC lib_symbol.

        Each pin tuple: (name, number, electrical_type).
        electrical_type: "input" | "output" | "bidirectional" |
                         "passive" | "power_in" | "power_out"

        Returns lib_id string (e.g. "MyLib:MyChip") for placement.
        """
        pins_top = pins_top or []
        pins_bottom = pins_bottom or []
        n = max(len(pins_left), len(pins_right), 1)
        hh = max(math.ceil(n * self.GRID / 2 / self.GRID) * self.GRID,
                 5.08)
        lib_id = f"{lib}:{name}"
        text = self._build_ic_symbol(
            lib, name, ref_prefix, footprint,
            pins_left, pins_right, pins_top, pins_bottom,
            body_w, hh,
        )
        self._lib_symbols[lib_id] = dict(
            text=text, hh=hh, bw=body_w, ref_prefix=ref_prefix,
            footprint=footprint,
            pins_left=pins_left, pins_right=pins_right,
            pins_top=pins_top, pins_bottom=pins_bottom,
        )
        return lib_id

    def define_passive(self, type_name, footprint=""):
        """Register a standard 2-pin passive (R, C, or L).

        Returns lib_id (e.g. "Device:R").  Safe to call multiple times.
        """
        _defaults = {
            "R": ("Device", "R", "R",
                  "Resistor_SMD:R_0402_1005Metric"),
            "C": ("Device", "C", "C",
                  "Capacitor_SMD:C_0402_1005Metric"),
            "L": ("Device", "L", "L",
                  "Inductor_SMD:L_0805_2012Metric"),
        }
        lib, name, ref_prefix, default_fp = _defaults[type_name]
        fp = footprint or default_fp
        lib_id = f"{lib}:{name}"
        if lib_id not in self._lib_symbols:
            text = self._build_passive_symbol(lib, name, ref_prefix, fp)
            self._lib_symbols[lib_id] = dict(
                text=text, ref_prefix=ref_prefix,
                type="passive", body_w=2.54,
                footprint=fp,
            )
        return lib_id

    def define_power(self, name):
        """Register a power symbol (GND, +3V3, +5V, …).

        Returns lib_id.  Safe to call multiple times.
        """
        lib_id = f"power:{name}"
        if lib_id not in self._lib_symbols:
            text = self._build_power_symbol(name)
            self._lib_symbols[lib_id] = dict(
                text=text, ref_prefix="#PWR", type="power",
            )
        return lib_id

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API — Placement
    # ════════════════════════════════════════════════════════════════

    def place_ic(self, lib_id, value, x, y, nets=None):
        """Place an IC with wire stubs, labels, and power symbols.

        Args:
            lib_id: from define_ic()
            value:  display value string
            x, y:   schematic coordinates (IC body centre)
            nets:   {pin_name: net_name} mapping.
                    "NC"  → no-connect marker at pin
                    ""    → wire stub only (caller handles connection)
                    "GND" → power symbol at stub end  (any power_nets member)
                    "xyz" → net label "xyz" at stub end

        Returns:
            dict  pin_name → (x, y) of stub endpoint.
                  Also keyed by net_name when non-empty and non-NC.
        """
        info = self._lib_symbols[lib_id]
        nets = nets or {}

        ref = self._next_ref(info["ref_prefix"])
        pl, pr = info["pins_left"], info["pins_right"]
        pt, pb = info["pins_top"], info["pins_bottom"]
        bw, hh = info["bw"], info["hh"]

        all_pnums = [p[1] for p in pl + pr + pt + pb]
        sym_uuid = self._uid()
        footprint = info.get("footprint", "")
        self._instances.append(
            self._sym_instance_sexpr(
                lib_id, ref, value, footprint, x, y, 0, all_pnums, sym_uuid,
                in_bom=info.get("in_bom", "yes"),
                on_board=info.get("on_board", "yes"),
            )
        )

        pin_xl = -(bw + self.PIN_LEN)
        pin_xr = bw + self.PIN_LEN
        ends = {}

        def _proc(pn, ax, ay, stub_dx, stub_dy, lbl_angle):
            """Process one pin: stub wire + label/power/NC."""
            net = nets.get(pn, pn)
            if net == "NC":
                self._no_connects.append(self._no_connect_sexpr(ax, ay))
                return
            ex, ey = ax + stub_dx, ay + stub_dy
            self._wires.append(self._wire_sexpr(ax, ay, ex, ey))
            ends[pn] = (ex, ey)
            if net in self.power_nets:
                self.power_at(net, ex, ey)
            elif net:
                self._labels.append(
                    self._label_sexpr(net, ex, ey, lbl_angle))
            # Also index by net name (convenient for callers)
            if net and net != pn and net != "NC":
                ends[net] = (ex, ey)

        G, S = self.GRID, self.STUB
        for i, (pn, _, _) in enumerate(pl):
            ax, ay = self._pin_abs(x, y, pin_xl, hh - G - i * G)
            _proc(pn, ax, ay, -S, 0, 180)
        for i, (pn, _, _) in enumerate(pr):
            ax, ay = self._pin_abs(x, y, pin_xr, hh - G - i * G)
            _proc(pn, ax, ay, S, 0, 0)
        if pt:
            sx = -((len(pt) - 1) * G) / 2
            yt = hh + self.PIN_LEN
            for i, (pn, _, _) in enumerate(pt):
                ax, ay = self._pin_abs(x, y, sx + i * G, yt)
                _proc(pn, ax, ay, 0, -S, 90)
        if pb:
            sx = -((len(pb) - 1) * G) / 2
            yb = -(hh + self.PIN_LEN)
            for i, (pn, _, _) in enumerate(pb):
                ax, ay = self._pin_abs(x, y, sx + i * G, yb)
                _proc(pn, ax, ay, 0, S, 270)

        return ends

    def place_passive_h(self, lib_id, value, x, y):
        """Place a horizontal 2-pin passive.

        Returns ((left_x, left_y), (right_x, right_y)).
        """
        info = self._lib_symbols[lib_id]
        ref = self._next_ref(info["ref_prefix"])
        bw = info.get("body_w", 2.54)
        sym_uuid = self._uid()
        footprint = info.get("footprint", "")
        self._instances.append(
            self._sym_instance_sexpr(
                lib_id, ref, value, footprint, x, y, 0, ["1", "2"], sym_uuid,
                in_bom=info.get("in_bom", "yes"),
                on_board=info.get("on_board", "yes"),
            )
        )
        lx, ly = self._pin_abs(x, y, -(bw + self.PIN_LEN), 0)
        rx, ry = self._pin_abs(x, y,   bw + self.PIN_LEN,  0)
        return (lx, ly), (rx, ry)

    def place_passive_v(self, lib_id, value, x, y):
        """Place a vertical 2-pin passive (90° rotation).

        Returns ((top_x, top_y), (bottom_x, bottom_y)).
        """
        info = self._lib_symbols[lib_id]
        ref = self._next_ref(info["ref_prefix"])
        bw = info.get("body_w", 2.54)
        sym_uuid = self._uid()
        footprint = info.get("footprint", "")
        self._instances.append(
            self._sym_instance_sexpr(
                lib_id, ref, value, footprint, x, y, 90, ["1", "2"], sym_uuid,
                in_bom=info.get("in_bom", "yes"),
                on_board=info.get("on_board", "yes"),
            )
        )
        tp = self._pin_abs(x, y, -(bw + self.PIN_LEN), 0, 90)
        bp = self._pin_abs(x, y,   bw + self.PIN_LEN,  0, 90)
        return tp, bp

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API — Primitives
    # ════════════════════════════════════════════════════════════════

    def wire(self, x1, y1, x2, y2):
        """Add a wire segment."""
        self._wires.append(self._wire_sexpr(x1, y1, x2, y2))

    def label(self, name, x, y, angle=0):
        """Add a net label."""
        self._labels.append(self._label_sexpr(name, x, y, angle))

    def no_connect(self, x, y):
        """Add a no-connect (X) marker."""
        self._no_connects.append(self._no_connect_sexpr(x, y))

    def text(self, txt, x, y, size=3.0):
        """Add a text annotation (not electrically significant)."""
        self._texts.append(self._text_sexpr(txt, x, y, size))

    def power_at(self, name, x, y):
        """Place a power symbol at (x, y).  Auto-defines if needed."""
        lib_id = f"power:{name}"
        if lib_id not in self._lib_symbols:
            self.define_power(name)
        ref = self._next_pwr_ref()
        sym_uuid = self._uid()
        self._instances.append(
            self._pwr_instance_sexpr(name, ref, x, y, sym_uuid))

    def gnd_at(self, x, y):
        """Convenience: place GND power symbol."""
        self.power_at("GND", x, y)

    def v33_at(self, x, y):
        """Convenience: place +3V3 power symbol."""
        self.power_at("+3V3", x, y)

    def pwr_flag_at(self, x, y):
        """Place a PWR_FLAG symbol at (x, y).

        PWR_FLAG has a `power_out` pin that satisfies KiCad's
        `power_pin_not_driven` ERC check.  Place one on each
        net that has power_in pins but no explicit power_out source
        (e.g. GND, +3V3, VBAT, battery-negative nets).
        """
        lib_id = "power:PWR_FLAG"
        if lib_id not in self._lib_symbols:
            text = self._build_pwr_flag_symbol()
            self._lib_symbols[lib_id] = dict(
                text=text, ref_prefix="#FLG", type="power",
            )
        self._pwr_counter += 1
        ref = f"#FLG{self._pwr_counter:04d}"
        sym_uuid = self._uid()
        self._instances.append(
            self._pwr_instance_sexpr("PWR_FLAG", ref, x, y, sym_uuid))

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API — High-level wiring helpers
    #
    # All helpers wire to the NEAR pin and place power/GND at the
    # FAR pin, so the wire never crosses through the component body.
    # ════════════════════════════════════════════════════════════════

    def pull_up_h(self, pin_xy, value, direction="left",
                  power_net="+3V3", offset_grids=6):
        """Horizontal pull-up resistor.

        Places R with ``offset_grids`` grid-units of clearance.
        Wire → near pin, power symbol → far pin.
        """
        x, y = pin_xy
        self.define_passive("R")
        if direction == "left":
            rx = snap(x - offset_grids * self.GRID)
            p1, p2 = self.place_passive_h("Device:R", value, rx, y)
            self.wire(x, y, p2[0], p2[1])           # near (right)
            self.power_at(power_net, p1[0], p1[1])   # far  (left)
        else:
            rx = snap(x + offset_grids * self.GRID)
            p1, p2 = self.place_passive_h("Device:R", value, rx, y)
            self.wire(x, y, p1[0], p1[1])           # near (left)
            self.power_at(power_net, p2[0], p2[1])   # far  (right)

    def pull_up_v(self, pin_xy, value, direction="up",
                  power_net="+3V3", offset_grids=4):
        """Vertical pull-up resistor."""
        x, y = pin_xy
        self.define_passive("R")
        if direction == "up":
            ry = snap(y - offset_grids * self.GRID)
            p1, p2 = self.place_passive_v("Device:R", value, x, ry)
            self.wire(x, y, p2[0], p2[1])           # near (bottom)
            self.power_at(power_net, p1[0], p1[1])   # far  (top)
        else:
            ry = snap(y + offset_grids * self.GRID)
            p1, p2 = self.place_passive_v("Device:R", value, x, ry)
            self.wire(x, y, p1[0], p1[1])           # near (top)
            self.power_at(power_net, p2[0], p2[1])   # far  (bottom)

    def pull_down_h(self, pin_xy, value, direction="left",
                    offset_grids=6):
        """Horizontal pull-down resistor (to GND)."""
        self.pull_up_h(pin_xy, value, direction,
                       power_net="GND", offset_grids=offset_grids)

    def pull_down_v(self, pin_xy, value, direction="down",
                    offset_grids=4):
        """Vertical pull-down resistor (to GND)."""
        self.pull_up_v(pin_xy, value, direction,
                       power_net="GND", offset_grids=offset_grids)

    def decoupling_cap_h(self, pin_xy, value, direction="right",
                         offset_grids=6):
        """Horizontal decoupling capacitor (to GND)."""
        x, y = pin_xy
        self.define_passive("C")
        if direction == "right":
            cx = snap(x + offset_grids * self.GRID)
            p1, p2 = self.place_passive_h("Device:C", value, cx, y)
            self.wire(x, y, p1[0], p1[1])      # near (left)
            self.power_at("GND", p2[0], p2[1]) # far  (right)
        else:
            cx = snap(x - offset_grids * self.GRID)
            p1, p2 = self.place_passive_h("Device:C", value, cx, y)
            self.wire(x, y, p2[0], p2[1])      # near (right)
            self.power_at("GND", p1[0], p1[1]) # far  (left)

    def decoupling_cap_v(self, pin_xy, value, direction="down",
                         offset_grids=4):
        """Vertical decoupling capacitor (to GND)."""
        x, y = pin_xy
        self.define_passive("C")
        if direction == "down":
            cy = snap(y + offset_grids * self.GRID)
            p1, p2 = self.place_passive_v("Device:C", value, x, cy)
            self.wire(x, y, p1[0], p1[1])      # near (top)
            self.power_at("GND", p2[0], p2[1]) # far  (bottom)
        else:
            cy = snap(y - offset_grids * self.GRID)
            p1, p2 = self.place_passive_v("Device:C", value, x, cy)
            self.wire(x, y, p2[0], p2[1])      # near (bottom)
            self.power_at("GND", p1[0], p1[1]) # far  (top)

    def series_passive_h(self, pin_xy, lib_id, value, direction="right",
                         offset_grids=6):
        """Place a series passive inline.  Returns the far-pin (x, y).

        Wire connects pin_xy → near pin.
        Caller connects the returned far pin to whatever comes next.
        """
        x, y = pin_xy
        if direction == "right":
            px = snap(x + offset_grids * self.GRID)
            p1, p2 = self.place_passive_h(lib_id, value, px, y)
            self.wire(x, y, p1[0], p1[1])   # near (left)
            return p2                        # far  (right)
        else:
            px = snap(x - offset_grids * self.GRID)
            p1, p2 = self.place_passive_h(lib_id, value, px, y)
            self.wire(x, y, p2[0], p2[1])   # near (right)
            return p1                        # far  (left)

    def series_passive_v(self, pin_xy, lib_id, value, direction="down",
                         offset_grids=4):
        """Vertical series passive.  Returns the far-pin (x, y)."""
        x, y = pin_xy
        if direction == "down":
            py = snap(y + offset_grids * self.GRID)
            p1, p2 = self.place_passive_v(lib_id, value, x, py)
            self.wire(x, y, p1[0], p1[1])
            return p2
        else:
            py = snap(y - offset_grids * self.GRID)
            p1, p2 = self.place_passive_v(lib_id, value, x, py)
            self.wire(x, y, p2[0], p2[1])
            return p1

    # ════════════════════════════════════════════════════════════════
    # PUBLIC API — Output
    # ════════════════════════════════════════════════════════════════

    def generate(self):
        """Produce the complete .kicad_sch file content as a string."""
        root_uuid = self._root_uuid
        O = []
        O.append('(kicad_sch')
        O.append('  (version 20231120)')
        O.append('  (generator kicad_builder)')
        O.append(f'  (uuid {root_uuid})')
        O.append(f'  (paper "{self.paper}")')
        O.append('')

        # ── Title block ──
        O.append('  (title_block')
        if self.title:
            O.append(f'    (title "{self.title}")')
        if self.date:
            O.append(f'    (date "{self.date}")')
        if self.rev:
            O.append(f'    (rev "{self.rev}")')
        if self.company:
            O.append(f'    (company "{self.company}")')
        for i, c in enumerate(self.comments, 1):
            O.append(f'    (comment {i} "{c}")')
        O.append('  )')
        O.append('')

        # ── Library symbols ──
        O.append('  (lib_symbols')
        for info in self._lib_symbols.values():
            O.append(info['text'])
        O.append('  )')
        O.append('')

        # ── Schematic content ──
        O.extend(self._texts)
        O.append('')
        O.extend(self._instances)
        O.append('')
        O.extend(self._labels)
        O.append('')
        O.extend(self._wires)
        O.append('')
        O.extend(self._no_connects)
        O.append('')

        # ── Sheet instances ──
        O.append('  (sheet_instances')
        O.append('    (path "/"')
        O.append('      (page "1")')
        O.append('    )')
        O.append('  )')

        O.append(')')
        return '\n'.join(O)

    def write(self, path):
        """Generate and write to a file.  Returns the content string."""
        content = self.generate()
        with open(path, 'w') as f:
            f.write(content)
        return content

    def audit(self, content=None):
        """Print a diagnostic report (parens balance, net usage, etc.)."""
        if content is None:
            content = self.generate()
        n_bytes = len(content)
        n_lines = content.count('\n')
        depth = 0
        for c in content:
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
        balanced = depth == 0

        labels = {}
        for line in content.split('\n'):
            if '(label "' in line:
                name = line.split('(label "')[1].split('"')[0]
                labels[name] = labels.get(name, 0) + 1
        single = sorted(n for n, c in labels.items() if c == 1)

        print(f"  {n_bytes:,} bytes, {n_lines:,} lines")
        print(f"  Parens balanced: {balanced}")
        print(f"  Symbols: {len(self._instances)}")
        print(f"  Wires: {len(self._wires)}")
        print(f"  Labels: {len(self._labels)}")
        print(f"  No-connects: {len(self._no_connects)}")
        print(f"  Unique nets: {len(labels)}")
        if single:
            print(f"  Single-use labels (review): {single}")
        return balanced


# ════════════════════════════════════════════════════════════════════
# Self-test
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("KicadSchematicBuilder self-test …")
    sch = KicadSchematicBuilder(
        title="Self-Test",
        date="2026-03-03",
        rev="0.1",
        company="Test",
        project="Self-Test",
    )

    # Define symbols
    sch.define_passive("R")
    sch.define_passive("C")
    sch.define_passive("L")
    sch.define_power("GND")
    sch.define_power("+3V3")

    ic_id = sch.define_ic(
        "Test", "TestIC", "U", "Package:QFN-8",
        pins_left=[
            ("VIN", "1", "power_in"),
            ("EN", "2", "input"),
        ],
        pins_right=[
            ("VOUT", "3", "power_out"),
            ("SDA", "4", "bidirectional"),
        ],
        pins_bottom=[("GND", "5", "power_in")],
    )

    # Place IC with power-aware nets
    u1 = sch.place_ic(ic_id, "TestIC", snap(100), snap(100), nets={
        "VIN": "+3V3",    # → power symbol, no label
        "EN": "ENABLE",   # → net label
        "VOUT": "V_OUT",
        "SDA": "I2C_SDA",
        "GND": "GND",     # → power symbol
    })

    # High-level helpers (safe wiring)
    sch.pull_up_h(u1["EN"], "10k", direction="left")
    sch.decoupling_cap_h(u1["VIN"], "100nF", direction="left")
    sch.pull_up_v(u1["SDA"], "4.7k", direction="up")

    # Series passive
    far = sch.series_passive_h(
        u1["V_OUT"], "Device:L", "2.2uH", direction="right")
    sch.label("+3V3_OUT", far[0], far[1], 0)

    # Text annotation
    sch.text("Self-Test Schematic", 50, 30, 4)

    # Generate and audit
    content = sch.generate()
    print()
    ok = sch.audit(content)

    # Verify instances blocks exist for placed symbols
    n_inst = content.count('(instances')
    print(f"  instances blocks: {n_inst}")
    assert n_inst >= 1, "No instances blocks found!"
    assert ok, "Parens not balanced!"
    print("\n✓ Self-test passed.")
