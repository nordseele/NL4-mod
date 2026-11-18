# Patchs de l'OS et procédure d'essai

État au 2026-11-18. Rien n'a encore été installé sur le clavier.

## Fabrication

```sh
docker build -t nl4-arm tools/patch                          # une fois : GCC ARM + python3-lzo
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/pack_oscab.py ghidra/bin/os.cab build/palier1_os.cab
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier2   # ou palier3
tools/patch/make_updater.sh build/palier2_os.cab             # -> build/palier2_os.app
```

`build/` est hors git (il contient le firmware Clavia).

**Où va notre code.** Dans les 0xad0 octets libres entre la fin du CODE officiel
(0xc040b530) et la première variable statique (0xc040c000). La table de démarrage
(0xc0404fb4 : copie de 0x40b530 octets, puis remise à zéro de 0x526008 octets jusqu'à
0xc0931538) effacerait cette zone : `build.py` déplace le début de la remise à zéro
après notre code (deux mots), sans changer sa fin. Pour des patchs plus gros : la
section SRAM agrandie (`docs/faisabilite.md`).

**Garde-fous de `build.py`.** Chaque mot modifié est comparé à sa valeur d'origine avant
écriture ; pas de variables globales dans le patch ; taille bornée au trou ; liste du
code produit dans `build/<palier>/patch.lst`. `pack_oscab.py` relit ensuite tout le
fichier comme l'updater et le clavier.

**Installer un `os.cab`.** L'updater lit `Contents/Resources/os.cab` dans son propre
paquet (`CImageTransferFrame::ReadOSResource`), sans autre contrôle que ceux de
`docs/oscab-format.md`. `make_updater.sh` copie l'application depuis le dmg officiel,
remplace ce fichier, retire la quarantaine et la signe en ad hoc. Le lancement de la copie
n'a pas encore été essayé.

## Paliers

| Palier | Fichier | Contenu | SHA-256 de `os.cab` |
|---|---|---|---|
| 0 | dmg officiel | répétition : réinstaller l'OS 1.32 officiel | `42bbad95…ed16819` |
| 1 | `build/palier1_os.app` | OS officiel recompressé (LZO1X-999), sections identiques | `af3342c3…fee6240` |
| 2 | `build/palier2_os.app` | un slot écoute aussi les canaux 2 à 16 | `d821c4ee…5f92cfab` |
| 3 | `build/palier3_os.app` | palier 2 + bend par note ±48 sur les canaux 2 à 16 | `d1e20a19…63562ce09` |

### Palier 2 en détail (`tools/patch/palier2.c`)

Différences avec l'officiel, vérifiées par réextraction (4 mots + 0xc8 octets ajoutés) :

| Adresse | Avant | Après | Rôle |
|---|---|---|---|
| 0xc00e0540 | `bl 0xc00df898` | `bl 0xc040b530` | création des zones de notes → `mpe_zone_setup` |
| 0xc0404fc0 | 0x40b530 | 0x40b5f8 | table de démarrage : fin de la partie conservée |
| 0xc0404fc4 | 0x526008 | 0x525f40 | table de démarrage : remise à zéro (fin inchangée) |
| 0xc040aad8 | 4 | 36 | zones (port, canal) par cible de notes |

`mpe_zone_setup` appelle la création d'origine, puis, **si le canal MIDI global vaut 1**,
ajoute à chaque slot des zones « canal global » (qui suivent le Keyboard Focus) pour les
canaux 2 à 16, sur chaque port MIDI activé. Avec un autre canal global, le comportement est
celui d'origine.

**Risques connus.** (1) Mémoire : 36 zones au lieu de 4 par cible, ≈ 2,5 Ko par zone,
soit de l'ordre de 1 Mo de tas en plus **[estimation]**. (2) Les notes pourraient aussi
dépendre d'un masque de canaux que ce palier ne touche pas : c'est ce que l'essai dira.
Le bend, la pression et les CC des canaux 2 à 16 ne sont pas encore reçus (palier 3).

