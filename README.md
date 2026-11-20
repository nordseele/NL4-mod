# NL4 M

### MPE for the Nord Lead 4

**NL4 M (BETA)** (repository `NL4-mod`) is an unofficial firmware modification for the Clavia
(Nord Keyboards) Nord Lead 4, OS 1.32. It adds **MPE** (MIDI Polyphonic Expression):
per-note pitch bend, pressure (Z) and timbre (Y, CC74) from an MPE controller such as a
LinnStrument or an Osmose.

> [!WARNING]
> **Unofficial, experimental firmware — use at your own risk.** This project is
> not affiliated with or endorsed by Clavia DMI AB (Nord Keyboards), and it is
> provided **as-is, with no warranty** (see the [GPL](LICENSE), sections 15-16).
>
> - Installing it **replaces the operating system of your Nord Lead 4.** If
>   something goes wrong, you may have to restore the official OS (power on
>   while holding Shift + Store, then run the official OS 1.32 updater), and in
>   the worst case open the instrument and reprogram its flash memory.
> - It **changes what the main processor sends to the DSPs** (per-voice
>   level, filter and modulation). Test it at **low volume and without
>   headphones** the first time.
> - It has been tested on **one unit only.**
> - **Back up your programs and performances first** (Nord Sound Manager), and
>   check that you can start the instrument in Update mode (Shift + Store)
>   before you install anything.
>
> You are responsible for what you install on your instrument.

**How it was made.** The code was written by AI (Claude, through Claude Code), under
my direction: I set the goals, made the design decisions and reviewed the results. All
hardware testing was done by me, on my own Nord Lead 4.

## What it adds

MPE is played **from an external MPE controller only** (LinnStrument, Osmose, Seaboard…),
over USB or 5-pin MIDI. The Nord Lead 4's own keyboard has no aftertouch and sends no
per-note expression: it keeps working as before.

- **MPE Lower Zone:** member channels 2 to 16, in addition to the global channel. Notes go
  to the slot(s) in Keyboard Focus.
- **Per-note pitch bend**, range 48, 24, 12 or 2 semitones.
- **Per-note Y (CC74) and Z (pressure)**, each routed to the program's Wheel morph, its
  Velocity morph or Filter Freq directly; Z can also drive the voice level.
- **Pressure as Channel Pressure or Poly Aftertouch:** on a member channel, both are read
  as the Z of that channel's note (7-bit values).
- Response curves for Y and Z, and an option to scale Z by the note velocity.
- The same pitch can be held on several channels, each note keeping its own expression.
- Slot channels A–D that fall on a member channel are ignored while MPE is on.

## MIDI menu settings

The settings are new entries **at the end of the MIDI menu**, after entry 8: turn the dial
to reach them, hold Shift and turn to change the value. They are saved with the other
global settings. The display shows the entry letter, a dot and the value, e.g. `E.On`.
The first value is the default.

| Display | Setting | Values |
|---|---|---|
| `E` | **MPE** | `Of` off · `On` on |
| `r` | **Bend range** of the member channels | `48` · `24` · `12` · ` 2` semitones |
| `y` | **Y (CC74) goes to** | `nO` Wheel morph · `vE` Velocity morph · `Fr` Filter Freq directly · `Of` nothing |
| `C` | **Y curve** | `Li` linear · `CA` square (slow at the bottom) · `dO` soft (fast at the bottom) |
| `P` | **Z (pressure) goes to** | `LE` level (from silence to the normal level) · `nO` Wheel morph · `vE` Velocity morph · `Fr` Filter Freq · `Of` nothing · `vL` Z replaces the velocity of the level (small range, about 6 dB) |
| `H` | **Z curve** | `CA` square · `Li` linear · `dO` soft |
| `v` | **Z × velocity** | `Of` Z alone · `On` Z scaled by the note's velocity |

Why these letters: the display cannot show a `Z` (it would read as a `2`, already used by
Local), hence `P` for pressure and `E` for MPE. `nO` stands for the wheel (the French word
"moLette", the `n` standing in for an `M`), and `vE` reads as "UE" on the display.

Tips:
- Set the controller to an MPE lower zone with a pitch-bend range equal to `r` (48 by
  default), and keep the slot channels A–D on Off or on channel 1.
- `y.nO` and `P.nO` use the program's own Wheel morph: pick a program whose wheel does
  something, and keep the physical wheel down (Y and Z add to it).
- On the LinnStrument, send Z as Channel Pressure or Poly Aftertouch, not in 14-bit mode.

Details of each setting, and how it was built step by step:
[docs/patches.md](docs/patches.md), "Stage 11 in detail".

## Repository layout

