"""Patch TinyUSB and esp_tinyusb for macOS CDC-ECM compatibility.

Invoked by CMakeLists.txt via execute_process() during CMake configuration,
AFTER the component manager has extracted managed_components.

Patches applied:
  1. esp_tinyusb/CMakeLists.txt  — add tinyusb_net.c for ECM mode
  2. esp_tinyusb/usb_descriptors.c — add ECM descriptor support
  3. esp_tinyusb/descriptors_control.c — add ECM to default descriptor fallback
  4. tinyusb ecm_rndis_device.c — 100 Mbps speed, debug variable, speed notification
"""

import os
import sys

if len(sys.argv) < 2:
    print("[patch_ecm_cmake] ERROR: no base path provided", file=sys.stderr)
    sys.exit(1)

BASE = sys.argv[1]  # project root (managed_components parent)
MARKER = "// [AirBridge.S3 ECM patched]"

ESP_TINYUSB = os.path.join(BASE, "managed_components", "espressif__esp_tinyusb")
TINYUSB = os.path.join(BASE, "managed_components", "espressif__tinyusb")


def patch_file(filepath, patches):
    """Apply text patches idempotently. Each patch is applied if its search
    string matches; already-applied patches are silently skipped."""
    if not os.path.exists(filepath):
        print(f"[patch_ecm_cmake] WARNING: {filepath} not found, skipping")
        return 0

    with open(filepath, "r") as f:
        content = f.read()

    patched = content
    applied = 0
    for old, new in patches:
        if old in patched:
            patched = patched.replace(old, new, 1)
            applied += 1

    if applied > 0 and patched != content:
        with open(filepath, "w") as f:
            f.write(patched)

    return applied


# =========================================================================
# Patch 1: esp_tinyusb/CMakeLists.txt — add tinyusb_net.c for ECM mode
# =========================================================================
cmake_patches = [
    (
        'if(CONFIG_TINYUSB_NET_MODE_NCM)\n'
        '    list(APPEND srcs\n'
        '         "tinyusb_net.c"\n'
        '         )\n'
        'endif() # CONFIG_TINYUSB_NET_MODE_NCM',

        'if(CONFIG_TINYUSB_NET_MODE_NCM OR CONFIG_TINYUSB_NET_MODE_ECM_RNDIS)\n'
        '    list(APPEND srcs\n'
        '         "tinyusb_net.c"\n'
        '         )\n'
        'endif() # CONFIG_TINYUSB_NET_MODE_NCM or ECM_RNDIS',
    ),
]

cmake_file = os.path.join(ESP_TINYUSB, "CMakeLists.txt")
n = patch_file(cmake_file, cmake_patches)
if n > 0:
    print(f"[patch_ecm_cmake] CMakeLists.txt: {n} patch(es) applied")
else:
    print("[patch_ecm_cmake] CMakeLists.txt: already patched (or not found)")


