#pragma once
#include <Arduino.h>
#include "config.h"

// Start the configuration web server on port 80
void webserver_init(APConfig &cfg);

// Call in loop() to handle incoming HTTP requests
void webserver_handle();
