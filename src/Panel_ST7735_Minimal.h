#pragma once
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// Diagnostic panel class: replicates the user's proven-working raw
// esp-idf spi_master ST7735 init sequence byte-for-byte, bypassing
// Panel_ST7735S's built-in init table.
//
// Panel_ST7735S::getInitCommands() sends ~13 commands (FRMCTR1-3,
// INVCTR, PWCTR1-5, VMCTR1, GMCTRP1/GMCTRN1) before NORON/DISPON --
// gamma and power-supply tuning the raw test never sends at all. The
// raw test's sequence is only:
//   SWRESET (+150ms) -> SLPOUT (+150ms) -> COLMOD=0x05 -> MADCTL=0x00
//   -> INVOFF (+10ms) -> NORON (+10ms) -> DISPON (+100ms)
// and is confirmed to light up this exact physical panel with correct
// (non-inverted) colors. If this minimal table works where the stock
// Panel_ST7735S table doesn't, one of the extra power/gamma commands
// is putting this panel unit into a non-responsive (blank white)
// state.
//
// INVOFF, not INVON: raw_spi_test's own INVON was mistaken for a bug
// for several rounds -- screen colors looked completely wrong (log
// said BLACK, screen showed white; GREEN logged, magenta shown) --
// until checking the actual bitwise complements showed it was exactly
// INVON's documented, correct inversion, not corruption. The panel's
// native (uninverted) colors are correct, so INVON is unneeded here.
//
// Command byte encoding (see lgfx::Panel_Device::command_list()):
//   cmd, num_args[|CMD_INIT_DELAY], args..., [delay_ms], ..., 0xFF, 0xFF
struct Panel_ST7735_Minimal : public lgfx::Panel_ST7735S {
protected:
    const uint8_t* getInitCommands(uint8_t listno) const override {
        static constexpr uint8_t cmds[] = {
            CMD_SWRESET, CMD_INIT_DELAY, 150,
            CMD_SLPOUT,  CMD_INIT_DELAY, 150,
            CMD_COLMOD,  1,              0x05,
            CMD_MADCTL,  1,              0x00,
            CMD_INVOFF,  CMD_INIT_DELAY, 10,
            CMD_NORON,   CMD_INIT_DELAY, 10,
            CMD_DISPON,  CMD_INIT_DELAY, 100,
            0xFF, 0xFF
        };
        switch (listno) {
        case 0:  return cmds;
        default: return nullptr;
        }
    }
};
