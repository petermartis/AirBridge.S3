cmake_minimum_required(VERSION 3.16.0)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ESP32GEEK-WIFI-AP)

# Patch TinyUSB and esp_tinyusb for macOS CDC-ECM compatibility.
# Must run here (during CMake configuration) because the ESP-IDF component
# manager re-extracts managed_components from cache earlier in this step,
# overwriting any patches applied from PlatformIO's SCons scripts.
execute_process(
    COMMAND python3 ${CMAKE_CURRENT_SOURCE_DIR}/patch_ecm_cmake.py
        ${CMAKE_CURRENT_SOURCE_DIR}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    RESULT_VARIABLE _patch_result
    OUTPUT_VARIABLE _patch_output
    ERROR_VARIABLE _patch_error
)
if(_patch_output)
    message(STATUS ${_patch_output})
endif()
if(_patch_error)
    message(WARNING "patch_ecm_cmake: ${_patch_error}")
endif()

# The esp_tinyusb CMakeLists.txt only compiles tinyusb_net.c for NCM mode.
# Our patch_ecm_cmake.py fixes this, but the patch runs AFTER project() has
# already evaluated the component CMakeLists.txt on a fresh configure.
# Work around by explicitly adding tinyusb_net.c to the component target.
if(CONFIG_TINYUSB_NET_MODE_ECM_RNDIS)
    idf_component_get_property(_esp_tinyusb_lib espressif__esp_tinyusb COMPONENT_LIB)
    target_sources(${_esp_tinyusb_lib} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/managed_components/espressif__esp_tinyusb/tinyusb_net.c
    )
endif()

# ESP-IDF Kconfig doesn't recognize Arduino-framework options
# stripped from sdkconfig on every CMake reconfiguration.  Re-append them.
set(_sdkconfig "${CMAKE_CURRENT_SOURCE_DIR}/sdkconfig.esp32s3geek")
if(EXISTS ${_sdkconfig})
    file(READ ${_sdkconfig} _sdk_content)
    string(FIND "${_sdk_content}" "CONFIG_ARDUINO_USB_MODE=0" _pos)
    if(_pos EQUAL -1)
        file(APPEND ${_sdkconfig} "\nCONFIG_ARDUINO_USB_MODE=0\nCONFIG_ARDUINO_USB_CDC_ON_BOOT=0\n")
        message(STATUS "Re-appended Arduino USB OTG settings to sdkconfig")
    endif()
endif()

# Same strip-on-reconfigure problem as above, for esp32s31's lwIP TCP
# buffer tuning (see sdkconfig.s31.defaults for why these values
# matter -- NAT throughput was capped to roughly window/RTT, ~7Mbit/s
# measured on real hardware against a 1Gbit/s upstream, by lwIP's
# 5760-byte default window). Confirmed on this project: even a full
# clean (deleting sdkconfig.esp32s31 and the entire .pio/build/
# esp32s31 cache) still regenerates these at their raw Kconfig
# defaults instead of sdkconfig.s31.defaults' values -- something in
# this hybrid build's config generation doesn't apply board_build.
# sdkconfig_defaults for these keys the way it does for most others.
#
# 16384, not 65535: a first attempt at the max value caused boot/
# reboot loops on real hardware (~128KB of internal SRAM per TCP
# connection on a 327KB-total chip -- see sdkconfig.s31.defaults).
set(_sdkconfig_s31 "${CMAKE_CURRENT_SOURCE_DIR}/sdkconfig.esp32s31")
if(EXISTS ${_sdkconfig_s31})
    file(READ ${_sdkconfig_s31} _sdk_content_s31)
    string(FIND "${_sdk_content_s31}" "CONFIG_LWIP_TCP_WND_DEFAULT=16384" _pos_s31)
    if(_pos_s31 EQUAL -1)
        file(APPEND ${_sdkconfig_s31}
            "\nCONFIG_LWIP_TCP_SND_BUF_DEFAULT=16384\nCONFIG_LWIP_TCP_WND_DEFAULT=16384\nCONFIG_LWIP_TCP_RECVMBOX_SIZE=16\n")
        message(STATUS "Re-appended TCP buffer tuning to sdkconfig.esp32s31")
    endif()
    # WiFi AMPDU block-ack window -- explicit revert to stock default
    # (6). Raising this to 12 (see git history / sdkconfig.s31.defaults)
    # caused a 100%-reproducible crash: boot got to exactly
    # "wifi_ap_init OK" every time and died before "wifi_sta_start OK"
    # ever printed, right where WiFi.begin() starts STA association.
    # Must be explicitly re-appended at 6, not just removed from this
    # script, or an already-appended "=12" from a previous build stays
    # the winning (last) occurrence forever.
    string(FIND "${_sdk_content_s31}" "CONFIG_ESP_WIFI_RX_BA_WIN=6" _pos_ba)
    if(_pos_ba EQUAL -1)
        file(APPEND ${_sdkconfig_s31}
            "\nCONFIG_ESP_WIFI_TX_BA_WIN=6\nCONFIG_ESP_WIFI_RX_BA_WIN=6\n")
        message(STATUS "Re-appended WiFi BA window revert to sdkconfig.esp32s31")
    endif()
endif()
