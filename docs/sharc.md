# Code des SHARC (ADSP-21489)

Exploration du 2026-11-18. Légende : **[sûr]** lu ; **[hyp.]** déduit.

## Où il est  [sûr]

Dans la section CODE de l'OS ARM (image 1 de `os.cab`), sous forme de **deux flux de
démarrage ADI 214xx** (format 32 bits, non compressés), un par SHARC :

| Flux | Adresse ARM | Taille | Blocs | Code VISA (INIT_L16 à 0x1C0300) | Données |
|---|---|---|---|---|---|
| 1 | 0xc03c5720 | 0x13C10 | 445 | 0x6A28 octets | blocs 0, 1, 3 (0x90000, 0xB0000, 0xE0000) |
| 2 | 0xc03d9334 | 0x13DB0 | 451 | 0x6B30 octets | idem, un peu plus en bloc 0 |

Chaque flux est suivi de sa longueur en mots de 32 bits (0x4F04, 0x4F6C). Il commence
par le noyau de démarrage ADI (256 instructions), identique octet pour octet à celui du
Prophet 12, puis des blocs ZERO_LDATA / INIT_L16 / INIT_L32, et finit par FINAL_INIT.
L'ARM les envoie au démarrage : chargeur `fn_c010cc98`, pointeurs vers les deux flux en
0xc010cddc / 0xc010cde0. Les deux programmes sont proches mais différents : rôles
distincts **[hyp. : un SHARC par moitié des voix, plus les effets sur l'un des deux]**.

Conséquence pour la sûreté : comme sur le Prophet 12, les SHARC ne gardent aucun programme
à eux ; réinstaller l'OS réinstalle aussi leur code.

## Outils

- `tools/extract_sharc.py` : extrait les deux flux (`ghidra/bin/sharc/*.ldr`, hors git),
  vérifie la chaîne de blocs et la longueur.
- Ghidra : extension `roblg/ghidra-sharc` (prise en charge annoncée des
  ADSP-21483–21489), **réutilisée telle que compilée dans le projet Prophet 12**
  (`p12RE/ghidra/projects_sharc/ext/installed/SHARC`, montée en lecture seule). Import
  sans tête dans un conteneur jetable, projet dans `ghidra/sharc_work/` (hors git) :

```sh
docker run --rm -v "$PWD/ghidra/bin/sharc":/ldr:ro -v "$PWD/ghidra/sharc_work":/work \
  -v /Users/matthiasbudde/CODE/p12RE/ghidra/projects_sharc/ext/installed/SHARC:/ghidra/Ghidra/Extensions/SHARC:ro \
  --entrypoint /ghidra/support/analyzeHeadless ghcr.io/clearbluejar/pyghidra-mcp:sha-f43400b \
  /work/proj nl4dsp -import /ldr/sharc1_c03c5720.ldr /ldr/sharc2_c03d9334.ldr \
  -loader SharcLdrLoader -overwrite -scriptPath /work/scripts -postScript Survey.java
```

Scripts dans `tools/sharc/` (à copier dans `ghidra/sharc_work/scripts/`) : `Survey.java`
(repris du projet Prophet 12), `CmdHandlers.java` (crée les 27 `dsp_cmd_NN` depuis la
table DM 0x92180), `ListAll.java` et `DumpAll.java` (désassemblage et pseudo-C complets,
argument = fichier de sortie, avec `-process <prog> -postScript …`).

Résultat de l'import : 48 et 50 fonctions, ≈ 1 900 instructions chacun, **0 erreur, 100 % des
fonctions décompilées**. La couverture est partielle (le code fait ≈ 27 Ko ; une grande
partie n'est atteinte que par interruptions ou appels indirects).

## Liaison ARM → SHARC  [sûr sauf mention]

**Côté ARM.** `hw_write(dsp, mot1, mot2)` (c014f0d0) écrit deux mots de 32 bits dans un
port mappé sur le bus EMIFA de l'AM1705, avec contrôle de flux par GPIO. Table des ports
(c0402668) : jusqu'à 4 ports en **0x62000000 / +4 / +8 / +C** (EMIFA CS3), deux utilisés
(un par SHARC). Une logique de liaison sur la carte **[hyp.]** les sérialise vers le SHARC.
Les voix alternent entre les deux SHARC : `dsp = numéro matériel & 1`, 10 voix chacun.

**Côté SHARC.** La routine audio (`FUN_sw_001c25fb`, appelée à chaque bloc) commence par
vider un **tampon circulaire de paires de mots**, rempli par DMA chaînée depuis un port
série SPORT (registres DMA 0xC40–0xC4F, pointeur courant lu en 0x2400 **[hyp.]**) :

```
mot 1 = [commande : 8 bits | adresse : 24 bits]      mot 2 = valeur
commande 0      : DM[adresse] = valeur               (écriture directe)
commande 1..26  : appel de la table DM 0x92180       (identique sur les deux SHARC)
```

Les 27 commandes sont des **primitives d'accès mémoire**, pas des commandes de synthèse :
écritures à I7 / I7+1, relectures renvoyées par SPI (TXSPI 0x1003), réglage des
pointeurs I7 / M7, écriture en flux `DM(I7, M7) = valeur` (cmd 18, 19), relance du DMA
de réception (cmd 22), transfert DMA mémoire (cmd 25). L'interruption SPI (VEC_P1I)
sert à la relecture : elle reçoit une adresse et renvoie son contenu.

**Conséquence : le SHARC est un moteur « bête » dont l'ARM écrit directement les
paramètres en mémoire.** Chaque paramètre de voix est une case mémoire du SHARC
(adresse = base + voix × pas, par ex. la hauteur : `voix × 8 + base`).

**Lissage.** Juste après, la routine audio rapproche chaque paramètre de sa cible
(`courant += coef × (cible − courant)`, cible en 0x921A4…, courant en 0xE1E00…, par
groupes). Des changements continus et fréquents ne feront donc pas de clics.

## Ce que ça change pour le MPE

- **Rien à modifier côté SHARC.** Y / Z par voix = l'ARM écrit, pour une seule voix,
  des valeurs qu'il écrit déjà aujourd'hui pour toutes les voix d'un slot ; le SHARC
  les applique et les lisse.
- Pas d'équivalent de la commande 0x1F6 du Prophet 12 à trouver : tout passe par des
  écritures mémoire. Une piste plus légère que `voice_apply_velocity` existe donc :
  écrire directement, pour une voix, la ou les adresses SHARC des destinations
  voulues (par ex. la coupure du filtre). À cartographier : adresse SHARC de chaque
  paramètre de voix (appels de `hw_write`, ~285).

## À explorer, si utile au MPE

1. ~~Protocole ARM → SHARC~~ : fait (section « Liaison »).
2. ~~Lissage~~ : oui, par bloc, côté SHARC.
3. ~~Entrée de modulation par voix~~ : pas besoin, écritures mémoire directes.
4. Carte des adresses SHARC des paramètres de voix (depuis les appels de `hw_write`).
5. Rôle des deux programmes (différence de ≈ 0x100 octets de code) et coût CPU par bloc.
