#pragma once
#include <Arduino.h>
#include "config.h"

// Start the configuration web server on port 80
void webserver_init(APConfig &cfg);

// Call in loop() to handle incoming HTTP requests
void webserver_handle();

// Enable/disable the captive-portal DNS hijack (answers every query with
// this device's own IP). Must be disabled once a real uplink is online --
// left hijacking permanently, it answers WiFi clients' DNS queries with
// this device's IP forever, breaking all internet access even once NAT
// is working. Call whenever uplink state changes; redundant calls are a
// no-op.
void webserver_set_captive_portal(bool enabled);
