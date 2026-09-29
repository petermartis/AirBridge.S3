"""PlatformIO pre-build hook: teach LovyanGFX about the ESP32-S31 target.

LovyanGFX (through at least v1.2.30) predates the ESP32-S31 and has no
CONFIG_IDF_TARGET_ESP32S31 branch anywhere, so it falls through to code
paths written for other chips that don't quite match. AirBridge.S3 only
ever uses lgfx::Bus_SPI on this target (see LGFX_Config_s31.h) — no
parallel bus, no I2C — so every patch below is scoped to making SPI work,
not to making the other peripherals correct.

1. device.hpp's platform switch has no S31 case, so it falls into the
   generic "#else" written for the original classic ESP32. That branch
   unconditionally includes esp32/Bus_Parallel8.hpp, which needs
   <rom/lldesc.h> — a header ESP-IDF only ships for targets it has an
   esp_rom/<target> component for, and as of ESP-IDF v6.1.0 that
   component doesn't exist yet for esp32s31. Fix: add an S31 branch with
   just Light_PWM + Bus_SPI (no Bus_I2C — see point 4).

2. common.hpp's fast GPIO helpers have two implementations: a modern one
   (struct-typed `GPIO.out_w1ts.val` registers) used by C2/C3/C5/C6/C61/H2,
   and a legacy one (raw `GPIO.out_w1ts` + dual-bank pin>=32 handling) for
   classic ESP32. S31 falls into the legacy "#else" by default, but its
   SoC headers use the modern struct-typed registers like its RISC-V
   siblings, so the legacy code fails to compile. Fix: add S31 to the
   modern branch. Caveat: that branch (like its C2/C3/etc. siblings)
   doesn't implement the pin>=32 dual-bank path the legacy branch has —
   fine here since every pin AirBridge.S3 drives on the S31 (SPI
   CS/DC/RST/SCK/MOSI) is below GPIO32, but worth knowing if this project
   ever wires the display to a higher pin.

3. Bus_SPI.hpp — which we DO use — separately needs lldesc_t for its own
   DMA descriptors, via the same missing <rom/lldesc.h>. Unlike the ROM
   header, <soc/lldesc.h> is chip-generic and already ships for every
   target (S31 included), so we add it as a final fallback in Bus_SPI's
   own __has_include chain.

4. common.inl's `i2c::` namespace and Bus_I2C.inl are compiled
   unconditionally for every ESP_PLATFORM target (regardless of what
   device.hpp includes — Bus_I2C.inl #includes Bus_I2C.hpp itself), and
   assume a legacy i2c_dev_t register layout. The S31's I2C peripheral is
   different enough (its SoC header has no `fifo_data`, `status_reg`,
   `clk_conf`, `.period`/`.time`/`.nack` union members those functions
   reference, plus an undeclared `LP_I2C_SCLK_XTAL_D2`) that this isn't a
   couple of renamed fields — it's a different register set entirely, and
   guessing at a correct mapping without S31 documentation would be worse
   than not having I2C. Since this project never uses I2C, both are
   skipped outright for CONFIG_IDF_TARGET_ESP32S31 rather than patched.

Safe to drop all of these once upstream LovyanGFX adds real ESP32-S31
support.
"""

import os

Import("env")  # noqa: F821 — injected by PlatformIO's SConscript

libdeps_dir = env.subst(os.path.join("$PROJECT_LIBDEPS_DIR", "$PIOENV"))
platforms_dir = os.path.join(
    libdeps_dir, "LovyanGFX", "src", "lgfx", "v1", "platforms"
)


def patch_file(relpath, marker, old, new):
    path = os.path.join(platforms_dir, relpath)
    if not os.path.exists(path):
        print(f"[patch_lovyangfx_s31] WARNING: {path} not found, skipping")
        return
    with open(path, "r") as f:
        content = f.read()
    if marker in content:
        print(f"[patch_lovyangfx_s31] {relpath}: already patched")
    elif old not in content:
        print(
            f"[patch_lovyangfx_s31] WARNING: expected anchor text not found "
            f"in {relpath} (LovyanGFX version changed upstream?) — patch "
            f"NOT applied, build will likely fail again"
        )
    else:
        with open(path, "w") as f:
            f.write(content.replace(old, new, 1))
        print(f"[patch_lovyangfx_s31] {relpath}: patched")


# 1. device.hpp — add an S31 branch before the ESP32H2 one (SPI only —
# no Bus_I2C.hpp, see point 4)
patch_file(
    "device.hpp",
    "// [AirBridge.S3 S31 patched: device]",
    " #elif defined (CONFIG_IDF_TARGET_ESP32H2)\n",
    (
        " #elif defined (CONFIG_IDF_TARGET_ESP32S31)"
        "  // [AirBridge.S3 S31 patched: device]\n"
        "\n"
        "  #include \"esp32/Light_PWM.hpp\"\n"
        "  #include \"esp32/Bus_SPI.hpp\"\n"
        "\n"
        " #elif defined (CONFIG_IDF_TARGET_ESP32H2)\n"
    ),
)

