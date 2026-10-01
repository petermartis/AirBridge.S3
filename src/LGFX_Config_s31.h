#pragma once

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "Panel_ST7735_Minimal.h"
#include "Bus_IDF_SPI.h"

//
// AirBridge.S3 — LovyanGFX hardware configuration (esp32s31 env)
// External 1.8" ST7735 LCD, 128x160, SPI
//
// Wiring:
//   VCC   -> 3V3
//   GND   -> GND
//   LED   -> 3V3 (backlight always on, no GPIO control)
//   SCK   -> GPIO35 (SPI clock)
//   SDA   -> GPIO37 (SPI MOSI)
//   CS    -> GPIO39 (chip select)
//   A0    -> GPIO40 (D/C)
//   RESET -> GPIO43
//
// BUS — Bus_IDF_SPI (backed directly by ESP-IDF's spi_master driver),
// not lgfx::Bus_SPI: lgfx::Bus_SPI's own register-banging
// implementation never produced a visible result on this ST7735 panel
// on ESP32-S31 (see Bus_IDF_SPI.h).
//
// pin_cs on the PANEL below is deliberately left unset (-1): CS is
// owned entirely by the ESP-IDF driver via devcfg.spics_io_num inside
// Bus_IDF_SPI, not bit-banged by Panel_Device — setting it here too
// would mean two different things driving the same physical pin.
//
// NOTE — display offset (offset_x/offset_y below): ST7735 controllers have
// a fixed 132x162 GRAM regardless of the glass size soldered to them, and
// the windowing offset into that GRAM varies by panel batch/tab color
// (this is the same "green tab / red tab / black tab" issue as the
// Adafruit_ST7735 library). offset_x=2, offset_y=1 is the most common
// value reported for this exact 128x160 red-PCB module family, but it is
// NOT verified against your physical unit. If the image on first boot is
// shifted, or a row/column of pixels is cut off on one edge, adjust these
// two values (try 0,0 or 2,3 next) — this is a per-panel calibration, not
// a code bug.
//

class LGFX : public lgfx::LGFX_Device {
    // Minimal-init-table subclass (see Panel_ST7735_Minimal.h) instead
    // of lgfx::Panel_ST7735S directly — skips ~13 gamma/power commands
    // this panel doesn't need.
    Panel_ST7735_Minimal _panel;
    Bus_IDF_SPI          _bus;

public:
    LGFX(void) {
        // ---- SPI bus ----
        {
            auto cfg = _bus.config();
            cfg.spi_host   = SPI2_HOST;   // FSPI / GPSPI2
            cfg.spi_mode   = 0;
            cfg.freq_write = 10000000;
            cfg.pin_sclk   = 35;
            cfg.pin_mosi   = 37;
            cfg.pin_miso   = -1;
            cfg.pin_cs     = 39;
            cfg.pin_dc     = 40;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }

        // ---- Panel (ST7735S, 128x160) ----
        {
            auto cfg = _panel.config();
            cfg.pin_cs       = -1;   // CS owned by Bus_IDF_SPI — see note above
            cfg.pin_rst      = 43;
            cfg.pin_busy     = -1;
            cfg.panel_width  = 128;
            cfg.panel_height = 160;
            cfg.memory_width = 132;
            cfg.memory_height= 162;
            cfg.offset_x     = 2;   // see calibration note above
            cfg.offset_y     = 1;   // see calibration note above
            cfg.offset_rotation = 0;
            cfg.invert       = false;  // matches Panel_ST7735_Minimal's INVOFF
            cfg.rgb_order    = true;   // matches MADCTL=0x00 (no BGR bit)
            cfg.dlen_16bit   = false;
            cfg.bus_shared   = false;
            _panel.config(cfg);
        }

        // ---- Backlight: LED wired straight to 3V3, no PWM control ----
        // (no Light_PWM instance — nothing to drive; setBrightness() is a
        //  harmless no-op without a registered backlight controller)

        setPanel(&_panel);
    }

    // Replaces LovyanGFX's built-in hardware reset pulse (inside the
    // normal init() -> Panel_Device::init() path: an 8ms low pulse /
    // 64ms settle) with a more conservative one (5ms high confirm, 20ms
    // low pulse, 150ms settle after release) proven reliable on this
    // panel, then calls init_without_reset() so LovyanGFX's own shorter
    // pulse never runs. Use this instead of plain init().
    void initWithManualReset(void)
    {
        int8_t pin_rst = _panel.config().pin_rst;
        if (pin_rst >= 0)
        {
            gpio_config_t rst_conf = {};
            rst_conf.pin_bit_mask = (1ULL << pin_rst);
            rst_conf.mode = GPIO_MODE_OUTPUT;
            rst_conf.pull_up_en = GPIO_PULLUP_DISABLE;
            rst_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
            rst_conf.intr_type = GPIO_INTR_DISABLE;
            gpio_config(&rst_conf);

            gpio_set_level((gpio_num_t)pin_rst, 1);
            delay(5);
            gpio_set_level((gpio_num_t)pin_rst, 0);
            delay(20);
            gpio_set_level((gpio_num_t)pin_rst, 1);
            delay(150);
        }
        init_without_reset();
    }
};
