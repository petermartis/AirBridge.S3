#include "webserver.h"
#include <WiFi.h>
#include <WiFiClient.h>

static WiFiServer http_server(80);
static APConfig *current_cfg = nullptr;

// ---- Embedded HTML page ----
// NOTE: We avoid snprintf() into a fixed-size buffer because it truncated the page
// (hiding the Save & Reboot button on some clients).
static const char HTML_PAGE[] PROGMEM = R"rawhtml(
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AirBridge.S3</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee;
         display: flex; justify-content: center; padding: 20px; }
  .card { background: #16213e; border-radius: 12px; padding: 24px; width: 100%;
          max-width: 520px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
  h1 { text-align: center; margin-bottom: 20px; color: #0ff; font-size: 1.4em; }
  label { display: block; margin-top: 14px; font-size: 0.85em; color: #aaa; }
  input[type=text], input[type=number] {
    width: 100%; padding: 10px; margin-top: 4px; border: 1px solid #333;
    border-radius: 6px; background: #0f3460; color: #fff; font-size: 1em;
  }
  input:focus { outline: none; border-color: #0ff; }
  .range-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .range-row input { width: 92px; }
  .range-row span { color: #888; }
  button {
    width: 100%; margin-top: 24px; padding: 14px; border: none;
    border-radius: 8px; background: #e94560; color: #fff; font-size: 1.1em;
    font-weight: bold; cursor: pointer; transition: background 0.2s;
  }
  button:hover { background: #c0392b; }
  .note { text-align: center; margin-top: 12px; font-size: 0.75em; color: #666; }
</style>
</head>
<body>
<div class="card">
  <h1>&#128225; AirBridge.S3 Settings</h1>
  <form method="POST" action="/save">
    <label>SSID</label>
    <input type="text" name="ssid" value="%SSID%" maxlength="31" required>

    <label>WiFi Password (min 8 chars, WPA2)</label>
    <input type="text" name="password" value="%PASS%" minlength="8" maxlength="63" required>

    <label>Device IP Address</label>
    <input type="text" name="ip" value="%IP%" inputmode="decimal" placeholder="192.168.1.1" required>

    <label>DHCP Range (last octet of %NET%0/24)</label>
    <div class="range-row">
      <span>%NET%</span>
      <input type="number" name="dhcp_s" value="%DS%" min="2" max="254" required>
      <span>&ndash;</span>
      <span>%NET%</span>
      <input type="number" name="dhcp_e" value="%DE%" min="2" max="255" required>
    </div>

    <button type="submit">&#128260; Save &amp; Reboot</button>
  </form>
  <p class="note">Device will reboot after saving. Reconnect to the new SSID.</p>
</div>
</body>
</html>
)rawhtml";

// URL-decode a percent-encoded string in-place
static String url_decode(const String &in) {
    String out;
    out.reserve(in.length());
    for (unsigned int i = 0; i < in.length(); i++) {
        if (in[i] == '+') {
            out += ' ';
        } else if (in[i] == '%' && i + 2 < in.length()) {
            char hex[3] = { in[i+1], in[i+2], 0 };
            out += (char)strtol(hex, NULL, 16);
            i += 2;
        } else {
            out += in[i];
        }
    }
    return out;
}

// Parse a form field value from URL-encoded POST body
static String get_form_field(const String &body, const String &name) {
    String search = name + "=";
    int start = body.indexOf(search);
    if (start < 0) return "";
    start += search.length();
    int end = body.indexOf('&', start);
    if (end < 0) end = body.length();
    return url_decode(body.substring(start, end));
}

static void send_response(WiFiClient &client, int code, const String &content_type, const String &body) {
    const char *reason = "OK";
    if (code == 400) reason = "Bad Request";
    if (code == 404) reason = "Not Found";

    client.printf("HTTP/1.1 %d %s\r\n", code, reason);
    client.printf("Content-Type: %s\r\n", content_type.c_str());
    client.printf("Content-Length: %u\r\n", (unsigned)body.length());
    client.print("Connection: close\r\n\r\n");
    client.print(body);
}

static bool parse_ip4(const String &s, uint8_t out[4]) {
    int part = 0;
    int start = 0;

    for (int i = 0; i <= (int)s.length(); i++) {
        if (i == (int)s.length() || s[i] == '.') {
            if (part >= 4) return false;
            String seg = s.substring(start, i);
            seg.trim();
            if (seg.length() == 0 || seg.length() > 3) return false;
            for (unsigned int j = 0; j < seg.length(); j++) {
                if (!isDigit(seg[j])) return false;
            }
            int v = seg.toInt();
            if (v < 0 || v > 255) return false;
            out[part++] = (uint8_t)v;
            start = i + 1;
        }
    }

    return part == 4;
}

static String build_page() {
    String page = FPSTR(HTML_PAGE);

    char net_prefix[16];
    snprintf(net_prefix, sizeof(net_prefix), "%u.%u.%u.",
        current_cfg->ip[0], current_cfg->ip[1], current_cfg->ip[2]);

    page.replace("%SSID%", current_cfg->ssid);
    page.replace("%PASS%", current_cfg->password);
    page.replace("%IP%", config_ip_str(current_cfg->ip));
    page.replace("%NET%", String(net_prefix));
    page.replace("%DS%", String(current_cfg->dhcp_start));
    page.replace("%DE%", String(current_cfg->dhcp_end));

    return page;
}

static void handle_root(WiFiClient &client) {
    send_response(client, 200, "text/html", build_page());
}

static void handle_save(WiFiClient &client, const String &body) {
    String ssid = get_form_field(body, "ssid");
    String pass = get_form_field(body, "password");
    String ip_s = get_form_field(body, "ip");

    if (ssid.length() == 0 || ssid.length() > 31) {
        send_response(client, 400, "text/plain", "SSID must be 1-31 chars");
        return;
    }
    if (pass.length() < 8 || pass.length() > 63) {
        send_response(client, 400, "text/plain", "Password must be 8-63 chars");
        return;
    }

    uint8_t ip[4];
    if (!parse_ip4(ip_s, ip) || ip[3] == 0 || ip[3] == 255) {
        send_response(client, 400, "text/plain", "Invalid IP address");
        return;
    }

    int ds = get_form_field(body, "dhcp_s").toInt();
    int de = get_form_field(body, "dhcp_e").toInt();
    if (ds < 2 || ds > 254 || de < 2 || de > 255 || ds >= de) {
        send_response(client, 400, "text/plain", "Invalid DHCP range (start 2-254, end 2-255, start < end)");
        return;
    }

    current_cfg->ssid       = ssid;
    current_cfg->password   = pass;
    current_cfg->ip[0]      = ip[0];
    current_cfg->ip[1]      = ip[1];
    current_cfg->ip[2]      = ip[2];
    current_cfg->ip[3]      = ip[3];
    current_cfg->dhcp_start = (uint8_t)ds;
    current_cfg->dhcp_end   = (uint8_t)de;

    config_save(*current_cfg);

    String resp = "<html><body style='background:#1a1a2e;color:#0f0;text-align:center;"
                  "font-family:sans-serif;padding:60px'>"
                  "<h2>&#9989; Settings Saved!</h2>"
                  "<p>Rebooting in 2 seconds...</p></body></html>";
    send_response(client, 200, "text/html", resp);
    client.stop();
    delay(2000);
    ESP.restart();
}

void webserver_init(APConfig &cfg) {
    current_cfg = &cfg;
    http_server.begin();
    Serial.println("[Web] Config server started on port 80");
}

void webserver_handle() {
    WiFiClient client = http_server.available();
    if (!client) return;

    // Wait for data
    unsigned long timeout = millis() + 3000;
    while (!client.available() && millis() < timeout) {
        delay(1);
    }
    if (!client.available()) { client.stop(); return; }

    // Read request line
    String request_line = client.readStringUntil('\n');
    request_line.trim();

    // Determine method and path
    bool is_post = request_line.startsWith("POST");
    String path = "/";
    int sp1 = request_line.indexOf(' ');
    int sp2 = request_line.indexOf(' ', sp1 + 1);
    if (sp1 > 0 && sp2 > sp1) {
        path = request_line.substring(sp1 + 1, sp2);
    }

    // Read headers, find Content-Length
    int content_length = 0;
    while (client.available()) {
        String header = client.readStringUntil('\n');
        header.trim();
        if (header.length() == 0) break;  // end of headers
        if (header.startsWith("Content-Length:")) {
            content_length = header.substring(15).toInt();
        }
    }

    // Read body for POST
    String body;
    if (is_post && content_length > 0) {
        body.reserve(content_length);
        unsigned long body_timeout = millis() + 3000;
        while ((int)body.length() < content_length && millis() < body_timeout) {
            if (client.available()) {
                body += (char)client.read();
            } else {
                delay(1);
            }
        }
    }

    // Route
    if (is_post && path == "/save") {
        handle_save(client, body);
    } else {
        handle_root(client);
    }

    client.stop();
}
