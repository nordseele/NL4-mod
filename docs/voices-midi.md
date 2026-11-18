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
- Mais le canal ne va pas plus loin : la cible appelle le slot avec des paires
  {note, vélocité} seulement (section « Du slot à l'allocateur »).

### Des cibles au slot  [sûr]

- `slot_midi_input_ctor` (c00f1c5c, n° de slot en paramètre) construit **l'entrée MIDI
  d'un slot** : la partie notes a pour destination **le slot lui-même**
  (`fn_c01108fc(partie notes, slot)`), la partie contrôleurs a pour destination la 2ᵉ
  interface du slot (`slot + 4`).
- Le 2ᵉ argument des méthodes de note est un **masque de destinations** : bit 1 = MIDI
  OUT (classe `fn_c01289a4`, file de sortie par couple (port, canal)), autre bit = synthé
  interne. Une 3ᵉ classe de destination (`fn_c00f8154`) ne fait que compter les notes
  tenues (indicateur).
- `slot->vt[0]` = **`slot_note_on`** (c000f044) : calcule pour la note les valeurs de
  **morph de vélocité et de suivi de clavier** (`(note − 64) × 0x10000`,
  `vélocité >> 3`, base + vélocité × quantité, bornées, pour chaque destination de
  morph), les applique au moteur du slot, puis transmet la note à l'objet en `slot+0x20`.
  Ce calcul n'a lieu que si le bit 2 du masque est mis.
- Conséquence pour le MPE : le morph de vélocité est **calculé au Note On, au niveau du
  slot**. C'est un endroit naturel pour une modulation par note (Y/Z), à condition de
  le rendre continu et par voix.

### Du slot à l'allocateur  [sûr]

Les méthodes de note de toute la chaîne ont la même forme :
`vt[0]` = Note On, `vt[1]` = Note Off, arguments `(objet, &masque, notes, nombre)`, où
`notes` est un tableau de paires **{note, vélocité}**. Un appel peut donc porter
plusieurs notes (accord, Chord Memory **[hyp.]**).

```
slot_note_on (c000f044)                    morph de vélocité si masque & 2
  └─ slot+0x1C = slot+0x20 : filtre de destinations (0x88 octets, vtable 0xc01bd848)
       note_dest_filter_on / _off (c00121b8 / c00123b4)
       un octet d'état par note (128) : sur quelles destinations la note a été lancée,
       pour que le Note Off reparte au même endroit
  └─ slot+0x18 : arpégiateur (0x460 octets, vtable 0xc01bd8c0)
       arp_note_on / _off (c00148f4 / c0012a68) ; laisse passer si l'arpège est coupé
       (drapeaux +0x1D, +0x1E, +0x458 ; tables de 128 notes en +0x10 / +0x14)
  └─ slot+0x14 : sortie du slot (8 octets {vtable 0xc01bd6d8, n° de slot})
       slot_sink_note_on → slot_queue_note_on (c0028780)
       slot_sink_note_off → slot_queue_note_off (c0027888)
            └─ table de touches du slot, file d'événements, puis note_queue_drain
```

`slot_arp_param_in` (c000fb8c, ex-`slot_controller_in`) règle l'objet `slot+0x18`, donc
l'arpégiateur **[hyp. forte]**.

**`slot_queue_note_on(n° de slot, notes, nombre, &masque)`**, pour chaque note :
- masque & 1 : purge des événements en attente pour (slot, note), création de la note
  dans la **table des notes** (`notemap_create`, avec des réglages du slot : `+0x22C`,
  `+0x22D`, `+0x258`), puis un événement immédiat de type 1 ;
- masque & 2 : mise à jour de la table de 128 touches du slot (tenue, plus basse, plus
  haute), vélocité `>> 3` dans la note, événement immédiat de type 2, puis **deux
  événements en file : type 3 puis type 4**. Un observateur global (`*0xc040d3e4`,
  méthode 2) reçoit (slot, note, vélocité) ;
- masque & 4 : événement de type 6.

`slot_queue_note_off` met à jour la table de touches et range un événement de type 5.
L'observateur reçoit la note par sa méthode 3.

**File d'événements** : réservoir de 0x800 entrées de 16 octets
`{vtable, type (+4), slot (+8), note (+0xC)}` en `0xc04a6578`, et anneau de 0x200
pointeurs (compte, lecture, écriture en `0xc04af1f0 − 0xC74 / −0xC70 / −0xC6C`).
`note_queue_drain` (c0027708) les exécute dans l'ordre. Un événement de type 3 attend
tant que les voix de la note précédente ne sont pas assez retombées (seuil 0x8000).

**Patron visiteur** : un événement appelle une méthode du **gestionnaire de notes**
(`0xc04ae578`, vtable `0xc01bde50`) avec lui-même en argument :

| type | vtable de l'événement | méthode du gestionnaire |
|---|---|---|
| 1 | 0xc01bddf0 | vt[0] = `note_ev1_alloc_voices` (c0026ae0) |
| 2 | 0xc01bde00 | vt[1] = `note_ev2_handler` (c0026d50) → `alloc_ev2` → `alloc_core` |
| 3 | 0xc01bde20 | vt[2] = `note_on_build_voices` (c00268d0) |
| 4 | 0xc01bde10 | vt[3] = `note_event_handler` (c00263b4) |
| 6 | 0xc01bde30 | vt[4] = `note_ev6_handler` (c0026c34) |
| 5 | 0xc01bde40 | vt[5] = `note_off_event` (c002718c) → `alloc_note_off_collect` |

**Deux chemins d'allocation, tous deux actifs :**
- type 1 (masque & 1) : `note_ev1_alloc_voices` (ex-`note_off_release_voices`, nom faux)
  lit le mode de la note (`fn_c0016070`). Mode 1 → `alloc_take_mode1` (c0018dcc), qui
  réutilise les voix d'une note du même slot (**[hyp.]** mono / legato). Modes 0 et 2 →
  `alloc_take` (c0019220). Les deux trient les notes actives (tri de Shell), demandent
  `nombre × param[1]` voix (**[hyp.]** × unisson) à **`alloc_pick`** (c0018324,
  2,7 Ko), puis préparent chaque voix rendue (`fn_c0037db4`) ;
- type 2 (masque & 2) : `note_ev2_handler` → `alloc_ev2` (c001a7a0) → `alloc_core`
  (c0019884).

`alloc_note_on` (c001b004) n'a aucun appelant, ni direct ni par pointeur : c'est
peut-être du code mort. Les rôles exacts des deux chemins (réservation puis
déclenchement ?) restent à lire.

**Table des notes** (`0xc040f470`) : un arbre binaire de recherche, dont les nœuds
d'environ 0x258 octets ont leurs fils en `[0x93]` / `[0x94]`. `notemap_has` /
`notemap_get` / `notemap_create` cherchent avec la clé **`note | slot << 8`**, calculée
depuis la paire {slot, note}.

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

`note_event_handler` (c00263b4) est la méthode du gestionnaire de notes appelée par
l'événement de type 4 (section « Du slot à l'allocateur »). Elle retrouve la note dans la
table (`notemap_has`, `notemap_get`), puis traite : entrée active, mode (1/2/3 —
**[hyp.]** poly / mono / legato), liste de ses voix, déclenchement ou relâchement de
chaque voix.

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

