# HANDOFF — status of the NL4 MPE project (MPE for the Nord Lead 4)

Last update: 2026-11-20.

## Resuming in a new conversation

**Status**: **stage 11 tried on the instrument on 2026-11-20: OK** (`build/palier11_os.app`,
`os.cab` `1b7fb57c…c2274204`). All MPE options are in the MIDI menu, after entry 8 (table
in `README.md` and in `docs/patches.md`, "Stage 11 in detail"):
- MPE lower zone, member channels 2 to 16, from an **external** MPE controller (the Lead 4's
  own keyboard has no aftertouch and sends no per-note expression);
- per-note bend (48 / 24 / 12 / 2 semitones);
- Y (CC74) and Z (Channel Pressure or Poly AT of the member channels) each routed to the
  Wheel morph, the Velocity morph or Filter Freq directly; Z also to the voice level
  (`LE`: level × Z, from silence to the normal level; `vL`: Z replaces the level's
  velocity, ≈ 6 dB);
- curves for Y and Z, Z × velocity;
- A–D channels lying on a member channel are ignored while MPE is on;
- same pitch on several channels (stage 9, note renumbering).

Tried by the user with the Osmose and the LinnStrument: all destinations, curves and
`v` work. Z on the LinnStrument must be sent as Channel Pressure or Poly AT on 7 bits (the
14-bit mode may go through a CC, which our code does not read **[to check]**).

The step-by-step history (stages 1 to 11, each version and each test) is in
`docs/patches.md`. Space: the hole after the CODE is full (0xab8 / 0xad0); the next
additions go into the dead code areas (`tools/find_dead_code.py`, `DEAD` in `build.py`).

**Not done, by the user's choice (2026-11-20)**: RPN 6 / RPN 0 (letting the controller set
the zone and the bend range). Low priority; the menu is enough. If it is done one day: as
a convenience on top of the menu, never as a dependency.

**Repository**: `github.com/nordseele/NL4_MPE`, public since 2026-11-20 (README, warning
and licence modelled on P12 MPE, `nordseele/P12_MPE`). `hardware/` (photos of the board) stays local.

Recovery table kept from the first stages:

| Result | Next |
|---|---|
| The re-signed updater does not launch | look at the macOS message; try `xattr -cr` / ad hoc signing by hand, or replace `os.cab` in a copy of the official app |
| The keyboard refuses the file (stage 1) | re-read `CBinFile::Verify` on the Mac side and the Update program (unknown); compare with the official `os.cab` |
| A modified OS does not boot | power on while holding Shift + Store, install the official OS 1.32; for stage 10 and later, `build/palier9dead_os.app` tells whether the dead area is the cause |

Technical start-up:
1. Read this file, `docs/patches.md`, `docs/feasibility.md`, then `docs/voices-midi.md`.
2. Ghidra container: `docker ps --filter name=pyghidra-nl4` (otherwise `docker start
   pyghidra-nl4`). The imported ELF carries all names from `tools/symbols.txt`.
3. Build image for the patches: `docker build -t nl4-arm tools/patch` if it is missing.
   Build: `docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py
   palier11`, then `tools/patch/make_updater.sh build/palier11_os.cab`.
4. If `ghidra/bin/` is empty: `tools/rebuild.sh`, then the pseudo-C (command at the top
   of `tools/dump_decomp.py`, in the background); check: 0 "Subroutine does not return".
5. SHARC programs: `tools/extract_sharc.py` and `docs/sharc.md` (throwaway Ghidra project
   in `ghidra/sharc_work/`, extension built in the Prophet 12 project).

Checks at each build (method used since stage 9): rebuild the previous stages and check
that they stay identical byte for byte; compare the new image word by word with the
original (only the expected words, the dead area used and the added code may differ);
re-extract the `.cab`; no call to libgcc in the produced code. The user tests by hand on
the instrument; if a cause is not sure, prefer a diagnostic version that shows the state
in the menu over a blind fix. Always test with a program that sounds with the wheel down.

**Decisions taken**: prototype with Y on Velocity first, then per-parameter application
(stage 7) and selectable destinations (stage 11); then helper functions to convert a
program; a program editor idea to study later (lead: contribute the Lead 4 to OpenNord).
Hardware backup of the flash dropped (U38 empty, `docs/hardware.md`).

## Goal

