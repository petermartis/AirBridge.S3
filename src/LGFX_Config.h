#pragma once

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

//
// AirBridge.S3 — LovyanGFX hardware configuration
// Waveshare ESP32-S3-GEEK: 1.14" ST7789 LCD, 135x240, SPI
//

class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_ST7789  _panel;
    lgfx::Bus_SPI       _bus;
    lgfx::Light_PWM     _backlight;

public:
    LGFX(void) {
        // ---- SPI bus ----
        {
            auto cfg = _bus.config();
            cfg.spi_host   = SPI2_HOST;   // FSPI / GPSPI2
            cfg.spi_mode   = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read  = 16000000;
            cfg.pin_sclk   = 12;
            cfg.pin_mosi   = 11;
            cfg.pin_miso   = -1;
            cfg.pin_dc     =  8;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }

        // ---- Panel (ST7789, 135x240 on 240x320 memory) ----
        {
            auto cfg = _panel.config();
            cfg.pin_cs       = 10;
            cfg.pin_rst      =  9;
            cfg.pin_busy     = -1;
            cfg.panel_width  = 135;
            cfg.panel_height = 240;
            cfg.memory_width = 240;
            cfg.memory_height= 320;
            cfg.offset_x     = 52;
            cfg.offset_y     = 40;
            cfg.offset_rotation = 0;
            cfg.invert       = true;
            cfg.rgb_order    = false;  // BGR (ST7789 default)
            cfg.dlen_16bit   = false;
            cfg.bus_shared   = false;
            _panel.config(cfg);
        }

        // ---- Backlight (GPIO 7, active-high) ----
        {
            auto cfg = _backlight.config();
            cfg.pin_bl      = 7;
            cfg.invert      = false;
            cfg.freq        = 44100;
            cfg.pwm_channel = 7;
            _backlight.config(cfg);
            _panel.setLight(&_backlight);
        }

        setPanel(&_panel);
    }
};