`alloc_note_on` (c001b004, sans appelant) et `alloc_ev2` (c001a7a0) préparent et
trient, puis appellent **`alloc_core`** (c0019884). Le chemin du type 1 passe, lui, par
`alloc_pick` (section « Du slot à l'allocateur ») ; il reste à le comparer avec
`alloc_core`. Ce qu'on sait d'`alloc_core` :
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
  `slot_queue_note_on` / `slot_queue_note_off` (c0028780 / c0027888).
- Le canal MIDI n'y figure pas. **Il disparaît dès l'appel au slot** : `target_note_on`
  transmet des paires {note, vélocité}, sans le canal.

Deux doigts sur la même hauteur dans le même slot (courant sur LinnStrument) seraient
confondus. Endroits qui indexent par numéro de note, du premier au dernier :

| où | structure | indexée par |
|---|---|---|
| cible | table [zone][note] (une zone par (port, canal)) | déjà par canal |
| filtre de destinations | 128 octets d'état | note |
| arpégiateur | tables de 128 notes | note |
| slot | table de 128 touches | note |
| table des notes | arbre | `note | slot << 8` |
| file d'événements | entrée {slot, note} | (slot, note) |
| allocateur | note active +0x14 / +0x18 | (slot, note) |

**Piste la plus simple** : faire passer une note « étendue » `note + 128 × canal` à partir
de `target_note_on`. Les tables de 128 deviendraient 128 × 16, ou bien l'arpégiateur et
le filtre seraient contournés en mode MPE. La clé de l'arbre (`note | slot << 8`) doit
alors être élargie (`slot << 12`), sinon la note 256 du slot 0 vaut la note 0 du
slot 1. Enfin, il faudra masquer (`& 0x7F`) partout où la note sert à la hauteur :
`note_on_build_voices`, le suivi de clavier de `slot_note_on`, l'affichage.

## Construction des voix d'une note

`note_on_build_voices` (c00268d0) : hauteur de chaque voix =
`(note − 64 + décalage_i) × 0x10000` (décalages : Chord Memory / unisson **[hyp.]**).
Le relâchement (`note_off_event`, c002718c, type 5) passe par `alloc_note_off_collect`
et dépend des réglages du slot (`+0x22C`).

## Contrôleurs de jeu du slot

Le slot hérite de trois interfaces (vtables en `0xc01bd738`, +0x60, +0x6C). La 2ᵉ
(`slot+4`, une seule méthode) reçoit les contrôleurs MIDI : relais
`slot_midi_ctrl_in_thunk` (c000fb44, `sub r0, r0, #4`) → **`slot_midi_ctrl_in`**
(c000fa58).

`slot_controller_in` (c000fb8c) ne fait **pas** partie de ce chemin, malgré son nom : son
`switch` (0–9) agit sur l'objet `slot+0x18`, et il est appelé à l'initialisation
(`fn_c000fd80`). `fn_c00f04a4` est un aiguillage de 77 paramètres (0–0x4C) agissant sur le
slot : probablement l'arrivée des CC et des réglages du panneau.

### `slot_midi_ctrl_in(slot, n°, valeur)`  [sûr]

Mémorise la valeur en `slot+0x224 + n° × 4` (>> 16), puis la convertit en **paramètre
du slot** par `slot_set_param` :

| contrôleur | paramètre du slot | condition |
|---|---|---|
| 5 (CC4) | 0x57 | |
| 7 (molette) | 0x29 | `slot+0x260 == 1` |
| **8 (pression)** | **0x29** (même destination que la molette) | `slot+0x260 == 2` |
| **9 (bend)** | **0x23** | |
| 10 (CC7) | 0x56 | |
| 11 (CC10) | 0x55 | |

`slot+0x260` (écrit par `slot_set_wheel_src`) devait choisir qui pilote le paramètre
0x29 : la molette (1) ou la pression (2). **La valeur 2 n'est jamais écrite** (voir
« Molette, pression et morph par voix ») : dans l'OS 1.32, la pression ne fait rien.

