# Menus (System, MIDI, Sound): study

Goal: add the MPE options to the MIDI menu (done in stages 10 and 11, `docs/patches.md`):
MPE Off / zone, Y and Z destinations, curves, bend range, A–D channels ignored in MPE mode.

## What the manual shows (p. 43)

The display is an LED display with a few characters. A menu entry = a letter or a digit,
then its value. MIDI menu: `G` global channel, `A b c d` slot channels, `t` Soft Thru,
`1` interface (P / U), `2` Local, `3` Control Change Mode (Sr / r / S / Off),
`4` Program Change Mode (same range), `5` Pitch Bend Mode (same range), `6` Send CC,
`7` Dump One, `8` Dump Program Bank. "Local" goes back to On at each power-on.

## Labels  [sure unless stated]

- **Labels in ASCII**, converted for the display elsewhere **[hyp.]**:
  - `0xc03c32b8…0xc03c3304`: `On `, `Of`, `Hej`, `%2d.`, `34`, ` 1`…` 4`, `c1`, `c2`, `r5`,
    `r7`, `y7`, `KO`, `Ft`, `AU`, `CL`, `OP`, as well as `%s.%s`, `%s.--`;
  - `0xc03c3b48…`: ` S`, ` r`, `Sr`, `CC`, ` Ok`, `Abt`, `Pr`, `bn`.
- Entry letter: a one-character string passed to the constructor (`"1"` at `0xc01ca280`,
  `"G"` at `0xc03c21a8`, `"t"` at `0xc0404880`…).

## Building the menus (2026-11-19)  [sure]

`menus_build` (`fn_c00fb7a4`, 0xe0-byte object stored at `0xc04edce8`, called by
`fn_c00fc4a8` at boot with the application object `app`) creates the pages, then each
entry through `operator_new` + constructor, and adds it with
`menu_page_add(list, page no., entry)` (`fn_c0124cec`). A page (0x238 bytes) keeps its
count at `+0x24` and its entries at `+0x28…`: **131 slots**, so there is room to add
entries. The page number is at `page+0x234`.

| Field of `menus_build` | Page | Entries (in order) |
|---|---|---|
| `[0x2f]` | System | 1…8, then 4 entries A–d (`fn_c00fecbc(i)`) |
| **`[0x30]`** | **MIDI** (`fn_c00fd0b0`) | **G, A, b, c, d, t, 1…8** (next table) |
| `[0x31]` | Sound | 1 (`fn_c0100ed8`, added after the MIDI menu), 2…5 |
| `[0x2d]`, `[0x2e]`, `[0x32]`–`[0x34]` | others (Mutator, etc., not identified) | |

MIDI menu, entry by entry:

| Letter | Constructor | Size | Main vtable | Global setting no. |
|---|---|---|---|---|
| G | `fn_c0101cd8` | 0x60 | `0xc03c45d0` | 6 (def. 0, max 16 = Off) |
| A b c d | `fn_c0101da8(i)` | 0x64 | `0xc03c4350` | none: not in the global table |
| t | `fn_c0101d40` | 0x60 | `0xc03c4490` | 0x1a (def. 16 = Off) |
| 1 Interface | `fn_c010173c` | 0x60 | `0xc03c47b0` | 7 |
| 2 Local | `fn_c01000b4` | 0x60 | `0xc03c35d8` | 5 (not saved, as in the manual) |
| 3 CC Mode | `fn_c0100120` | 0x60 | `0xc03c3678` | 8 |
| 4 PC Mode | `fn_c010018c` | 0x60 | `0xc03c3718` | 9 |
| 5 PB Mode | `fn_c01001f8` | 0x60 | `0xc03c37b8` | 0x1d |
| 6 Send CC | `fn_c010028c` | 0xa4 | | (action) |
| 7, 8 Dump | `fn_c0100504`, `fn_c010066c` | 0xac | | (actions) |

## A menu entry  [sure]

