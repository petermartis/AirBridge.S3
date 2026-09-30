#pragma once

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

//
// AirBridge.S3 — LovyanGFX hardware configuration (esp32s31 env)
// External 1.8" ST7735 LCD, 128x160, SPI
//
// Wiring — as verified against a known-working raw esp-idf spi_master
// test on the actual board (not the original GPIO8-12 plan this project
// started from, which turned out not to match the real hardware):
//   VCC   -> 3V3
//   GND   -> GND
//   LED   -> 3V3 (backlight always on, no GPIO control)
//   SCK   -> GPIO35 (SPI clock)
//   SDA   -> GPIO37 (SPI MOSI)
//   CS    -> GPIO39 (chip select)
//   A0    -> GPIO40 (D/C)
//   RESET -> GPIO43
//
// invert/rgb_order below are set to match that same working test's init
// sequence (it sends INVON / 0x21, and a MADCTL of 0x00 with no BGR bit
// set) rather than the ST7735 defaults, since it's proven to actually
// work on this panel.
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
            cfg.pin_sclk   = 35;
            cfg.pin_mosi   = 37;
            cfg.pin_miso   = -1;
            cfg.pin_dc     = 40;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }

        // ---- Panel (ST7735S, 128x160) ----
        {
            auto cfg = _panel.config();
            cfg.pin_cs       = 39;
            cfg.pin_rst      = 43;
            cfg.pin_busy     = -1;
            cfg.panel_width  = 128;
            cfg.panel_height = 160;
            cfg.memory_width = 132;
            cfg.memory_height= 162;
            cfg.offset_x     = 2;   // see calibration note above
            cfg.offset_y     = 1;   // see calibration note above
            cfg.offset_rotation = 0;
            cfg.invert       = true;   // matches the working test's INVON (0x21)
            cfg.rgb_order    = true;   // matches the working test's MADCTL=0x00 (no BGR bit)
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
