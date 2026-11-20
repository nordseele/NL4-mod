# MIDI input and voices — research notes (OS v1.32)

Names come from `tools/symbols.txt`, carried by the ELF (`tools/rebuild.sh`). The full
pseudo-C is regenerated with `tools/dump_decomp.py` into `ghidra/bin/decomp.c` (not in
git). Legend: **[sure]** read in the code; **[hyp.]** inferred, to be confirmed.

> **Addresses corrected on 2026-11-18.** Before the commit following `6c7f2fb`, the image
> loaded the 0x20-byte section header: all **function** addresses in earlier notes were
> 0x20 too high. Addresses of **global variables** (read from literal pools, e.g.
> 0xc04b0040) were already right.

## MIDI receive chain  [sure]

```
USB-MIDI (4-byte packets, CIN → length)          DIN (5-pin port)
  usbmidi_rx_packets / …2   c013e930 / c013e7f0      fn_c014c590 creates its parser
        └────────────── midi_parse_byte (c013c6c8) ──┘
             running status, SysEx (F0…F7), real time F8–FF
             └─ midi_rx_to_queue (vtable 0xc0400eb0): each message becomes a
                0x40-byte object {type, port (+4), channel (+5), arg1 (+8), arg2 (+0xC)}
                stored in a queue (outside the interrupt)
                  └─ subscription bus: midi_subscribe(sub-object, type, priority, flags)
                       └─ application handlers (area c011f000–c0122800)
                            └─ for each target (slot…): test of the (port, channel) mask
```

### Methods called by the parser

| vtable | message | arguments |
|---|---|---|
| +0x00 | Note On | (channel, note, velocity); velocity 0 → Note Off with velocity 0x40 |
| +0x04 | Note Off | (channel, note, velocity) |
| +0x08 | Poly Aftertouch (0xA0) | (channel, note, value) |
| +0x0C | Control Change | (channel, CC no., value) |
| +0x10 | Program Change | (channel, program) |
| +0x14 | Channel Pressure (0xD0) | (channel, value) |
| +0x18 | Pitch Bend | (channel, signed value −8192…+8191, already centred) |
| +0x1C | end of SysEx (buffer) | |
| +0x2C | Tune Request (0xF6) | |
| +0x30 | clock / real time | |

Three classes implement this interface: `midi_rx_to_queue` (0xc0400eb0, connected to the
parsers), a **MIDI transmitter** (0xc0400d70, encodes USB-MIDI packets into an output
buffer) and a variant of the transmitter (0xc0401128).

The manual's MIDI implementation chart (p. 47) confirms: **Channel Aftertouch transmitted
and recognised**, Poly Aftertouch ("Key's") neither transmitted nor recognised, Pitch Bend
transmitted and recognised.

### Message types (subscription bus)

The "type" of a message is the address of a RAM location; handlers subscribe to it at
boot (`midi_subscribe`, c013135c).

| Type | Message |
|---|---|
| 0xc09140bc | Note On |
| 0xc09140c0 | Note Off |
| 0xc09140b0 | Pitch Bend |
| 0xc09140b4 | **Poly AT and Channel Pressure (same type)** |
| 0xc09140b8 | Program Change |
| 0xc09140ac, c4, c8, cc, d0 | Control Change (5 types: a few CCs handled separately) |
| 0xc09140a8 | SysEx |
| 0xc09140d4 … e8 | real time / clock / misc. |

### Internal controllers  [sure]

Table read in MIDI transmission (`fn_c011f36c`, output queue):

| internal no. | MIDI |
|---|---|
| 5 | CC4 |
| 6 | CC11 (expression pedal) |
| 7 | CC1 (wheel) |
| **8** | **Channel Pressure (aftertouch)** |
| **9** | **Pitch Bend** (signed 16-bit value) |
| 10 | CC7 (volume) |
| 11 | CC10 (pan) |
| 13 | CC70 |
| 3 | CC82 |

On reception, `midi_bend_in` (c0120398) and `midi_pressure_in` (c01202ac) walk the list
of targets and call `target_controller_in(target, port, channel, no., value)` (c0112fac)
with no. = 9 and 8. **Received aftertouch therefore becomes an internal controller (no. 8)
of the slot.** What it modulates is still to be found.

### Channel → slot routing: bit masks  [sure]

`target_controller_in`:
1. is the target active (`+0x20`)?
2. **bit `channel + 16 × port`** of the target's mask (words from `+0x10`);
3. is the controller allowed on reception (`+0x2D1 + no. × 0x18`)?
4. scaling (`fn_c011f004`), storage **per target and per controller**
   (`+0x2D4 + no. × 0x18`), then `target->vt[0](target, no., value, 0)`.

