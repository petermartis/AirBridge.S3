"""
Pre-build script for PlatformIO (env:esp32s31 only).

Ensures sdkconfig.esp32s31's lwIP TCP buffer overrides (see
sdkconfig.s31.defaults for why -- NAT throughput was capped to
roughly window/RTT by lwIP's 5760-byte default window, ~7Mbit/s
measured on real hardware against a 1Gbit/s upstream) are present
*before* CMake/confgen runs, not after.

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
    "CONFIG_LWIP_TCP_SND_BUF_DEFAULT=65535",
    "CONFIG_LWIP_TCP_WND_DEFAULT=65535",
    "CONFIG_LWIP_TCP_RECVMBOX_SIZE=48",
    "CONFIG_LWIP_TCPIP_RECVMBOX_SIZE=64",
]

if os.path.isfile(sdkconfig_path):
    with open(sdkconfig_path, "r") as f:
        content = f.read()
    if "CONFIG_LWIP_TCP_WND_DEFAULT=65535" not in content:
        with open(sdkconfig_path, "a") as f:
            f.write("\n" + "\n".join(overrides) + "\n")
        print("patch_sdkconfig_s31: appended TCP buffer tuning to sdkconfig.esp32s31")
# If the file doesn't exist yet, there's nothing to patch -- a fresh
# confgen run will read sdkconfig.s31.defaults directly, and
# CMakeLists.txt's own file(APPEND) workaround catches that case on
# the build right after.
