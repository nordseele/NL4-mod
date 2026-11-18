# Réception MIDI et voix — notes de recherche (OS v1.32)

Les noms viennent de `tools/symbols.txt`, que l'ELF porte (`tools/rebuild.sh`). Le
pseudo-C complet se régénère avec `tools/dump_decomp.py` dans `ghidra/bin/decomp.c`
(hors git). Légende : **[sûr]** lu dans le code ; **[hyp.]** déduit, à confirmer.

## Chaîne de réception MIDI

```
USB-MIDI (paquets de 4 octets, CIN → longueur)
  usbmidi_rx_packets / usbmidi_rx_packets2      c013e950 / c013e810
    └─ midi_parse_byte(parser, octet)           c013c6e8
         running status, SysEx (F0…F7), temps réel F8–FF
         └─ récepteur->vtable[...]  (objet installé après la construction du port)
```

**[sûr]** Méthodes du récepteur, appelées par `midi_parse_byte` :

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

Le parseur transmet donc bien l'aftertouch polyphonique et la pression de canal, avec le
canal. **Pas encore vu :** ce que le récepteur du Lead 4 en fait (ignoré, ou routé vers
une modulation), ni où se fait l'aiguillage canal → slot. Le port est construit avec un
récepteur nul (`usbmidi_port_ctor(…, 0)`) : le vrai récepteur est branché plus tard. Il
reste à le trouver (chercher qui écrit le champ `parser+0`). Le port DIN a sans doute
son propre parseur.

## Création des slots et des voix  [sûr]

`synth_create_slots_and_voices(4, …)` (c0010a64), appelée depuis le démarrage :

- 4 × `slot_ctor(obj, i)` (0x4B4 octets, i = 0…3). Chaque slot contient un
  `slot_engine` (0x8B8 octets, `slot_engine_ctor`) avec des blocs de paramètres par
  slot de 0xA0 octets (2 × 0x50).
- 20 × `voice_ctor(obj, i)` (0x598 octets, i = 0…19). Chaque voix s'enregistre dans un
  **tableau global de 20 pointeurs** en `0xc04b0040` (zone RAM non initialisée).
- Tableau des 4 slots en `0xc040d3b0`.

Les 20 voix forment donc un réservoir unique, partagé par les 4 slots, ce qui confirme
le manuel.

## Voix  (0x598 octets)

- `+0x00` = numéro de voix. Plusieurs sous-objets reçoivent aussi le numéro (oscillateurs,
  enveloppes…). **[sûr]**
- `voice_pitch_to_hw` (c002cd30) et `voice_pitch_mod_update` (c002ec1c) calculent la
  **hauteur par voix** : base + modulation (champs +0x160 / +0x17C / +0x168), table
  exponentielle (256 entrées exposant + 256 mantisse) → fréquence, écrite par
  `hw_write(bit0(id), adresse, valeur)` (c014f0f0, ~300 appels). **[sûr]**
- Le numéro matériel de voix (`+0x118`) se découpe en `bit0` = sélection d'une
  destination parmi deux, `>>1` = index. **[hyp.]** Deux puces / cœurs de synthèse,
  10 voix chacun.
- **Conséquence pour le MPE [hyp. forte]** : le pitch est déjà calculé et poussé
  **voix par voix** par l'ARM. Un pitch bend par note revient à remplacer, pour une voix,
  la composante bend commune au slot par une valeur propre à la voix. Pas besoin de
  toucher au moteur de son, si les autres modulations suivent le même chemin.

## Allocation des voix

`note_event_handler` (c00263d4) consomme une file d'événements de note (0x800 entrées de
16 octets). Pour chaque note, il retrouve l'entrée active, son mode (1/2/3 — **[hyp.]**
poly / mono / legato, ou gestion de l'unisson) et la liste de ses voix, puis déclenche ou
relâche chaque voix (`fn_c0032ee0`, `FUN_c00320b8`, `fn_c0037dd4`, `FUN_c00323d0`).

Objet allocateur (global, `*(DAT_c00268d0 - 0xca0)`) **[sûr pour la structure]** :

| Champ | Sens |
|---|---|
| +0x04 | compteur d'événements (horodatage) |
| +0x68 | dernière valeur de référence reçue |
| +0x6C | nombre de notes actives |
| +0x70 | tableau de pointeurs vers les notes actives |

Note active :

| Champ | Sens |
|---|---|
| +0x00 | clé de tri (priorité / âge) — tri de Shell dans `alloc_note_on` / `alloc_update_sort` |
| +0x04 | propriétaire ou horodatage (comparé à un identifiant dans `alloc_has` / `alloc_count_of`) |
| +0x14, +0x18 | identité de la note (2 mots : **[hyp.]** source/slot et numéro de note) |
| +0x1C | état (0, 1, 2, 3 ; 2 = tenue ? 1 et 3 exclus de la recherche de note-off) |
| +0x20 | drapeau mis à 1 au relâchement |
| +0x28 | nombre de voix utilisées (unisson > 1) |
| +0x2C | voix (pointeurs ; numéro de voix en +8) |

Les listes de voix renvoyées font 20 entrées + un compteur en +0x50.

`alloc_note_on` (c001b024) prépare et trie, puis appelle **`alloc_core` (c00198a4, 3,8 Ko)**,
le cœur de l'allocation et du vol de voix. **Pas encore lu.**

## Questions ouvertes, par ordre d'utilité pour le MPE

1. **Récepteur MIDI** : son aiguillage canal → slot, et ce qu'il fait de 0xA0 / 0xD0 / CC74.
2. **`alloc_core`** : comment un slot obtient ses voix (limite par slot ? priorité ? vol
   de la plus ancienne ?), et où est mémorisé le lien voix → canal.
3. **Pitch bend** : où le bend reçu est converti par le Bend Range (1–12, 24, 48) puis
   additionné à la hauteur des voix du slot. C'est le point d'injection du bend par note.
4. **Modulations par voix** : le morph de vélocité est appliqué par voix ; trouver où, pour
   y brancher la pression (Z) et le CC74 (Y) en continu.
5. Confirmer les deux destinations de `hw_write` (deux DSP ? FPGA ?) et la cadence des
   mises à jour (bloc audio ? 1 kHz ?), pour savoir si 20 mises à jour par voix passent.
