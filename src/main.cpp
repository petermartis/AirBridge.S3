//
// AirBridge.S3 — Portable WiFi Access Point
// Hardware: Waveshare ESP32-S3-GEEK (1.14" ST7789 LCD)
//
// Features:
//   - WiFi AP with configurable SSID/password
//   - USB NCM tethering for internet via host PC
//   - NAT/NAPT between USB uplink and WiFi clients
//   - Status display (SSID, password, USB/NAT state, clients)
//   - Web configuration UI
//

#include <Arduino.h>
#include <esp_system.h>

#include "config.h"
#include "wifi_ap.h"
#include "display.h"
#include "webserver.h"
#include "usb_net.h"
#include "nat.h"

static APConfig g_cfg;
static ClientInfo g_clients[10];
static int g_client_count = 0;
static bool g_prev_usb_online = false;

// Display refresh interval (ms)
static const unsigned long DISPLAY_INTERVAL = 2000;
static unsigned long g_last_display = 0;

void setup() {
    // 1. Display init (LovyanGFX handles backlight on GPIO 7)
    display_init();
    display_boot_screen();

    // 2. Config + WiFi AP
    config_load(g_cfg);
    wifi_ap_init(g_cfg);
    usb_net_init();
    webserver_init(g_cfg);

    // 3. Initial display update
    delay(500);
    g_client_count = wifi_ap_get_clients(g_clients, 10);
    display_update(g_cfg, usb_net_is_online(), g_clients, g_client_count);

}

void loop() {
    webserver_handle();
    usb_net_loop();

    unsigned long now = millis();
    if (now - g_last_display >= DISPLAY_INTERVAL) {
        g_last_display = now;
        g_client_count = wifi_ap_get_clients(g_clients, 10);
        bool usb_online = usb_net_is_online();
        if (usb_online && !g_prev_usb_online) nat_enable();
        else if (!usb_online && g_prev_usb_online) nat_disable();
        g_prev_usb_online = usb_online;
        display_update(g_cfg, usb_online, g_clients, g_client_count);
    }
    delay(1);
}
