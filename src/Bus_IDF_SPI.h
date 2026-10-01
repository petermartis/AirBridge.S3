#pragma once
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <driver/gpio.h>
#include <driver/spi_master.h>
#include <esp_log.h>
#include <Arduino.h>

// A LovyanGFX bus implementation backed directly by ESP-IDF's
// spi_master driver (spi_bus_initialize / spi_bus_add_device /
// spi_device_transmit), in place of lgfx::Bus_SPI's own low-level
// register-banging implementation, which never produced a visible
// result on this ST7735 panel on ESP32-S31 despite correct wiring,
// GPIO dual-bank handling, and SPI clock speed/source.
//
// Scope: write-only, matching what this project's ST7735 display
// actually needs (no panel readback, no touch controller on this
// bus). Everything below IBus that this doesn't override — the read
// path, DMA queueing — is inherited as a harmless no-op/false from
// lgfx::Bus_NULL.
struct Bus_IDF_SPI : public lgfx::Bus_NULL
{
    struct config_t
    {
        int8_t pin_sclk = -1;
        int8_t pin_mosi = -1;
        int8_t pin_miso = -1;
        int8_t pin_cs   = -1;
        int8_t pin_dc   = -1;
        int spi_host    = SPI2_HOST;
        int spi_mode    = 0;
        uint32_t freq_write = 10000000;
    };

    const config_t& config(void) const { return _cfg; }
    void config(const config_t& cfg) { _cfg = cfg; }

    lgfx::bus_type_t busType(void) const override { return lgfx::bus_type_t::bus_spi; }

    bool init(void) override
    {
        if (_dev != nullptr) return true;

        gpio_config_t dc_conf = {};
        dc_conf.pin_bit_mask = (1ULL << _cfg.pin_dc);
        dc_conf.mode = GPIO_MODE_OUTPUT;
        dc_conf.pull_up_en = GPIO_PULLUP_DISABLE;
        dc_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
        dc_conf.intr_type = GPIO_INTR_DISABLE;
        gpio_config(&dc_conf);
        gpio_set_level((gpio_num_t)_cfg.pin_dc, 1);

        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = _cfg.pin_mosi;
        buscfg.miso_io_num = _cfg.pin_miso;
        buscfg.sclk_io_num = _cfg.pin_sclk;
        buscfg.quadwp_io_num = -1;
        buscfg.quadhd_io_num = -1;
        // Largest single transaction this bus ever issues is writeBytes'
        // 256-byte chunk cap below; sized to match.
        buscfg.max_transfer_sz = 264;
        esp_err_t err = spi_bus_initialize((spi_host_device_t)_cfg.spi_host, &buscfg, SPI_DMA_CH_AUTO);
        if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
            // Not silently swallowed: Panel_Device::init() (LovyanGFX)
            // discards this function's return value and always reports
            // success regardless, so this is the only place a failure
            // here would ever be visible at all. The on-screen BOOT_STEP
            // checkpoints can't show this either -- the screen itself
            // needs this same bus, so if it's what's broken, nothing can
            // ever draw. Flash the onboard RGB LED instead: it doesn't
            // depend on SPI2_HOST at all, so it stays a reliable signal
            // even in exactly the failure mode this is trying to catch.
            ESP_LOGE("Bus_IDF_SPI", "spi_bus_initialize failed: %d (%s)", err, esp_err_to_name(err));
            signal_init_failure();
            return false;
        }