Each target has **several masks** (`+0x10`, `+0x54`, `+0x5C`, `+0x68` depending on the
class), filled by `mask_add_channel` (c0114524) and its variants (c011c344, c011c374,
c011c3a4); channel 16 ("Off") is ignored. Configuration happens in `midi_routing_setup`
(c00dee54): for each enabled port (`+0x1FC`, `+0x1FD`, probably USB and DIN), it adds a
channel (`+0x1E8`) to the masks of several targets, testing slot by slot whether it is
active (`fn_c010bb1c(…, i)`).

**Consequences for MPE:**
- A slot can **already listen to several channels**: routing is a bit mask, not a channel
  number. An MPE zone = adding the member channels (2–16) to the slot's mask in
  `midi_routing_setup`.
- Pitch bend and pressure are **stored per target (slot)**, one value shared by all its
  voices. This is where the path has to be diverted to a per-note value: keep the original
  channel, find the active note on that channel, and apply the value to its voices only.

### Note path  [sure up to the targets]

```
type Note On (0xc09140bc)
  └─ midi_note_handlers_ctor (c0121580): 10 subscriptions (Note On/Off, 4 CC types…),
     each through a this-adjusting relay (sub r0, r0, #N ; b …)
       └─ midi_noteon_dispatch (c011fec8) / midi_noteoff_dispatch (c011fdcc)
            └─ targets_call_member (c011f62c): for each target in the list,
               call of a member function pointer (ARM ABI {ptr, adj})
                 └─ target_note_on (c011129c) / target_note_off (c0111424)
```

`target_note_on(target, port, channel, note, velocity)`:
1. `target_find_zone` (c011ecc8) looks up the **(port, channel)** pair in the target's
   list (`+0xF0`: count at +4, ports at +8, channels at +0xC) → **zone index**;
2. zone table (`target[0x31]`): active zone, **key range** (low and high bounds = split)
   and **transposition** (offset + octave × 12) → final note;
3. table **[zone][input note] → sent note** (128 entries per zone): if the input note is
   already held, a Note Off is sent first;
4. sent by `target->vt[0](target, 3, {note, velocity})` (method overridden by the derived
   class). `target_note_off` reads back the stored note, switches it off through `vt[1]`
   and resets it to −1.

Targets (`note_target_ctor`, c0112b64) register in a global list on construction. The
number of zones is global (`*DAT_c0112d9c`). They are **composite objects**: controller
part (mask, `fn_c0114590`) at +0, note part at +0x430, and for some a 3rd part at +0x53C.
Everything is assembled by `app_midi_graph_ctor` (c00e107c), whose masks are then filled
by `midi_routing_setup` (fields [0x52], [0x57], [0x58]+0x53C, [0x5C]).

**For MPE:**
- A zone = a (port, channel) pair. Declaring each member channel as a zone of the same
  target would give each channel **its own 128-note table**: no more collision between
  channels at this level, without changing the structure.
- But the channel goes no further: the target calls the slot with {note, velocity} pairs
  only (section "From the slot to the allocator").

### From the targets to the slot  [sure]

- `slot_midi_input_ctor` (c00f1c5c, slot number as parameter) builds **the MIDI input of a
  slot**: the note part has **the slot itself** as destination
  (`fn_c01108fc(note part, slot)`), the controller part has the slot's 2nd interface
  (`slot + 4`) as destination.
- The 2nd argument of the note methods is a **destination mask**: bit 1 = MIDI OUT (class
  `fn_c01289a4`, output queue per (port, channel) pair), another bit = internal synth. A
  3rd destination class (`fn_c00f8154`) only counts the held notes (indicator).
- `slot->vt[0]` = **`slot_note_on`** (c000f044): computes for the note the values of the
  **velocity morph and keyboard tracking** (`(note − 64) × 0x10000`, `velocity >> 3`,
  base + velocity × amount, bounded, for each morph destination), applies them to the
  slot's engine, then passes the note on to the object at `slot+0x20`. This computation
  only happens if bit 2 of the mask is set.
- Consequence for MPE: the velocity morph is **computed at Note On, at the slot level**.
  It is a natural place for a per-note modulation (Y/Z), provided it is made continuous
  and per voice.

### From the slot to the allocator  [sure]

The note methods of the whole chain have the same shape: `vt[0]` = Note On, `vt[1]` =
Note Off, arguments `(object, &mask, notes, count)`, where `notes` is an array of
**{note, velocity}** pairs. One call can therefore carry several notes (chord, Chord
Memory **[hyp.]**).

