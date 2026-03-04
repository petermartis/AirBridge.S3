"""AirBridge Pro — Auto-placement script for KiCad 9 Scripting Console.

Usage:
  1. In KiCad PCB Editor: Tools → Scripting Console
  2. Paste:  exec(open("/Users/peterm/AirBridge.S3/hardware/place_components.py").read())

Board layout (90 × 65 mm):
  ┌─────────────────────────────────────────────────┐
  │ J2(USB-C Pwr)  U3(STUSB)   U5(ESP32-S3)  J5   │ ← top
  │ J1(Batt) U4(AXP)           U6(ESP32-C5)  (LCD) │
  │ U1(DW01) Q1(FET)    U2(W5500) Y1   J3(RJ45)   │ ← bottom
  └─────────────────────────────────────────────────┘
"""

import pcbnew

board = pcbnew.GetBoard()

# ── Helpers ──────────────────────────────────────────────────────
def mm(v):
    """mm → KiCad internal units (nanometres)."""
    return pcbnew.FromMM(v)

def place(ref, x_mm, y_mm, rot_deg=0):
    """Move footprint by reference designator."""
    for fp in board.GetFootprints():
        if fp.GetReference() == ref:
            fp.SetPosition(pcbnew.VECTOR2I(mm(x_mm), mm(y_mm)))
            fp.SetOrientationDegrees(rot_deg)
            return True
    print(f"  ⚠ {ref} not found on board")
    return False

# ── Board origin ────────────────────────────────────────────────
# All coordinates are absolute mm.  Board is 90×65 at (100,100).
OX, OY = 100, 100
BW, BH = 90, 65

# ── Major component placement ──────────────────────────────────
print("Placing connectors...")
place("J2",  OX + 8,   OY + 12)          # USB-C Power — left edge
place("J1",  OX + 8,   OY + 35)          # JST Battery — left edge
place("J3",  OX + 80,  OY + 48, 180)     # RJ45 — right edge
place("J4",  OX + 45,  OY + 60)          # USB-C Data — bottom center
place("J5",  OX + 70,  OY + 4,  0)       # LCD FPC — top right

print("Placing ICs...")
place("U3",  OX + 24,  OY + 12)          # STUSB4500 — near USB-C Pwr
place("U4",  OX + 24,  OY + 35)          # AXP2101 — near battery
place("U1",  OX + 12,  OY + 52)          # DW01A — near battery
place("Q1",  OX + 28,  OY + 52)          # FS8205A — near DW01A
place("U5",  OX + 48,  OY + 20, 0)       # ESP32-S3 — center-top
place("U6",  OX + 48,  OY + 46, 0)       # ESP32-C5 — center-bottom
place("U2",  OX + 68,  OY + 32)          # W5500 — right, near RJ45
place("Y1",  OX + 62,  OY + 42)          # Crystal — near W5500

print("Placing passives...")
# ── STUSB4500 area (U3) passives ──
place("R1",  OX + 18,  OY + 8)           # STUSB_RESET pull-up
place("C1",  OX + 30,  OY + 8)           # STUSB VDD decoupling

# ── AXP2101 area (U4) passives ──
place("L1",  OX + 34,  OY + 30)          # SW1 inductor → +3V3
place("C2",  OX + 38,  OY + 30)          # FB1 decoupling
place("C3",  OX + 18,  OY + 30)          # VBUS_OUT decoupling
place("R2",  OX + 34,  OY + 38)          # TS pull-down

# ── DW01A area (U1) passives ──
place("C4",  OX + 16,  OY + 56)          # TD decoupling

# ── ESP32-S3 area (U5) passives ──
place("R3",  OX + 40,  OY + 14)          # S3_EN pull-up
place("R4",  OX + 40,  OY + 10)          # S3_BOOT pull-up
place("C5",  OX + 56,  OY + 14)          # S3 3V3 decoupling (h)
place("C6",  OX + 56,  OY + 10)          # S3 3V3 decoupling (v)
place("R5",  OX + 58,  OY + 18)          # I2C SDA pull-up
place("R6",  OX + 58,  OY + 22)          # I2C SCL pull-up

# ── ESP32-C5 area (U6) passives ──
place("R7",  OX + 40,  OY + 42)          # C5_EN pull-up
place("C7",  OX + 40,  OY + 46)          # C5 3V3 decoupling

# ── W5500 area (U2) passives ──
place("R8",  OX + 74,  OY + 36)          # EXRES pull-down
place("C8",  OX + 74,  OY + 28)          # W5500 3V3 decoupling (h)
place("C9",  OX + 68,  OY + 26)          # W5500 AVDD decoupling (v)

# ── Crystal (Y1) load caps ──
place("C10", OX + 58,  OY + 44)          # XI load cap
place("C11", OX + 66,  OY + 44)          # XO load cap

# ── RJ45 LED resistors ──
place("R9",  OX + 80,  OY + 40)          # LED_G_K
place("R10", OX + 80,  OY + 44)          # LED_Y_K

# ── USB-C Data (J4) CC pull-downs ──
place("R11", OX + 38,  OY + 56)          # CC1 pull-down
place("R12", OX + 42,  OY + 56)          # CC2 pull-down

# ── LCD (J5) passives ──
place("R13", OX + 78,  OY + 8)           # LEDA current limit
place("R14", OX + 78,  OY + 4)           # TOUCH_RST pull-up

# ── Update board outline ────────────────────────────────────────
print("Setting board outline (90 × 65 mm)...")
# Remove old edge cuts
for dwg in list(board.GetDrawings()):
    if dwg.GetLayerName() == "Edge.Cuts":
        board.Remove(dwg)

# Add new rectangle
rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECT)
rect.SetStart(pcbnew.VECTOR2I(mm(OX), mm(OY)))
rect.SetEnd(pcbnew.VECTOR2I(mm(OX + BW), mm(OY + BH)))
rect.SetLayer(board.GetLayerID("Edge.Cuts"))
rect.SetWidth(mm(0.1))
board.Add(rect)

# ── Refresh view ────────────────────────────────────────────────
pcbnew.Refresh()
print(f"\n✓ Placed all components on {BW}×{BH}mm board.")
print("  Next: Fine-tune positions, then route traces.")
