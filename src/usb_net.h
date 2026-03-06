#pragma once
#include <Arduino.h>

// Initialize USB ECM (Ethernet Control Model) device
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

// Debug: init stage + extra info for LCD bottom area
int usb_net_init_stage();
uint32_t usb_net_crash_pc();
uint32_t usb_net_crash_cause();
uint32_t usb_net_crash_vaddr();
uint32_t usb_net_crash_count();
const char *usb_net_debug_line();
