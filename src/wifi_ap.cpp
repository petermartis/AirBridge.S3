#include "wifi_ap.h"
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_log.h>
#include <lwip/ip4_addr.h>
#include <dhcpserver/dhcpserver.h>

static const char *TAG = "WiFi";

static esp_netif_t *ap_netif_handle() {
    return esp_netif_get_handle_from_ifkey("WIFI_AP_DEF");
}

void wifi_ap_init(const APConfig &cfg) {
    // Configure static IP for the AP
    IPAddress local_ip(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress gateway(cfg.ip[0], cfg.ip[1], cfg.ip[2], cfg.ip[3]);
    IPAddress subnet(255, 255, 255, 0);

    // Temporary bring-up diagnostic (see main.cpp's BOOT_STEP) --
    // bisecting a silent hang on real S31 hardware that stops right
    // around here with no further output. Remove once found and fixed.
    ESP_LOGI(TAG, "WiFi.mode...");
    // Use AP+STA if repeater is enabled, otherwise AP only
    WiFi.mode(cfg.repeater_on ? WIFI_AP_STA : WIFI_AP);
    ESP_LOGI(TAG, "WiFi.mode OK");
    WiFi.softAPConfig(local_ip, gateway, subnet);
    ESP_LOGI(TAG, "softAPConfig OK");
    WiFi.softAP(cfg.ssid.c_str(), cfg.password.c_str(), 1, 0, 10);
    ESP_LOGI(TAG, "softAP OK");

    wifi_ap_apply_dhcp_range(cfg);
    ESP_LOGI(TAG, "apply_dhcp_range OK");

    ESP_LOGI(TAG, "AP started: SSID=%s IP=%s mode=%s",
        cfg.ssid.c_str(),
        config_ip_str(cfg.ip).c_str(),
        cfg.repeater_on ? "AP+STA" : "AP");
}

// The DHCP server only accepts option changes while stopped, and rejects a
// range that contains the AP's own address or exceeds DHCPS_MAX_LEASE (100).
void wifi_ap_apply_dhcp_range(const APConfig &cfg) {
    esp_netif_t *ap_netif = ap_netif_handle();
    if (!ap_netif) {
        ESP_LOGE(TAG, "AP netif not found, DHCP range not applied");
        return;
    }

    uint8_t start = cfg.dhcp_start;
    uint8_t end   = cfg.dhcp_end;
    if (end > 254) end = 254;
    if (start < 1) start = 1;
    if (start >= end) {
        ESP_LOGW(TAG, "DHCP range %u-%u invalid, leaving default", start, end);
        return;
    }
    // Never hand out the AP's own address.
    if (cfg.ip[3] >= start && cfg.ip[3] <= end) {
        if (cfg.ip[3] < 254 && (uint8_t)(cfg.ip[3] + 1) < end) {
            start = cfg.ip[3] + 1;
        } else if (cfg.ip[3] > 1) {
            end = cfg.ip[3] - 1;
        } else {
            ESP_LOGW(TAG, "DHCP range %u-%u contains AP IP, leaving default", start, end);
            return;
        }
    }
    if (end - start + 1 > DHCPS_MAX_LEASE) {
        end = start + DHCPS_MAX_LEASE - 1;
    }

    esp_err_t err = esp_netif_dhcps_stop(ap_netif);
    if (err != ESP_OK && err != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STOPPED) {
        ESP_LOGE(TAG, "DHCP stop failed: %s", esp_err_to_name(err));
        return;
    }

    dhcps_lease_t lease = {};
    lease.enable = true;
    lease.start_ip.addr = ESP_IP4TOADDR(cfg.ip[0], cfg.ip[1], cfg.ip[2], start);
    lease.end_ip.addr   = ESP_IP4TOADDR(cfg.ip[0], cfg.ip[1], cfg.ip[2], end);

    err = esp_netif_dhcps_option(ap_netif, ESP_NETIF_OP_SET,
                                 ESP_NETIF_REQUESTED_IP_ADDRESS,
                                 &lease, sizeof(lease));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "DHCP range set failed: %s", esp_err_to_name(err));
    } else {
        ESP_LOGI(TAG, "DHCP range: %u.%u.%u.%u-%u",
                 cfg.ip[0], cfg.ip[1], cfg.ip[2], start, end);
    }

    err = esp_netif_dhcps_start(ap_netif);
    if (err != ESP_OK && err != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED) {
        ESP_LOGE(TAG, "DHCP start failed: %s", esp_err_to_name(err));
    }
}

