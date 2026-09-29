# AirBridge.S3

Turn a **Waveshare ESP32-S3-GEEK** USB dongle into a portable WiFi access point
with internet tethering. Plug it into any computer's USB port — the host shares
its internet over USB, and AirBridge.S3 re-broadcasts it as a WiFi hotspot.

A 1.14" color LCD shows live status (SSID, password, USB/NAT state, connected
clients), and a built-in web UI lets you reconfigure everything on the fly.

## Features

- **WiFi Access Point** — WPA2 hotspot with configurable SSID and password
- **USB Internet Tethering** — Appears as a USB Ethernet adapter (NCM) to the host; gets internet via DHCP
- **NAT/NAPT** — Automatically routes traffic between the USB uplink and WiFi clients
- **Status Display** — 1.14" ST7789 LCD showing SSID, password, IP, USB link state, NAT status, CPU/memory usage, and connected devices
- **Crash Diagnostics** — LCD shows reset reason (PANIC, WDT, brownout, etc.) on non-normal boots
- **Web Configuration** — Browser UI to change SSID, password, IP address, and DHCP range
- **Persistent Config** — Settings stored in NVS flash, survive reboots

## How It Works

```
┌─────────────┐   USB NCM    ┌──────────────┐   WiFi AP   ┌──────────┐
│  Host PC    │─────────────▶│ AirBridge.S3 │◀────────────│ Phone /  │
│  (internet) │  Ethernet    │  ESP32-S3    │   802.11n   │ Laptop   │
└─────────────┘              └──────────────┘             └──────────┘
                                  │  NAT
                              translates WiFi
                              client traffic
                              to USB uplink
```

1. The host PC sees AirBridge.S3 as a USB Ethernet adapter
2. macOS/Linux Internet Sharing (or equivalent) gives it an IP via DHCP
3. AirBridge.S3 runs a WiFi AP on a separate subnet (default `192.168.3.0/24`)
4. NAT/NAPT on the ESP32 bridges WiFi clients to the USB uplink

## Hardware

Two build targets share this tree; pick the PlatformIO env for what you have.

### `esp32s3geek` — Waveshare ESP32-S3-GEEK (default)

