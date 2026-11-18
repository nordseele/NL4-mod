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

## En-tête de section (0x20 octets, non chargé)

Chaque section commence par 0x20 octets qui **ne sont pas chargés** : la charge utile
qui suit démarre à l'adresse de chargement. En-tête nul pour SRAM et CODE ; pour ARM0,
il contient des valeurs (img1 : `b540c07c 82030000 0200241a 13b0950a c1fc2e18 c0c43518
c0010000 00110000`), rôle inconnu. Vérifié : avec cette règle, 3 737 entrées sur 3 738
des tables de pointeurs de code tombent sur un début de fonction, et 353 chaînes sur
364 sont pointées exactement ; en chargeant l'en-tête, tout est décalé de 0x20.
`tools/unpack_oscab.py` écrit la charge utile seule.

## Compression : LZO1X

Chaque section compressée commence par 0x20 octets nuls, puis un flux LZO1X standard
**sans marqueur de fin** : il s'arrête à la taille compressée de l'en-tête. La sortie
inclut les 0x20 octets nuls. L'image 1 décode 1 octet de trop (dernier littéral), tronqué
à la taille déclarée. L'image 2 tombe pile sur sa taille.

Validé avec la bibliothèque de référence liblzo2 2.10 (`lzo1x_decompress_safe`) : mêmes
octets que `tools/unpack_oscab.py`. Elle s'arrête 4 octets avant la taille déclarée,
avec « input overrun », faute de marqueur de fin.

## Checksums : partiellement résolus

- **SRAM** (images 1 et 2) : `~sum(octets) & 0xffffffff` sur la section entière. Exact.
- **CODE, ARM0** : même ordre de grandeur (les 16 bits de poids fort concordent), mais
  pas égal. Écarts : ARM0 img1 0x516, img2 0x755 ; CODE img1 0xb62, img2 0xc9f. La somme
  couvre sans doute quelques octets de plus que la section seule (ou applique un
  traitement à ARM0, dont les 0x20 premiers octets ne sont pas du code). **À résoudre
  avant toute écriture de firmware modifié.**
- Le programme Mac contient `Zevs::CRC::CCRC32` / `CCRC32X` : piste pour le checksum
  du flux.

## Hachés de référence (charges utiles, sortie de `tools/rebuild.sh`)

```
img1_ARM0_ffff0020.bin  f331c6e6a89a749d4e72cf72468abb2b9dcf3c7b17228dea27ac20dea57dedba
img1_CODE_c0000000.bin  8b417445b175995e77398d2012a67840249abdc7f8d4a3399373f246671010e6
img1_SRAM_80000000.bin  c79b45785551a2bcb1c7a6376fa1b1d8555a4b3288da4c23e66fa0081d7ef597
img2_ARM0_ffff0020.bin  40be0e0beec00cd3206f9addd01a71ab2f52007d5cdc5192e926063a89374555
img2_CODE_c0000000.bin  756b74d8a411420ad430a0cb7259d8fa802f21fc041fd1ae4ae0c4d04dddd680
img2_SRAM_80000000.bin  d1b3937d4bf59f56f759b0f24c61ab58fd9bf6db09cec7fe69cf2fa9e4b59150
```