```
slot_note_on (c000f044)                    velocity morph if mask & 2
  └─ slot+0x1C = slot+0x20: destination filter (0x88 bytes, vtable 0xc01bd848)
       note_dest_filter_on / _off (c00121b8 / c00123b4)
       one state byte per note (128): on which destinations the note was started,
       so that the Note Off goes back to the same place
  └─ slot+0x18: arpeggiator (0x460 bytes, vtable 0xc01bd8c0)
       arp_note_on / _off (c00148f4 / c0012a68); passes through if the arpeggio is off
       (flags +0x1D, +0x1E, +0x458; 128-note tables at +0x10 / +0x14)
  └─ slot+0x14: slot output (8 bytes {vtable 0xc01bd6d8, slot no.})
       slot_sink_note_on → slot_queue_note_on (c0028780)
       slot_sink_note_off → slot_queue_note_off (c0027888)
            └─ the slot's key table, event queue, then note_queue_drain
```

`slot_arp_param_in` (c000fb8c, formerly `slot_controller_in`) sets the object at
`slot+0x18`, hence the arpeggiator **[strong hyp.]**.

**`slot_queue_note_on(slot no., notes, count, &mask)`**, for each note:
- mask & 1: purge of pending events for (slot, note), creation of the note in the
  **note table** (`notemap_create`, with slot settings: `+0x22C`, `+0x22D`, `+0x258`),
  then an immediate type 1 event;
- mask & 2: update of the slot's 128-key table (held, lowest, highest), velocity `>> 3`
  in the note, immediate type 2 event, then **two queued events: type 3 then type 4**. A
  global observer (`*0xc040d3e4`, method 2) receives (slot, note, velocity);
- mask & 4: type 6 event.

`slot_queue_note_off` updates the key table and queues a type 5 event. The observer
receives the note through its method 3.

**Event queue**: pool of 0x800 16-byte entries `{vtable, type (+4), slot (+8), note
(+0xC)}` at `0xc04a6578`, and a ring of 0x200 pointers (count, read, write at
`0xc04af1f0 − 0xC74 / −0xC70 / −0xC6C`). `note_queue_drain` (c0027708) runs them in
order. A type 3 event waits as long as the voices of the previous note have not decayed
enough (threshold 0x8000).

**Visitor pattern**: an event calls a method of the **note handler** (`0xc04ae578`,
vtable `0xc01bde50`) with itself as argument:

| type | event vtable | handler method |
|---|---|---|
| 1 | 0xc01bddf0 | vt[0] = `note_ev1_alloc_voices` (c0026ae0) |
| 2 | 0xc01bde00 | vt[1] = `note_ev2_handler` (c0026d50) → `alloc_ev2` → `alloc_core` |
| 3 | 0xc01bde20 | vt[2] = `note_on_build_voices` (c00268d0) |
| 4 | 0xc01bde10 | vt[3] = `note_event_handler` (c00263b4) |
| 6 | 0xc01bde30 | vt[4] = `note_ev6_handler` (c0026c34) |
| 5 | 0xc01bde40 | vt[5] = `note_off_event` (c002718c) → `alloc_note_off_collect` |

**Two allocation paths, both active:**
- type 1 (mask & 1): `note_ev1_alloc_voices` (formerly `note_off_release_voices`, a wrong
  name) reads the note's mode (`fn_c0016070`). Mode 1 → `alloc_take_mode1` (c0018dcc),
  which reuses the voices of a note of the same slot (**[hyp.]** mono / legato). Modes 0
  and 2 → `alloc_take` (c0019220). Both sort the active notes (Shell sort), request
  `count × param[1]` voices (**[hyp.]** × unison) from **`alloc_pick`** (c0018324,
  2.7 KB), then prepare each returned voice (`fn_c0037db4`);
- type 2 (mask & 2): `note_ev2_handler` → `alloc_ev2` (c001a7a0) → `alloc_core`
  (c0019884).

`alloc_note_on` (c001b004) has no caller, neither direct nor through a pointer: it may be
dead code. The exact roles of the two paths (reservation then triggering?) remain to be
read.

**Note table** (`0xc040f470`): a binary search tree whose nodes of about 0x258 bytes have
their children at `[0x93]` / `[0x94]`. `notemap_has` / `notemap_get` / `notemap_create`
search with the key **`note | slot << 8`**, computed from the {slot, note} pair.

## Creation of slots and voices  [sure]

`synth_create_slots_and_voices(4, …)` (c0010a44), called at boot:

- 4 × `slot_ctor(obj, i)` (c000f314, 0x4B4 bytes, i = 0…3). Each slot contains a
  `slot_engine` (0x8B8 bytes, `slot_engine_ctor`, c001d610) with per-slot parameter blocks
  of 0xA0 bytes (2 × 0x50).
