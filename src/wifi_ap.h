#pragma once
#include <Arduino.h>
#include "config.h"

// Info about a connected WiFi client
struct ClientInfo {
    uint8_t  mac[6];
    uint8_t  ip[4];
    String   hostname;
};

// Initialize WiFi AP (and STA if repeater is enabled)
void wifi_ap_init(const APConfig &cfg);

// Get list of currently connected clients (call periodically)
// Returns number of clients written into `out`, up to `max_clients`
int wifi_ap_get_clients(ClientInfo *out, int max_clients);

// Get count of connected stations
int wifi_ap_client_count();

// --- WiFi STA uplink (repeater mode) ---

// Start STA connection to upstream network
void wifi_sta_start(const String &ssid, const String &pass);

// Check if STA is connected to upstream
bool wifi_sta_is_connected();

// Get STA signal strength (dBm), 0 if not connected
int wifi_sta_rssi();

// Get STA IP as string (empty if not connected)
String wifi_sta_ip_str();

// Scan for available networks, returns JSON array string
// e.g. [{"ssid":"MyNet","rssi":-55,"enc":true}, ...]
String wifi_scan_networks();
