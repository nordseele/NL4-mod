# Hardware: Nord Lead 4 main board

Source: the user's photos (kept locally, not in the repository, 2026-11-18). Board "Nord
Lead 4 Vers 0.9 CLA28F", label "Moderkort NL4 0,92". Legend: **[seen]** read on the
board; **[hyp.]** inferred.

## Components

| Ref. | Chip | Role |
|---|---|---|
| U27 | **TI AM1705** (TI part `AM1705DPTP4`, 176-pin PTP package) [seen] | ARM926 processor: the OS analysed here |
| U25, U26 | **ADI ADSP-21489** SHARC (×2) [seen] | audio synthesis [hyp.] |
| U29 | Micron MT48LC8M16A2: 16 MB SDR SDRAM (×16) [seen] | ARM memory at 0xC0000000 |
| U38 | **Micron N25Q032A13E**: 32 Mbit (4 MB) SPI NOR flash, SOIC-8, 3.3 V [seen] | ARM boot flash [strong hyp.] |
| P5 | 2 × 4 male header, next to U38, connected through resistor network RN27 [seen] | **programming connector of U38** [sure, continuity] |
| TP5 | unpopulated 2 × 10 footprint, next to the AM1705 [seen] | 20-pin ARM JTAG [hyp.] |
| P6 | 2 pads "NordRack Jumper" [seen] | same board for the Nord Lead 4R |
| U10, U34 | SOIC-8 near the SHARCs, marked "24M02-DR" + probable ST logo (read by the user, lot K232K), identical | ST M24M02-DR I²C EEPROM, 2 Mbit [hyp.]; use unknown |
| Y1 | 24 MHz crystal near the AM1705 [seen] | ARM clock |

## What this corrects

- **Platform: AM1705**, not OMAP-L138. The AM1705 is the DSP-less version of the
  OMAP-L137 family: ARM926 only, SDR SDRAM on EMIFB at 0xC0000000, 128 KB shared RAM at
  0x80000000, local RAM at 0xFFFF0000. All addresses of the analysis remain right. SDR
  SDRAM, not DDR2, confirms the L137 family.
- **The flash** is the Micron N25Q032, already named by image 2 ("Micron N25Q032",
  "SST 25VF032": the two possible parts for U38).
- **The SHARCs do the audio.** The ARM already computes the pitch voice by voice
  (`voice_pitch_offset`). Per-voice values therefore go from the ARM to the SHARCs
  [strong hyp.]. A per-note bend would be done on the ARM side, without touching the
  SHARC code.
