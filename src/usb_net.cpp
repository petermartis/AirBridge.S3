#include "usb_net.h"

//
// USB NCM Network Device — TinyUSB NCM + custom esp_netif driver
//
// The ESP32 appears as a USB Ethernet adapter (NCM class) to the host.
// A custom esp_netif with DHCP client obtains an IP from the host.
// lwIP routes + NATs WiFi AP traffic through this interface.
//

#include <string.h>
#include <esp_log.h>
#include <esp_mac.h>
#include <esp_event.h>
#include <esp_netif.h>

#include "tinyusb.h"
#include "tinyusb_default_config.h"
#include "tinyusb_net.h"

static const char *TAG = "USB_NET";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
static esp_netif_t *s_usb_netif = NULL;
static bool s_usb_link_up = false;
static bool s_usb_has_ip  = false;
static esp_netif_ip_info_t s_usb_ip_info = {};
static char s_status_msg[48] = "Init...";

// Exposed for display debug line
const char *usb_net_status_msg() { return s_status_msg; }

// ---------------------------------------------------------------------------
// Custom esp_netif I/O driver
// ---------------------------------------------------------------------------
typedef struct {
    esp_netif_driver_base_t base;   // must be first member
} usb_netif_driver_t;

static usb_netif_driver_t s_driver = {};

// lwIP → USB: transmit a packet from the IP stack to the host
static esp_err_t usb_netif_transmit(void *h, void *buffer, size_t len)
{
    if (!tud_ready()) return ESP_FAIL;
    return tinyusb_net_send_sync(buffer, len, NULL, pdMS_TO_TICKS(100));
}

// lwIP → USB: transmit with free (not used, but required by interface)
static esp_err_t usb_netif_transmit_wrap(void *h, void *buffer, size_t len, void *netstack_buf)
{
    return usb_netif_transmit(h, buffer, len);
}

// Driver post-attach: called by esp_netif after the driver is attached
static esp_err_t usb_driver_post_attach(esp_netif_t *esp_netif, void *args)
{
    usb_netif_driver_t *drv = (usb_netif_driver_t *)args;
    drv->base.netif = esp_netif;

    // Set the driver transmit function
    esp_netif_driver_ifconfig_t driver_cfg = {};
    driver_cfg.handle = drv;
    driver_cfg.transmit = usb_netif_transmit;
    driver_cfg.transmit_wrap = usb_netif_transmit_wrap;
    ESP_ERROR_CHECK(esp_netif_set_driver_config(esp_netif, &driver_cfg));

    return ESP_OK;
}

// ---------------------------------------------------------------------------
// TinyUSB NCM callbacks
// ---------------------------------------------------------------------------

// USB → lwIP: received an Ethernet frame from the host
static esp_err_t usb_recv_callback(void *buffer, uint16_t len, void *ctx)
{
    if (s_usb_netif) {
        esp_netif_receive(s_usb_netif, buffer, len, NULL);
    }
    return ESP_OK;
}

// Free callback for tinyusb_net_send_sync (not needed for lwIP-originated buffers)
static void usb_free_tx_cb(void *buffer, void *ctx)
{
    // No-op: lwIP manages its own buffers
}

// ---------------------------------------------------------------------------
// IP event handler — detect when DHCP assigns an IP on the USB interface
// ---------------------------------------------------------------------------
static void ip_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    // Only handle Ethernet/STA got-IP events (same data structure: ip_event_got_ip_t)
    if (id == IP_EVENT_ETH_GOT_IP || id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)data;
        if (event->esp_netif != s_usb_netif) return;  // not our interface

        s_usb_ip_info = event->ip_info;
        s_usb_has_ip = true;
        snprintf(s_status_msg, sizeof(s_status_msg), "IP:" IPSTR,
                 IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "USB got IP: " IPSTR ", GW: " IPSTR,
                 IP2STR(&event->ip_info.ip), IP2STR(&event->ip_info.gw));
    } else if (id == IP_EVENT_ETH_LOST_IP || id == IP_EVENT_STA_LOST_IP) {
        // Can't safely check esp_netif for LOST events, just clear if we had IP
        if (s_usb_has_ip) {
            s_usb_has_ip = false;
            memset(&s_usb_ip_info, 0, sizeof(s_usb_ip_info));
            snprintf(s_status_msg, sizeof(s_status_msg), "IP lost");
            ESP_LOGW(TAG, "USB lost IP");
        }
    }
}

