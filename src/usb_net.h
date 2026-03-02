#pragma once
#include <Arduino.h>

// Initialize USB NCM (Network Control Model) device
// ESP32-S3 will appear as a USB Ethernet adapter to the host PC
void usb_net_init();

// Check if USB network link is up and has an IP from the host
bool usb_net_is_online();

// Get the USB interface's IP as a string (empty if offline)
String usb_net_ip_str();

// Call periodically to process USB network events
void usb_net_loop();

// Get human-readable status for LCD debug display
const char *usb_net_status_msg();
