#pragma once

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

//
// AirBridge.S3 — LovyanGFX hardware configuration (esp32s31 env)
// External 1.8" ST7735 LCD, 128x160, SPI
//
// Wiring:
//   VCC   -> 3V3
//   GND   -> GND
//   LED   -> 3V3 (backlight always on, no GPIO control)
//   SCK   -> GPIO12 (SPI clock)
//   SDA   -> GPIO11 (SPI MOSI)
//   CS    -> GPIO10 (chip select)
//   A0    -> GPIO9  (D/C)
//   RESET -> GPIO8
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
    lgfx::Panel_ST7735S _panel;
    lgfx::Bus_SPI       _bus;

public:
    LGFX(void) {
        // ---- SPI bus ----
        {
            auto cfg = _bus.config();
            cfg.spi_host   = SPI2_HOST;   // FSPI / GPSPI2
            cfg.spi_mode   = 0;
            cfg.freq_write = 27000000;    // ST7735 tops out lower than ST7789
            cfg.freq_read  = 14000000;
            cfg.pin_sclk   = 12;
            cfg.pin_mosi   = 11;
            cfg.pin_miso   = -1;
            cfg.pin_dc     =  9;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }

        // ---- Panel (ST7735S, 128x160) ----
        {
            auto cfg = _panel.config();
            cfg.pin_cs       = 10;
            cfg.pin_rst      =  8;
            cfg.pin_busy     = -1;
            cfg.panel_width  = 128;
            cfg.panel_height = 160;
            cfg.memory_width = 132;
            cfg.memory_height= 162;
            cfg.offset_x     = 2;   // see calibration note above
            cfg.offset_y     = 1;   // see calibration note above
            cfg.offset_rotation = 0;
            cfg.invert       = false;
            cfg.rgb_order    = false;  // BGR (ST7735 default)
            cfg.dlen_16bit   = false;
            cfg.bus_shared   = false;
            _panel.config(cfg);
        }

        // ---- Backlight: LED wired straight to 3V3, no PWM control ----
        // (no Light_PWM instance — nothing to drive; setBrightness() is a
        //  harmless no-op without a registered backlight controller)

        setPanel(&_panel);
    }
};
