#include "display.h"
#include "LGFX_Config.h"
#include "usb_net.h"
#include "nat.h"

static LGFX tft;
static LGFX_Sprite sprite(&tft);

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
    tft.setRotation(2);  // portrait flipped 180°
    tft.fillScreen(COL_BG);
    tft.setBrightness(255);  // backlight on (managed by LovyanGFX Light_PWM)

    // Create full-screen sprite for flicker-free updates
    sprite.setColorDepth(16);
    sprite.createSprite(SCREEN_W, SCREEN_H);
}

void display_boot_screen() {
    tft.fillScreen(COL_BG);
    tft.setTextColor(COL_HEADER_FG, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    tft.drawString("AirBridge.S3", SCREEN_W / 2, SCREEN_H / 2 - 20);
    tft.setTextFont(2);
    tft.drawString("Booting...", SCREEN_W / 2, SCREEN_H / 2 + 15);
}

static void draw_separator(LGFX_Sprite &s, int y) {
    s.drawFastHLine(0, y, SCREEN_W, COL_SEP);
}

void display_update(const APConfig &cfg, bool usb_online,
                    ClientInfo *clients, int client_count)
{
    // Draw to off-screen sprite, then push in one shot (no flicker)
    sprite.fillScreen(COL_BG);
    int y = 0;

    // ---- Header bar ----
    sprite.fillRect(0, y, SCREEN_W, 22, COL_HEADER_BG);
    sprite.setTextColor(COL_HEADER_FG, COL_HEADER_BG);
    sprite.setTextDatum(MC_DATUM);
    sprite.setTextFont(2);
    sprite.drawString("AirBridge.S3", SCREEN_W / 2, y + 11);
    y += 24;

    // ---- SSID ----
    sprite.setTextDatum(TL_DATUM);
    sprite.setTextFont(1);  // 6x8 GLCD font
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("SSID:", 2, y);
    y += 10;
    sprite.setTextColor(COL_VALUE, COL_BG);
    sprite.setTextFont(2);  // 16px font for the value
    sprite.drawString(cfg.ssid, 2, y);
    y += 18;

    // ---- Password ----
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("Password:", 2, y);
    y += 10;
    sprite.setTextColor(COL_PASS, COL_BG);
    sprite.setTextFont(2);
    sprite.drawString(cfg.password, 2, y);
    y += 18;

    // ---- IP Address ----
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("IP:", 2, y);
    y += 10;
    sprite.setTextColor(COL_VALUE, COL_BG);
    sprite.setTextFont(1);
    sprite.drawString(config_ip_str(cfg.ip), 2, y);
    y += 10;

    draw_separator(sprite, y + 1);
    y += 4;

    // ---- USB Status ----
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("USB:", 2, y);
    if (usb_online) {
        sprite.setTextColor(COL_USB_ON, COL_BG);
        sprite.drawString("Online (NAT)", 28, y);
    } else {
        sprite.setTextColor(COL_USB_OFF, COL_BG);
        sprite.drawString("Offline", 28, y);
    }
    y += 12;

    draw_separator(sprite, y + 1);
    y += 4;

    // ---- Connected Clients header ----
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    {
        char hdr[32];
        snprintf(hdr, sizeof(hdr), "Clients (%d):", client_count);
        sprite.drawString(hdr, 2, y);
    }
    y += 12;

    // ---- Debug: USB/NAT status ----
    draw_separator(sprite, y + 1);
    y += 4;
    sprite.setTextFont(1);
    sprite.setTextColor(0x7BEF, COL_BG);  // light gray
    sprite.drawString(usb_net_status_msg(), 2, y);
    y += 10;
    if (nat_is_active()) {
        sprite.setTextColor(COL_USB_ON, COL_BG);
        sprite.drawString("NAT: active", 2, y);
    } else {
        sprite.setTextColor(COL_USB_OFF, COL_BG);
        sprite.drawString("NAT: off", 2, y);
    }
    y += 12;
    draw_separator(sprite, y + 1);
    y += 4;

    if (client_count == 0) {
        sprite.setTextColor(COL_NOCONN, COL_BG);
        sprite.drawString("No devices", 2, y);
    } else {
        // ---- Client list ----
        sprite.setTextFont(1);
        for (int i = 0; i < client_count && y < (SCREEN_H - 16); i++) {
            sprite.setTextColor(COL_IP, COL_BG);
            char ip_str[16];
            snprintf(ip_str, sizeof(ip_str), "%d.%d.%d.%d",
                clients[i].ip[0], clients[i].ip[1],
                clients[i].ip[2], clients[i].ip[3]);
            sprite.drawString(ip_str, 4, y);
            y += 10;

            sprite.setTextColor(COL_HOST, COL_BG);
            String host = clients[i].hostname;
            if (host.length() > 22) host = host.substring(0, 22);
            sprite.drawString(host, 8, y);
            y += 12;
        }
    }

    // Push entire frame to display at once
    sprite.pushSprite(0, 0);
}
