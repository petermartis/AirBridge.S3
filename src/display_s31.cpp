#include "display.h"
#include "LGFX_Config_s31.h"
#include "usb_net.h"
#include "nat.h"
#include "sysmon.h"

static LGFX tft;
static LGFX_Sprite sprite(&tft);

// Portrait: 128 wide x 160 tall
static const int W = 128;
static const int H = 160;

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
static const uint16_t COL_BAR_BG    = 0x2104;  // very dark gray
static const uint16_t COL_DOT       = 0x4208;
static const uint16_t COL_DOT_ON    = TFT_WHITE;

// How many display_update() calls (each DISPLAY_INTERVAL, see main.cpp)
// each page stays on screen before auto-advancing.
static const int PAGE_HOLD_TICKS = 3;

enum Page { PAGE_JOIN = 0, PAGE_STATUS = 1, PAGE_CLIENTS = 2, PAGE_COUNT = 3 };

static int s_page = PAGE_JOIN;
static int s_page_hold = 0;
static int s_client_scroll = 0;

// ---- Shared header, drawn identically on every page ----
static int draw_header(const APConfig &cfg) {
    sprite.fillRect(0, 0, W, 12, COL_HEADER_BG);
    sprite.setTextDatum(MC_DATUM);
    sprite.setTextFont(1);
    sprite.setTextColor(COL_HEADER_FG, COL_HEADER_BG);

    String title = cfg.show_title ? "AirBridge" : "";
    if (cfg.show_cpu) {
        if (title.length()) title += "  ";
        title += "C:" + String(sysmon_cpu_percent()) + "%";
    }
    if (cfg.show_mem) {
        if (title.length()) title += "  ";
        title += "M:" + String(sysmon_mem_percent()) + "%";
    }
    if (title.length()) sprite.drawString(title, W / 2, 6);

    // Page indicator dots, top-right
    for (int i = 0; i < PAGE_COUNT; i++) {
        int x = W - 4 - (PAGE_COUNT - 1 - i) * 6;
        sprite.fillCircle(x, 10, 1, (i == s_page) ? COL_DOT_ON : COL_DOT);
    }
    return 13;
}

// Draws `value` right-aligned to fit within `maxWidth`, trying font4 first
// and falling back to font2 if it doesn't fit at the given x.
static void draw_autosize(const String &value, int x, int y, int maxWidth, uint16_t color) {
    sprite.setTextDatum(TL_DATUM);
    sprite.setTextColor(color, COL_BG);
    sprite.setTextFont(4);
    if (sprite.textWidth(value) <= maxWidth) {
        sprite.drawString(value, x, y);
    } else {
        sprite.setTextFont(2);
        if (sprite.textWidth(value) <= maxWidth) {
            sprite.drawString(value, x, y + 5);  // re-baseline vs font4
        } else {
            sprite.setTextFont(1);
            sprite.drawString(value, x, y + 9);
        }
    }
}

// ---- Page 1: SSID / password / IP, big and legible ----
static void draw_page_join(const APConfig &cfg, int y) {
    const int margin = 4;

    sprite.setTextDatum(TL_DATUM);
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("SSID", margin, y);
    y += 10;
    draw_autosize(cfg.ssid, margin, y, W - 2 * margin, COL_VALUE);
    y += 32;

    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("PASSWORD", margin, y);
    y += 10;
    draw_autosize(cfg.password, margin, y, W - 2 * margin, COL_PASS);
    y += 32;

    sprite.drawFastHLine(margin, y, W - 2 * margin, COL_SEP);
    y += 6;

    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("IP", margin, y);
    sprite.setTextFont(2);
    sprite.setTextColor(COL_IP, COL_BG);
    sprite.drawString(config_ip_str(cfg.ip), margin + 26, y - 4);
}

static void draw_bar(int x, int y, int w, int h, int percent, uint16_t color) {
    sprite.fillRect(x, y, w, h, COL_BAR_BG);
    int fill = (w * percent) / 100;
    if (fill > 0) sprite.fillRect(x, y, fill, h, color);
    sprite.drawRect(x, y, w, h, COL_SEP);
}

// ---- Page 2: USB / STA / NAT status + CPU/MEM gauges ----
static void draw_page_status(const APConfig &cfg, bool usb_online,
                              bool sta_connected, int sta_rssi, int y) {
    const int margin = 4;
    const int rowH = 28;

    // USB
    sprite.setTextDatum(TL_DATUM);
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("USB UPLINK", margin, y);
    sprite.setTextFont(2);
    if (usb_online) {
        sprite.setTextColor(COL_ON, COL_BG);
        sprite.drawString("Online", margin, y + 10);
    } else {
        sprite.setTextColor(COL_OFF, COL_BG);
        sprite.setTextFont(1);
        sprite.drawString(usb_net_status_msg(), margin, y + 12);
    }
    y += rowH;

    // STA (repeater uplink)
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("WIFI UPLINK", margin, y);
    sprite.setTextFont(2);
    if (sta_connected) {
        sprite.setTextColor(COL_ON, COL_BG);
        sprite.drawString(String(sta_rssi) + " dBm", margin, y + 10);
    } else if (cfg.repeater_on) {
        sprite.setTextColor(COL_OFF, COL_BG);
        sprite.drawString("Connecting...", margin, y + 10);
    } else {
        sprite.setTextColor(COL_DIM, COL_BG);
        sprite.drawString("Disabled", margin, y + 10);
    }
    y += rowH;

    // NAT
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("NAT", margin, y);
    sprite.setTextFont(2);
    sprite.setTextColor(nat_is_active() ? COL_ON : COL_OFF, COL_BG);
    sprite.drawString(nat_is_active() ? "Active" : "Inactive", margin, y + 10);
    y += rowH;

    sprite.drawFastHLine(margin, y, W - 2 * margin, COL_SEP);
    y += 8;

    // CPU / MEM gauges
    int cpu = sysmon_cpu_percent();
    int mem = sysmon_mem_percent();

    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("CPU " + String(cpu) + "%", margin, y);
    draw_bar(margin, y + 9, W - 2 * margin, 8,
             cpu, cpu > 85 ? COL_OFF : COL_ON);
    y += 22;

    sprite.setTextColor(COL_LABEL, COL_BG);
    sprite.drawString("MEM " + String(mem) + "%", margin, y);
    draw_bar(margin, y + 9, W - 2 * margin, 8,
             mem, mem > 85 ? COL_OFF : COL_ON);
}

