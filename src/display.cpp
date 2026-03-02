#include "display.h"
#include <TFT_eSPI.h>

static TFT_eSPI tft = TFT_eSPI();

// Portrait: 135 wide x 240 tall
static const int SCREEN_W = 135;
static const int SCREEN_H = 240;

// Colors
static const uint16_t COL_BG        = TFT_BLACK;
static const uint16_t COL_HEADER_BG = 0x1A3F;  // dark blue
static const uint16_t COL_HEADER_FG = TFT_WHITE;
static const uint16_t COL_LABEL     = TFT_CYAN;
static const uint16_t COL_VALUE     = TFT_WHITE;
static const uint16_t COL_PASS      = TFT_GREEN;
static const uint16_t COL_USB_ON    = TFT_GREEN;
static const uint16_t COL_USB_OFF   = TFT_RED;
static const uint16_t COL_SEP       = 0x4208;  // dark gray
static const uint16_t COL_IP        = TFT_YELLOW;
static const uint16_t COL_HOST      = 0x7BEF;  // light gray
static const uint16_t COL_NOCONN   = 0x4208;  // dim

void display_init() {
    tft.init();
    tft.setRotation(2);  // portrait flipped 180° (up-side down)
    tft.fillScreen(COL_BG);

    // Turn on backlight
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, TFT_BACKLIGHT_ON);
}

void display_boot_screen() {
    tft.fillScreen(COL_BG);
    tft.setTextColor(COL_HEADER_FG, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    tft.drawString("WiFi AP", SCREEN_W / 2, SCREEN_H / 2 - 20);
    tft.setTextFont(2);
    tft.drawString("Booting...", SCREEN_W / 2, SCREEN_H / 2 + 15);
}

static void draw_separator(int y) {
    tft.drawFastHLine(0, y, SCREEN_W, COL_SEP);
}

void display_update(const APConfig &cfg, bool usb_online,
                    ClientInfo *clients, int client_count)
{
    tft.fillScreen(COL_BG);
    int y = 0;

    // ---- Header bar ----
    tft.fillRect(0, y, SCREEN_W, 22, COL_HEADER_BG);
    tft.setTextColor(COL_HEADER_FG, COL_HEADER_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString("WiFi AP", SCREEN_W / 2, y + 11);
    y += 24;

    // ---- SSID ----
    tft.setTextDatum(TL_DATUM);
    tft.setTextFont(1);  // 6x8 GLCD font
    tft.setTextColor(COL_LABEL, COL_BG);
    tft.drawString("SSID:", 2, y);
    y += 10;
    tft.setTextColor(COL_VALUE, COL_BG);
    tft.setTextFont(2);  // 16px font for the value
    tft.drawString(cfg.ssid, 2, y);
    y += 18;

    // ---- Password ----
    tft.setTextFont(1);
    tft.setTextColor(COL_LABEL, COL_BG);
    tft.drawString("Password:", 2, y);
    y += 10;
    tft.setTextColor(COL_PASS, COL_BG);
    tft.setTextFont(2);
    tft.drawString(cfg.password, 2, y);
    y += 18;

    // ---- IP Address ----
    tft.setTextFont(1);
    tft.setTextColor(COL_LABEL, COL_BG);
    tft.drawString("IP:", 2, y);
    y += 10;
    tft.setTextColor(COL_VALUE, COL_BG);
    tft.setTextFont(1);
    tft.drawString(config_ip_str(cfg.ip), 2, y);
    y += 10;

    draw_separator(y + 1);
    y += 4;

    // ---- USB Status ----
    tft.setTextFont(1);
    tft.setTextColor(COL_LABEL, COL_BG);
    tft.drawString("USB:", 2, y);
    if (usb_online) {
        tft.setTextColor(COL_USB_ON, COL_BG);
        tft.drawString("Online (NAT)", 28, y);
    } else {
        tft.setTextColor(COL_USB_OFF, COL_BG);
        tft.drawString("Offline", 28, y);
    }
    y += 12;

    draw_separator(y + 1);
    y += 4;

    // ---- Connected Clients header ----
    tft.setTextFont(1);
    tft.setTextColor(COL_LABEL, COL_BG);
    {
        char hdr[32];
        snprintf(hdr, sizeof(hdr), "Clients (%d):", client_count);
        tft.drawString(hdr, 2, y);
    }
    y += 12;

    if (client_count == 0) {
        tft.setTextColor(COL_NOCONN, COL_BG);
        tft.drawString("No devices", 2, y);
        return;
    }

    // ---- Client list ----
    // Each client: IP line + hostname line = ~20px
    tft.setTextFont(1);  // 6x8 GLCD — fits "192.168.1.100" (13 chars * 6 = 78px) in 135px
    for (int i = 0; i < client_count && y < (SCREEN_H - 16); i++) {
        // IP address
        tft.setTextColor(COL_IP, COL_BG);
        char ip_str[16];
        snprintf(ip_str, sizeof(ip_str), "%d.%d.%d.%d",
            clients[i].ip[0], clients[i].ip[1],
            clients[i].ip[2], clients[i].ip[3]);
        tft.drawString(ip_str, 4, y);
        y += 10;

        // Hostname (truncate if too long)
        tft.setTextColor(COL_HOST, COL_BG);
        String host = clients[i].hostname;
        if (host.length() > 22) host = host.substring(0, 22);
        tft.drawString(host, 8, y);
        y += 12;
    }
}
