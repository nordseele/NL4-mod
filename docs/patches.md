# Patchs de l'OS et procédure d'essai

État au 2026-11-19 : paliers 1 à 3 essayés sur l'instrument, tous réussis (« Résultats des essais » en fin de fichier).

## Fabrication

```sh
docker build -t nl4-arm tools/patch                          # une fois : GCC ARM + python3-lzo
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/pack_oscab.py ghidra/bin/os.cab build/palier1_os.cab
docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier2   # ou palier3, palier4, palier5
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
remplace ce fichier, lui donne **son propre identifiant et son nom** (`CFBundleIdentifier`
`….<palier>`, `CFBundleName` = nom du palier, visible dans la barre de menus), retire la
quarantaine et la signe en ad hoc. Sans identifiant propre, macOS peut ramener au premier
plan une copie déjà ouverte (ou en choisir une autre depuis Spotlight / le Dock) et
reflasher l'OS précédent : c'est la cause soupçonnée du diagnostic sans effet du
2026-11-19. La copie se lance sans
problème (essayé le 2026-11-19).

## Paliers

| Palier | Fichier | Contenu | SHA-256 de `os.cab` |
|---|---|---|---|
| 0 | dmg officiel | répétition : réinstaller l'OS 1.32 officiel | `42bbad95…ed16819` |
| 1 | `build/palier1_os.app` | OS officiel recompressé (LZO1X-999), sections identiques | `af3342c3…fee6240` |
| 2 | `build/palier2_os.app` | un slot écoute aussi les canaux 2 à 16 | `d821c4ee…5f92cfab` |
| 3 | `build/palier3_os.app` | palier 2 + bend par note ±48 sur les canaux 2 à 16 | `d1e20a19…63562ce09` |
| 4 | `build/palier4_os.app` | palier 3 + Y (CC74) par note → entrée vélocité de la voix | `adad2f09…965a8b51` |
| 5 | `build/palier5_os.app` | palier 3 + Y (CC74) par note → **morph Wheel** de la voix (remplace le palier 4) | `0bf5f7a5…21f97fd6` (3ᵉ version, relais CC corrigé) |
| 6 | `build/palier6_os.app` | palier 5 + **Z (pression) → Level** par note, Y lissé, quantités Wheel sur 16 bits (remplace le palier 5) | `d3675dcd…29aa009b0` |
| 7 | `build/palier7_os.app` | palier 6, mais Y n'applique que les paramètres morphés, un par un, comme la molette | `d7aa9d2c…a6e78e85bc9f1a55` |
| 8 | `build/palier8_os.app` | palier 7, Z → Level jouable : Poly AT accepté, courbe Z², Z remplace la vélocité pour le volume, relâche préservée | `8e2a4db9…5ede0b8578d18721` |
| 9 | `build/palier9_os.app` | palier 8 + **même hauteur sur plusieurs canaux** (note renumérotée, hauteur corrigée par voix) | `f877453a…3ee5d8a4` (2ᵉ version : Note Off répétable) |
| 10 | `build/palier10_os.app` | palier 9, **MPE réglé au menu MIDI** (P, r, y, L), sauvegardé ; ne dépend plus du canal global | `74acf1e8…91ac54d5` (3ᵉ version, **essayée : OK** ; 2ᵉ `b74493fb…` : démarre, `P` n'agit qu'après redémarrage ; 1ʳᵉ `5b3caf19…` : ne redémarre pas) |
| 11 | `build/palier11_os.app` | palier 10 + destinations de Y et Z au choix (molette / vélocité / Filter Freq / volume pour Z), courbes, Z × vélocité, canaux A–D ignorés en MPE ; MPE sur `E`, Z sur `P` | `1b7fb57c…c2274204` (4ᵉ version, **essayée : OK** : `LE` = volume × Z ; 3ᵉ `f5db51f3…` : `LE` marche, ≈ 6 dB ; 1ʳᵉ et 2ᵉ : `LE` sans effet) |
| 11 diag | `build/palier11diag_os.app` | palier 11 + vélocité, `voix+0x3c` et gain de volume de la dernière note au menu | `d17d8c96…246fc5b3` (avec la 4ᵉ version ; relevé fait avec `0dffbea9…`) |
| 9 bis | `build/palier9dead_os.app` | diagnostic : palier 9 avec ses deux enveloppes de notes dans la zone morte du palier 10 | `d45724c1…6ae545b92` |

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

### Palier 5 en détail (`tools/patch/palier5.c`, avec `palier2.c` et `palier3.c`)

Remplace le palier 4 : Y ne prend plus la place de la vélocité, il agit comme **un morph
Wheel propre à chaque note**. Les programmes d'usine qui ont un morph Wheel parlant
réagissent donc à Y sans réglage. 0xa00 octets sur les 0xad0 du trou (il reste 0xd0).
14 mots modifiés, vérifiés par réextraction (SRAM, ARM0 et image 2 identiques).

**2ᵉ version (2026-11-19).** La 1ʳᵉ enveloppait `prog_morph_amount_in` pour capter les
quantités Wheel : sur l'instrument, Y n'avait aucun effet. Cette méthode n'est appelée qu'à
l'**édition** d'un morph ; au chargement, les quantités Velocity passent par un autre
chemin (`c00efbb4`), et les quantités Wheel restent dans le modèle de paramètres du
programme, qui calcule le morph Wheel lui-même. La 2ᵉ version **interroge le modèle**.

| Adresse | Avant | Après | Rôle |
|---|---|---|---|
| 0xc01bde58, 0xc01bde5c | `note_on_build_voices`, `note_event_handler` | `mpe5_…` | ceux du palier 3, plus une demande de recalcul |
| 0xc01202a8 | `b midi_cc_in` | `b mpe_cc_in` | relais du sous-objet CC (voir ci-dessous) |
| 0xc0000480 | `synth_tick` | `mpe_synth_tick` | comme le palier 4, autre contenu |
| (+ les 10 autres mots du palier 3) | | | |

Fonctionnement :
1. **Quantités Wheel.** Modèle du slot s : `*(0xc04eb824[s] + 0x1a4)` (objet programme du
   slot, champ posé par son constructeur `fn_c00e7660`). Pour chacune des 78 destinations
   (table 0xc04ed3fc, 3 octets par destination, `[1]` = entrée de morph) :
   `fn_c0118c24(modèle, {modèle+0x30, n°}, 0)` rend la quantité Wheel, rangée dans
   `wq[s][entrée]` (bornée à ±127). Relu à chaque recalcul (Note On, tous les 32 ticks), un
   slot par tick au plus une fois. Numérotation **[hyp. forte]** : 0 = Wheel, 1 = Velocity,
   2 à 8 = les 7 Impulse (manuel : 9 sources ; la fonction d'édition c00eb378 envoie 2 à 8).
2. **CC74 des canaux membres** : gardé par canal, n'atteint pas le panneau (palier 4).
3. **Application, dans `synth_tick`** : pour une voix jouée sur un canal membre, quand son Y
   change, après un Note On, ou tous les 32 ticks : `base += (Y + 1) × qté Wheel / 128` sur
   les entrées de morph du slot, `voice_apply_velocity(voix, vélocité de la note)`, puis
   la base est rendue. Les entrées sont partagées par les voix du slot, mais rien ne
   tourne entre l'ajout et le retrait (même contexte que le palier 4).
4. Le recalcul tous les 32 ticks rattrape un réglage du panneau : `slot_set_param`
   recalcule les voix paramètre par paramètre, sans notre terme.

**Limites connues.** (1) La molette physique agit toujours sur toutes les notes ; Y
s'ajoute à elle. (2) Si Y ne fait toujours rien : soit la source 0 n'est pas
Wheel, soit le modèle n'est pas celui du slot ; essayer aussi d'éditer un morph Wheel. (3) Quantités bornées à ±127 (pleine échelle d'un
paramètre, comme Velocity). (4) Destinations de l'arpégiateur ignorées. (5) Coût : comme
le palier 4, plus un recalcul de chaque voix MPE tous les 32 ticks.

**3ᵉ version (2026-11-19) : la vraie cause.** Les CC n'arrivent pas à `midi_cc_in` par
l'entrée de vtable remplacée aux paliers 4 et 5. Chaque abonné MIDI est un objet à
plusieurs sous-objets (un par type de message : bend, pression, « autres CC »…), et le bus
appelle l'entrée [1] de la vtable **du sous-objet**. Pour le bend, c'est le sous-objet
principal, d'où le succès du palier 3. Pour les CC, c'est un relais partagé par les trois
classes, `0xc01202a4 : sub r0, r0, #24 ; b midi_cc_in`, qui saute directement. **Le
CC74 des canaux membres n'a donc jamais atteint notre code, ni au palier 4 ni au palier 5**
(l'effet entendu au palier 4 venait sans doute de la vélocité du jeu). Correction : le saut
du relais (0xc01202a8) vise `mpe_cc_in`. La pression a le même relais (`0xc0120390 → b
midi_pressure_in`) : à brancher de la même façon pour Z. Le diagnostic garde la même
correction (SHA-256 `e25ec6a2…5e08f877`).

### Palier 5, version de diagnostic (`build/palier5diag_os.app`)

La 2ᵉ version du palier 5 n'a pas d'effet non plus (essai du 2026-11-19). Pour savoir où le
chemin s'arrête sans sortie de débogage, `palier5diag.c` (= `palier5.c` avec `DIAG`)
**transpose toutes les notes d'un slot** selon ce que la lecture du modèle a trouvé pour
ce slot. Hauteur normale jusqu'à la lecture (déclenchée par la 1ʳᵉ note MPE qui reçoit un
Y), puis un **saut** :