// ---- Page 3: connected client list, scrolls if it overflows ----
static void draw_page_clients(ClientInfo *clients, int client_count, int y) {
    const int margin = 4;
    const int rowH = 16;

    sprite.setTextDatum(TL_DATUM);
    sprite.setTextFont(1);
    sprite.setTextColor(COL_LABEL, COL_BG);
    char hdr[24];
    snprintf(hdr, sizeof(hdr), "CLIENTS (%d)", client_count);
    sprite.drawString(hdr, margin, y);
    y += 12;

    if (client_count == 0) {
        sprite.setTextColor(COL_DIM, COL_BG);
        sprite.drawString("No devices connected", margin, y);
        return;
    }

    int visible_rows = (H - y) / rowH;
    if (visible_rows < 1) visible_rows = 1;

    // Advance the scroll window each time this page is drawn so every
    // client is eventually shown, even if more are connected than fit.
    if (client_count > visible_rows) {
        s_client_scroll = (s_client_scroll + 1) % client_count;
    } else {
        s_client_scroll = 0;
    }

    for (int row = 0; row < visible_rows && row < client_count; row++) {
        int i = (s_client_scroll + row) % client_count;
        int cy = y + row * rowH;

        char ip_part[8];
        snprintf(ip_part, sizeof(ip_part), ".%-3d ", clients[i].ip[3]);
        sprite.setTextFont(2);
        sprite.setTextColor(COL_IP, COL_BG);
        sprite.drawString(ip_part, margin, cy);
        int ip_w = sprite.textWidth(ip_part);

        char mac[13];
        snprintf(mac, sizeof(mac), "%02X%02X%02X%02X%02X%02X",
            clients[i].mac[0], clients[i].mac[1], clients[i].mac[2],
            clients[i].mac[3], clients[i].mac[4], clients[i].mac[5]);
        sprite.setTextFont(1);
        sprite.setTextColor(COL_MAC, COL_BG);
        sprite.drawString(mac, margin + ip_w, cy + 4);
    }
}

void display_init() {
    tft.init();
    tft.setRotation(0);  // portrait 128x160
    tft.fillScreen(COL_BG);
    tft.setBrightness(255);  // no-op: backlight is hardwired to 3V3

    sprite.setColorDepth(16);
    sprite.createSprite(W, H);
}

void display_debug_step(const char *msg) {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString(msg, W / 2, H / 2);
}

void display_boot_screen() {
    tft.fillScreen(COL_BG);
    tft.setTextColor(COL_HEADER_FG, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    tft.drawString("AirBridge", W / 2, H / 2 - 20);
    tft.setTextFont(2);
    tft.drawString(".S31", W / 2, H / 2 + 6);
    tft.setTextFont(1);
    tft.drawString("Booting...", W / 2, H / 2 + 30);
}

void display_boot_msg(int reason) {
    // 3=SW_RESET 4=PANIC 5=INT_WDT 6=TASK_WDT 9=BROWNOUT
    const char *names[] = {"?","VBAT","EXT","SW","PANIC","IWDT","TWDT","WDT","DSLP","BROWN","SDIO","USB"};
    const char *name = (reason >= 0 && reason <= 11) ? names[reason] : "?";
    tft.fillScreen(COL_BG);
    tft.setTextColor(TFT_RED, COL_BG);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(4);
    tft.drawString("RESET", W / 2, H / 2 - 16);
    tft.setTextFont(2);
    char buf[32];
    snprintf(buf, sizeof(buf), "%d %s", reason, name);
    tft.drawString(buf, W / 2, H / 2 + 14);
}

void display_update(const APConfig &cfg, bool usb_online,
                    bool sta_connected, int sta_rssi,
                    ClientInfo *clients, int client_count)
{
    sprite.fillScreen(COL_BG);

    int y = draw_header(cfg);

    switch (s_page) {
        case PAGE_JOIN:
            draw_page_join(cfg, y);
            break;
        case PAGE_STATUS:
            draw_page_status(cfg, usb_online, sta_connected, sta_rssi, y);
            break;
        case PAGE_CLIENTS:
        default:
            draw_page_clients(clients, client_count, y);
            break;
    }

    sprite.pushSprite(0, 0);

    if (++s_page_hold >= PAGE_HOLD_TICKS) {
        s_page_hold = 0;
        s_page = (s_page + 1) % PAGE_COUNT;
    }
}
