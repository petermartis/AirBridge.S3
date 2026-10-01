//
// Isolated Bus_IDF_SPI diagnostic -- see platformio.ini in this
// directory for why this exists. Drives Bus_IDF_SPI.h's writeCommand()
// / writeBytes() directly, reproducing raw_spi_test's exact proven
// sequence and pin config, but through Bus_IDF_SPI instead of calling
// spi_device_transmit directly, and completely bypassing LovyanGFX's
// Panel_LCD/LGFX_Device layer (no Panel_ST7735_Minimal, no
// LGFX_Config_s31, no setColorDepth()/setRotation()/clear()
// auto-calls).
//
// writeBytes() is used for ALL data here (not writeData()/
// writeDataRepeat()), including the 4-byte CASET/RASET window values
// and the repeated 16-bit color payload -- writeBytes() sends a raw
// byte buffer exactly as given, with no multi-byte packing/swapping
// involved, so this test can't be affected by anything to do with
// Bus_IDF_SPI's packing convention (the bug already found and fixed
// in pack_lsb_first()). That isolates whether Bus_IDF_SPI's
// transaction/chunking mechanics themselves are sound.
//
#include <Arduino.h>
#define LGFX_USE_V1
#include "../../src/Bus_IDF_SPI.h"

#define PIN_NUM_MOSI 37
#define PIN_NUM_CLK  35
#define PIN_NUM_CS   39
#define PIN_NUM_DC   40
#define PIN_NUM_RST  43

static Bus_IDF_SPI bus;

static void send_cmd(uint8_t cmd)
{
    bus.writeCommand(cmd, 8);
}

static void send_data(const uint8_t *data, uint32_t len)
{
    bus.writeBytes(data, len, true, false);
}

static void set_addr_window(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1)
{
    uint8_t data[4];

    send_cmd(0x2A); // CASET
    data[0] = 0x00; data[1] = x0; data[2] = 0x00; data[3] = x1;
    send_data(data, 4);

    send_cmd(0x2B); // RASET
    data[0] = 0x00; data[1] = y0; data[2] = 0x00; data[3] = y1;
    send_data(data, 4);

    send_cmd(0x2C); // RAMWR
}

static void fill_color(uint16_t color, int width, int height)
{
    const int total_pixels = width * height;
    const int chunk_pixels = 128;
    uint8_t buf[chunk_pixels * 2];

    for (int i = 0; i < chunk_pixels; i++) {
        buf[i * 2]     = color >> 8;
        buf[i * 2 + 1] = color & 0xFF;
    }

    set_addr_window(0, 0, width - 1, height - 1);

    int remaining = total_pixels;
    while (remaining > 0) {
        int send_pixels = remaining > chunk_pixels ? chunk_pixels : remaining;
        send_data(buf, send_pixels * 2);
        remaining -= send_pixels;
    }
}

static void log_step(const char *s)
{
    Serial.println(s);
    Serial.flush();
}

static void panel_init(void)
{
    log_step("[bus_idf_spi_test] manual reset...");
    gpio_config_t rst_conf = {};
    rst_conf.pin_bit_mask = (1ULL << PIN_NUM_RST);
    rst_conf.mode = GPIO_MODE_OUTPUT;
    rst_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    rst_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    rst_conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&rst_conf);

    gpio_set_level((gpio_num_t)PIN_NUM_RST, 1);
    delay(5);
    gpio_set_level((gpio_num_t)PIN_NUM_RST, 0);
    delay(20);
    gpio_set_level((gpio_num_t)PIN_NUM_RST, 1);
    delay(150);
    log_step("[bus_idf_spi_test] reset pulse done");

    Bus_IDF_SPI::config_t cfg;
    cfg.spi_host   = SPI2_HOST;
    cfg.spi_mode   = 0;
    cfg.freq_write = 10000000;
    cfg.pin_sclk   = PIN_NUM_CLK;
    cfg.pin_mosi   = PIN_NUM_MOSI;
    cfg.pin_miso   = -1;
    cfg.pin_cs     = PIN_NUM_CS;
    cfg.pin_dc     = PIN_NUM_DC;
    bus.config(cfg);

    log_step("[bus_idf_spi_test] bus.init()...");
    bool ok = bus.init();
    Serial.printf("[bus_idf_spi_test] bus.init() returned %d\n", ok);
    Serial.flush();

    log_step("[bus_idf_spi_test] sending SWRESET...");
    send_cmd(0x01); // SWRESET
    delay(150);
    log_step("[bus_idf_spi_test] SWRESET sent OK");

    send_cmd(0x11); // SLPOUT
    delay(150);
    log_step("[bus_idf_spi_test] SLPOUT sent OK");

    {
        uint8_t data = 0x05; // 16-bit color
        send_cmd(0x3A);
        send_data(&data, 1);
    }
    {
        uint8_t data = 0x00; // rotation default
        send_cmd(0x36);
        send_data(&data, 1);
    }

    send_cmd(0x20); // INVOFF
    delay(10);
    send_cmd(0x13); // NORON
    delay(10);
    send_cmd(0x29); // DISPON
    delay(100);
    log_step("[bus_idf_spi_test] panel_init complete");
}

void setup(void)
{
    Serial.begin(115200);
    delay(500);
    log_step("[bus_idf_spi_test] setup() start");
    panel_init();
    log_step("[bus_idf_spi_test] setup() done");
}

void loop(void)
{
    log_step("[bus_idf_spi_test] Fill RED");
    fill_color(0xF800, 128, 160);
    delay(1000);

    log_step("[bus_idf_spi_test] Fill GREEN");
    fill_color(0x07E0, 128, 160);
    delay(1000);

    log_step("[bus_idf_spi_test] Fill BLUE");
    fill_color(0x001F, 128, 160);
    delay(1000);

    log_step("[bus_idf_spi_test] Fill WHITE");
    fill_color(0xFFFF, 128, 160);
    delay(1000);

    log_step("[bus_idf_spi_test] Fill BLACK");
    fill_color(0x0000, 128, 160);
    delay(1000);
}