# 2. common.hpp — add S31 to the modern struct-typed GPIO register branch
# (anchor includes the C61 prefix so it can't match the unrelated
# "#if defined ( CONFIG_IDF_TARGET_ESP32H2 )" SPI-register-macro block
# earlier in the same file)
patch_file(
    "esp32/common.hpp",
    "// [AirBridge.S3 S31 patched: common]",
    "defined ( CONFIG_IDF_TARGET_ESP32C61 ) || defined ( CONFIG_IDF_TARGET_ESP32H2 )\n",
    "defined ( CONFIG_IDF_TARGET_ESP32C61 ) || defined ( CONFIG_IDF_TARGET_ESP32H2 )"
    " || defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: common]\n",
)

# 3. Bus_SPI.hpp — add a chip-generic <soc/lldesc.h> fallback
patch_file(
    "esp32/Bus_SPI.hpp",
    "// [AirBridge.S3 S31 patched: Bus_SPI]",
    "#elif __has_include(<esp32/rom/lldesc.h>)\n #include <esp32/rom/lldesc.h>\n#endif\n",
    (
        "#elif __has_include(<esp32/rom/lldesc.h>)\n #include <esp32/rom/lldesc.h>\n"
        "#elif __has_include(<soc/lldesc.h>)  "
        "// [AirBridge.S3 S31 patched: Bus_SPI]\n"
        " #include <soc/lldesc.h>\n"
        "#endif\n"
    ),
)

# 4a. Bus_I2C.inl — skip the whole file for S31 (it #includes Bus_I2C.hpp
# itself and implements it against common.inl's i2c:: helpers, both
# unconditionally on ESP_PLATFORM; see point 4 above)
patch_file(
    "esp32/Bus_I2C.inl",
    "&& !defined (CONFIG_IDF_TARGET_ESP32S31)",
    "#if defined (ESP_PLATFORM)\n#include <sdkconfig.h>\n\n#include \"Bus_I2C.hpp\"",
    (
        "#if defined (ESP_PLATFORM) && !defined (CONFIG_IDF_TARGET_ESP32S31)"
        "  // [AirBridge.S3 S31 patched: Bus_I2C.inl]\n"
        "#include <sdkconfig.h>\n\n#include \"Bus_I2C.hpp\""
    ),
)


def patch_lines(relpath, start_1based, end_1based, expect_start_prefix, expect_end_line, wrap_open, wrap_close, marker):
    """Wrap an exact, pre-identified line range in an #if/#endif, after
    verifying the file still looks like it did when that range was found
    (defensive against upstream reformatting the file)."""
    path = os.path.join(platforms_dir, relpath)
    if not os.path.exists(path):
        print(f"[patch_lovyangfx_s31] WARNING: {path} not found, skipping")
        return
    with open(path, "r") as f:
        lines = f.readlines()
    if marker in "".join(lines):
        print(f"[patch_lovyangfx_s31] {relpath}: already patched")
        return
    i0, i1 = start_1based - 1, end_1based - 1
    if (
        i1 >= len(lines)
        or not lines[i0].startswith(expect_start_prefix)
        or lines[i1].rstrip("\n") != expect_end_line
    ):
        print(
            f"[patch_lovyangfx_s31] WARNING: {relpath} doesn't match the "
            f"expected line {start_1based}/{end_1based} content (LovyanGFX "
            f"version changed upstream?) — patch NOT applied, build will "
            f"likely fail again"
        )
        return
    lines[i1] = lines[i1].rstrip("\n") + "\n" + wrap_close + "\n"
    lines[i0] = wrap_open + "\n" + lines[i0]
    with open(path, "w") as f:
        f.writelines(lines)
    print(f"[patch_lovyangfx_s31] {relpath}: patched")


# 4b. common.inl — skip the `namespace i2c { ... }` block for S31 (see
# point 4 above). Line numbers pinned to LovyanGFX 1.2.30; the content
# check below refuses to touch the file if that's changed upstream.
patch_lines(
    "esp32/common.inl",
    1151,
    2607,
    "  namespace i2c",
    "  }",
    "#if !defined (CONFIG_IDF_TARGET_ESP32S31)"
    "  // [AirBridge.S3 S31 patched: common.inl]",
    "#endif  // CONFIG_IDF_TARGET_ESP32S31",
    "[AirBridge.S3 S31 patched: common.inl]",
)

# 5. common.inl's getApbFrequency() — same modern-vs-legacy clock-divider
# split as points 2/3, this time in rtc_cpu_freq_config_t: `conf.div` is
# a plain integer on classic chips but a hal_utils_clk_div_t struct (with
# an `.integer` member) on newer ones. ESP32-P4 already needed its own
# branch for this; S31 needs the same treatment.
patch_file(
    "esp32/common.inl",
    "// [AirBridge.S3 S31 patched: getApbFrequency]",
    "    #if defined ( CONFIG_IDF_TARGET_ESP32P4 )\n",
    "    #if defined ( CONFIG_IDF_TARGET_ESP32P4 ) || defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: getApbFrequency]\n",
)
