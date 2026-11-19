# HANDOFF — état du projet NL4 MPE

Dernière mise à jour : 2026-11-19.

## Reprise dans une nouvelle conversation

**Situation** : paliers 1 à 3 **essayés et réussis** sur l'instrument le 2026-11-19
(bend par note ±48 sur les canaux 2 à 16 ; `docs/patches.md`, « Résultats des essais »).
**Palier 4 essayé le 2026-11-19, semble marcher** (Y par note ; réglage du morph Velocity
pénible, voir « Ergonomie de Y » dans `docs/patches.md`) : Y (CC74) des canaux 2 à 16 →
`voice_apply_velocity` dans `synth_tick` (`build/palier4_os.app`, `docs/patches.md`).
**Palier 5** : Y → morph Wheel par voix (la vélocité reste celle de la note). 1ʳᵉ version
essayée : stable, mais Y sans effet ; 2ᵉ version (quantités Wheel lues dans le modèle
de paramètres du slot) : stable, Y toujours sans effet. Diagnostic : aucun effet, ce qui a mené à la
**vraie cause** : les CC passent par un relais de sous-objet (`0xc01202a4`) qui saute
directement à `midi_cc_in` ; le CC74 n'a jamais atteint notre code (paliers 4 et 5).
**3ᵉ version (relais branché) essayée le 2026-11-19 : ça marche**, Y agit comme un morph
Wheel par note, mais Y à 127 reste en dessous de la molette à fond, et la modulation va par paliers audibles.
**Palier 6 essayé** : Z semble marcher (à mettre en option), échelle de Y correcte, mais
artefacts insupportables (Y continu → recalcul complet de la voix à chaque pas).
**Palier 7 essayé le 2026-11-19 : artefacts disparus** (`build/palier7_os.app`) : Y n'applique
plus que les paramètres morphés, un par un, comme la molette. Reste à départager : Y à 127
semble encore un peu en dessous de la molette à fond (contrôleur ou échelle).
Z → Level décevant au palier 7. **Palier 8 essayé : semble fonctionner, mais décevant ; on
s'arrête là** (Z → Wheel / Velocity en option du menu). Même note sur deux canaux : la plus
récente vole le bend de l'autre. **Reprise (nouvelle conversation, 2026-11-19)** : palier 9, 2ᵉ version, **essayé : OK** (même hauteur
sur deux canaux, plus de notes bloquées) ; continuer l'étude du menu MIDI depuis `docs/menus.md` : trouver la liste des
entrées, la navigation, la sauvegarde des réglages. Palier 9 et `docs/menus.md` pas encore
commités.
**Palier 9** (`build/palier9_os.app`) : même hauteur sur
plusieurs canaux par renumérotation de la note (`docs/patches.md`, « Palier 9 en détail »).
Palier 8 (`build/palier8_os.app`) : Poly AT accepté, courbe Z², Z remplace la vélocité pour le
volume, Z = 0 retardé de 3 ticks (relâche). Ensuite : étude du menu MIDI (lecture seule, en cours : `docs/menus.md`),
puis RPN 6 / RPN 0. Note de transfert pour un projet Nord Stage 2 : `docs/pour-nord-stage-2.md`.
**Options voulues dans le menu MIDI** (décision de l'utilisateur, 2026-11-19) : destination
de Y au choix Velocity, Wheel ou Cutoff direct ; même choix pour Z, plus Level. Toutes
passent par le chemin paramètre par paramètre du palier 7. Aussi : courbes de réponse au choix
pour Y et Z ; Z remplace ou multiplie la vélocité ; plage de bend réglable ; canaux A–D
ignorés automatiquement en mode MPE. Palier 6 : Z (pression) → Level par
note (gain d'ampli renvoyé au SHARC), Y et Z lissés, quantités Wheel sur 16 bits, variables
déplacées au début du tas (`docs/patches.md`, « Palier 6 en détail »). Pendant les essais : canaux A–D sur Off
(sinon collision avec les canaux membres). L'utilisateur préfère les essais à la main
(`tools/mpe_test.py` existe). Ensuite : les options du menu MIDI (MPE Off / zone, Z → Level en option). Tableau de reprise
d'origine :

| Résultat | Suite |
|---|---|
| L'updater re-signé ne se lance pas | regarder le message macOS ; essayer `xattr -cr` / signature ad hoc à la main, ou remplacer `os.cab` dans l'app officielle copiée |
| Le clavier refuse le fichier (palier 1) | relire `CBinFile::Verify` côté Mac et le programme Update (inconnu) ; comparer avec `os.cab` officiel |
| Palier 2 : les notes des canaux 2–16 ne jouent pas | les notes dépendent sans doute aussi des masques (`fn_c011c344` sur `+0x53C` et `+0x170+4i`, comme dans `midi_routing_setup`) : les ajouter |
| Palier 2/3 : plantage au démarrage | mémoire (36 zones par cible) : baisser à 20 ou n'ajouter les membres que sur un port ; récupérer par Shift + Store + OS officiel |
| Palier 3 marche | palier 4 : Y (CC74) → entrée vélocité de la voix (`voice_apply_velocity`, `midi_cc_in`), puis Z (pression, `midi_pressure_in`) |

Mise en route technique :
1. Lire ce fichier, `docs/patches.md`, `docs/faisabilite.md`, puis `docs/voices-midi.md`.
2. Conteneur Ghidra : `docker ps --filter name=pyghidra-nl4` (sinon `docker start
   pyghidra-nl4`). L'ELF importé porte tous les noms de `tools/symbols.txt` (99 noms).
3. Image de compilation des patchs : `docker build -t nl4-arm tools/patch` si elle
   manque. Construire : `docker run --rm -v "$PWD":/w nl4-arm python3 -I
   tools/patch/build.py palier3`, puis `tools/patch/make_updater.sh build/palier3_os.cab`.
4. Si `ghidra/bin/` est vide : `tools/rebuild.sh`, puis le pseudo-C (commande en tête de
   `tools/dump_decomp.py`, en arrière-plan) ; contrôle : 0 « Subroutine does not
   return ».
5. Programmes SHARC : `tools/extract_sharc.py` et `docs/sharc.md` (projet Ghidra jetable
   dans `ghidra/sharc_work/`, extension compilée dans le projet Prophet 12).

**Activation du MPE dans les paliers 2–3** : uniquement par **canal MIDI global = 1**
(pas par un message du contrôleur). Rustine de prototype : à remplacer par une entrée du
menu MIDI (« MPE : Off / zone basse / zone haute »), le message de configuration MPE
(RPN 6) pouvant s'y ajouter en confort, jamais en dépendance. Le système de menus reste à
lire (piste : descripteurs de menu comme `fn_c010885c`, « Velocity Morph » / « Wheel
Morph »).

**Décisions prises** : prototype avec Y sur Velocity d'abord ; sources Y/Z distinctes
plus tard (piste Impulse 6/7, `docs/faisabilite.md`) ; ensuite fonctions d'aide à la
conversion d'un programme ; idée d'éditeur de programmes à étudier après le prototype
(piste : contribuer le Lead 4 à OpenNord). Sauvegarde matérielle de la flash
abandonnée (U38 vide, `docs/hardware.md`).

## Objectif

MPE complet sur le Nord Lead 4 : X = pitch bend par note (±48 demi-tons), Y = timbre
(CC74), Z = pression (channel pressure par canal membre). Il faut d'abord comprendre
l'allocation des voix et les modes Performance / slots, puis décider à quel niveau
greffer le MPE.

## Où on en est

- [x] `os.cab` décodé : table des sections, compression LZO1X (`docs/oscab-format.md`).
- [x] OS v1.32 complet décompressé (4,2 Mo de code ARM) et chargé dans Ghidra.
- [x] La 2ᵉ image est identifiée : un firmware de test usine.
- [x] **Adresses corrigées** : toutes les adresses de fonctions notées avant le commit
  qui suit `6c7f2fb` étaient 0x20 trop hautes (voir l'encadré de `docs/voices-midi.md`).
  Explication complète le 2026-11-18 : les offsets des sections comptent depuis l'en-tête
  de l'image, pas depuis le préambule. Le prétendu « en-tête non chargé » était la fin de
  la section précédente (`docs/oscab-format.md`). Les adresses restent bonnes ; chaque
  section a récupéré ses 0x20 derniers octets.
- [x] **Checksums des 6 sections reproduits** (2026-11-18) : `~somme des octets`, sur la
  section et sur le flux compressé. `tools/unpack_oscab.py` les vérifie à chaque
  extraction.
- [x] **Protocole de mise à jour lu** dans le programme Mac (`docs/update-protocol.md`) :
  4 programmes sur le clavier (OS, TP, Update, Boot). Update et Boot ne sont pas dans
  `os.cab`, donc vraisemblablement jamais réécrits.
- [~] Réception MIDI : chaîne complète jusqu'aux slots pour les contrôleurs (bend = n° 9,
  pression = n° 8), aiguillage par **masques de bits (port, canal)** par cible, donc un
  slot peut déjà écouter plusieurs canaux. Notes : chemin connu jusqu'au **Note On du
  slot** (`slot_note_on`), avec **une zone par couple (port, canal)** et une table de
  128 notes par zone dans les cibles. Reste le lien `slot_note_on` → gestionnaire de voix.
- [~] Voix : 4 slots + réservoir global de 20 voix, réservoir de 64 notes, vol de voix
  par priorité, hauteur calculée et écrite voix par voix. **Une note est identifiée par
  (slot, numéro de note), sans le canal** : c'est la première chose à changer pour le MPE.
- [x] Où tourne la synthèse : deux SHARC ADSP-21489, 10 voix chacun ; l'ARM écrit
  leurs paramètres en mémoire par `hw_write` (`docs/sharc.md`).
- [x] **Chemin du bend** (2026-11-18) : bend MIDI → paramètre 0x23 du slot → objet bend
  du moteur du slot (`engine+0x28C`), lissé sur 32 ticks → lu par chaque voix dans
  `voice_pitch_offset`, à côté du glide propre à la voix. **Courbe non linéaire
  au-delà de 2 demi-tons** (linéaire puis parabolique) : le MPE à ±48 demandera sa propre
  échelle. Bend Range = paramètres moteur 0x21 (les deux sens) / 0x22 (vers le bas). Le
  pitch stick du panneau : chemin non trouvé, à tester sur l'instrument.
- [x] **Note On du slot → allocateur** (2026-11-18) : le canal disparaît dès l'appel au
  slot (paires {note, vélocité}). Chaîne : filtre de destinations → arpégiateur →
  sortie du slot → file d'événements {type, slot, note} → gestionnaire de notes (patron
  visiteur, 6 types). Table des notes = arbre clé `note | slot << 8`. Piste MPE : note
  étendue `note + 128 × canal` dès `target_note_on`, clé de l'arbre élargie, hauteur
  masquée. `note_off_release_voices` était mal nommé (c'est l'allocation au Note On).

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
- Le programme Mac de mise à jour est aussi dans le projet Ghidra
  (`/nordosupdate_x86_64-<suffixe>`, tranche x86_64 extraite par `lipo`, voir
  `docs/update-protocol.md`).
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
- Le processeur est un **AM1705** (famille OMAP-L137, ARM seul), avec deux SHARC
  ADSP-21489 pour l'audio et une flash SPI Micron N25Q032 (U38). Voir `docs/hardware.md`.
- Le démarrage passe très probablement par la ROM de l'AM1705 (chargement d'une image
  AIS depuis la flash SPI), puis par un 1er étage Clavia dans la flash, absent de la mise
  à jour.