| Saut | Sens |
|---|---|
| aucun | lecture jamais faite : voix MPE non reconnue ou slot de la voix ≥ 4 |
| +24 (deux octaves) | pas de modèle pour ce slot (`0xc04eb824[slot] + 0x1a4` nul) |
| +12 (octave) | modèle lu, aucune quantité ni Wheel (source 0) ni Velocity (source 1) |
| +7 (quinte) | quantités Velocity trouvées, mais pas Wheel : la source 0 n'est pas Wheel |
| +5 (quarte) | quantités Wheel trouvées : si Y ne fait toujours rien, c'est l'application |

Essai : programme avec un morph Wheel **et** un morph Velocity, canaux A–D sur Off, canal
global = 1 ; tenir une note au clavier du Nord, toucher une note du LinnStrument en
bougeant Y, écouter si la note tenue saute.

1ʳᵉ mouture (2026-11-19) : +5 permanent dès l'allumage, donc **inaudible sans référence**
(toutes les notes décalées pareil) ; l'essai « aucune transposition » ne permettait pas de
conclure. SHA-256 de la 2ᵉ mouture : `7d7ae111…74ced0cc`.

### Palier 6 en détail (`tools/patch/palier6.c`, avec `palier2.c` et `palier3.c`)

Remplace `palier5.c` (même structure) et ajoute :

