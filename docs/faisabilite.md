# Étape 2 — Faisabilité du MPE sur le Nord Lead 4 (OS 1.32)

Note de conception, 2026-11-18. Elle s'appuie sur `docs/voices-midi.md` (chemins MIDI,
voix, allocation, bend, morph), `docs/update-protocol.md` et `docs/oscab-format.md`
(mise à jour, checksums), `docs/hardware.md` (carte). Légende : **[sûr]** lu dans le
code ; **[hyp.]** déduit ; **[à mesurer]** se tranchera sur le prototype.

## Verdict

**Faisable, par un patch de l'OS ARM seul**, sans toucher au code des SHARC. Le firmware
calcule déjà la hauteur et les paramètres de morph **voix par voix** côté ARM ; un slot
sait déjà écouter plusieurs canaux. Le travail consiste à garder le canal MIDI jusqu'aux
voix et à remplacer, pour une voix, des valeurs aujourd'hui communes au slot.

- **Bend par note (±48)** : simple, chemin entièrement connu.
- **Y (CC74)** : moyen, chemin connu ; coût processeur [à mesurer].
- **Z (pression)** : moyen à difficile selon la source de morph choisie (voir
  « Assigner Y et Z dans un programme »).
- **Notes MPE simultanées** : jusqu'à **20** (la polyphonie du Lead 4), partagées entre
  les slots ; moins en unisson.

Rien de ce qu'on a lu ne rend le projet impossible. Les deux inconnues sont le coût
processeur du recalcul continu des voix et le chemin du morph Wheel / Impulse vers les
voix (pour Z).

## Ce que le firmware fait déjà pour nous  [sûr]

| Besoin MPE | Déjà là | Où |
|---|---|---|
| Un slot écoute 15 canaux membres | aiguillage par masque de bits (port, canal) | `target_controller_in`, `midi_routing_setup` |
| Une table de notes par canal | une zone de 128 notes par (port, canal) dans chaque cible | `target_note_on`, `target_find_zone` |
| Hauteur propre à chaque voix | `voice_pitch_offset` ajoute déjà un terme par voix (glide) | c001ccf4 |
| Recalcul continu des voix | `synth_tick` recalcule la hauteur des 20 voix à chaque tick | c0010c34 |
| Paramètres propres à chaque voix | 59 paramètres du son ont une copie par voix | `voice_param_handler` |
| Morph calculé par voix | entrée vélocité + entrée clavier, par voix | `voice_apply_velocity`, `voice_morph_eval` |
| Paramètres modifiables pendant une note | tourner un bouton du panneau change le son des notes tenues | (comportement de l'instrument) |
| Bend en 14 bits | conservés jusqu'au moteur | `midi_bend_in` → `bend_set_value` |
| Canal de chaque CC | `midi_cc_in` reçoit (port, canal, n°, valeur) | c011ffc4 |

## Modifications nécessaires

### A. Zone MPE : faire écouter les canaux membres  — simple
Ajouter les canaux 2 à 16 (zone basse) au masque du slot dans `midi_routing_setup`
(c00dee54). Configuration : idéalement par le **message de configuration MPE**
(RPN 6 sur le canal maître), que l'Osmose et le LinnStrument envoient. On l'intercepte
dans `midi_cc_in` (CC 101 / 100 / 6) : **pas d'écran à ajouter** pour activer une zone.
Reste un réglage pour choisir le slot (ou la Performance) qui reçoit la zone [à concevoir].

### B. Garder le canal d'une note  — moyen, le point le plus délicat
Le canal disparaît à `target_note_on`, qui ne transmet que {note, vélocité}. Deux
niveaux possibles :

1. **Niveau 1 : une table canal → note, à côté.** On n'élargit pas l'identité des notes.
   Au Note On d'un canal membre, on mémorise « canal c joue la note n du slot s ».
   Les expressions (bend, Y, Z) du canal c vont aux voix de (s, n). Limite : deux doigts
   sur **la même hauteur** dans le même slot restent confondus (rare sur l'Osmose,
   possible sur le LinnStrument : même note sur deux rangées).
2. **Niveau 2 : la note « étendue »** `note + 128 × canal` dans toute la chaîne (tables
   de 128 du filtre de destinations, de l'arpégiateur et du slot ; clé de l'arbre
   `note | slot << 8` à élargir en `slot << 12` ; masque `& 0x7F` partout où la note
   sert à la hauteur). Plus de collision, mais 7 structures touchées : plus de risque.

Proposition : **niveau 1 d'abord**, niveau 2 seulement si les doublons gênent en jeu.
L'arpégiateur et la Chord Memory sont désactivés sur un slot en mode MPE.

### C. Bend par note (±48)  — simple
- Réception : `midi_bend_in` (c0120398) connaît le canal. Sur un canal membre, au lieu
  de la valeur commune du slot (contrôleur 9 → paramètre 0x23), ranger la valeur dans
  la voix de la note de ce canal.
- Application : dans `voice_pitch_offset`, ajouter ce terme de la voix au calcul, comme
  le glide (`voix+0x590`). Le bend du canal maître reste le bend commun du slot.
- **Échelle linéaire** : la courbe du Lead 4 est parabolique au-delà de 2 demi-tons
  (`bend_set_value`) ; le terme MPE utilise sa propre échelle linéaire ±48.
- Pas de lissage sur 32 ticks pour ce terme : les contrôleurs MPE envoient des valeurs
  denses.

### D. Y (CC74 des canaux membres)  — moyen
- Réception : intercepter le CC74 des canaux membres dans `midi_cc_in` ; sur le canal
  maître, il garde son sens (Filter Frequency).
- Application : poser la valeur dans l'entrée de morph de la voix, puis rappeler
  `voice_apply_velocity` (c0032098), qui recalcule et applique tous les paramètres
  morphés de cette voix sans redéclencher les enveloppes. Variante plus légère :
  écrire directement l'adresse SHARC de quelques paramètres de la voix (le SHARC lisse
  les valeurs, `docs/sharc.md`).
