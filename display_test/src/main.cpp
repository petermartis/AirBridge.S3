//
// Isolated ESP32-S31 display test — see platformio.ini in this directory.
// Deliberately outside the main src/ tree so it can never be picked up
// by, or interfere with, the real firmware's build.
//
#include <Arduino.h>
#define LGFX_USE_V1
#include "../../src/LGFX_Config_s31.h"

static LGFX tft;

void setup() {
    Serial.begin(115200);
    delay(500);  // let power/backlight settle before we touch SPI
    Serial.println("[display_test] setup() start");

    tft.initWithManualReset();
    Serial.println("[display_test] tft.initWithManualReset() returned");
    tft.setRotation(0);

    // Solid color fills: each visible for 1s even if text rendering has
    // a problem of its own. If NONE of these show up, the panel isn't
    // receiving/responding to SPI at all — check wiring
    // (SCK12/MOSI11/CS10/DC9/RESET8) and the RESET line first.
    // Diagnostic: spi_device_transmit()'s return value is now checked
    // (see Bus_IDF_SPI::check()) and counted. Printing the running
    // count/fail-count after each fill tells us, independent of what the
    // panel actually shows, whether every fillScreen() issues the same
    // number of SPI transactions and whether the driver itself ever
    // reports one failing -- real hardware showed the screen visibly
    // changing on the first fill only, then sticking, even though every
    // Serial checkpoint below still fires normally (no hang, no crash).
    auto log_bus_stats = [](const char *step) {
        Serial.printf("[display_test] %s: bus calls=%lu fails=%lu\n", step,
                      (unsigned long)Bus_IDF_SPI::transmitCount(),
                      (unsigned long)Bus_IDF_SPI::transmitFailCount());
    };

    tft.fillScreen(TFT_RED);
    Serial.println("[display_test] filled RED");
    log_bus_stats("after RED");
    delay(1000);
    tft.fillScreen(TFT_GREEN);
    Serial.println("[display_test] filled GREEN");
    log_bus_stats("after GREEN");
    delay(1000);
    tft.fillScreen(TFT_BLUE);
    Serial.println("[display_test] filled BLUE");
    log_bus_stats("after BLUE");
    delay(1000);
    tft.fillScreen(TFT_BLACK);
    log_bus_stats("after BLACK");

    // Text + a border rectangle: if the colors above worked but this
    // looks shifted/cropped on one edge, that's the offset_x/offset_y
    // calibration noted in LGFX_Config_s31.h, not a wiring problem.
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString("DISPLAY OK", tft.width() / 2, tft.height() / 2);
    tft.drawRect(0, 0, tft.width(), tft.height(), TFT_YELLOW);
    log_bus_stats("after text+rect");
    Serial.println("[display_test] setup() done");
}

void loop() {
    static uint32_t last = 0;
    static bool on = false;
    if (millis() - last > 1000) {
        last = millis();
        on = !on;
        // Blink a small square each second as a "still alive, not
        // crash-looped back to boot" heartbeat.
        tft.fillRect(4, 4, 8, 8, on ? TFT_WHITE : TFT_BLACK);
    }
}