# =========================================================================
# Patch 2: esp_tinyusb/usb_descriptors.c — add ECM descriptor support
# =========================================================================
desc_patches = [
    # 2a: Device descriptor class — set IAD class for ECM (and NCM)
    (
        '#if CFG_TUD_CDC\n'
        '    // Use Interface Association Descriptor (IAD) for CDC\n'
        '    // As required by USB Specs IAD\'s subclass must be common class (2) and protocol must be IAD (1)\n'
        '    .bDeviceClass = TUSB_CLASS_MISC,\n'
        '    .bDeviceSubClass = MISC_SUBCLASS_COMMON,\n'
        '    .bDeviceProtocol = MISC_PROTOCOL_IAD,',

        '#if CFG_TUD_CDC || CFG_TUD_ECM_RNDIS || CFG_TUD_NCM\n'
        '    // Use Interface Association Descriptor (IAD) for CDC / ECM / NCM\n'
        '    // As required by USB Specs IAD\'s subclass must be common class (2) and protocol must be IAD (1)\n'
        '    .bDeviceClass = TUSB_CLASS_MISC,\n'
        '    .bDeviceSubClass = MISC_SUBCLASS_COMMON,\n'
        '    .bDeviceProtocol = MISC_PROTOCOL_IAD,',
    ),
    # 2b: Interface enum — broaden NCM guard to include ECM
    (
        '#if CFG_TUD_NCM\n'
        '    ITF_NUM_NET,\n'
        '    ITF_NUM_NET_DATA,\n'
        '#endif',

        '#if CFG_TUD_NCM || CFG_TUD_ECM_RNDIS\n'
        '    ITF_NUM_NET,\n'
        '    ITF_NUM_NET_DATA,\n'
        '#endif',
    ),
    # 2b: Total descriptor length — add ECM length contribution
    (
        '                          CFG_TUD_NCM * TUD_CDC_NCM_DESC_LEN +',

        '                          CFG_TUD_NCM * TUD_CDC_NCM_DESC_LEN +\n'
        '                          CFG_TUD_ECM_RNDIS * TUD_CDC_ECM_DESC_LEN +',
    ),
    # 2c: Endpoint enum — broaden NCM guard to include ECM
    (
        '#if CFG_TUD_NCM\n'
        '    EPNUM_NET_NOTIF,\n'
        '    EPNUM_NET_DATA,\n'
        '#endif',

        '#if CFG_TUD_NCM || CFG_TUD_ECM_RNDIS\n'
        '    EPNUM_NET_NOTIF,\n'
        '    EPNUM_NET_DATA,\n'
        '#endif',
    ),
    # 2d: STRID enum — broaden NCM guard to include ECM
    (
        '#if CFG_TUD_NCM\n'
        '    STRID_NET_INTERFACE,\n'
        '    STRID_MAC,\n'
        '#endif',

        '#if CFG_TUD_NCM || CFG_TUD_ECM_RNDIS\n'
        '    STRID_NET_INTERFACE,\n'
        '    STRID_MAC,\n'
        '#endif',
    ),
    # 2e: FS config descriptor — add ECM descriptor block after NCM block
    (
        '#if CFG_TUD_NCM\n'
        '    // Interface number, description string index, MAC address string index, EP notification address and size, EP data address (out, in), and size, max segment size.\n'
        '    TUD_CDC_NCM_DESCRIPTOR(ITF_NUM_NET, STRID_NET_INTERFACE, STRID_MAC, (0x80 | EPNUM_NET_NOTIF), 64, EPNUM_NET_DATA, (0x80 | EPNUM_NET_DATA), 64, CFG_TUD_NET_MTU),\n'
        '#endif',

        '#if CFG_TUD_NCM\n'
        '    // Interface number, description string index, MAC address string index, EP notification address and size, EP data address (out, in), and size, max segment size.\n'
        '    TUD_CDC_NCM_DESCRIPTOR(ITF_NUM_NET, STRID_NET_INTERFACE, STRID_MAC, (0x80 | EPNUM_NET_NOTIF), 64, EPNUM_NET_DATA, (0x80 | EPNUM_NET_DATA), 64, CFG_TUD_NET_MTU),\n'
        '#endif\n'
        '\n'
        '#if CFG_TUD_ECM_RNDIS\n'
        '    // CDC-ECM: Interface number, description string index, MAC address string index, EP notification address and size, EP data address (out, in), and size, max segment size.\n'
        '    TUD_CDC_ECM_DESCRIPTOR(ITF_NUM_NET, STRID_NET_INTERFACE, STRID_MAC, (0x80 | EPNUM_NET_NOTIF), 64, EPNUM_NET_DATA, (0x80 | EPNUM_NET_DATA), 64, CFG_TUD_NET_MTU),\n'
        '#endif',
    ),
    # 2f: tusb_get_mac_string_id — broaden NCM guard to include ECM
    (
        '#if CFG_TUD_NCM\n'
        'uint8_t tusb_get_mac_string_id(void)\n'
        '{\n'
        '    return STRID_MAC;\n'
        '}\n'
        '#endif',

        '#if CFG_TUD_NCM || CFG_TUD_ECM_RNDIS\n'
        'uint8_t tusb_get_mac_string_id(void)\n'
        '{\n'
        '    return STRID_MAC;\n'
        '}\n'
        '#endif',
    ),
]