- Le chargeur (mode 5, Boot) et le programme de mise à jour (mode 4, Update) ne sont
  pas dans `os.cab` (`docs/update-protocol.md`).
- **Mode Update sans OS : confirmé** sur l'instrument (Shift + Store à l'allumage →
  « RDY », reconnu par Nord OS Update).

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
- **Piste Y/Z** : le morph de vélocité est calculé **par voix** (`voice_morph_eval`) à
  partir de la vélocité de la voix → faire varier cette entrée en continu (CC74 / pression
  du canal) et recalculer la voix.
- Le pitch est déjà calculé et écrit **voix par voix** par l'ARM (`voice_pitch_*`).

## SHARC (exploration du 2026-11-18, `docs/sharc.md`)

Deux programmes SHARC dans l'OS ARM (0xc03c5720, 0xc03d9334), extraits par
`tools/extract_sharc.py`, ouverts avec l'extension compilée du projet Prophet 12. Le
SHARC est un moteur dont l'ARM écrit les paramètres en mémoire (paires
[cmd|adresse, valeur] par `hw_write`), lissés à chaque bloc : **rien à modifier côté
SHARC pour le MPE**.

## Plan (validé avec l'utilisateur le 2026-11-18)

**Étape 1 — finir la cartographie (analyse, sans risque).** Ordre conseillé :
1. ~~Chemin du bend~~ : fait (`docs/voices-midi.md`, « Chemin du pitch bend »). Reste
   le pitch stick du panneau : un test sur l'instrument suffit.
