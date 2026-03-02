#pragma once
#include <Arduino.h>

// Enable NAT (NAPT) on the WiFi AP interface so clients can
// reach the internet through the USB tethered connection
void nat_enable();

// Disable NAT
void nat_disable();

// Check if NAT is currently active
bool nat_is_active();
