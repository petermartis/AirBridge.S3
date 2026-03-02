#pragma once
#include <Arduino.h>

struct APConfig {
    String   ssid;
    String   password;
    uint8_t  ip[4];         // e.g. {192,168,1,1}
    uint8_t  dhcp_start;    // last octet of range start
    uint8_t  dhcp_end;      // last octet of range end
};

// Load config from NVS (fills defaults if no saved config)
void config_load(APConfig &cfg);

// Save config to NVS
void config_save(const APConfig &cfg);

// Format IP as string
String config_ip_str(const uint8_t ip[4]);
