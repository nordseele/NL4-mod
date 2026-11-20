# OS patches and test procedure

Status on 2026-11-20: stages 1 to 11 tried on the instrument; the current stage (11) works
("Test results" at the end of this file). The code files keep the French word for a stage:
`palierN.c`, `build/palierN_os.app`.

## Building

```sh
docker build -t nl4-arm tools/patch                          # once: GCC ARM + python3-lzo
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/pack_oscab.py ghidra/bin/os.cab build/palier1_os.cab
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier2   # or palier3 … palier11
tools/patch/make_updater.sh build/palier2_os.cab             # -> build/palier2_os.app
```

`build/` is not in git (it contains Clavia's firmware).

**Where our code goes.** Into the 0xad0 free bytes between the end of the official CODE
(0xc040b530) and the first static variable (0xc040c000). The startup table
(0xc0404fb4: copy of 0x40b530 bytes, then zeroing of 0x526008 bytes up to 0xc0931538)
would clear this area: `build.py` moves the start of the zeroing past our code (two words),
without changing its end. For larger patches: the enlarged SRAM section
(`docs/feasibility.md`), or dead code areas (stage 10).

**Safeguards in `build.py`.** Every modified word is compared with its original value
before writing; no global variables in the patch (except where placed explicitly); size
bounded by the hole; listing of the produced code in `build/<stage>/patch.lst`.
`pack_oscab.py` then re-reads the whole file the way the updater and the keyboard do.

**Installing an `os.cab`.** The updater reads `Contents/Resources/os.cab` inside its own
bundle (`CImageTransferFrame::ReadOSResource`), with no checks other than those of
`docs/oscab-format.md`. `make_updater.sh` copies the application from the official dmg,
replaces that file, gives it **its own identifier and name** (`CFBundleIdentifier`
`….<stage>`, `CFBundleName` = stage name, visible in the menu bar), removes the quarantine
flag and signs it ad hoc. Without its own identifier, macOS may bring an already open copy
to the front (or pick another one from Spotlight / the Dock) and reflash the previous OS:
the suspected cause of the ineffective diagnostic of 2026-11-19. The copy launches
without problems (tried on 2026-11-19).

## Stages

| Stage | File | Contents | SHA-256 of `os.cab` |
|---|---|---|---|
| 0 | official dmg | rehearsal: reinstall the official OS 1.32 | `42bbad95…ed16819` |
| 1 | `build/palier1_os.app` | official OS recompressed (LZO1X-999), identical sections | `af3342c3…fee6240` |
| 2 | `build/palier2_os.app` | a slot also listens to channels 2 to 16 | `d821c4ee…5f92cfab` |
| 3 | `build/palier3_os.app` | stage 2 + per-note bend ±48 on channels 2 to 16 | `d1e20a19…63562ce09` |
| 4 | `build/palier4_os.app` | stage 3 + per-note Y (CC74) → velocity input of the voice | `adad2f09…965a8b51` |
| 5 | `build/palier5_os.app` | stage 3 + per-note Y (CC74) → **Wheel morph** of the voice (replaces stage 4) | `0bf5f7a5…21f97fd6` (3rd version, CC relay fixed) |
| 6 | `build/palier6_os.app` | stage 5 + **Z (pressure) → Level** per note, smoothed Y, 16-bit Wheel amounts (replaces stage 5) | `d3675dcd…29aa009b0` |
| 7 | `build/palier7_os.app` | stage 6, but Y only applies the morphed parameters, one by one, like the wheel | `d7aa9d2c…a6e78e85bc9f1a55` |
| 8 | `build/palier8_os.app` | stage 7, playable Z → Level: Poly AT accepted, Z² curve, Z replaces velocity for the level, release preserved | `8e2a4db9…5ede0b8578d18721` |
| 9 | `build/palier9_os.app` | stage 8 + **same pitch on several channels** (renumbered note, pitch corrected per voice) | `f877453a…3ee5d8a4` (2nd version: repeatable Note Off) |
| 10 | `build/palier10_os.app` | stage 9, **MPE set in the MIDI menu** (P, r, y, L), saved; no longer depends on the global channel | `74acf1e8…91ac54d5` (3rd version, **tried: OK**; 2nd `b74493fb…`: boots, `P` only acts after a restart; 1st `5b3caf19…`: does not boot) |
| 11 | `build/palier11_os.app` | stage 10 + selectable Y and Z destinations (wheel / velocity / Filter Freq / level for Z), curves, Z × velocity, channels A–D ignored in MPE; MPE on `E`, Z on `P` | `1b7fb57c…c2274204` (4th version, **tried: OK**: `LE` = level × Z; 3rd `f5db51f3…`: `LE` works, ≈ 6 dB; 1st and 2nd: `LE` has no effect) |
| 11 diag | `build/palier11diag_os.app` | stage 11 + velocity, `voice+0x3c` and level gain of the last note shown in the menu | `d17d8c96…246fc5b3` (with the 4th version; reading taken with `0dffbea9…`) |
| 9 bis | `build/palier9dead_os.app` | diagnostic: stage 9 with its two note wrappers in the dead area of stage 10 | `d45724c1…6ae545b92` |

### Stage 2 in detail (`tools/patch/palier2.c`)

Differences from the official image, checked by re-extraction (4 words + 0xc8 bytes added):

| Address | Before | After | Role |
|---|---|---|---|
| 0xc00e0540 | `bl 0xc00df898` | `bl 0xc040b530` | note zone creation → `mpe_zone_setup` |
| 0xc0404fc0 | 0x40b530 | 0x40b5f8 | startup table: end of the preserved part |
| 0xc0404fc4 | 0x526008 | 0x525f40 | startup table: zeroing (end unchanged) |
| 0xc040aad8 | 4 | 36 | (port, channel) zones per note target |

`mpe_zone_setup` calls the original creation, then, **if the global MIDI channel is 1**,
adds "global channel" zones (which follow the Keyboard Focus) to each slot for channels
2 to 16, on each enabled MIDI port. With another global channel, the behaviour is the
original one.

**Known risks.** (1) Memory: 36 zones instead of 4 per target, ≈ 2.5 KB per zone, i.e.
on the order of 1 MB of extra heap **[estimate]**. (2) Notes might also depend on a channel
mask that this stage does not touch: the test will tell. Bend, pressure and CCs of
channels 2 to 16 are not received yet (stage 3).

### Stage 3 in detail (`tools/patch/palier3.c`, with `palier2.c`)

0x548 bytes (code and tables), 12 modified words, checked by re-extraction:

| Address | Before | After | Role |
|---|---|---|---|
| 0xc011ffac | `target_note_on` | `mpe_target_note_on` | pointer in `midi_noteon_dispatch`: sets the current channel |
| 0xc00119f8 | `b slot_queue_note_on` | `b mpe_queue_note_on` | records `chan_of[slot][note]` |
| 0xc01bde58 | `note_on_build_voices` | `mpe_build_voices` | note handler vt[2] (type 3) |
| 0xc01bde5c | `note_event_handler` | `mpe_note_event` | vt[3] (type 4): binds voices and channel |
| 0xc03bf32c, 0xc03ed740, 0xc03edc2c | `midi_bend_in` | `mpe_bend_in` | the three receive tables (bend, pressure, CC) |
| 0xc001ccf4 | 1st instruction of `voice_pitch_offset` | `b mpe_voice_pitch_offset` | replaced function: original formula + the voice's bend |
| (+ the 4 words of stage 2) | | | |

How it works:
1. `mpe_target_note_on` puts the message's channel in `g_chan` during the original call;
   in the same call stack, `mpe_queue_note_on` stores `channel + 1` for each
   (slot, note) sent to the allocator.
2. After the methods that start voices (types 3 and 4), `bind_voices` reads back from the
   note table the voices of (slot, note) and assigns them that channel.
3. `mpe_bend_in`: if the MPE zone is active and the channel is 2 to 16, the value is kept
   in `g_bend[channel]` and **does not reach the slot**; channel 1 keeps the common bend
   (with the program's range and curve).
4. `mpe_voice_pitch_offset` adds `bend × 384` to each voice (±8192 → ±48 semitones in
   16.16, linear, no smoothing).

**Known limits.** Two fingers on the same pitch in the same slot share the same entry
(level 1 of `docs/feasibility.md`). The arpeggiator and Chord Memory are not handled.
Pressure and CC74 of member channels not handled yet.

### Stage 4 in detail (`tools/patch/palier4.c`, with `palier2.c` and `palier3.c`)

0x648 bytes (code and tables), 16 modified words, checked by re-extraction (SRAM, ARM0 and
image 2 identical to the official ones). The rebuilt stage 3 keeps the same SHA-256: making
`voice_chan` visible from `palier4.c` does not change the binary.

| Address | Before | After | Role |
|---|---|---|---|
| 0xc03bf334, 0xc03ed748, 0xc03edc34 | `midi_cc_in` | `mpe_cc_in` | the three receive tables, CC entry |
| 0xc0000480 | `synth_tick` | `mpe_synth_tick` | init literal pool: level 4 handler |
| (+ the 12 words of stage 3) | | | |

How it works:
1. `mpe_cc_in`: if the MPE zone is active, a CC74 on channels 2 to 16 is kept in
   `g_y[channel]` and **does not reach the panel** (Filter Freq does not move for the whole
   slot). CC74 on channel 1 and all other CCs follow the original path.
2. `mpe_synth_tick` calls `synth_tick`, then, for each played voice (byte `+8` = 3, the
   test of `slot_set_param`) bound to a member channel that has already received a CC74:
   if the velocity input of the voice (`voice[0x14]`) differs from the channel's Y, it calls
   `voice_apply_velocity(voice, Y)` again. This recomputes all Velocity-morph destinations
   of that voice, without retriggering the envelopes (`fn_c002f898`, called at the end,
   calls none of the triggers c0032ec0 / c00323b0 / c0032708).
3. The Note On puts the note's velocity back into `voice[0x14]`; at the next tick, the
   channel's current Y replaces it (the MPE controller sends its initial Y before the Note On).
   At most one recomputation per voice and per tick, and only when Y changes.

Why `synth_tick`: the firmware already drains the note queue there (`fn_c002787c` →
`note_queue_drain`), so `voice_apply_velocity` already runs there on Note On. We stay in
the same context as the original code.

**Known limits.** (1) **Y replaces the note's velocity** for the whole voice: the amp's
velocity curve (`voice+0x40` → `+0x354` / `+0x334`) also follows Y, so with a program
whose amp envelope reacts to velocity, Y also modulates the level. Y / Z sources separate
from Velocity (`docs/feasibility.md`) will lift this limit.
(2) Cost not measured: 20 voices × one recomputation at worst per tick **[≈ 10 µs per
voice, hyp.]**. (3) A program without a Velocity-morph destination does not react to Y
(expected).

### Stage 5 in detail (`tools/patch/palier5.c`, with `palier2.c` and `palier3.c`)

Replaces stage 4: Y no longer takes the place of velocity, it acts as **a Wheel morph of
its own for each note**. Factory programs with a meaningful Wheel morph therefore react to
Y without any setting. 0xa00 bytes of the 0xad0 of the hole (0xd0 left).
14 modified words, checked by re-extraction (SRAM, ARM0 and image 2 identical).

**2nd version (2026-11-19).** The 1st wrapped `prog_morph_amount_in` to capture the Wheel
amounts: on the instrument, Y had no effect. That method is only called when a morph is
**edited**; on load, Velocity amounts go through another path (`c00efbb4`), and Wheel
amounts stay in the program's parameter model, which computes the Wheel morph itself. The
2nd version **queries the model**.

| Address | Before | After | Role |
|---|---|---|---|
| 0xc01bde58, 0xc01bde5c | `note_on_build_voices`, `note_event_handler` | `mpe5_…` | those of stage 3, plus a recomputation request |
| 0xc01202a8 | `b midi_cc_in` | `b mpe_cc_in` | CC sub-object relay (see below) |
| 0xc0000480 | `synth_tick` | `mpe_synth_tick` | as in stage 4, different contents |
| (+ the 10 other words of stage 3) | | | |

How it works:
1. **Wheel amounts.** Model of slot s: `*(0xc04eb824[s] + 0x1a4)` (program object of the
   slot, field set by its constructor `fn_c00e7660`). For each of the 78 destinations
   (table 0xc04ed3fc, 3 bytes per destination, `[1]` = morph entry):
   `fn_c0118c24(model, {model+0x30, no.}, 0)` returns the Wheel amount, stored in
   `wq[s][entry]` (bounded to ±127). Re-read at each recomputation (Note On, every 32
   ticks), at most one slot per tick, once. Numbering **[strong hyp.]**: 0 = Wheel,
   1 = Velocity, 2 to 8 = the 7 Impulse sources (manual: 9 sources; the edit function
   c00eb378 sends 2 to 8).
2. **CC74 of member channels**: kept per channel, does not reach the panel (stage 4).
3. **Application, in `synth_tick`**: for a voice played on a member channel, when its Y
   changes, after a Note On, or every 32 ticks: `base += (Y + 1) × Wheel amount / 128` on
   the slot's morph entries, `voice_apply_velocity(voice, note velocity)`, then the base is
   restored. The entries are shared by the slot's voices, but nothing runs between the
   addition and the removal (same context as stage 4).
4. The recomputation every 32 ticks catches up with a panel change: `slot_set_param`
   recomputes the voices parameter by parameter, without our term.

**Known limits.** (1) The physical wheel still acts on all notes; Y adds to it. (2) If Y
still does nothing: either source 0 is not Wheel, or the model is not the slot's; also try
editing a Wheel morph. (3) Amounts bounded to ±127 (full scale of a parameter, like
Velocity). (4) Arpeggiator destinations ignored. (5) Cost: as stage 4, plus one
recomputation of each MPE voice every 32 ticks.

**3rd version (2026-11-19): the real cause.** CCs do not reach `midi_cc_in` through the
vtable entry replaced in stages 4 and 5. Each MIDI subscriber is an object with several
sub-objects (one per message type: bend, pressure, "other CCs"…), and the bus calls entry
[1] of the **sub-object's** vtable. For bend, it is the main sub-object, hence the success
of stage 3. For CCs, it is a relay shared by the three classes,
`0xc01202a4 : sub r0, r0, #24 ; b midi_cc_in`, which jumps directly. **The CC74 of member
channels therefore never reached our code, neither in stage 4 nor in stage 5** (the effect
heard in stage 4 most likely came from the playing velocity). Fix: the relay's branch
(0xc01202a8) targets `mpe_cc_in`. Pressure has the same relay (`0xc0120390 → b
midi_pressure_in`): to be hooked the same way for Z. The diagnostic keeps the same fix
(SHA-256 `e25ec6a2…5e08f877`).

### Stage 5, diagnostic version (`build/palier5diag_os.app`)

The 2nd version of stage 5 has no effect either (test of 2026-11-19). To find where the
path stops without any debug output, `palier5diag.c` (= `palier5.c` with `DIAG`)
**transposes all notes of a slot** according to what reading the model found for that
slot. Normal pitch until the read (triggered by the 1st MPE note that receives a Y), then a
**jump**:

| Jump | Meaning |
|---|---|
| none | read never done: MPE voice not recognised, or the voice's slot ≥ 4 |
| +24 (two octaves) | no model for this slot (`0xc04eb824[slot] + 0x1a4` is null) |
| +12 (octave) | model read, no amount for Wheel (source 0) or Velocity (source 1) |
| +7 (fifth) | Velocity amounts found, but not Wheel: source 0 is not Wheel |
| +5 (fourth) | Wheel amounts found: if Y still does nothing, it is the application |

Test: a program with a Wheel morph **and** a Velocity morph, channels A–D on Off, global
channel = 1; hold a note on the Nord keyboard, touch a note on the LinnStrument while
moving Y, listen whether the held note jumps.

1st build (2026-11-19): +5 permanently from power-on, hence **inaudible without a
reference** (all notes shifted equally); the "no transposition" test could not conclude.
SHA-256 of the 2nd build: `7d7ae111…74ced0cc`.

### Stage 6 in detail (`tools/patch/palier6.c`, with `palier2.c` and `palier3.c`)

Replaces `palier5.c` (same structure) and adds:

- **Z → Level.** Pressure arrives through a sub-object relay, like CCs:
  `0xc0120390 : sub r0, #12 ; b midi_pressure_in`. The branch (`0xc0120394`) is replaced
  by `b mpe_pressure_in`. The pressure message carries the note at `+8`, or −1 for a
  Channel Pressure (`c013c1c8`). Only the latter is taken, and only on channels 2 to 16;
  Poly AT stays with the firmware. The voice's amp gain is computed in `voice_push_params`
  (`voice+0x334`, 8.23, 0x800000 = 1, from the velocity curve `voice+0x40`). It is sent to
  the SHARC by `amp_gain_write(voice+0x35c, gain)` (c0061a08: SHARC `n & 1`, DM
  `0x9245c + (n >> 1) × 0x40`). In `synth_tick`, we send `gain × Z` again. It is resent
  when Z moves, after each recomputation of the voice by Y (which sent the original gain
  again), at the start of a note and every 32 ticks. A channel that never received
  pressure keeps the original gain.
- **16-bit Wheel amounts.** Stage 5 bounded them to ±127. The firmware passes amounts to
  the engine as they are (`prog_morph_amount_in`: `amount << 16` → `entry.amount`,
  c0011fa8), so a larger amount was clipped and Y at 127 did not reach the effect of the
  wheel fully up (test of 2026-11-19). **[hyp.: to be confirmed by testing]** The min / max
  bounds of the entries are fixed (parameter range, `c001de64…`): they play no part.
- **Smoothing.** Y and Z of each voice move 1/8 of the way towards their target at each
  tick, in steps of 1/256. A voice that starts takes its target immediately. With stage 5,
  the 128 steps of CC74 were audible on a large amount (test of 2026-11-19).
  **[Real duration unknown: it depends on the period of `synth_tick`, not measured.]**
- **Variables at the start of the heap.** Code and variables no longer fitted in the free
  area. `heap_bss` in `build.py` places the zeroed variables at `0xc0931538` (end of the
  startup zeroing = start of the `_sbrk` heap, c014af98, limit 0xc1000000). It moves the
  start of the heap (word `0xc014afd0`) and the size of the zeroing by the same amount
  (0x5b0 bytes).

**Known limits.**
- **Releasing the pressure before the Note Off cuts the note.** Z only follows the voice
  while the note is played; if the controller sends Z = 0 before the Note Off, the release
  is silent.
- **Cost.** While Y glides, the voice is recomputed at every tick (about 90 ticks for a
  jump from 0 to 127).
- **Stolen voice.** A voice stolen without going through another state glides from the
  value of the previous note (`shortcut:` in the code).

### Stage 7 in detail (`tools/patch/palier7.c` = `palier6.c` with `PER_PARAM`)

In stage 6, each step of Y re-ran `voice_apply_velocity`, which sends all the voice's
settings (≈ 80) to the SHARC again. A finger on the pad is never still, and smoothing
added a recomputation at every tick: unbearable artefacts (test of 2026-11-19). The wheel,
on the other hand, goes through `slot_set_param` → `c000f6ec`, which only processes the
changed parameter. For each voice of the slot, that path calls:
- `voice_morph_eval(voice+0x48, n)` (c0033538, chosen by c0029bb0), which gives the morphed
  value of parameter n for that voice;
- `voice_param_handler(&method, voice, n)` (c0029678, `switch` on n), which gives
  `{object, function}`, then `function(object, value)`.

Stage 7 does the same, voice by voice, **only for parameters that have a Wheel amount**:
base + Y × amount during the evaluation, then application. Morph entry i is parameter
no. i of the slot (`voice_morph_eval` indexes the table by number). A parameter without a
per-voice method falls on the default method (`bx lr`): no effect, as with the wheel.

### Stage 8 in detail (`tools/patch/palier8.c` = `palier6.c` with `PER_PARAM` and `PALIER8`)

Stage 7 test: Z → Level disappointing, and it is hard to hear whether it acts. Stage 8
fixes four likely causes:
- **Poly AT accepted as Z** on member channels: a member channel carries only one note.
  According to Roger Linn's support, the LinnStrument sends pressure as Poly AT by
  default; stage 7 ignored it.
- **Z² curve**: perceived loudness is logarithmic. With a linear curve, almost the whole
  travel sounded loud; Z² gives Z = 64 → 25 % (−12 dB), Z = 32 → 6 % (−24 dB).
- **Z replaces velocity for the level**: gain = Z², 1 at Z = 127, instead of
  `velocity gain × Z`. With the product, a softly struck note could not get louder. A
  channel that never received pressure keeps the original level.
- **Release preserved**: according to a forum thread (unofficial), the LinnStrument sends
  Z = 0 just before each Note On and Note Off. A Z = 0 is only applied to the channel after
  `ZWAIT` = 3 ticks: if the Note Off arrives first, the voice goes into release with its
  level. A note that starts takes the received Z at once, without waiting.

Planned next as MIDI menu options: selectable curves for Y and Z, and "replace" or
"multiply" velocity.

### Stage 9 in detail (`tools/patch/palier9.c`, `palier3alias.c`, `alias.h`)

The firmware identifies a note by (slot, number): the channel is gone as soon as the slot
is called (`docs/voices-midi.md`, "Identity of a note"). Two fingers on the same pitch made
a single note, and `bind_voices` gave both voices the channel of the most recent one (test:
"the most recent steals the other's bend"). Widening the identity of notes would touch every
128-key table, the arpeggiator, the note tree, the queue and the allocator. Stage 9
renumbers instead:

- **Note On** (`mpe9_target_note_on`, pointer `0xc011ffac`): on a member channel, if the
  pitch is already held on another member channel, the note enters under the nearest free
  number (n + 1, n − 1, n + 2… up to ± 12; `alias_on`). A repeated Note On on the same
  channel keeps its number.
- **Note Off** (`mpe9_target_note_off`, pointer `0xc011feb0` to `target_note_off`,
  c0111424): switches off the number actually played and frees it (`alias_off`).
- **Pitch**: the offset (note − played number) goes through `g_off` to `mpe_queue_note_on`,
  which stores it per (slot, note); `bind_voices` gives it to each voice, and
  `mpe_voice_pitch_offset` adds it in semitones. The keyboard input of the morph
  (voice[0x13] = pitch) follows; the display and the arpeggiator's key tracking do not.
- **Once per target.** The dispatcher (`c011fdcc` for Note Off, via `c011f62c`) calls
  `target_note_on` / `target_note_off` for each target. The 1st version freed the alias on
  the first Note Off: the following targets switched off the original number, and the
  renumbered notes stayed stuck (test of 2026-11-19). The alias now stays known until the
  next Note On of (channel, note), and it is reused only if it is free.
- `test_alias.c` checks the assignment on the Mac, repeated calls included:
  `cc -o /tmp/t tools/patch/test_alias.c && /tmp/t`.

**Limits.**
- Only member channels are tracked: a note on channel 1 or from the local keyboard on the
  same pitch is still merged.
- If the 25 numbers around the note are taken, the note is merged as before.
- Whatever depends on the note number rather than on the voice's pitch will be off by one
  or two semitones for the renumbered note **[hyp.: nothing audible]**.

### Stage 10 in detail (`tools/patch/palier10.c`, which includes stages 2, 3 and 9)

MPE is no longer enabled by "global channel = 1" but by four entries added **at the end of
the MIDI menu** (after 8; wheel to get there, Shift + wheel to change):

| Letter | Option (bits of setting 0x21) | Values (default first) | Effect |
|---|---|---|---|
| `P` | MPE (bit 0) | `Of`, `On` | lower zone: channels 2 to 16 as members, on the slot in Keyboard Focus |
| `r` | bend range (bits 1–2) | `48`, `24`, `12`, ` 2` | bend of member channels, in semitones |
| `y` | Y (bit 3) | `On`, `Of` | Y (CC74) → per-note Wheel morph; `Of`: CC74 of members ignored |
| `L` | Z (bit 4) | `On`, `Of` | Z (pressure) → per-note Level; `Of`: pressure of members ignored |

**1st version (2026-11-20): the keyboard no longer booted.** It added 4 settings
(no. 0x22 to 0x25) to the table of global settings. Cause, found by reading: the listener
of these settings (object of `fn_c00ee098`, base constructor `fn_c00e3f70`) stores in
**its own object** arrays of 34 cells indexed by number (one byte per number at `+0x104`,
pairs of words at `+0x58`, and 0x22 hard-coded in `fn_c00e3f70` and `fn_c00e2ab0`). Our
numbers wrote beyond them, over the timer object at `+0xe0` and its callback pointer at
`+0xec`. **Lesson: the number of global settings is fixed at 34.**

**2nd version.** The four options are bit fields of setting **0x21**: it is saved on 31
bits, but its maximum is 0 in OS 1.32 (always 0, no reader or writer by number in the
CODE). `build.py` raises this maximum to 0x1f (`0xc03c02a4`). Neither the table nor the
saved record change shape; the official OS reads a value > 0 as out of range and brings it
back to 0 (the options then return to their defaults).

How it works:
- **Entries**: `mpe10_menus_done` replaces the last call of `menus_build` (`0xc00fc0e8`).
  Each entry is built by the PB Mode constructor (`fn_c01001f8`, object enlarged to 0x64
  bytes, option number at `+0x60`), then receives our copies of the PB Mode vtables: main
  (wheel `[5]`, formatting `[12]`, display `[13]`) and sub-object `+0xc` (wheel relay). The
  wheel only changes its own field: `global_step(app, 0x21, …, delta << shift)`. `build.py`
  checks that the copied words and the descriptor of 0x21 are those of the original image.
- **Taking effect**: after `global_step`, the wheel sets `app[0x1fe]` and re-runs
  `app_routing_update`, as the firmware does for the global channel; `mpe_zone_setup`
  re-reads the options (the new value is passed to it through `g_force`). At boot, the
  zone creation reads the loaded setting. `mpe10_on_global` (pointer `0xc03bf200`) does
  the same if the application is notified of no. 0x21. The global channel is no longer
  added a 2nd time as a member.
- **Space**: the hole after the CODE is no longer enough (0xaa8 bytes of 0xad0). The rest
  (0x2d0 bytes) goes into **dead code** of the firmware, `0xc002d1f8`–`0xc002daa4` (`DEAD`
  in `build.py`), found by `tools/find_dead_code.py`: no word of any image points into it,
  no branch, PC-relative load or `adr` from elsewhere reaches it, and it follows the end of
  a function. `build.py` distributes the functions itself (the hole first, then the dead
  areas), because `ld --enable-non-contiguous-regions` crashes; variables stay in the hole
  or the heap.
- Checks: the rebuilt stage 9 is identical byte for byte; the stage 10 image differs from
  the original only by the expected words, the dead area used and the added code.

**To try**:
1. After the update: the keyboard reboots; MIDI menu, wheel past 8 →
   `P.Of`, `r.48`, `y.On`, `L.On`.
2. `P` to `On`: MPE works as in stage 9, **whatever the global channel** (keep A–D on Off).
3. `r` to `12` then ` 2`: bend range of member channels.
4. `y` then `L` to `Of`: Y then Z have no effect.
5. Switch off, switch on: the four settings are kept, and MPE works from power-on.

**Test of the 2nd version (2026-11-20)**: the keyboard reboots, the entries are shown.
`P.On` changed nothing until the next restart; afterwards, MIDI notes on member channels
play. The setting is therefore saved, but the application is not notified of a change of
no. 0x21 (it probably only receives the numbers it is subscribed to **[hyp.]**):
`mpe10_on_global` was not called. **3rd version**: the wheel itself re-runs the zone
creation (above). With `P.Of`, it is normal that channels 2 to 16 do not play (only the
global channel is listened to).

**Test of the 3rd version (2026-11-20): same fault** (`P.On` only acts after a restart).
Re-reading the re-run (zones emptied then recreated by `fn_c00df898`, targets re-enabled
by the Keyboard Focus in `midi_routing_setup`, `target_note_on` without a mask) shows no
difference between boot and a re-run. Hence a **diagnostic** version,
`build/palier10diag_os.app` (`palier10diag.c`, `4f93e105…ba80d8e77`): in the MIDI menu,
`r` shows the **number of zones** of slot A's target and `y` shows
**zone creations (mod 16) | g_mpe_on**, in hexadecimal. Expected: `r.02` to `r.04` with
`P.Of`, about `r.20` with `P.On` (2 original zones + 30 of ours); the 1st digit of `y`
increases at each re-run, the 2nd is 1 with `P.On`.

**Diagnostic reading (2026-11-20)**: after a restart with `P.Of`: `r.02`, `y.60`; `P`
switched to `On` without restarting: `r.20`, `y.71`. **The re-run works**: the 30 zones
of the member channels are created at once and MPE is active. The silence most likely came
from the test program: it has a morph on the wheel and is only audible with the wheel up;
per-note Y adds to that morph, and the panel wheel still acts on the slot **[hyp., to be
confirmed with a sound audible with the wheel down]**.

**Final test (2026-11-20): OK.** With the normal version, `y` and `L` on `On`, the program
plays from the LinnStrument as in stage 9, and `P.On` acts without a restart. The fault
came from the test program and from `y` left on `Of`.

**If a version does not boot**: try `build/palier9dead_os.app`. It is stage 9 with its two
note wrappers (Note On / Note Off of member channels) moved into the same dead area. If it
boots and plays like stage 9, the dead area is not the cause; otherwise, it is.

### Stage 11 in detail (`tools/patch/palier11.c`, which includes `palier10.c`)

The MPE options still missing, all in the bits of setting 0x21 (maximum raised to
`0x1fff` by `build.py`). MIDI menu, after 8 (wheel to go to the entry, Shift + wheel to
change the value). The display has 3 characters: entry letter, dot, value on 2 characters.
The default comes first.

| Display | Setting | Values | Bits of 0x21 |
|---|---|---|---|
| `E.Of` | **MPE** | `Of` off · `On` on | 0 |
| `r.48` | **bend range** of member channels | `48` · `24` · `12` · ` 2` semitones | 1–2 |
| `y.nO` | **Y (CC74) goes to…** | `nO` Wheel morph · `vE` Velocity morph · `Fr` Filter Freq directly · `Of` nothing | 3–4 |
| `C.Li` | **Y curve** | `Li` linear · `CA` square (slow at the bottom) · `dO` soft (fast at the bottom) | 8–9 |
| `P.LE` | **Z (pressure) goes to…** | `LE` level (from 0 to the normal level) · `nO` wheel · `vE` velocity · `Fr` Filter Freq · `Of` nothing · `vL` level velocity (Z replaces velocity, ≈ 6 dB) | 5–7 |
| `H.CA` | **Z curve** | `CA` square · `Li` linear · `dO` soft | 10–11 |
| `v.Of` | **Z × velocity** | `Of` Z alone · `On` Z multiplied by the note's velocity | 12 |

Letters: `E` for MPE and `P` (pressure) for Z, because a Z would show as a 2, already
used by Local. `nO` = wheel (French "moLette"; the n stands in for an M). `vE` reads "UE"
on the display. A saved value out of range (e.g. 5 to 7 for `P`) reads as the default.

**Compatibility with stage 10**: bits 0 to 2 (MPE, bend) do not move. Bits 3 and 4 change
meaning: a stage 10 `y.Of` becomes `y.vE`, an `L.Of` becomes `y.Fr`.

How it works:
- **All destinations per parameter** (stage 7 path): for each morph entry of the voice, an
  offset is added to the base during `voice_morph_eval`, then applied by
  `voice_param_handler`. Y and Z are applied **together**: otherwise the 2nd evaluation
  would erase the 1st when both target the same parameter.
  - **nO (Wheel)**: offset = value × the program's Wheel amount (as in stage 7).
  - **vE (Velocity)**: `voice_morph_eval` adds `amount × (velocity + 1) / 128`
    (`o[2]` = `voice[0x14]`, checked in the pseudo-C); the offset replaces
    (velocity + 1) / 128 by the value. Only parameters that have a Velocity amount move.
  - **Fr (Filter Freq direct)**: parameter no. **0x15**. Offset = value × (max − min) of
    the entry: at 127, the filter is fully open from the knob's setting. **Tried
    (Z → Fr, 2026-11-20): acts on the cutoff as expected.**
  - **Level**: the per-voice level method (parameter no. 0, `c0036dbc`) **ignores the
    value passed**. It reads a slot setting S (`[voice+0x414] + 8`,
    `voice+0x414 = engine+0x6ac`, set by `voice_bind_engine`) and the **velocity at
    `voice+0x42c`**, copied from `voice+0x3c` by `voice_push_params`. Index
    = S × velocity / 127 − S / 2 (S / 2 capped at 32), table ≈ 0.19 dB per step
    (`0xc01c8b54` / `0xc01c8954`), gain capped at 0x800000; stored at `voice+0x3b0`
    (= `[voice+0x3dc] + 0x14`, `voice+0x3dc = voice+0x39c`), sent by
    **`c005ee84(voice[0x3d8], gain)`** → SHARC DM `0x9248a + (n >> 1) × 0x40`
    (`c005eec8`, called by `voice_push_params`, writes the same address).
  - **`LE`, level × Z** (4th version): `gain of voice+0x3b0 × curve(Z)` is sent again by
    `c005ee84`, `voice+0x3b0` left intact. Z = 0 → silence, Z = 127 → normal level
    (velocity included). Resent when Z moves, at the start of the note and every 32 ticks:
    if the firmware recomputes the level (knob turned), the normal level may come back for
    up to 32 ticks.
  - **`vL`, Z replaces velocity** (3rd version, kept): Z on 0…127 into `voice+0x42c`, then
    the method. Test of 2026-11-20: works, but ≈ 6 dB of range at most (the formula
    above). `vL` comes after `Of` so that `Of` keeps its saved value.
  - Versions without effect: the gain of stages 6 to 10 (`amp_gain_write`, `voice+0x334`,
    DM `0x9245c`: another address, whose role is unknown), then an offset on the base of
    parameter no. 0 (2nd version), since the method ignores the value.
- **Parameter numbers**: name table `0xc01c9be8…`, 16-byte entries
  `{no., group, name, unit}` (0 = Output Level, 0x15 = Filter Freq, 0x16 = Resonance).
  Layout confirmed by what was already known: 0x21 / 0x22 = Pitch Bend Range,
  0x23 = "Pitch Bend xxx" (the bend value), 0x24 = Voice Mode, 0x25 = Legato, with no
  per-voice method from 0x21 to 0x25. A 1st reading as `{group, name, unit, no.}` gave
  0x16 (Resonance) for Filter Freq: fixed before the test.
- **1st version: Level = amp gain of stages 6 to 10** (`amp_gain_write`), tried on
  2026-11-20: **no effect on the level** (and already "disappointing" in stage 8). Replaced
  by Output Level. Cause not investigated **[hyp.: gain rewritten by the firmware, or value
  ignored by the SHARC]**.
- **v.On**: the value of Z is multiplied by (velocity + 1) / 128 before the offset, for all
  destinations.
- **Curves** (on the smoothed value, 0…1): linear; square (x²); soft = 1 − (1 − x)².
- **Channels A–D**: `app_routing_update` (c00e04cc) copies the channel settings
  (`app+0x1d8…0x1e4`) into the effective channels `app+0x1ec…0x1f8` (16 = Off, a channel
  equal to the global one becomes Off), then calls the zone creation (our
  `mpe_zone_setup`) and sets the controller masks from those same fields. In MPE mode, an
  A–D channel lying on a member channel (MIDI 2 to 16) is set to Off **in the effective
  fields only**, before the zone creation: no zone and no mask for it. The settings and the
  menu do not change; going back to `E.Of` (or changing A–D, which also re-runs
  `app_routing_update` through `fn_c00e0960`) restores them. An A–D channel on MIDI 1
  stays. Channels A–D are stored outside the global table: per-slot model `app[0x53 + i]`,
  setting no. 1 (`fn_c00e2740` / `fn_c00e2894`, called by the menu entry `fn_c0101da8`).
- Space: 0xab8 bytes in the hole (of 0xad0) + 0x764 in the 1st dead area (of 0x8ac). The
  hole is full: the next addition will go into the dead areas.
- Checks: stages 9 and 10 rebuilt identical byte for byte; the stage 11 image differs from
  the original only by the 20 words of stage 10 (including the maximum of 0x21), the dead
  area and the added code; `.cab` re-extracted, the 5 other sections identical to the
  official ones; no call to libgcc in the produced code.

**Level diagnostic** (`build/palier11diag_os.app`, `palier11diag.c`, `DIAG11`): stage 11
(2nd version) showing in the menu, for the **last note started on a member channel**, in
hexadecimal (`b`, `d` in lower case):

| Entry | Shows |
|---|---|
| `E` | MPE, as usual (leave on `On`) |
| `r` | note velocity (`voice[0x14]`, `7F` = 127) |
| `y` `C` `P` `H` | the 4 bytes of `voice+0x3c`, most to least significant: `y.00 C.40 P.00 H.00` = `0x00400000` |
| `v` | `voice+0x3b0 >> 16`: the gain computed by `c0036dbc` (`80` = gain 1) |

**Reading of 2026-11-20** (LinnStrument): velocity `07` → `voice+0x3c = 0x00000007`,
`v.11`; velocity `3A` → `0x0000003A`, `v.1d`. **`voice+0x3c` is the velocity (0…127) and
the gain depends on it**: hence the 3rd version of LE.

Entries `r` to `v` keep their wheel: do not turn them during the reading. Intended
reading: play a **soft** note on the LinnStrument, release it, note `r y C P H v`; then a
**loud** note; then a loud one with the panel's Output Level halfway. Interpretation:
- `voice+0x3c` varies with velocity → it is the velocity factor of the level; Z will
  replace (or multiply) it in `voice+0x42c`, then `c0036dbc` will be called again;
- it does not vary → look elsewhere (it then depends on the program, not the note);
- `v` gives the scale of the output gain (8.23 if `80` = full).

**Test of the 3rd version (2026-11-20): LE works, but the range is small** (small
variation around the level, impossible to go down to silence). Cause, read in `c0036dbc`:
index = S × (velocity / 127) − S / 2, where S = `[voice+0x414] + 8` (slot setting, capped
at 65; beyond that, S / 2 is replaced by 32). Index ≥ 0 → table `0xc01c8b54`, index < 0 →
table `0xc01c8954`, **≈ 0.19 dB per step**; gain capped at 0x800000 (0 dB), stored at
`voice+0x3b0`. So at best ≈ −6 dB to 0 dB through velocity: replacing velocity with Z
cannot go further. Hence, as the user proposed, two modes (4th version): `LE` (level × Z)
and `vL` (Z replaces velocity).

**Z on the LinnStrument**: our code reads Z from **Channel Pressure or Poly AT, on 7
bits**. The LinnStrument can send it on 14 bits (setting used by the user during the tests
of 2026-11-20). If that mode goes through a CC (CC11 + low byte), our code sees no
pressure: tests of Z need Z as Channel Pressure or Poly AT **[to check: what the 14-bit
mode sends]**. 14 bits would bring nothing to the level (`voice+0x42c` is an integer from
0 to 127); for the other destinations, smoothing already fills the steps.

**Limits.**
- Changing the destination during a note leaves the parameters of the old destination at
  their last value until the next note.
- Y and Z both on `vE`: the two offsets add up (each replaces velocity).
- `P.LE`: a note starts at the level of the received pressure; without pressure at the
  start, the attack is silent until Z rises (normal in MPE).

**To try** (a program that sounds with the wheel down, A–D on Off unless stated):
1. After the update, MIDI menu after 8: `E`, `r`, `y`, `C`, `P`, `H`, `v` (MPE stays on
   `On` if it was).
2. `P.LE`: pressure sets the level of each note, from silence to the normal level (also
   try `H.Li`, `H.dO`); `P.vL`: small variation, like the 3rd version.
3. `y.Fr`: Y opens the filter, note by note.
4. `y.vE` on a program with a Velocity morph: Y drives it.
5. `P.nO`, `P.vE`; Y and Z together on `nO`.
6. `C` then `H`: `CA` more gradual at the bottom, `dO` livelier.
7. `P.LE` and `v.On`: a softly struck note stays soft even at full pressure.
8. Slot B on channel 3, `E.On`: notes on channel 3 only go to the played slot; `E.Of`:
   slot B plays channel 3 again.

## Test script (`tools/mpe_test.py`)

Sends precise scenarios to the keyboard over USB (mido + python-rtmidi), like an MPE
controller in the lower zone: initial state (bend, CC74, pressure) before each Note On, one
member channel per note, "all off" at the end even after Ctrl-C.

```sh
python3 tools/mpe_test.py --list            # ports and scenarios
python3 tools/mpe_test.py same-note         # same note on two channels
python3 tools/mpe_test.py y --seconds 10    # Y as phase-shifted sine waves on 3 notes
python3 tools/mpe_test.py all
```

Scenarios: `same-note`, `bend`, `y`, `chord8` (load), `pressure` (for the Z stage),
`master` (channel 1). Expected for `same-note` before stage 9: the two notes **share** the
same entry (a note was still identified by (slot, number)), so releasing channel 2 probably
also cut the note on channel 3.

## Test procedure on the instrument

First of all: the official file remains available (dmg in `vendor/`). If an OS does not
boot: **power on while holding Shift + Store**, then install the official OS.

1. **Stage 0.** Power on while holding Shift + Store ("RDY"), run the official updater,
   install. Check that everything works and that the programs are there.
2. **Stage 1.** Same with `build/palier1_os.app`. Expected: "Update completed
   successfully", instrument unchanged.
3. **Stage 2.** Same with `build/palier2_os.app`. Then, MIDI menu: global channel = 1.
   Play from the Osmose or the LinnStrument in MPE mode (lower zone, 15 channels).
   Expected: all notes play on the slot that has the Keyboard Focus, whatever their
   channel; no per-note expression yet. Also check the local keyboard, the other slots,
   and a cold boot.
4. **Stage 3.** Same procedure with `build/palier3_os.app`, global channel = 1.
   Controller in MPE lower zone, **bend range of member channels set to ±48**. Expected:
   each note follows its own glide; the bend of channel 1 (or the stick) moves all notes
   according to the program's range. Also try: two notes gliding in opposite directions,
   a note released during a glide (the release still follows the channel), a program
   change.
5. **Stage 4.** Same procedure with `build/palier4_os.app`, global channel = 1. Choose
   (or set up) a program with a **clearly audible Velocity morph** (e.g. Filter Freq or an
   oscillator level, Velocity morph) and the amp envelope **without** velocity if
   possible. Expected: sliding the finger in Y (LinnStrument) or the matching gesture on the
   Osmose changes the timbre **of that note only**; the other held notes keep theirs. Also
   check: per-note bend (stage 3) still works; CC74 on channel 1 keeps its usual effect;
   no stutter or lost notes with an 8-note chord and Y in continuous motion (CPU load).
6. **Stage 5.** Same procedure with `build/palier5_os.app`, global channel = 1. Take a
   factory program whose wheel has a clear effect, **wheel at rest**. Expected:
   `python3 tools/mpe_test.py y` varies that effect on each note separately; the striking
   velocity keeps its usual effect; the wheel acts on all notes. Then `bend`, `chord8` and
   `same-note`.
7. **Stage 6.** `build/palier6_os.app`, same settings (A–D on Off, global channel = 1).
   - Y fully up must give the same effect as the wheel fully up.
   - Y must glide without audible steps.
   - Pressure must set the level of each note; a controller that sends no pressure keeps
     the normal level.
   - Also check an 8-note chord with Y and Z in motion (load).
8. **Stage 7.** Same tests as stage 6; expected: no more artefacts when the finger moves
   on the pad.
9. **Stage 8.** Pressure must set the level of each note, from silence to full level,
   whatever the striking velocity. The release must stay audible when the finger is
   lifted. If nothing changes, check on the controller what it sends for Z (Channel
   Pressure or Poly AT) and its minimum value.
10. **Stage 9.** Hold the same pitch on two channels, for example two rows of the
    LinnStrument. Expected:
    - each finger keeps its bend, its Y and its pressure;
    - both notes are at the same pitch;
    - lifting a finger only switches off its note.
11. Write down what happens and go back to the official OS if needed.

## Test results (from 2026-11-19)

| Stage | Result |
|---|---|
| 1 | OK. The re-signed updater launches; the keyboard accepts the recompressed file. |
| 2 | OK in Performance: notes on channels 2 to 16 play on the slot in Keyboard Focus. No per-note bend or timbre (expected). |
| 3 | OK: notes on channels 2 to 16, **independent per-note bend**. |
| 5 (3rd version) | **OK**: Y (CC74) of channels 2 to 16 acts as a Wheel morph of its own for each note. Two faults: Y at 127 does not reach the effect of the wheel fully up, and the modulation moves **in audible steps** (the wheel is smooth). Fixed in stage 6. |
| 6 | Per-note Z → level: seems to work (not sure; to be made an option). Y scale: seems right now. **Unbearable artefacts** when the finger moves on the pad: Y arrives continuously, and each step recomputed the whole voice. Stage 7. |
| 11 (4th version, 2026-11-20) | **OK**: `P.LE` (level × Z) works; the other Y and Z destinations, the curves and `v` (Z × velocity) also tried: OK. |
| 9 (2nd version) | **OK**: same pitch on two channels, each note keeps its expression, no more stuck notes. |
| 9 (1st version) | **Stuck notes**: the alias was freed at the first of the Note Offs sent to each target. Fixed (2nd version). |
| 8 | Z → Level **seems to work, but disappointing** as a way to play. Decision: go no further; Z → Wheel or Velocity will come as a menu option. **Same note on two channels** (test): the most recent note steals the bend of the older one (known limit of stage 3). |
| 7 (Z) | Z → Level disappointing: hard to hear whether it acts, velocity seems to dominate. Stage 8. |
| 7 | **Artefacts gone**: applying Y parameter by parameter, like the wheel, was the right way. Impression that Y at 127 does not quite reach the wheel fully up yet (controller or scale, to be settled). |
| 5 (1st and 2nd versions) | Stable, synth responsive. **Y has no effect** (Wheel amounts never captured, see "Stage 5 in detail"). Workaround for the collision: channels A–D on Off. |
| 4 | **Actually not** (CC74 never received, see stage 5, 3rd version). First impression: Y acts note by note (test on a single-layer Performance, Velocity morph → cutoff). Per-note bend still works. **Hard to set up**: the Velocity morph has to be built by hand, with its range, program by program. |

Course of an update as seen on the updater: "freeing some space for update", then
transfer, then automatic restart of the keyboard. **Quit the updater after each update**:
otherwise opening it again reports that the port (protocol) is already in use.

**Ergonomics of Y (stage 4).** The principle works, but it depends on a Velocity morph set
in each program, and the morph's range is awkward to set from the panel. Ideas: the
"convert for MPE" helper function (set a Velocity morph → cutoff by default), or a fixed
destination for Y, independent of the program's morphs (done in stage 11: `y.Fr`).

**Collision with the slots' channels.** Outside Performance, a slot set to its own MIDI
channel (e.g. slot C on channel 4) also plays the MPE notes of that channel, in addition to
the slot in Keyboard Focus. Handled in stage 11: in MPE mode, A–D channels lying on a
member channel are ignored.
