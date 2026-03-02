#include "wifi_ap.h"
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_log.h>
#include <lwip/ip4_addr.h>

static const char *TAG = "WiFi";

void wifi_ap_init(const APConfig &cfg) {
    // Configure static IP for the AP
    IPAddress local_ip(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress gateway(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress subnet(255, 255, 255, 0);

    // Use AP+STA if repeater is enabled, otherwise AP only
    WiFi.mode(cfg.repeater_on ? WIFI_AP_STA : WIFI_AP);
    WiFi.softAPConfig(local_ip, gateway, subnet);
    WiFi.softAP(cfg.ssid.c_str(), cfg.password.c_str(), 1, 0, 10);

    ESP_LOGI(TAG, "AP started: SSID=%s IP=%s mode=%s",
        cfg.ssid.c_str(),
        config_ip_str(cfg.ip).c_str(),
        cfg.repeater_on ? "AP+STA" : "AP");
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

// ---------------------------------------------------------------------------
// WiFi STA uplink (repeater mode)
// ---------------------------------------------------------------------------

void wifi_sta_start(const String &ssid, const String &pass) {
    if (ssid.length() == 0) {
        ESP_LOGW(TAG, "STA start skipped: no uplink SSID configured");
        return;
    }
    ESP_LOGI(TAG, "STA connecting to: %s", ssid.c_str());
    WiFi.begin(ssid.c_str(), pass.c_str());
}

bool wifi_sta_is_connected() {
    return WiFi.isConnected();
}

int wifi_sta_rssi() {
    if (!WiFi.isConnected()) return 0;
    return WiFi.RSSI();
}

String wifi_sta_ip_str() {
    if (!WiFi.isConnected()) return "";
    return WiFi.localIP().toString();
}

String wifi_scan_networks() {
    ESP_LOGI(TAG, "Starting WiFi scan...");
    int n = WiFi.scanNetworks(false, false, false, 300);
    String json = "[";
    for (int i = 0; i < n; i++) {
        if (i > 0) json += ",";
        json += "{\"ssid\":\"";
        // Escape any quotes in SSID
        String ssid = WiFi.SSID(i);
        ssid.replace("\"", "\\\"");
        json += ssid;
        json += "\",\"rssi\":";
        json += String(WiFi.RSSI(i));
        json += ",\"enc\":";
        json += (WiFi.encryptionType(i) != WIFI_AUTH_OPEN) ? "true" : "false";
        json += "}";
    }
    json += "]";
    WiFi.scanDelete();
    ESP_LOGI(TAG, "Scan found %d networks", n);
    return json;
}
