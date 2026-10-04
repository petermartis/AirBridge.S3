#include "wifi_ap.h"
#include "display.h"
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_event.h>
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
    // around here with no further output. ESP_LOGE, not ESP_LOGI: this
    // board's configured log level filters out INFO entirely, which is
    // why no diagnostic line was ever showing up even when it ran.
    // Remove once found and fixed.
    ESP_LOGE(TAG, "WiFi.mode...");
    // Use AP+STA if repeater is enabled, otherwise AP only
    WiFi.mode(cfg.repeater_on ? WIFI_AP_STA : WIFI_AP);
    ESP_LOGE(TAG, "WiFi.mode OK");
    WiFi.softAPConfig(local_ip, gateway, subnet);
    ESP_LOGE(TAG, "softAPConfig OK");
    WiFi.softAP(cfg.ssid.c_str(), cfg.password.c_str(), 1, 0, 10);
    ESP_LOGE(TAG, "softAP OK");

    wifi_apply_tx_power(cfg.tx_power_dbm);

    wifi_ap_apply_dhcp_range(cfg);
    ESP_LOGE(TAG, "apply_dhcp_range OK");

    ESP_LOGI(TAG, "AP started: SSID=%s IP=%s mode=%s",
        cfg.ssid.c_str(),
        config_ip_str(cfg.ip).c_str(),
        cfg.repeater_on ? "AP+STA" : "AP");
}

// esp_wifi_set_max_tx_power() takes units of 0.25dBm over range [8,84]
// (2-20dBm) and only actually supports 11 discrete power levels within
// that range -- any other value gets silently rounded down to one of
// them by the driver. The web UI only offers those 11 exact dBm values,
// so what's configured is what's actually applied, with no hidden
// rounding to explain. Must be called after WiFi is started (softAP()
// already is, by the time wifi_ap_init() calls this).
void wifi_apply_tx_power(int8_t dbm) {
    if (dbm < 2) dbm = 2;
    if (dbm > 20) dbm = 20;
    esp_wifi_set_max_tx_power(dbm * 4);
}

// --- 40MHz channel / forced 11ax: ABANDONED ---
// Tried as a throughput lever separate from the lwIP TCP window/AMPDU
// block-ack tuning abandoned in sdkconfig.s31.defaults: a runtime
// esp_wifi_set_bandwidth()/esp_wifi_set_protocols() call on the radio's
// own PHY config, done after softAP()/WiFi.begin(), specifically to
// avoid the Kconfig-level netif/lwIP memory path that caused that
// other reboot loop.
//
// Confirmed on real hardware via log_e() (ESP_LOGx is invisible on
// this build -- CONFIG_ESP_CONSOLE_SECONDARY_NONE=y):
//   esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW40) -> ESP_ERR_INVALID_ARG
//   every single boot. 40MHz/HT40 is flatly rejected for softAP on
//   this chip/SDK combination -- never actually took effect, so it
//   bought nothing.
//   esp_wifi_set_protocols(WIFI_IF_AP, ...WIFI_PROTOCOL_11AX...) ->
//   ESP_OK, but boots became non-deterministically unstable right
//   around this call (device resets, sometimes mid-sequence between
//   the bandwidth and protocol calls, sometimes just after) -- a new
//   failure mode not present before this change, unlike the earlier
//   TCP-window crash's 100%-reproducible single failure point. Forcing
//   11AX (WiFi 6/HE) onto the AP interface is the suspect, since it's
//   the one call that both succeeded and sits right where the
//   instability appeared.
//
// Reverted entirely rather than guessing which half is safe: no
// bandwidth/protocol override is applied, leaving the driver's own
// defaults (20MHz, 11b/g/n, no forced 11ax) in place. If revisited,
// test forcing 11ax alone, in isolation, before trying HT40 again --
// and expect HT40 on softAP needs a different API or config path
// entirely given the flat ESP_ERR_INVALID_ARG, not just a retry.

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

