# OS update: protocol and safety

Source: the Mac program `Nord OS Update` (x86_64 slice, C++ symbols present), analysed in
Ghidra (`/nordosupdate_x86_64-…`, `pyghidra-nl4` container). To recreate it:
`lipo "vendor/Nord OS Update (binaire seul, extrait de l'app)" -thin x86_64 -output
ghidra/bin/nordosupdate_x86_64`, then `import_binary`. Legend: **[sure]** read in the code;
**[hyp.]** inferred.

## The keyboard's four programs  [sure]

The keyboard announces a "software mode" (`Zevs::ESoftwareMode`, `S_GetModeString`):

| no. | name | where |
|---|---|---|
| 0 | OS | image 1 of `os.cab` |
| 1 | TP | image 2 of `os.cab` (factory test program: LCD, MIDI, LEDs, serial number) |
| 2, 3 | Reserved1 / Reserved2 | — |
| 4 | **Update** | **not in `os.cab`**, in the keyboard's flash |
| 5 | **Boot** | **not in `os.cab`**, in the keyboard's flash |

The update program (4) and the loader (5) are not part of the file. An OS update therefore
does not rewrite them **[strong hyp.]**: nothing in the protocol transmits their code.
Image 2 contains no erase or update-receive routine.

## Course of an update  [sure]

Two-layer USB protocol: `Ctrl` (version, reboot, boot) and `IT` (transfer).

1. **Connection** (`DeviceConnected`, state 0): version request for each of the four
   programs (`SendRemoteVersionRequest`, `OnVersionReply`).
2. **Start** (`StartSending`): `CQryVersion`. If the keyboard answers in mode 4 (Update),
   go to 3. Otherwise, `CReqReboot` (Ctrl message no. 4, one byte = target mode, here
   **4**), wait for the reconnection, new request. If the keyboard is still not in mode 4:
   "ERROR: Synth is still not in update mode after reboot."
3. **Information** (`CRpyInfo`): the keyboard gives the size of its area and the size of a
   sector. Larger file → "File is too big! Memory is only %d KB".
4. **Erase** (`CReqErase`, one sector at a time): as many sectors as the file size
   requires (`file size / sector size`, rounded up). "Freeing space for update…", then
   "Erase sector %d failed" on failure. **The keyboard chooses where this area is.**
5. **Transfer** (`SendBinFileSection` for each section, `XfrBegin` / `XfrData` /
   `XfrEnd`).
6. **End** (`ITProtocolFinished`): `CReqReboot` with mode **0** (OS). After the
   reconnection, the announced version must be the file's: "Update completed
   successfully", otherwise "Update seems to have failed".

`CReqBoot` (Ctrl message no. 5, a 32-bit address) makes the keyboard start at a given
address (`ITProtocolFinished_BootAtAddress`, "BIN-file code section started"). It is used
to transfer raw `.bin` files (`SendResourceBin`).

The protocol also defines `CReqMemDump` / `CReqMemWrite` (memory read and write) and
`CReqChecksum`. The Mac program does not use them: their handlers are empty. **Whether the
keyboard's Update program accepts them is unknown.** If it does, it would be a way to read
the flash over USB. Not to be tested.

## Safety: what this implies

- **Checksums: solved** (`docs/oscab-format.md`). A modified `os.cab` can carry correct
  sums.
- **Power loss during the update**: the OS area is erased before the transfer. Nord must
  therefore make sure that a keyboard without a valid OS stays recoverable, otherwise any
  USB cut would make it unusable. **[hyp.]** The loader checks the OS at boot and stays in
  Update mode if the OS is invalid.
- **Modified OS that boots then crashes**: this is the real risk. Rebooting into Update
  mode normally goes through the OS (`CReqReboot`). A way to enter Update mode without the
  OS is therefore needed: **power on while holding Shift + Store**. **Confirmed on the
  Lead 4** (2026-11-18): the display shows "RDY" and Nord OS Update recognises the
  keyboard.
- **Last resort, hardware**: the firmware memory is not reachable without taking the board
  out (U38, the SPI flash on connector P5, is empty: `docs/hardware.md`), or a UART boot
  from the AM1705 ROM (boot mode pins).

## Left to do for step 3

1. ~~Enter Update mode without the OS~~: done.
2. ~~File check on the Mac side~~: read (`docs/oscab-format.md`), reproduced by
   `tools/pack_oscab.py`.
3. ~~Backup of U38~~: U38 is empty (`docs/hardware.md`); the firmware is in another
   memory. Hardware backup dropped, except as a last resort.
