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

6. Bus_SPI.inl / common.inl's SPI *clock-source* handling — found after
   points 1-5 fixed the board's "compiles, boots, panel stays blank"
   symptom on GPIO/pins but a *proven-working* raw esp-idf spi_master
   test on the same wiring still worked where this firmware didn't (see
   git history for the earlier failed attempts this ruled out: wiring,
   GPIO bank, SPI clock speed setting, and the ST7735 init command
   table were all confirmed byte-for-byte equivalent to the raw test's
   and made no difference).

   getSpiClockFrequency() picks its implementation by #if/#elif chain
   over CONFIG_IDF_TARGET_*, one branch per chip family, because each
   family's GP-SPI2 clock source is wired up differently: some chips
   simply run it off APB (always 80MHz once CPU clock >=80MHz), others
   (S3/C2/C3) read a mux-select bit, others (C5/C6/C61/H2) decode a
   source-select + divider field. S31 matches none of those listed
   branches, so it falls into the final generic "#else return
   getApbFrequency()" — silently assuming an 80MHz source.

   ESP32-P4 needed its own branch here instead of that generic
   fallback, because P4's GP-SPI2/GP-SPI3 clock source is independently
   selectable (XTAL / RC_FAST / SPLL) via dedicated HP_SYS_CLKRST
   register fields, not simply tied to APB. S31 needs the same kind of
   real decode instead of the 80MHz guess — but NOT by reusing P4's
   branch outright. First attempt at this patch did exactly that
   (reading framework-arduinoespressif32-libs/esp32s31/.../
   hp_sys_clkrst_reg.h showed the *field* names/bit-positions
   — HP_SYS_CLKRST_REG_GPSPI2_CLK_SRC_SEL / _HS_CLK_DIV_NUM /
   _MST_CLK_DIV_NUM — are identical to P4's) and it failed to compile:
   S31 packs each peripheral's clock config into its own one-register
   HP_SYS_CLKRST_GPSPI{2,3}_CTRL0_REG, not P4's shared
   PERI_CLK_CTRL116_REG/117_REG pair — P4's register *names* simply
   don't exist for S31, even though the bitfields inside each
   peripheral's own register match. Worse, the clk_src_sel *value*
   encoding differs too: P4 uses 4 for its PLL source, S31 uses 2 (for
   BBPLL) — confirmed against ESP-IDF's own
   esp_hal_gpspi/esp32s31/include/hal/spi_ll.h
   spi_ll_set_clk_source(), not guessed, after a first guess at
   reusing P4's case labels would have silently mis-decoded a PLL
   source on this chip. So this is its own S31 branch below, not a
   condition added onto P4's.

   If the real GP-SPI2 clock source on this board isn't actually
   sitting at 80MHz (unknown without instrumenting it — S31 is new
   enough that there's no public reference for its out-of-reset clock
   tree state), every freq_write/freq_read divider LovyanGFX computes
   is calculated against the wrong base clock. The SPI peripheral still
   completes each transaction from the CPU's point of view (the status
   bit LovyanGFX polls just reflects "shifted out however many bits at
   whatever divider we told it," not whether that maps to a sane
   real-world frequency) — so firmware runs with no crash, CS/DC/RESET
   all toggle at the right moments, and the panel simply never
   receives an intelligible byte. That matches every real-hardware
   symptom seen so far exactly.

   LGFX_SPI_CLOCK_TAKEOVER (which *actively* reprograms the clock
   source to a known-good value rather than just reading whatever it
   already is) is left alone for S31 — not extended the way point 2's
   GPIO branch or this point's getSpiClockFrequency() are. Once
   getSpiClockFrequency() reads the true current source, S31's default
   out-of-reset source (XTAL, confirmed 0 = SPI_CLK_SRC_XTAL in the
   same spi_ll.h) already divides evenly to the 10MHz this project
   requests, so take-over would have nothing to improve — and
   reusing P4's take-over register writes would mean writing the
   wrong registers for the reason above. Bus_SPI.inl is untouched by
   this point entirely; only common.inl's getSpiClockFrequency()
   changes.

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

# 6a. common.inl — the HP_SYS_CLKRST_GPSPI{2,3}_* register/field macros
# 6b below reads live in <soc/hp_sys_clkrst_reg.h>, which nothing on
# this target includes otherwise: P4/C5/C6/C61 only get it via
# Bus_SPI.inl's LGFX_SPI_CLOCK_TAKEOVER gate, which S31 deliberately
# doesn't join (see docstring point 6 — that machinery assumes P4's
# register map). Included directly here instead, scoped to S31 only.
patch_file(
    "esp32/common.inl",
    "// [AirBridge.S3 S31 patched: hp_sys_clkrst include]",
    "#include <driver/spi_common.h>\n"
    "#include <driver/spi_master.h>\n",
    "#include <driver/spi_common.h>\n"
    "#include <driver/spi_master.h>\n"
    "#if defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: hp_sys_clkrst include]\n"
    " #include <soc/hp_sys_clkrst_reg.h>\n"
    "#endif\n",
)

