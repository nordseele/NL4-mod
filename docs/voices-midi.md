# Réception MIDI et voix — notes de recherche (OS v1.32)

Les noms viennent de `tools/symbols.txt`, que l'ELF porte (`tools/rebuild.sh`). Le
pseudo-C complet se régénère avec `tools/dump_decomp.py` dans `ghidra/bin/decomp.c`
(hors git). Légende : **[sûr]** lu dans le code ; **[hyp.]** déduit, à confirmer.

> **Adresses corrigées le 2026-11-18.** Avant le commit qui suit `6c7f2fb`, l'image
> chargeait l'en-tête de section de 0x20 octets : toutes les adresses de **fonctions**
> des notes antérieures étaient trop hautes de 0x20. Les adresses de **variables
> globales** (lues dans les pools de littéraux, ex. 0xc04b0040) étaient déjà justes.

## Chaîne de réception MIDI  [sûr]

```
USB-MIDI (paquets de 4 octets, CIN → longueur)    DIN (port 5 broches)
  usbmidi_rx_packets / …2   c013e930 / c013e7f0      fn_c014c590 crée son parseur
        └────────────── midi_parse_byte (c013c6c8) ──┘
             running status, SysEx (F0…F7), temps réel F8–FF
             └─ midi_rx_to_queue (vtable 0xc0400eb0) : chaque message devient un
                objet de 0x40 octets {type, port (+4), canal (+5), arg1 (+8), arg2 (+0xC)}
                rangé dans une file (hors interruption)
                  └─ bus d'abonnement : midi_subscribe(sous-objet, type, priorité, drapeaux)
                       └─ gestionnaires de l'application (zone c011f000–c0122800)
                            └─ pour chaque cible (slot…) : test du masque (port, canal)
```

### Méthodes appelées par le parseur

| vtable | message | arguments |
|---|---|---|
| +0x00 | Note On | (canal, note, vélocité) ; vélocité 0 → Note Off avec vélocité 0x40 |
| +0x04 | Note Off | (canal, note, vélocité) |
| +0x08 | Poly Aftertouch (0xA0) | (canal, note, valeur) |
| +0x0C | Control Change | (canal, n° CC, valeur) |
| +0x10 | Program Change | (canal, programme) |
| +0x14 | Channel Pressure (0xD0) | (canal, valeur) |
| +0x18 | Pitch Bend | (canal, valeur signée −8192…+8191, déjà centrée) |
| +0x1C | fin de SysEx (tampon) | |
| +0x2C | Tune Request (0xF6) | |
| +0x30 | horloge / temps réel | |

Trois classes implémentent cette interface : `midi_rx_to_queue` (0xc0400eb0, branchée
sur les parseurs), un **émetteur MIDI** (0xc0400d70, encode en paquets USB-MIDI vers un
tampon de sortie) et une variante de l'émetteur (0xc0401128).