- Base: `menu_entry_ctor` (`fn_c0125368`), **7 sub-objects** of 12 bytes (at `+0`,
  `+0xc`, …, `+0x48`), each subscribed to the bus through `midi_subscribe`. Fields:
  `+0x54` = `app`, `+0x58` = 3rd parameter, `+0x5c` = label, `+0x51` = active entry (read
  by `menu_entry_is_active`, `fn_c0125514`).
- The constructors of entries 2 to 5 set the 7 vptrs from **a single base** `0xc03c35d0`
  (+8, +0x48, +0x58…): that is why no vtable appears as a literal.
- Main vtable (indices): `[12]` = formatting `(this, value, buffer, size)` (e.g.
  `fn_c00ffd28`: 0…3 → `Of` / ` S` / ` r` / `Sr`), `[13]` = display
  `(this, buffer, size)` = `formatting(global_get(app, no.))`, `[5]` = knob turn.
- **Knob turn** (`fn_c0100a20` for PB Mode): only acts if the entry is active and the event
  is of type 2; then `global_step(app, no., 0xc08ee8b8, 1, delta)` (`fn_c00e2824`).
- **Lesson from stage 5, still true here**: the knob turn arrives through the sub-object
  `+0xc` (subscribed to the bus), whose vtable (`0xc03c37f8` for PB Mode) contains the
  relay `sub r0, r0, #0xc ; b fn_c0100a20`. A new entry must therefore provide **its main
  vtable and that of the `+0xc` sub-object** (at least).

## Global settings  [sure]

- Read: `global_get(app, no.)` (`fn_c00e270c`), write:
  `global_step(app, no., source, clamp, delta)` (`fn_c00e2824`). The model is `app[0x52]`
  (`app+0x148`), built by `global_model_ctor` (`fn_c00ed8b0`, internal name
  "CRouterParam" by default). Its parameter table (`fn_c00edda0` → `param_table_ctor`,
  `fn_c010e4f0`) receives **the descriptor array `0xc03bff00` and the count 0x22** (34
  settings, no. 0 to 0x21). The table allocates its arrays from that count: adding some
  would only require copying the array elsewhere and changing pointer + count (but see
  "What this allows": the listener has fixed arrays).
- `global_step` (via `fn_c011eeb8`): value + delta, clamped if `clamp = 1`, otherwise
  wrapping from 0 to max.
- Descriptor = 7 words: `[no., default, max, bits, ?, flags, CC]`. Byte `+0x15` (flags
  0x100) = **saved**; a change marks the table as modified (`table+0x1c`) and calls
  `table+0x20`. CC = associated MIDI CC number, −1 otherwise (id 3 → CC 119, id 4 →
  CC 115, id 0x18 → CC 58).

