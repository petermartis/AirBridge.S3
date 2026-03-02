# ESP32-S3-GEEK Portable WiFi Access Point

Firmware for the **Waveshare ESP32-S3-GEEK** USB dongle that turns it into a
portable WiFi access point with a color status display and web configuration.

## Features

- **WiFi AP** — WPA2 access point with configurable SSID and password
- **DHCP Server** — Automatic IP assignment for connected clients
- **1.14" LCD** — Shows SSID, password, IP address, USB status, and
  connected clients with MAC addresses
- **Web Config** — Browser UI at `http://<device-ip>/` to change
  SSID, password, IP address, and DHCP range

### Planned

- **USB Tethering** — USB NCM network device for sharing a host PC's internet
- **NAT/NAPT** — Automatic routing between USB uplink and WiFi clients

## Hardware

- [Waveshare ESP32-S3-GEEK](https://www.waveshare.com/wiki/ESP32-S3-GEEK) (ESP32-S3R2, 16 MB Flash, 2 MB PSRAM)
- 1.14" ST7789 IPS LCD (240×135, SPI)
- USB-A male connector (native USB on GPIO19/20)

## Build

Requires [PlatformIO](https://platformio.org/).

```bash
# Build
pio run

# Upload (hold BOOT, plug in, release BOOT)
pio run -t upload

# Serial monitor (UART0 — needs USB-to-serial adapter)
pio device monitor
```

## Default Settings

- **SSID**: `PM_Travel`
- **Password**: `Adames007`
- **IP Address**: `192.168.1.1`
- **Subnet**: `255.255.255.0`
- **DHCP Range**: `.2` – `.255`

## Web Configuration

Connect to the WiFi AP and open `http://192.168.1.1/` (or your configured IP).
Change any setting and click **Save & Reboot**. The device restarts with the
new configuration.

## Pin Map

```
LCD MOSI   GPIO11      USB D+     GPIO20
LCD SCLK   GPIO12      USB D-     GPIO19
LCD CS     GPIO10      BOOT btn   GPIO0
LCD DC     GPIO8       RGB LED    GPIO38
LCD RST    GPIO9
LCD BL     GPIO7
```

## Project Structure

```
src/
├── main.cpp        — Setup + main loop
├── config.cpp/h    — NVS config storage with defaults
├── wifi_ap.cpp/h   — SoftAP init, client tracking
├── display.cpp/h   — ST7789 UI rendering
├── webserver.cpp/h — HTTP config interface
├── usb_net.cpp/h   — USB NCM tethering (stub)
└── nat.cpp/h       — NAT/NAPT (stub)
```

## License

MIT
