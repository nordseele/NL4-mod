# HANDOFF — état du projet NL4 MPE

Dernière mise à jour : 2026-11-18 (fin de session, commit `0b217da` et suivant).

## Reprise dans une nouvelle conversation

1. Lire ce fichier, puis `docs/voices-midi.md` (notes de recherche détaillées).
2. Vérifier que le conteneur tourne : `docker ps --filter name=pyghidra-nl4` (sinon
   `docker start pyghidra-nl4`). Les outils MCP `pyghidra-nl4` se chargent au démarrage
   de la session (`.mcp.json`).
3. **Réimporter l'ELF dans Ghidra** : le programme du serveur date d'avant les derniers
   noms. `list_project_binaries`, `delete_project_binary` sur l'ancien, puis
   `import_binary /projects/bin/nl4_os132_full.elf`.
4. Si `ghidra/bin/` est vide ou douteux : `tools/rebuild.sh`, puis régénérer le pseudo-C
   (commande en tête de `tools/dump_decomp.py`, ≈ 5 min, en arrière-plan). Contrôle de
   qualité : `grep -c 'Subroutine does not return' ghidra/bin/decomp.c` doit donner 0.
5. Reprendre au **plan**, étape 1 (section « Plan » plus bas).

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
  slot peut déjà écouter plusieurs canaux. Notes : chemin connu jusqu'au **Note On du
  slot** (`slot_note_on`), avec **une zone par couple (port, canal)** et une table de
  128 notes par zone dans les cibles. Reste le lien `slot_note_on` → gestionnaire de voix.
- [~] Voix : 4 slots + réservoir global de 20 voix, réservoir de 64 notes, vol de voix
  par priorité, hauteur calculée et écrite voix par voix. **Une note est identifiée par
  (slot, numéro de note), sans le canal** : c'est la première chose à changer pour le MPE.
- [ ] Où tourne la synthèse : indices de deux destinations matérielles (`hw_write`).
- [x] **Chemin du bend** (2026-11-18) : bend MIDI → paramètre 0x23 du slot → objet bend
  du moteur du slot (`engine+0x28C`), lissé sur 32 ticks → lu par chaque voix dans
  `voice_pitch_offset`, à côté du glide propre à la voix. **Courbe non linéaire
  au-delà de 2 demi-tons** (linéaire puis parabolique) : le MPE à ±48 demandera sa propre
  échelle. Bend Range = paramètres moteur 0x21 (les deux sens) / 0x22 (vers le bas). Le
  pitch stick du panneau : chemin non trouvé, à tester sur l'instrument.

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
- Deux focus : **Keyboard Focus** (slots joués par le clavier, LED allumée) et **Panel
  Focus** (un seul slot, LED clignotante, édité par le panneau). L'utilisateur pense que
  le pitch stick n'agit que sur le slot actif hors Performance : **à vérifier sur
  l'instrument**.
- **Sources de morph** : molette / pédale d'expression, vélocité, 3 boutons Impulse.
  Le clavier n'a pas de capteur d'aftertouch, mais la charte MIDI (p. 47) indique
  Channel Aftertouch **transmis et reconnu** (Poly AT non). Dans le code, la pression
  reçue devient le contrôleur interne n° 8 du slot ; ce qu'elle module reste à trouver.
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

## À quel niveau mettre le MPE

Retenu : **une zone MPE par slot**, et idéalement une zone au niveau de la Performance
avec bascule automatique. Le « MPE léger » à 4 slots est écarté (déjà testé, pas le but).

Ce que le code permet déjà, ou impose :
- **Aiguillage** : masques de bits (port, canal) par cible → une zone = ajouter les
  canaux membres 2–16 au masque du slot (`midi_routing_setup`, c00dee54).
- **Cibles** : une zone par couple (port, canal), avec sa table de 128 notes → pas de
  collision entre canaux à ce niveau si chaque canal membre est une zone.
- **Obstacle 1** : plus loin, une note est identifiée par (slot, numéro de note), dans
  l'allocateur et dans le tableau de touches du slot → y ajouter le canal.
- **Obstacle 2** : bend (contrôleur 9) et pression (n° 8) sont mémorisés **par slot** →
  les rendre par note / par voix.
- **Piste Y/Z** : le morph de vélocité est calculé au Note On, au niveau du slot
  (`slot_note_on`) → à rendre continu et par voix.
- Le pitch est déjà calculé et écrit **voix par voix** par l'ARM (`voice_pitch_*`).

## Plan (validé avec l'utilisateur le 2026-11-18)

**Étape 1 — finir la cartographie (analyse, sans risque).** Ordre conseillé :
1. ~~Chemin du bend~~ : fait (`docs/voices-midi.md`, « Chemin du pitch bend »). Reste
   le pitch stick du panneau : un test sur l'instrument suffit.
2. **Note On du slot → voix** : `slot_note_on` (c000f044) → objet `slot+0x20`
   (`fn_c0012e0c`, 0x88 octets, qui pointe vers l'objet `fn_c0013344` de 0x460 octets)
   → file d'événements → `note_event_handler` / `alloc_core`.
3. **Pression (n° 8) et CC74** : la pression pilote le paramètre 0x29 du slot à la
   place de la molette quand `slot+0x260 == 2`. Reste ce qu'est 0x29 dans le moteur
   (méthode c0023e48), le CC74, et le chemin par voix du morph de vélocité.
4. Annexes : `midi_routing_setup` en entier (champs des canaux global / A–D / Soft Thru),
   bits de la clé de vol de voix, destinations de `hw_write` et cadence des mises à jour.

**Étape 2 — verdict de faisabilité.** Note de conception : modifications nécessaires,
fonctions touchées, niveau (slot / Performance), ce qui est simple, risqué ou impossible
(ex. si le moteur n'accepte pas de modulation continue par voix). Décision de l'utilisateur
de continuer ou non.

**Étape 3 — sécurité avant toute écriture (bloquant).**
- Reproduire les checksums CODE / ARM0 (piste `CCRC32X` du programme Mac ; l'en-tête
  d'ARM0 contient des métadonnées).
- Comprendre la mise à jour : protocole `CITProtocol` du programme Mac, zones de flash
  réécrites.
- Voie de récupération : ouvrir le clavier (comme fait sur le Prophet 12), repérer la
  flash SPI, **sauvegarder la flash complète au programmateur avant tout essai**.

**Étape 4 — prototype progressif (seulement après l'étape 3).** Plus petit patch
observable d'abord (un slot qui écoute plusieurs canaux), puis canal dans la clé, bend
par voix, pression, timbre. Tests avec l'Osmose et le LinnStrument.

## Méthode de travail qui marche

- Ghidra (serveur MCP) pour les renommages et les vérifications ponctuelles. Pour
  chercher en masse, utiliser `ghidra/bin/decomp.c` (≈ 5 000 fonctions en pseudo-C) avec
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
- **Fonctions absentes du pseudo-C** : les méthodes des tables de paramètres
  (`engine_param_handler`, `voice_param_handler`) ne sont atteintes que par des pointeurs
  rangés dans des pools de littéraux, ou par un `b` final. Les graines ne les trouvent
  pas : il faut les nommer à la main dans `tools/symbols.txt`. Pour lire une méthode,
  prendre le n° de paramètre → la valeur du pool (`DAT_…`) → `disassemble` sur le serveur.
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