- 20 × `voice_ctor(obj, i)` (c002f1cc, 0x598 bytes, i = 0…19). Each voice registers in a
  **global array of 20 pointers** at `0xc04b0040`.
- Array of the 4 slots at `0xc040d3b0`.

The 20 voices form a single pool, shared by the 4 slots (confirms the manual).

## Voice  (0x598 bytes)

- `+0x00` = voice number; several sub-objects receive it too. **[sure]**
- `voice_pitch_to_hw` (c002cd10) and `voice_pitch_mod_update` (c002ebfc) compute the
  **per-voice pitch**: base + modulation (+0x160 / +0x17C / +0x168), exponential table
  (exponent + mantissa) → frequency, written by `hw_write(bit0(id), address, value)`
  (c014f0d0, ~300 calls). **[sure]**
- Hardware number (`+0x118`): `bit0` = one destination out of two, `>>1` = index.
  **[hyp.]** two synthesis chips / cores of 10 voices.
- **[strong hyp.]** The pitch is pushed voice by voice by the ARM: a per-note bend amounts
  to replacing, for one voice, the slot's bend component with a value of its own.

## Voice allocation

`note_event_handler` (c00263b4) is the note handler method called by the type 4 event
(section "From the slot to the allocator"). It finds the note in the table
(`notemap_has`, `notemap_get`), then handles: active entry, mode (1/2/3 — **[hyp.]**
poly / mono / legato), list of its voices, triggering or releasing each voice.

Allocator object: global, at `0xc04a7210 − 0xca0`. **[sure for the structure]**

| Field | Meaning |
|---|---|
| +0x04 | event counter (timestamp) |
| +0x6C | number of active notes |
| +0x70 | array of pointers to the active notes |

Active note:

| Field | Meaning |
|---|---|
| +0x00 | sort key (priority / age) — Shell sort in `alloc_note_on` / `alloc_update_sort` |
| +0x04 | timestamp / owner |
| +0x14, +0x18 | identity of the note: **(slot, note number)** |
| +0x1C | state (0–3) |
| +0x20 | flag set to 1 on release |
| +0x28 | number of voices used (unison > 1) |
| +0x2C | voices (pointers; voice number at +8) |

`alloc_note_on` (c001b004, no caller) and `alloc_ev2` (c001a7a0) prepare and sort, then
call **`alloc_core`** (c0019884). The type 1 path goes through `alloc_pick` instead
(section "From the slot to the allocator"); it remains to be compared with `alloc_core`.
What is known about `alloc_core`:
- pool of **64 notes** (0x80-byte entries), separate from the 20 voices;
- number of voices per note passed in the call: 1 in poly, more in unison;
- voices are taken from the notes at the head of the sorted list; the key combines state,
  age and other criteria (voice stealing). Bit layout not decoded.

## Identity of a note: (slot, note number)  [sure]

This is **the first obstacle for MPE**.

- Note events carry `+8` = **slot number** (index in the slot array) and `+0xC` = **note
  number** (pitch computed from `note − 64`).
- The allocator copies this pair (`+0x14`, `+0x18`).
- Each slot keeps a **128-key array** (`+0x1C`), the number of held keys (`+0x224`), the
  lowest and the highest (`+0x21C` / `+0x220`): `slot_queue_note_on` /
  `slot_queue_note_off` (c0028780 / c0027888).
- The MIDI channel is not there. **It disappears as soon as the slot is called**:
  `target_note_on` passes {note, velocity} pairs, without the channel.

Two fingers on the same pitch in the same slot (common on a LinnStrument) would be merged.
Places that index by note number, from first to last:

| where | structure | indexed by |
|---|---|---|
| target | table [zone][note] (one zone per (port, channel)) | already by channel |
| destination filter | 128 state bytes | note |
| arpeggiator | 128-note tables | note |
| slot | 128-key table | note |
| note table | tree | `note | slot << 8` |
| event queue | entry {slot, note} | (slot, note) |
| allocator | active note +0x14 / +0x18 | (slot, note) |

**Simplest idea**: pass an "extended" note `note + 128 × channel` from `target_note_on`
on. The 128-entry tables would become 128 × 16, or the arpeggiator and the filter would be
bypassed in MPE mode. The tree key (`note | slot << 8`) must then be widened
(`slot << 12`), otherwise note 256 of slot 0 equals note 0 of slot 1. Finally, the note
would have to be masked (`& 0x7F`) everywhere it is used for pitch:
`note_on_build_voices`, the keyboard tracking of `slot_note_on`, the display. (Stage 9
renumbers notes instead: `docs/patches.md`.)