- **Z → Level.** La pression arrive par un relais de sous-objet, comme les CC :
  `0xc0120390 : sub r0, #12 ; b midi_pressure_in`. On remplace le saut (`0xc0120394`) par
  `b mpe_pressure_in`. Le message de pression porte la note en `+8`, ou −1 pour un Channel
  Pressure (`c013c1c8`). Seul ce dernier est pris, et seulement sur les canaux 2 à 16 ; le
  Poly AT reste au firmware. Le gain d'ampli de la voix est calculé dans
  `voice_push_params` (`voix+0x334`, 8.23, 0x800000 = 1, depuis la courbe de vélocité
  `voix+0x40`). Il est envoyé au SHARC par `amp_gain_write(voix+0x35c, gain)` (c0061a08 :
  SHARC `n & 1`, DM `0x9245c + (n >> 1) × 0x40`). Dans `synth_tick`, on renvoie
  `gain × Z`. Il est renvoyé quand Z bouge, après chaque recalcul de la voix par Y (qui a
  renvoyé le gain d'origine), au début d'une note et tous les 32 ticks. Un canal sans
  pression reçue garde le gain d'origine.
- **Quantités Wheel sur 16 bits.** Le palier 5 les bornait à ±127. Le firmware passe les
  quantités au moteur telles quelles (`prog_morph_amount_in` : `quantité << 16` →
  `entrée.qté`, c0011fa8), donc une quantité plus grande était coupée et Y à 127
  n'atteignait pas l'effet de la molette à fond (essai du 2026-11-19).
  **[hyp. : à confirmer à l'essai]** Les bornes min / max des entrées sont fixes (plage du
  paramètre, `c001de64…`) : elles n'y sont pour rien.
- **Lissage.** Y et Z de chaque voix font 1/8 du chemin vers leur cible à chaque tick,
  en pas de 1/256. Une voix qui commence prend sa cible tout de suite. Avec le palier 5,
  les 128 pas du CC74 s'entendaient sur une grande quantité (essai du 2026-11-19).
  **[Durée réelle inconnue : elle dépend de la période de `synth_tick`, non mesurée.]**
- **Variables au début du tas.** Le code et les variables ne tenaient plus dans la zone
  libre. `heap_bss` dans `build.py` range les variables mises à zéro en `0xc0931538`
  (fin de la mise à zéro du démarrage = début du tas de `_sbrk`, c014af98, limite
  0xc1000000). Il décale le début du tas (mot `0xc014afd0`) et la taille de la mise à
  zéro d'autant (0x5b0 octets).

**Limites connues.**
- **Relâcher la pression avant le Note Off coupe la note.** Z ne suit la voix que
  pendant la note jouée ; si le contrôleur envoie Z = 0 avant le Note Off, la relâche est
  muette.
- **Coût.** Pendant qu'Y glisse, la voix est recalculée à chaque tick (environ 90 ticks
  pour un saut de 0 à 127).
- **Voix volée.** Une voix volée sans repasser par un autre état glisse depuis la valeur
  de la note d'avant (`shortcut:` dans le code).

### Palier 7 en détail (`tools/patch/palier7.c` = `palier6.c` avec `PER_PARAM`)

Au palier 6, chaque pas de Y relançait `voice_apply_velocity`, qui renvoie au SHARC tous
les réglages de la voix (≈ 80). Un doigt sur le pad n'est jamais immobile, et le lissage
ajoutait un recalcul à chaque tick : artefacts insupportables (essai du 2026-11-19). La
molette, elle, passe par `slot_set_param` → `c000f6ec`, qui ne traite que le paramètre
modifié. Pour chaque voix du slot, ce chemin appelle :
- `voice_morph_eval(voix+0x48, n)` (c0033538, choisi par c0029bb0), qui donne la valeur
  morphée du paramètre n pour cette voix ;
- `voice_param_handler(&méthode, voix, n)` (c0029678, `switch` sur n), qui donne
  `{objet, fonction}`, puis `fonction(objet, valeur)`.

Le palier 7 fait pareil, voix par voix, **seulement pour les paramètres qui ont une
quantité Wheel** : base + Y × quantité le temps de l'évaluation, puis application.
L'entrée de morph i est le paramètre n° i du slot (`voice_morph_eval` indexe la table
par n°). Un paramètre sans méthode par voix tombe sur la méthode par défaut (`bx lr`) :
sans effet, comme pour la molette.

### Palier 8 en détail (`tools/patch/palier8.c` = `palier6.c` avec `PER_PARAM` et `PALIER8`)

Essai du palier 7 : Z → Level décevant, et on n'entend pas bien si ça agit. Le palier 8
corrige quatre causes probables :
- **Poly AT accepté comme Z** sur les canaux membres : sur un canal membre il n'y a
  qu'une note. Selon le support Roger Linn, le LinnStrument envoie la pression en
  Poly AT par défaut ; le palier 7 l'ignorait.
- **Courbe Z²** : le volume perçu est logarithmique. En linéaire, presque toute la course
  sonnait fort ; Z² donne Z = 64 → 25 % (−12 dB), Z = 32 → 6 % (−24 dB).
- **Z remplace la vélocité pour le volume** : gain = Z², 1 à Z = 127, au lieu de
  `gain de vélocité × Z`. Avec le produit, une note frappée doucement ne pouvait pas
  monter. Un canal qui n'a jamais reçu de pression garde le volume d'origine.
- **Relâche préservée** : d'après un fil de forum (non officiel), le LinnStrument envoie
  Z = 0 juste avant chaque Note On et Note Off. Un Z = 0 n'est appliqué au canal qu'après
  `ZWAIT` = 3 ticks : si le Note Off arrive avant, la voix part en relâche avec son
  niveau. Une note qui commence prend tout de suite le Z reçu, sans attente.

Prévu ensuite comme options du menu MIDI : courbes au choix pour Y et Z, et « remplace » ou
« multiplie » la vélocité.

### Palier 9 en détail (`tools/patch/palier9.c`, `palier3alias.c`, `alias.h`)

