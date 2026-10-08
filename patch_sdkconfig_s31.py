"""
Pre-build script for PlatformIO (env:esp32s31 only).

Explicitly re-asserts the lwIP TCP buffer and WiFi AMPDU block-ack
window values from sdkconfig.s31.defaults into sdkconfig.esp32s31,
*before* CMake/confgen runs, not after. See sdkconfig.s31.defaults for
the full history: these were raised for throughput, then abandoned
after a reboot loop that was later root-caused (via esp_reset_reason()
logged over serial) to a BROWNOUT on a marginal USB power supply, not
these values -- it reproduced identically whether these were at their
raised values, a more conservative halfway point, or fully stock. Now
re-raised, with a proper power supply confirmed stable.

These values must be explicitly asserted here, not left to
sdkconfig.s31.defaults alone: a device that already has a *different*
value appended by a previous build of this project (e.g. the stock
values from when this was reverted) would otherwise keep that as the
winning (last) occurrence in sdkconfig.esp32s31 forever, since this
script (and CMakeLists.txt's matching fallback) work by appending the
last, and so winning, occurrence of each key.

Why this exists at all: board_build.sdkconfig_defaults isn't reliably
applied for these specific keys in this hybrid Arduino+ESP-IDF build
-- even a full clean (deleting sdkconfig.esp32s31 and the entire
.pio/build/esp32s31 cache) regenerates them at their raw Kconfig
defaults instead of sdkconfig.s31.defaults' values, for reasons never
fully root-caused. CMakeLists.txt has a matching file(APPEND ...)
workaround (see its comment, originally added for Arduino USB OTG
options), but that code runs as part of the same CMake project() call
that just finished generating sdkconfig.h -- so it only takes effect
on a *second* build, after the appended file is read from the start.
A plain `git pull` + one `pio run` would silently keep the stale
config. Running this before SCons invokes CMake at all avoids that
two-pass trap.
"""
import os

Import("env")

project_dir = env.subst("$PROJECT_DIR")
sdkconfig_path = os.path.join(project_dir, "sdkconfig.esp32s31")

# Must match sdkconfig.s31.defaults -- see the module docstring and
# that file's comment for the throughput/brownout history.
overrides = [
    "CONFIG_LWIP_TCP_SND_BUF_DEFAULT=65535",
    "CONFIG_LWIP_TCP_WND_DEFAULT=65535",
    "CONFIG_LWIP_TCP_RECVMBOX_SIZE=48",
    "CONFIG_LWIP_TCPIP_RECVMBOX_SIZE=64",
    "CONFIG_ESP_WIFI_TX_BA_WIN=12",
    "CONFIG_ESP_WIFI_RX_BA_WIN=12",
]

if os.path.isfile(sdkconfig_path):
    with open(sdkconfig_path, "r") as f:
        content = f.read()
    missing = [line for line in overrides if line not in content]
    if missing:
        with open(sdkconfig_path, "a") as f:
            f.write("\n" + "\n".join(missing) + "\n")
        print("patch_sdkconfig_s31: appended to sdkconfig.esp32s31: " + ", ".join(missing))
# If the file doesn't exist yet, there's nothing to patch -- a fresh
# confgen run will read sdkconfig.s31.defaults directly (which has
# nothing to override here now), and CMakeLists.txt's own
# file(APPEND) workaround catches the stale-value case on the build
# right after, same as this script does up front.
