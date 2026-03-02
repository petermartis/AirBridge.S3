#pragma once
#include <Arduino.h>
#include "config.h"

// Info about a connected WiFi client
struct ClientInfo {
    uint8_t  mac[6];
    uint8_t  ip[4];
    String   hostname;
};

// Initialize WiFi AP with given config
void wifi_ap_init(const APConfig &cfg);

// Get list of currently connected clients (call periodically)
// Returns number of clients written into `out`, up to `max_clients`
int wifi_ap_get_clients(ClientInfo *out, int max_clients);

// Get count of connected stations
int wifi_ap_client_count();