## Building the voices of a note

`note_on_build_voices` (c00268d0): pitch of each voice =
`(note − 64 + offset_i) × 0x10000` (offsets: Chord Memory / unison **[hyp.]**). Release
(`note_off_event`, c002718c, type 5) goes through `alloc_note_off_collect` and depends on
the slot settings (`+0x22C`).

## Performance controllers of the slot

The slot inherits three interfaces (vtables at `0xc01bd738`, +0x60, +0x6C). The 2nd
(`slot+4`, a single method) receives MIDI controllers: relay `slot_midi_ctrl_in_thunk`
(c000fb44, `sub r0, r0, #4`) → **`slot_midi_ctrl_in`** (c000fa58).

`slot_controller_in` (c000fb8c) is **not** part of this path, despite its name: its
`switch` (0–9) acts on the object at `slot+0x18`, and it is called at initialisation
(`fn_c000fd80`). `fn_c00f04a4` is a switch over 77 parameters (0–0x4C) acting on the slot:
probably where CCs and panel settings arrive.

### `slot_midi_ctrl_in(slot, no., value)`  [sure]

Stores the value at `slot+0x224 + no. × 4` (>> 16), then converts it into a **slot
parameter** through `slot_set_param`:

| controller | slot parameter | condition |
|---|---|---|
| 5 (CC4) | 0x57 | |
| 7 (wheel) | 0x29 | `slot+0x260 == 1` |
| **8 (pressure)** | **0x29** (same destination as the wheel) | `slot+0x260 == 2` |
| **9 (bend)** | **0x23** | |
| 10 (CC7) | 0x56 | |
| 11 (CC10) | 0x55 | |

`slot+0x260` (written by `slot_set_wheel_src`) was meant to choose what drives parameter
0x29: the wheel (1) or pressure (2). **The value 2 is never written** (see "Wheel,
pressure and per-voice morph"): in OS 1.32, pressure does nothing.

### `slot_set_param(slot, no., &value)` (c000f93c)  [sure]

Stores the value at `slot+0x2D4 + no. × 4`, then looks at the parameter's flags (byte
`slot+0x278 + no.`, 6 by default, 0xF for 0x3E, 0x3F, 0x43):
- bit 2: sent to the **slot's engine**. `engine_param_convert` (c001e7dc) gives the
  conversion function, `engine_param_handler` (c001e26c, `switch` on the number) the
  method that applies it;
- bit 4: sent to **each voice of the slot**. Loop over the 20 voices of `0xc04b0040`; a
  voice is taken if it belongs to this slot and its state (`+8`) is 3.
  `voice_param_handler` (c0029678) gives the voice's method;
- bit 8: 2nd send to the engine (with code 8);
- bit 1: deferred processing (queue).

For 0x23 (bend), `voice_param_handler` has **no** case: it is the default method
(c00333d0, a plain `bx lr`). **Bend is never sent voice by voice**, only to the slot's
engine.

## Wheel, pressure and per-voice morph  [sure unless stated]

### Pressure is dead code
`slot+0x260` is only written as 0 (constructor) and by `slot_set_wheel_src` (c000f510),
whose only caller, `slot_wheel_mode_apply` (c00f0270), and the same logic copied in
`fn_c00f0438`, only pass 0 or 1. The "pressure → 0x29" case of `slot_midi_ctrl_in`
therefore never runs. This is consistent with the manual: the Lead 4 has no aftertouch,
and the "Wheel" morph source groups wheel, pedal, CC1 and CC11. **Z needs a new path**;
nothing has to be undone.

`slot_wheel_mode_apply` reads a mode at `+0x630` (0 to 3) and sets parameters 0x29, 0x2B,
0x2C, 0x2D. Mode 3: 0x29 = current wheel value, 0x2B = 100, the wheel drives 0x29. Modes 1
and 2: 0x29 fixed at 127, 0x2B taken from `+0x62C`, 0x2C / 0x2D constant. Mode 0:
everything at 0. Exact meaning unknown (pedal setting?) **[hyp.]**.

### The wheel morph is global to the slot
0x29 only has a case in `engine_param_handler` (→ `engine_param_wheel_morph`, c0023e48),
not in `voice_param_handler`. The method bounds the value to 127, passes it through a
curve (16-bit products), writes `engine+0x878` / `+0x87C`, then notifies the object at
`engine+0x864` (c0052434) if a counter changed. A single value for the whole slot.

