//
// AirBridge.S3 — Portable WiFi Access Point
// Hardware: Waveshare ESP32-S3-GEEK (1.14" ST7789 LCD)
//           or ESP32-S31 + external 1.8" ST7735 TFT (see platformio.ini)
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
#include <esp_rom_sys.h>

#include "config.h"
#include "wifi_ap.h"
#include "display.h"
#include "webserver.h"
#include "usb_net.h"
#include "nat.h"

// Temporary bring-up diagnostic: bisecting a silent hang somewhere in
// setup() on real S31 hardware (no crash, no further output after
// config_load()'s Preferences warnings) by checkpointing each major
// init call. Draws to the physical screen (not just ESP_LOGI) because
// the USB console has proven unreliable during this early boot window
// -- output printed before native-USB enumeration finishes can be
// silently dropped, which is suspected to be why no checkpoint has
// shown up there yet even though the display itself is confirmed
// working (display_test). The screen isn't subject to that at all.
// Remove once the real hang/crash is found and fixed.
static const char *TAG_BOOT = "boot";
#define BOOT_STEP(msg) do { ESP_LOGI(TAG_BOOT, msg); display_debug_step(msg); } while (0)

static APConfig g_cfg;
static ClientInfo g_clients[10];
static int g_client_count = 0;

// Track previous uplink states for NAT enable/disable
static bool g_prev_has_uplink = false;

// Display refresh interval (ms)
static const unsigned long DISPLAY_INTERVAL = 2000;
static unsigned long g_last_display = 0;

void setup() {
    // 0. Check reset reason (helps diagnose USB crash)
    esp_reset_reason_t rst = esp_reset_reason();
    // Will display after screen init

    // 1. Display init (LovyanGFX handles backlight on GPIO 7)
    // (not using BOOT_STEP here -- the screen isn't ready to draw to
    // until display_init() itself has run; ESP_LOGI only for this one)
    ESP_LOGI(TAG_BOOT, "display_init...");
    display_init();
    BOOT_STEP("display_init OK");
    if (rst != ESP_RST_POWERON && rst != ESP_RST_DEEPSLEEP) {
        // Show reset reason briefly — helps diagnose crashes
        // 3=SW_RESET, 4=PANIC, 5=INT_WDT, 6=TASK_WDT, 9=BROWNOUT
        display_boot_msg(rst);
        delay(2000);
    }
    display_boot_screen();
    BOOT_STEP("display_boot_screen OK");

    // 2. Config + WiFi AP (uses AP+STA mode if repeater is on)
    config_load(g_cfg);
    BOOT_STEP("config_load OK");
    wifi_ap_init(g_cfg);
    BOOT_STEP("wifi_ap_init OK");

    // 3. Start STA uplink if repeater is enabled
    if (g_cfg.repeater_on) {
        wifi_sta_start(g_cfg.uplink_ssid, g_cfg.uplink_pass);
        BOOT_STEP("wifi_sta_start OK");
    }

    // 4. USB NCM + web server
    usb_net_init();
    BOOT_STEP("usb_net_init OK");
    webserver_init(g_cfg);
    BOOT_STEP("webserver_init OK");

    // 5. Initial display update
    delay(500);
    g_client_count = wifi_ap_get_clients(g_clients, 10);
    display_update(g_cfg, usb_net_is_online(),
                   wifi_sta_is_connected(), wifi_sta_rssi(),
                   g_clients, g_client_count);
    BOOT_STEP("setup() complete");
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

        // WiFi clients need a real DNS server to resolve names through the
        // uplink; otherwise the AP advertises itself and nothing answers.
        if (has_uplink) {
            uint32_t dns = usb_online ? usb_net_dns_addr() : 0;
            if (dns == 0 && sta_online) dns = wifi_sta_dns_addr();
            wifi_ap_set_client_dns(dns);
        }

        display_update(g_cfg, usb_online,
                       sta_online, wifi_sta_rssi(),
                       g_clients, g_client_count);
    }
    delay(1);
}
