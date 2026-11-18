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

P5.8, clavier débranché : 10,007 kΩ vers P5.1 (VCC), 10,26 kΩ vers P5.2 (masse). C'est
une **résistance de tirage de 10 kΩ vers VCC** : P5.8 → VCC = 10 kΩ, et P5.8 → masse =
10 kΩ + la résistance du rail 3,3 V vers la masse (≈ 0,25 kΩ hors tension). Le rail
3,3 V est donc chargé par beaucoup de composants : **ne pas l'alimenter par le Pico**.
Ligne active à l'état bas tirée au + : **reset du système [sûr]**. Clavier allumé, P5.1 =
3,3 V ; un contact entre P5.8 et la masse a fait claquer les relais de sortie et éteint
la LED rouge LD1 (voisine de P5), puis le clavier est reparti normalement (2026-11-18).
LD1 sert donc de témoin : éteinte = carte en reset.

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

### Firmware du Pico

`hardware/pico/pico_serprog.uf2` (hors git), compilé le 2026-11-18 dans un conteneur
Ubuntu 22.04 : pico-sdk 1.5.1, `pico-serprog` commit `7f4c4b7` (17 oct. 2023),
`PICO_BOARD=pico` (RP2040, pas le Pico 2). Broches confirmées dans `main.c` : CS = GP1,
SCK = GP2, MOSI = GP3, MISO = GP4. Côté Mac : `brew install flashrom` (1.8.0).

## Lecture de U38 (2026-11-18) : la puce est vide

Câblage P5 + reset tenu (LD1 éteinte), Pico `pico-serprog`, `flashrom` 1.8.0 :
- détection correcte (« N25Q032..3E », 4096 kB) ; deux lectures complètes **identiques,
  entièrement à 0xFF** ;
- vérification par commandes de lecture seules (`spiprobe.py`, opcodes 9F, 05, 70, B5,
  85, 65, 03, 0B, 5A) : RDID complet `20 BA 16 10 …`, signature SFDP « SFDP » lue
  correctement → **le câblage et la liaison sont bons**. READ et FAST READ rendent
  0xFF à 0, 0x100, 0x10000, 0x100000, 0x200000, 0x3F0000, 0x3FFF00 ;
- registre d'état 0xB2 : SRWD = 1, TB = 1, BP2 = 1 (protection configurée), WEL = 1 ;
  registre de drapeaux 0x82 : erreur de protection. `flashrom -r` a tenté de lever la
  protection (« Unsetting lock bit(s) failed ») : **écriture du registre d'état refusée
  par la puce, rien n'a changé** ; WEL s'efface à la mise hors tension.

Conclusion : **le firmware n'est pas dans U38** (ou U38 a un autre usage). Le
programme de démarrage et l'OS sont dans une autre mémoire, à trouver (face inférieure
de la carte ?). Leçon : `flashrom -r` tente un déverrouillage, donc une écriture du
registre d'état ; pour une lecture pure, préférer `spiprobe.py` étendu.

## Ce que l'OS fait de U38  [sûr sauf mention]

Au démarrage, l'initialisation système (c0005070) crée un objet flash SPI
(`spiflash_create`, c014c4a0) sur le contrôleur SPI n° 0 de l'AM1705, et l'identifie
par RDID (`spiflash_detect`, c01374b4) dans une table (c03efb20) : « Micron N25Q032 »
(ID 20 BA 16) ou « SST 25VF032 », 4 Mo, secteurs 64 Ko, sous-secteurs 4 Ko, pages 256 o.
Le pilote a une méthode d'**effacement complet** (`spiflash_chip_erase`, c013730c :
0x50, 0xC7, attente, lecture du registre de drapeaux). L'OS contient aussi un système de
fichiers « FFS » (messages d'erreur c0402e30…).

U38 est donc bien utilisée par l'OS, et pourtant vide sur ce clavier. Hypothèses : zone
de travail effacée après usage (réception d'une mise à jour, transferts Sound
Manager) ; le firmware et les sons sont dans une autre mémoire (face inférieure,
mémoire parallèle **[hyp.]**). Sans conséquence pour le MPE.
