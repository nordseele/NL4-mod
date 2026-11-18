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
- [ ] Allocation des voix : pas encore étudiée dans le code.
- [ ] Réception MIDI (canal → slot, pitch bend, pression, CC) : pas encore étudiée.
- [ ] Où tourne la synthèse (ARM, DSP C674x interne, autre puce) : inconnu.

## Environnement

- Conteneur `pyghidra-nl4` (port 8003), projet `ghidra/nl4_ghidra.gpr`, programme
  `/nl4_os132_full.elf-0ddff2` (le suffixe change si on réimporte). Serveur MCP déclaré
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
| `Alloc State` | 0xc01bde98 | aucun pointeur direct trouvé (nom de debug ?) |

Les chaînes sans pointeur direct sont peut-être adressées par base + décalage. Il faut
aussi chercher des références à l'intérieur des chaînes.

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

1. Trouver la réception MIDI : le parseur des octets d'état (0x80/0x90/0xB0/0xD0/0xE0),
   puis la table canal → slot.
2. Suivre la note-on jusqu'à l'allocation des voix : réservoir de 20, vol de voix,
   unison / mono / legato.
3. Trouver la structure d'une voix et ce qui la met à jour (pitch, morph de vélocité).
4. Déterminer où tourne la synthèse : chercher du code C674x embarqué dans CODE ou un
   protocole vers une autre puce.
5. Reproduire les checksums CODE / ARM0 (piste `CCRC32X` dans le programme Mac).
6. Tester le « MPE léger » sur le vrai clavier.

## Risques

- Flasher une image modifiée peut **rendre le clavier inutilisable** si le chargeur la
  refuse ou si l'OS plante au démarrage. Aucune écriture tant qu'on ne sait pas comment
  récupérer (mode de mise à jour, réécriture du chargeur ou non).
- Droits : le firmware et les logiciels Clavia restent hors du dépôt. On ne publie que des
  notes, des formats et notre propre code (même ligne que
  [opennord](https://github.com/simonflore/opennord), `docs/LEGAL.md`).
