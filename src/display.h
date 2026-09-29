#pragma once
#include <Arduino.h>
#include "config.h"
#include "wifi_ap.h"

// Initialize the LCD (implementation + panel driver depend on the build
// env: display_s3geek.cpp/ST7789 for esp32s3geek, display_s31.cpp/ST7735
// for esp32s31 — see platformio.ini's build_src_filter per env)
void display_init();

// Show boot splash screen
void display_boot_screen();

// Show reset reason (for crash diagnostics)
void display_boot_msg(int reason);

// Full UI redraw: SSID, password, uplink status, client list, system stats
void display_update(const APConfig &cfg, bool usb_online,
                    bool sta_connected, int sta_rssi,
                    ClientInfo *clients, int client_count);
