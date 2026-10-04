"""
Pre-build script for PlatformIO (env:esp32s31 only).

Explicitly re-asserts stock lwIP TCP buffer and WiFi AMPDU block-ack
window values in sdkconfig.esp32s31, *before* CMake/confgen runs, not
after. These are reverts, not tuning: every attempt to raise them
caused boot/reboot loops on real hardware, including a 100%-
reproducible crash at 16384 (and also at 65535) -- every single boot
reaching exactly "wifi_ap_init OK" and dying before "wifi_sta_start
OK" ever printed, right where WiFi.begin() starts STA association
while AP mode is already up. Raising the AMPDU block-ack window
(TX/RX_BA_WIN) to 12 was tested independently and reverting it alone
did NOT fix the crash, ruling it out and leaving the TCP window as
the implicated cause -- most likely because lwIP needs more memory up
front to bring up a second network interface (STA, on top of the
already-running AP) when these buffer defaults are larger, not just a
per-active-connection cost as originally assumed. See
sdkconfig.s31.defaults for the full investigation.

These values must be explicitly re-asserted at their stock defaults,
not just removed from this script: a device that already had a larger
value appended by a previous build of this project would otherwise
keep that as the winning (last) occurrence in sdkconfig.esp32s31
forever, since this script (and CMakeLists.txt's matching fallback)
work by appending the last, and so winning, occurrence of each key.

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

# All reverts to stock Kconfig defaults -- see the module docstring.
overrides = [
    "CONFIG_LWIP_TCP_SND_BUF_DEFAULT=5760",
    "CONFIG_LWIP_TCP_WND_DEFAULT=5760",
    "CONFIG_LWIP_TCP_RECVMBOX_SIZE=6",
    "CONFIG_ESP_WIFI_TX_BA_WIN=6",
    "CONFIG_ESP_WIFI_RX_BA_WIN=6",
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