# 6b. common.inl — getSpiClockFrequency() gets its own S31 branch (see
# docstring point 6 for why this isn't just "add S31 to P4's condition"
# the way the other points in this file are — the register map and the
# clk_src_sel value encoding both genuinely differ from P4's, verified
# against ESP-IDF's own esp32s31 SoC headers and HAL source, not
# assumed from the bitfield-layout match alone). Bus_SPI.inl is left
# untouched — LGFX_SPI_CLOCK_TAKEOVER stays P4/C5/C6/C61-only.
#
# Inserted as its own #elif ahead of the function's final "#else return
# getApbFrequency()" fallback, which is what S31 would otherwise hit.
# That fallback text is unique in this function (every other branch's
# #else is chip-specific, like P4's `#else (void)spi_host; return
# getApbFrequency(); #endif` immediately inside its own #if), so anchoring
# on it doesn't risk matching a different one of the function's branches.
patch_file(
    "esp32/common.inl",
    "// [AirBridge.S3 S31 patched: getSpiClockFrequency]",
    "#else\n"
    "    (void)spi_host;\n"
    "    return getApbFrequency();\n"
    "#endif\n"
    "#endif\n"
    "  }\n",
    "#elif defined ( CONFIG_IDF_TARGET_ESP32S31 )"
    "  // [AirBridge.S3 S31 patched: getSpiClockFrequency]\n"
    "    // S31's GP-SPI2/GP-SPI3 clock config each live in their own\n"
    "    // one-register CTRL0 (HP_SYS_CLKRST_GPSPI{2,3}_CTRL0_REG), not\n"
    "    // P4's shared PERI_CLK_CTRL116/117 pair, and clk_src_sel's value\n"
    "    // encoding is S31's own too (2 = BBPLL here vs P4's 4 = SPLL) —\n"
    "    // both confirmed against esp_hal_gpspi/esp32s31/include/hal/\n"
    "    // spi_ll.h's spi_ll_set_clk_source(), not assumed from the\n"
    "    // bitfield layout inside each register matching P4's.\n"
    "    uint32_t ctrl0;\n"
    "    uint32_t source_sel;\n"
    "    uint32_t hs_div;\n"
    "    uint32_t mst_div;\n"
    "    if (spi_host == SPI2_HOST)\n"
    "    {\n"
    "      ctrl0 = REG_READ(HP_SYS_CLKRST_GPSPI2_CTRL0_REG);\n"
    "      source_sel = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI2_CLK_SRC_SEL);\n"
    "      hs_div = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI2_HS_CLK_DIV_NUM);\n"
    "      mst_div = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI2_MST_CLK_DIV_NUM);\n"
    "    }\n"
    "    else if (spi_host == SPI3_HOST)\n"
    "    {\n"
    "      ctrl0 = REG_READ(HP_SYS_CLKRST_GPSPI3_CTRL0_REG);\n"
    "      source_sel = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI3_CLK_SRC_SEL);\n"
    "      hs_div = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI3_HS_CLK_DIV_NUM);\n"
    "      mst_div = VALUE_GET_FIELD(ctrl0, HP_SYS_CLKRST_REG_GPSPI3_MST_CLK_DIV_NUM);\n"
    "    }\n"
    "    else\n"
    "    {\n"
    "      return getApbFrequency();\n"
    "    }\n"
    "\n"
    "    uint32_t source_hz;\n"
    "    switch (source_sel)\n"
    "    {\n"
    "    case 0: source_hz = get_xtal_frequency(); break;      // SPI_CLK_SRC_XTAL\n"
    "    case 1: source_hz = get_rc_fast_frequency(); break;   // SPI_CLK_SRC_RC_FAST\n"
    "    case 2: source_hz = 480000000u; break;                // SPI_CLK_SRC_BBPLL\n"
    "    default: source_hz = 480000000u; break; // Safe upper bound for an unknown source.\n"
    "    }\n"
    "    return source_hz / (hs_div + 1) / (mst_div + 1);\n"
    "#else\n"
    "    (void)spi_host;\n"
    "    return getApbFrequency();\n"
    "#endif\n"
    "#endif\n"
    "  }\n",
)

# 6f. common.inl — the get_rc_fast_frequency() lambda used by the P4
# branch above (its RC_FAST source_sel case) is itself declared under a
# separate, narrower guard that never included P4's own sibling S31.
# Without this, 6e's P4 branch compiles for S31 but calls an
# undeclared function the moment it hits the RC_FAST case.
patch_file(
    "esp32/common.inl",
    "// [AirBridge.S3 S31 patched: get_rc_fast_frequency]",
    "#if defined ( CONFIG_IDF_TARGET_ESP32C5 ) || defined ( CONFIG_IDF_TARGET_ESP32C61 ) \\\n"
    " || defined ( CONFIG_IDF_TARGET_ESP32C6 ) || defined ( CONFIG_IDF_TARGET_ESP32H2 ) \\\n"
    " || defined ( CONFIG_IDF_TARGET_ESP32P4 )\n",
    "// [AirBridge.S3 S31 patched: get_rc_fast_frequency]\n"
    "#if defined ( CONFIG_IDF_TARGET_ESP32C5 ) || defined ( CONFIG_IDF_TARGET_ESP32C61 ) \\\n"
    " || defined ( CONFIG_IDF_TARGET_ESP32C6 ) || defined ( CONFIG_IDF_TARGET_ESP32H2 ) \\\n"
    " || defined ( CONFIG_IDF_TARGET_ESP32P4 ) || defined ( CONFIG_IDF_TARGET_ESP32S31 )\n",
)
