# Format `os.cab` (Nord Lead 4 OS v1.32)

Source : `Update Nord Lead 4 OS v1.32.app/Contents/Resources/os.cab` (3 074 576 octets,
SHA-256 `42bbad95…ed16819`). Le programme Mac (`Nord OS Update`, wxWidgets) ne décompresse
rien : il découpe le fichier en sections et les envoie par USB
(`CITProtocol::ParseAndSendBinFileSections`). La décompression et la vérification se font
sur le clavier.

## En-tête du fichier (big-endian)

| Offset | Valeur | Sens |
|---|---|---|
| 0x00 | 0x20 | taille de ce préambule |
| 0x04 | 0x2a2b9e | fin de l'image 1 = début de l'image 2 |
| 0x08 | 0x2a2bbe | en-tête de l'image 2 |
| 0x0c | 0x4be52 | taille de l'image 2 (depuis 0x2a2bbe) |

Il reste 0x20 octets après la fin de l'image 2 (rôle inconnu).

## Image

`[0x20 préambule][en-tête][sections…]` ; les offsets des sections comptent depuis le début
de l'image (préambule inclus).

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

Les adresses correspondent à la carte mémoire d'un TI OMAP-L138 / AM18xx (ARM926 +
DSP C674x) : RAM partagée 0x80000000, DDR2 0xc0000000, RAM locale ARM et vecteurs hauts
0xffff0000. ARM little-endian. Le point d'entrée (0xffff0040) fait `ldr pc, =0xc0000000`.

## Compression : LZO1X

Chaque section compressée commence par 0x20 octets nuls, puis un flux LZO1X standard
**sans marqueur de fin** : il s'arrête à la taille compressée de l'en-tête. La sortie
inclut les 0x20 octets nuls. L'image 1 décode 1 octet de trop (dernier littéral), tronqué
à la taille déclarée. L'image 2 tombe pile sur sa taille.

## Checksums : partiellement résolus

- **SRAM** (images 1 et 2) : `~sum(octets) & 0xffffffff` sur la section entière. Exact.
- **CODE, ARM0** : même ordre de grandeur (les 16 bits de poids fort concordent), mais
  pas égal. Écarts : ARM0 img1 0x516, img2 0x755 ; CODE img1 0xb62, img2 0xc9f. La somme
  couvre sans doute quelques octets de plus que la section seule (ou applique un
  traitement à ARM0, dont les 0x20 premiers octets ne sont pas du code). **À résoudre
  avant toute écriture de firmware modifié.**
- Le programme Mac contient `Zevs::CRC::CCRC32` / `CCRC32X` : piste pour le checksum
  du flux.

## Hachés de référence (sortie de `tools/rebuild.sh`)

```
img1_SRAM_80000000.bin  ac192273ba004b187adf0475c062cdd9029974eaf7dfeccbffb663b2fd9c5993
img1_CODE_c0000000.bin  7f4154e78c568310c05a45ab7b127ca636fbe091f4c4aef088743a3e72abe6f5
img1_ARM0_ffff0020.bin  da17bfd694820ae8cc325e83cabe0419cd4cec3c5176fc0fdd8c240f13460838
img2_SRAM_80000000.bin  87d62557715c4475cd165ffc89b6c40d2b142a00597d95ec15a0e02da8890430
img2_CODE_c0000000.bin  360e438940d654ba68da544b582f6d495e66ed8793a6376073b63b60543f6dbf
img2_ARM0_ffff0020.bin  7ccb961ccf82cf57737b4b394c3c5f9e186a78970a73d16bf926238ef703d034
```
