#include "nat.h"

//
// NAT (NAPT) — Real implementation using ESP-IDF lwIP NAPT
//
// Enables IP forwarding + NAPT on the WiFi AP interface so that
// WiFi clients can reach the internet through the USB NCM uplink.
// Requires CONFIG_LWIP_IP_FORWARD=y and CONFIG_LWIP_IPV4_NAPT=y.
//

#include <esp_log.h>
#include <esp_netif.h>
#include "lwip/lwip_napt.h"

static const char *TAG = "NAT";
static bool s_nat_active = false;

void nat_enable() {
    if (s_nat_active) return;

    // Get the WiFi AP netif and its IP
    esp_netif_t *ap_netif = esp_netif_get_handle_from_ifkey("WIFI_AP_DEF");
    if (!ap_netif) {
        ESP_LOGE(TAG, "WiFi AP netif not found");
        return;
    }

    esp_netif_ip_info_t ip_info;
    if (esp_netif_get_ip_info(ap_netif, &ip_info) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get AP IP info");
        return;
    }

    // Enable NAPT on the AP interface (ip_napt_enable returns void)
    ip_napt_enable(ip_info.ip.addr, 1);
    s_nat_active = true;
    ESP_LOGI(TAG, "NAPT enabled on AP (" IPSTR ")", IP2STR(&ip_info.ip));
}

void nat_disable() {
    if (!s_nat_active) return;

    esp_netif_t *ap_netif = esp_netif_get_handle_from_ifkey("WIFI_AP_DEF");
    if (ap_netif) {
        esp_netif_ip_info_t ip_info;
        if (esp_netif_get_ip_info(ap_netif, &ip_info) == ESP_OK) {
            ip_napt_enable(ip_info.ip.addr, 0);
        }
    }
    s_nat_active = false;
    ESP_LOGI(TAG, "NAPT disabled");
}

bool nat_is_active() {
    return s_nat_active;
}
