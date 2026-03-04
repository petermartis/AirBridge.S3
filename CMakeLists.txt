cmake_minimum_required(VERSION 3.16.0)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ESP32GEEK-WIFI-AP)

# Patch TinyUSB NCM driver for macOS compatibility.
# Must run here (during CMake configuration) because the ESP-IDF component
# manager re-extracts managed_components from cache earlier in this step,
# overwriting any patches applied from PlatformIO's SCons scripts.
execute_process(
    COMMAND python3 ${CMAKE_CURRENT_SOURCE_DIR}/patch_ncm_cmake.py
        ${CMAKE_CURRENT_SOURCE_DIR}/managed_components/espressif__tinyusb/src/class/net/ncm_device.c
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    RESULT_VARIABLE _patch_result
    OUTPUT_VARIABLE _patch_output
    ERROR_VARIABLE _patch_error
)
if(_patch_output)
    message(STATUS ${_patch_output})
endif()
if(_patch_error)
    message(WARNING "patch_ncm_cmake: ${_patch_error}")
endif()

# ESP-IDF Kconfig doesn't recognize Arduino-framework options, so they get
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
