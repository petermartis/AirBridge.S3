#include "usb_net.h"

//
// USB NCM Network Device
//
// The Arduino ESP32 core bundles TinyUSB headers but the pre-built
// SDK library does NOT enable CFG_TUD_NCM. Full USB NCM networking
// requires ESP-IDF framework with the esp_tinyusb managed component.
//
// This file provides a graceful stub so the rest of the firmware
// compiles and runs — WiFi AP works standalone without USB tethering.
// When USB NCM becomes available (ESP-IDF build), the full
// implementation path activates automatically.
//

#include <esp_event.h>
#include <esp_netif.h>

static bool s_warned = false;

void usb_net_init() {
    Serial.println("[USB] USB NCM tethering module loaded.");
    Serial.println("[USB] Note: USB NCM requires ESP-IDF framework with esp_tinyusb component.");
    Serial.println("[USB] WiFi AP works standalone. USB tethering disabled in Arduino build.");
}

bool usb_net_is_online() {
    return false;
}

void usb_net_loop() {
    // No-op in Arduino build
}
