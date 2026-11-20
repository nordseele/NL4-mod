# Menus (System, MIDI, Sound) : étude

But : ajouter au menu MIDI les options MPE. Celles qui sont voulues sont listées dans
`HANDOFF.md` : MPE Off / zone, destination de Y et de Z, courbes, plage de bend, canaux
A–D ignorés en mode MPE.

## Ce que montre le manuel (p. 43)

L'afficheur est à LED, quelques caractères. Une entrée de menu = une lettre ou un chiffre,
puis sa valeur. Menu MIDI : `G` canal global, `A b c d` canaux des slots, `t` Soft Thru,
`1` interface (P / U), `2` Local, `3` Control Change Mode (Sr / r / S / Off),
`4` Program Change Mode (même plage), `5` Pitch Bend Mode (même plage), `6` Send CC,
`7` Dump One, `8` Dump Program Bank. « Local » revient à On à chaque allumage.

## Libellés  [sûr sauf mention]

- **Libellés en ASCII**, convertis pour l'afficheur ailleurs **[hyp.]** :
  - `0xc03c32b8…0xc03c3304` : `On `, `Of`, `Hej`, `%2d.`, `34`, ` 1`…` 4`, `c1`, `c2`, `r5`,
    `r7`, `y7`, `KO`, `Ft`, `AU`, `CL`, `OP`, ainsi que `%s.%s`, `%s.--` ;
  - `0xc03c3b48…` : ` S`, ` r`, `Sr`, `CC`, ` Ok`, `Abt`, `Pr`, `bn`.
- Lettre de l'entrée : chaîne d'un caractère passée au constructeur (`"1"` en
  `0xc01ca280`, `"G"` en `0xc03c21a8`, `"t"` en `0xc0404880`…).

## Construction des menus (2026-11-19)  [sûr]

