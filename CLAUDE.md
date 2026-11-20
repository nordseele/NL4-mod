# NL4 MPE — MPE for the Nord Lead 4

Read `HANDOFF.md` first (status, plan, how to resume), then `docs/voices-midi.md`.

Project rules:
- Clavia's firmware, software and manual stay out of git (`vendor/`, `ghidra/bin/`,
  `build/`). Only notes, formats and our own tools are committed. The repository is
  public: no data extracted from the firmware either (generated files go to `ghidra/bin/`).
- Never write to the keyboard or flash anything before step 3 of the plan (checksums
  reproduced, Update mode through Shift + Store checked: both done). The hardware backup
  of the flash is no longer required: U38 is empty and the firmware memory is not
  reachable without taking the board out (last resort).
- To read an SPI chip: `tools/spiprobe.py` (read-only). No `flashrom -r`, which tries to
  remove the write protection.
- The project's Ghidra container: `pyghidra-nl4` (port 8003). Do not touch the other
  pyghidra containers (other projects).
- Function names go into `tools/symbols.txt`, then `tools/rebuild.sh` and re-import into
  Ghidra.
- Remote: `github.com/nordseele/NL4_MPE`, **public** since 2026-11-20 (the user's
  decision). `hardware/` (photos of the board) stays local. Docs are written in English.
- The user writes in French: answer in French.
