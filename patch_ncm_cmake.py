"""Patch TinyUSB NCM driver for macOS compatibility.

Invoked by CMakeLists.txt via execute_process() during CMake configuration,
AFTER the component manager has extracted managed_components.
"""

import os
import sys

if len(sys.argv) < 2:
    print("[patch_ncm_cmake] ERROR: no file path provided", file=sys.stderr)
    sys.exit(1)

NCM_FILE = sys.argv[1]
MARKER = "// [AirBridge.S3 patched]"

PATCHES = [
    # Patch 1: 100 Mbps speed for Full Speed USB
    (
        "notify_speed_change.downlink = 12000000;\n"
        "      notify_speed_change.uplink = 12000000;",
        "// Patched: 100 Mbps so macOS maps to 100BaseTX medium\n"
        "      notify_speed_change.downlink = 100000000;\n"
        "      notify_speed_change.uplink = 100000000;",
    ),
    # Patch 2: ACK packet filter / multicast filter class requests
    (
        "        case NCM_GET_NTB_PARAMETERS: {\n"
        "          // transfer NTB parameters to host.\n"
        "          tud_control_xfer(rhport, request, (void *) (uintptr_t) &ntb_parameters, sizeof(ntb_parameters));\n"
        "        } break;\n"
        "\n"
        "          // unsupported request\n"
        "        default:\n"
        "          return false;",
        "        case NCM_GET_NTB_PARAMETERS: {\n"
        "          // transfer NTB parameters to host.\n"
        "          tud_control_xfer(rhport, request, (void *) (uintptr_t) &ntb_parameters, sizeof(ntb_parameters));\n"
        "        } break;\n"
        "\n"
        "        case NCM_SET_ETHERNET_PACKET_FILTER:\n"
        "        case NCM_SET_ETHERNET_MULTICAST_FILTERS:\n"
        "          // macOS sends these during Internet Sharing bridge setup.\n"
        "          tud_control_status(rhport, request);\n"
        "          break;\n"
        "\n"
        "          // unsupported request\n"
        "        default:\n"
        "          return false;",
    ),
    # Patch 3a: Add debug variable for LCD display
    (
        "static ncm_interface_t ncm_interface;\n"
        "CFG_TUD_MEM_SECTION static ncm_epbuf_t ncm_epbuf;",
        "static ncm_interface_t ncm_interface;\n"
        "CFG_TUD_MEM_SECTION static ncm_epbuf_t ncm_epbuf;\n"
        "\n"
        "// Debug: expose notification state for LCD display\n"
        "volatile uint16_t ncm_notif_debug = 0xFFFF;",
    ),
    # Patch 3b: Capture usbd_edpt_xfer return value in SPEED notification
    (
        "    usbd_edpt_xfer(rhport, ncm_interface.ep_notif, (uint8_t*) &ncm_epbuf.epnotif, notif_len);\n"
        "\n"
        "    ncm_interface.notification_xmit_state = NOTIFICATION_CONNECTED;\n"
        "    ncm_interface.notification_xmit_is_running = true;\n"
        "  } else if (ncm_interface.notification_xmit_state == NOTIFICATION_CONNECTED) {",
        "    bool xfer_ok = usbd_edpt_xfer(rhport, ncm_interface.ep_notif, (uint8_t*) &ncm_epbuf.epnotif, notif_len);\n"
        "\n"
        "    ncm_interface.notification_xmit_state = NOTIFICATION_CONNECTED;\n"
        "    ncm_interface.notification_xmit_is_running = true;\n"
        "    ncm_notif_debug = (ncm_interface.ep_notif & 0xFF)\n"
        "                    | ((uint16_t)ncm_interface.notification_xmit_state << 8)\n"
        "                    | ((uint16_t)ncm_interface.notification_xmit_is_running << 10)\n"
        "                    | ((uint16_t)ncm_interface.link_is_up << 11)\n"
        "                    | ((uint16_t)xfer_ok << 12);\n"
        "  } else if (ncm_interface.notification_xmit_state == NOTIFICATION_CONNECTED) {",
    ),
    # Patch 3c: Reorder SET_INTERFACE — ACK control status BEFORE notification
    (
        "          if (ncm_interface.itf_data_alt == 1) {\n"
        "            tud_network_recv_renew_r(rhport);\n"
        "            notification_xmit(rhport, false);\n"
        "          }\n"
        "          tud_control_status(rhport, request);",
        "          tud_control_status(rhport, request);\n"
        "          if (ncm_interface.itf_data_alt == 1) {\n"
        "            tud_network_recv_renew_r(rhport);\n"
        "            notification_xmit(rhport, false);\n"
        "          }",
    ),
    # Patch 4: Send notifications from netd_open (macOS needs them before SET_INTERFACE)
    (
        "  TU_ASSERT(usbd_open_edpt_pair(rhport, p_desc, 2, TUSB_XFER_BULK, &ncm_interface.ep_out, &ncm_interface.ep_in));\n"
        "  drv_len += 2 * sizeof(tusb_desc_endpoint_t);\n"
        "\n"
        "  return drv_len;\n"
        "} // netd_open",
        "  TU_ASSERT(usbd_open_edpt_pair(rhport, p_desc, 2, TUSB_XFER_BULK, &ncm_interface.ep_out, &ncm_interface.ep_in));\n"
        "  drv_len += 2 * sizeof(tusb_desc_endpoint_t);\n"
        "\n"
        "  // macOS requires SPEED + CONNECTED notifications before it sends SET_INTERFACE alt=1.\n"
        "  // Send them here during initial enumeration rather than waiting for SET_INTERFACE.\n"
        "  notification_xmit(rhport, false);\n"
        "\n"
        "  return drv_len;\n"
        "} // netd_open",
    ),
    # Patch 3d: Add debug markers in SET_INTERFACE handler
    (
        "          tud_control_status(rhport, request);\n"
        "          if (ncm_interface.itf_data_alt == 1) {\n"
        "            tud_network_recv_renew_r(rhport);\n"
        "            notification_xmit(rhport, false);\n"
        "          }",
        "          tud_control_status(rhport, request);\n"
        "          if (ncm_interface.itf_data_alt == 1) {\n"
        "            ncm_notif_debug = 0xAA00 | ncm_interface.ep_notif;\n"
        "            tud_network_recv_renew_r(rhport);\n"
        "            notification_xmit(rhport, false);\n"
        "          } else {\n"
        "            ncm_notif_debug = 0xBB00 | (uint16_t)request->wValue;\n"
        "          }",
    ),
]

if not os.path.exists(NCM_FILE):
    print(f"[patch_ncm_cmake] WARNING: {NCM_FILE} not found, skipping")
    sys.exit(0)

with open(NCM_FILE, "r") as f:
    content = f.read()

if MARKER in content:
    sys.exit(0)  # already patched

patched = content
applied = 0
for old, new in PATCHES:
    if old in patched:
        patched = patched.replace(old, new, 1)
        applied += 1

if applied > 0:
    patched = patched.replace(
        '#include "ncm.h"',
        '#include "ncm.h"\n' + MARKER,
        1,
    )
    with open(NCM_FILE, "w") as f:
        f.write(patched)
    print(f"[patch_ncm_cmake] Applied {applied}/{len(PATCHES)} patches to ncm_device.c")
else:
    print("[patch_ncm_cmake] WARNING: no patches matched")