// Raw ESP-IDF scan, bypassing Arduino's WiFiScanClass entirely: on real
// S31 hardware, WiFi.scanNetworks(true, ...) starts a scan successfully
// (confirmed: returns WIFI_SCAN_RUNNING, correct WiFi mode) that then
// never completes -- scanComplete() stayed at WIFI_SCAN_RUNNING for 40+
// seconds straight (polled directly via curl, no browser involved).
// That's consistent with Arduino's own WIFI_EVENT_SCAN_DONE subscription
// never firing in this hybrid Arduino+ESP-IDF build, rather than the
// underlying scan itself never finishing -- so this registers our own
// handler directly on ESP-IDF's event loop instead of going through
// WiFiGenericClass's event dispatch.
static volatile bool s_scan_done = false;
static bool s_scan_in_progress = false;
static bool s_scan_handler_registered = false;

static void on_wifi_scan_done(void*, esp_event_base_t, int32_t, void*) {
    s_scan_done = true;
}

void wifi_scan_start() {
    if (s_scan_in_progress) return;

    if (!s_scan_handler_registered) {
        esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_SCAN_DONE, &on_wifi_scan_done, nullptr);
        s_scan_handler_registered = true;
    }

    // Matches what WiFi.scanNetworks() did internally: scanning needs
    // the STA interface up even though this device's primary role here
    // is AP.
    WiFi.enableSTA(true);

    wifi_scan_config_t config = {};
    config.show_hidden = false;
    config.scan_type = WIFI_SCAN_TYPE_ACTIVE;
    config.scan_time.active.max = 300;

    s_scan_done = false;
    esp_err_t err = esp_wifi_scan_start(&config, false);
    s_scan_in_progress = (err == ESP_OK);

    // Temporary bring-up diagnostic: this build has no working serial
    // console (CONFIG_ESP_CONSOLE_SECONDARY_NONE=y, see
    // sdkconfig.s31.defaults -- re-enabling USB-Serial/JTAG was tried
    // and produced no visible console on real S31 hardware), so
    // ESP_LOGx output here goes nowhere. Using the TFT instead, as
    // intended by that same sdkconfig comment ("use LCD for debug").
    char buf[32];
    snprintf(buf, sizeof(buf), "scan start e=%d m=%d", (int)err, (int)WiFi.getMode());
    display_debug_step(buf);
}

String wifi_scan_result() {
    if (s_scan_in_progress && !s_scan_done) {
        display_debug_step("scan RUNNING (raw)...");
        return "{\"scanning\":true}";
    }
    bool started_ok = s_scan_in_progress;
    s_scan_in_progress = false;

    if (!started_ok) {
        display_debug_step("scan FAILED to start");
        return "{\"scanning\":false,\"networks\":[]}";
    }

    uint16_t count = 0;
    esp_wifi_scan_get_ap_num(&count);

    wifi_ap_record_t *records = nullptr;
    if (count > 0) {
        records = (wifi_ap_record_t *)malloc(count * sizeof(wifi_ap_record_t));
        if (records && esp_wifi_scan_get_ap_records(&count, records) != ESP_OK) {
            free(records);
            records = nullptr;
            count = 0;
        }
    }

    char buf[32];
    snprintf(buf, sizeof(buf), "scan done n=%u", (unsigned)count);
    display_debug_step(buf);

    String json = "{\"scanning\":false,\"networks\":[";
    for (uint16_t i = 0; i < count; i++) {
        if (i > 0) json += ",";
        json += "{\"ssid\":\"";
        // Escape backslashes and quotes so an odd SSID can't break the JSON
        String ssid = String((const char *)records[i].ssid);
        ssid.replace("\\", "\\\\");
        ssid.replace("\"", "\\\"");
        json += ssid;
        json += "\",\"rssi\":";
        json += String(records[i].rssi);
        json += ",\"enc\":";
        json += (records[i].authmode != WIFI_AUTH_OPEN) ? "true" : "false";
        json += "}";
    }
    json += "]}";
    if (records) free(records);
    return json;
}
