"""
Pre-build script for PlatformIO (env:esp32s31 only).

Ensures sdkconfig.esp32s31's lwIP TCP buffer overrides (see
sdkconfig.s31.defaults for why -- NAT throughput was capped to
roughly window/RTT by lwIP's 5760-byte default window, ~7Mbit/s
measured on real hardware against a 1Gbit/s upstream) are present
*before* CMake/confgen runs, not after.

16384, not 65535: a first attempt at the max value (65535) caused
boot/reboot loops on real hardware -- ~128KB of internal SRAM per TCP
connection on a chip with only 327KB total, shared with the WiFi
driver, display, HTTP server and NAT state. 16384 (~32KB/connection)
still raises the window/RTT ceiling well past what the radio itself
can deliver, without the OOM risk.

CONFIG_ESP_WIFI_TX_BA_WIN/RX_BA_WIN are explicitly reverted to their
stock default (6) below, not just left out: a prior version of this
script appended =12 for both (ESP-IDF's own documented throughput
recommendation), which caused a 100%-reproducible crash -- boot got
to exactly "wifi_ap_init OK" every time and died before
"wifi_sta_start OK" ever printed, right where WiFi.begin() starts STA
association. Since this script's job is appending the LAST (and so
winning) occurrence of each key, simply removing these from the list
would leave any already-appended "=12" from a previous build as the
winning value forever -- these must be explicitly re-asserted at 6 to
actually override that.

Why this exists: board_build.sdkconfig_defaults isn't being applied
for these specific keys in this hybrid Arduino+ESP-IDF build -- even
a full clean (deleting sdkconfig.esp32s31 and the entire .pio/build/
esp32s31 cache) regenerates them at their raw Kconfig defaults
instead. CMakeLists.txt has a file(APPEND ...) workaround for this
same class of problem (see its comment, originally added for Arduino
USB OTG options), but that code runs as part of the same CMake
project() call that just finished generating sdkconfig.h -- so it
only takes effect on a *second* build, after the appended file is
read from the start. A plain `git pull` + one `pio run` would
silently keep the stale config. Running this before SCons invokes
CMake at all avoids that two-pass trap.
"""
import os

Import("env")

project_dir = env.subst("$PROJECT_DIR")
sdkconfig_path = os.path.join(project_dir, "sdkconfig.esp32s31")

overrides = [
    "CONFIG_LWIP_TCP_SND_BUF_DEFAULT=16384",
    "CONFIG_LWIP_TCP_WND_DEFAULT=16384",
    "CONFIG_LWIP_TCP_RECVMBOX_SIZE=16",
    # Explicit revert to stock default -- see the module docstring for
    # why this can't just be removed from the list.
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
# confgen run will read sdkconfig.s31.defaults directly, and
# CMakeLists.txt's own file(APPEND) workaround catches that case on
# the build right after.
