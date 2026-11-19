# Patchs de l'OS et procédure d'essai

État au 2026-11-19 : paliers 1 à 3 essayés sur l'instrument, tous réussis (« Résultats des essais » en fin de fichier).

## Fabrication

```sh
docker build -t nl4-arm tools/patch                          # une fois : GCC ARM + python3-lzo
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/pack_oscab.py ghidra/bin/os.cab build/palier1_os.cab
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier2   # ou palier3, palier4
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
remplace ce fichier, retire la quarantaine et la signe en ad hoc. La copie se lance sans
problème (essayé le 2026-11-19).

## Paliers

| Palier | Fichier | Contenu | SHA-256 de `os.cab` |
|---|---|---|---|
| 0 | dmg officiel | répétition : réinstaller l'OS 1.32 officiel | `42bbad95…ed16819` |
| 1 | `build/palier1_os.app` | OS officiel recompressé (LZO1X-999), sections identiques | `af3342c3…fee6240` |
| 2 | `build/palier2_os.app` | un slot écoute aussi les canaux 2 à 16 | `d821c4ee…5f92cfab` |
| 3 | `build/palier3_os.app` | palier 2 + bend par note ±48 sur les canaux 2 à 16 | `d1e20a19…63562ce09` |
| 4 | `build/palier4_os.app` | palier 3 + Y (CC74) par note → entrée vélocité de la voix | `adad2f09…965a8b51` |

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

### Palier 4 en détail (`tools/patch/palier4.c`, avec `palier2.c` et `palier3.c`)

0x648 octets (code et tables), 16 mots modifiés, vérifiés par réextraction (SRAM, ARM0 et
image 2 identiques à l'officiel). Le palier 3 reconstruit garde le même SHA-256 : rendre
`voice_chan` visible depuis `palier4.c` ne change pas le binaire.

| Adresse | Avant | Après | Rôle |
|---|---|---|---|
| 0xc03bf334, 0xc03ed748, 0xc03edc34 | `midi_cc_in` | `mpe_cc_in` | les trois tables de réception, entrée CC |
| 0xc0000480 | `synth_tick` | `mpe_synth_tick` | pool de l'initialisation : gestionnaire de niveau 4 |
| (+ les 12 mots du palier 3) | | | |

Fonctionnement :
1. `mpe_cc_in` : si la zone MPE est active, un CC74 des canaux 2 à 16 est gardé dans
   `g_y[canal]` et **n'atteint pas le panneau** (Filter Freq ne bouge pas pour tout le
   slot). Le CC74 du canal 1 et tous les autres CC suivent le chemin d'origine.
2. `mpe_synth_tick` appelle `synth_tick`, puis, pour chaque voix jouée (octet `+8` = 3,
   le test de `slot_set_param`) liée à un canal membre qui a déjà reçu un CC74 : si
   l'entrée vélocité de la voix (`voix[0x14]`) diffère du Y du canal, il rappelle
   `voice_apply_velocity(voix, Y)`. Ce rappel recalcule toutes les destinations du morph
   Velocity de cette voix, sans redéclencher les enveloppes (`fn_c002f898`, appelé en fin,
   n'appelle aucun des déclencheurs c0032ec0 / c00323b0 / c0032708).
3. Le Note On remet la vélocité de la note dans `voix[0x14]` ; au tick suivant, le Y courant
   du canal la remplace (le contrôleur MPE envoie son Y initial avant le Note On).
   Au plus un recalcul par voix et par tick, et seulement quand Y change.

Pourquoi `synth_tick` : le firmware y vide déjà la file de notes (`fn_c002787c` →
`note_queue_drain`), donc `voice_apply_velocity` y tourne déjà au Note On. On reste dans
le même contexte que le code d'origine.

**Limites connues.** (1) **Y remplace la vélocité** de la note pour toute la voix : la
courbe de vélocité de l'ampli (`voix+0x40` → `+0x354` / `+0x334`) suit aussi Y, donc avec
un programme dont l'enveloppe d'ampli réagit à la vélocité, Y module aussi le volume. Les
sources Y / Z distinctes de Velocity (`docs/faisabilite.md`) lèveront cette limite.
(2) Coût non mesuré : 20 voix × un recalcul au pire par tick **[≈ 10 µs par voix, hyp.]**.
(3) Un programme sans destination de morph Velocity ne réagit pas à Y (attendu).



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
5. **Palier 4.** Même procédure avec `build/palier4_os.app`, canal global = 1. Choisir
   (ou régler) un programme avec un **morph Velocity bien audible** (ex. Filter Freq ou
   niveau d'un oscillateur, Velocity morph) et l'enveloppe d'ampli **sans** vélocité si
   possible. Attendu : faire glisser le doigt en Y (LinnStrument) ou le mouvement
   correspondant de l'Osmose change le timbre **de cette note seulement** ; les autres
   notes tenues gardent le leur. Vérifier aussi : le bend par note (palier 3) marche
   encore ; le CC74 du canal 1 garde son effet habituel ; pas de saccades ni de notes
   perdues avec un accord de 8 notes et Y en mouvement continu (charge du processeur).
6. Noter ce qui se passe et revenir à l'officiel si besoin.

## Résultats des essais (2026-11-19)

| Palier | Résultat |
|---|---|
| 1 | OK. L'updater re-signé se lance ; le clavier accepte le fichier recompressé. |
| 2 | OK en Performance : les notes des canaux 2 à 16 jouent sur le slot en Keyboard Focus. Pas de bend ni de timbre par note (attendu). |
| 3 | OK : notes des canaux 2 à 16, **bend par note indépendant**. |
| 4 | OK, selon toute vraisemblance : Y agit note par note (essai sur une Performance à un seul layer, morph Velocity → cutoff). Le bend par note marche toujours. **Réglage difficile** : il faut construire le morph Velocity à la main, avec sa plage, programme par programme. |

Déroulé d'une mise à jour vu sur l'updater : « freeing some space for update », puis
transfert, puis redémarrage automatique du clavier. **Quitter l'updater après chaque
mise à jour** : sinon une nouvelle ouverture signale que le port (protocole) est déjà
utilisé.

**Ergonomie de Y (palier 4).** Le principe marche, mais il dépend d'un morph Velocity
réglé dans chaque programme, et la plage du morph se règle mal depuis le panneau. Pistes :
la fonction d'aide « convertir pour le MPE » (poser un morph Velocity → cutoff par
défaut), ou une destination fixe pour Y, indépendante des morphs du programme.

**Collision avec les canaux des slots.** Hors Performance, un slot réglé sur un canal
MIDI propre (ex. slot C sur le canal 4) joue aussi les notes MPE de ce canal, en plus du
slot en Keyboard Focus. À traiter quand le MPE aura son entrée de menu : soit ignorer
les canaux propres des slots pendant que la zone est active, soit le signaler.