| Path | Contents | In git |
|---|---|---|
| `tools/unpack_oscab.py` | reads `os.cab` and decompresses its LZO1X sections | yes |
| `tools/mkelf.py` | wraps raw sections into an ARM ELF with seed symbols, for Ghidra | yes |
| `tools/seeds_low.txt` | SRAM and ARM0 function starts given to Ghidra (earlier one-off scan) | yes |
| `tools/find_func_starts.py` | generates `funcs_seed.txt` (`bl` targets, prologues, tables) | yes |
| `tools/find_ptr_tables.py` | generates `vtables.txt` (tables of code pointers) | yes |
| `tools/symbols.txt` | names given to identified functions (carried by the ELF) | yes |
| `tools/rebuild.sh` | regenerates all of `ghidra/bin/` from the dmg | yes |
| `tools/dump_decomp.py` | pseudo-C of every function → `ghidra/bin/decomp.c` (throwaway container) | yes |
| `tools/spiprobe.py` | read-only SPI flash probe (Pico `pico-serprog`) | yes |
| `tools/pack_oscab.py` | rebuilds `os.cab` (replaced sections, LZO, checksums, verification) | yes |
| `tools/patch/` | OS patches: Docker image (GCC ARM), `build.py`, `palier*.c`, `make_updater.sh` | yes |
| `tools/extract_sharc.py` | extracts the two SHARC programs from the OS (`ghidra/bin/sharc/`) | yes |
| `docs/oscab-format.md` | `os.cab` format, sections, compression, checksums | yes |
| `docs/update-protocol.md` | update protocol (Mac program), keyboard modes, safety | yes |
| `docs/hardware.md` | main board: chips, SPI flash, P5 connector, recovery | yes |
| `docs/feasibility.md` | feasibility study: verdict, changes, Y/Z options, prototype plan | yes |
| `docs/nord-stage-2-notes.md` | what may carry over to an MPE project on the Nord Stage 2 | yes |
| `docs/patches.md` | patches, stages (`palierN` in file names), test procedure on the instrument | yes |
| `docs/sharc.md` | SHARC code: location, format, Ghidra import | yes |
| `docs/voices-midi.md` | MIDI input, slots, voices, allocator (research notes) | yes |
| `docs/menus.md` | System, MIDI and Sound menus | yes |
| `build/` | rebuilt OS images and updater copies | no |
| `ghidra/sharc_work/` | SHARC Ghidra project (throwaway) | no |
| `vendor/` | official dmg, PDF manual (+ `manual.txt`), extracted binary | no |
| `ghidra/bin/` | `os.cab`, decompressed sections, full ELF, `vtables.txt` and `funcs_seed.txt` (generated by `rebuild.sh`) | no |
| `ghidra/nl4_ghidra.*` | Ghidra project of the `pyghidra-nl4` container | no |
| `.mcp.json` | connects the Ghidra MCP server (`127.0.0.1:8003`) | yes |

## Setup

1. Put `Update Nord Lead 4 OS v1.32.dmg` (downloaded from nordkeyboards.com) in `vendor/`.
2. `tools/rebuild.sh`
3. Dedicated Ghidra container (does not affect other pyghidra containers):

```bash
docker run -d --name pyghidra-nl4 --restart unless-stopped -p 127.0.0.1:8003:8000 -e JAVA_TOOL_OPTIONS=-Duser.name=matthias -v "$PWD/ghidra":/projects ghcr.io/clearbluejar/pyghidra-mcp:sha-f43400b -t streamable-http -o 0.0.0.0 --project-path /projects/nl4_ghidra.gpr
```

4. In Claude Code, import `/projects/bin/nl4_os132_full.elf` with the `import_binary`
   tool of the `pyghidra-nl4` server.

## Build

```bash
docker build -t nl4-arm tools/patch        # once: GCC ARM + python3-lzo
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier11
tools/patch/make_updater.sh build/palier11_os.cab
```

This writes `build/palier11_os.app`, a copy of the official updater carrying the
modified `os.cab`. The build and test procedure is in [docs/patches.md](docs/patches.md).

## Caution

Nothing in this repository writes to the keyboard by itself. Flashing a modified
firmware can make the synth unusable: see the risks section of HANDOFF.md.

Do not share the contents of `build/`, `vendor/` or `ghidra/`: they contain Clavia's
firmware.

## Licence

Copyright (c) 2026 nordseele.

NL4 M is free software under the **GNU General Public License, version 3 or
later** ([LICENSE](LICENSE)), with an additional permission
([LICENSE-EXCEPTION.md](LICENSE-EXCEPTION.md)) that allows combining it with
the Nord Lead 4 firmware, which the GPL alone would not. In short: you may use,
study, change and share this code; if you distribute a modified version, you
must keep the copyright notices and publish your changes under the same terms.

The licence covers the code in this repository only, not Clavia's firmware
that the build modifies. "Nord", "Nord Lead" and "Clavia" are trademarks of
their owners and are used here only to say which instrument this modification
is for.