| no. | def. | max | bits | saved | known role |
|---|---|---|---|---|---|
| 0 | 0 | 127 | 0 | no | |
| 1 | 0 | 1 | 1 | yes | |
| 2 | 0 | 99 | 7 | yes | |
| 3 | 0 | 3 | 2 | yes | CC 119 |
| 4 | 1 | 15 | 4 | yes | CC 115 |
| 5 | 1 | 1 | 1 | no | Local (MIDI 2) |
| 6 | 0 | 16 | 5 | yes | global channel (MIDI G), 16 = Off |
| 7 | 2 | 2 | 2 | yes | interface (MIDI 1) |
| 8 | 3 | 3 | 2 | yes | CC Mode (MIDI 3) |
| 9 | 3 | 3 | 2 | yes | PC Mode (MIDI 4) |
| 0xa | 6 | 12 | 4 | yes | Transpose (System 2), 6 = 0 |
| 0xb | 50 | 100 | 7 | yes | Fine Tune (System 3), 50 = 0 |
| 0xc | 2 | 4 | 3 | yes | |
| 0xd | 0 | 2 | 3 | yes | Sustain Pedal Polarity (System 4) |
| 0xe | 0 | 4 | 3 | yes | Ctrl Pedal Type (System 5) |
| 0xf | 0 | 1 | 2 | yes | Ctrl Pedal Mode (System 6) |
| 0x10 | 0 | 9 | 4 | yes | Ctrl Pedal Gain (System 7) |
| 0x11, 0x12 | | | | yes | (0x11: entries `0xc03c3e90` / `0xc03c3f68`, page not identified) |
| 0x13 | 0 | 1 | 1 | yes | Delay Mode (Sound 2) |
| 0x14 | 50 | 100 | 7 | yes | Vibrato Rate (Sound 3) |
| 0x15 | 25 | 50 | 6 | yes | Vibrato Amount (Sound 4); set to 15 by the v2 → v3 converter |
| 0x16–0x18 | | | | yes | |
| 0x19 | 0 | 2 | 2 | yes | (Mst Clk Kbd Sync, Sound 1, 3 values? **[hyp.]**) |
| 0x1a | 16 | 16 | 5 | yes | Soft Thru (MIDI t), 16 = Off |
| 0x1b | | | | no | (entry `fn_c0102d04`, Mutator history?) |
| 0x1c | 0 | 1 | 0 | no | Impulse Morph Protect (System 8) |
| 0x1d | 3 | 3 | 2 | yes | PB Mode (MIDI 5) |
| 0x1e | 1 | 1 | 1 | yes | |
| 0x1f, 0x20 | 0 | 1 | 1 | no | |
| 0x21 | 0 | 0 | 31 | yes | ? (max 0: always 0) — **carries our MPE options** (max raised by `build.py`) |

## Saving the global settings  [sure unless stated]

- File type no. 1 of the storage manager (`storage_ctor`, `fn_c00faaf4`; `fn_c00f9ec8`),
  bound to the reference of the global model (`0xc04e6b5c` = `0xc04e6ac8 + 0x94`, filled
  by `app_midi_graph_ctor`).
- **Fixed-size record: 38 bytes** (`fn_c00fa060`: field `+0x18 = 0x26`; buffer allocated
  by `fn_c0122b64`).
- Format: **16 bits of version (3)**, then each saved setting in number order, on its
  number of bits, **without a tag** (`param_table_load`, `fn_c010ee60` → `fn_c010ec60`). A
  value outside `0…max` goes back to the default. Total in 1.32: 144 bits = 18 bytes:
  **20 bytes (160 bits) are left free** in the record.
- Check by computation: the v2 → v3 converter (`fn_c00f8b18`) rewrites 6 bits at bit 88
  and the version at bit 0; bit 88 falls exactly on no. 0x15.
- Versions: `fn_c00f83e4` upgrades the read version step by step through the table
  `0xc03c1af0` (only v2 → v3 exists); unknown version (> 2 and ≠ 3) → error 6. The bit
  reader (`fn_c012a950`) does not check the end of the buffer.

## What this allows for the MPE options

1. ~~New settings from 0x22 on~~: **tried, the keyboard no longer boots** (stage 10, 1st
   version). The listener of the global settings (`fn_c00e3f70`) stores 34-cell arrays in
   its own object: **the number of settings is fixed at 34**.
2. Chosen: setting **0x21** (saved on 31 bits, max 0, unused) carries our options as bit
   fields; only its maximum is changed.
3. **New entries**: call `menu_page_add` on the MIDI page at the end of `menus_build`,
   with entries cloned from PB Mode (constructor `fn_c01001f8`, then our copies of the main
   vtable and of the `+0xc` sub-object's vtable, with our display, formatting and knob
   functions for our numbers).
4. Read by our MPE code: `global_get(app, no.)`, instead of the "global channel = 1" of
   stages 2 to 9.

## Navigation (2026-11-20)  [sure]

- Opening: `menus_on_button` (`fn_c00fb204`, vtable of the menus object `0xc03c2178`)
  receives the panel buttons. With Shift, 0x1b / 0x1c / 0x1d open System / MIDI / Sound
  (slot buttons A, B, C); 0x14 and 0x15 open two other pages. Page change:
  `menu_list_show_page` (`fn_c0124e7c`), current page at `list+0x88`.