desc_file = os.path.join(ESP_TINYUSB, "usb_descriptors.c")
n = patch_file(desc_file, desc_patches)
if n > 0:
    print(f"[patch_ecm_cmake] usb_descriptors.c: {n}/{len(desc_patches)} patches applied")
else:
    print("[patch_ecm_cmake] usb_descriptors.c: already patched (or no matches)")


# =========================================================================
# Patch 3: esp_tinyusb/descriptors_control.c — add ECM to fallback check
# =========================================================================
ctrl_patches = [
    # Full-speed fallback
    (
        '#if (CFG_TUD_CDC > 0 || CFG_TUD_MSC > 0 || CFG_TUD_NCM > 0)\n'
        '        // We provide default config descriptors only for CDC, MSC and NCM classes',

        '#if (CFG_TUD_CDC > 0 || CFG_TUD_MSC > 0 || CFG_TUD_NCM > 0 || CFG_TUD_ECM_RNDIS > 0)\n'
        '        // We provide default config descriptors only for CDC, MSC, NCM, and ECM classes',
    ),
]

# The same pattern appears twice (FS and HS) — patch both occurrences
ctrl_file = os.path.join(ESP_TINYUSB, "descriptors_control.c")
if os.path.exists(ctrl_file):
    with open(ctrl_file, "r") as f:
        ctrl_content = f.read()
    ctrl_patched = ctrl_content
    ctrl_applied = 0
    for old, new in ctrl_patches:
        # Replace ALL occurrences (FS + HS blocks)
        count = ctrl_patched.count(old)
        if count > 0:
            ctrl_patched = ctrl_patched.replace(old, new)
            ctrl_applied += count
    if ctrl_applied > 0 and ctrl_patched != ctrl_content:
        with open(ctrl_file, "w") as f:
            f.write(ctrl_patched)
        print(f"[patch_ecm_cmake] descriptors_control.c: {ctrl_applied} occurrence(s) patched")
    else:
        print("[patch_ecm_cmake] descriptors_control.c: already patched")
else:
    print(f"[patch_ecm_cmake] WARNING: {ctrl_file} not found")


