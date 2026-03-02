FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.cpp ${CMAKE_SOURCE_DIR}/src/*.c)

idf_component_register(
    SRCS ${app_sources}
    INCLUDE_DIRS "."
    REQUIRES
        framework-arduinoespressif32
        esp_wifi
        esp_netif
        nvs_flash
        esp_event
        lwip
        esp_driver_spi
        esp_driver_gpio
        tinyusb
)
