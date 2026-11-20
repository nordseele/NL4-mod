# SHARC code (ADSP-21489)

Exploration of 2026-11-18. Legend: **[sure]** read; **[hyp.]** inferred.

## Where it is  [sure]

In the CODE section of the ARM OS (image 1 of `os.cab`), as **two ADI 214xx boot
streams** (32-bit format, uncompressed), one per SHARC:

| Stream | ARM address | Size | Blocks | VISA code (INIT_L16 at 0x1C0300) | Data |
|---|---|---|---|---|---|
| 1 | 0xc03c5720 | 0x13C10 | 445 | 0x6A28 bytes | blocks 0, 1, 3 (0x90000, 0xB0000, 0xE0000) |
| 2 | 0xc03d9334 | 0x13DB0 | 451 | 0x6B30 bytes | same, a little more in block 0 |

Each stream is followed by its length in 32-bit words (0x4F04, 0x4F6C). It starts with the
ADI boot kernel (256 instructions), identical byte for byte to the Prophet 12's, then
ZERO_LDATA / INIT_L16 / INIT_L32 blocks, and ends with FINAL_INIT. The ARM sends them at
boot: loader `fn_c010cc98`, pointers to the two streams at 0xc010cddc / 0xc010cde0. The two
programs are close but different: distinct roles **[hyp.: one SHARC per half of the
voices, plus the effects on one of the two]**.

Consequence for safety: as on the Prophet 12, the SHARCs keep no program of their own;
reinstalling the OS also reinstalls their code.

## Tools

- `tools/extract_sharc.py`: extracts the two streams (`ghidra/bin/sharc/*.ldr`, not in
  git), checks the block chain and the length.
- Ghidra: the `roblg/ghidra-sharc` extension (announced support for the
  ADSP-21483–21489), **reused as built in the Prophet 12 project**
  (`<Prophet 12 project>/ghidra/projects_sharc/ext/installed/SHARC`, mounted read-only).
  Headless import in a throwaway container, project in `ghidra/sharc_work/` (not in git):

```sh
docker run --rm -v "$PWD/ghidra/bin/sharc":/ldr:ro -v "$PWD/ghidra/sharc_work":/work \
  -v "$SHARC_EXT":/ghidra/Ghidra/Extensions/SHARC:ro \
  --entrypoint /ghidra/support/analyzeHeadless ghcr.io/clearbluejar/pyghidra-mcp:sha-f43400b \
  /work/proj nl4dsp -import /ldr/sharc1_c03c5720.ldr /ldr/sharc2_c03d9334.ldr \
  -loader SharcLdrLoader -overwrite -scriptPath /work/scripts -postScript Survey.java
```

(`SHARC_EXT` = the folder of the built extension.) Scripts in `tools/sharc/` (to copy into
`ghidra/sharc_work/scripts/`): `Survey.java` (taken from the Prophet 12 project),
`CmdHandlers.java` (creates the 27 `dsp_cmd_NN` from the DM table 0x92180), `ListAll.java`
and `DumpAll.java` (full disassembly and pseudo-C, argument = output file, with
`-process <prog> -postScript …`).

Result of the import: 48 and 50 functions, ≈ 1,900 instructions each, **0 errors, 100 %
of functions decompiled**. Coverage is partial (the code is ≈ 27 KB; a large part is only
reached through interrupts or indirect calls).

## ARM → SHARC link  [sure unless stated]

**ARM side.** `hw_write(dsp, word1, word2)` (c014f0d0) writes two 32-bit words to a port
mapped on the AM1705's EMIFA bus, with GPIO flow control. Port table (c0402668): up to 4
ports at **0x62000000 / +4 / +8 / +C** (EMIFA CS3), two used (one per SHARC). Link logic
on the board **[hyp.]** serialises them to the SHARC. Voices alternate between the two
SHARCs: `dsp = hardware number & 1`, 10 voices each.

**SHARC side.** The audio routine (`FUN_sw_001c25fb`, called at each block) starts by
draining a **ring buffer of word pairs**, filled by chained DMA from a SPORT serial port
(DMA registers 0xC40–0xC4F, current pointer read at 0x2400 **[hyp.]**):

```
word 1 = [command: 8 bits | address: 24 bits]      word 2 = value
command 0      : DM[address] = value               (direct write)
command 1..26  : call through the DM table 0x92180 (identical on both SHARCs)
```

The 27 commands are **memory access primitives**, not synthesis commands: writes at I7 /
I7+1, reads sent back over SPI (TXSPI 0x1003), setting of the I7 / M7 pointers, stream
write `DM(I7, M7) = value` (cmd 18, 19), restart of the receive DMA (cmd 22), memory DMA
transfer (cmd 25). The SPI interrupt (VEC_P1I) serves the read-back: it receives an
address and sends back its contents.

**Consequence: the SHARC is a "dumb" engine whose parameters the ARM writes directly in
memory.** Each voice parameter is a SHARC memory cell (address = base + voice × stride,
e.g. the pitch: `voice × 8 + base`).

**Smoothing.** Right after, the audio routine moves each parameter towards its target
(`current += coef × (target − current)`, target at 0x921A4…, current at 0xE1E00…, by
groups). Continuous and frequent changes will therefore not click.

## What this changes for MPE

- **Nothing to change on the SHARC side.** Per-voice Y / Z = the ARM writes, for a single
  voice, values it already writes today for all voices of a slot; the SHARC applies and
  smooths them.
- No equivalent of the Prophet 12's command 0x1F6 to find: everything goes through memory
  writes. A lighter path than `voice_apply_velocity` therefore exists: write directly, for
  one voice, the SHARC address(es) of the wanted destinations (e.g. the filter cutoff). To
  map: the SHARC address of each voice parameter (calls of `hw_write`, ~285). (Stage 11
  found the per-voice level address: DM `0x9248a + (n >> 1) × 0x40`, `docs/patches.md`.)

## To explore, if useful for MPE

1. ~~ARM → SHARC protocol~~: done (section "Link").
2. ~~Smoothing~~: yes, per block, on the SHARC side.
3. ~~Per-voice modulation input~~: not needed, direct memory writes.
4. Map of the SHARC addresses of voice parameters (from the calls of `hw_write`).
5. Role of the two programs (≈ 0x100 bytes of code difference) and CPU cost per block.