# =========================================================================
# Patch 4: ecm_rndis_device.c — breadcrumbs + ECM compatibility
# =========================================================================
ecm_patches = [
    # 4a: Add extern for RTC NOINIT breadcrumb
    (
        '#include "net_device.h"\n'
        '#include "rndis_protocol.h"',

        '#include "net_device.h"\n'
        '#include "rndis_protocol.h"\n'
        '\n'
        '// [AirBridge.S3] RTC NOINIT breadcrumbs for crash debugging\n'
        'extern volatile uint32_t g_ecm_crash_stage;',
    ),
    # 4b: Breadcrumb at netd_open entry
    (
        'uint16_t netd_open(uint8_t rhport, tusb_desc_interface_t const * itf_desc, uint16_t max_len) {\n'
        '  bool const is_rndis',

        'uint16_t netd_open(uint8_t rhport, tusb_desc_interface_t const * itf_desc, uint16_t max_len) {\n'
        '  g_ecm_crash_stage = 0x10; // entered netd_open\n'
        '  bool const is_rndis',
    ),
    # 4c: Breadcrumb after is_ecm check
    (
        'TU_VERIFY(is_rndis || is_ecm, 0);\n'
        '\n'
        '  // confirm interface',

        'TU_VERIFY(is_rndis || is_ecm, 0);\n'
        '  g_ecm_crash_stage = 0x11; // is_ecm/is_rndis check passed\n'
        '\n'
        '  // confirm interface',
    ),
    # 4d: Breadcrumb before notification EP open
    (
        '  // notification endpoint (if any)\n'
        '  if (TUSB_DESC_ENDPOINT == tu_desc_type(p_desc)) {',

        '  g_ecm_crash_stage = 0x12; // about to open notification endpoint\n'
        '  // notification endpoint (if any)\n'
        '  if (TUSB_DESC_ENDPOINT == tu_desc_type(p_desc)) {',
    ),
    # 4e: Breadcrumb after notification EP opened
    (
        '_netd_itf.ep_notif = ((tusb_desc_endpoint_t const*)p_desc)->bEndpointAddress;\n'
        '\n'
        '    drv_len += tu_desc_len(p_desc);',

        '_netd_itf.ep_notif = ((tusb_desc_endpoint_t const*)p_desc)->bEndpointAddress;\n'
        '    g_ecm_crash_stage = 0x13; // notification EP opened OK\n'
        '\n'
        '    drv_len += tu_desc_len(p_desc);',
    ),
    # 4f: Breadcrumb before data interface processing
    (
        '  //   - 1 : IN & OUT endpoints for active networking\n'
        '  TU_ASSERT(TUSB_DESC_INTERFACE == tu_desc_type(p_desc), 0);',

        '  //   - 1 : IN & OUT endpoints for active networking\n'
        '  g_ecm_crash_stage = 0x14; // about to process data interface\n'
        '  TU_ASSERT(TUSB_DESC_INTERFACE == tu_desc_type(p_desc), 0);',
    ),
    # 4g: Breadcrumb before endpoint pair check
    (
        '  // Pair of endpoints\n'
        '  TU_ASSERT(TUSB_DESC_ENDPOINT == tu_desc_type(p_desc), 0);',

        '  g_ecm_crash_stage = 0x15; // about to check endpoint pair\n'
        '  // Pair of endpoints\n'
        '  TU_ASSERT(TUSB_DESC_ENDPOINT == tu_desc_type(p_desc), 0);',
    ),
    # 4h: Breadcrumb at return
    (
        '  drv_len += 2*sizeof(tusb_desc_endpoint_t);\n'
        '\n'
        '  return drv_len;',

        '  drv_len += 2*sizeof(tusb_desc_endpoint_t);\n'
        '\n'
        '  g_ecm_crash_stage = 0x16; // netd_open returning\n'
        '  return drv_len;',
    ),
]

ecm_file = os.path.join(TINYUSB, "src", "class", "net", "ecm_rndis_device.c")
n = patch_file(ecm_file, ecm_patches)
if n > 0:
    print(f"[patch_ecm_cmake] ecm_rndis_device.c: {n}/{len(ecm_patches)} breadcrumb patches applied")
else:
    print("[patch_ecm_cmake] ecm_rndis_device.c: already patched (or no matches)")