### The velocity morph is computed voice by voice
`voice_param_handler` covers 59 parameters (0x00–0x20, 0x26–0x28, 0x2C–0x2F, 0x31,
0x35–0x37, 0x3B, 0x3E–0x44, 0x46, 0x4B–0x4F): **each voice keeps its own copy of the
sound's parameters.** Before applying a value, `slot_set_param` (bit 4) passes it through
the voice's converter, the object at `voice+0x48`:

```
voice_morph_eval (c0033538)  object o = voice+0x48, parameter n
  e = table[n]  (o+0xC → +0xC, 5 words: base, velocity amount, keyboard amount, min, max)
  keyboard = (o[1] + table+4) >> 7          o[1] = (note − 64) << 16  [hyp., by analogy]
  value    = base + (o[2] + 1) × vel_amount >> 7 + f(keyboard × keyboard_amount)
  (*(o+0x10))[n] = bound(value, min, max)       o[2] = velocity  [strong hyp.]
```

It is the same formula as the one in `slot_note_on` for the arpeggiator. The velocity and
the note of each voice are therefore **per-voice inputs** of a per-voice computation.

### Where velocity enters the voice  [sure]
`voice_apply_velocity(voice, velocity)` (c0032098), called by `note_event_handler`
(c00263b4) for each voice of a note, except in mode 3 (legato **[hyp.]**):
- `voice[0xF]` = velocity; `voice[0x10]` = velocity curve (v² term);
- `voice[0x13]` = **`voice_pitch_offset(voice)`** (current pitch, bend included): it is
  the "keyboard" input of the morph; `voice[0x14]` = velocity: the "velocity" input;
- then evaluates the whole morph table of the voice (`voice[0x15]`, same formula as
  `voice_morph_eval`) and pushes the results to the voice's sub-objects (≈ 80 setting
  calls: oscillators, filter, envelopes).

This is **the function to call again** for Y / Z: it recomputes all parameters of a voice
without retriggering the envelopes (triggering is separate: c0032ec0, c00323b0, c0032708
**[hyp.]**). Estimated cost: a few thousand instructions per call, i.e. on the order of
10 µs at 456 MHz **[hyp., to be measured]**.

**Consequence for MPE (Y / Z)**: vary the velocity input `o[2]` of a voice continuously,
from the CC74 or the pressure of its channel, then recompute and apply the parameters of
**that voice only**. All "Velocity" morph destinations of a program are then driven by Y or
Z, note by note, without touching the engine or the SHARC code. To check: where `o[1]` and
`o[2]` are written at Note On, and the cost of a full recomputation on each message (20
voices at most).

### The two stages of the morph  [sure unless stated]

The morph is applied in **two stages**:

1. **Program stage (global to the slot): Wheel and Impulse.** Each program parameter is
   an object with listeners; an adapter (c00f16e4, created in `fn_c00ef064`) forwards each
   new value to `slot_param_in(prog, no., value)` (c00f04a4, 77 cases) then
   `slot_set_param`. The value that reaches the slot already includes the effect of the
   Wheel and Impulse morphs **[strong hyp.: nothing in the slot or the voices reads the
   wheel for the destinations]**. The exact place where the parameter model adds these
   morphs has not been read yet.
2. **Voice stage: Velocity and Keyboard.** The slot's engine keeps a morph descriptor at
   `engine+0x270` (`morph_table_ctor`, c0011ff8: count, keyboard offset, ?, entries,
   outputs, velocity, keyboard). One 0x14-byte entry per parameter:
   **{base, Velocity amount, Keyboard amount, min, max}**.
   - `slot_set_param` → `engine_morph_eval` (c0011f18) stores the received value in
     `base`, then computes the engine's value;
   - on triggering, each voice binds to the engine (`voice_bind_engine`, c002f020:
     `voice+0x54 = engine+0x270`); `voice_apply_velocity` and `voice_morph_eval` compute
     `base + velocity × amount + keyboard × amount`, bounded, for that voice;
   - Velocity amounts come from the program: `prog_morph_amount_in` (c00ef774, program
     method) → `slot_set_vel_morph_amount` (c0010448) writes `entry[i].vel_amount`. A
     table of 3 bytes per morph destination (in BSS, 0xc04ed3fc) gives `i`, or "Z" for the
     arpeggiator's destinations (`slot_set_arp_vel_morph_amount`, c0010450, descriptor
     `slot+0x4b0`).

**Consequence**: only the second stage is per voice. A per-voice Y / Z source separate
from Velocity requires adding, per entry, two amounts (Y, Z) and two per-voice inputs, and
extending the computation. The entry format (0x14 bytes) is read by four functions
(`voice_morph_eval`, `voice_apply_velocity`, `engine_morph_eval`, `slot_note_on`): rather
than widening it, keep **parallel tables** (Y amount, Z amount per entry) in our own
memory, and replace the two voice functions with ours.