- **SHARC code**: since found in the CODE section (`docs/sharc.md`); the ARM loads it at
  boot. The [Ghidra SHARC module](https://github.com/roblg/ghidra-sharc) is used to read
  it.

## Boot and recovery

- **Update mode without the OS: confirmed** (2026-11-18). Power on while holding Shift +
  Store: the display shows "RDY", the Nord OS Update program recognises the keyboard
  (OS 1.32). A modified OS that crashes can therefore be repaired over USB, without
  opening the keyboard.
- The AM1705 ROM reads the BOOT pins at reset. It can boot from SPI flash or from the UART
  (AIS format), which offers a fallback if the flash is damaged [hyp.: pins not located].
- Flash backup: through P5 if it is indeed U38's connector, otherwise a SOIC-8 clip on
  U38. Keyboard **switched off and unplugged** in both cases. The programmer powers the
  chip at 3.3 V; if the AM1705 interferes with the read, look for a reset pin on P5.

## Continuity test (P5 ↔ U38)

Keyboard unplugged. N25Q032 in SOIC-8, pin 1 marked with a dot:

| U38 pin | Signal |
|---|---|
| 1 | S# (CS) |
| 2 | DQ1 (MISO) |
| 3 | W# |
| 4 | GND |
| 5 | DQ0 (MOSI) |
| 6 | C (CLK) |
| 7 | HOLD# |
| 8 | VCC |

SOIC-8 numbering: pin 1 at the dot, then counter-clockwise (1 to 4 on one side, 5 to 8
coming back along the other). Opposite 1: 8. P5: pin 1 at the triangle, odd pins on one
row, even pins opposite.

For each P5 pin, note the U38 pin that beeps (through RN27, measure on both sides of the
network too; with an ohmmeter if the beeper does not sound). Also note the P5 pins
connected to ground or to nothing.

Result (2026-11-18, measured twice by the user):

| P5 | U38 | Signal |
|---|---|---|
| 1 | 8 | VCC |
| 2 | 4 | GND |
| 3 | 1 | CS |
| 4 | 6 | CLK |
| 5 | 2 | MISO |
| 6 | 5 | MOSI |
| 7 | 3 | W# |
| 8 | — | does not go to U38 |

**P5 is the programming connector of U38 [sure].** HOLD# (U38.7) is not on it: it is
probably pulled up by the board. P5.8 goes elsewhere, probably to the AM1705's reset, to
keep the ARM off the bus during programming [hyp.].

P5.8, keyboard unplugged: 10.007 kΩ to P5.1 (VCC), 10.26 kΩ to P5.2 (ground). It is a
**10 kΩ pull-up to VCC**: P5.8 → VCC = 10 kΩ, and P5.8 → ground = 10 kΩ + the resistance
of the 3.3 V rail to ground (≈ 0.25 kΩ unpowered). The 3.3 V rail is therefore loaded by
many components: **do not power it from the Pico**. Active-low line pulled up: **system
reset [sure]**. Keyboard on, P5.1 = 3.3 V; a contact between P5.8 and ground made the
output relays click and switched off the red LED LD1 (next to P5), then the keyboard
restarted normally (2026-11-18). LD1 is therefore an indicator: off = board in reset.

## Programmer

The user's programmers are not suitable: MPLAB Snap (Microchip microcontrollers), Olimex
AVR-ISP-MK2 (AVR), ST-Link (STM32 SWD). A 3.3 V SPI flash reader driven by `flashrom` is
needed: Raspberry Pi Pico with `pico-serprog`, Raspberry Pi (`linux_spi`) or an FT232H /
FT2232H board. Avoid the ordinary CH341A: its data lines often output 5 V.

## Raspberry Pi Pico (`pico-serprog`) ↔ P5 wiring

Default `pico-serprog` pinout (project README); physical pin numbers of the Pico (pin 1 =
USB corner, GP0).

| Pico | Signal | P5 | U38 |
|---|---|---|---|
| 2 (GP1) | CS | 3 | 1 |
| 4 (GP2) | SCK | 4 | 6 |
| 5 (GP3) | MOSI | 6 | 5 |
| 6 (GP4) | MISO | 5 | 2 |
| 3 (GND) | ground | 2 | 4 |
| 36 (3V3 OUT) | 3.3 V | 1 | 8 — **do not connect before the procedure** |
| 38 (GND) | spare ground | 8 ? | if P5.8 is the ARM reset |

Do not use pins 39 (VSYS) and 40 (VBUS, 5 V). No `.uf2` provided: build it with the Pico
SDK. Planned read: `flashrom -p serprog:dev=/dev/<port>:115200,spispeed=…  -r
nl4_flash.bin` (low speed first, two reads compared). See the lesson below: prefer
`tools/spiprobe.py`, which only reads.

### Pico firmware

`pico_serprog.uf2` (kept locally, not in git), built on 2026-11-18 in an Ubuntu 22.04
container: pico-sdk 1.5.1, `pico-serprog` commit `7f4c4b7` (17 Oct 2023),
`PICO_BOARD=pico` (RP2040, not the Pico 2). Pins confirmed in `main.c`: CS = GP1,
SCK = GP2, MOSI = GP3, MISO = GP4. On the Mac: `brew install flashrom` (1.8.0).

## Reading U38 (2026-11-18): the chip is empty

P5 wiring + reset held (LD1 off), Pico `pico-serprog`, `flashrom` 1.8.0:
- correct detection ("N25Q032..3E", 4096 kB); two complete reads **identical, entirely
  0xFF**;
- check with read-only commands (`spiprobe.py`, opcodes 9F, 05, 70, B5, 85, 65, 03, 0B,
  5A): full RDID `20 BA 16 10 …`, SFDP signature "SFDP" read correctly → **wiring and
  link are good**. READ and FAST READ return 0xFF at 0, 0x100, 0x10000, 0x100000,
  0x200000, 0x3F0000, 0x3FFF00;
- status register 0xB2: SRWD = 1, TB = 1, BP2 = 1 (protection configured), WEL = 1; flag
  register 0x82: protection error. `flashrom -r` tried to remove the protection
  ("Unsetting lock bit(s) failed"): **status register write refused by the chip, nothing
  changed**; WEL clears at power-off.

Conclusion: **the firmware is not in U38** (or U38 has another use). The boot program and
the OS are in another memory, to be found (underside of the board?). Lesson: `flashrom -r`
attempts an unlock, hence a status register write; for a pure read, prefer an extended
`spiprobe.py`.

## What the OS does with U38  [sure unless stated]

At boot, the system initialisation (c0005070) creates an SPI flash object
(`spiflash_create`, c014c4a0) on SPI controller no. 0 of the AM1705, and identifies it by
RDID (`spiflash_detect`, c01374b4) in a table (c03efb20): "Micron N25Q032" (ID 20 BA 16)
or "SST 25VF032", 4 MB, 64 KB sectors, 4 KB subsectors, 256-byte pages. The driver has a
**full erase** method (`spiflash_chip_erase`, c013730c: 0x50, 0xC7, wait, read of the flag
register). The OS also contains an "FFS" file system (error messages c0402e30…).

U38 is therefore used by the OS, and yet empty on this keyboard. Hypotheses: a work area
erased after use (receiving an update, Sound Manager transfers); the firmware and sounds
are in another memory (underside, parallel memory **[hyp.]**). No consequence for MPE.
