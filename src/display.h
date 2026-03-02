#pragma once
#include <Arduino.h>
#include "config.h"
#include "wifi_ap.h"

// Initialize the ST7789 display (portrait mode)
void display_init();

// Show boot splash screen
void display_boot_screen();

// Full UI redraw: SSID, password, USB status, client list
void display_update(const APConfig &cfg, bool usb_online,
                    ClientInfo *clients, int client_count);