2. ~~Note On du slot → voix~~ : fait (`docs/voices-midi.md`, « Du slot à
   l'allocateur »). Reste : le rôle exact des deux chemins d'allocation (`alloc_pick`
   au type 1, `alloc_core` au type 2).
3. ~~Pression et morph~~ : fait (`docs/voices-midi.md`, « Molette, pression et morph par
   voix »). La pression est du code mort dans l'OS 1.32 ; le morph molette est global au
   slot ; **le morph de vélocité est calculé voix par voix** (`voice_morph_eval`), avec la
   vélocité comme entrée par voix : c'est le point d'entrée retenu pour Y / Z. L'entrée
   est écrite au Note On par `voice_apply_velocity` (c0032098), la fonction à rappeler
   en continu. Le CC74 s'intercepte dans `midi_cc_in` (c011ffc4), qui connaît le canal.
   Assignation prévue : Y → source de morph Velocity, Z → source Wheel (par voix, à
   étudier). Reste : comment le morph Wheel atteint les voix, fréquence de `synth_tick`.
4. Annexes : `midi_routing_setup` en entier (champs des canaux global / A–D / Soft Thru),
   bits de la clé de vol de voix, destinations de `hw_write` et cadence des mises à jour.

**Étape 2 — verdict de faisabilité : rédigé (`docs/faisabilite.md`), décision de
l'utilisateur en attente.** Verdict : faisable par un patch ARM seul. Note de conception : modifications nécessaires,
fonctions touchées, niveau (slot / Performance), ce qui est simple, risqué ou impossible
(ex. si le moteur n'accepte pas de modulation continue par voix). Décision de l'utilisateur
de continuer ou non.

**Étape 3 — sécurité avant toute écriture : faite (2026-11-18).**
- ~~Reproduire les checksums~~ : fait.
- ~~Comprendre la mise à jour~~ : fait côté Mac (`docs/update-protocol.md`). Reste à lire
  la vérification du fichier (« OS BinFile seems broken »).
- ~~Entrer en mode Update sans l'OS~~ : Shift + Store à l'allumage, confirmé.
- ~~Sauvegarde de la flash~~ : abandonnée. U38 (N25Q032, connecteur P5) a été lue
  proprement mais elle est **vide** ; le firmware est dans une autre mémoire, non
  accessible sans démonter la carte (`docs/hardware.md`). Règle de `CLAUDE.md` mise à
  jour avec l'accord de l'utilisateur.
- Piste sans matériel : lire le pilote du système de fichiers « FFS » de l'OS pour
  savoir sur quel bus est la mémoire du firmware.

**Préparé pour l'étape 4 (2026-11-18)** : `tools/pack_oscab.py` reconstruit un `os.cab`
valide (aller-retour identique, vérification de l'updater reproduite) ; notre code ira
dans la section SRAM agrandie (`docs/faisabilite.md`, « Où loger notre code »).
Reste à savoir comment donner le fichier à l'updater : remplacer
`Contents/Resources/os.cab` dans une copie de l'application (signature à refaire en
ad hoc si macOS refuse) **[à tester]**.

**Prêts à essayer (2026-11-18)** : paliers 0 à 3 (`docs/patches.md`). Le palier 2 fait
écouter les canaux 2 à 16 au slot en Keyboard Focus quand le canal global vaut 1 ; le
palier 3 y ajoute le bend par note ±48. **Essayés le 2026-11-19 : tout marche**
(updater re-signé, recompression, notes 2–16, bend par note). Quitter l'updater après
chaque mise à jour.

**Étape 4 — prototype progressif (seulement après l'étape 3).** Avant le premier OS
modifié : répéter la procédure en réinstallant l'OS 1.32 officiel depuis le mode
Shift + Store, et garder ce fichier prêt pour revenir en arrière. Puis le plus petit patch
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
- **Leçon (2026-11-19)** : remplacer un pointeur de vtable ne suffit pas. Un objet à
  plusieurs sous-objets est appelé par la vtable **du sous-objet**, souvent un relais
  `sub r0, r0, #N ; b méthode` qui saute directement. Chercher tous les chemins vers la
  méthode (pointeurs **et** `b` / `bl`) avant de choisir où brancher.
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

## Idées pour après le MPE (proposées par l'utilisateur, 2026-11-18)

Priorités de l'utilisateur : **les fonctions d'aide (conversion d'un programme en MPE)
avant tout** ; **des sources de modulation Y / Z distinctes de Velocity** l'intéressent ;
les nouvelles tables d'ondes ne sont qu'un exemple, pas un objectif (le synthé est déjà
complet).


- **Fonction « convertir pour le MPE »** à la manière du Mutator (`docs/faisabilite.md`).
- **Nouvelles tables d'ondes.** Repérage rapide **[hyp.]** : les tables sont côté ARM,
  bloc de données à haute entropie de 0xc01d0000 à ~0xc03bd000 (≈ 1,9 Mo pour 128
  tables, ≈ 15 Ko chacune, sans doute plusieurs niveaux par table), noms vers
  0xc03bd800, « WaveTable Version » en 0xc01ca768 ; l'ARM les envoie sans doute au
  SHARC à la demande (le SHARC n'a pas 1,9 Mo de RAM). Le manuel annonce 128 tables
  dans un chapitre et 114 dans les caractéristiques : peut-être des emplacements libres.
  Remplacer une table ne coûte pas de place ; en ajouter au-delà de 128 touche au format
  des programmes et au CC49 (0–127). Les échantillons se compressent mal : compter
  ≈ 15 Ko de flash par table, sur une marge connue de 200 Ko.

