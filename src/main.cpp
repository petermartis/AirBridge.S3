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
// setup() on real S31 hardware. Real root cause of why no checkpoint
// was ever showing up in the console, found on real hardware: this
// board's configured log level filters out ESP_LOGI entirely --
// Arduino's own Preferences.cpp errors were only ever visible because
// they go through a different, always-on logging path (Arduino's
// log_e()), not because anything of ours was failing to run. Fixed by
// using ESP_LOGE here instead, which Preferences' own errors already
// proved gets through. Also still drawing to the screen and setting
// the onboard RGB LED to a distinct color per step, in case the
// console turns out to still be lossy for an unrelated reason -- the
// LED doesn't depend on SPI2_HOST at all, so it stays trustworthy even
// if the bus itself turns out to be the thing that's broken. Remove
// once the real hang/crash is found and fixed.
static const char *TAG_BOOT = "boot";
#define BOOT_STEP(msg) do { ESP_LOGE(TAG_BOOT, msg); display_debug_step(msg); } while (0)

#ifdef RGB_BUILTIN
#define LED_STEP(r, g, b) rgbLedWrite(RGB_BUILTIN, r, g, b)
#else
#define LED_STEP(r, g, b) do {} while (0)
#endif

static APConfig g_cfg;
static ClientInfo g_clients[10];
static int g_client_count = 0;

// Track previous uplink states for NAT enable/disable
static bool g_prev_has_uplink = false;

// Display refresh interval (ms)
static const unsigned long DISPLAY_INTERVAL = 2000;
static unsigned long g_last_display = 0;

void setup() {
    // Self-test, before anything else at all: proves the LED mechanism
    // itself works on this exact board, independent of every subsystem
    // below. If this never blinks, the LED checkpoints after it can't
    // be trusted either -- but if even this doesn't show, that's its
    // own answer.
    LED_STEP(255, 255, 255);
    delay(200);
    LED_STEP(0, 0, 0);
    delay(200);
    LED_STEP(255, 255, 255);
    delay(200);
    LED_STEP(0, 0, 0);

    // 0. Check reset reason (helps diagnose USB crash)
    esp_reset_reason_t rst = esp_reset_reason();
    // Will display after screen init

    // 1. Display init (LovyanGFX handles backlight on GPIO 7)
    // (not using BOOT_STEP here -- the screen isn't ready to draw to
    // until display_init() itself has run)
    ESP_LOGE(TAG_BOOT, "display_init...");
    LED_STEP(0, 0, 255);  // blue
    display_init();
    BOOT_STEP("display_init OK");
    LED_STEP(0, 255, 0);  // green
    if (rst != ESP_RST_POWERON && rst != ESP_RST_DEEPSLEEP) {
        // Show reset reason briefly — helps diagnose crashes
        // 3=SW_RESET, 4=PANIC, 5=INT_WDT, 6=TASK_WDT, 9=BROWNOUT
        display_boot_msg(rst);
        delay(2000);
    }
    display_boot_screen();
    BOOT_STEP("display_boot_screen OK");
    LED_STEP(0, 255, 255);  // cyan

    // 2. Config + WiFi AP (uses AP+STA mode if repeater is on)
    config_load(g_cfg);
    BOOT_STEP("config_load OK");
    LED_STEP(255, 255, 0);  // yellow
    wifi_ap_init(g_cfg);
    BOOT_STEP("wifi_ap_init OK");
    LED_STEP(255, 0, 255);  // magenta

    // 3. Start STA uplink if repeater is enabled
    if (g_cfg.repeater_on) {
        wifi_sta_start(g_cfg.uplink_ssid, g_cfg.uplink_pass);
        BOOT_STEP("wifi_sta_start OK");
    }

    // 4. USB NCM + web server
    usb_net_init();
    BOOT_STEP("usb_net_init OK");
    LED_STEP(255, 128, 0);  // orange
    webserver_init(g_cfg);
    BOOT_STEP("webserver_init OK");
    LED_STEP(128, 0, 255);  // purple

    // 5. Initial display update
    delay(500);
    g_client_count = wifi_ap_get_clients(g_clients, 10);
    display_update(g_cfg, usb_net_is_online(),
                   wifi_sta_is_connected(), wifi_sta_rssi(),
                   g_clients, g_client_count);
    BOOT_STEP("setup() complete");
    LED_STEP(0, 0, 0);  // off: setup() reached the end successfully
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

        // Captive-portal DNS hijack must come down once a real uplink is
        // online -- left hijacking, it answers every WiFi client's DNS
        // query with this device's own IP forever, breaking internet
        // access even with NAT working.
        webserver_set_captive_portal(!has_uplink);

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