### Palier 3 en détail (`tools/patch/palier3.c`, avec `palier2.c`)

0x548 octets (code et tables), 12 mots modifiés, vérifiés par réextraction :

| Adresse | Avant | Après | Rôle |
|---|---|---|---|
| 0xc011ffac | `target_note_on` | `mpe_target_note_on` | pointeur dans `midi_noteon_dispatch` : pose le canal courant |
| 0xc00119f8 | `b slot_queue_note_on` | `b mpe_queue_note_on` | note `chan_of[slot][note]` |
| 0xc01bde58 | `note_on_build_voices` | `mpe_build_voices` | gestionnaire de notes vt[2] (type 3) |
| 0xc01bde5c | `note_event_handler` | `mpe_note_event` | vt[3] (type 4) : relie voix et canal |
| 0xc03bf32c, 0xc03ed740, 0xc03edc2c | `midi_bend_in` | `mpe_bend_in` | les trois tables de réception (bend, pression, CC) |
| 0xc001ccf4 | 1ʳᵉ instruction de `voice_pitch_offset` | `b mpe_voice_pitch_offset` | fonction remplacée : formule d'origine + bend de la voix |
| (+ les 4 mots du palier 2) | | | |

Fonctionnement :
1. `mpe_target_note_on` met le canal du message dans `g_chan` pendant l'appel d'origine ;
   dans la même pile d'appels, `mpe_queue_note_on` range `canal + 1` pour chaque
   (slot, note) qui part vers l'allocateur.
2. Après les méthodes qui démarrent les voix (types 3 et 4), `bind_voices` relit dans la
   table des notes les voix de (slot, note) et leur attribue ce canal.
3. `mpe_bend_in` : si la zone MPE est active et le canal est 2 à 16, la valeur est gardée
   dans `g_bend[canal]` et **n'atteint pas le slot** ; le canal 1 garde le bend commun
   (avec la plage et la courbe du programme).
4. `mpe_voice_pitch_offset` ajoute à chaque voix `bend × 384` (±8192 → ±48 demi-tons en
   16.16, linéaire, sans lissage).

**Limites connues.** Deux doigts sur la même hauteur dans le même slot partagent la même
entrée (niveau 1 de `docs/faisabilite.md`). L'arpégiateur et la Chord Memory ne sont
pas pris en compte. Pression et CC74 des canaux membres pas encore traités.

## Procédure d'essai sur l'instrument

Avant tout : le fichier officiel reste disponible (dmg dans `vendor/`). En cas d'OS qui ne
démarre pas : **allumer en tenant Shift + Store**, puis installer l'OS officiel.

1. **Palier 0.** Allumer en tenant Shift + Store (« RDY »), lancer l'updater officiel,
   installer. Vérifier que tout marche et que les programmes sont là.
2. **Palier 1.** Même chose avec `build/palier1_os.app`. Attendu : « Update completed
   successfully », instrument identique.
3. **Palier 2.** Même chose avec `build/palier2_os.app`. Puis, menu MIDI : canal global
   = 1. Jouer depuis l'Osmose ou le LinnStrument en mode MPE (zone basse, 15 canaux).
   Attendu : toutes les notes jouent sur le slot qui a le Keyboard Focus, quel que soit
   leur canal ; pas encore d'expression par note. Vérifier aussi le clavier local, les
   autres slots, et le démarrage à froid.
4. **Palier 3.** Même procédure avec `build/palier3_os.app`, canal global = 1.
   Contrôleur en MPE zone basse, **plage de bend des canaux membres réglée à ±48**.
   Attendu : chaque note suit son propre glissé ; le bend du canal 1 (ou le stick)
   déplace toutes les notes selon la plage du programme. Essayer aussi : deux notes
   glissées en sens contraires, note relâchée pendant un glissé (la release suit encore
   le canal), changement de programme.
5. Noter ce qui se passe et revenir à l'officiel si besoin.