La charte MIDI du manuel (p. 47) confirme : **Channel Aftertouch transmis et reconnu**,
Poly Aftertouch (« Key's ») ni transmis ni reconnu, Pitch Bend transmis et reconnu.

### Types de messages (bus d'abonnement)

Le « type » d'un message est l'adresse d'un emplacement en RAM ; les gestionnaires s'y
abonnent au démarrage (`midi_subscribe`, c013135c).

| Type | Message |
|---|---|
| 0xc09140bc | Note On |
| 0xc09140c0 | Note Off |
| 0xc09140b0 | Pitch Bend |
| 0xc09140b4 | **Poly AT et Channel Pressure (même type)** |
| 0xc09140b8 | Program Change |
| 0xc09140ac, c4, c8, cc, d0 | Control Change (5 types : quelques CC traités à part) |
| 0xc09140a8 | SysEx |
| 0xc09140d4 … e8 | temps réel / horloge / divers |

### Contrôleurs internes  [sûr]

Table lue dans l'émission MIDI (`fn_c011f36c`, file de sortie) :

| n° interne | MIDI |
|---|---|
| 5 | CC4 |
| 6 | CC11 (pédale d'expression) |
| 7 | CC1 (molette) |
| **8** | **Channel Pressure (aftertouch)** |
| **9** | **Pitch Bend** (valeur 16 bits signée) |
| 10 | CC7 (volume) |
| 11 | CC10 (panoramique) |
| 13 | CC70 |
| 3 | CC82 |

À la réception, `midi_bend_in` (c0120398) et `midi_pressure_in` (c01202ac) parcourent la
liste des cibles et appellent `target_controller_in(cible, port, canal, n°, valeur)`
(c0112fac) avec n° = 9 et 8. **L'aftertouch reçu devient donc un contrôleur interne
(n° 8) du slot.** Ce qu'il module reste à trouver.

### Aiguillage canal → slot : des masques de bits  [sûr]

`target_controller_in` :
1. la cible est-elle active (`+0x20`) ?
2. **bit `canal + 16 × port`** du masque de la cible (mots à partir de `+0x10`) ;
3. le contrôleur est-il autorisé en réception (`+0x2D1 + n° × 0x18`) ?
4. mise à l'échelle (`fn_c011f004`), mémorisation **par cible et par contrôleur**
   (`+0x2D4 + n° × 0x18`), puis `cible->vt[0](cible, n°, valeur, 0)`.

Chaque cible a **plusieurs masques** (`+0x10`, `+0x54`, `+0x5C`, `+0x68` selon la
classe), remplis par `mask_add_channel` (c0114524) et ses variantes (c011c344,
c011c374, c011c3a4) ; le canal 16 (« Off ») est ignoré. La configuration se fait dans
`midi_routing_setup` (c00dee54) : pour chaque port activé (`+0x1FC`, `+0x1FD`, sans doute
USB et DIN), elle ajoute un canal (`+0x1E8`) aux masques de plusieurs cibles, en testant
slot par slot s'il est actif (`fn_c010bb1c(…, i)`).

**Conséquences pour le MPE :**
- Un slot peut **déjà écouter plusieurs canaux** : l'aiguillage est un masque de bits,
  pas un numéro de canal. Une zone MPE = ajouter les canaux membres (2–16) au masque du
  slot dans `midi_routing_setup`.
- Le pitch bend et la pression sont **mémorisés par cible (slot)**, une valeur commune à
  toutes ses voix. C'est ici qu'il faudra dévier vers une valeur par note : garder le
  canal d'origine, retrouver la note active sur ce canal, et appliquer la valeur à ses
  voix seulement.

### Chemin des notes  [sûr jusqu'aux cibles]

```
type Note On (0xc09140bc)
  └─ midi_note_handlers_ctor (c0121580) : 10 abonnements (Note On/Off, 4 types de CC…),
     chacun via un relais d'ajustement de this (sub r0, r0, #N ; b …)
       └─ midi_noteon_dispatch (c011fec8) / midi_noteoff_dispatch (c011fdcc)
            └─ targets_call_member (c011f62c) : pour chaque cible de la liste,
               appel d'un pointeur de fonction membre (ABI ARM {ptr, adj})
                 └─ target_note_on (c011129c) / target_note_off (c0111424)
```

`target_note_on(cible, port, canal, note, vélocité)` :
1. `target_find_zone` (c011ecc8) cherche le couple **(port, canal)** dans la liste de la
   cible (`+0xF0` : nombre en +4, ports en +8, canaux en +0xC) → **index de zone** ;
2. table des zones (`cible[0x31]`) : zone active, **plage de touches** (bornes basse et
   haute = split) et **transposition** (décalage + octave × 12) → note finale ;
3. table **[zone][note d'entrée] → note envoyée** (128 entrées par zone) : si la note
   d'entrée est déjà tenue, un Note Off part d'abord ;
4. envoi par `cible->vt[0](cible, 3, {note, vélocité})` (méthode redéfinie par la classe
   dérivée). `target_note_off` relit la note mémorisée, l'éteint par `vt[1]` et remet −1.

Les cibles (`note_target_ctor`, c0112b64) s'inscrivent dans une liste globale à la
construction. Le nombre de zones est global (`*DAT_c0112d9c`). Ce sont des **objets
composites** : partie contrôleurs (masque, `fn_c0114590`) à +0, partie notes à +0x430,
et pour certaines une 3ᵉ partie à +0x53C. Tout est monté par `app_midi_graph_ctor`
(c00e107c), dont `midi_routing_setup` remplit ensuite les masques (champs [0x52], [0x57],
[0x58]+0x53C, [0x5C]).

**Pour le MPE :**
- Une zone = un couple (port, canal). Déclarer chaque canal membre comme une zone de la
  même cible donnerait à chaque canal **sa propre table de 128 notes** : plus de
  collision entre canaux à ce niveau, sans changer la structure.
- Il reste à savoir comment la sortie `vt[0]` atteint le slot et `note_event_handler`,
  où la clé redevient (slot, note) **sans le canal**.

## Création des slots et des voix  [sûr]

`synth_create_slots_and_voices(4, …)` (c0010a44), appelée depuis le démarrage :

- 4 × `slot_ctor(obj, i)` (c000f314, 0x4B4 octets, i = 0…3). Chaque slot contient un
  `slot_engine` (0x8B8 octets, `slot_engine_ctor`, c001d610) avec des blocs de
  paramètres par slot de 0xA0 octets (2 × 0x50).
- 20 × `voice_ctor(obj, i)` (c002f1cc, 0x598 octets, i = 0…19). Chaque voix
  s'enregistre dans un **tableau global de 20 pointeurs** en `0xc04b0040`.
- Tableau des 4 slots en `0xc040d3b0`.

Les 20 voix forment un réservoir unique, partagé par les 4 slots (confirme le manuel).

## Voix  (0x598 octets)

- `+0x00` = numéro de voix ; plusieurs sous-objets le reçoivent aussi. **[sûr]**
- `voice_pitch_to_hw` (c002cd10) et `voice_pitch_mod_update` (c002ebfc) calculent la
  **hauteur par voix** : base + modulation (+0x160 / +0x17C / +0x168), table
  exponentielle (exposant + mantisse) → fréquence, écrite par
  `hw_write(bit0(id), adresse, valeur)` (c014f0d0, ~300 appels). **[sûr]**
- Numéro matériel (`+0x118`) : `bit0` = une destination parmi deux, `>>1` = index.
  **[hyp.]** deux puces / cœurs de synthèse de 10 voix.
- **[hyp. forte]** Le pitch est poussé voix par voix par l'ARM : un bend par note
  revient à remplacer, pour une voix, la composante bend du slot par une valeur propre.

## Allocation des voix

`note_event_handler` (c00263b4) consomme une file d'événements de note (0x800 entrées de
16 octets). Pour chaque note : entrée active, mode (1/2/3 — **[hyp.]** poly / mono /
legato), liste de ses voix, déclenchement ou relâchement de chaque voix.

Objet allocateur : global, à `0xc04a7210 − 0xca0`. **[sûr pour la structure]**

| Champ | Sens |
|---|---|
| +0x04 | compteur d'événements (horodatage) |
| +0x6C | nombre de notes actives |
| +0x70 | tableau de pointeurs vers les notes actives |

Note active :

| Champ | Sens |
|---|---|
| +0x00 | clé de tri (priorité / âge) — tri de Shell dans `alloc_note_on` / `alloc_update_sort` |
| +0x04 | horodatage / propriétaire |
| +0x14, +0x18 | identité de la note : **(slot, numéro de note)** |
| +0x1C | état (0–3) |
| +0x20 | drapeau mis à 1 au relâchement |
| +0x28 | nombre de voix utilisées (unisson > 1) |
| +0x2C | voix (pointeurs ; numéro de voix en +8) |

`alloc_note_on` (c001b004) prépare et trie, puis appelle **`alloc_core`** (c0019884) :
- réservoir de **64 notes** (entrées de 0x80 octets), distinct des 20 voix ;
- nombre de voix par note passé à l'appel : 1 en poly, plus en unisson ;
- les voix sont prises sur les notes en tête de la liste triée ; la clé combine état,
  âge et autres critères (vol de voix). Détail des bits non décodé.

## Identité d'une note : (slot, numéro de note)  [sûr]

C'est **le premier obstacle pour le MPE**.

- Les événements de note portent `+8` = **numéro de slot** (index dans le tableau des
  slots) et `+0xC` = **numéro de note** (hauteur calculée depuis `note − 64`).
- L'allocateur recopie cette paire (`+0x14`, `+0x18`).
- Chaque slot tient un **tableau de 128 touches** (`+0x1C`), le nombre de touches tenues
  (`+0x224`), la plus basse et la plus haute (`+0x21C` / `+0x220`) :
  `slot_notes_update` (c0027888).
- Le canal MIDI n'y figure pas.

Deux doigts sur la même hauteur dans le même slot (courant sur LinnStrument) seraient
confondus. Il faut ajouter le canal à la clé (ex. `note | canal << 8`), masquer partout
où la note sert à la hauteur, et donner au tableau de touches une dimension canal.

## Construction des voix d'une note

`note_on_build_voices` (c00268d0) : hauteur de chaque voix =
`(note − 64 + décalage_i) × 0x10000` (décalages : Chord Memory / unisson **[hyp.]**).
Le relâchement (`note_off_release_voices`, c0026ae0) dépend du mode de la note.

## Contrôleurs de jeu du slot

`slot_controller_in` (c000fb8c) : méthode du slot, `switch` sur un numéro de contrôleur.
Le slot hérite de trois interfaces (vtables en `0xc01bd738`, +0x60, +0x6C).
`fn_c00f04a4` est un aiguillage de 77 paramètres (0–0x4C) agissant sur le slot :
probablement l'arrivée des CC et des réglages du panneau.

## Questions ouvertes, par ordre d'utilité pour le MPE

1. **Du graphe MIDI au slot** : cartographier `app_midi_graph_ctor` et la destination de
   `cible->vt[0]`, jusqu'à `note_event_handler`. Vérifier sur l'instrument et dans le
   code à quels slots s'applique le pitch stick (« Keyboard Focus » ou slot actif seul).
2. **Pitch bend** : où le contrôleur 9 du slot est mis à l'échelle par le Bend Range
   (1–12, 24, 48) et ajouté à la hauteur de ses voix — point d'injection du bend par note.
3. **Pression (contrôleur 8)** et CC74 : ce qu'ils modulent aujourd'hui, et le chemin
   par voix du morph de vélocité, pour y brancher Y/Z en continu.
4. Politique exacte du vol de voix (bits de la clé) et limite éventuelle par slot.
5. Les deux destinations de `hw_write` et la cadence des mises à jour.
