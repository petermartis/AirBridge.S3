"""PlatformIO pre-build hook: teach LovyanGFX about the ESP32-S31 target.

LovyanGFX predates the ESP32-S31 and has no CONFIG_IDF_TARGET_ESP32S31
branch anywhere, so it falls through to code paths written for other
chips that don't quite match. AirBridge.S3 only ever uses lgfx::Bus_SPI
on this target (see LGFX_Config_s31.h) — no parallel bus, no I2C — so
every patch below is scoped to making SPI work, not to making the other
peripherals correct.

platformio.ini pins LovyanGFX to an exact version for the esp32s31 env
(unlike esp32s3geek's floating ^1.2.0) specifically so these patches stay
matched to known-verified source. A LovyanGFX bump from 1.2.30 to 1.2.31
mid-port already reshuffled line numbers and restructured a whole file
(Bus_SPI.hpp's DMA-descriptor includes — no longer needs a patch at all,
see point 3) while leaving other files byte-identical; letting the
version float would silently re-break this on every future clean build.
Bump the pin deliberately, re-verify each patch below against the new
source, and update this docstring.

1. device.hpp's platform switch has no S31 case, so it falls into the
   generic "#else" written for the original classic ESP32. That branch
   unconditionally includes esp32/Bus_Parallel8.hpp, which needs
   <rom/lldesc.h> — a header ESP-IDF only ships for targets it has an
   esp_rom/<target> component for, and as of ESP-IDF v6.1.0 that
   component doesn't exist yet for esp32s31. Fix: add an S31 branch with
   Light_PWM + Bus_SPI + Bus_I2C.hpp.

   Bus_I2C.hpp IS included here even though this project never uses I2C
   (see point 4 for why the *implementation* is skipped) — device.hpp is
   reached very early in lgfx_v1.cpp's single-translation-unit build
   (via LGFXBase.hpp), well before panel/Panel_M5HDMI.hpp/.inl, which
   reference the bare `lgfx::Bus_I2C` type unconditionally regardless of
   what device.hpp chose. Declaring the type late instead (e.g. only via
   Bus_I2C.inl's own #include of this same header) is too late — that
   file is #include'd by lgfx_v1.cpp after Panel_M5HDMI, so the type
   still wouldn't exist yet when Panel_M5HDMI needs it. First version of
   this patch got this backwards and omitted the include, which built
   clean in isolation but broke on the very next file.

2. common.hpp's fast GPIO helpers have three implementations: classic
   ESP32's legacy raw-register one (with dual-bank pin>=32 handling),
   C2/C3/C5/C6/C61/H2's modern struct-typed one (`GPIO.out_w1ts.val`,
   single-bank only — those chips top out under 32 GPIOs so they never
   needed a bank1), and P4's modern struct-typed *and* dual-bank one
   (`(pin & 32) ? &GPIO.out1_w1ts.val : &GPIO.out_w1ts.val`). S31 falls
   into the classic legacy "#else" by default, which doesn't compile
   against its struct-typed registers.

   S31 needs the P4 shape, not the C2/C3/etc one: its SoC header has real
   out1/out1_w1ts/out1_w1tc/in1 bank1 registers (confirmed by reading
   framework-arduinoespressif32-libs/esp32s31/.../gpio_struct.h), and
   AirBridge.S3's actual wiring drives CS/DC/RESET on GPIO39/40/43 — all
   >=32 — so a single-bank implementation would silently toggle the
   wrong physical pin's bit instead of failing to compile, and the
   display would never respond to anything. (An earlier version of this
   patch put S31 in the C2/C3/etc branch instead, on the mistaken
   assumption this project would only ever use pins <32; caught only
   after a real round-trip against actual hardware showed a correctly-
   initializing, never-responding panel.) Fix: add S31 to the P4
   condition instead.

3. (Historical — no longer applied.) 1.2.30's Bus_SPI.hpp needed a
   lldesc_t fallback for the same missing-ROM-header reason as point 1.
   1.2.31 rewrote that file's DMA-descriptor includes to prefer
   <hal/dma_types.h> / <soc or hal/gdma_channel.h> ("ESP-IDF 6", per its
   own comment) and no longer references lldesc_t at all — compiles
   clean for S31 with no patch needed. Left as a numbered point so a
   future re-pin's diff-against-upstream doesn't wonder where patch 3
   went.

4. common.inl's `i2c::` namespace assumes a legacy i2c_dev_t register
   layout the S31 doesn't have (no `fifo_data`, `status_reg`, `clk_conf`,
   `.period`/`.time`/`.nack` union members those functions reference,
   plus an undeclared `LP_I2C_SCLK_XTAL_D2`) — a different register
   generation, not a few renamed fields. Since this project never uses
   I2C, that whole namespace is skipped outright for
   CONFIG_IDF_TARGET_ESP32S31 rather than patched (patch_namespace_skip
   below locates the namespace's matching closing brace by counting
   braces rather than a pinned line number, since that number already
   proved to drift between patch releases even when the surrounding code
   didn't otherwise change).

   Bus_I2C.inl (Bus_I2C's out-of-line method implementations) is
   compiled unconditionally too and calls into that same i2c:: namespace,
   so its implementation needs the same treatment — but only the
   implementation. Its own #include "Bus_I2C.hpp" must stay active (see
   point 1 for why device.hpp's own include is still the one that
   actually matters for Panel_M5HDMI — this one is belt-and-suspenders
   for anything reached between here and end of file). Bus_I2C.hpp is
   pure declarations with no calls into i2c:: (verified by reading it),
   so nothing in this project ever instantiating lgfx::Bus_I2C means the
   type existing with undefined (never-called) methods is fine.

Safe to drop all of these once upstream LovyanGFX adds real ESP32-S31
support.
"""

