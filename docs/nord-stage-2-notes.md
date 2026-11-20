# Notes for an MPE project on the Nord Stage 2

Written on 2026-11-19 from the Nord Lead 4 project (this repository). On the Lead 4
(OS 1.32), MPE works with a patch of the ARM OS alone:
- notes on channels 2 to 16 play;
- per-note bend at ±48;
- per-note Y (CC74), applied as a Wheel morph of the voice;
- per-note Z (pressure) on the level (first try at the time; selectable destinations
  since stage 11).

What follows is what is likely to be useful for another Clavia instrument. **Nothing is
checked on the Stage 2**: everything about it is a hypothesis to verify.

## Files to read in this repository

| File | Contents |
|---|---|
| `HANDOFF.md` | status, step-by-step plan, safety rules |
| `docs/oscab-format.md` | `os.cab` format (headers, sections, LZO1X, checksums) and rebuilding |
| `docs/update-protocol.md` | protocol of the Mac updater ↔ keyboard |
| `docs/feasibility.md` | MPE feasibility analysis, A–F breakdown |
| `docs/voices-midi.md` | MIDI input, voices, morph, CC routing (Lead 4 specific) |
| `docs/patches.md` | patch chain, detail of each stage, test results |
| `docs/sharc.md` | SHARC DSP code, ARM → SHARC link |
| `docs/hardware.md` | board (AM1705 + 2 × ADSP-21489), recovery |
| `tools/unpack_oscab.py`, `tools/pack_oscab.py` | decompress / rebuild `os.cab` |
| `tools/patch/build.py`, `tools/patch/*.c` | compile C into a hole of the image, set the branches, rebuild |
| `tools/patch/make_updater.sh` | copy the official updater, put our `os.cab` in it, re-sign |
| `tools/mkelf.py`, `tools/rebuild.sh`, `tools/symbols.txt` | ELF for Ghidra with our function names |

The tools contain addresses and constants specific to the Lead 4: to be adapted, not run
as they are.

## What is likely to be shared (same maker, to be checked)

- **Updater.** The Mac updater (classes `Zevs::CCabHeader`, `CBinHeader`, `CBinFile`)
  reads `Contents/Resources/os.cab`. Replacing it breaks the signature: the copy is
  re-signed ad hoc (`codesign --force --deep --sign -`) and the quarantine flag removed
  (`xattr -cr`). Each copy needs its own `CFBundleIdentifier`, otherwise macOS brings an
  already open copy to the front and reflashes the previous OS. Quit the updater after
  each update (otherwise "protocol already in use").
- **`os.cab`.** Big-endian headers, sections compressed with **LZO1X** (we recompress with
  LZO1X-999; the keyboard accepts it), two "~sum of bytes" checksums. If the Stage 2 uses
  the same format, `unpack_oscab.py` / `pack_oscab.py` should almost work.
- **Recovery.** On the Lead 4, Shift + Store at power-on forces Update mode and always
  allows putting the official OS back. Check the equivalent on the Stage 2 **before any
  flashing**.
- **Architecture.** ARM (AM1705 here) + SHARC for audio. The SHARC is a "dumb" engine: the
  ARM writes each voice's parameters directly into its memory and the SHARC smooths them.
  All of MPE was therefore done on the ARM side, without touching the SHARC code. The
  Stage 2 has other engines (piano, organ, synth): the voice structure will surely be
  different.

## Method that worked

1. **Without flashing anything**: decode and rebuild `os.cab` identically (same
   checksums). Ghidra on the ARM image, naming functions along the way.
2. **Stage 1**: flash the official OS recompressed by our tools (proves the chain and the
   re-signed updater).
3. Then one stage per feature, each one testable on its own on the instrument:
   - notes on channels 2–16;
   - per-note bend;
   - Y;
   - Z.
4. The added code is compiled C (`arm-none-eabi-gcc -Os -marm`, Docker container), linked
   into a free hole at the end of the CODE image. Original functions are diverted through
   vtable pointers or rewritten `b` instructions. Each modified word is checked against
   its original value. Final check: re-extract the produced `.cab` and compare with the
   original (only the expected words change).
5. When the hole is no longer enough, (zeroed) variables can go to the start of the heap:
   move the start of `_sbrk` and the size of the startup zeroing. Code can go into dead
   code areas of the firmware (`tools/find_dead_code.py`).

## Pitfalls met (they cost hours)

- **"This-adjusting" relays (C++ with multiple inheritance).** An object subscribed to
  MIDI has one sub-object per message type. The bus sometimes calls the sub-object's
  vtable, which points to a small relay `sub r0, r0, #N ; b function`. Replacing the entry
  in the main vtable is then useless. On the Lead 4, bend went through the vtable, but CCs
  and pressure went through relays. **To intercept a handler, also look for the `b`
  instructions to it, not only the pointers.**
- **The channel is lost early.** The firmware stores bend, pressure, etc. per target
  (slot), with a single value for all notes. You have to keep the channel of each voice
  yourself at Note On (voice → channel table) and apply the values per voice.
- **Do not recompute everything on each message.** Y arrives continuously (a finger on a
  pad is never still). Calling the function that recomputes the whole voice (≈ 80 settings
  sent to the DSP) at each step gave unbearable artefacts. You have to take the firmware's
  "one parameter, one voice" path (the one the wheel uses), only for the parameters
  concerned. Smooth the 7-bit values per voice (1/8 of the way per tick).
- **Channel collisions.** Channels set for slots or parts (A–D on the Lead 4) conflict with
  the MPE member channels. Stage 11 ignores them in MPE mode.
- **Controllers.** According to a forum thread (unofficial), the LinnStrument resets
  pressure to 0 before each Note On and Note Off, and by default it sends Poly AT rather
  than Channel Pressure. The MPE standard: per-note bend ±48 and ±2 on the master channel
  (settable through RPN 0), zone configuration through RPN 6 (MCM).
- **Diagnostics without debug output.** A diagnostic "by ear" (transposing the notes
  according to a code) was tedious and not very conclusive. Plan an output channel early
  instead, for example MIDI messages sent by the patch, or values shown in a menu entry
  (what stages 10 and 11 did).

## Safety rules kept here

- The maker's firmware, software and manual stay out of git: only notes, formats and our
  own tools are committed.
- Nothing written to the keyboard before the checksums are reproduced and the recovery
  mode is checked.
- SPI chips are read read-only (no `flashrom -r`, which tries to remove the write
  protection).
