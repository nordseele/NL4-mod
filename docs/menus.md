# Menus (System, MIDI, Sound) — étude en cours

But : ajouter au menu MIDI les options MPE. Celles qui sont voulues sont listées dans
`HANDOFF.md` : MPE Off / zone, destination de Y et de Z, courbes, plage de bend, canaux
A–D ignorés en mode MPE.

## Ce que montre le manuel (p. 43)

L'afficheur est à LED, quelques caractères. Une entrée de menu = une lettre ou un chiffre,
puis sa valeur. Menu MIDI : `G` canal global, `A b c d` canaux des slots, `t` Soft Thru,
`1` interface (P / U), `2` Local, `3` ?, `4` Program Change Mode (Sr / r / S / Off),
`5` Pitch Bend Mode (même plage), `6` Send CC, `7` Dump One, `8` Dump Program Bank.

## Firmware (lecture du 2026-11-19)  [sûr sauf mention]

- **Libellés en ASCII**, convertis pour l'afficheur ailleurs **[hyp.]** :
  - `0xc03c32b8…0xc03c3304` : `On `, `Of`, `Hej`, `%2d.`, `34`, ` 1`…` 4`, `c1`, `c2`, `r5`,
    `r7`, `y7`, `KO`, `Ft`, `AU`, `CL`, `OP`, ainsi que `%s.%s`, `%s.--` ;
  - `0xc03c3b48…` : ` S`, ` r`, `Sr`, `CC`, ` Ok`, `Abt`, `Pr`, `bn`.
- **Code du menu** vers `c00fe000`–`c0103500` (références à ces libellés).
- **Entrées = objets C++ avec vtable.** Exemple : `c00ffd28(this, valeur, tampon, taille)`
  formate une valeur 0…3 en `Of` / ` S` / ` r` / `Sr` par `c0175be8` (copie de chaîne
  **[hyp.]**). C'est l'entrée 16 d'une vtable en `0xc03c37a8` (début approximatif). Il y
  a une deuxième vtable, presque identique, en `0xc03c3748`, avec `c00ffd9c` :
  probablement Program Change Mode et Pitch Bend Mode. Ces vtables ont des sous-vtables
  (décalages −12, −24…, héritage multiple).
- Aucune adresse de ces vtables n'apparaît en littéral dans le code : les objets sont
  peut-être construits ailleurs, ou statiques. **À trouver ensuite : la liste des entrées
  du menu MIDI** (qui construit ces objets, comment le menu compte et parcourt ses
  entrées, où les réglages sont sauvegardés).