Le firmware identifie une note par (slot, numéro) : le canal disparaît dès l'appel au slot
(`docs/voices-midi.md`, « Identité d'une note »). Deux doigts sur la même hauteur faisaient
une seule note, et `bind_voices` donnait aux deux voix le canal du plus récent (essai :
« la plus récente vole le bend de l'autre »). Élargir l'identité des notes toucherait
toutes les tables de 128 touches, l'arpégiateur, l'arbre des notes, la file et
l'allocateur. Le palier 9 renumérote plutôt :

- **Note On** (`mpe9_target_note_on`, pointeur `0xc011ffac`) : sur un canal membre, si
  la hauteur est déjà tenue sur un autre canal membre, la note entre sous le numéro libre
  le plus proche (n + 1, n − 1, n + 2… jusqu'à ± 12 ; `alias_on`). Un Note On répété sur
  le même canal garde son numéro.
- **Note Off** (`mpe9_target_note_off`, pointeur `0xc011feb0` vers `target_note_off`,
  c0111424) : éteint le numéro réellement joué et le libère (`alias_off`).
- **Hauteur** : l'écart (note − numéro joué) passe par `g_off` à `mpe_queue_note_on`, qui
  le range par (slot, note) ; `bind_voices` le donne à chaque voix, et
  `mpe_voice_pitch_offset` l'ajoute en demi-tons. L'entrée clavier du morph (voix[0x13] =
  hauteur) suit, l'affichage et le suivi de clavier de l'arpégiateur non.
- **Une fois par cible.** Le répartiteur (`c011fdcc` pour le Note Off, via `c011f62c`)
  appelle `target_note_on` / `target_note_off` pour chaque cible. La 1ʳᵉ version libérait
  l'alias au premier Note Off : les cibles suivantes éteignaient le numéro d'origine, et
  les notes renumérotées restaient bloquées (essai du 2026-11-19). L'alias reste maintenant
  connu jusqu'au Note On suivant de (canal, note), et il est réutilisé seulement s'il est
  libre.
- `test_alias.c` vérifie l'attribution sur le Mac, appels répétés compris :
  `cc -o /tmp/t tools/patch/test_alias.c && /tmp/t`.

**Limites.**
- Seuls les canaux membres sont suivis : une note du canal 1 ou du clavier local sur la
  même hauteur reste confondue.
- Si les 25 numéros autour de la note sont pris, la note est confondue comme avant.
- Ce qui dépend du numéro de note et non de la hauteur de la voix sera décalé d'un ou deux
  demi-tons pour la note renumérotée **[hyp. : rien d'audible]**.

### Palier 10 en détail (`tools/patch/palier10.c`, qui inclut les paliers 2, 3 et 9)

Le MPE ne s'active plus par « canal global = 1 » mais par quatre entrées ajoutées **à la
fin du menu MIDI** (après 8 ; molette pour y aller, Shift + molette pour changer) :

| Lettre | Option (bits du réglage 0x21) | Valeurs (défaut en premier) | Effet |
|---|---|---|---|
| `P` | MPE (bit 0) | `Of`, `On` | zone basse : canaux 2 à 16 en membres, sur le slot en Keyboard Focus |
| `r` | plage du bend (bits 1–2) | `48`, `24`, `12`, ` 2` | bend des canaux membres, en demi-tons |
| `y` | Y (bit 3) | `On`, `Of` | Y (CC74) → morph Wheel par note ; `Of` : CC74 des membres ignoré |
| `L` | Z (bit 4) | `On`, `Of` | Z (pression) → Level par note ; `Of` : pression des membres ignorée |

**1ʳᵉ version (2026-11-20) : le clavier ne redémarrait plus.** Elle ajoutait 4 réglages
(n° 0x22 à 0x25) à la table des réglages globaux. Cause, trouvée à la lecture :
l'écouteur de ces réglages (objet de `fn_c00ee098`, constructeur de base `fn_c00e3f70`)
range dans **son propre objet** des tableaux de 34 cases indexés par n° (un octet par n°
en `+0x104`, des paires de mots en `+0x58`, et 0x22 en dur dans `fn_c00e3f70` et
`fn_c00e2ab0`). Nos n° écrivaient au-delà, sur l'objet minuterie en `+0xe0` et son
pointeur de rappel en `+0xec`. **Leçon : le nombre de réglages globaux est figé à 34.**

**2ᵉ version.** Les quatre options sont des champs de bits du réglage **0x21** : il est
sauvegardé sur 31 bits, mais son maximum vaut 0 dans l'OS 1.32 (toujours 0, aucun lecteur
ni écrivain par n° dans le CODE). `build.py` passe ce maximum à 0x1f (`0xc03c02a4`). Ni la
table ni l'enregistrement sauvegardé ne changent de forme ; l'OS officiel lit une valeur
> 0 hors bornes et la ramène à 0 (les options reviennent alors aux défauts).

Fonctionnement :
- **Entrées** : `mpe10_menus_done` remplace le dernier appel de `menus_build`
  (`0xc00fc0e8`). Chaque entrée est construite par le constructeur de PB Mode
  (`fn_c01001f8`, objet agrandi à 0x64 octets, n° de l'option en `+0x60`), puis reçoit nos
  copies des vtables de PB Mode : principale (molette `[5]`, formatage `[12]`, affichage
  `[13]`) et sous-objet `+0xc` (relais de la molette). La molette ne change que son
  champ : `global_step(app, 0x21, …, écart << décalage)`. `build.py` vérifie que les mots
  recopiés et le descripteur de 0x21 sont ceux de l'image d'origine.
- **Prise en compte** : après `global_step`, la molette pose `app[0x1fe]` et relance
  `app_routing_update`, comme le fait le firmware pour le canal global ; `mpe_zone_setup`
  relit les options (la nouvelle valeur lui est passée par `g_force`). Au démarrage, la
  création des zones lit le réglage chargé. `mpe10_on_global` (pointeur `0xc03bf200`) fait
  la même chose si l'application est prévenue du n° 0x21.
  Le canal global n'est plus ajouté une 2ᵉ fois comme membre.
- **Place** : le trou après le CODE ne suffit plus (0xaa8 octets sur 0xad0). Le reste
  (0x2d0 octets) va dans du **code mort** du firmware, `0xc002d1f8`–`0xc002daa4`
  (`DEAD` dans `build.py`), trouvé par `tools/find_dead_code.py` : aucun mot d'aucune
  image ne pointe dedans, aucun branchement, chargement relatif au PC ni `adr` venu
  d'ailleurs n'y arrive, et elle suit une fin de fonction. `build.py` répartit lui-même
  les fonctions (le trou d'abord, puis les zones mortes), car
  `ld --enable-non-contiguous-regions` plante ; les variables restent dans le trou ou le tas.
- Contrôles : le palier 9 reconstruit est identique octet pour octet ; l'image du palier 10
  ne diffère de l'originale que par les mots attendus, la zone morte utilisée et le code
  ajouté.

**À essayer** :
1. Après la mise à jour : le clavier redémarre ; menu MIDI, molette jusqu'après 8 →
   `P.Of`, `r.48`, `y.On`, `L.On`.
2. `P` sur `On` : le MPE marche comme au palier 9, **quel que soit le canal global**
   (garder A–D sur Off).
3. `r` sur `12` puis ` 2` : plage du bend des canaux membres.
4. `y` puis `L` sur `Of` : Y puis Z sans effet.
5. Éteindre, rallumer : les quatre réglages sont gardés, et le MPE marche dès l'allumage.

**Essai de la 2ᵉ version (2026-11-20)** : le clavier redémarre, les entrées s'affichent.
`P.On` ne changeait rien jusqu'au redémarrage suivant ; après, les notes MIDI des canaux
membres jouent. Le réglage est donc bien sauvegardé, mais l'application n'est pas prévenue
d'un changement du n° 0x21 (elle ne reçoit sans doute que les n° auxquels elle est
abonnée **[hyp.]**) : `mpe10_on_global` n'était pas appelé. **3ᵉ version** : la molette
relance elle-même la création des zones (ci-dessus). Avec `P.Of`, il est normal que les
canaux 2 à 16 ne jouent pas (seul le canal global est écouté).

**Essai de la 3ᵉ version (2026-11-20) : même défaut** (`P.On` n'agit qu'après un
redémarrage). Relire la relance (zones vidées puis recréées par `fn_c00df898`, cibles
réactivées par le Keyboard Focus dans `midi_routing_setup`, `target_note_on` sans masque)
ne montre aucune différence entre le démarrage et une relance. D'où une version de
**diagnostic**, `build/palier10diag_os.app` (`palier10diag.c`, `4f93e105…ba80d8e77`) : au
menu MIDI, `r` affiche le **nombre de zones** de la cible du slot A et `y` affiche
**créations des zones (mod 16) | g_mpe_on**, en hexadécimal. Attendu : `r.02` à `r.04`
avec `P.Of`, `r.20` environ avec `P.On` (2 zones d'origine + 30 nôtres) ; le 1ᵉʳ chiffre
de `y` augmente à chaque relance, le 2ᵉ vaut 1 avec `P.On`.

**Diagnostic relevé (2026-11-20)** : après redémarrage avec `P.Of` : `r.02`, `y.60` ;
`P` passé sur `On` sans redémarrer : `r.20`, `y.71`. **La relance marche** : les 30 zones
des canaux membres sont créées tout de suite et le MPE est actif. Le silence vient sans
doute du programme d'essai : il a un morph sur la molette et n'est audible que molette
levée ; Y par note s'ajoute à ce morph, la molette du panneau agit toujours sur le slot
**[hyp., à confirmer avec un son audible molette en bas]**.

**Essai final (2026-11-20) : OK.** Avec la version normale, `y` et `L` sur `On`, le
programme joue depuis le LinnStrument comme au palier 9, et `P.On` agit sans
redémarrage. Le défaut venait du programme d'essai et de `y` resté sur `Of`.

**Si une version ne redémarre pas** : essayer `build/palier9dead_os.app`. C'est
le palier 9 avec ses deux enveloppes de notes (Note On / Note Off des canaux membres)
déplacées dans la même zone morte. S'il démarre et joue comme le palier 9, la zone morte
est hors de cause ; sinon, c'est elle.

### Palier 11 en détail (`tools/patch/palier11.c`, qui inclut `palier10.c`)

Les options MPE encore manquantes, toutes dans les bits du réglage 0x21 (maximum passé à
`0x1fff` par `build.py`). Menu MIDI, après 8 (molette pour aller à l'entrée, Shift +
molette pour changer la valeur). L'afficheur a 3 caractères : lettre de l'entrée, point,
valeur sur 2 caractères. Le défaut est en premier.

| Afficheur | Réglage | Valeurs | Bits de 0x21 |
|---|---|---|---|
| `E.Of` | **MPE** | `Of` arrêt · `On` marche | 0 |
| `r.48` | **plage du bend** des canaux membres | `48` · `24` · `12` · ` 2` demi-tons | 1–2 |
| `y.nO` | **Y (CC74) va vers…** | `nO` morph molette (Wheel) · `vE` morph vélocité · `Fr` Filter Freq directement · `Of` rien | 3–4 |
| `C.Li` | **courbe de Y** | `Li` linéaire · `CA` carrée (lente en bas) · `dO` douce (rapide en bas) | 8–9 |
| `P.LE` | **Z (pression) va vers…** | `LE` volume (de 0 au volume normal) · `nO` molette · `vE` vélocité · `Fr` Filter Freq · `Of` rien · `vL` vélocité du volume (Z remplace la vélocité, ≈ 6 dB) | 5–7 |
| `H.CA` | **courbe de Z** | `CA` carrée · `Li` linéaire · `dO` douce | 10–11 |
| `v.Of` | **Z × vélocité** | `Of` Z seul · `On` Z multiplié par la vélocité de la note | 12 |

Lettres : `E` pour le MPE et `P` (pression) pour Z, parce qu'un Z s'afficherait comme un
2, déjà pris par Local. `nO` = moLette (le n tient lieu de M). `vE` se lit « UE » à
l'afficheur. Une valeur sauvegardée hors plage (ex. 5 à 7 pour `P`) se lit comme le défaut.

**Compatibilité avec le palier 10** : les bits 0 à 2 (MPE, bend) ne bougent pas. Les bits 3
et 4 changent de sens : un `y.Of` du palier 10 devient `y.vE`, un `L.Of` devient `y.Fr`.

Fonctionnement :
- **Toutes les destinations par paramètre** (chemin du palier 7) : pour chaque entrée de
  morph de la voix, un écart est ajouté à la base le temps de `voice_morph_eval`, puis
  appliqué par `voice_param_handler`. Y et Z sont appliqués **ensemble** : sinon la 2ᵉ
  évaluation effacerait la 1ʳᵉ quand les deux visent le même paramètre.
  - **nO (Wheel)** : écart = valeur × quantité Wheel du programme (comme au palier 7).
  - **vE (Velocity)** : `voice_morph_eval` ajoute `qté × (vélocité + 1) / 128`
    (`o[2]` = `voix[0x14]`, vérifié au pseudo-C) ; l'écart remplace (vélocité + 1) / 128
    par la valeur. Seuls les paramètres qui ont une quantité Velocity bougent.
  - **Fr (Filter Freq direct)** : paramètre n° **0x15**. Écart = valeur × (max − min) de
    l'entrée : à 127, le filtre est ouvert à fond depuis le réglage du bouton. **Essayé
    (Z → Fr, 2026-11-20) : agit bien sur la coupure.**
  - **Volume** : la méthode du volume par voix (paramètre n° 0, `c0036dbc`) **ignore la
    valeur passée**. Elle lit un réglage du slot S (`[voix+0x414] + 8`,
    `voix+0x414 = moteur+0x6ac`, posé par `voice_bind_engine`) et la **vélocité en
    `voix+0x42c`**, recopiée de `voix+0x3c` par `voice_push_params`. Indice
    = S × vélocité / 127 − S / 2 (S / 2 borné à 32), table ≈ 0,19 dB par pas
    (`0xc01c8b54` / `0xc01c8954`), gain borné à 0x800000 ; rangé en `voix+0x3b0`
    (= `[voix+0x3dc] + 0x14`, `voix+0x3dc = voix+0x39c`), envoyé par
    **`c005ee84(voix[0x3d8], gain)`** → SHARC DM `0x9248a + (n >> 1) × 0x40`
    (`c005eec8`, appelé par `voice_push_params`, écrit la même adresse).
  - **`LE`, volume × Z** (4ᵉ version) : `gain de voix+0x3b0 × courbe(Z)` est renvoyé par
    `c005ee84`, `voix+0x3b0` restant intact. Z = 0 → silence, Z = 127 → volume normal
    (vélocité comprise). Renvoyé quand Z bouge, au début de la note et tous les 32 ticks : si
    le firmware recalcule le volume (bouton tourné), le volume normal peut revenir jusqu'à
    32 ticks.
  - **`vL`, Z remplace la vélocité** (3ᵉ version, gardée) : Z sur 0…127 dans `voix+0x42c`,
    puis la méthode. Essai du 2026-11-20 : marche, mais ≈ 6 dB d'ampleur au plus (la formule
    ci-dessus). `vL` est après `Of` pour que `Of` garde sa valeur sauvegardée.
  - Versions sans effet : gain des paliers 6 à 10 (`amp_gain_write`, `voix+0x334`, DM
    `0x9245c` : une autre adresse, dont le rôle n'est pas connu), puis écart sur la base du
    paramètre n° 0 (2ᵉ version), puisque la méthode ignore la valeur.
- **Numéros des paramètres** : table des noms `0xc01c9be8…`, entrées de 16 octets
  `{n°, groupe, nom, unité}` (0 = Output Level, 0x15 = Filter Freq, 0x16 = Resonance).
  Disposition confirmée par ce qu'on sait déjà : 0x21 / 0x22 = Pitch Bend Range,
  0x23 = « Pitch Bend xxx » (la valeur du bend), 0x24 = Voice Mode, 0x25 = Legato, sans
  méthode par voix de 0x21 à 0x25. Une 1ʳᵉ lecture `{groupe, nom, unité, n°}` donnait
  0x16 (Resonance) pour Filter Freq : corrigé avant l'essai.
- **1ʳᵉ version : Level = gain d'ampli des paliers 6 à 10** (`amp_gain_write`), essayé le
  2026-11-20 : **aucun effet sur le volume** (et déjà « décevant » au palier 8). Remplacé
  par Output Level. Cause non cherchée **[hyp. : gain réécrit par le firmware, ou valeur
  ignorée par le SHARC]**.
- **v.On** : la valeur de Z est multipliée par (vélocité + 1) / 128 avant l'écart, pour
  toutes les destinations.
- **Courbes** (sur la valeur lissée, 0…1) : linéaire ; carrée (x²) ; douce
  = 1 − (1 − x)².
- **Canaux A–D** : `app_routing_update` (c00e04cc) recopie les réglages des canaux
  (`app+0x1d8…0x1e4`) dans les canaux effectifs `app+0x1ec…0x1f8` (16 = Off, un canal égal
  au global passe à Off), puis appelle la création des zones (notre `mpe_zone_setup`) et
  pose les masques des contrôleurs d'après ces mêmes champs. En mode MPE, un canal A–D
  situé sur un canal membre (MIDI 2 à 16) est mis à Off **dans les champs effectifs
  seulement**, avant la création des zones : ni zone ni masque pour lui. Les réglages et le
  menu ne changent pas ; un retour à `E.Of` (ou un changement de A–D, qui relance aussi
  `app_routing_update` par `fn_c00e0960`) les rétablit. Un canal A–D sur MIDI 1 reste.
  Les canaux A–D sont rangés hors de la table globale : modèle par slot `app[0x53 + i]`,
  réglage n° 1 (`fn_c00e2740` / `fn_c00e2894`, appelés par l'entrée de menu
  `fn_c0101da8`).
- Place : 0xab8 octets dans le trou (sur 0xad0) + 0x764 dans la 1ʳᵉ zone morte (sur
  0x8ac). Le trou est plein : le prochain ajout ira dans les zones mortes.
- Contrôles : paliers 9 et 10 reconstruits identiques octet pour octet ; l'image du
  palier 11 ne diffère de l'originale que par les 20 mots du palier 10 (dont le maximum de
  0x21), la zone morte et le code ajouté ; `.cab` réextrait, les 5 autres sections
  identiques à l'officiel ; aucun appel à libgcc dans le code produit.

**Diagnostic du Level** (`build/palier11diag_os.app`, `palier11diag.c`, `DIAG11`) : le
palier 11 (2ᵉ version) qui affiche au menu, pour la **dernière note démarrée sur un canal
membre**, en hexadécimal (`b`, `d` en minuscules) :

| Entrée | Affiche |
|---|---|
| `E` | MPE, comme d'habitude (à laisser sur `On`) |
| `r` | vélocité de la note (`voix[0x14]`, `7F` = 127) |
| `y` `C` `P` `H` | les 4 octets de `voix+0x3c`, du plus fort au plus faible : `y.00 C.40 P.00 H.00` = `0x00400000` |
| `v` | `voix+0x3b0 >> 16` : le gain calculé par `c0036dbc` (`80` = gain 1) |

**Relevé du 2026-11-20** (LinnStrument) : vélocité `07` → `voix+0x3c = 0x00000007`,
`v.11` ; vélocité `3A` → `0x0000003A`, `v.1d`. **`voix+0x3c` est la vélocité (0…127) et le
gain en dépend** : d'où la 3ᵉ version de LE.

Les entrées `r` à `v` gardent leur molette : ne pas les tourner pendant le relevé. Relevé
voulu : jouer une note **douce** sur le LinnStrument, la lâcher, noter `r y C P H v` ; puis
une note **forte** ; puis une forte avec Output Level du panneau au milieu. Lecture :
- `voix+0x3c` varie avec la vélocité → c'est le facteur de vélocité du volume ; Z le
  remplacera (ou le multipliera) dans `voix+0x42c`, puis on rappellera `c0036dbc` ;
- il ne varie pas → chercher ailleurs (il dépend alors du programme, pas de la note) ;
- `v` donne l'échelle du gain de sortie (8.23 si `80` = plein).

**Essai de la 3ᵉ version (2026-11-20) : LE marche, mais l'ampleur est faible** (petite
variation autour du niveau, impossible de descendre au silence). Cause, lue dans `c0036dbc` :
indice = S × (vélocité / 127) − S / 2, où S = `[voix+0x414] + 8` (réglage du slot, borné
à 65 ; au-delà, S / 2 est remplacé par 32). Indice ≥ 0 → table `0xc01c8b54`, indice < 0 →
table `0xc01c8954`, **≈ 0,19 dB par pas** ; gain borné à 0x800000 (0 dB), stocké en
`voix+0x3b0`. Donc au mieux ≈ −6 dB à 0 dB par la vélocité : remplacer la vélocité par Z ne
peut pas aller plus loin. D'où, sur la proposition de l'utilisateur, deux modes (4ᵉ
version) : `LE` (volume × Z) et `vL` (Z remplace la vélocité).

**Z sur le LinnStrument** : notre code lit Z dans le **Channel Pressure ou le Poly AT,
sur 7 bits**. Le LinnStrument peut l'envoyer sur 14 bits (réglage de l'utilisateur pendant
les essais du 2026-11-20). Si ce mode passe par un CC (CC11 + octet faible), notre code ne
voit aucune pression : les essais de Z demandent Z en Channel Pressure ou Poly AT
**[à vérifier : ce qu'envoie le mode 14 bits]**. Le 14 bits n'apporterait rien au volume
(`voix+0x42c` est un entier de 0 à 127) ; pour les autres destinations, le lissage comble déjà
les pas.

**Limites.**
- Changer de destination pendant une note laisse les paramètres de l'ancienne destination
  à leur dernière valeur jusqu'à la note suivante.
- Y et Z tous deux sur `vE` : les deux écarts s'additionnent (chacun remplace la vélocité).
- `P.LE` : une note commence au niveau de la pression reçue ; sans pression au départ,
  l'attaque est muette jusqu'à ce que Z monte (normal en MPE).

**À essayer** (programme qui sonne molette en bas, A–D sur Off sauf mention) :
1. Après la mise à jour, menu MIDI après 8 : `E`, `r`, `y`, `C`, `P`, `H`, `v` (le MPE
   reste sur `On` s'il y était).
2. `P.LE` : la pression règle le volume de chaque note, du silence au volume normal
   (essayer aussi `H.Li`, `H.dO`) ; `P.vL` : petite variation, comme la 3ᵉ version.
3. `y.Fr` : Y ouvre le filtre, note par note.
4. `y.vE` sur un programme avec un morph Velocity : Y le pilote.
5. `P.nO`, `P.vE` ; Y et Z ensemble sur `nO`.
6. `C` puis `H` : `CA` plus progressif en bas, `dO` plus vif.
7. `P.LE` et `v.On` : une note frappée doucement reste douce même pression à fond.
8. Slot B sur le canal 3, `E.On` : les notes du canal 3 ne vont qu'au slot joué ; `E.Of` :
   le slot B rejoue le canal 3.

## Script d'essai (`tools/mpe_test.py`)

Envoie des scénarios précis au clavier par USB (mido + python-rtmidi), comme un contrôleur
MPE en zone basse : état initial (bend, CC74, pression) avant chaque Note On, un canal
membre par note, « tout éteint » à la fin même après Ctrl-C.

```sh
python3 tools/mpe_test.py --list            # ports et scénarios
python3 tools/mpe_test.py same-note         # même note sur deux canaux
python3 tools/mpe_test.py y --seconds 10    # Y en sinusoïdes déphasées sur 3 notes
python3 tools/mpe_test.py all
```

Scénarios : `same-note`, `bend`, `y`, `chord8` (charge), `pressure` (pour le palier Z),
`master` (canal 1). Attendu pour `same-note` avec les paliers actuels : les deux notes
**partagent** la même entrée (une note est encore identifiée par (slot, numéro)), donc le
relâchement du canal 2 coupe sans doute aussi la note du canal 3.

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
5. **Palier 4.** Même procédure avec `build/palier4_os.app`, canal global = 1. Choisir
   (ou régler) un programme avec un **morph Velocity bien audible** (ex. Filter Freq ou
   niveau d'un oscillateur, Velocity morph) et l'enveloppe d'ampli **sans** vélocité si
   possible. Attendu : faire glisser le doigt en Y (LinnStrument) ou le mouvement
   correspondant de l'Osmose change le timbre **de cette note seulement** ; les autres
   notes tenues gardent le leur. Vérifier aussi : le bend par note (palier 3) marche
   encore ; le CC74 du canal 1 garde son effet habituel ; pas de saccades ni de notes
   perdues avec un accord de 8 notes et Y en mouvement continu (charge du processeur).
6. **Palier 5.** Même procédure avec `build/palier5_os.app`, canal global = 1. Prendre un
   programme d'usine dont la molette fait un effet net, **molette au repos**. Attendu :
   `python3 tools/mpe_test.py y` fait varier cet effet sur chaque note séparément ; la
   vélocité de frappe garde son effet habituel ; la molette agit sur toutes les notes.
   Puis `bend`, `chord8` et `same-note`.
7. **Palier 6.** `build/palier6_os.app`, mêmes réglages (A–D sur Off, canal global = 1).
   - Y à fond doit donner le même effet que la molette à fond.
   - Y doit glisser sans paliers audibles.
   - La pression doit faire le volume de chaque note ; un contrôleur qui n'envoie pas de
     pression garde le volume normal.
   - Vérifier aussi un accord de 8 notes avec Y et Z en mouvement (charge).
8. **Palier 7.** Mêmes essais que le palier 6 ; attendu : plus d'artefacts quand le doigt
   bouge sur le pad.
9. **Palier 8.** La pression doit faire le volume de chaque note, du silence au
   plein volume, quelle que soit la vélocité de frappe. La relâche doit rester audible
   quand on lève le doigt. Si rien ne change, vérifier sur le contrôleur ce qu'il envoie
   pour Z (Channel Pressure ou Poly AT) et sa valeur minimale.
10. **Palier 9.** Tenir la même hauteur sur deux canaux, par exemple deux rangées du
    LinnStrument. Attendu :
    - chaque doigt garde son bend, son Y et sa pression ;
    - les deux notes sont à la même hauteur ;
    - lever un doigt n'éteint que sa note.
11. Noter ce qui se passe et revenir à l'officiel si besoin.

## Résultats des essais (2026-11-19)

| Palier | Résultat |
|---|---|
| 1 | OK. L'updater re-signé se lance ; le clavier accepte le fichier recompressé. |
| 2 | OK en Performance : les notes des canaux 2 à 16 jouent sur le slot en Keyboard Focus. Pas de bend ni de timbre par note (attendu). |
| 3 | OK : notes des canaux 2 à 16, **bend par note indépendant**. |
| 5 (3ᵉ version) | **OK** : Y (CC74) des canaux 2 à 16 agit comme un morph Wheel propre à chaque note. Deux défauts : Y à 127 n'atteint pas l'effet de la molette à fond, et la modulation va **par paliers audibles** (la molette est fluide). Corrigés au palier 6 [à essayer]. |
| 6 | Z → volume par note : semble marcher (pas sûr ; à mettre en option). Échelle de Y : semble correcte maintenant. **Artefacts insupportables** quand le doigt bouge sur le pad : Y arrive en continu, et chaque pas recalculait toute la voix. Palier 7. |
| 11 (4ᵉ version, 2026-11-20) | **OK** : `P.LE` (volume × Z) marche ; `Fr` (Filter Freq) déjà vu aux essais précédents. |
| 9 (2ᵉ version) | **OK** : même hauteur sur deux canaux, chaque note garde son expression, plus de notes bloquées. |
| 9 (1ʳᵉ version) | **Notes bloquées** : l'alias était libéré au premier des Note Off envoyés à chaque cible. Corrigé (2ᵉ version, à essayer). |
| 8 | Z → Level **semble fonctionner, mais décevant** comme mode de jeu. Décision : ne pas aller plus loin ; Z → Wheel ou Velocity viendra en option du menu. **Même note sur deux canaux** (essai) : la note la plus récente vole le bend de la plus ancienne (limite connue du palier 3). |
| 7 (Z) | Z → Level décevant : on n'entend pas bien s'il agit, la vélocité semble prendre le dessus. Palier 8. |
| 7 | **Artefacts disparus** : appliquer Y paramètre par paramètre, comme la molette, était la bonne voie. Impression que Y à 127 n'atteint pas encore tout à fait la molette à fond (contrôleur ou échelle, à départager). |
| 5 (1ʳᵉ et 2ᵉ versions) | Stable, synthé responsif. **Y sans effet** (quantités Wheel jamais captées, voir « Palier 5 en détail »). Contournement de la collision : canaux A–D sur Off. |
| 4 | **En fait non** (CC74 jamais reçu, voir palier 5, 3ᵉ version). Impression d'abord : Y agit note par note (essai sur une Performance à un seul layer, morph Velocity → cutoff). Le bend par note marche toujours. **Réglage difficile** : il faut construire le morph Velocity à la main, avec sa plage, programme par programme. |

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
