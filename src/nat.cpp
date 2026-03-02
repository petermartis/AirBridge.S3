#include "nat.h"

// NOTE: The standard Arduino-ESP32 lwIP build does NOT include NAPT support.
// ip_napt_enable() is only available when lwIP is compiled with IP_NAPT=1,
// which requires a custom ESP-IDF sdkconfig (not possible via PlatformIO Arduino).
//
// Since USB NCM tethering is also not available in Arduino mode (see usb_net.cpp),
// there is no WAN uplink to NAT through anyway. This module is a graceful stub.
// When the project is migrated to ESP-IDF framework, both USB NCM and NAPT can
// be enabled together.

static bool s_nat_active = false;

void nat_enable() {
    if (s_nat_active) return;

    Serial.println("[NAT] NAPT not available in Arduino framework build.");
    Serial.println("[NAT] Requires ESP-IDF with CONFIG_LWIP_IP_FORWARD=y and CONFIG_LWIP_IPV4_NAPT=y");
    // Mark as "active" so callers don't retry repeatedly
    s_nat_active = true;
}

void nat_disable() {
    s_nat_active = false;
}

bool nat_is_active() {
    return s_nat_active;
}