### Morph sources and engine inputs (2026-11-19)  [sure unless stated]
- **Source numbers** **[strong hyp.]**: 0 = Wheel, 1 = Velocity, 2 to 8 = Impulse 1 to 7.
  `prog_morph_amount_in` (program vtable 0xc03c0b10, entry 6; copy for the secondary base
  `fn_c00ef7ec`, `this` − 0x53c) receives (parameter, source, amount) and only forwards
  source 1; the morph edit function (c00eb378) calls the same model method with sources
  2 to 8.
- **Engine morph descriptor** (`engine+0x270`, pointed to by `voice[0x15]`): `[0]` number
  of entries, `[3]` 0x14-byte entries {base, Velocity amount, keyboard amount, min, max}
  shared by the slot's voices, `[4]` outputs (shared scratch), `[5]` velocity, `[6]`
  keyboard. Setters: c0011fa8 (Velocity amount), c0011fc0 (keyboard amount), c0011fd8
  (min, max), `engine_morph_eval` (base).
- **Morph table of the voice** (`voice+0x48`, 90 entries, `morph_table_ctor` in
  `voice_ctor`): `voice[0x13]` = keyboard input (pitch), `voice[0x14]` = note velocity,
  `voice[0x15]` = engine descriptor, `voice[0x16]` = voice outputs.
- `voice_apply_velocity` ends with `fn_c0022718(engine)` then a jump to `fn_c002f898`
  (6.7 KB, ≈ 80 sub-object settings), which calls no envelope trigger. That one reads
  `voice+0x40` (velocity curve) for the amp gain `voice+0x334`: a lead for Z → Level.
- **Program parameter model**: program object of slot s at `0xc04eb824[s]` (constructor
  `fn_c00ea050`, base `fn_c00e7660`), model at `+0x1a4`. Reference to a parameter:
  `{model+0x30, no.}`. Reading a morph amount: `fn_c0118c24(model, &ref, source)` →
  `(*(model+0x14))->vt[0](no., source)`. Writing: `model->vt[6](&ref, source, amount, …)`
  (c00eb378, c00e4a70, c0108ecc). `fn_c0116cdc` returns an object whose `+8` is a mask of
  active sources (`1 << source`).
- **The Wheel morph is computed in this model**, not in the slot: the wheel only reaches
  the engine through parameter 0x29 (`engine_param_wheel_morph`, a single global output:
  wheel² × `engine+0x880` → `+0x878`, sent to the SHARC). `prog_morph_amount_in` is only
  called when editing; on load, Velocity amounts go through `c00efbb4` (setting by
  parameter number, caller not found).
- Where the wheel position multiplies the amount, in the model: still not read.

### CC routing and subscribers (2026-11-19)  [sure]
- The parser sorts a CC by its number (`fn_c013cb68`): 64 → type `0xc09140c4`, 66 →
  `c8`, 67 → `cc`, 114 → `d0`, **all others** (CC74 included) → `0xc09140ac`; identical
  pending CCs are merged in the queue.
- Subscribers: `fn_c0121938`, `fn_c0121c44`, `fn_c0122060` (twice), `fn_c0106344`,
  `fn_c013da1c`. Each subscription is a 3-word sub-object; the bus calls entry [1] of
  **its** vtable. Main vtable (0xc03edc28): [1] `midi_bend_in`, then pressure and CC;
  sub-objects: pressure → relay `0xc0120390` (`sub r0, #12 ; b midi_pressure_in`), CC →
  relay `0xc01202a4` (`sub r0, #24 ; b midi_cc_in`). These relays are shared by the three
  classes (0xc03bf3xx, 0xc03ed7xx, 0xc03edcxx). **To intercept CCs or pressure, hook the
  relay, not the vtable entry.**

### CC74  [sure for the receiver]
`midi_cc_in` (c011ffc4) receives CCs with their port and channel. Only performance CCs go
to the targets through `target_controller_in`: CC1 → no. 7, CC4 → 5, CC7 → 10, CC10 → 11,
CC11 → 6, CC70 → 13, CC77 → 14. The others, including **CC74 (Filter Frequency)**, take
another path (panel parameters), not followed: it is not needed. For MPE, it is enough to
intercept the CC74 of member channels **in `midi_cc_in`**, which knows the channel, and
send it to the velocity input of the voice played on that channel. On the master channel,
CC74 keeps its usual meaning.

### Rate
`synth_tick` is registered at boot as a level 4 handler (`fn_c0131e98(4, synth_tick)`, in
the initialisation function c00002a4). Its frequency is not determined; it is known to
already recompute the pitch of the 20 voices on each pass. The cost of Y / Z will be
measured on a prototype (limit to one recomputation per voice and per tick).

