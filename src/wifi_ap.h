#pragma once
#include <Arduino.h>
#include "config.h"

// Info about a connected WiFi client
struct ClientInfo {
    uint8_t  mac[6];
    uint8_t  ip[4];
};

// Initialize WiFi AP (and STA if repeater is enabled)
void wifi_ap_init(const APConfig &cfg);

// Get list of currently connected clients (call periodically)
// Returns number of clients written into `out`, up to `max_clients`
int wifi_ap_get_clients(ClientInfo *out, int max_clients);

// Get count of connected stations
int wifi_ap_client_count();

// Apply the configured DHCP lease range to the AP's DHCP server.
// Call after the AP is up; restarts the DHCP server.
void wifi_ap_apply_dhcp_range(const APConfig &cfg);

// Offer `dns_addr` (IPv4, network byte order) to WiFi clients via the AP's
// DHCP server, so they can resolve names through the uplink. No-op if 0.
void wifi_ap_set_client_dns(uint32_t dns_addr);

// --- WiFi STA uplink (repeater mode) ---

// Start STA connection to upstream network
void wifi_sta_start(const String &ssid, const String &pass);

// Check if STA is connected to upstream
bool wifi_sta_is_connected();

// Get STA signal strength (dBm), 0 if not connected
int wifi_sta_rssi();

// Get STA IP as string (empty if not connected)
String wifi_sta_ip_str();

// Upstream DNS server learned from the STA uplink (network byte order), 0 if none
uint32_t wifi_sta_dns_addr();

// Begin an asynchronous scan for available networks (no-op while one runs)
void wifi_scan_start();

// Poll the asynchronous scan, returns a JSON object string:
// {"scanning":true} while in progress, else {"networks":[{"ssid":..,"rssi":..,"enc":..}]}
String wifi_scan_result();
