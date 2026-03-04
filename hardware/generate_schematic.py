#!/usr/bin/env python3
"""
Generate AirBridge Pro KiCAD 9 schematic (.kicad_sch) — v5 (builder-based)

Uses KicadSchematicBuilder for:
  - Proper symbol_instances (eliminates duplicate_reference / unannotated)
  - Safe passive wiring helpers (eliminates wire-through-passive shorts)
  - Power-aware IC placement (eliminates multiple_net_names)

Run:  python3 hardware/generate_schematic.py
Output: hardware/AirBridge_Pro.kicad_sch
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicad_builder import KicadSchematicBuilder, snap


def build_airbridge_pro():
    sch = KicadSchematicBuilder(
        title="AirBridge Pro — Hardware Schematic",
        date="2026-03-03",
        rev="1.0",
        company="AirBridge",
        paper="A1",
        project="AirBridge_Pro",
        comments=[
            "Dual-chip ESP32 WiFi 6 network bridge",
            "ESP32-S3 I/O Hub + ESP32-C5 Routing Brain",
        ],
    )

    # ── Power symbols ──────────────────────────────────────────────
    sch.define_power("GND")
    sch.define_power("+3V3")
    sch.define_power("+5V")
    sch.define_power("VBUS")

    # ── Passives ───────────────────────────────────────────────────
    sch.define_passive("R")
    sch.define_passive("C")
    sch.define_passive("L")

    # ══════════════════════════════════════════════════════════════
    # IC / Connector symbol definitions
    # ══════════════════════════════════════════════════════════════

    # ESP32-S3-WROOM-1-N8R2
    s3_id = sch.define_ic("AirBridge", "ESP32-S3-WROOM-1-N8R2", "U",
        "RF_Module:ESP32-S3-WROOM-1",
        pins_left=[
            ("3V3", "2", "power_in"), ("EN", "3", "input"),
            ("IO0", "27", "bidirectional"), ("IO1", "39", "bidirectional"),
            ("IO2", "38", "bidirectional"), ("IO3", "15", "bidirectional"),
            ("IO4", "4", "bidirectional"), ("IO5", "5", "bidirectional"),
            ("IO6", "6", "bidirectional"), ("IO7", "7", "bidirectional"),
            ("IO8", "12", "bidirectional"),
        ],
        pins_right=[
            ("IO9", "17", "bidirectional"), ("IO10", "18", "bidirectional"),
            ("IO11", "19", "bidirectional"), ("IO12", "20", "bidirectional"),
            ("IO13", "21", "bidirectional"), ("IO14", "22", "bidirectional"),
            ("IO15", "8", "bidirectional"), ("IO16", "9", "bidirectional"),
            ("IO17", "10", "bidirectional"), ("IO19", "13", "bidirectional"),
            ("IO20", "14", "bidirectional"),
        ],
        pins_bottom=[("GND", "1", "power_in")],
        body_w=15.24)

    # ESP32-C5-WROOM-1-N8R4
    c5_id = sch.define_ic("AirBridge", "ESP32-C5-WROOM-1-N8R4", "U",
        "RF_Module:ESP32-S3-WROOM-1",  # placeholder — same WROOM form factor
        pins_left=[
            ("3V3", "2", "power_in"), ("EN", "3", "input"),
            ("IO0", "4", "bidirectional"), ("IO1", "5", "bidirectional"),
            ("IO2", "6", "bidirectional"), ("IO3", "7", "bidirectional"),
            ("IO4", "8", "bidirectional"),
        ],
        pins_right=[],
        pins_bottom=[("GND", "1", "power_in")],
        body_w=15.24)

    # W5500
    w5500_id = sch.define_ic("AirBridge", "W5500", "U",
        "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP3.5x3.5mm",
        pins_left=[
            ("MOSI", "49", "input"), ("MISO", "50", "output"),
            ("SCLK", "46", "input"), ("~{SCSn}", "48", "input"),
            ("~{INTn}", "32", "output"), ("~{RSTn}", "33", "input"),
            ("RSVD", "31", "input"),
        ],
        pins_right=[
            ("TXP", "19", "output"), ("TXN", "20", "output"),
            ("RXP", "21", "input"), ("RXN", "22", "input"),
            ("LINKLED", "29", "output"), ("ACTLED", "30", "output"),
            ("EXRES1", "17", "passive"),
        ],
        pins_top=[("3V3", "1", "power_in"), ("AVDD", "24", "power_in")],
        pins_bottom=[("GND", "9", "power_in"), ("XI", "36", "input"),
                     ("XO", "35", "output")],
        body_w=12.7)

    # HR911105A (RJ45)
    rj45_id = sch.define_ic("AirBridge", "HR911105A", "J",
        "Connector_RJ:RJ45_Hanrun_HR911105A_Horizontal",
        pins_left=[
            ("TX+", "1", "passive"), ("TX-", "2", "passive"),
            ("RX+", "3", "passive"), ("RX-", "6", "passive"),
        ],
        pins_right=[
            ("LED_G+", "9", "passive"), ("LED_G-", "10", "passive"),
            ("LED_Y+", "11", "passive"), ("LED_Y-", "12", "passive"),
        ],
        pins_bottom=[("GND", "13", "power_in"), ("SHIELD", "14", "passive")],
        body_w=10.16)

    # AXP2101
    axp_id = sch.define_ic("AirBridge", "AXP2101", "U",
        "Package_DFN_QFN:QFN-20-1EP_3x3mm_P0.45mm_EP1.6x1.6mm",
        pins_left=[
            ("VBUS", "1", "power_in"), ("BAT", "3", "passive"),
            ("SYS", "5", "power_out"), ("SDA", "10", "bidirectional"),
            ("SCL", "11", "input"), ("~{IRQ}", "12", "output"),
            ("EN", "14", "input"),
        ],
        pins_right=[
            ("SW1", "6", "passive"), ("FB1", "7", "passive"),
            ("SW2", "8", "passive"), ("FB2", "9", "passive"),
            ("SW3", "15", "passive"), ("FB3", "16", "passive"),
            ("TS", "4", "input"),
        ],
        pins_bottom=[("GND", "2", "power_in")],
        body_w=12.7)

    # STUSB4500
    stusb_id = sch.define_ic("AirBridge", "STUSB4500", "U",
        "Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
        pins_left=[
            ("CC1", "1", "bidirectional"), ("CC2", "2", "bidirectional"),
            ("VBUS_IN", "5", "power_in"), ("RESET", "9", "input"),
            ("ADDR0", "10", "input"), ("ADDR1", "11", "input"),
        ],
        pins_right=[
            ("VBUS_OUT", "6", "power_out"), ("~{ALERT}", "7", "output"),
            ("SDA", "3", "bidirectional"), ("SCL", "4", "input"),
            ("VDD", "12", "power_in"), ("VSYS", "13", "power_out"),
        ],
        pins_bottom=[("GND", "8", "power_in")],
        body_w=12.7)

    # DW01A (SOT-23-6)
    dw01a_id = sch.define_ic("AirBridge", "DW01A", "U",
        "Package_TO_SOT_SMD:SOT-23-6",  # confirmed in KiCad lib
        pins_left=[
            ("VCC", "5", "power_in"), ("GND", "6", "power_in"),
            ("CS", "2", "input"),
        ],
        pins_right=[
            ("OD", "1", "output"), ("OC", "3", "output"),
            ("TD", "4", "input"),
        ],
        body_w=7.62)

    # FS8205A (TSSOP-8)
    fs8205a_id = sch.define_ic("AirBridge", "FS8205A", "Q",
        "Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
        pins_left=[
            ("S1", "1", "passive"), ("G1", "3", "input"),
            ("G2", "6", "input"),
        ],
        pins_right=[
            ("D", "4", "passive"), ("S2", "7", "passive"),
        ],
        body_w=7.62)

    # USB-C Receptacle
    usbc_id = sch.define_ic("AirBridge", "USB_C_Receptacle", "J",
        "Connector_USB:USB_C_Receptacle_GCT_USB4085",
        pins_left=[
            ("VBUS", "A4", "power_out"), ("CC1", "A5", "bidirectional"),
            ("CC2", "B5", "bidirectional"), ("D+", "A6", "bidirectional"),
            ("D-", "A7", "bidirectional"),
        ],
        pins_right=[],
        pins_bottom=[("GND", "A1", "power_in"), ("SHIELD", "S1", "passive")],
        body_w=10.16)

    # 25 MHz Crystal
    crystal_id = sch.define_ic("AirBridge", "Crystal", "Y",
        "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm",
        pins_left=[("XI", "1", "passive")],
        pins_right=[("XO", "2", "passive")],
        pins_bottom=[("GND", "3", "passive")],
        body_w=5.08)

    # LCD FPC 18-pin
    lcd_id = sch.define_ic("AirBridge", "LCD_FPC_18P", "J",
        "Connector_FFC-FPC:Hirose_FH12-18S-0.5SH_1x18-1MP_P0.50mm_Horizontal",
        pins_left=[
            ("VDD", "1", "power_in"), ("IOVDD", "2", "power_in"),
            ("GND1", "3", "power_in"), ("MOSI", "4", "input"),
            ("SCLK", "5", "input"), ("~{CS}", "6", "input"),
            ("DC", "7", "input"), ("~{RST}", "8", "input"),
            ("BL", "9", "input"),
        ],
        pins_right=[
            ("T_SDA", "10", "bidirectional"), ("T_SCL", "11", "input"),
            ("T_INT", "12", "output"), ("T_RST", "13", "input"),
            ("T_VDD", "14", "power_in"), ("T_GND", "15", "power_in"),
            ("LEDK", "16", "passive"), ("LEDA", "17", "passive"),
            ("GND2", "18", "power_in"),
        ],
        body_w=10.16)

    # JST-PH 2-pin
    jst_id = sch.define_ic("AirBridge", "JST_PH_2", "J",
        "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",  # confirmed
        pins_left=[("BAT+", "1", "passive"), ("BAT-", "2", "passive")],
        pins_right=[],
        body_w=7.62)

    # ══════════════════════════════════════════════════════════════
    # Section headers
    # ══════════════════════════════════════════════════════════════
    sch.text("AirBridge Pro v1.0 — Hardware Schematic", 30, 15, 5)
    sch.text("=== POWER MANAGEMENT ===", 30, 38, 4)
    sch.text("=== ESP32-S3 (I/O Hub) ===", 330, 38, 4)
    sch.text("=== ESP32-C5 (WiFi 6) ===", 620, 38, 4)
    sch.text("=== ETHERNET ===", 30, 330, 4)
    sch.text("=== DISPLAY ===", 620, 330, 4)
    sch.text("=== USB DATA ===", 330, 330, 4)

    # ══════════════════════════════════════════════════════════════
    # Place ICs — ordered by ref designator within each prefix
    # ══════════════════════════════════════════════════════════════

    # ── U prefix: U1=DW01A, U2=W5500, U3=STUSB4500,
    #              U4=AXP2101, U5=ESP32-S3, U6=ESP32-C5 ──

    u1 = sch.place_ic(dw01a_id, "DW01A", snap(66), snap(340), nets={
        "VCC": "VBAT", "GND": "BAT_NEG",
        "CS": "GND",                       # tied to GND directly
        "OD": "DW01_OD", "OC": "DW01_OC", "TD": "DW01_TD",
    })

    u2 = sch.place_ic(w5500_id, "W5500", snap(130), snap(440), nets={
        "MOSI": "SPI1_MOSI", "MISO": "SPI1_MISO", "SCLK": "SPI1_SCLK",
        "~{SCSn}": "W5500_CS", "~{INTn}": "W5500_INT",
        "~{RSTn}": "W5500_RST",
        "RSVD": "GND",                     # tied to GND directly
        "TXP": "ETH_TXP", "TXN": "ETH_TXN",
        "RXP": "ETH_RXP", "RXN": "ETH_RXN",
        "LINKLED": "ETH_LINK", "ACTLED": "ETH_ACT",
        "EXRES1": "W5500_EXRES",
        "3V3": "+3V3", "AVDD": "+3V3",
        "GND": "GND",                      # power symbol, not label
        "XI": "XTAL_XI", "XO": "XTAL_XO",
    })

    u3 = sch.place_ic(stusb_id, "STUSB4500", snap(220), snap(110), nets={
        "CC1": "CC1", "CC2": "CC2", "VBUS_IN": "VBUS_5V",
        "RESET": "STUSB_RESET",
        "ADDR0": "GND",                    # tied to GND directly
        "ADDR1": "GND",                    # tied to GND directly
        "VBUS_OUT": "VBUS_OUT", "~{ALERT}": "STUSB_ALERT",
        "SDA": "I2C_SDA", "SCL": "I2C_SCL",
        "VDD": "+3V3", "VSYS": "NC",       # not used in this design
        "GND": "GND",                      # power symbol, not label
    })

    u4 = sch.place_ic(axp_id, "AXP2101", snap(220), snap(260), nets={
        "VBUS": "VBUS_OUT", "BAT": "VBAT", "SYS": "NC",
        "SDA": "I2C_SDA", "SCL": "I2C_SCL",
        "~{IRQ}": "NC", "EN": "+3V3",       # IRQ not routed in v1.0
        "SW1": "AXP_SW1", "FB1": "AXP_FB1",
        "SW2": "NC", "FB2": "NC", "SW3": "NC", "FB3": "NC",
        "TS": "AXP_TS",
        "GND": "GND",                      # power symbol, not label
    })

    u5 = sch.place_ic(s3_id, "ESP32-S3-WROOM-1-N8R2",
        snap(440), snap(180), nets={
        "3V3": "+3V3", "EN": "S3_EN", "IO0": "S3_BOOT",
        "IO1": "LCD_MOSI", "IO2": "LCD_SCLK", "IO3": "LCD_CS",
        "IO4": "LCD_DC", "IO5": "LCD_RST",
        "IO6": "SPI1_MOSI", "IO7": "SPI1_MISO", "IO8": "SPI1_SCLK",
        "IO9": "W5500_CS", "IO10": "W5500_INT", "IO11": "W5500_RST",
        "IO12": "C5_CS",
        "IO13": "I2C_SDA", "IO14": "I2C_SCL",
        "IO15": "TOUCH_INT", "IO16": "LCD_BL", "IO17": "C5_HANDSHAKE",
        "IO19": "USB_DM", "IO20": "USB_DP",
        "GND": "GND",
    })

    u6 = sch.place_ic(c5_id, "ESP32-C5-WROOM-1-N8R4",
        snap(660), snap(130), nets={
        "3V3": "+3V3", "EN": "C5_EN",
        "IO0": "SPI1_MOSI", "IO1": "SPI1_MISO",
        "IO2": "SPI1_SCLK", "IO3": "C5_CS",
        "IO4": "C5_HANDSHAKE",
        "GND": "GND",
    })

    # ── J prefix: J1=Battery, J2=USB-C Power, J3=RJ45,
    #              J4=USB-C Data, J5=LCD FPC ──

    j1 = sch.place_ic(jst_id, "Battery", snap(60), snap(260), nets={
        "BAT+": "VBAT", "BAT-": "BAT_NEG",
    })

    j2 = sch.place_ic(usbc_id, "USB-C Power", snap(76), snap(110), nets={
        "VBUS": "VBUS_5V", "CC1": "CC1", "CC2": "CC2",
        "D+": "NC", "D-": "NC",
        "GND": "GND", "SHIELD": "GND",     # both tied to GND
    })

    j3 = sch.place_ic(rj45_id, "HR911105A", snap(300), snap(440), nets={
        "TX+": "ETH_TXP", "TX-": "ETH_TXN",
        "RX+": "ETH_RXP", "RX-": "ETH_RXN",
        "LED_G+": "ETH_LINK", "LED_G-": "LED_G_K",
        "LED_Y+": "ETH_ACT", "LED_Y-": "LED_Y_K",
        "GND": "GND", "SHIELD": "GND",     # both tied to GND
    })

    j4 = sch.place_ic(usbc_id, "USB-C Data", snap(410), snap(420), nets={
        "VBUS": "NC", "CC1": "USB1_CC1", "CC2": "USB1_CC2",
        "D+": "USB_DP", "D-": "USB_DM",
        "GND": "GND", "SHIELD": "GND",     # both tied to GND
    })

    j5 = sch.place_ic(lcd_id, "2.0in LCD+Touch", snap(660), snap(440), nets={
        "VDD": "+3V3", "IOVDD": "+3V3", "GND1": "GND",
        "MOSI": "LCD_MOSI", "SCLK": "LCD_SCLK", "~{CS}": "LCD_CS",
        "DC": "LCD_DC", "~{RST}": "LCD_RST", "BL": "LCD_BL",
        "T_SDA": "I2C_SDA", "T_SCL": "I2C_SCL",
        "T_INT": "TOUCH_INT", "T_RST": "TOUCH_RST",
        "T_VDD": "+3V3", "T_GND": "GND",
        "LEDK": "GND",                     # tied to GND directly
        "LEDA": "LEDA",
        "GND2": "GND",
    })

    # ── Q prefix: Q1=FS8205A ──

    q1 = sch.place_ic(fs8205a_id, "FS8205A", snap(155), snap(340), nets={
        "S1": "BAT_NEG", "G1": "DW01_OD", "G2": "DW01_OC",
        "D": "GND",                        # tied to GND (was FS_DRAIN)
        "S2": "GND",                       # tied to GND (was FS_GND)
    })

    # ── Y prefix: Y1=Crystal ──

    y1 = sch.place_ic(crystal_id, "25MHz", snap(76), snap(510), nets={
        "XI": "XTAL_XI", "XO": "XTAL_XO",
        "GND": "GND",
    })

    # ══════════════════════════════════════════════════════════
    # PWR_FLAG — satisfy power_pin_not_driven ERC
    # ══════════════════════════════════════════════════════════
    # Place on any net that has power_in pins but no power_out.
    # GND: place on first GND power symbol (J2 GND area)
    sch.pwr_flag_at(*j2["GND"])
    # +3V3: place on first +3V3 power symbol (S3 3V3 area)
    sch.pwr_flag_at(*u5["+3V3"])
    # VBAT: place on battery connector BAT+ stub
    sch.pwr_flag_at(*j1["VBAT"])
    # BAT_NEG: place on battery connector BAT- stub
    sch.pwr_flag_at(*j1["BAT_NEG"])

    # ══════════════════════════════════════════════════════════
    # Support circuitry — helpers for all passives
    # ══════════════════════════════════════════════════════════

    # ── STUSB4500 (U3) ────────────────────────────────────────────
    sch.pull_up_h(u3["STUSB_RESET"], "10k", direction="left")
    sch.decoupling_cap_h(u3["+3V3"], "100nF", direction="right")

    # ── AXP2101 (U4) ─────────────────────────────────────────────
    # L1: SW1 → inductor → +3V3 rail
    l1_far = sch.series_passive_h(
        u4["AXP_SW1"], "Device:L", "2.2uH",
        direction="right", offset_grids=7)
    sch.power_at("+3V3", *l1_far)

    sch.decoupling_cap_h(u4["AXP_FB1"], "22uF",
                         direction="right", offset_grids=7)
    sch.decoupling_cap_h(u4["VBUS_OUT"], "10uF",
                         direction="left", offset_grids=6)
    sch.pull_down_h(u4["AXP_TS"], "10k", direction="right")

    # ── DW01A (U1) ────────────────────────────────────────────────
    sch.decoupling_cap_v(u1["DW01_TD"], "100nF",
                         direction="down", offset_grids=4)

    # ── ESP32-S3 (U5) ────────────────────────────────────────────
    sch.pull_up_h(u5["S3_EN"], "10k", direction="left")
    sch.pull_up_h(u5["S3_BOOT"], "10k", direction="left")     # fix: was dangling

    sch.decoupling_cap_h(u5["+3V3"], "100nF",
                         direction="left", offset_grids=6)
    sch.decoupling_cap_v(u5["+3V3"], "10uF",
                         direction="up", offset_grids=6)

    sch.pull_up_h(u5["I2C_SDA"], "4.7k", direction="right")
    sch.pull_up_h(u5["I2C_SCL"], "4.7k", direction="right")

    # ── ESP32-C5 (U6) ────────────────────────────────────────────
    sch.pull_up_h(u6["C5_EN"], "10k", direction="left")
    sch.decoupling_cap_h(u6["+3V3"], "100nF",
                         direction="left", offset_grids=6)

    # ── W5500 (U2) ───────────────────────────────────────────────
    sch.pull_down_h(u2["W5500_EXRES"], "12.4k", direction="right")
    sch.decoupling_cap_h(u2["3V3"], "100nF",
                         direction="right", offset_grids=5)
    sch.decoupling_cap_v(u2["AVDD"], "100nF",
                         direction="up", offset_grids=5)

    # ── Crystal (Y1) load caps ────────────────────────────────────
    sch.decoupling_cap_v(y1["XTAL_XI"], "20pF",
                         direction="down", offset_grids=5)
    sch.decoupling_cap_v(y1["XTAL_XO"], "20pF",
                         direction="down", offset_grids=5)

    # ── RJ45 (J3) LED current-limit resistors ────────────────────
    sch.pull_down_h(j3["LED_G_K"], "330", direction="right")
    sch.pull_down_h(j3["LED_Y_K"], "330", direction="right")

    # ── USB-C Data (J4) CC pull-downs ─────────────────────────────
    sch.pull_down_h(j4["USB1_CC1"], "5.1k", direction="left")
    sch.pull_down_h(j4["USB1_CC2"], "5.1k", direction="left")

    # ── LCD (J5) ─────────────────────────────────────────────────
    sch.pull_up_h(j5["LEDA"], "10R", direction="right")
    sch.pull_up_h(j5["TOUCH_RST"], "10k", direction="right")

    # ══════════════════════════════════════════════════════════════
    # Annotations
    # ══════════════════════════════════════════════════════════════
    sch.text("WiFi 6: 2.4+5GHz 802.11ax", 680, 100, 1.5)
    sch.text("AP + STA simultaneous", 680, 107, 1.5)
    sch.text("USB NCM Tethering (S3 OTG)", 380, 390, 2)
    sch.text("ST7789T3 240x320 SPI@40MHz", 640, 350, 1.5)
    sch.text("CST816D Touch I2C@0x15", 640, 357, 1.5)
    sch.text("I2C bus: 0x15=CST816D  0x28=STUSB4500  0x34=AXP2101",
             340, 295, 1.5)
    sch.text("SPI1 shared: W5500(CS=IO9) + C5(CS=IO12) @36-80MHz",
             340, 302, 1.5)
    sch.text("SPI2 LCD: IO1-5 -> ST7789T3 @40MHz", 340, 309, 1.5)
    sch.text("USB OTG: IO19/20 -> USB-C#1 NCM tethering", 340, 316, 1.5)

    return sch


def main():
    sch = build_airbridge_pro()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "AirBridge_Pro.kicad_sch")
    content = sch.write(path)
    print(f"Generated: {path}")
    sch.audit(content)


if __name__ == "__main__":
    main()
