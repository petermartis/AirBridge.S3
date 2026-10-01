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
    // a problem of its own.
    tft.fillScreen(TFT_RED);
    Serial.println("[display_test] filled RED");
    delay(1000);
    tft.fillScreen(TFT_GREEN);
    Serial.println("[display_test] filled GREEN");
    delay(1000);
    tft.fillScreen(TFT_BLUE);
    Serial.println("[display_test] filled BLUE");
    delay(1000);
    tft.fillScreen(TFT_BLACK);

    // Text + a border rectangle: if the colors above worked but this
    // looks shifted/cropped on one edge, that's the offset_x/offset_y
    // calibration noted in LGFX_Config_s31.h, not a wiring problem.
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString("DISPLAY OK", tft.width() / 2, tft.height() / 2);
    tft.drawRect(0, 0, tft.width(), tft.height(), TFT_YELLOW);
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