# =========================================================================
# Patch 5: usbd.c — breadcrumbs at ISR, event, task, and process_set_config
# =========================================================================
usbd_patches = [
    # 5pre_a: File-scope extern so breadcrumbs visible to all functions
    (
        '#include "device/usbd.h"\n'
        '#include "device/usbd_pvt.h"',

        '#include "device/usbd.h"\n'
        '#include "device/usbd_pvt.h"\n'
        '\n'
        '// [AirBridge.S3] RTC NOINIT breadcrumbs for crash debugging (file-scope)\n'
        'extern volatile uint32_t g_ecm_crash_stage;',
    ),
    # 5pre_b: Breadcrumb in tud_task_ext after event dequeue
    (
        '    dcd_event_t event;\n'
        '    if (!osal_queue_receive(_usbd_q, &event, timeout_ms)) return;\n'
        '\n'
        '#if CFG_TUSB_DEBUG >= CFG_TUD_LOG_LEVEL',

        '    dcd_event_t event;\n'
        '    if (!osal_queue_receive(_usbd_q, &event, timeout_ms)) return;\n'
        '    g_ecm_crash_stage = 0x70 | (event.event_id & 0x0F); // task: event dequeued\n'
        '\n'
        '#if CFG_TUSB_DEBUG >= CFG_TUD_LOG_LEVEL',
    ),
    # 5pre_c: Breadcrumb in dcd_event_handler entry (ISR context)
    (
        'TU_ATTR_FAST_FUNC void dcd_event_handler(dcd_event_t const* event, bool in_isr) {\n'
        '  bool send = false;',

        'TU_ATTR_FAST_FUNC void dcd_event_handler(dcd_event_t const* event, bool in_isr) {\n'
        '  g_ecm_crash_stage = 0x60 | (event->event_id & 0x0F); // event handler (ISR ctx)\n'
        '  bool send = false;',
    ),
    # 5pre_d: Breadcrumbs in BUS_RESET event handler
    (
        '      case DCD_EVENT_BUS_RESET:\n'
        '        TU_LOG_USBD(": %s Speed\\r\\n", tu_str_speed[event.bus_reset.speed]);\n'
        '        usbd_reset(event.rhport);\n'
        '        _usbd_dev.speed = event.bus_reset.speed;\n'
        '        break;',

        '      case DCD_EVENT_BUS_RESET:\n'
        '        g_ecm_crash_stage = 0x80; // BUS_RESET: about to log\n'
        '        TU_LOG_USBD(": %s Speed\\r\\n", tu_str_speed[event.bus_reset.speed]);\n'
        '        g_ecm_crash_stage = 0x81; // BUS_RESET: about to call usbd_reset\n'
        '        usbd_reset(event.rhport);\n'
        '        g_ecm_crash_stage = 0x82; // BUS_RESET: usbd_reset returned\n'
        '        _usbd_dev.speed = event.bus_reset.speed;\n'
        '        g_ecm_crash_stage = 0x83; // BUS_RESET: done\n'
        '        break;',
    ),
    # 5pre_e: Breadcrumbs in configuration_reset
    (
        'static void configuration_reset(uint8_t rhport) {\n'
        '  for (uint8_t i = 0; i < TOTAL_DRIVER_COUNT; i++) {\n'
        '    usbd_class_driver_t const* driver = get_driver(i);\n'
        '    TU_ASSERT(driver,);\n'
        '    driver->reset(rhport);\n'
        '  }\n'
        '\n'
        '  tu_varclr(&_usbd_dev);',

        'static void configuration_reset(uint8_t rhport) {\n'
        '  g_ecm_crash_stage = 0x84; // config_reset: before driver loop\n'
        '  for (uint8_t i = 0; i < TOTAL_DRIVER_COUNT; i++) {\n'
        '    usbd_class_driver_t const* driver = get_driver(i);\n'
        '    TU_ASSERT(driver,);\n'
        '    g_ecm_crash_stage = 0x85; // config_reset: about to call driver->reset\n'
        '    driver->reset(rhport);\n'
        '    g_ecm_crash_stage = 0x86; // config_reset: driver->reset returned\n'
        '  }\n'
        '\n'
        '  g_ecm_crash_stage = 0x87; // config_reset: about to clear usbd_dev\n'
        '  tu_varclr(&_usbd_dev);',
    ),
    # 5a: entry breadcrumb for process_set_config
    (
        '// Process Set Configure Request\n'
        '// This function parse configuration descriptor & open drivers accordingly\n'
        'static bool process_set_config(uint8_t rhport, uint8_t cfg_num)\n'
        '{\n'
        '  // index is cfg_num-1',

        '// Process Set Configure Request\n'
        '// This function parse configuration descriptor & open drivers accordingly\n'
        'static bool process_set_config(uint8_t rhport, uint8_t cfg_num)\n'
        '{\n'
        '  g_ecm_crash_stage = 0xB0; // entered process_set_config\n'
        '  // index is cfg_num-1',
    ),
    # 5b: After getting descriptor
    (
        'tusb_desc_configuration_t const * desc_cfg = (tusb_desc_configuration_t const *) tud_descriptor_configuration_cb(cfg_num-1);\n'
        '  TU_ASSERT(desc_cfg',

        'tusb_desc_configuration_t const * desc_cfg = (tusb_desc_configuration_t const *) tud_descriptor_configuration_cb(cfg_num-1);\n'
        '  g_ecm_crash_stage = 0xB1; // got descriptor, about to assert\n'
        '  TU_ASSERT(desc_cfg',
    ),
    # 5c: Entering parse loop
    (
        'uint8_t const * desc_end = ((uint8_t const*) desc_cfg) + tu_le16toh(desc_cfg->wTotalLength);\n'
        '\n'
        '  while( p_desc < desc_end )',

        'uint8_t const * desc_end = ((uint8_t const*) desc_cfg) + tu_le16toh(desc_cfg->wTotalLength);\n'
        '\n'
        '  g_ecm_crash_stage = 0xB2; // entering descriptor parse loop\n'
        '  while( p_desc < desc_end )',
    ),
    # 5d: After IAD found
    (
        'p_desc = tu_desc_next(p_desc); // next to Interface\n'
        '\n'
        '      // IAD',

        'p_desc = tu_desc_next(p_desc); // next to Interface\n'
        '      g_ecm_crash_stage = 0xB3; // found IAD, advanced past it\n'
        '\n'
        '      // IAD',
    ),
    # 5e: Before INTERFACE assert
    (
        '    }\n'
        '\n'
        '    TU_ASSERT( TUSB_DESC_INTERFACE == tu_desc_type(p_desc) );',

        '    }\n'
        '\n'
        '    g_ecm_crash_stage = 0xB4; // about to assert TUSB_DESC_INTERFACE\n'
        '    TU_ASSERT( TUSB_DESC_INTERFACE == tu_desc_type(p_desc) );',
    ),
    # 5f: Before driver loop
    (
        'uint8_t drv_id;\n'
        '    for (drv_id = 0; drv_id < TOTAL_DRIVER_COUNT; drv_id++)',

        'uint8_t drv_id;\n'
        '    g_ecm_crash_stage = 0xB5; // about to try drivers\n'
        '    for (drv_id = 0; drv_id < TOTAL_DRIVER_COUNT; drv_id++)',
    ),
    # 5g: Before and after driver->open
    (
        'TU_ASSERT(driver);\n'
        '      uint16_t const drv_len = driver->open(rhport, desc_itf, remaining_len);',

        'TU_ASSERT(driver);\n'
        '      g_ecm_crash_stage = 0xB6; // about to call driver->open\n'
        '      uint16_t const drv_len = driver->open(rhport, desc_itf, remaining_len);\n'
        '      g_ecm_crash_stage = 0xB7; // driver->open returned',
    ),
]