- **Coût** : quelques milliers d'instructions par appel, ≈ 10 µs [hyp.]. Pour tenir,
  au plus un recalcul par voix et par tick, seulement si la valeur a changé. À
  mesurer : la fréquence de `synth_tick` et la marge processeur.

### E. Z (pression des canaux membres)  — moyen à difficile
- Réception : `midi_pressure_in` (c01202ac) connaît le canal. Le chemin d'origine
  (pression → paramètre 0x29, morph Wheel) est du code mort dans l'OS 1.32 : rien à
  défaire.
- Application : dépend de la source de morph choisie (section suivante).

### F. Fabriquer et installer l'OS modifié  — moyen, outillage
- Patch du code dans `img1_CODE` (ARM), nouvelles routines dans une zone libre ou en
  fin de section (la taille déclarée change ; le clavier annonce sa taille maximale
  avant l'effacement : « Memory is only %d KB »).
- Recompresser la section en LZO1X, recalculer les deux checksums (`~somme des
  octets`) et les tailles, reconstruire `os.cab`. Outil à écrire
  (`tools/pack_oscab.py`), validé d'abord en reproduisant `os.cab` à l'identique ou à
  l'équivalent.
- Vérification du fichier côté Mac : lue et reproduite (somme de l'en-tête d'image
  comprise). **Outil écrit et vérifié** : `tools/pack_oscab.py`.

## Assigner Y et Z dans un programme

Le Lead 4 a trois familles de sources de morph, assignées depuis le panneau (tenir la
source, tourner la destination) et enregistrées dans le programme : **Velocity**,
**Wheel** (molette, pédale, CC1, CC11) et **7 Impulse Morphs**.

| Option | Principe | Coût | Ce qu'on perd |
|---|---|---|---|
| **Velocity ← Y** | l'entrée vélocité de la voix suit le CC74 en continu (valeur de départ : la vélocité du Note On) | faible : le calcul par voix existe | le morph de vélocité « pur » en mode MPE |
| **Wheel ← Z** | ce que Clavia avait prévu pour l'aftertouch (code mort) | moyen : le morph Wheel est calculé une fois par slot (`engine_param_wheel_morph`), il faut le rendre propre à chaque voix | la molette comme source par voix (elle resterait globale si on cumule) |
| **Impulse 6 / 7 ← Y / Z** | dédier deux Impulse Morphs à Y et Z ; Velocity reste intact | moyen : rendre ces morphs continus et par voix ; chemin non lu | deux des sept Impulse Morphs |
| **Nouvelle source** | une vraie source « Y », « Z » | élevé : format des programmes, interface, compatibilité Sound Manager | — |

Recommandation : **Velocity ← Y pour le premier prototype** (aucune inconnue), puis
choisir pour Z entre Wheel et Impulse après lecture de leur chemin vers les voix. Aucune
option n'exige de nouvel écran ni ne casse les programmes existants, sauf la dernière.

## Place disponible sur l'ARM (AM1705)

- **RAM** : 16 Mo de SDRAM (U29). Le code occupe 4,2 Mo à partir de 0xc0000000, les
  données statiques vont jusque vers 0xc04F0000, des tampons sont utilisés jusque vers
  0xc0930000 : il reste vraisemblablement plusieurs Mo, à confirmer (bornes du tas non
  lues) **[hyp.]**.
- **Où loger notre code** : la section CODE ne peut pas grandir (les données de l'OS
  commencent à 0xc040c000, 2,7 Ko après sa fin). En revanche, la **section SRAM** est
  du code exécuté depuis la RAM partagée de 128 Ko (53 fonctions de Nord, 0x80000000–
  0x80001c24). Au-dessus, rien n'est référencé jusqu'aux piles (sommet de la pile
  système en 0x8001e7a0, piles IRQ/FIQ/SVC jusqu'à 0x8001f000, zone d'échange en
  0x8001ff00). On agrandit donc la section SRAM avec notre code, appelé depuis le CODE
  par des sauts longs. Inconnue : la profondeur réelle de la pile système (elle
  descend depuis 0x8001e7a0) ; avec un patch de 16 Ko en 0x80001c40, il faudrait
  qu'elle dépasse ~100 Ko pour nous atteindre **[hyp.]**. Repli : code mort du CODE
  (717 fonctions sans référence directe, 276 Ko, à confirmer une par une).
- **Code** : le patch MPE et une fonction d'aide à la conversion (ci-dessous) pèsent
  quelques dizaines de Ko. La limite est la zone de flash réservée à l'OS, que le
  clavier annonce à l'updater (« Memory is only %d KB ») et que nous ne connaissons pas.
  L'OS compressé fait 2,75 Mo.
- **Processeur** : marge inconnue ; à mesurer sur le prototype.
- **Côté SHARC** : rien à ajouter (`docs/sharc.md`).

### Une fonction « convertir pour le MPE »
Possible dans l'esprit du Mutator : par exemple, recopier les destinations du morph
Wheel vers le morph Velocity (pour Y), régler le bend à ±48, couper l'arpégiateur.
Le coût n'est pas la place mais l'interface : trouver un geste de panneau libre (une
combinaison Shift + bouton) et le code d'édition des morphs. Plus simple si Y passe par
Velocity (les assignations existent déjà) ; une nouvelle source demanderait d'abord de
changer le format des programmes.

## Polyphonie et limites

- 20 voix au total, partagées par les quatre slots ; une note MPE = une voix (deux ou
  plus en unisson). Une zone MPE sur un slot peut donc jouer jusqu'à 20 notes.
- Le vol de voix suit les règles actuelles (clé de tri de l'allocateur, bits non
  décodés) : une voix volée perd son expression avec sa note, ce qui est le
  comportement attendu.
- Une zone par slot est possible en théorie (quatre zones = quatre plages de canaux),
  mais le MPE n'a que deux zones (basse et haute) : en pratique, **une zone par
  Performance** routée vers un slot, ou deux zones vers deux slots.

## Risques

| Risque | Gravité | Parade |
|---|---|---|
| OS modifié qui plante au démarrage | moyenne | mode Update par Shift + Store (vérifié), réinstallation du 1.32 officiel |
| Fichier refusé par l'updater | faible | vérification Mac lue et reproduite par `pack_oscab.py` |
| Processeur saturé par Y/Z continus | moyenne | limiter à un recalcul par voix et par tick ; mesurer |
| Boot / Update abîmés | très faible | une mise à jour ne les réécrit pas ; dernier recours : démonter la carte |
| Comportement des SHARC inconnu | faible | on ne leur envoie que ce que le panneau envoie déjà |

## Plan du prototype (étape 4), du plus sûr au plus utile

Chaque palier se teste sur l'instrument avant le suivant.

0. **Répétition** : réinstaller l'OS 1.32 officiel depuis Shift + Store.
1. **Chaîne d'outils** : reconstruire `os.cab` sans modification de fond (recompressé,
   checksums recalculés), l'installer, vérifier que tout marche.
2. **Plus petit patch visible** : une chaîne modifiée à l'écran, ou un slot qui écoute
   les canaux 2 à 16. Les notes de l'Osmose jouent, sans expression.
3. **Bend par note** (C), niveau 1 de l'identité (B1).
4. **Y → morph Velocity** (D), avec mesure du coût.
5. **Z** (E) selon l'option retenue.
6. Activation par RPN 6 ; niveau 2 de l'identité si les doublons gênent.

## Décision demandée

Continuer vers l'étape 4 avec ce plan, en commençant par les paliers 0 et 1 (aucune
modification du comportement), ou s'arrêter ici.