Full MPE on the Nord Lead 4: X = per-note pitch bend (±48 semitones), Y = timbre (CC74),
Z = pressure (channel pressure per member channel). As many MPE notes as possible
(chords of 8 notes and more), each note independent (X/Y/Z). Controllers: Expressive E
Osmose and LinnStrument. The "light MPE" with 4 slots was already tried and is not the
goal.

## Where things stand (analysis)

- [x] `os.cab` decoded: section table, LZO1X compression (`docs/oscab-format.md`).
- [x] Full OS v1.32 decompressed (4.2 MB of ARM code) and loaded in Ghidra.
- [x] The 2nd image is identified: a factory test firmware.
- [x] **Addresses corrected**: all function addresses noted before the commit following
  `6c7f2fb` were 0x20 too high (see the box in `docs/voices-midi.md`). Full explanation on
  2026-11-18: section offsets count from the image header, not from the preamble. The
  so-called "unloaded header" was the end of the previous section
  (`docs/oscab-format.md`). Addresses stay valid; each section got its last 0x20 bytes
  back.
- [x] **Checksums of the 6 sections reproduced** (2026-11-18): `~sum of bytes`, on the
  section and on the compressed stream. `tools/unpack_oscab.py` checks them at each
  extraction.
- [x] **Update protocol read** in the Mac program (`docs/update-protocol.md`): 4 programs
  on the keyboard (OS, TP, Update, Boot). Update and Boot are not in `os.cab`, so most
  likely never rewritten.
- [x] MIDI input: complete chain to the slots for controllers (bend = no. 9, pressure =
  no. 8), routing by **(port, channel) bit masks** per target, so a slot can already
  listen to several channels. Notes: **one zone per (port, channel) pair** and a 128-note
  table per zone in the targets, then slot → allocator (`docs/voices-midi.md`).
- [x] Voices: 4 slots + a global pool of 20 voices, a pool of 64 notes, voice stealing by
  priority, pitch computed and written voice by voice. **A note is identified by (slot,
  note number), without the channel**: handled by stages 3 and 9.
- [x] Where synthesis runs: two SHARC ADSP-21489, 10 voices each; the ARM writes their
  parameters in memory through `hw_write` (`docs/sharc.md`).
- [x] **Bend path** (2026-11-18): MIDI bend → slot parameter 0x23 → bend object of the
  slot's engine (`engine+0x28C`), smoothed over 32 ticks → read by each voice in
  `voice_pitch_offset`, next to the voice's own glide. **Non-linear curve beyond 2
  semitones** (linear then parabolic): MPE at ±48 uses its own scale. Bend Range = engine
  parameters 0x21 (both directions) / 0x22 (downwards). The panel's pitch stick: path not
  found, to test on the instrument.
- [x] **Slot Note On → allocator** (2026-11-18): the channel disappears as soon as the
  slot is called ({note, velocity} pairs). Chain: destination filter → arpeggiator → slot
  output → event queue {type, slot, note} → note handler (visitor pattern, 6 types). Note
  table = tree keyed by `note | slot << 8`.
- [x] **MIDI menu** (`docs/menus.md`): page and entry construction (`menus_build`), global
  settings (34 descriptors at `0xc03bff00`, `global_get` / `global_step`, the number is
  fixed at 34), saving (fixed 38-byte record), navigation, display (ASCII, safe letters),
  automatic flash write (2 s timer). Our options are bit fields of setting 0x21.

Details: **`docs/voices-midi.md`**. Function names: `tools/symbols.txt`.

## Environment

- Container `pyghidra-nl4` (port 8003), project `ghidra/nl4_ghidra.gpr`, program
  `/nl4_os132_full.elf-<suffix>` (the suffix changes at each import:
  `list_project_binaries`). MCP server declared in `.mcp.json`. Other pyghidra containers
  (octalab, p12, sharc) belong to other projects: **do not touch them**.
- The Mac update program is also in the Ghidra project (`/nordosupdate_x86_64-<suffix>`,
  x86_64 slice extracted with `lipo`, see `docs/update-protocol.md`).
- Ghidra chose `ARM:LE:32:v8`. The real core is an ARM926 (v5TE). No visible effect so
  far.
- The pyghidra-mcp metadata sheet shows "0 instructions / Analyzed false", but the
  analysis did run: thousands of `FUN_c0…` functions.
- The manual as text: `vendor/manual.txt` (generated by pdftotext, not in git).

