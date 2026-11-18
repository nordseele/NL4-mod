# Format `os.cab` (Nord Lead 4 OS v1.32)

Source : `Update Nord Lead 4 OS v1.32.app/Contents/Resources/os.cab` (3 074 576 octets,
SHA-256 `42bbad95…ed16819`). Le programme Mac (`Nord OS Update`, wxWidgets) ne décompresse
rien : il découpe le fichier en sections et les envoie par USB
(`CITProtocol::ParseAndSendBinFileSections`). La décompression se fait sur le clavier.
Protocole de mise à jour : `docs/update-protocol.md`.

## En-tête du fichier (big-endian)

| Offset | Valeur | Sens |
|---|---|---|
| 0x00 | 0x20 | taille de ce préambule |
| 0x04 | 0x2a2b9e | fin de l'image 1 = début de l'image 2 |
| 0x08 | 0x2a2bbe | en-tête de l'image 2 |
| 0x0c | 0x4be52 | taille de l'image 2 (depuis 0x2a2bbe) |

Les 0x20 octets qui suivent l'image 2 sont la fin de sa dernière section (ARM0) : voir
« Offsets des sections ».

## Image

`[0x20 préambule][en-tête][sections…]` ; les offsets des sections comptent depuis
**l'en-tête** (préambule exclu).

En-tête : `u32 0x00ss0100` (ss = 0x84 / 0x70), `u32 ?`, `u32 0x00640000`, `u32 0`,
`u32 nombre de sections` (3), puis 3 entrées de 0x2c octets :

| Champ | Type |
|---|---|
| tag | 4 ASCII (`SRAM`, `CODE`, `ARM0`) |
| offset | u32 |
| taille décompressée | u32 |
| adresse de chargement | u32 |
| checksum | u32 |
| taille compressée | u32 (0 = stocké tel quel) |
| checksum du flux compressé | u32 |
| réservé | 4 × u32 |

## Sections

| Image | Tag | Adresse | Taille | Stockage |
|---|---|---|---|---|
| 1 (OS) | SRAM | 0x80000000 | 0x1c24 | brut |
| 1 (OS) | CODE | 0xc0000000 | 0x40b530 | LZO1X, 0x2a0a3e octets |
| 1 (OS) | ARM0 | 0xffff0020 | 0x268 | brut |
| 2 (test usine) | SRAM | 0x80000000 | 0x1490 | brut |
| 2 (test usine) | CODE | 0xc0000000 | 0x89098 | LZO1X, 0x4a472 octets |
| 2 (test usine) | ARM0 | 0xffff0020 | 0x27c | brut |

Les adresses correspondent à la carte mémoire du TI **AM1705** vu sur la carte (famille
OMAP-L137, ARM926 seul, `docs/hardware.md`) : RAM partagée 0x80000000, SDRAM (EMIFB)
0xc0000000, RAM locale ARM et vecteurs hauts 0xffff0000. ARM little-endian. Le point d'entrée (0xffff0040) fait `ldr pc, =0xc0000000`.

## Offsets des sections  [corrigé le 2026-11-18]

Une section occupe `taille` octets (ou `taille compressée`) à partir de
`début de l'image + 0x20 + offset`. Ses octets sont chargés tels quels à l'adresse de
chargement.

Erreur précédente : on comptait l'offset depuis le début du préambule, donc 0x20 octets
trop tôt. Les 0x20 octets « d'en-tête non chargé » qu'on croyait voir au début de chaque
section étaient en fait **la fin de la section précédente** : des zéros après SRAM,
et pour ARM0 les derniers octets du flux LZO de CODE, avec son marqueur de fin
`11 00 00`. Il manquait donc à chaque section ses 0x20 derniers octets. Les adresses
déjà publiées ne changent pas : l'ancienne image CODE est exactement le début de la
nouvelle, qui a 0x20 octets de plus.

## Compression : LZO1X

Flux LZO1X standard, **avec** son marqueur de fin. Il occupe exactement la taille
compressée et donne exactement la taille déclarée (images 1 et 2). L'« octet de
trop » et l'« input overrun » de liblzo2 notés auparavant venaient de l'offset décalé.

## Checksums : résolus  [sûr]

Pour les 6 sections des deux images, `tools/unpack_oscab.py` les vérifie à chaque
extraction :
- **checksum** = `~(somme des octets de la section) & 0xffffffff`, octets non signés,
  section décompressée ;
- **checksum du flux compressé** = la même formule sur les octets compressés ;
- sections stockées brutes : checksum du flux = 0.

Pour un firmware modifié, il suffit donc de recalculer ces deux sommes, puis de mettre à
jour les tailles. Le programme Mac a aussi un CRC-32 (`Zevs::CRC::CCRC32` : CRC-32
réfléchi, registre initial 0xFFFFFFFF, complément final ; `CCRC32X` rend 0 pour un
registre nul). Il sert au transport (« Message CRC error »), pas aux sections. Le
message « OS BinFile seems broken. Checksum does not match » montre qu'il vérifie aussi
le fichier avant l'envoi. **Cette vérification n'a pas encore été lue** ; elle porte
sans doute sur les mêmes sommes.

## Hachés de référence (charges utiles, sortie de `tools/rebuild.sh`)

```
img1_ARM0_ffff0020.bin  7554211a164a4b2aa7e9a2ee7adfbb002c621de1885ddddba9ef0935476e6cc9
img1_CODE_c0000000.bin  c29d959d9c0e9ea09c9bea733321948de9fba412b982d067081c5c19e609cc6d
img1_SRAM_80000000.bin  ada475d4618926caa6eff8905fb18ad71ef1072062214c2ad44ef18bb5c2a89a
img2_ARM0_ffff0020.bin  0c34341743c9644ce78349adb4967491d7ee399c43354f8246d2e757d59e74e8
img2_CODE_c0000000.bin  376e1b11ed8ae04bdd288787aa803ce0b7c8887a5da0c32e1a8ee5751e4dbbef
img2_SRAM_80000000.bin  d9ebae40678cb0dfe92ad578fdf520446263a422e59d7569f79c61b705947f8c
```
