#include "config.h"
#include <Preferences.h>

static const char* NVS_NS = "ap_config";

void config_load(APConfig &cfg) {
    Preferences prefs;
    prefs.begin(NVS_NS, true); // read-only

    cfg.ssid       = prefs.getString("ssid", "PM_Travel");
    cfg.password   = prefs.getString("password", "Adames007");
    cfg.ip[0]      = prefs.getUChar("ip0", 192);
    cfg.ip[1]      = prefs.getUChar("ip1", 168);
    cfg.ip[2]      = prefs.getUChar("ip2", 1);
    cfg.ip[3]      = prefs.getUChar("ip3", 1);
    cfg.dhcp_start = prefs.getUChar("dhcp_s", 2);
    cfg.dhcp_end   = prefs.getUChar("dhcp_e", 255);

    // WiFi repeater
    cfg.repeater_on  = prefs.getBool("rep_on", false);
    cfg.uplink_ssid  = prefs.getString("rep_ssid", "");
    cfg.uplink_pass  = prefs.getString("rep_pass", "");

    // Display options
    cfg.show_title = prefs.getBool("show_ttl", true);
    cfg.show_cpu   = prefs.getBool("show_cpu", true);
    cfg.show_mem   = prefs.getBool("show_mem", true);

    prefs.end();
}

void config_save(const APConfig &cfg) {
    Preferences prefs;
    prefs.begin(NVS_NS, false); // read-write

    prefs.putString("ssid", cfg.ssid);
    prefs.putString("password", cfg.password);
    prefs.putUChar("ip0", cfg.ip[0]);
    prefs.putUChar("ip1", cfg.ip[1]);
    prefs.putUChar("ip2", cfg.ip[2]);
    prefs.putUChar("ip3", cfg.ip[3]);
    prefs.putUChar("dhcp_s", cfg.dhcp_start);
    prefs.putUChar("dhcp_e", cfg.dhcp_end);

    // WiFi repeater
    prefs.putBool("rep_on", cfg.repeater_on);
    prefs.putString("rep_ssid", cfg.uplink_ssid);
    prefs.putString("rep_pass", cfg.uplink_pass);

    // Display options
    prefs.putBool("show_ttl", cfg.show_title);
    prefs.putBool("show_cpu", cfg.show_cpu);
    prefs.putBool("show_mem", cfg.show_mem);

    prefs.end();
}

String config_ip_str(const uint8_t ip[4]) {
    return String(ip[0]) + "." + String(ip[1]) + "." +
           String(ip[2]) + "." + String(ip[3]);
}
