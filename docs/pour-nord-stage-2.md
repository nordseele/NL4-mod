# Notes pour un projet MPE sur le Nord Stage 2

Écrit le 2026-11-19 depuis le projet Nord Lead 4 (ce dépôt, `/Users/matthiasbudde/CODE/NL4`).
Sur le Lead 4 (OS 1.32), le MPE marche par un patch de l'OS ARM seul :
- les notes des canaux 2 à 16 jouent ;
- bend par note à ±48 ;
- Y (CC74) par note, appliqué comme un morph Wheel de la voix ;
- Z (pression) par note sur le volume (premier essai).

Ce qui suit est ce qui a des chances de servir pour un autre instrument Clavia. **Rien
n'est vérifié sur le Stage 2** : tout ce qui le concerne est une hypothèse à contrôler.

## Fichiers à lire dans ce dépôt

| Fichier | Contenu |
|---|---|
| `HANDOFF.md` | état, plan par étapes, règles de sûreté |
| `docs/oscab-format.md` | format `os.cab` (en-têtes, sections, LZO1X, checksums) et reconstruction |
| `docs/update-protocol.md` | protocole de l'updater Mac ↔ clavier |
| `docs/faisabilite.md` | analyse de faisabilité MPE, découpage A–F |
| `docs/voices-midi.md` | réception MIDI, voix, morph, aiguillage des CC (spécifique Lead 4) |
| `docs/patches.md` | chaîne de patch, détail de chaque palier, résultats des essais |
| `docs/sharc.md` | code des DSP SHARC, liaison ARM → SHARC |
| `docs/hardware.md` | carte (AM1705 + 2 × ADSP-21489), récupération |
| `tools/unpack_oscab.py`, `tools/pack_oscab.py` | décompresser / reconstruire `os.cab` |
| `tools/patch/build.py`, `tools/patch/*.c` | compiler du C dans un trou de l'image, poser les sauts, reconstruire |
| `tools/patch/make_updater.sh` | copier l'updater officiel, y mettre notre `os.cab`, re-signer |
| `tools/mkelf.py`, `tools/rebuild.sh`, `tools/symbols.txt` | ELF pour Ghidra avec nos noms de fonctions |

Les outils contiennent des adresses et des constantes propres au Lead 4 : à adapter, pas
à lancer tels quels.

## Ce qui a des chances d'être commun (même marque, à vérifier)

- **Updater.** L'updater Mac (classes `Zevs::CCabHeader`, `CBinHeader`, `CBinFile`) lit
  `Contents/Resources/os.cab`. Le remplacer casse la signature : on re-signe la copie en
  ad hoc (`codesign --force --deep --sign -`) et on retire la quarantaine
  (`xattr -cr`). Chaque copie a besoin de son propre `CFBundleIdentifier`, sinon macOS
  ramène au premier plan une copie déjà ouverte et reflashe l'OS précédent. Quitter
  l'updater après chaque mise à jour (sinon « protocol already in use »).
- **`os.cab`.** En-têtes big-endian, sections compressées en **LZO1X** (on recompresse
  en LZO1X-999 ; le clavier l'accepte), deux checksums de type « ~somme des octets ». Si
  le Stage 2 utilise le même format, `unpack_oscab.py` / `pack_oscab.py` devraient
  presque marcher.
- **Récupération.** Sur le Lead 4, Shift + Store au démarrage force le mode Update et
  permet toujours de remettre l'OS officiel. Vérifier l'équivalent sur le Stage 2
  **avant tout flash**.
- **Architecture.** ARM (AM1705 ici) + SHARC pour l'audio. Le SHARC est un moteur
  « bête » : l'ARM écrit directement les paramètres de chaque voix dans sa mémoire et le
  SHARC les lisse. Tout le MPE s'est donc fait côté ARM, sans toucher au code SHARC.
  Le Stage 2 a d'autres moteurs (piano, orgue, synthé) : la structure des voix sera
  sûrement différente.

## Méthode qui a marché

1. **Sans rien flasher** : décoder et reconstruire `os.cab` à l'identique (mêmes
   checksums). Ghidra sur l'image ARM, nommer les fonctions au fur et à mesure.
2. **Palier 1** : flasher l'OS officiel recompressé par nos outils (prouve la chaîne et
   l'updater re-signé).
3. Puis un palier par fonction, chacun essayable seul sur l'instrument :
   - notes des canaux 2–16 ;
   - bend par note ;
   - Y ;
   - Z.
4. Le code ajouté est du C compilé (`arm-none-eabi-gcc -Os -marm`, conteneur Docker),
   lié dans un trou libre à la fin de l'image CODE. Les fonctions d'origine sont
   détournées par des pointeurs de vtable ou des `b` réécrits. Chaque mot modifié est
   vérifié contre sa valeur d'origine. Vérification finale : réextraire le `.cab`
   produit et comparer avec l'original (seuls les mots attendus changent).
5. Quand le trou ne suffit plus, les variables (mises à zéro) peuvent aller au début du
   tas : décaler le début de `_sbrk` et la taille de la mise à zéro du démarrage.

## Pièges rencontrés (ils coûtent des heures)

- **Relais « this-adjusting » (C++ à héritage multiple).** Un objet abonné au MIDI a un
  sous-objet par type de message. Le bus appelle parfois la vtable du sous-objet, qui
  pointe vers un petit relais `sub r0, r0, #N ; b fonction`. Remplacer l'entrée de la
  vtable principale ne sert alors à rien. Sur le Lead 4, le bend passait par la vtable,
  mais les CC et la pression passaient par des relais. **Pour intercepter un
  gestionnaire, chercher aussi les `b` vers lui, pas seulement les pointeurs.**
- **Le canal est perdu tôt.** Le firmware range bend, pression, etc. par cible (slot),
  avec une seule valeur pour toutes les notes. Il faut garder soi-même le canal de chaque
  voix au Note On (table voix → canal) et appliquer les valeurs par voix.
- **Ne pas tout recalculer à chaque message.** Y arrive en continu (un doigt sur un pad
  n'est jamais immobile). Rappeler la fonction qui recalcule toute la voix (≈ 80 réglages
  envoyés au DSP) à chaque pas donnait des artefacts insupportables. Il faut prendre le
  chemin du firmware « un paramètre, une voix » (celui qu'utilise la molette), seulement
  pour les paramètres concernés. Lisser les valeurs 7 bits par voix (1/8 du chemin par
  tick).
- **Collisions de canaux.** Les canaux réglés pour les slots ou parties (A–D sur le
  Lead 4) entrent en conflit avec les canaux membres MPE. En attendant une option, les
  mettre sur Off.
- **Contrôleurs.** D'après un fil de forum (non officiel), le LinnStrument remet la
  pression à 0 avant chaque Note On et Note Off, et il envoie par défaut du Poly AT
  plutôt que de la Channel Pressure. La norme MPE : bend ±48 par note et ±2 sur le
  canal maître (réglables par RPN 0), configuration de zone par RPN 6 (MCM).
- **Diagnostic sans sortie de débogage.** Un diagnostic « à l'oreille » (transposer les
  notes selon un code) a été pénible et peu concluant. Prévoir plutôt tôt un canal de
  sortie, par exemple des messages MIDI envoyés par le patch.

## Règles de sûreté gardées ici

- Firmware, logiciels et manuel du constructeur hors de git : on ne commite que des
  notes, des formats et nos outils.
- Rien d'écrit sur le clavier avant que les checksums soient reproduits et que le mode
  de récupération soit vérifié.
- Lecture de puces SPI en lecture seule (pas de `flashrom -r`, qui tente de lever la
  protection en écriture).