- [Waveshare ESP32-S3-GEEK](https://www.waveshare.com/wiki/ESP32-S3-GEEK) — ESP32-S3R2, 16 MB flash, 2 MB PSRAM, USB-A male plug
- 1.14" ST7789 IPS LCD (135×240, SPI), built into the dongle
- Native USB-OTG on GPIO19/20

```
LCD MOSI   GPIO11      USB D+     GPIO20
LCD SCLK   GPIO12      USB D-     GPIO19
LCD CS     GPIO10      BOOT btn   GPIO0
LCD DC     GPIO8       RGB LED    GPIO38
LCD RST    GPIO9
LCD BL     GPIO7
```

### `esp32s31` — ESP32-S31 + external 1.8" ST7735 TFT

- ESP32-S31 (dual-core RISC-V, Wi-Fi 6, native USB-OTG 2.0 High-Speed) —
  see [Toolchain status](#esp32-s31-toolchain-status-read-before-building) below
- 1.8" ST7735 TFT, 128×160, SPI, backlight tied to 3V3 (always on)

```
Display   ESP32-S31   Purpose
VCC       3V3         3.3V power
GND       GND         Common ground
LED       3V3         Backlight, always on
SCK       GPIO12      SPI clock
SDA       GPIO11      SPI MOSI
CS        GPIO10      Chip select
A0        GPIO9       Data/command (DC)
RESET     GPIO8       Reset
```

#### ESP32-S31 toolchain status — read before building

The S31 launched in 2026, on release-candidate tooling: ESP-IDF support
landed as preview in **v6.1** (`esp32s3geek` uses the stable v5.5.5),
arduino-esp32 support is merged only on the unreleased `release/v4.0.x`
branch, and pioarduino/platform-espressif32 has no S31 board definition
on its `main`/`develop` branches — the `esp32s31` env instead pins the
pre-release tag `61.04.00-RC1` directly, with a local copy of that tag's
`esp32-s31-coreboard-1.json` in `boards/` since no stable release ships
it yet.

**This env has been build-verified**: `pio run -e esp32s31` produces a
working `firmware.factory.bin` (1.22 MB flash, 57 KB RAM) from a clean
checkout. Getting there needed real fixes, all committed here — not just
following the toolchain's happy path:

- **LovyanGFX (`^1.2.0`, currently resolves to 1.2.30) has no idea the
  S31 exists.** `patch_lovyangfx_s31.py` (new pre-build hook, mirrors the
  existing `patch_ecm_cmake.py`/`patch_tinyusb.py` pattern) fixes three
  gaps: its platform switch falls into classic-ESP32 code that needs a
  ROM header (`rom/lldesc.h`) IDF 6.1.0 doesn't ship for this target yet;
  its fast-GPIO helpers assume the legacy raw-register layout instead of
  the struct-typed one the S31 actually uses (like its RISC-V siblings);
  and its I2C driver assumes a register layout the S31's I2C peripheral
  doesn't have at all (different `i2c_dev_t` shape — not a few renamed
  fields, a different peripheral generation). Since this project only
  ever uses `lgfx::Bus_SPI` on the S31 (see `LGFX_Config_s31.h`), I2C is
  skipped outright rather than guessed at. Full rationale is in that
  file's docstring.
- **`patch_ecm_cmake.py`'s literal-text patches were written against IDF
  5.5.5's TinyUSB source; several silently no-op'd against 6.1.0's.**
  Verified via `pio run -e esp32s31 -v`, which prints an applied-count
  per patch group:
  - `CMakeLists.txt`, `usb_descriptors.c`, `ecm_rndis_device.c`,
    `dcd_dwc2.c`: all patches apply cleanly (`dcd_dwc2.c` needed 3
    anchor fixes for text IDF 6.1.0 changed — an added include, an added
    condition clause, an added guard block — now fixed and applying
    9/9).
  - `descriptors_control.c`: needed an anchor fix for an added
    `CFG_TUD_MTP` clause; now applies to both occurrences.
  - `usbd.c`: **4 of 12** crash-diagnostic breadcrumb patches apply
    (`0x60`, `0x80`–`0x87`). The other 8, all inside `process_set_config`
    (`0x70`, `0xB0`–`0xB7`), don't — that function was restructured
    enough in this TinyUSB version that re-deriving correct anchors
    wasn't done here. This only affects the LCD's post-crash diagnostic
    code (fewer checkpoints are instrumented); it doesn't affect the
    build or normal operation.
  - Run `pio run -e esp32s31 -v 2>&1 | grep patch_ecm_cmake` yourself to
    re-check this after any TinyUSB/esp_tinyusb version bump.
- **Still genuinely unverified — no real S31 hardware was available to
  test against**:
  - Whether the resulting firmware actually enumerates and tethers
    correctly. The S31's USB-OTG is real USB 2.0 High-Speed (480 Mbps),
    unlike the S3's Full-Speed (12 Mbps); the NCM notification-ordering
    and packet-filter-ACK logic in `patch_ecm_cmake.py` was reverse
    engineered against Full-Speed behavior and may need rework.
  - The ST7735 display offset (`offset_x`/`offset_y` in
    `src/LGFX_Config_s31.h`) — panel-batch-dependent (same issue as
    Adafruit's ST7735 "tab color" quirk). The checked-in values are the
    most commonly reported ones for this 128×160 module family, not
    verified against a specific unit — if the image is shifted or
    clipped on one edge on first boot, adjust those two values.
  - `dependencies.lock` has been regenerated against the actual resolved
    IDF 6.1.0 component set from a successful build (previously it only
    reflected IDF 5.5.5).

## Architecture

### Stack

```
┌────────────────────────────────────────────────┐
│               Application Layer                │
│  main.cpp · display · webserver · config (NVS) │
├────────────────────────────────────────────────┤
│             Network Layer                      │
│  wifi_ap.cpp    WiFi SoftAP + DHCP server      │
│  usb_net.cpp    TinyUSB NCM + custom esp_netif │
│  sysmon.h       CPU% + memory% monitoring       │
│  nat.cpp        lwIP NAPT (IP forwarding)      │
├────────────────────────────────────────────────┤
│           Framework (hybrid build)             │
│  Arduino 3.x/4.x API + ESP-IDF 5.5/6.1 (lwIP, │
│  (WiFi, Preferences,    TinyUSB, esp_netif,    │
│   WebServer)            NAPT, NVS)             │
├────────────────────────────────────────────────┤
│  LovyanGFX         SPI display driver          │
├────────────────────────────────────────────────┤
│  pioarduino        PlatformIO build system     │
└────────────────────────────────────────────────┘
```

### Key Components

- **`usb_net.cpp`** — Initializes TinyUSB in USB-OTG mode with NCM (Network Control Model) class. Creates a custom `esp_netif` driver that bridges TinyUSB NCM packets into lwIP. Runs DHCP client to obtain an IP from the host. Tracks USB link state via `tud_ready()`. Shows NCM notification debug state on the LCD when offline.
- **`sysmon.h`** — Inline helpers for CPU utilization (via FreeRTOS idle-task runtime, dual-core aware) and heap memory usage percentage.
- **`nat.cpp`** — Enables ESP-IDF's built-in lwIP NAPT on the WiFi AP interface. Activated automatically when the USB link gets an IP; disabled when the link drops.
- **`wifi_ap.cpp`** — Configures the ESP32 SoftAP with static IP, WPA2, and the Arduino DHCP server. Enumerates connected stations and resolves their IPs via the DHCP lease table.
- **`display_s3geek.cpp`** — Drives the ST7789 LCD via LovyanGFX with a full-screen sprite buffer for flicker-free updates. Dense 3-column landscape layout (240×135): SSID/password/IP, USB/STA/NAT status, and a 2-column client grid, all on one screen.
- **`display_s31.cpp`** — Drives the ST7735 LCD via LovyanGFX. Portrait (128×160), auto-cycling through three full-screen pages every few seconds: a large-font SSID/password/IP "join" screen, a USB/STA/NAT status screen with CPU/MEM bar gauges, and a scrolling client list. Only one of `display_s3geek.cpp` / `display_s31.cpp` is compiled per env — see `build_src_filter` in `platformio.ini` and the target check in `src/CMakeLists.txt`.
- **`webserver.cpp`** — Minimal HTTP server (raw `WiFiServer`) serving an embedded HTML/CSS config page. Handles form POST to save settings to NVS and reboot.
- **`config.cpp`** — Reads/writes AP configuration (SSID, password, IP, DHCP range) to ESP32 NVS flash using the Arduino `Preferences` library.
- **`LGFX_Config_s3geek.h`** — LovyanGFX hardware descriptor for the Waveshare ESP32-S3-GEEK's SPI bus, ST7789 panel geometry/offsets, and PWM backlight.
- **`LGFX_Config_s31.h`** — LovyanGFX hardware descriptor for the ESP32-S31's external ST7735 panel (no backlight control — LED is wired straight to 3V3).

### Why a Hybrid Build?

The project uses `framework = arduino, espidf` (pioarduino) because:
- **Arduino** provides convenient APIs for WiFi, Preferences (NVS), and rapid prototyping
- **ESP-IDF** is required for TinyUSB NCM networking, `esp_netif` custom drivers, `ip_napt_enable()`, and lwIP IP forwarding — none of which are exposed through the Arduino layer

### macOS NCM Patches

The stock TinyUSB NCM driver doesn't fully work with macOS. A build-time patch script (`patch_ncm_cmake.py`) automatically applies fixes during CMake configuration:

1. **100 Mbps speed** — Reports 100 Mbps instead of 12 Mbps so macOS maps to a 100BaseTX medium
2. **Packet filter ACK** — Acknowledges `SET_ETHERNET_PACKET_FILTER` and `SET_ETHERNET_MULTICAST_FILTERS` requests that macOS sends during Internet Sharing setup
3. **Notification ordering** — Sends CONNECTED + SPEED notifications from `netd_open()` (during enumeration) and reorders SET_INTERFACE to ACK before sending notifications
4. **Debug telemetry** — Exposes `ncm_notif_debug` variable for LCD display diagnostics

These patches are applied to the managed component at build time and don't modify tracked source files. Written and verified against `esp32s3geek`'s IDF 5.5.5 TinyUSB; see [ESP32-S31 toolchain status](#esp32-s31-toolchain-status-read-before-building) for exactly which of them needed anchor fixes for `esp32s31`'s IDF 6.1.0 TinyUSB, and which are still incomplete there.

## Build & Flash

Requires [PlatformIO](https://platformio.org/) (CLI or VS Code extension).
Two envs are defined — `esp32s3geek` (default) and `esp32s31`; pick one with
`-e` or set it as `default_envs` in `platformio.ini`.

```bash
# Build (defaults to esp32s3geek)
pio run
pio run -e esp32s31

# Flash (see note below about boot mode)
pio run -e esp32s31 -t upload

# Full clean rebuild (needed after sdkconfig changes)
pio run -e esp32s31 -t clean && pio run -e esp32s31
```

### Entering Bootloader Mode

Since the firmware uses USB-OTG for NCM networking (not USB-Serial), the
automatic upload reset circuit is unavailable on boards without separate
bootloader-strapping hardware. To flash:

1. Hold the **BOOT** button on the board
2. Plug the board into USB (or press **RST** if already plugged in)
3. Release **BOOT**
4. Run `pio run -t upload`

After flashing, unplug and re-plug the board to boot normally.

### Serial Console

The USB port is used for NCM networking, so there is no USB serial console.
Debug output uses `ESP_LOGx()` macros. To see logs, connect a USB-to-UART
adapter to UART0 (or use the on-device LCD for status).

## Usage

### Quick Start

1. Flash the firmware (see above)
2. Plug AirBridge.S3 into your computer's USB port
3. The LCD shows the WiFi SSID and password
4. Connect your phone/tablet to the displayed SSID

### Sharing Internet from macOS

1. Open **System Settings → General → Sharing → Internet Sharing**
2. Share from: **Wi-Fi** (or **Ethernet** — whichever has internet)
3. To devices using: check **AirBridge.S3** (appears as a USB Ethernet adapter)
4. Enable Internet Sharing
5. The LCD will show `USB: Online (NAT)` once DHCP completes
6. WiFi clients now have internet access through your Mac

### Sharing Internet from Linux

```bash
# Find the NCM interface (usually usb0 or enx...)
ip link show

# Enable IP forwarding and NAT
sudo sysctl net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Assign an IP to the USB interface
sudo ip addr add 192.168.7.1/24 dev usb0
sudo ip link set usb0 up
```

### Web Configuration

Connect to the WiFi AP and open `http://<device-ip>/` (default `http://192.168.3.1/`).
You can change:
- SSID and password
- Device IP address
- DHCP range

Click **Save & Reboot** — the device restarts with the new settings.

## Default Settings

- **SSID**: `PM_Travel`
- **Password**: `Adames007`
- **IP Address**: `192.168.3.1`
- **Subnet**: `255.255.255.0`
- **DHCP Range**: `.2` – `.255`

## Project Structure

```
src/
├── main.cpp             Setup + main loop (init, periodic display refresh)
├── config.cpp/h         NVS config storage with defaults
├── wifi_ap.cpp/h        SoftAP init, client tracking via DHCP lease table
├── display.h            Shared display interface (both boards implement this)
├── display_s3geek.cpp   ST7789 LCD rendering for esp32s3geek (LovyanGFX, sprite buffer)
├── display_s31.cpp      ST7735 LCD rendering for esp32s31 (LovyanGFX, paged UI)
├── webserver.cpp/h      HTTP config interface (embedded HTML/CSS)
├── usb_net.cpp/h        USB NCM tethering (TinyUSB + custom esp_netif)
├── nat.cpp/h            NAT/NAPT (lwIP ip_napt_enable)
├── sysmon.h             CPU utilization + memory usage monitoring
├── LGFX_Config_s3geek.h LovyanGFX hardware config for ESP32-S3-GEEK (ST7789)
├── LGFX_Config_s31.h    LovyanGFX hardware config for ESP32-S31 (ST7735)
├── CMakeLists.txt       Excludes the non-matching display_*.cpp per IDF_TARGET
└── idf_component.yml    ESP-IDF managed component deps (esp_tinyusb)

boards/
└── esp32-s31-coreboard-1.json  Local copy of the S31 board def (see README's toolchain status section)

patch_ncm_cmake.py       Build-time NCM driver patches for macOS (both envs)
patch_tinyusb.py         PlatformIO pre-build hook (delegates to CMake patch)
patch_lovyangfx_s31.py   PlatformIO pre-build hook: LovyanGFX ESP32-S31 compat fixes
platformio.ini           PlatformIO build configuration (esp32s3geek + esp32s31 envs)
sdkconfig.defaults       ESP-IDF Kconfig overrides for esp32s3geek
sdkconfig.s31.defaults   ESP-IDF Kconfig overrides for esp32s31
partitions_16MB.csv      Custom partition table (16 MB flash, both boards)

docs/                    Technical spec, diagrams (SVG)
hardware/                KiCad schematic + PCB for AirBridge Pro (next-gen)
```

## License

MIT
