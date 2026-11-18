# Format `os.cab` (Nord Lead 4 OS v1.32)

Source : `Update Nord Lead 4 OS v1.32.app/Contents/Resources/os.cab` (3 074 576 octets,
SHA-256 `42bbad95…ed16819`). Le programme Mac (`Nord OS Update`, wxWidgets) ne décompresse
rien : il découpe le fichier en sections et les envoie par USB
(`CITProtocol::ParseAndSendBinFileSections`). La décompression se fait sur le clavier.
Protocole de mise à jour : `docs/update-protocol.md`.

## En-tête du fichier (big-endian)  [sûr : lu dans l'updater, `Zevs::CCabHeader`]

Quatre couples (offset, taille), un par programme ; les couples vides valent 0. L'updater
vérifie qu'ils ne se chevauchent pas.

| Offset | Valeur | Sens |
|---|---|---|
| 0x00 / 0x04 | 0x20 / 0x2a2b9e | image 1 (OS) : offset, taille |
| 0x08 / 0x0c | 0x2a2bbe / 0x4be52 | image 2 (test usine) : offset, taille |
| 0x10–0x1c | 0 | inutilisés |

## En-tête d'image (0x2d4 octets, big-endian)  [sûr : `Zevs::CBinHeader`]

| Offset | Type | Sens |
|---|---|---|
| 0x00 | u16 | version (0x84 = 1.32 ; 0x70 pour l'image 2) |
| 0x02 | u8 | type (doit valoir 1) |
| 0x03 | u8 | 0 |
| 0x04 | u16 | build (0x32a = 810) |
| 0x06 | u16 | **somme de l'en-tête** = `~(somme des octets de [0x08, 0x2d4)) & 0xffff` |
| 0x08 | u32 | adresse de départ (0x00640000 ; ne doit pas valoir 0xffffffff) |
| 0x0c | u32 | 0 |
| 0x10 | u32 | nombre de sections (3) |
| 0x14 | 16 × 0x2c | emplacements de section (3 utilisés) |

Les offsets de section comptent depuis le début de l'image (cet en-tête). Les sections
se suivent sans alignement, juste après l'en-tête (0x2d4).

### Ce que vérifie l'updater Mac avant d'envoyer  [sûr]
`CUpdateEngine::ParseAndDisplayFileInfo` : `CCabFile::Verify` (couples cohérents), puis
`CBinFile::Verify` sur l'image 1 : en-tête non vide, somme de l'en-tête, type 1,
adresse de départ ≠ −1, et pour chaque section : étiquette en ASCII imprimable et
somme 16 bits des octets envoyés (`~Get16` = 16 bits de poids faible de notre
checksum, compressé si la section l'est). Échec → « OS BinFile seems broken ».
Version et build sont ensuite affichés (`GetOSString`).

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

Pour un firmware modifié : recalculer ces deux sommes, les tailles, les offsets, et la
somme de l'en-tête d'image. `tools/pack_oscab.py` le fait (voir plus bas). Le programme
Mac a aussi un CRC-32 (`Zevs::CRC::CCRC32` : CRC-32
réfléchi, registre initial 0xFFFFFFFF, complément final ; `CCRC32X` rend 0 pour un
registre nul). Il sert au transport (« Message CRC error »), pas aux sections.

## Hachés de référence (charges utiles, sortie de `tools/rebuild.sh`)

```
img1_ARM0_ffff0020.bin  7554211a164a4b2aa7e9a2ee7adfbb002c621de1885ddddba9ef0935476e6cc9
img1_CODE_c0000000.bin  c29d959d9c0e9ea09c9bea733321948de9fba412b982d067081c5c19e609cc6d
img1_SRAM_80000000.bin  ada475d4618926caa6eff8905fb18ad71ef1072062214c2ad44ef18bb5c2a89a
img2_ARM0_ffff0020.bin  0c34341743c9644ce78349adb4967491d7ee399c43354f8246d2e757d59e74e8
img2_CODE_c0000000.bin  376e1b11ed8ae04bdd288787aa803ce0b7c8887a5da0c32e1a8ee5751e4dbbef
img2_SRAM_80000000.bin  d9ebae40678cb0dfe92ad578fdf520446263a422e59d7569f79c61b705947f8c
```

## Reconstruire `os.cab` : `tools/pack_oscab.py`  [vérifié hors instrument]

Remplace des sections de l'image 1 (`TAG=fichier`), recompresse, recalcule sommes,
tailles, offsets et somme d'en-tête, recopie l'image 2, puis relit le résultat comme
l'updater et le clavier (décompression complète et vérification de toutes les sommes).

- **Aller-retour sans modification** : les six sections réextraites sont identiques
  octet pour octet aux originales.
- **Compression** : Nord n'utilise ni LZO1X-1 ni LZO1X-999 tels quels (flux CODE de
  2 755 134 octets). Avec python-lzo niveau 9 (LZO1X-999) : 2 555 912 octets, fichier
  complet de 2 875 354 octets (**200 Ko de moins que l'officiel**). Sans python-lzo,
  repli sur un LZO1X-1 en Python : 2 978 357 octets (+223 Ko).
- Les flux produits sont décompressés à l'identique par la vraie liblzo2 (python3-lzo,
  conteneur jetable) et par notre décodeur.
- Non vérifié : que le programme Update du clavier accepte le fichier (palier 1 du
  prototype, `docs/faisabilite.md`).
