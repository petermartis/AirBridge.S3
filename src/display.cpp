#include "display.h"
#include "LGFX_Config.h"
#include "usb_net.h"
#include "nat.h"
#include "sysmon.h"

static LGFX tft;
static LGFX_Sprite sprite(&tft);

// Landscape: 240 wide x 135 tall
static const int W = 240;
static const int H = 135;

// Colors
static const uint16_t COL_BG        = TFT_BLACK;
static const uint16_t COL_HEADER_BG = 0x1A3F;  // dark blue
static const uint16_t COL_HEADER_FG = TFT_WHITE;
static const uint16_t COL_LABEL     = TFT_CYAN;
static const uint16_t COL_VALUE     = TFT_WHITE;
static const uint16_t COL_PASS      = TFT_GREEN;
static const uint16_t COL_ON        = TFT_GREEN;
static const uint16_t COL_OFF       = TFT_RED;
static const uint16_t COL_SEP       = 0x4208;  // dark gray
static const uint16_t COL_IP        = TFT_YELLOW;
static const uint16_t COL_MAC       = 0x7BEF;  // light gray
static const uint16_t COL_DIM       = 0x4208;

// 3-column X positions (80px each)
static const int C1 = 2;
static const int C2 = 82;
static const int C3 = 162;

void display_init() {
    tft.init();
    tft.setRotation(1);  // landscape 240x135
    tft.fillScreen(COL_BG);
    tft.setBrightness(255);

    sprite.setColorDepth(16);
    sprite.createSprite(W, H);
}