### `slot_set_param(slot, n°, &valeur)` (c000f93c)  [sûr]

Mémorise la valeur en `slot+0x2D4 + n° × 4`, puis consulte les drapeaux du paramètre
(octet `slot+0x278 + n°`, 6 par défaut, 0xF pour 0x3E, 0x3F, 0x43) :
- bit 2 : envoi au **moteur du slot**. `engine_param_convert` (c001e7dc) donne la
  fonction de conversion, `engine_param_handler` (c001e26c, `switch` sur le n°) la
  méthode qui l'applique ;
- bit 4 : envoi à **chaque voix du slot**. Boucle sur les 20 voix de `0xc04b0040` ; une
  voix est prise si elle appartient à ce slot et si son état (`+8`) vaut 3.
  `voice_param_handler` (c0029678) donne la méthode de la voix ;
- bit 8 : 2ᵉ envoi au moteur (avec le code 8) ;
- bit 1 : traitement différé (file).

Pour 0x23 (bend), `voice_param_handler` n'a **pas** de cas : c'est la méthode par défaut
(c00333d0, un simple `bx lr`). **Le bend n'est jamais envoyé voix par voix**,
seulement au moteur du slot.

## Molette, pression et morph par voix  [sûr sauf mention]

### La pression est du code mort
`slot+0x260` n'est écrit qu'à 0 (constructeur) et par `slot_set_wheel_src` (c000f510),
dont le seul appelant, `slot_wheel_mode_apply` (c00f0270), et la même logique recopiée
dans `fn_c00f0438`, ne passent que 0 ou 1. Le cas « pression → 0x29 » de `slot_midi_ctrl_in` ne
s'exécute donc jamais. C'est cohérent avec le manuel : le Lead 4 n'a pas d'aftertouch,
et la source de morph « Wheel » regroupe molette, pédale, CC1 et CC11. **Pour Z, il
faudra un chemin neuf** ; rien n'est à défaire.