import os
import re

Import("env")  # noqa: F821 — injected by PlatformIO's SConscript

libdeps_dir = env.subst(os.path.join("$PROJECT_LIBDEPS_DIR", "$PIOENV"))
platforms_dir = os.path.join(
    libdeps_dir, "LovyanGFX", "src", "lgfx", "v1", "platforms"
)


def patch_file(relpath, marker, old, new, optional=False):
    path = os.path.join(platforms_dir, relpath)
    if not os.path.exists(path):
        print(f"[patch_lovyangfx_s31] WARNING: {path} not found, skipping")
        return
    with open(path, "r") as f:
        content = f.read()
    if marker in content:
        print(f"[patch_lovyangfx_s31] {relpath}: already patched")
    elif old not in content:
        level = "note" if optional else "WARNING"
        print(
            f"[patch_lovyangfx_s31] {level}: expected anchor text not found "
            f"in {relpath} (LovyanGFX version changed upstream?) — patch "
            f"NOT applied{' (optional — may simply no longer be needed)' if optional else ', build will likely fail again'}"
        )
    else:
        with open(path, "w") as f:
            f.write(content.replace(old, new, 1))
        print(f"[patch_lovyangfx_s31] {relpath}: patched")


def _strip_comments_and_literals(text):
    """Blank out //, /* */, "..." and '...' contents (keeping newlines and
    length) so a brace count over the result only sees structural braces."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i : i + 2] == "//":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and text[i : i + 2] == "/*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c in "\"'":
            quote = c
            j = i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def patch_namespace_skip(relpath, namespace_name, wrap_open, wrap_close, marker):
    """Wrap `namespace <namespace_name> { ... }` in an #if/#endif, locating
    its matching closing brace by counting braces (comment/string-aware)
    from the namespace keyword — robust to the block's line count changing
    between LovyanGFX releases, unlike a pinned line-number range."""
    path = os.path.join(platforms_dir, relpath)
    if not os.path.exists(path):
        print(f"[patch_lovyangfx_s31] WARNING: {path} not found, skipping")
        return
    with open(path, "r") as f:
        text = f.read()
    if marker in text:
        print(f"[patch_lovyangfx_s31] {relpath}: already patched")
        return

    needle = f"namespace {namespace_name}"
    start = text.find(needle)
    if start == -1:
        print(
            f"[patch_lovyangfx_s31] WARNING: 'namespace {namespace_name}' "
            f"not found in {relpath} (LovyanGFX version changed upstream?) "
            f"— patch NOT applied, build will likely fail again"
        )
        return

    # Pull in an immediately-preceding "inline" (as in "inline namespace v1")
    # so it doesn't get orphaned on its own with nothing following once the
    # #if skips the namespace body — "inline" alone is a syntax error.
    m = re.search(r"inline\s+$", text[:start])
    if m:
        start = m.start()

    clean = _strip_comments_and_literals(text)
    brace_open = clean.find("{", start)
    if brace_open == -1:
        print(f"[patch_lovyangfx_s31] WARNING: no opening brace found for "
              f"'namespace {namespace_name}' in {relpath} — patch NOT applied")
        return
    depth = 0
    j = brace_open
    while j < len(clean):
        depth += clean[j] == "{"
        depth -= clean[j] == "}"
        if depth == 0:
            break
        j += 1
    else:
        print(f"[patch_lovyangfx_s31] WARNING: unbalanced braces scanning "
              f"'namespace {namespace_name}' in {relpath} — patch NOT applied")
        return

    patched = text[:start] + wrap_open + "\n" + text[start : j + 1] + "\n" + wrap_close + text[j + 1 :]
    with open(path, "w") as f:
        f.write(patched)
    print(f"[patch_lovyangfx_s31] {relpath}: patched ({namespace_name} skipped, "
          f"{text[start:j+1].count(chr(10))+1} lines)")


# 1. device.hpp — add an S31 branch before the ESP32H2 one. Bus_I2C.hpp
# IS included despite this project not using I2C — see point 1 above for
# why (Panel_M5HDMI needs the bare type declared this early).
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
        "  #include \"esp32/Bus_I2C.hpp\"\n"
        "\n"
        " #elif defined (CONFIG_IDF_TARGET_ESP32H2)\n"
    ),
)

# 2. common.hpp — add S31 to the P4 branch (modern struct-typed *and*
# dual-bank registers — see docstring point 2 for why this, not the
# C2/C3/etc branch, is the correct one for S31)
patch_file(
    "esp32/common.hpp",
    "// [AirBridge.S3 S31 patched: common]",
    "#if defined ( CONFIG_IDF_TARGET_ESP32P4 )\n",
    "#if defined ( CONFIG_IDF_TARGET_ESP32P4 ) || defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: common]\n",
)

# 3. Bus_SPI.hpp lldesc_t patch — retired, see docstring point 3. Kept as
# an optional (non-scary-warning) attempt in case a future LovyanGFX pin
# reverts to the old rom/lldesc.h-based includes.
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
    optional=True,
)

# 4a. Bus_I2C.inl — keep its own "#include Bus_I2C.hpp" active (the type
# must exist — see docstring point 4) but skip the lgfx::v1 namespace
# body that implements it against the broken i2c:: helpers.
patch_namespace_skip(
    "esp32/Bus_I2C.inl",
    "v1",
    "#if !defined (CONFIG_IDF_TARGET_ESP32S31)"
    "  // [AirBridge.S3 S31 patched: Bus_I2C.inl]",
    "#endif  // CONFIG_IDF_TARGET_ESP32S31 (Bus_I2C.inl)",
    "[AirBridge.S3 S31 patched: Bus_I2C.inl]",
)

# 4b. common.inl — skip the `namespace i2c { ... }` block for S31 (see
# docstring point 4). Locates its own closing brace rather than trusting
# a pinned line number.
patch_namespace_skip(
    "esp32/common.inl",
    "i2c",
    "#if !defined (CONFIG_IDF_TARGET_ESP32S31)"
    "  // [AirBridge.S3 S31 patched: common.inl i2c]",
    "#endif  // CONFIG_IDF_TARGET_ESP32S31 (common.inl i2c)",
    "[AirBridge.S3 S31 patched: common.inl i2c]",
)

# 5. common.inl's getApbFrequency() — same modern-vs-legacy clock-divider
# split as point 2, this time in rtc_cpu_freq_config_t: `conf.div` is a
# plain integer on classic chips but a hal_utils_clk_div_t struct (with
# an `.integer` member) on newer ones. ESP32-P4 already needed its own
# branch for this; S31 needs the same treatment. (This function is well
# before the i2c:: namespace patched above, so the two don't interact.)
patch_file(
    "esp32/common.inl",
    "// [AirBridge.S3 S31 patched: getApbFrequency]",
    "    #if defined ( CONFIG_IDF_TARGET_ESP32P4 )\n",
    "    #if defined ( CONFIG_IDF_TARGET_ESP32P4 ) || defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: getApbFrequency]\n",
)
