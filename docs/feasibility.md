# Step 2 — Feasibility of MPE on the Nord Lead 4 (OS 1.32)

Design note, 2026-11-18 (the stages that followed are in `docs/patches.md`). It relies on
`docs/voices-midi.md` (MIDI paths, voices, allocation, bend, morph),
`docs/update-protocol.md` and `docs/oscab-format.md` (update, checksums),
`docs/hardware.md` (board). Legend: **[sure]** read in the code; **[hyp.]** inferred;
**[to measure]** will be settled on the prototype.

## Verdict

**Feasible, with a patch of the ARM OS alone**, without touching the SHARC code. The
firmware already computes the pitch and the morph parameters **voice by voice** on the ARM
side; a slot can already listen to several channels. The work consists of keeping the MIDI
channel all the way to the voices and replacing, for one voice, values that are currently
shared by the slot.

- **Per-note bend (±48)**: simple, path fully known.
- **Y (CC74)**: medium, path known; CPU cost [to measure].
- **Z (pressure)**: medium to hard depending on the chosen morph source (see "Assigning Y
  and Z in a program").
- **Simultaneous MPE notes**: up to **20** (the Lead 4's polyphony), shared between the
  slots; fewer in unison.

Nothing read so far makes the project impossible. The two unknowns are the CPU cost of
continuously recomputing the voices and the path of the Wheel / Impulse morph to the
voices (for Z).

## What the firmware already does for us  [sure]

| MPE need | Already there | Where |
|---|---|---|
| A slot listens to 15 member channels | routing by (port, channel) bit mask | `target_controller_in`, `midi_routing_setup` |
| One note table per channel | one 128-note zone per (port, channel) in each target | `target_note_on`, `target_find_zone` |
| Pitch of its own for each voice | `voice_pitch_offset` already adds a per-voice term (glide) | c001ccf4 |
| Continuous recomputation of the voices | `synth_tick` recomputes the pitch of the 20 voices at each tick | c0010c34 |
| Parameters of their own for each voice | 59 sound parameters have a per-voice copy | `voice_param_handler` |
| Morph computed per voice | velocity input + keyboard input, per voice | `voice_apply_velocity`, `voice_morph_eval` |
| Parameters that can change during a note | turning a panel knob changes the sound of held notes | (behaviour of the instrument) |
| 14-bit bend | kept up to the engine | `midi_bend_in` → `bend_set_value` |
| Channel of each CC | `midi_cc_in` receives (port, channel, no., value) | c011ffc4 |

## Changes needed

### A. MPE zone: make the member channels heard  — simple
Add channels 2 to 16 (lower zone) to the slot's mask in `midi_routing_setup` (c00dee54).
Activation: **a MIDI menu entry** ("MPE: Off / lower zone / upper zone"), so as not to
depend on any controller. The **MPE Configuration Message** (RPN 6 on the master channel,
intercepted in `midi_cc_in`) may be added on top as a convenience, never as a dependency.
Prototype (stages 2–3): enabled when the global channel is 1 [stopgap].

### B. Keep the channel of a note  — medium, the most delicate point
The channel disappears at `target_note_on`, which only passes {note, velocity}. Two
possible levels:

1. **Level 1: a channel → note table, on the side.** The identity of notes is not
   widened. At the Note On of a member channel, we record "channel c plays note n of slot
   s". The expressions (bend, Y, Z) of channel c go to the voices of (s, n). Limit: two
   fingers on **the same pitch** in the same slot stay merged (rare on the Osmose,
   possible on the LinnStrument: same note on two rows).
2. **Level 2: the "extended" note** `note + 128 × channel` in the whole chain (128-entry
   tables of the destination filter, the arpeggiator and the slot; tree key
   `note | slot << 8` to widen to `slot << 12`; mask `& 0x7F` wherever the note is used
   for pitch). No more collisions, but 7 structures touched: more risk.

Proposal: **level 1 first**, level 2 only if duplicates get in the way when playing. The
arpeggiator and Chord Memory are disabled on a slot in MPE mode. (Stage 9 finally solved
duplicates by renumbering notes.)

### C. Per-note bend (±48)  — simple
- Reception: `midi_bend_in` (c0120398) knows the channel. On a member channel, instead of
  the slot's shared value (controller 9 → parameter 0x23), store the value in the voice of
  that channel's note.
- Application: in `voice_pitch_offset`, add this voice term to the computation, like the
  glide (`voice+0x590`). The bend of the master channel stays the slot's shared bend.
- **Linear scale**: the Lead 4's curve is parabolic beyond 2 semitones
  (`bend_set_value`); the MPE term uses its own linear ±48 scale.
- No 32-tick smoothing for this term: MPE controllers send dense values.

### D. Y (CC74 of the member channels)  — medium
- Reception: intercept the CC74 of member channels in `midi_cc_in`; on the master channel,
  it keeps its meaning (Filter Frequency).
- Application: put the value into the voice's morph input, then call
  `voice_apply_velocity` (c0032098) again, which recomputes and applies all morphed
  parameters of that voice without retriggering the envelopes. Lighter variant: write the
  SHARC address of a few voice parameters directly (the SHARC smooths values,
  `docs/sharc.md`).
- **Cost**: a few thousand instructions per call, ≈ 10 µs [hyp.]. To keep up, at most one
  recomputation per voice and per tick, only if the value changed. To measure: the
  frequency of `synth_tick` and the CPU margin.

### E. Z (pressure of the member channels)  — medium to hard
- Reception: `midi_pressure_in` (c01202ac) knows the channel. The original path
  (pressure → parameter 0x29, Wheel morph) is dead code in OS 1.32: nothing to undo.
- Application: depends on the chosen morph source (next section).

### F. Building and installing the modified OS  — medium, tooling
- Patch of the code in `img1_CODE` (ARM), new routines in a free area or at the end of the
  section (the declared size changes; the keyboard announces its maximum size before
  erasing: "Memory is only %d KB").
- Recompress the section with LZO1X, recompute the two checksums (`~sum of bytes`) and
  the sizes, rebuild `os.cab`. Tool to write (`tools/pack_oscab.py`), validated first by
  reproducing `os.cab` identically or equivalently.
- File verification on the Mac side: read and reproduced (image header sum included).
  **Tool written and checked**: `tools/pack_oscab.py`.

## Assigning Y and Z in a program

The Lead 4 has three families of morph sources, assigned from the panel (hold the source,
turn the destination) and stored in the program: **Velocity**, **Wheel** (wheel, pedal,
CC1, CC11) and **7 Impulse Morphs**.

| Option | Principle | Cost | What is lost |
|---|---|---|---|
| **Velocity ← Y** | the voice's velocity input follows CC74 continuously (start value: the Note On velocity) | low: the per-voice computation exists | the "pure" velocity morph in MPE mode |
| **Wheel ← Z** | what Clavia had planned for aftertouch (dead code) | medium: the Wheel morph is computed once per slot (`engine_param_wheel_morph`), it has to be made per voice | the wheel as a per-voice source (it would stay global if combined) |
| **Impulse 6 / 7 ← Y / Z** | dedicate two Impulse Morphs to Y and Z; Velocity stays intact | medium: make these morphs continuous and per voice; path not read | two of the seven Impulse Morphs |
| **New source** | a real "Y", "Z" source | high: program format, interface, Sound Manager compatibility | — |

Recommendation: **Velocity ← Y for the first prototype** (no unknowns), then choose for Z
between Wheel and Impulse after reading their path to the voices. No option requires a
new screen or breaks existing programs, except the last one. (Outcome: stage 7 applies Y
and Z per parameter, like the wheel; stage 11 makes the destination selectable.)

## Y / Z sources separate from Velocity (study of 2026-11-18)

From `docs/voices-midi.md`, "The two stages of the morph": Wheel and Impulse apply at the
program level (one value for the whole slot); Velocity and Keyboard apply per voice, in
{base, Velocity amount, Keyboard amount, min, max} entries. Hence:

**Per-voice computation — feasible.** Two parallel tables (Y amount, Z amount per morph
entry) and two per-voice inputs (Y value, Z value of the channel). Our versions of
`voice_morph_eval` and of the loop of `voice_apply_velocity` add
`Y × amount_Y + Z × amount_Z`. Velocity keeps its role.

**Where to store the Y / Z assignments — three options:**

| Option | Assignment on the panel | Storage | Cost |
|---|---|---|---|
| **Impulse 6 and 7 reserved for Y and Z** (in MPE mode) | existing gesture (hold Impulse 6, turn) | existing, in the program | read the Impulse assignments in the parameter model and prevent their global effect; path not read yet |
| **New Y and Z sources** | new gesture (e.g. Shift + Velocity / Wheel) | **to be created**: free bytes in the program format, or a separate file | high: format, interface, Sound Manager |
| **Velocity ← Y** (reminder) | existing gesture | existing | low, but continuous velocity is lost |

Recommendation: **Impulse 6 / 7** if their assignments can be read per destination (next
reading: the program's parameter model and its morphs, starting from the adapter c00f16e4
and `fn_c00ef064`). It is also the basis of the conversion function: "copy the Wheel
destinations to Impulse 7 (Z)", which the Lead 4's morph copy-paste can already do
between sources (to be checked in the code).

## Space available on the ARM (AM1705)

- **RAM**: 16 MB of SDRAM (U29). The code takes 4.2 MB from 0xc0000000, static data go up
  to about 0xc04F0000, buffers are used up to about 0xc0930000: several MB are most likely
  left, to be confirmed (heap bounds not read) **[hyp.]**.
- **Where to put our code**: the CODE section cannot grow (the OS data start at
  0xc040c000, 2.7 KB after its end). The **SRAM section**, however, is code run from the
  128 KB shared RAM (53 Nord functions, 0x80000000–0x80001c24). Above it, nothing is
  referenced up to the stacks (top of the system stack at 0x8001e7a0, IRQ/FIQ/SVC stacks
  up to 0x8001f000, exchange area at 0x8001ff00). The SRAM section can therefore be
  enlarged with our code, called from the CODE through long branches. Unknown: the real
  depth of the system stack (it grows down from 0x8001e7a0); with a 16 KB patch at
  0x80001c40, it would have to exceed ~100 KB to reach us **[hyp.]**. Fallback: dead code
  in the CODE (717 functions without a direct reference, 276 KB, to be confirmed one by
  one). (Used from stage 10 on: `tools/find_dead_code.py`.)
- **Code**: the MPE patch and a conversion helper (below) weigh a few tens of KB. The
  limit is the flash area reserved for the OS, which the keyboard announces to the updater
  ("Memory is only %d KB") and which we do not know. The compressed OS is 2.75 MB.
- **CPU**: margin unknown; to measure on the prototype.
- **SHARC side**: nothing to add (`docs/sharc.md`).

### A "convert for MPE" function
Possible in the spirit of the Mutator: for example, copy the destinations of the Wheel
morph to the Velocity morph (for Y), set the bend to ±48, switch off the arpeggiator. The
cost is not space but the interface: finding a free panel gesture (a Shift + button
combination) and the morph editing code. Simpler if Y goes through Velocity (the
assignments already exist); a new source would first require changing the program
format.

## Polyphony and limits

- 20 voices in total, shared by the four slots; one MPE note = one voice (two or more in
  unison). An MPE zone on a slot can therefore play up to 20 notes.
- Voice stealing follows the current rules (allocator sort key, bits not decoded): a
  stolen voice loses its expression with its note, which is the expected behaviour.
- One zone per slot is possible in theory (four zones = four channel ranges), but MPE only
  has two zones (lower and upper): in practice, **one zone per Performance** routed to a
  slot, or two zones to two slots.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Modified OS crashes at boot | medium | Update mode through Shift + Store (checked), reinstall the official 1.32 |
| File refused by the updater | low | Mac check read and reproduced by `pack_oscab.py` |
| CPU saturated by continuous Y/Z | medium | limit to one recomputation per voice and per tick; measure |
| Boot / Update damaged | very low | an update does not rewrite them; last resort: take the board out |
| Unknown SHARC behaviour | low | we only send them what the panel already sends |

## Prototype plan (step 4), from safest to most useful

Each stage is tested on the instrument before the next one.

0. **Rehearsal**: reinstall the official OS 1.32 from Shift + Store.
1. **Toolchain**: rebuild `os.cab` without any substantive change (recompressed,
   checksums recomputed), install it, check that everything works.
2. **Smallest visible patch**: a changed string on the display, or a slot that listens to
   channels 2 to 16. The Osmose's notes play, without expression.
3. **Per-note bend** (C), identity level 1 (B1).
4. **Y → Velocity morph** (D), with a measurement of the cost.
5. **Z** (E) according to the chosen option.
6. Activation through RPN 6; identity level 2 if duplicates get in the way.

## Decision requested (2026-11-18)

Continue to step 4 with this plan, starting with stages 0 and 1 (no change in behaviour),
or stop here. (Decision: continue; see `docs/patches.md`.)