`slot_wheel_mode_apply` lit un mode à `+0x630` (0 à 3) et règle les paramètres 0x29,
0x2B, 0x2C, 0x2D. Mode 3 : 0x29 = valeur courante de la molette, 0x2B = 100, la molette
pilote 0x29. Modes 1 et 2 : 0x29 fixé à 127, 0x2B tiré de `+0x62C`, 0x2C / 0x2D
constants. Mode 0 : tout à 0. Sens exact inconnu (réglage de la pédale ?) **[hyp.]**.

### Le morph molette est global au slot
0x29 n'a de cas que dans `engine_param_handler` (→ `engine_param_wheel_morph`, c0023e48),
pas dans `voice_param_handler`. La méthode borne la valeur à 127, la passe par une
courbe (produits 16 bits), écrit `moteur+0x878` / `+0x87C`, puis prévient l'objet
`moteur+0x864` (c0052434) si un compteur a changé. Une seule valeur pour tout le slot.

### Le morph de vélocité est calculé voix par voix
`voice_param_handler` couvre 59 paramètres (0x00–0x20, 0x26–0x28, 0x2C–0x2F, 0x31,
0x35–0x37, 0x3B, 0x3E–0x44, 0x46, 0x4B–0x4F) : **chaque voix garde sa propre copie des
paramètres du son.** Avant d'appliquer une valeur, `slot_set_param` (bit 4) la fait
passer par le convertisseur de la voix, l'objet `voix+0x48` :

```
voice_morph_eval (c0033538)  objet o = voix+0x48, paramètre n
  e = table[n]  (o+0xC → +0xC, 5 mots : base, quantité vélocité, quantité clavier, min, max)
  clavier = (o[1] + table+4) >> 7          o[1] = (note − 64) << 16  [hyp., par analogie]
  valeur  = base + (o[2] + 1) × qté_vél >> 7 + f(clavier × qté_clavier)
  (*(o+0x10))[n] = borne(valeur, min, max)       o[2] = vélocité  [hyp. forte]
```

C'est la même formule que celle de `slot_note_on` pour l'arpégiateur. La vélocité et la
note de chaque voix sont donc des **entrées par voix** d'un calcul par voix.

**Conséquence pour le MPE (Y / Z)** : faire varier en continu l'entrée vélocité `o[2]`
d'une voix, depuis le CC74 ou la pression de son canal, puis recalculer et appliquer
les paramètres de **cette voix seulement**. Toutes les destinations de morph
« Velocity » d'un programme deviennent alors pilotées par Y ou Z, note par note, sans
toucher au moteur ni au code SHARC. À vérifier : où `o[1]` et `o[2]` sont écrits au
Note On, et le coût d'un recalcul complet à chaque message (20 voix maximum).

### CC74
Le manuel l'affecte à **Filter Frequency**, un paramètre du programme : il passe par le
chemin normal du panneau, donc vers toutes les voix du slot. Son n° de paramètre n'est
pas encore identifié (aiguillage `fn_c00f04a4`, 77 cas). Pour le MPE, il faudra le
détourner sur les canaux membres.

## Chemin du pitch bend  [sûr]

```
midi_bend_in (c0120398)
  └─ target_controller_in(cible, port, canal, 9, valeur −8192…+8191)
       ctrl_scale_in (c011f004) : < 0 → × 1024 ; ≥ 0 → × 0x1FC1 / 8, borné à 0x7F0000
       └─ slot_midi_ctrl_in (c000fa58) → slot_set_param(slot, 0x23)
            └─ engine_param_bend (c0022f40) → bend_set_value(engine + 0x28C, v)
                 objet « bend » du slot : cible en +0xC
  synth_tick (c0010c34), à chaque tick :
     pour chaque slot actif : lissage +0x14 → +0xC en 32 pas (pas en +0x18)
     puis pour les 20 voix : voice_pitch_tick (c002eff8) → voice_pitch_mod_update(voix, 0)
          hauteur = voice_pitch_offset(voix + 0x590, engine + 0x28C)
                  = bend lissé (+0x14) + transposition du slot + glide de la voix
```

