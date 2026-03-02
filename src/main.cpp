//
// ESP32-S3-GEEK Portable WiFi Access Point
// Waveshare ESP32-S3-GEEK with 1.14" ST7789 LCD
//
// Features:
//   - WiFi AP with configurable SSID/password
//   - DHCP server (192.168.1.2 - 192.168.1.255)
//   - USB NCM tethering for internet via host PC
//   - NAT/NAPT between USB and WiFi
//   - 1.14" display showing SSID, password, connected clients
//   - Web config UI at http://<device-ip>/
//

#include <Arduino.h>
#include <esp_system.h>

#include "config.h"
#include "wifi_ap.h"
#include "display.h"
#include "webserver.h"
#include "usb_net.h"
#include "nat.h"

static const char* reset_reason_str(esp_reset_reason_t r) {
    switch (r) {
        case ESP_RST_POWERON:   return "POWERON";
        case ESP_RST_EXT:       return "EXT";
        case ESP_RST_SW:        return "SW";
        case ESP_RST_PANIC:     return "PANIC";
        case ESP_RST_INT_WDT:   return "INT_WDT";
        case ESP_RST_TASK_WDT:  return "TASK_WDT";
        case ESP_RST_WDT:       return "WDT";
        case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
        case ESP_RST_BROWNOUT:  return "BROWNOUT";
        case ESP_RST_SDIO:      return "SDIO";
        default:                return "OTHER";
    }
}

static APConfig g_cfg;
static ClientInfo g_clients[10];
static int g_client_count = 0;
static bool g_prev_usb_online = false;

// Display refresh interval (ms)
static const unsigned long DISPLAY_INTERVAL = 2000;
static unsigned long g_last_display = 0;

void setup() {
    // Serial for debug (over UART0 since USB is used for NCM)
    Serial.begin(115200);
    delay(500);
    Serial.println("\n========================================");
    Serial.println("  ESP32-S3-GEEK WiFi AP");
    Serial.println("========================================");

    esp_reset_reason_t rr = esp_reset_reason();
    Serial.printf("[Boot] Reset reason: %d (%s)\n", (int)rr, reset_reason_str(rr));

    // 1. Init display first — show boot screen
    display_init();
    display_boot_screen();

    // 2. Load config from NVS (or defaults)
    config_load(g_cfg);
    Serial.printf("[Config] SSID=%s IP=%s DHCP=%d-%d\n",
        g_cfg.ssid.c_str(),
        config_ip_str(g_cfg.ip).c_str(),
        g_cfg.dhcp_start, g_cfg.dhcp_end);

    // 3. Start WiFi AP
    wifi_ap_init(g_cfg);

    // 4. Start USB NCM tethering
    usb_net_init();

    // 5. Start web config server
    webserver_init(g_cfg);

    // 6. Initial display update
    delay(500);
    g_client_count = wifi_ap_get_clients(g_clients, 10);
    display_update(g_cfg, usb_net_is_online(), g_clients, g_client_count);

    Serial.println("[Main] Ready!");
}

void loop() {
    // Handle web server requests
    webserver_handle();

    // Process USB network events
    usb_net_loop();

    // Periodically update display and manage NAT
    unsigned long now = millis();
    if (now - g_last_display >= DISPLAY_INTERVAL) {
        g_last_display = now;

        // Refresh client list
        g_client_count = wifi_ap_get_clients(g_clients, 10);

        // Check USB tethering status
        bool usb_online = usb_net_is_online();

        // Enable/disable NAT based on USB link state
        if (usb_online && !g_prev_usb_online) {
            // USB just came online — enable NAT
            nat_enable();
        } else if (!usb_online && g_prev_usb_online) {
            // USB went offline — disable NAT
            nat_disable();
        }
        g_prev_usb_online = usb_online;

        // Update display
        display_update(g_cfg, usb_online, g_clients, g_client_count);
    }

    // Give background tasks time (helps avoid watchdog resets under load)
    delay(1);
}
