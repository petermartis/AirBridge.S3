# AirBridge Pro — KiCad Hardware Design

**Version:** 1.0  
**Date:** March 2026  
**Status:** Hardware Design Phase

## Overview

AirBridge Pro is a portable, battery-powered multi-mode network bridge built on a dual-chip ESP32 architecture. This KiCad project contains the complete schematic and PCB layout for the device.

## Key Features

The device provides WiFi 6 access point capability, WiFi-to-WiFi repeater mode, USB NCM internet tethering, and wired Ethernet connectivity. All functions are managed through a 2.0-inch capacitive touchscreen LCD and a web-based configuration interface.

## Architecture

The design employs two specialized ESP32 chips connected via a high-speed SPI link carrying raw Ethernet frames at 40-80 MHz.

| Chip | Role | Key Functions |
|------|------|---------------|
| ESP32-S3-WROOM-1-N8R2 | I/O Hub | USB OTG, LCD, Ethernet (W5500), Power Management |
| ESP32-C5-WROOM-1-N8R4 | Routing Brain | WiFi 6 AP+STA, NAT/NAPT, DHCP, Web Server |

## Project Files

| File | Description |
|------|-------------|
| `AirBridge_Pro.kicad_pro` | KiCad project file with design rules and net classes |
| `AirBridge_Pro.kicad_sch` | Full schematic with all components and connections |
| `AirBridge_Pro.kicad_pcb` | 4-layer PCB layout (70mm x 50mm) |
| `AirBridge_Pro.kicad_sym` | Custom symbol library |
| `AirBridge_Pro.kicad_dru` | Custom design rules (antenna keep-out, impedance, etc.) |

## Component Summary

### Core Modules
- **U1:** ESP32-S3-WROOM-1-N8R2 (I/O Hub, 8MB Flash, 2MB PSRAM)
- **U2:** ESP32-C5-WROOM-1-N8R4 (WiFi 6 Routing Brain, 8MB Flash, 4MB PSRAM)

### Networking
- **U3:** W5500 (WIZnet Ethernet MAC+PHY, QFN-48)
- **J1:** HR911105A (RJ45 with integrated magnetics)
- **Y1:** 25 MHz crystal (W5500 clock source)

### Power Management
- **U4:** AXP2101 (PMIC: charger + 3x buck + fuel gauge)
- **U5:** STUSB4500 (USB-C PD sink controller, 5V/3A)
- **U6:** DW01A (LiPo battery protection)
- **U7:** FS8205A (Dual N-MOSFET for battery protection)
- **L1:** 2.2 uH inductor (AXP2101 DCDC1)

### Connectors
- **J2:** USB-C #1 (Data port, NCM tethering via S3 OTG)
- **J3:** USB-C #2 (Power input, 5V/3A PD charging)
- **J4:** JST-PH 2-pin (LiPo battery, 1.25mm pitch)
- **J5:** LCD FPC 15-pin (2.0" IPS display + CST816D touch)

### Display
- ST7789T3 LCD controller (SPI @ 40 MHz, 240x320)
- CST816D capacitive touch controller (I2C @ 0x15)

## PCB Specifications

| Parameter | Value |
|-----------|-------|
| Layers | 4 (Signal - GND - Power - Signal) |
| Board Size | 70mm x 50mm |
| Thickness | 1.6mm |
| Min Trace/Space | 6/6 mil (0.15mm) |
| Impedance (single-ended) | 50 ohm |
| Impedance (differential) | 100 ohm (Ethernet, USB) |
| Copper Finish | HASL |

## Net Classes

| Class | Track Width | Clearance | Notes |
|-------|-------------|-----------|-------|
| Default | 0.2mm | 0.15mm | General signal routing |
| Power | 0.5mm | 0.2mm | +3V3, GND, VBUS, VBAT |
| USB_Diff | 0.15mm | 0.15mm | USB D+/D- differential pair (90 ohm) |
| Ethernet_Diff | 0.2mm | 0.15mm | ETH TX/RX differential pairs (100 ohm) |

## I2C Bus (Shared, on ESP32-S3)

| Address | Device | Function |
|---------|--------|----------|
| 0x15 | CST816D | Capacitive touch controller |
| 0x28 | STUSB4500 | USB-C PD sink controller |
| 0x34 | AXP2101 | PMIC + fuel gauge |

Pull-up resistors R6 (4.7K) and R7 (4.7K) to +3V3 are included.

## Critical Layout Notes

1. **WiFi Antenna Keep-out:** No copper on any layer within 10mm of the ESP32-C5 module antenna area. Ground plane extends to module edge but not under antenna.

2. **Ethernet Section:** W5500 and 25 MHz crystal placed as close as possible to the RJ45 jack. TX/RX differential pairs are length-matched to 25mm or less.

3. **Power Section:** AXP2101 DCDC inductor loop (SW to L to VOUT) kept tight and short. Input/output capacitors within 3mm of AXP2101 pins. Power section on opposite end of board from RF sections.

4. **USB-C Connectors:** Data port (D+/D-) routed as 90 ohm differential impedance. Power port CC1/CC2 traces to STUSB4500 kept short. ESD protection (TVS diodes) on both ports.

5. **SPI Buses:** Clock lines under 50mm with matched impedance. Decoupling caps at each SPI slave CS pin. Inter-chip SPI traces between S3 and C5 as short as possible.

## How to Open

1. Install KiCad 8.0 or later from [kicad.org](https://www.kicad.org/)
2. Open `AirBridge_Pro.kicad_pro` in KiCad
3. The schematic and PCB layout will be accessible from the project manager

## License

This hardware design is part of the AirBridge Pro project.
