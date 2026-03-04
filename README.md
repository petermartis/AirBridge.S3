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

- [Waveshare ESP32-S3-GEEK](https://www.waveshare.com/wiki/ESP32-S3-GEEK) — ESP32-S3R2, 16 MB flash, 2 MB PSRAM, USB-A male plug
- 1.14" ST7789 IPS LCD (135×240, SPI)
- Native USB-OTG on GPIO19/20

### Pin Map

```
LCD MOSI   GPIO11      USB D+     GPIO20
LCD SCLK   GPIO12      USB D-     GPIO19
LCD CS     GPIO10      BOOT btn   GPIO0
LCD DC     GPIO8       RGB LED    GPIO38
LCD RST    GPIO9
LCD BL     GPIO7
```

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
│  Arduino 3.x API   +   ESP-IDF 5.5 (lwIP,     │
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
- **`display.cpp`** — Drives the ST7789 LCD via LovyanGFX with a full-screen sprite buffer for flicker-free updates. Shows SSID, password, AP IP, USB status, NAT state, and a scrolling client list.
- **`webserver.cpp`** — Minimal HTTP server (raw `WiFiServer`) serving an embedded HTML/CSS config page. Handles form POST to save settings to NVS and reboot.
- **`config.cpp`** — Reads/writes AP configuration (SSID, password, IP, DHCP range) to ESP32 NVS flash using the Arduino `Preferences` library.
- **`LGFX_Config.h`** — LovyanGFX hardware descriptor for the Waveshare ESP32-S3-GEEK's SPI bus, ST7789 panel geometry/offsets, and PWM backlight.

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

These patches are applied to the managed component at build time and don't modify tracked source files.

## Build & Flash

Requires [PlatformIO](https://platformio.org/) (CLI or VS Code extension).

```bash
# Build
pio run

# Flash (see note below about boot mode)
pio run -t upload

# Full clean rebuild (needed after sdkconfig changes)
pio run -t clean && pio run
```

### Entering Bootloader Mode

Since the firmware uses USB-OTG for NCM networking (not USB-Serial), the
automatic upload reset circuit is unavailable. To flash:

1. Hold the **BOOT** button on the dongle
2. Plug the dongle into USB (or press **RST** if already plugged in)
3. Release **BOOT**
4. Run `pio run -t upload`

After flashing, unplug and re-plug the dongle to boot normally.

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
├── main.cpp          Setup + main loop (init, periodic display refresh)
├── config.cpp/h      NVS config storage with defaults
├── wifi_ap.cpp/h     SoftAP init, client tracking via DHCP lease table
├── display.cpp/h     ST7789 LCD rendering (LovyanGFX, sprite buffer)
├── webserver.cpp/h   HTTP config interface (embedded HTML/CSS)
├── usb_net.cpp/h     USB NCM tethering (TinyUSB + custom esp_netif)
├── nat.cpp/h         NAT/NAPT (lwIP ip_napt_enable)
├── sysmon.h          CPU utilization + memory usage monitoring
├── LGFX_Config.h     LovyanGFX hardware config for ESP32-S3-GEEK
└── idf_component.yml ESP-IDF managed component deps (esp_tinyusb)

patch_ncm_cmake.py    Build-time NCM driver patches for macOS
patch_tinyusb.py      PlatformIO pre-build hook (delegates to CMake patch)
platformio.ini        PlatformIO build configuration
sdkconfig.defaults    ESP-IDF Kconfig overrides
partitions_16MB.csv   Custom partition table (16 MB flash)

docs/                 Technical spec, diagrams (SVG)
hardware/             KiCad schematic + PCB for AirBridge Pro (next-gen)
```

## License

MIT