// ---------------------------------------------------------------------------
// Create the custom esp_netif for the USB interface
// ---------------------------------------------------------------------------
static esp_netif_t *create_usb_netif(void)
{
    // Base netif config: DHCP client, custom driver
    esp_netif_inherent_config_t base_cfg = ESP_NETIF_INHERENT_DEFAULT_ETH();
    base_cfg.if_key = "USB_NCM";
    base_cfg.if_desc = "usb ncm";
    base_cfg.route_prio = 50;  // lower than WiFi STA (100) but functional

    // Use default Ethernet-style lwIP netif (handles ARP, DHCP, etc.)
    esp_netif_config_t cfg = {};
    cfg.base = &base_cfg;
    cfg.stack = ESP_NETIF_NETSTACK_DEFAULT_ETH;

    esp_netif_t *netif = esp_netif_new(&cfg);
    if (!netif) {
        ESP_LOGE(TAG, "Failed to create USB netif");
        return NULL;
    }

    // Set MAC address (use WiFi STA MAC + locally administered bit)
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    mac[0] |= 0x02;  // locally administered
    mac[5] ^= 0x01;  // differentiate from WiFi
    esp_netif_set_mac(netif, mac);

    // Attach our custom driver
    s_driver.base.post_attach = usb_driver_post_attach;
    ESP_ERROR_CHECK(esp_netif_attach(netif, &s_driver));

    return netif;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
void usb_net_init()
{
    ESP_LOGI(TAG, "Initializing USB NCM...");
    snprintf(s_status_msg, sizeof(s_status_msg), "USB init...");

    // 1. Install TinyUSB driver with custom device name
    static const char *usb_strings[] = {
        "\x09\x04",       // 0: Language (English)
        "AirBridge.S3",    // 1: Manufacturer
        "AirBridge.S3",    // 2: Product (shown in macOS Network)
        "000001",          // 3: Serial number
    };
    tinyusb_config_t tusb_cfg = TINYUSB_DEFAULT_CONFIG();
    tusb_cfg.descriptor.string = usb_strings;
    tusb_cfg.descriptor.string_count = sizeof(usb_strings) / sizeof(usb_strings[0]);
    esp_err_t ret = tinyusb_driver_install(&tusb_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "TinyUSB install failed: %s", esp_err_to_name(ret));
        snprintf(s_status_msg, sizeof(s_status_msg), "USB drv fail");
        return;
    }

    // 2. Initialize NCM network class
    tinyusb_net_config_t net_cfg = {};
    net_cfg.on_recv_callback = usb_recv_callback;
    net_cfg.free_tx_buffer = usb_free_tx_cb;
    net_cfg.user_context = NULL;
    esp_read_mac(net_cfg.mac_addr, ESP_MAC_WIFI_STA);
    net_cfg.mac_addr[0] |= 0x02;
    net_cfg.mac_addr[5] ^= 0x01;

    ret = tinyusb_net_init(&net_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "TinyUSB NCM init failed: %s", esp_err_to_name(ret));
        snprintf(s_status_msg, sizeof(s_status_msg), "NCM fail");
        return;
    }

    // 3. Register IP event handler
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID,
                                                ip_event_handler, NULL));

    // 4. Create esp_netif with DHCP client for USB
    s_usb_netif = create_usb_netif();
    if (!s_usb_netif) {
        snprintf(s_status_msg, sizeof(s_status_msg), "Netif fail");
        return;
    }

    // 5. Start DHCP client
    esp_netif_dhcpc_start(s_usb_netif);

    snprintf(s_status_msg, sizeof(s_status_msg), "Waiting for host...");
    ESP_LOGI(TAG, "USB NCM ready, waiting for host connection");
}

bool usb_net_is_online()
{
    return s_usb_has_ip;
}

String usb_net_ip_str()
{
    if (!s_usb_has_ip) return "";
    char buf[16];
    snprintf(buf, sizeof(buf), IPSTR, IP2STR(&s_usb_ip_info.ip));
    return String(buf);
}

void usb_net_loop()
{
    // Track USB link state changes
    bool link_now = tud_ready();

    if (link_now && !s_usb_link_up) {
        // Link just came up — notify esp_netif
        s_usb_link_up = true;
        esp_netif_action_start(s_usb_netif, NULL, 0, NULL);
        esp_netif_action_connected(s_usb_netif, NULL, 0, NULL);
        snprintf(s_status_msg, sizeof(s_status_msg), "Connected, DHCP...");
        ESP_LOGI(TAG, "USB link UP");
    } else if (!link_now && s_usb_link_up) {
        // Link went down
        s_usb_link_up = false;
        s_usb_has_ip = false;
        esp_netif_action_disconnected(s_usb_netif, NULL, 0, NULL);
        esp_netif_action_stop(s_usb_netif, NULL, 0, NULL);
        snprintf(s_status_msg, sizeof(s_status_msg), "Disconnected");
        ESP_LOGW(TAG, "USB link DOWN");
    }
}
