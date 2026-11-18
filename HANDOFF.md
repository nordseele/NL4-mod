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
- [x] **Adresses corrigées** : l'en-tête de 0x20 octets de chaque section n'est pas chargé.
  Toutes les adresses de fonctions notées avant le commit qui suit `6c7f2fb` étaient
  0x20 trop hautes (voir l'encadré de `docs/voices-midi.md`).
- [ ] Checksums CODE / ARM0 pas encore reproduits (SRAM oui).
- [~] Réception MIDI : chaîne complète jusqu'aux slots pour les contrôleurs (bend = n° 9,
  pression = n° 8), aiguillage par **masques de bits (port, canal)** par cible, donc un
  slot peut déjà écouter plusieurs canaux. Le gestionnaire Note On reste à identifier.
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
| `Unison` | 0xc01ca38c | 3 pointeurs |
| `Legato` | 0xc01c9180 | 2 pointeurs |
| `Polyphonic` | 0xc01ca2f0 | 1 pointeur |
| `Alloc State` | 0xc01bde80 | `FUN_c0027670` → `fn_c001c77c(allocateur, "Alloc State")` : affichage de debug de l'allocateur |

Contrôle de la disposition corrigée : 353 chaînes sur 364 de la zone de données sont
pointées exactement ; 3 737 entrées de tables de code sur 3 738 tombent sur un début de
fonction. Les chaînes `FFS…` désignent un système de fichiers en flash (programmes /
performances). `WaveTable Version: 05`.

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

1. Identifier le gestionnaire Note On / Note Off de l'application (abonnés de
   `fn_c0121580` au type 0xc09140bc ; candidat `fn_c011a550`, masque `+0x68`), et
   comment il passe du canal au slot puis à `note_event_handler`.
2. Suivre le contrôleur 9 (bend) dans le slot : `cible->vt[0](cible, 9, valeur, 0)` →
   mise à l'échelle par le Bend Range → hauteur des voix. C'est le point d'injection du
   bend par note. Idem pour le n° 8 (pression) et les CC (CC74).
3. Lire `midi_routing_setup` (c00dee54) en entier : quels champs portent les canaux
   global / A–D / Soft Thru, et où ajouter les canaux membres d'une zone MPE.
4. Détailler la clé de tri d'`alloc_core` (vol de voix) et la limite éventuelle par slot.
5. Trouver l'application par voix du morph de vélocité, pour y brancher Y/Z.
6. Identifier les deux destinations de `hw_write` et la cadence des mises à jour.
7. Reproduire les checksums CODE / ARM0 (piste `CCRC32X` dans le programme Mac ;
   l'en-tête de 0x20 octets d'ARM0 n'est pas nul et contient peut-être des métadonnées
   de chargement).

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
- `tools/vtables.txt` (généré par `tools/find_ptr_tables.py`) liste les tables de
  pointeurs vers du code. Depuis la correction des adresses, 3 737 entrées sur 3 738
  tombent sur un début de fonction. Une vtable C++ (ABI Itanium) se lit à `vptr` ; une
  entrée en `sub r0, r0, #N ; b …` est un relais d'ajustement de `this` (héritage
  multiple) vers la vraie méthode.
- Le MIDI passe par un **bus d'abonnement** : ne pas chercher d'appels directs entre la
  réception et les slots ; partir des types (0xc09140a8…e8) et de `midi_subscribe`.
- Le CODE décompressé est validé : la bibliothèque officielle liblzo2 (Homebrew `lzo`)
  donne exactement les mêmes octets. Elle signale « input overrun » à la fin, faute de
  marqueur de fin LZO.
- Pas de RTTI dans le firmware : pas de noms de classes, on nomme à la main dans
  `tools/symbols.txt`, puis `tools/rebuild.sh` et réimport.
- Leçon : une adresse de fonction (position dans l'image) et une adresse lue dans un pool
  de littéraux (valeur absolue) ne se vérifient pas de la même façon. Toujours contrôler
  la disposition par des statistiques globales (pointeurs vers chaînes, entrées de
  tables), pas sur quelques cas : c'est ainsi que le décalage de 0x20 a été trouvé.

## Risques

- Flasher une image modifiée peut **rendre le clavier inutilisable** si le chargeur la
  refuse ou si l'OS plante au démarrage. Aucune écriture tant qu'on ne sait pas comment
  récupérer (mode de mise à jour, réécriture du chargeur ou non).
- Droits : le firmware et les logiciels Clavia restent hors du dépôt. On ne publie que des
  notes, des formats et notre propre code (même ligne que
  [opennord](https://github.com/simonflore/opennord), `docs/LEGAL.md`).