- Dial: `menus_on_dial` (`fn_c00fb18c`) receives the type 2 event. **Without Shift** (bit 0
  of `ev+4`, read by `fn_c0131938(0, …)`), it moves the current entry: `menu_list_step`
  (`fn_c0124e6c`) does `entry = bound(current + delta, 0, count − 1)` on `page+0x24`.
  **With Shift**, the active entry receives the turn (its `[5]`).
- Entries added at the end of the MIDI page are therefore reachable **without any other
  change**. The chosen entry becomes active (`+0x51 = 1`) then `vt[3]`; it is deactivated
  by `vt[4]` (after `vt[11]`, which may refuse).

## Display  [sure unless stated]

- `vt[2]` of an entry refreshes the display: `vt[13]` writes the value into a 4-byte
  buffer (`0xc04edd1c`), then `led_printf(display, "%s.%s", label, value)`
  (`fn_c0145530`, the same function that shows "1.32" at boot). For PB Mode: "5.Sr".
- The ARM sends **ASCII** to the driver (`fn_c01452f0`, one character per position). The
  7-segment font is in none of the images of `os.cab`, as bytes, words or inverted logic:
  the conversion happens elsewhere **[hyp.: hardware or another processor]**.
- Safe letters, since the OS already shows them: digits, `A b C c d E e F G H i j K k L n
  O o P r S t U u v y`, `-` and the dot. Examples: `Abt`, `Hej`, `PSt`, `CPy`, `FuL`,
  `rcv`, `E.Sy`, `E.vE`, `E.Ck`, `KO`, `Ft`, `AU`, `CL`, `OP`, `y7`, `r5`. Existing entry
  labels: `1`…`8`, `G`, `A b c d`, `t`. Free for our entries: `9`, and for example `P`,
  `y`, `U`, `H`, `L`, `n`, `r`, `S`. A `Z` would show as a `2` and a `v` reads as `U`.

## Writing to flash  [sure]

- Save object of the global settings, created by `storage_ctor` (vtable `0xc03c2090`,
  listens to the global model through `fn_c0123120`):
  - a saved setting changes → `fn_c00fafa4` sets "to be written" (`+0x18 = 1`);
  - **2000 ms timer** (`fn_c01320a0(…, 2000)`, callback `0xc00fb094`): if writing is not
    blocked (`+9`), `fn_c00fb048` checks whether the model has changed (router `vt[13]`)
    and starts the write;
  - `fn_c00fafe0` writes the record (`manager->vt[0]`) then clears the mark (router
    `vt[14]`);
  - a bus event `0xc08eee38` forces the write (value 0) or blocks it (`+9`).
- Consequence: our settings are written **without any code of ours**, at most 2 s after a
  change, like the original settings.

## Slot channels A–d (2026-11-20)  [sure]

- Not in the global table: each slot i has its own model `app[0x53 + i]`
  (`app+0x14c + 4i`), setting no. 1. Read `fn_c00e2740(app, i, 1)`, dial
  `fn_c00e2894(app, i, 1, …)` (entry `fn_c0101da8`, vtable `0xc03c4350`: `[5]`
  `fn_c0101be8`, `[13]` `fn_c0101ba8`).
- `fn_c00e0960` (change of a channel) sets `app[0x1fe]`; `app_routing_update` then copies
  global and A–d (`app+0x1d4…0x1e4`) into the **effective** channels `app+0x1e8…0x1f8`
  (A–d equal to the global → 16 = Off), then creates the zones (`fn_c00df898`) and the
  masks. Stage 11 sets to Off (in MPE mode), in these effective fields, the A–d channels
  that fall on a member channel.

Still to read: no. 0xc, 0x11, 0x12, 0x16 to 0x18 (no effect on the project).
