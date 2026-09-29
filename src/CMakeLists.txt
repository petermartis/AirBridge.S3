FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.cpp ${CMAKE_SOURCE_DIR}/src/*.c)

# Two board variants share this tree but ship mutually-exclusive display
# implementations (different panel, different UI layout). Keep only the
# one matching the target chip out of the glob above so their duplicate
# display_init()/display_update()/etc. symbols don't collide at link time.
idf_build_get_property(_airbridge_target IDF_TARGET)
if(_airbridge_target STREQUAL "esp32s3")
    list(REMOVE_ITEM app_sources ${CMAKE_SOURCE_DIR}/src/display_s31.cpp)
elseif(_airbridge_target STREQUAL "esp32s31")
    list(REMOVE_ITEM app_sources ${CMAKE_SOURCE_DIR}/src/display_s3geek.cpp)
endif()

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