## What the manual says (v1.x, 2013)

- **20 voices in total**, shared between the 4 slots (A–D). Unison and Chord Memory reduce
  polyphony.
- **Performance** = 4 programs (one per slot), layered or split (A+B on the left, C+D on
  the right), 99 locations.
- **MIDI channel per slot** (A, b, c, d: 1–16 / Off) + global channel. A slot assigned to
  a channel plays even if it is not active on the panel.
- **Bend Range per program**: 1–12, 24, 48, and asymmetric −12/−24 (2 downwards). The ±48
  of MPE therefore already exists.
- **Voice Mode** per program: Poly, Mono, Legato, Unison (several levels), Glide.
- Two focuses: **Keyboard Focus** (slots played by the keyboard, LED lit) and **Panel
  Focus** (a single slot, blinking LED, edited by the panel). The user thinks the pitch
  stick only acts on the active slot outside Performance: **to check on the instrument**.
- **Morph sources**: wheel / expression pedal, velocity, 3 Impulse buttons. The keyboard
  has no aftertouch sensor, but the MIDI chart (p. 47) gives Channel Aftertouch
  **transmitted and recognised** (Poly AT not). In the code, received pressure becomes the
  slot's internal controller no. 8, which drives nothing (dead code).
- The MIDI menu has a "Pitch Bend Mode" (Sr / r / S / Off).

## Leads in the firmware

| String | Address | Referenced from |
|---|---|---|
| `Unison` | 0xc01ca38c | 3 pointers |
| `Legato` | 0xc01c9180 | 2 pointers |
| `Polyphonic` | 0xc01ca2f0 | 1 pointer |
| `Alloc State` | 0xc01bde80 | `FUN_c0027670` → `fn_c001c77c(allocator, "Alloc State")`: debug display of the allocator |

Check of the corrected layout: 353 of the 364 strings of the data area are pointed to
exactly; 3,737 of 3,738 code table entries fall on a function start. The `FFS…` strings
denote a flash file system (programs / performances). `WaveTable Version: 05`.

## Bootloader

It is **not** in `os.cab`.
- Image 2 is a **factory test / service** program: "LCD Test", "MIDI Test", "Check LEDs",
  "Serial Number", SPI flash identifiers (Micron N25Q032, SST 25VF032/26VF032). It runs at
  the same addresses as the OS.
- The processor is an **AM1705** (OMAP-L137 family, ARM only), with two SHARC ADSP-21489
  for audio and a Micron N25Q032 SPI flash (U38). See `docs/hardware.md`.
- Boot most likely goes through the AM1705 ROM (loading an AIS image from the SPI flash),
  then a Clavia 1st stage in flash, not part of the update.
- The loader (mode 5, Boot) and the update program (mode 4, Update) are not in `os.cab`
  (`docs/update-protocol.md`).
- **Update mode without the OS: confirmed** on the instrument (Shift + Store at power-on →
  "RDY", recognised by Nord OS Update).

## SHARC (exploration of 2026-11-18, `docs/sharc.md`)

Two SHARC programs in the ARM OS (0xc03c5720, 0xc03d9334), extracted by
`tools/extract_sharc.py`, opened with the extension built in the Prophet 12 project. The
SHARC is an engine whose parameters the ARM writes in memory ([cmd|address, value] pairs
through `hw_write`), smoothed at each block: **nothing to change on the SHARC side for
MPE**.

## Plan (agreed with the user on 2026-11-18)

1. **Step 1 — mapping (analysis, no risk)**: done (`docs/voices-midi.md`). Remaining
   details: the panel's pitch stick, the exact roles of the two allocation paths
   (`alloc_pick` / `alloc_core`), the bits of the voice-stealing key, the frequency of
   `synth_tick`.
2. **Step 2 — feasibility verdict**: written (`docs/feasibility.md`): feasible with an ARM
   patch alone. The user decided to continue.
3. **Step 3 — safety before any write: done (2026-11-18).** Checksums reproduced; update
   protocol read; Update mode through Shift + Store confirmed; flash backup dropped (U38,
   read cleanly, is **empty**; the firmware is in another memory, not reachable without
   taking the board out, `docs/hardware.md`). The `CLAUDE.md` rule was updated with the
   user's agreement.
4. **Step 4 — progressive prototype**: stages 0 to 11 (`docs/patches.md`), all tried on
   the instrument. Quit the updater after each update.

