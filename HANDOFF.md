# HANDOFF — état du projet NL4 MPE

Dernière mise à jour : 2026-11-18.

## Objectif

MPE complet sur le Nord Lead 4 : X = pitch bend par note (±48 demi-tons), Y = timbre
(CC74), Z = pression (channel pressure par canal membre). Il faut d'abord comprendre
l'allocation des voix et les modes Performance / slots, puis décider à quel niveau
greffer le MPE.

## Où on en est

- [x] `os.cab` décodé : table des sections, compression LZO1X (`docs/oscab-format.md`).
- [x] OS v1.32 complet décompressé (4,2 Mo de code ARM) et chargé dans Ghidra.
- [x] La 2ᵉ image est identifiée : un firmware de test usine.
- [ ] Checksums CODE / ARM0 pas encore reproduits (SRAM oui).
- [~] Réception MIDI : parseur trouvé, il transmet Poly AT, Channel Pressure et Pitch Bend
  avec le canal. Le récepteur du Lead 4 (aiguillage canal → slot) reste à trouver.
- [~] Voix : 4 slots + réservoir global de 20 voix, réservoir de 64 notes, vol de voix
  par priorité, hauteur calculée et écrite voix par voix. **Une note est identifiée par
  (slot, numéro de note), sans le canal** : c'est la première chose à changer pour le MPE.
- [ ] Où tourne la synthèse : indices de deux destinations matérielles (`hw_write`).

Détail : **`docs/voices-midi.md`**. Noms des fonctions : `tools/symbols.txt`.

## Objectif MPE retenu (2026-11-18)

Pas le « MPE léger » à 4 slots (déjà testé, pas le but). Visé : le plus de notes MPE
possible (accords de 8 notes et plus), chaque note indépendante (X/Y/Z). Contrôleurs :
Expressive E Osmose et LinnStrument. Idéal : une zone MPE par slot, et/ou une zone au
niveau de la Performance avec bascule automatique quand le clavier est en mode
Performance.

## Environnement

- Conteneur `pyghidra-nl4` (port 8003), projet `ghidra/nl4_ghidra.gpr`, programme
  `/nl4_os132_full.elf-<suffixe>` (le suffixe change à chaque import :
  `list_project_binaries`). Serveur MCP déclaré
  dans `.mcp.json`. Les autres conteneurs pyghidra (octalab, p12, sharc) appartiennent à
  d'autres projets : **ne pas y toucher**.
- Ghidra a choisi `ARM:LE:32:v8`. Le vrai cœur est un ARM926 (v5TE). Sans effet visible
  jusqu'ici.
- La fiche de métadonnées de pyghidra-mcp affiche « 0 instruction / Analyzed false »,
  mais l'analyse a bien tourné : des milliers de fonctions `FUN_c0…`.
- Le manuel en texte : `vendor/manual.txt` (généré par pdftotext).

## Ce que dit le manuel (v1.x, 2013)

- **20 voix au total**, partagées entre les 4 slots (A–D). L'unisson et le Chord Memory
  réduisent la polyphonie.
- **Performance** = 4 programmes (un par slot), en layer ou split (A+B à gauche, C+D à
  droite), 99 emplacements.
- **Canal MIDI par slot** (A, b, c, d : 1–16 / Off) + canal global. Un slot affecté à un
  canal joue même s'il n'est pas actif sur le panneau.
- **Bend Range par programme** : 1–12, 24, 48, et asymétriques −12/−24 (2 vers le bas).
  Le ±48 du MPE existe donc déjà.
- **Voice Mode** par programme : Poly, Mono, Legato, Unison (plusieurs niveaux), Glide.
- **Sources de morph** : molette / pédale d'expression, vélocité, 3 boutons Impulse.
  Le clavier n'a pas d'aftertouch. Pourtant la chaîne `AfterTouch` existe dans le
  firmware : à vérifier si la pression MIDI entrante est reçue et à quoi elle sert.
- Le menu MIDI a un « Pitch Bend Mode » (Sr / r / S / Off).

## Pistes dans le firmware

| Chaîne | Adresse | Référencée depuis |
|---|---|---|
| `Unison` | 0xc01ca3ac | table en 0xc01ca0fc / 0xc01ca10c |
| `Legato` | 0xc01c91a0 | 0xc04050b4 |
| `Polyphonic` | 0xc01ca310 | aucun pointeur direct trouvé |
| ~~`Alloc State`~~ | 0xc01bdea0 | faux ami : table numérique (voir Méthode) |

Autres repères : des fonctions très appelées (`FUN_c014f260`, 1 560 appels ; `FUN_c0181b44`,
920) sont probablement des utilitaires (memcpy, printf…). Les chaînes `FFS…` désignent un
système de fichiers en flash (programmes / performances). `WaveTable Version: 05`.

## Bootloader

Il n'est **pas** dans `os.cab`.
- L'image 2 est un programme de **test usine / service** : « LCD Test », « MIDI Test »,
  « Check LEDs », « Serial Number », identifiants de flash SPI (Micron N25Q032,
  SST 25VF032/26VF032). Elle tourne aux mêmes adresses que l'OS.
- Le démarrage passe très probablement par la ROM de l'OMAP-L138 (chargement d'une image
  AIS depuis la flash SPI), puis par un 1er étage Clavia dans la flash, absent de la mise
  à jour.