// Without this the DHCP server falls back to advertising its own address as the
// DNS server (CONFIG_LWIP_DHCPS_ADD_DNS), which nothing on the device answers.
void wifi_ap_set_client_dns(uint32_t dns_addr) {
    static uint32_t s_offered_dns = 0;
    if (dns_addr == 0 || dns_addr == s_offered_dns) return;

    esp_netif_t *ap_netif = ap_netif_handle();
    if (!ap_netif) return;

    esp_netif_dns_info_t dns = {};
    dns.ip.type = ESP_IPADDR_TYPE_V4;
    dns.ip.u_addr.ip4.addr = dns_addr;
    esp_err_t err = esp_netif_set_dns_info(ap_netif, ESP_NETIF_DNS_MAIN, &dns);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "AP DNS set failed: %s", esp_err_to_name(err));
        return;
    }

    // OFFER_DNS can only be toggled while the DHCP server is stopped.
    uint8_t offer = 1;
    err = esp_netif_dhcps_stop(ap_netif);
    if (err != ESP_OK && err != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STOPPED) {
        ESP_LOGE(TAG, "DHCP stop failed: %s", esp_err_to_name(err));
        return;
    }
    err = esp_netif_dhcps_option(ap_netif, ESP_NETIF_OP_SET,
                                 ESP_NETIF_DOMAIN_NAME_SERVER,
                                 &offer, sizeof(offer));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "DHCP DNS option failed: %s", esp_err_to_name(err));
    }
    err = esp_netif_dhcps_start(ap_netif);
    if (err != ESP_OK && err != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED) {
        ESP_LOGE(TAG, "DHCP start failed: %s", esp_err_to_name(err));
        return;
    }

    s_offered_dns = dns_addr;
    ESP_LOGI(TAG, "Offering DNS " IPSTR " to WiFi clients",
             IP2STR(&dns.ip.u_addr.ip4));
}

int wifi_ap_client_count() {
    return WiFi.softAPgetStationNum();
}

int wifi_ap_get_clients(ClientInfo *out, int max_clients) {
    wifi_sta_list_t wifi_list;
    if (esp_wifi_ap_get_sta_list(&wifi_list) != ESP_OK) return 0;

    // Get IP addresses for each connected station via DHCP server
    esp_netif_t *ap_netif = ap_netif_handle();

    int count = wifi_list.num;
    if (count > max_clients) count = max_clients;
    if (count <= 0) return 0;

    // One IPC call for every station rather than one per station.
    esp_netif_pair_mac_ip_t pairs[ESP_WIFI_MAX_CONN_NUM] = {};
    if (count > ESP_WIFI_MAX_CONN_NUM) count = ESP_WIFI_MAX_CONN_NUM;
    for (int i = 0; i < count; i++) {
        memcpy(out[i].mac, wifi_list.sta[i].mac, 6);
        memcpy(pairs[i].mac, wifi_list.sta[i].mac, 6);
    }

    bool have_ips = ap_netif &&
        esp_netif_dhcps_get_clients_by_mac(ap_netif, count, pairs) == ESP_OK;

    for (int i = 0; i < count; i++) {
        if (have_ips) {
            uint32_t ip_addr = pairs[i].ip.addr;
            out[i].ip[0] = (ip_addr >> 0)  & 0xFF;
            out[i].ip[1] = (ip_addr >> 8)  & 0xFF;
            out[i].ip[2] = (ip_addr >> 16) & 0xFF;
            out[i].ip[3] = (ip_addr >> 24) & 0xFF;
        } else {
            memset(out[i].ip, 0, 4);
        }
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

uint32_t wifi_sta_dns_addr() {
    esp_netif_t *sta_netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (!sta_netif) return 0;
    esp_netif_dns_info_t dns = {};
    if (esp_netif_get_dns_info(sta_netif, ESP_NETIF_DNS_MAIN, &dns) != ESP_OK) return 0;
    return dns.ip.u_addr.ip4.addr;
}

void wifi_scan_start() {
    if (WiFi.scanComplete() == WIFI_SCAN_RUNNING) return;
    ESP_LOGI(TAG, "Starting WiFi scan...");
    WiFi.scanNetworks(true, false, false, 300);
}

String wifi_scan_result() {
    int16_t n = WiFi.scanComplete();
    if (n == WIFI_SCAN_RUNNING) return "{\"scanning\":true}";

    String json = "{\"scanning\":false,\"networks\":[";
    for (int16_t i = 0; i < n; i++) {
        if (i > 0) json += ",";
        json += "{\"ssid\":\"";
        // Escape backslashes and quotes so an odd SSID can't break the JSON
        String ssid = WiFi.SSID(i);
        ssid.replace("\\", "\\\\");
        ssid.replace("\"", "\\\"");
        json += ssid;
        json += "\",\"rssi\":";
        json += String(WiFi.RSSI(i));
        json += ",\"enc\":";
        json += (WiFi.encryptionType(i) != WIFI_AUTH_OPEN) ? "true" : "false";
        json += "}";
    }
    json += "]}";
    if (n >= 0) {
        WiFi.scanDelete();
        ESP_LOGI(TAG, "Scan found %d networks", n);
    }
    return json;
}
