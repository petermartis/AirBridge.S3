#include "wifi_ap.h"
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_log.h>
#include <lwip/ip4_addr.h>

void wifi_ap_init(const APConfig &cfg) {
    // Configure static IP for the AP
    IPAddress local_ip(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress gateway(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress subnet(255, 255, 255, 0);

    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(local_ip, gateway, subnet);
    WiFi.softAP(cfg.ssid.c_str(), cfg.password.c_str(), 1, 0, 10);

    // NOTE: DHCP range customization is intentionally not done here.
    // The Arduino-ESP32 core already starts a DHCP server for SoftAP based on
    // the IP/netmask set via WiFi.softAPConfig().
    //
    // We previously attempted to poke esp_netif DHCP options here, but that can
    // produce errors on some core versions and may contribute to instability.
    // We'll implement explicit DHCP lease-range control in a follow-up using
    // the correct DHCP server APIs.

    ESP_LOGI("WiFi", "AP started: SSID=%s IP=%s DHCP=%d-%d",
        cfg.ssid.c_str(),
        config_ip_str(cfg.ip).c_str(),
        cfg.dhcp_start, cfg.dhcp_end);
}

int wifi_ap_client_count() {
    return WiFi.softAPgetStationNum();
}

int wifi_ap_get_clients(ClientInfo *out, int max_clients) {
    wifi_sta_list_t wifi_list;
    if (esp_wifi_ap_get_sta_list(&wifi_list) != ESP_OK) return 0;

    // Get IP addresses for each connected station via DHCP server
    esp_netif_t *ap_netif = esp_netif_get_handle_from_ifkey("WIFI_AP_DEF");

    int count = 0;
    for (int i = 0; i < wifi_list.num && count < max_clients; i++) {
        memcpy(out[count].mac, wifi_list.sta[i].mac, 6);

        // Look up IP via DHCP server
        esp_netif_pair_mac_ip_t pair = {};
        memcpy(pair.mac, wifi_list.sta[i].mac, 6);
        if (ap_netif && esp_netif_dhcps_get_clients_by_mac(ap_netif, 1, &pair) == ESP_OK) {
            uint32_t ip_addr = pair.ip.addr;
            out[count].ip[0] = (ip_addr >> 0)  & 0xFF;
            out[count].ip[1] = (ip_addr >> 8)  & 0xFF;
            out[count].ip[2] = (ip_addr >> 16) & 0xFF;
            out[count].ip[3] = (ip_addr >> 24) & 0xFF;
        } else {
            memset(out[count].ip, 0, 4);
        }

        char mac_name[18];
        snprintf(mac_name, sizeof(mac_name), "%02X:%02X:%02X:%02X:%02X:%02X",
            out[count].mac[0], out[count].mac[1], out[count].mac[2],
            out[count].mac[3], out[count].mac[4], out[count].mac[5]);
        out[count].hostname = String(mac_name);

        count++;
    }

    return count;
}
