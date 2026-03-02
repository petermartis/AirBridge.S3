//
// AirBridge.S3 — Portable WiFi Access Point
// Hardware: Waveshare ESP32-S3-GEEK (1.14" ST7789 LCD)
//
// Features:
//   - WiFi AP with configurable SSID/password
//   - USB NCM tethering for internet via host PC
//   - WiFi repeater (STA uplink to upstream network)
//   - NAT/NAPT between uplink(s) and WiFi clients
//   - Status display with CPU/memory monitoring
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

// Track previous uplink states for NAT enable/disable
static bool g_prev_has_uplink = false;

// Display refresh interval (ms)
static const unsigned long DISPLAY_INTERVAL = 2000;
static unsigned long g_last_display = 0;

void setup() {
    // 1. Display init (LovyanGFX handles backlight on GPIO 7)
    display_init();
    display_boot_screen();

    // 2. Config + WiFi AP (uses AP+STA mode if repeater is on)
    config_load(g_cfg);
    wifi_ap_init(g_cfg);

    // 3. Start STA uplink if repeater is enabled
    if (g_cfg.repeater_on) {
        wifi_sta_start(g_cfg.uplink_ssid, g_cfg.uplink_pass);
    }

    // 4. USB NCM + web server
    usb_net_init();
    webserver_init(g_cfg);

    // 5. Initial display update
    delay(500);
    g_client_count = wifi_ap_get_clients(g_clients, 10);
    display_update(g_cfg, usb_net_is_online(),
                   wifi_sta_is_connected(), wifi_sta_rssi(),
                   g_clients, g_client_count);
}

void loop() {
    webserver_handle();
    usb_net_loop();

    unsigned long now = millis();
    if (now - g_last_display >= DISPLAY_INTERVAL) {
        g_last_display = now;
        g_client_count = wifi_ap_get_clients(g_clients, 10);

        // Check if any uplink is online (USB or STA)
        bool usb_online = usb_net_is_online();
        bool sta_online = wifi_sta_is_connected();
        bool has_uplink = usb_online || sta_online;

        // Enable/disable NAT when uplink state changes
        if (has_uplink && !g_prev_has_uplink) nat_enable();
        else if (!has_uplink && g_prev_has_uplink) nat_disable();
        g_prev_has_uplink = has_uplink;

        display_update(g_cfg, usb_online,
                       sta_online, wifi_sta_rssi(),
                       g_clients, g_client_count);
    }
    delay(1);
}
