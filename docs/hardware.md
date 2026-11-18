# Matériel : carte mère du Nord Lead 4

Source : photos de l'utilisateur (`hardware/photos/`, 2026-11-18). Carte « Nord Lead 4
Vers 0.9 CLA28F », étiquette « Moderkort NL4 0,92 ». Légende : **[vu]** lu sur la
carte ; **[hyp.]** déduit.

## Composants

| Repère | Puce | Rôle |
|---|---|---|
| U27 | **TI AM1705** (référence TI `AM1705DPTP4`, boîtier PTP 176 broches) [vu] | processeur ARM926 : l'OS analysé ici |
| U25, U26 | **ADI ADSP-21489** SHARC (×2) [vu] | synthèse audio [hyp.] |
| U29 | Micron MT48LC8M16A2 : SDRAM SDR 16 Mo (×16) [vu] | mémoire de l'ARM à 0xC0000000 |
| U38 | **Micron N25Q032A13E** : flash SPI NOR 32 Mbit (4 Mo), SOIC-8, 3,3 V [vu] | flash de démarrage de l'ARM [hyp. forte] |
| P5 | barrette mâle 2 × 4, voisine de U38, reliée par le réseau de résistances RN27 [vu] | **connecteur de programmation de U38** [sûr, continuité] |
| TP5 | empreinte 2 × 10 non équipée, à côté de l'AM1705 [vu] | JTAG ARM 20 broches [hyp.] |
| P6 | 2 pastilles « NordRack Jumper » [vu] | même carte pour le Nord Lead 4R |
| U10, U34 | SOIC-8 près des SHARC, marquage « 24M02-DR » + logo ST probable (lu par l'utilisateur, lot K232K), identiques | EEPROM I²C ST M24M02-DR, 2 Mbit [hyp.] ; usage inconnu |
| Y1 | quartz 24 MHz près de l'AM1705 [vu] | horloge de l'ARM |

## Ce que ça corrige

- **Plateforme : AM1705**, pas OMAP-L138. L'AM1705 est la version sans DSP de la famille
  OMAP-L137 : ARM926 seul, SDRAM SDR sur EMIFB à 0xC0000000, RAM partagée de 128 Ko à
  0x80000000, RAM locale à 0xFFFF0000. Toutes les adresses de l'analyse restent justes.
  La SDRAM SDR, et non DDR2, confirme la famille L137.
- **La flash** est la Micron N25Q032, déjà citée par l'image 2 (« Micron N25Q032 »,
  « SST 25VF032 » : les deux références possibles de U38).
- **Les SHARC font l'audio.** L'ARM calcule déjà la hauteur voix par voix
  (`voice_pitch_offset`). Les valeurs par voix partent donc de l'ARM vers les SHARC
  [hyp. forte]. Un bend par note se ferait côté ARM, sans toucher au code SHARC.
- **Code des SHARC** : pas encore localisé. `os.cab` ne contient que des images ARM.
  Deux possibilités : (1) le code SHARC est une donnée dans CODE, et l'ARM le charge au
  démarrage ; (2) les SHARC ont leur propre flash (U10 / U34 ?). Le
  [module Ghidra SHARC](https://github.com/roblg/ghidra-sharc) servira dans les deux cas.

## Démarrage et récupération

- **Mode Update sans l'OS : confirmé** (2026-11-18). Allumer en tenant Shift + Store :
  l'écran affiche « RDY », le programme Nord OS Update reconnaît le clavier (OS 1.32).
  Un OS modifié qui plante reste donc réparable par USB, sans ouvrir le clavier.
- La ROM de l'AM1705 lit les broches BOOT au reset. Elle sait démarrer depuis la flash
  SPI ou depuis l'UART (format AIS), ce qui offre un recours si la flash est abîmée
  [hyp. : broches non repérées].
- Sauvegarde de la flash : par P5 si c'est bien le connecteur de U38, sinon pince
  SOIC-8 sur U38. Clavier **hors tension et débranché** dans les deux cas. Le
  programmateur alimente la puce en 3,3 V ; si l'AM1705 gêne la lecture, chercher une
  broche de reset sur P5.

## Test de continuité à faire (P5 ↔ U38)

Clavier débranché. N25Q032 en SOIC-8, broche 1 marquée d'un point :

| Broche U38 | Signal |
|---|---|
| 1 | S# (CS) |
| 2 | DQ1 (MISO) |
| 3 | W# |
| 4 | GND |
| 5 | DQ0 (MOSI) |
| 6 | C (CLK) |
| 7 | HOLD# |
| 8 | VCC |

Numérotation SOIC-8 : broche 1 au point, puis sens inverse des aiguilles d'une montre
(1 à 4 sur un côté, 5 à 8 en revenant par l'autre). En face du 1 : le 8.
P5 : broche 1 au triangle, impairs sur une rangée, pairs en face.

Pour chaque broche de P5, noter la broche de U38 qui sonne (à travers RN27, mesurer
aussi des deux côtés du réseau ; en ohmmètre si le bip ne sonne pas). Noter aussi les
broches de P5 reliées à la masse ou à rien.

Résultat (2026-11-18, mesuré deux fois par l'utilisateur) :

| P5 | U38 | Signal |
|---|---|---|
| 1 | 8 | VCC |
| 2 | 4 | GND |
| 3 | 1 | CS |
| 4 | 6 | CLK |
| 5 | 2 | MISO |
| 6 | 5 | MOSI |
| 7 | 3 | W# |
| 8 | — | ne va pas à U38 |

**P5 est le connecteur de programmation de U38 [sûr].** HOLD# (U38.7) n'y est pas : il est
sans doute tiré au + par la carte. P5.8 va ailleurs, probablement au reset de l'AM1705,
pour tenir l'ARM à l'écart du bus pendant la programmation [hyp.].

## Programmateur

Ceux de l'utilisateur ne conviennent pas : MPLAB Snap (microcontrôleurs Microchip),
Olimex AVR-ISP-MK2 (AVR), ST-Link (SWD des STM32). Il faut un lecteur de flash SPI en
3,3 V piloté par `flashrom` : Raspberry Pi Pico avec `pico-serprog`, Raspberry Pi
(`linux_spi`) ou carte FT232H / FT2232H. Éviter le CH341A ordinaire : ses lignes de
données sortent souvent en 5 V.

## Câblage Raspberry Pi Pico (`pico-serprog`) ↔ P5

Brochage par défaut de `pico-serprog` (README du projet) ; numéros de broches physiques
du Pico (broche 1 = coin USB, GP0).

| Pico | Signal | P5 | U38 |
|---|---|---|---|
| 2 (GP1) | CS | 3 | 1 |
| 4 (GP2) | SCK | 4 | 6 |
| 5 (GP3) | MOSI | 6 | 5 |
| 6 (GP4) | MISO | 5 | 2 |
| 3 (GND) | masse | 2 | 4 |
| 36 (3V3 OUT) | 3,3 V | 1 | 8 — **ne pas brancher avant la procédure** |
| 38 (GND) | masse en réserve | 8 ? | si P5.8 est le reset de l'ARM |

Ne pas utiliser les broches 39 (VSYS) et 40 (VBUS, 5 V). Pas de `.uf2` fourni : à
compiler avec le SDK Pico. Lecture prévue :
`flashrom -p serprog:dev=/dev/<port>:115200,spispeed=…  -r nl4_flash.bin` (vitesse
basse d'abord, deux lectures comparées).