## Working method that works

- Ghidra (MCP server) for renamings and spot checks. For bulk searches, use
  `ghidra/bin/decomp.c` (≈ 5,000 functions in pseudo-C) with grep / Python. It is the
  quality reference: `tools/dump_decomp.py` disables the "Non-Returning Functions -
  Discovered" analyser. The MCP server keeps the default analysis.
- Why this option: `operator_new` calls the routine that throws `bad_alloc`, Ghidra infers
  that `operator_new` never returns, and stops disassembling after each `new` (hundreds of
  truncated functions, "Subroutine does not return").
- Function starts (`ghidra/bin/funcs_seed.txt`, generated by `tools/rebuild.sh` with
  `tools/find_func_starts.py`, plus `tools/seeds_low.txt` for SRAM and ARM0): `bl`
  targets, pointer table entries, and `push {…, lr}` **only** after a return or a branch.
  A `push` in 2nd position (`operator_new` starts with `cmp r0, #0`) must not become a
  start: it splits the function in two.
- `ghidra/bin/vtables.txt` (generated by `tools/rebuild.sh` with
  `tools/find_ptr_tables.py`; not in git, like `funcs_seed.txt`: they are data extracted
  from the firmware) lists the tables of pointers to code. Since the address correction,
  3,737 of 3,738 entries fall on a function start. A C++ vtable (Itanium ABI) is read at
  `vptr`; an entry `sub r0, r0, #N ; b …` is a `this`-adjusting relay (multiple
  inheritance) to the real method.
- MIDI goes through a **subscription bus**: do not look for direct calls between reception
  and the slots; start from the types (0xc09140a8…e8) and `midi_subscribe`.
- The decompressed CODE is validated: the official liblzo2 library (Homebrew `lzo`) gives
  exactly the same bytes.
- **Functions missing from the pseudo-C**: the methods of the parameter tables
  (`engine_param_handler`, `voice_param_handler`) are only reached through pointers stored
  in literal pools, or through a final `b`. The seeds do not find them: they have to be
  named by hand in `tools/symbols.txt`. To read a method, take the parameter number → the
  pool value (`DAT_…`) → `disassemble` on the server.
- No RTTI in the firmware: no class names, name things by hand in `tools/symbols.txt`,
  then `tools/rebuild.sh` and re-import.
- **Lesson (2026-11-19)**: replacing a vtable pointer is not enough. An object with
  several sub-objects is called through the **sub-object's** vtable, often a relay
  `sub r0, r0, #N ; b method` that jumps directly. Look for all paths to the method
  (pointers **and** `b` / `bl`) before choosing where to hook.
- Lesson: a function address (position in the image) and an address read from a literal
  pool (absolute value) are not checked the same way. Always check the layout with global
  statistics (pointers to strings, table entries), not on a few cases: that is how the
  0x20 offset was found.

## Risks

- Flashing a modified image can **make the keyboard unusable** if the loader refuses it or
  if the OS crashes at boot. Recovery: Shift + Store, then the official OS.
- Rights: Clavia's firmware and software stay out of the repository. Only notes, formats
  and our own code are published (same line as
  [opennord](https://github.com/simonflore/opennord)). Licence GPL v3 + exception, like
  P12 M (`LICENSE`, `LICENSE-EXCEPTION.md`).

## Ideas for after MPE (proposed by the user, 2026-11-18)

The user's priorities: **helper functions (converting a program to MPE) first of all**;
**Y / Z modulation sources separate from Velocity** interest them (partly done in
stage 11); new wavetables are only an example, not a goal (the synth is already complete).

- **"Convert for MPE" function** in the manner of the Mutator (`docs/feasibility.md`).
- **New wavetables.** Quick look **[hyp.]**: the tables are on the ARM side, a
  high-entropy data block from 0xc01d0000 to ~0xc03bd000 (≈ 1.9 MB for 128 tables,
  ≈ 15 KB each, probably several levels per table), names around 0xc03bd800, "WaveTable
  Version" at 0xc01ca768; the ARM probably sends them to the SHARC on demand (the SHARC
  does not have 1.9 MB of RAM). The manual announces 128 tables in one chapter and 114 in
  the specifications: maybe free slots. Replacing a table costs no space; adding beyond
  128 touches the program format and CC49 (0–127). Samples compress badly: count
  ≈ 15 KB of flash per table, on a known margin of 200 KB.