**L'objet bend** (`slot_engine+0x28C`, créé par `bend_ctor`, c001c894) :
`[0]` → structure de 0x21C octets, `[4]` = transposition du slot (octave × 12 + demi-tons
+ fin, méthodes c001cbbc / c001cbfc / c001cc3c). La structure contient :

| champ | sens |
|---|---|
| +0x04 | plage vers le haut (demi-tons, 2 par défaut) |
| +0x08 | plage vers le bas (demi-tons, 2 par défaut) |
| +0x0C | bend cible (demi-tons en 16.16) |
| +0x10 / +0x18 | dernière cible vue / pas du lissage |
| +0x14 | bend lissé, **lu par toutes les voix du slot** |
| +0x1C… | table de 128 valeurs (courbe cubique), recalculée par `bend_set_range` ; usage inconnu |

**Bend Range** = paramètres du moteur : **0x21** (`engine_param_bend_range`, c0023208)
règle les deux sens (`engine+0x250`), **0x22** (`engine_param_bend_down`, c0022fc0) le sens
descendant seul (`engine+0x254`, cas asymétrique −12 / −24). Les deux appellent
`bend_set_range` (c001c9d8). `slot_set_bend_range` (c000fb4c, entrée 15 de la vtable du
slot) envoie 0x21 et 0x22 d'un coup.

**Courbe** (`bend_set_value`, c001cb30), v = ±0x800000 (0x7F0000 est traité comme
+0x800000) :

```
bend = 2 × v / 0x800000                          (linéaire sur 2 demi-tons)
     + (plage − 2) × (v / 0x800000)² × signe(v)  (parabolique au-delà)
```

**La courbe n'est pas linéaire au-delà de 2 demi-tons.** Avec une plage de 48, un bend à
mi-course donne 1 + 46 / 4 = 12,5 demi-tons au lieu de 24. Le MPE suppose une
correspondance linéaire (glissés de hauteur des contrôleurs), donc **le bend MPE aura
besoin de sa propre échelle linéaire**. La résolution de 14 bits est conservée jusque-là.

**Pour le MPE :**
- **Point d'injection** : `voice_pitch_offset` (c001ccf4, 3 appelants :
  `voice_pitch_mod_update`, `voice_pitch_tick` via celui-ci, et la mise en hauteur au
  Note On `fn_c0032098`). Elle additionne déjà un terme **propre à la voix** : le glide
  (`voix+0x590`, réglé par les paramètres de voix 0x26–0x28). Un bend par note
  s'ajoute au même endroit : bend du slot remplacé (ou complété) par une valeur de la
  voix, en échelle linéaire.
- Le recalcul a déjà lieu **à chaque tick, pour les 20 voix**, quand un slot est actif.
  `voice_pitch_mod_update` sort tôt si la valeur combinée n'a pas changé. Il n'y a donc
  rien à ajouter pour la cadence : il suffit que la valeur par voix change.
- Le lissage sur 32 ticks se fait par slot. Un bend par note voudra le sien (ou aucun, les
  contrôleurs MPE envoyant des valeurs denses).
- À déterminer : la durée d'un tick (fréquence de `synth_tick`).

## Questions ouvertes, par ordre d'utilité pour le MPE

1. ~~Du graphe MIDI au slot~~ : fait jusqu'au gestionnaire de notes. Reste le rôle des
   deux chemins d'allocation (`alloc_pick` / `alloc_core`). **Pitch stick du panneau** : son chemin
   n'est pas trouvé. Il n'emprunte pas `midi_bend_in` de façon visible, et
   `midi_routing_setup` n'ajoute que le canal global. Le plus simple : tester sur
   l'instrument (deux slots en Keyboard Focus hors Performance, bouger le stick).
2. ~~Pitch bend~~ : fait (section « Chemin du pitch bend »).
3. ~~Pression et morph~~ : fait (section « Molette, pression et morph par voix »). Reste
   le n° de paramètre du CC74 (Filter Freq) et le rôle exact de `slot+0x630`.
4. Politique exacte du vol de voix (bits de la clé) et limite éventuelle par slot.
5. Les deux destinations de `hw_write` et la cadence des mises à jour.