        spi_device_interface_config_t devcfg = {};
        devcfg.clock_speed_hz = _cfg.freq_write;
        devcfg.mode = _cfg.spi_mode;
        devcfg.spics_io_num = _cfg.pin_cs;
        devcfg.queue_size = 1;
        err = spi_bus_add_device((spi_host_device_t)_cfg.spi_host, &devcfg, &_dev);
        if (err != ESP_OK) {
            ESP_LOGE("Bus_IDF_SPI", "spi_bus_add_device failed: %d (%s)", err, esp_err_to_name(err));
            signal_init_failure();
        }
        return err == ESP_OK;
    }

    void release(void) override
    {
        if (_dev != nullptr)
        {
            spi_bus_remove_device(_dev);
            _dev = nullptr;
        }
    }

    void beginTransaction(void) override {}
    void endTransaction(void) override {}
    void wait(void) override {}
    bool busy(void) const override { return false; }
    void initDMA(void) override {}
    void addDMAQueue(const uint8_t* data, uint32_t length) override { writeBytes(data, length, true, false); }
    void execDMAQueue(void) override {}
    void flush(void) override {}

    bool writeCommand(uint32_t data, uint_fast8_t bit_length) override
    {
        gpio_set_level((gpio_num_t)_cfg.pin_dc, 0);
        uint8_t cmd = (uint8_t)data;
        spi_transaction_t t = {};
        t.length = bit_length;
        t.tx_buffer = &cmd;
        check(spi_device_transmit(_dev, &t), "writeCommand");
        return true;
    }

    void writeData(uint32_t data, uint_fast8_t bit_length) override
    {
        gpio_set_level((gpio_num_t)_cfg.pin_dc, 1);
        uint8_t buf[4];
        pack_lsb_first(data, bit_length, buf);
        spi_transaction_t t = {};
        t.length = bit_length;
        t.tx_buffer = buf;
        check(spi_device_transmit(_dev, &t), "writeData");
    }

    void writeDataRepeat(uint32_t data, uint_fast8_t bit_length, uint32_t count) override
    {
        gpio_set_level((gpio_num_t)_cfg.pin_dc, 1);
        uint32_t bytelen = (bit_length + 7) >> 3;
        uint8_t unit[4];
        pack_lsb_first(data, bit_length, unit);

        static constexpr uint32_t CHUNK_UNITS = 128;
        uint8_t chunk[CHUNK_UNITS * 4];
        uint32_t fill = CHUNK_UNITS < count ? CHUNK_UNITS : count;
        for (uint32_t i = 0; i < fill; i++)
        {
            memcpy(chunk + i * bytelen, unit, bytelen);
        }

        while (count > 0)
        {
            uint32_t n = count > CHUNK_UNITS ? CHUNK_UNITS : count;
            spi_transaction_t t = {};
            t.length = n * bytelen * 8;
            t.tx_buffer = chunk;
            check(spi_device_transmit(_dev, &t), "writeDataRepeat");
            count -= n;
        }
    }

    void writePixels(lgfx::pixelcopy_t* pc, uint32_t length) override
    {
        uint8_t buf[256];
        uint32_t remain = length;
        while (remain > 0)
        {
            uint32_t n = remain > 128 ? 128 : remain;
            pc->fp_copy(buf, 0, n, pc);
            writeBytes(buf, n * 2, true, false);
            remain -= n;
        }
    }

    void writeBytes(const uint8_t* data, uint32_t length, bool dc, bool use_dma) override
    {
        (void)use_dma;
        gpio_set_level((gpio_num_t)_cfg.pin_dc, dc ? 1 : 0);
        while (length > 0)
        {
            uint32_t n = length > 256 ? 256 : length;
            spi_transaction_t t = {};
            t.length = n * 8;
            t.tx_buffer = data;
            check(spi_device_transmit(_dev, &t), "writeBytes");
            data += n;
            length -= n;
        }
    }

private:
    static void check(esp_err_t err, const char* who)
    {
        if (err != ESP_OK)
        {
            ESP_LOGE("Bus_IDF_SPI", "%s failed: %d (%s)", who, err, esp_err_to_name(err));
            signal_init_failure();
        }
    }

    // Latches the onboard RGB LED solid red -- see the comment at the
    // call site. #ifdef-guarded since RGB_BUILTIN is only defined on
    // boards that actually have one; a board without it just skips this
    // (ESP_LOGE above is still the fallback either way).
    static void signal_init_failure(void)
    {
#ifdef RGB_BUILTIN
        rgbLedWrite(RGB_BUILTIN, 255, 0, 0);
#endif
    }

    // LovyanGFX pre-packs multi-byte `data` expecting the bus to shift
    // it out LSB-of-the-value-first (matching how its own Bus_SPI
    // hardware path consumes a packed word from a FIFO register) -- not
    // MSB-first, despite data looking like a plain big-endian numeric
    // value at a glance.
    static void pack_lsb_first(uint32_t data, uint_fast8_t bit_length, uint8_t* out)
    {
        uint32_t bytelen = (bit_length + 7) >> 3;
        for (uint32_t i = 0; i < bytelen; i++)
        {
            out[i] = (uint8_t)(data >> (8 * i));
        }
    }

    config_t _cfg;
    spi_device_handle_t _dev = nullptr;
};