usbd_file = os.path.join(TINYUSB, "src", "device", "usbd.c")
n = patch_file(usbd_file, usbd_patches)
if n > 0:
    print(f"[patch_ecm_cmake] usbd.c: {n}/{len(usbd_patches)} breadcrumb patches applied")
else:
    print("[patch_ecm_cmake] usbd.c: already patched (or no matches)")


# =========================================================================
# Patch 6: dcd_dwc2.c — ISR-level breadcrumbs in dcd_int_handler()
# =========================================================================
dwc2_patches = [
    # 6a: Add extern for RTC NOINIT breadcrumb
    (
        '#include "device/dcd.h"\n'
        '#include "device/usbd_pvt.h"\n'
        '#include "dwc2_common.h"',

        '#include "device/dcd.h"\n'
        '#include "device/usbd_pvt.h"\n'
        '#include "dwc2_common.h"\n'
        '\n'
        '// [AirBridge.S3] RTC NOINIT breadcrumbs for ISR crash debugging\n'
        'extern volatile uint32_t g_ecm_crash_stage;',
    ),
    # 6b: ISR entry breadcrumb
    (
        'void dcd_int_handler(uint8_t rhport) {\n'
        '  dwc2_regs_t* dwc2 = DWC2_REG(rhport);',

        'void dcd_int_handler(uint8_t rhport) {\n'
        '  g_ecm_crash_stage = 0x50; // ISR entry\n'
        '  dwc2_regs_t* dwc2 = DWC2_REG(rhport);',
    ),
    # 6c: USB Reset breadcrumb
    (
        '  if (gintsts & GINTSTS_USBRST) {\n'
        '    // USBRST is start of reset.',

        '  if (gintsts & GINTSTS_USBRST) {\n'
        '    g_ecm_crash_stage = 0x51; // ISR: USB reset\n'
        '    // USBRST is start of reset.',
    ),
    # 6d: Enum done breadcrumb
    (
        '  if (gintsts & GINTSTS_ENUMDNE) {\n'
        '    // ENUMDNE is the end of reset',

        '  if (gintsts & GINTSTS_ENUMDNE) {\n'
        '    g_ecm_crash_stage = 0x52; // ISR: enum done\n'
        '    // ENUMDNE is the end of reset',
    ),
    # 6e: Suspend breadcrumb
    (
        '  if (gintsts & GINTSTS_USBSUSP) {\n'
        '    dwc2->gintsts = GINTSTS_USBSUSP;',

        '  if (gintsts & GINTSTS_USBSUSP) {\n'
        '    g_ecm_crash_stage = 0x53; // ISR: suspend\n'
        '    dwc2->gintsts = GINTSTS_USBSUSP;',
    ),
    # 6f: OUT EP breadcrumb
    (
        '  // OUT endpoint interrupt handling.\n'
        '  if (gintsts & GINTSTS_OEPINT) {',

        '  // OUT endpoint interrupt handling.\n'
        '  if (gintsts & GINTSTS_OEPINT) {\n'
        '    g_ecm_crash_stage = 0x54; // ISR: OUT EP',
    ),
    # 6g: IN EP breadcrumb
    (
        '  // IN endpoint interrupt handling.\n'
        '  if (gintsts & GINTSTS_IEPINT) {',

        '  // IN endpoint interrupt handling.\n'
        '  if (gintsts & GINTSTS_IEPINT) {\n'
        '    g_ecm_crash_stage = 0x55; // ISR: IN EP',
    ),
    # 6h: SOF breadcrumb
    (
        '  if(gintsts & GINTSTS_SOF) {\n'
        '    dwc2->gintsts = GINTSTS_SOF;',

        '  if(gintsts & GINTSTS_SOF) {\n'
        '    g_ecm_crash_stage = 0x56; // ISR: SOF\n'
        '    dwc2->gintsts = GINTSTS_SOF;',
    ),
    # 6i: ISR completed breadcrumb
    (
        '    handle_incomplete_iso_in(rhport);\n'
        '  }\n'
        '}\n'
        '\n'
        '#if CFG_TUD_TEST_MODE',

        '    handle_incomplete_iso_in(rhport);\n'
        '  }\n'
        '\n'
        '  g_ecm_crash_stage = 0x5F; // ISR completed OK\n'
        '}\n'
        '\n'
        '#if CFG_TUD_TEST_MODE',
    ),
]

dwc2_file = os.path.join(TINYUSB, "src", "portable", "synopsys", "dwc2", "dcd_dwc2.c")
n = patch_file(dwc2_file, dwc2_patches)
if n > 0:
    print(f"[patch_ecm_cmake] dcd_dwc2.c: {n}/{len(dwc2_patches)} ISR breadcrumb patches applied")
else:
    print("[patch_ecm_cmake] dcd_dwc2.c: already patched (or no matches)")