- Question clé pour la sûreté : la mise à jour réécrit-elle seulement la zone OS (le
  chargeur restant intact, donc récupérable), et le chargeur vérifie-t-il le checksum
  avant de lancer l'OS ?

## À quel niveau mettre le MPE (hypothèses, à vérifier dans le code)

1. **Sans toucher au firmware (« MPE léger », 4 voix).** Mettre le même programme dans
   les 4 slots, en Mono, sur les canaux 2–5, Bend Range 48. Puis régler le contrôleur MPE
   sur 4 canaux membres. On obtient du pitch bend par note sur 4 notes. Y/Z seulement si
   un CC reçu par slot pilote le morph molette/pédale. **Testable dès maintenant, sans
   risque.** C'est aussi un bon banc d'essai pour vérifier le comportement MIDI réel.
2. **Une « zone MPE » au niveau d'un slot.** Un slot reçoit le canal maître + les canaux
   membres. Chaque note prend une voix du réservoir de 20, et le bend / pression / CC74
   d'un canal membre ne s'applique qu'à la voix de cette note. Ça colle au modèle MPE (une
   zone = un timbre). Il faut :
   - une allocation qui mémorise le canal d'origine de chaque voix ;
   - un pitch bend par voix (sans doute déjà là : désaccord d'unisson, glide) ;
   - une modulation continue par voix pour Y/Z. Le morph de vélocité est déjà par voix,
     mais figé à l'attaque : piste à creuser.
3. **Au niveau de la Performance** (2 zones MPE haute et basse ↔ split A+B / C+D) :
   extension possible de l'option 2, plus tard.

Questions bloquantes pour 2 et 3 : la structure d'une voix, et l'endroit où la synthèse
calcule les paramètres par voix (et à quelle cadence).

## Prochaines étapes

1. Trouver le récepteur MIDI du Lead 4 (qui écrit `parser+0`), puis l'aiguillage
   canal → slot et le traitement de 0xA0 / 0xD0 / 0xE0 / CC74. Pistes : les appelants
   de `slot_controller_in` et de `slot_notes_update`, et le port DIN (`fn_c014c5b0`).
2. Détailler la clé de tri d'`alloc_core` (politique exacte du vol de voix) et la limite
   éventuelle de voix par slot.
3. Trouver où le pitch bend reçu est mis à l'échelle (Bend Range) et ajouté à la hauteur
   des voix : c'est le point d'injection du bend par note.
4. Trouver l'application par voix du morph de vélocité, pour y brancher Y/Z.
5. Identifier les deux destinations de `hw_write` et la cadence des mises à jour.
6. Reproduire les checksums CODE / ARM0 (piste `CCRC32X` dans le programme Mac).

## Méthode de travail qui marche

- Ghidra (serveur MCP) pour les renommages et les vérifications ponctuelles. Pour
  chercher en masse, utiliser `ghidra/bin/decomp.c` (≈ 5 400 fonctions en pseudo-C) avec
  grep / Python. C'est la référence de qualité : `tools/dump_decomp.py` désactive
  l'analyseur « Non-Returning Functions - Discovered ». Le serveur MCP, lui, garde
  l'analyse par défaut.
- Pourquoi cette option : `operator_new` appelle la routine qui lève `bad_alloc`, Ghidra
  en déduit qu'`operator_new` ne revient jamais, et cesse de désassembler après chaque
  `new` (des centaines de fonctions tronquées, « Subroutine does not return »).
- Débuts de fonctions (`tools/funcs_seed.txt`, généré par `tools/find_func_starts.py`) :
  cibles de `bl`, entrées de tables de pointeurs, et `push {…, lr}` **seulement** après
  un retour ou un saut. Un `push` en 2ᵉ position (`operator_new` commence par
  `cmp r0, #0`) ne doit pas devenir un début : il coupe la fonction en deux.
- `tools/vtables.txt` liste des **tables de pointeurs vers du code**, pas toutes de vraies
  vtables : environ un tiers seulement des entrées tombent sur un début de fonction.
  Certaines pointent sur les `blx` de petites fonctions de relais. À utiliser avec
  prudence.
- Le CODE décompressé est validé : la bibliothèque officielle liblzo2 (Homebrew `lzo`)
  donne exactement les mêmes octets. Elle signale « input overrun » à la fin, faute de
  marqueur de fin LZO.
- Pas de RTTI dans le firmware : pas de noms de classes, on nomme à la main dans
  `tools/symbols.txt`, puis `tools/rebuild.sh` et réimport.
- Attention aux faux amis : `Alloc State` en 0xc01bdea0 n'est pas une chaîne, c'est une
  table numérique de la conversion hauteur → fréquence.

## Risques

- Flasher une image modifiée peut **rendre le clavier inutilisable** si le chargeur la
  refuse ou si l'OS plante au démarrage. Aucune écriture tant qu'on ne sait pas comment
  récupérer (mode de mise à jour, réécriture du chargeur ou non).
- Droits : le firmware et les logiciels Clavia restent hors du dépôt. On ne publie que des
  notes, des formats et notre propre code (même ligne que
  [opennord](https://github.com/simonflore/opennord), `docs/LEGAL.md`).