void display_boot_screen() {
    tft.fillScreen(COL_BG);
    tft.setTextColor(COL_HEADER_FG, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    tft.drawString("AirBridge.S3", W / 2, H / 2 - 10);
    tft.setTextFont(2);
    tft.drawString("Booting...", W / 2, H / 2 + 20);
}

void display_boot_msg(int reason) {
    // 3=SW_RESET 4=PANIC 5=INT_WDT 6=TASK_WDT 9=BROWNOUT
    const char *names[] = {"?","VBAT","EXT","SW","PANIC","IWDT","TWDT","WDT","DSLP","BROWN","SDIO","USB"};
    const char *name = (reason >= 0 && reason <= 11) ? names[reason] : "?";
    tft.fillScreen(COL_BG);
    tft.setTextColor(TFT_RED, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    char buf[32];
    snprintf(buf, sizeof(buf), "RST:%d %s", reason, name);
    tft.drawString(buf, W / 2, H / 2);
}

void display_update(const APConfig &cfg, bool usb_online,
                    bool sta_connected, int sta_rssi,
                    ClientInfo *clients, int client_count)
{
    sprite.fillScreen(COL_BG);
    int y = 0;

    // ---- Title bar (optional, centered content) ----
    if (cfg.show_title) {
        sprite.fillRect(0, 0, W, 14, COL_HEADER_BG);
        sprite.setTextColor(COL_HEADER_FG, COL_HEADER_BG);
        sprite.setTextDatum(MC_DATUM);
        sprite.setTextFont(1);

        String title = "AirBridge.S3";
        if (cfg.show_cpu) title += "  CPU:" + String(sysmon_cpu_percent()) + "%";
        if (cfg.show_mem) title += "  MEM:" + String(sysmon_mem_percent()) + "%";
        sprite.drawString(title, W / 2, 7);
        y = 16;
    } else {
        // Even without title, show CPU/MEM if enabled (in a slim bar)
        if (cfg.show_cpu || cfg.show_mem) {
            sprite.fillRect(0, 0, W, 10, COL_HEADER_BG);
            sprite.setTextColor(COL_MAC, COL_HEADER_BG);
            sprite.setTextDatum(MC_DATUM);
            sprite.setTextFont(1);
            String stats = "";
            if (cfg.show_cpu) stats += "CPU:" + String(sysmon_cpu_percent()) + "%";
            if (cfg.show_cpu && cfg.show_mem) stats += "  ";
            if (cfg.show_mem) stats += "MEM:" + String(sysmon_mem_percent()) + "%";
            sprite.drawString(stats, W / 2, 5);
            y = 12;
        } else {
            y = 1;
        }
    }

    // ---- SSID / Password / IP  (3 columns: label + value) ----
    sprite.setTextDatum(TL_DATUM);
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("SSID:", C1, y);
    sprite.drawString("Pass:", C2, y);
    sprite.drawString("IP:",   C3, y);
    y += 9;

    sprite.setTextFont(2);
    sprite.setTextColor(COL_VALUE, COL_BG);
    sprite.drawString(cfg.ssid, C1, y);
    sprite.setTextColor(COL_PASS, COL_BG);
    sprite.drawString(cfg.password, C2, y);
    sprite.setTextColor(COL_VALUE, COL_BG);
    sprite.drawString(config_ip_str(cfg.ip), C3, y);
    y += 18;

    sprite.drawFastHLine(0, y, W, COL_SEP);
    y += 2;

    // ---- USB / STA / NAT  (3 columns, font 2) ----
    sprite.setTextFont(2);

    // USB (show debug status when offline)
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("USB:", C1, y);
    if (usb_online) {
        sprite.setTextColor(COL_ON, COL_BG);
        sprite.drawString("On", C1 + 36, y);
    } else {
        sprite.setTextColor(COL_OFF, COL_BG);
        sprite.setTextFont(1);
        sprite.drawString(usb_net_status_msg(), C1 + 30, y + 2);
        sprite.setTextFont(2);
    }

    // STA
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("STA:", C2, y);
    if (sta_connected) {
        sprite.setTextColor(COL_ON, COL_BG);
        char rssi[10];
        snprintf(rssi, sizeof(rssi), "%ddB", sta_rssi);
        sprite.drawString(rssi, C2 + 36, y);
    } else if (cfg.repeater_on) {
        sprite.setTextColor(COL_OFF, COL_BG);
        sprite.drawString("...", C2 + 36, y);
    } else {
        sprite.setTextColor(COL_DIM, COL_BG);
        sprite.drawString("Off", C2 + 36, y);
    }

    // NAT
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("NAT:", C3, y);
    sprite.setTextColor(nat_is_active() ? COL_ON : COL_OFF, COL_BG);
    sprite.drawString(nat_is_active() ? "On" : "Off", C3 + 36, y);
    y += 18;

    sprite.drawFastHLine(0, y, W, COL_SEP);
    y += 2;

    // ---- Clients header ----
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    {
        char hdr[24];
        snprintf(hdr, sizeof(hdr), "Clients (%d):", client_count);
        sprite.drawString(hdr, C1, y);
    }
    y += 10;

    // ---- Client grid (2 columns, vertical divider) ----
    int mid = W / 2;
    if (client_count > 0) {
        sprite.drawFastVLine(mid, y, H - y, COL_SEP);
    }
    sprite.setTextFont(1);

    for (int i = 0; i < client_count; i++) {
        int col = i % 2;            // 0=left, 1=right
        int row = i / 2;
        int cy  = y + row * 10;
        if (cy >= H - 2) break;     // no more vertical space

        int cx = (col == 0) ? C1 : mid + 3;

        // Format: ".{last_octet} {MAC_no_colons}"
        char ip_part[8];
        snprintf(ip_part, sizeof(ip_part), ".%d ", clients[i].ip[3]);

        // IP part (yellow)
        sprite.setTextColor(COL_IP, COL_BG);
        sprite.drawString(ip_part, cx, cy);
        int ip_w = sprite.textWidth(ip_part);

        // MAC part (gray, no colons to fit in column)
        char mac[13];
        snprintf(mac, sizeof(mac), "%02X%02X%02X%02X%02X%02X",
            clients[i].mac[0], clients[i].mac[1], clients[i].mac[2],
            clients[i].mac[3], clients[i].mac[4], clients[i].mac[5]);
        sprite.setTextColor(COL_MAC, COL_BG);
        sprite.drawString(mac, cx + ip_w, cy);
    }

    if (client_count == 0) {
        sprite.setTextColor(COL_DIM, COL_BG);
        sprite.drawString("No devices", C1, y);
    }

    sprite.pushSprite(0, 0);
}
