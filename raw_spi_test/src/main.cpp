//
// Byte-for-byte reproduction of the user's own proven-working raw
// esp-idf spi_master ST7735 test (confirmed working standalone via
// `idf.py --preview build / flash / monitor` on this exact board,
// panel, and wiring) — only the entry point is adapted from
// app_main() to Arduino's setup()/loop() so this can be built through
// PlatformIO's Arduino framework instead. See platformio.ini in this
// directory for why.
//
#include <Arduino.h>
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"

#define PIN_NUM_MOSI 37
#define PIN_NUM_CLK  35
#define PIN_NUM_CS   39
#define PIN_NUM_DC   40
#define PIN_NUM_RST  43

static const char *TAG = "st7735";

static spi_device_handle_t tft_spi;

static void tft_send_cmd(uint8_t cmd)
{
    gpio_set_level((gpio_num_t)PIN_NUM_DC, 0);
    spi_transaction_t t = {};
    t.length = 8;
    t.tx_buffer = &cmd;
    ESP_ERROR_CHECK(spi_device_transmit(tft_spi, &t));
}

static void tft_send_data(const uint8_t *data, int len)
{
    if (len <= 0) return;
    gpio_set_level((gpio_num_t)PIN_NUM_DC, 1);
    spi_transaction_t t = {};
    t.length = len * 8;
    t.tx_buffer = data;
    ESP_ERROR_CHECK(spi_device_transmit(tft_spi, &t));
}

static void tft_set_addr_window(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1)
{
    uint8_t data[4];

    tft_send_cmd(0x2A); // CASET
    data[0] = 0x00;
    data[1] = x0;
    data[2] = 0x00;
    data[3] = x1;
    tft_send_data(data, 4);

    tft_send_cmd(0x2B); // RASET
    data[0] = 0x00;
    data[1] = y0;
    data[2] = 0x00;
    data[3] = y1;
    tft_send_data(data, 4);

    tft_send_cmd(0x2C); // RAMWR
}

static void tft_fill_color(uint16_t color, int width, int height)
{
    const int total_pixels = width * height;
    const int chunk_pixels = 128;
    uint8_t buf[chunk_pixels * 2];

    for (int i = 0; i < chunk_pixels; i++) {
        buf[i * 2]     = color >> 8;
        buf[i * 2 + 1] = color & 0xFF;
    }

    tft_set_addr_window(0, 0, width - 1, height - 1);

    int remaining = total_pixels;
    while (remaining > 0) {
        int send_pixels = remaining > chunk_pixels ? chunk_pixels : remaining;
        tft_send_data(buf, send_pixels * 2);
        remaining -= send_pixels;
    }
}

static void tft_init(void)
{
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << PIN_NUM_DC) | (1ULL << PIN_NUM_RST);
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&io_conf));

    gpio_set_level((gpio_num_t)PIN_NUM_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(5));
    gpio_set_level((gpio_num_t)PIN_NUM_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level((gpio_num_t)PIN_NUM_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(150));

    spi_bus_config_t buscfg = {};
    buscfg.mosi_io_num = PIN_NUM_MOSI;
    buscfg.miso_io_num = -1;
    buscfg.sclk_io_num = PIN_NUM_CLK;
    buscfg.quadwp_io_num = -1;
    buscfg.quadhd_io_num = -1;
    buscfg.max_transfer_sz = 128 * 2 + 8;
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO));

    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = 10000000;
    devcfg.mode = 0;
    devcfg.spics_io_num = PIN_NUM_CS;
    devcfg.queue_size = 1;
    ESP_ERROR_CHECK(spi_bus_add_device(SPI2_HOST, &devcfg, &tft_spi));

    tft_send_cmd(0x01); // SWRESET
    vTaskDelay(pdMS_TO_TICKS(150));

    tft_send_cmd(0x11); // SLPOUT
    vTaskDelay(pdMS_TO_TICKS(150));

    {
        uint8_t data = 0x05;   // 16-bit color
        tft_send_cmd(0x3A);    // COLMOD
        tft_send_data(&data, 1);
    }

    {
        uint8_t data = 0x00;   // rotation default
        tft_send_cmd(0x36);    // MADCTL
        tft_send_data(&data, 1);
    }

    tft_send_cmd(0x21); // INVON, many ST7735 modules need this
    vTaskDelay(pdMS_TO_TICKS(10));

    tft_send_cmd(0x13); // NORON
    vTaskDelay(pdMS_TO_TICKS(10));

    tft_send_cmd(0x29); // DISPON
    vTaskDelay(pdMS_TO_TICKS(100));
}

void setup(void)
{
    Serial.begin(115200);
    delay(500);
    ESP_LOGI(TAG, "Starting ST7735 test (raw spi_master, via Arduino/PlatformIO build)");
    tft_init();
}

void loop(void)
{
    ESP_LOGI(TAG, "Fill RED");
    tft_fill_color(0xF800, 128, 160);
    vTaskDelay(pdMS_TO_TICKS(1000));

    ESP_LOGI(TAG, "Fill GREEN");
    tft_fill_color(0x07E0, 128, 160);
    vTaskDelay(pdMS_TO_TICKS(1000));

    ESP_LOGI(TAG, "Fill BLUE");
    tft_fill_color(0x001F, 128, 160);
    vTaskDelay(pdMS_TO_TICKS(1000));

    ESP_LOGI(TAG, "Fill WHITE");
    tft_fill_color(0xFFFF, 128, 160);
    vTaskDelay(pdMS_TO_TICKS(1000));

    ESP_LOGI(TAG, "Fill BLACK");
    tft_fill_color(0x0000, 128, 160);
    vTaskDelay(pdMS_TO_TICKS(1000));
}
