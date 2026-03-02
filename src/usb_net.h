#pragma once
#include <Arduino.h>

// Initialize USB NCM (Network Control Model) device
// ESP32-S3 will appear as a USB Ethernet adapter to the host PC
void usb_net_init();

// Check if USB network link is up and has an IP from the host
bool usb_net_is_online();

// Call periodically to process USB network events
void usb_net_loop();