`menus_build` (`fn_c00fb7a4`, objet de 0xe0 octets rangé en `0xc04edce8`, appelé par
`fn_c00fc4a8` au démarrage avec l'objet application `app`) crée les pages, puis chaque
entrée par `operator_new` + constructeur, et l'ajoute par
`menu_page_add(liste, n° de page, entrée)` (`fn_c0124cec`). Une page (0x238 octets) garde
son compte en `+0x24` et ses entrées en `+0x28…` : **131 places**, donc de quoi ajouter
des entrées. Le n° de page est en `page+0x234`.

| Champ de `menus_build` | Page | Entrées (dans l'ordre) |
|---|---|---|
| `[0x2f]` | System | 1…8, puis 4 entrées A–d (`fn_c00fecbc(i)`) |
| **`[0x30]`** | **MIDI** (`fn_c00fd0b0`) | **G, A, b, c, d, t, 1…8** (tableau suivant) |
| `[0x31]` | Sound | 1 (`fn_c0100ed8`, ajoutée après le menu MIDI), 2…5 |
| `[0x2d]`, `[0x2e]`, `[0x32]`–`[0x34]` | autres (Mutator, etc., non identifiées) | |

Menu MIDI, entrée par entrée :

| Lettre | Constructeur | Taille | Vtable principale | N° du réglage global |
|---|---|---|---|---|
| G | `fn_c0101cd8` | 0x60 | `0xc03c45d0` | 6 (déf. 0, max 16 = Off) |
| A b c d | `fn_c0101da8(i)` | 0x64 | `0xc03c4350` | aucun : pas dans la table globale |
| t | `fn_c0101d40` | 0x60 | `0xc03c4490` | 0x1a (déf. 16 = Off) |
| 1 Interface | `fn_c010173c` | 0x60 | `0xc03c47b0` | 7 |
| 2 Local | `fn_c01000b4` | 0x60 | `0xc03c35d8` | 5 (non sauvegardé, conforme au manuel) |
| 3 CC Mode | `fn_c0100120` | 0x60 | `0xc03c3678` | 8 |
| 4 PC Mode | `fn_c010018c` | 0x60 | `0xc03c3718` | 9 |
| 5 PB Mode | `fn_c01001f8` | 0x60 | `0xc03c37b8` | 0x1d |
| 6 Send CC | `fn_c010028c` | 0xa4 | | (action) |
| 7, 8 Dump | `fn_c0100504`, `fn_c010066c` | 0xac | | (actions) |

## Une entrée de menu  [sûr]

- Base : `menu_entry_ctor` (`fn_c0125368`), **7 sous-objets** de 12 octets (en `+0`,
  `+0xc`, …, `+0x48`), chacun abonné au bus par `midi_subscribe`. Champs : `+0x54` = `app`,
  `+0x58` = 3ᵉ paramètre, `+0x5c` = libellé, `+0x51` = entrée active (lu par
  `menu_entry_is_active`, `fn_c0125514`).
- Les constructeurs des entrées 2 à 5 posent les 7 vptr à partir d'**une seule base**
  `0xc03c35d0` (+8, +0x48, +0x58…) : c'est pourquoi aucune vtable n'apparaît en littéral.
- Vtable principale (indices) : `[12]` = formatage `(this, valeur, tampon, taille)` (ex.
  `fn_c00ffd28` : 0…3 → `Of` / ` S` / ` r` / `Sr`), `[13]` = affichage
  `(this, tampon, taille)` = `formatage(global_get(app, n°))`, `[5]` = tour de bouton.
- **Tour de bouton** (`fn_c0100a20` pour PB Mode) : n'agit que si l'entrée est active et
  si l'événement est de type 2 ; puis
  `global_step(app, n°, 0xc08ee8b8, 1, delta)` (`fn_c00e2824`).
- **Leçon du palier 5, encore vraie ici** : le tour de bouton arrive par le sous-objet
  `+0xc` (abonné au bus), dont la vtable (`0xc03c37f8` pour PB Mode) contient le relais
  `sub r0, r0, #0xc ; b fn_c0100a20`. Une nouvelle entrée doit donc fournir **sa vtable
  principale et celle du sous-objet `+0xc`** (au moins).

## Réglages globaux  [sûr]

- Lecture : `global_get(app, n°)` (`fn_c00e270c`), écriture :
  `global_step(app, n°, source, borne, delta)` (`fn_c00e2824`). Le modèle est `app[0x52]`
  (`app+0x148`), construit par `global_model_ctor` (`fn_c00ed8b0`, nom interne
  « CRouterParam » par défaut). Sa table de paramètres (`fn_c00edda0` →
  `param_table_ctor`, `fn_c010e4f0`) reçoit **le tableau de descripteurs `0xc03bff00` et
  le nombre 0x22** (34 réglages, n° 0 à 0x21). La table alloue ses tableaux d'après ce
  nombre : en ajouter ne demande que de copier le tableau ailleurs et de changer
  pointeur + nombre.
- `global_step` (via `fn_c011eeb8`) : valeur + delta, bornée si `borne = 1`, sinon en
  boucle de 0 à max.
- Descripteur = 7 mots : `[n°, défaut, max, bits, ?, drapeaux, CC]`. L'octet `+0x15`
  (drapeaux 0x100) = **sauvegardé** ; un changement marque la table modifiée
  (`table+0x1c`) et appelle `table+0x20`. CC = n° de CC MIDI associé, −1 sinon (id 3 →
  CC 119, id 4 → CC 115, id 0x18 → CC 58).

| n° | déf. | max | bits | sauv. | rôle connu |
|---|---|---|---|---|---|
| 0 | 0 | 127 | 0 | non | |
| 1 | 0 | 1 | 1 | oui | |
| 2 | 0 | 99 | 7 | oui | |
| 3 | 0 | 3 | 2 | oui | CC 119 |
| 4 | 1 | 15 | 4 | oui | CC 115 |
| 5 | 1 | 1 | 1 | non | Local (MIDI 2) |
| 6 | 0 | 16 | 5 | oui | canal global (MIDI G), 16 = Off |
| 7 | 2 | 2 | 2 | oui | interface (MIDI 1) |
| 8 | 3 | 3 | 2 | oui | CC Mode (MIDI 3) |
| 9 | 3 | 3 | 2 | oui | PC Mode (MIDI 4) |
| 0xa | 6 | 12 | 4 | oui | Transpose (System 2), 6 = 0 |
| 0xb | 50 | 100 | 7 | oui | Fine Tune (System 3), 50 = 0 |
| 0xc | 2 | 4 | 3 | oui | |
| 0xd | 0 | 2 | 3 | oui | Sustain Pedal Polarity (System 4) |
| 0xe | 0 | 4 | 3 | oui | Ctrl Pedal Type (System 5) |
| 0xf | 0 | 1 | 2 | oui | Ctrl Pedal Mode (System 6) |
| 0x10 | 0 | 9 | 4 | oui | Ctrl Pedal Gain (System 7) |
| 0x11, 0x12 | | | | oui | (0x11 : entrées `0xc03c3e90` / `0xc03c3f68`, page non identifiée) |
| 0x13 | 0 | 1 | 1 | oui | Delay Mode (Sound 2) |
| 0x14 | 50 | 100 | 7 | oui | Vibrato Rate (Sound 3) |
| 0x15 | 25 | 50 | 6 | oui | Vibrato Amount (Sound 4) ; mis à 15 par le convertisseur v2 → v3 |
| 0x16–0x18 | | | | oui | |
| 0x19 | 0 | 2 | 2 | oui | (Mst Clk Kbd Sync, Sound 1, 3 valeurs ? **[hyp.]**) |
| 0x1a | 16 | 16 | 5 | oui | Soft Thru (MIDI t), 16 = Off |
| 0x1b | | | | non | (entrée `fn_c0102d04`, historique du Mutator ?) |
| 0x1c | 0 | 1 | 0 | non | Impulse Morph Protect (System 8) |
| 0x1d | 3 | 3 | 2 | oui | PB Mode (MIDI 5) |
| 0x1e | 1 | 1 | 1 | oui | |
| 0x1f, 0x20 | 0 | 1 | 1 | non | |
| 0x21 | 0 | 0 | 31 | oui | ? (max 0 : toujours 0) |

## Sauvegarde des réglages globaux  [sûr sauf mention]

- Type de fichier n° 1 du gestionnaire de stockage (`storage_ctor`, `fn_c00faaf4` ;
  `fn_c00f9ec8`), lié à la référence du modèle global (`0xc04e6b5c` = `0xc04e6ac8 + 0x94`,
  remplie par `app_midi_graph_ctor`).
- **Enregistrement de taille fixe : 38 octets** (`fn_c00fa060` : champ `+0x18 = 0x26` ;
  tampon alloué par `fn_c0122b64`).
- Format : **16 bits de version (3)**, puis chaque réglage sauvegardé dans l'ordre des
  n°, sur son nombre de bits, **sans étiquette** (`param_table_load`, `fn_c010ee60` →
  `fn_c010ec60`). Une valeur hors de `0…max` revient au défaut. Total en 1.32 :
  144 bits = 18 octets : **il reste 20 octets (160 bits) libres** dans l'enregistrement.
- Contrôle par le calcul : le convertisseur v2 → v3 (`fn_c00f8b18`) réécrit 6 bits au bit
  88 et la version au bit 0 ; le bit 88 tombe exactement sur le n° 0x15.
- Versions : `fn_c00f83e4` monte la version lue pas à pas par la table `0xc03c1af0`
  (seul v2 → v3 existe) ; version inconnue (> 2 et ≠ 3) → erreur 6. Le lecteur de bits
  (`fn_c012a950`) ne contrôle pas la fin du tampon.

## Ce que cela permet pour les options MPE  [hyp., à valider]

1. ~~Nouveaux réglages à partir de 0x22~~ : **essayé, le clavier ne redémarre plus**
   (palier 10, 1ʳᵉ version). L'écouteur des réglages globaux (`fn_c00e3f70`) range des
   tableaux de 34 cases dans son propre objet : **le nombre de réglages est figé à 34**.
2. Retenu : le réglage **0x21** (sauvegardé sur 31 bits, max 0, inutilisé) porte nos
   options en champs de bits ; on ne change que son maximum.
3. **Nouvelles entrées** : appeler `menu_page_add` sur la page MIDI à la fin de
   `menus_build`, avec des entrées clonées de PB Mode (constructeur `fn_c01001f8`, puis
   nos copies de la vtable principale et de celle du sous-objet `+0xc`, avec nos
   fonctions d'affichage, de formatage et de tour de bouton pour nos n°).
4. Lecture par notre code MPE : `global_get(app, n°)`, à la place du « canal global = 1 »
   des paliers 2 à 9.

## Navigation (2026-11-20)  [sûr]

- Ouverture : `menus_on_button` (`fn_c00fb204`, vtable de l'objet menus `0xc03c2178`)
  reçoit les boutons du panneau. Avec Shift, 0x1b / 0x1c / 0x1d ouvrent System / MIDI /
  Sound (slots A, B, C) ; 0x14 et 0x15 ouvrent deux autres pages. Changement de page :
  `menu_list_show_page` (`fn_c0124e7c`), page courante en `liste+0x88`.
- Molette : `menus_on_dial` (`fn_c00fb18c`) reçoit l'événement de type 2. **Sans Shift**
  (bit 0 de `ev+4`, lu par `fn_c0131938(0, …)`), elle déplace l'entrée courante :
  `menu_list_step` (`fn_c0124e6c`) fait `entrée = borne(courante + delta, 0, compte − 1)`
  sur `page+0x24`. **Avec Shift**, c'est l'entrée active qui reçoit le tour (son `[5]`).
- Donc des entrées ajoutées à la fin de la page MIDI sont atteintes **sans autre
  changement**. L'entrée choisie passe active (`+0x51 = 1`) puis `vt[3]` ; elle se
  désactive par `vt[4]` (après `vt[11]`, qui peut refuser).

## Affichage  [sûr sauf mention]

- `vt[2]` d'une entrée rafraîchit l'afficheur : `vt[13]` écrit la valeur dans un tampon
  de 4 octets (`0xc04edd1c`), puis
  `led_printf(afficheur, "%s.%s", libellé, valeur)` (`fn_c0145530`, la même fonction qui
  affiche « 1.32 » au démarrage). Pour PB Mode : « 5.Sr ».
- L'ARM envoie de l'**ASCII** au pilote (`fn_c01452f0`, un caractère par position). La
  police 7 segments n'est dans aucune des images de `os.cab`, en octets, en mots ou en
  logique inversée : la conversion est faite ailleurs **[hyp. : matériel ou autre
  processeur]**.
- Lettres sûres, car déjà affichées par l'OS : chiffres, `A b C c d E e F G H i j K k L
  n O o P r S t U u v y`, `-` et le point. Exemples : `Abt`, `Hej`, `PSt`, `CPy`, `FuL`,
  `rcv`, `E.Sy`, `E.vE`, `E.Ck`, `KO`, `Ft`, `AU`, `CL`, `OP`, `y7`, `r5`. Les libellés
  d'entrée existants : `1`…`8`, `G`, `A b c d`, `t`. Libres pour nos entrées : `9`, et
  par exemple `P` (MPE), `y`, `U`, `H`, `L`, `n`, `r`, `S`.

## Écriture en flash  [sûr]

- Objet de sauvegarde des réglages globaux, créé par `storage_ctor` (vtable
  `0xc03c2090`, écoute le modèle global par `fn_c0123120`) :
  - un réglage sauvegardé change → `fn_c00fafa4` met « à écrire » (`+0x18 = 1`) ;
  - **minuterie de 2000 ms** (`fn_c01320a0(…, 2000)`, rappel `0xc00fb094`) : si
    l'écriture n'est pas bloquée (`+9`), `fn_c00fb048` regarde si le modèle a changé
    (routeur `vt[13]`) et lance l'écriture ;
  - `fn_c00fafe0` écrit l'enregistrement (`gestionnaire->vt[0]`) puis efface la marque
    (routeur `vt[14]`) ;
  - un événement du bus `0xc08eee38` force l'écriture (valeur 0) ou la bloque (`+9`).
- Conséquence : nos réglages ajoutés à la table seront écrits **sans code de notre
  part**, au plus 2 s après un changement, comme les réglages d'origine.

Reste à lire : les n° 0xc, 0x11, 0x12, 0x16 à 0x18 (sans effet sur le projet), et où
sont rangés les canaux A–d des slots (page MIDI, `fn_c0101da8`) ; ce sera utile pour
« canaux A–D ignorés en mode MPE ».
