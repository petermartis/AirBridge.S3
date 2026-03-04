#pragma once
#include <Arduino.h>
#include "config.h"
#include "wifi_ap.h"

// Initialize the ST7789 display (portrait mode)
void display_init();

// Show boot splash screen
void display_boot_screen();

// Show reset reason (for crash diagnostics)
void display_boot_msg(int reason);

// Full UI redraw: SSID, password, uplink status, client list, system stats
void display_update(const APConfig &cfg, bool usb_online,
                    bool sta_connected, int sta_rssi,
                    ClientInfo *clients, int client_count);