## Pitch bend path  [sure]

```
midi_bend_in (c0120398)
  └─ target_controller_in(target, port, channel, 9, value −8192…+8191)
       ctrl_scale_in (c011f004): < 0 → × 1024; ≥ 0 → × 0x1FC1 / 8, bounded to 0x7F0000
       └─ slot_midi_ctrl_in (c000fa58) → slot_set_param(slot, 0x23)
            └─ engine_param_bend (c0022f40) → bend_set_value(engine + 0x28C, v)
                 the slot's "bend" object: target at +0xC
  synth_tick (c0010c34), at each tick:
     for each active slot: smoothing +0x14 → +0xC in 32 steps (step at +0x18)
     then for the 20 voices: voice_pitch_tick (c002eff8) → voice_pitch_mod_update(voice, 0)
          pitch = voice_pitch_offset(voice + 0x590, engine + 0x28C)
                = smoothed bend (+0x14) + slot transposition + voice glide
```

**The bend object** (`slot_engine+0x28C`, created by `bend_ctor`, c001c894): `[0]` → a
0x21C-byte structure, `[4]` = slot transposition (octave × 12 + semitones + fine, methods
c001cbbc / c001cbfc / c001cc3c). The structure contains:

| field | meaning |
|---|---|
| +0x04 | upward range (semitones, 2 by default) |
| +0x08 | downward range (semitones, 2 by default) |
| +0x0C | target bend (semitones in 16.16) |
| +0x10 / +0x18 | last seen target / smoothing step |
| +0x14 | smoothed bend, **read by all voices of the slot** |
| +0x1C… | table of 128 values (cubic curve), recomputed by `bend_set_range`; use unknown |

**Bend Range** = engine parameters: **0x21** (`engine_param_bend_range`, c0023208) sets
both directions (`engine+0x250`), **0x22** (`engine_param_bend_down`, c0022fc0) the
downward direction alone (`engine+0x254`, asymmetric case −12 / −24). Both call
`bend_set_range` (c001c9d8). `slot_set_bend_range` (c000fb4c, entry 15 of the slot's
vtable) sends 0x21 and 0x22 at once.

**Curve** (`bend_set_value`, c001cb30), v = ±0x800000 (0x7F0000 is treated as
+0x800000):

```
bend = 2 × v / 0x800000                          (linear over 2 semitones)
     + (range − 2) × (v / 0x800000)² × sign(v)   (parabolic beyond)
```

**The curve is not linear beyond 2 semitones.** With a range of 48, a half-way bend gives
1 + 46 / 4 = 12.5 semitones instead of 24. MPE assumes a linear mapping (pitch glides of
the controllers), so **the MPE bend needs its own linear scale**. The 14-bit resolution is
kept up to that point.

**For MPE:**
- **Injection point**: `voice_pitch_offset` (c001ccf4, 3 callers: `voice_pitch_mod_update`,
  `voice_pitch_tick` through it, and the pitch setting at Note On `fn_c0032098`). It
  already adds a **voice-specific** term: the glide (`voice+0x590`, set by voice
  parameters 0x26–0x28). A per-note bend is added at the same place: the slot's bend
  replaced (or complemented) by a value of the voice, on a linear scale.
- The recomputation already happens **at every tick, for the 20 voices**, when a slot is
  active. `voice_pitch_mod_update` exits early if the combined value has not changed.
  There is therefore nothing to add for the rate: it is enough for the per-voice value to
  change.
- Smoothing over 32 ticks is done per slot. A per-note bend will want its own (or none,
  since MPE controllers send dense values).
- To be determined: the duration of a tick (frequency of `synth_tick`).

## Open questions, in order of usefulness for MPE

1. ~~From the MIDI graph to the slot~~: done up to the note handler. Remaining: the role
   of the two allocation paths (`alloc_pick` / `alloc_core`). **Panel pitch stick**: its
   path has not been found. It does not visibly use `midi_bend_in`, and
   `midi_routing_setup` only adds the global channel. Simplest: test on the instrument (two
   slots in Keyboard Focus outside Performance, move the stick).
2. ~~Pitch bend~~: done (section "Pitch bend path").
3. ~~Pressure, morph, CC74~~: done (section "Wheel, pressure and per-voice morph").
   Remaining: the role of `slot+0x630` and how the Wheel morph reaches the voices (for Z).
4. Exact voice-stealing policy (bits of the key) and any per-slot limit.
5. The two destinations of `hw_write` (the two SHARCs, 10 voices each [strong hyp.]) and
   the frequency of `synth_tick`.
