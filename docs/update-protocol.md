# Mise à jour de l'OS : protocole et sûreté

Source : le programme Mac `Nord OS Update` (tranche x86_64, symboles C++ présents),
analysé dans Ghidra (`/nordosupdate_x86_64-…`, conteneur `pyghidra-nl4`). Pour le
recréer : `lipo "vendor/Nord OS Update (binaire seul, extrait de l'app)" -thin x86_64
-output ghidra/bin/nordosupdate_x86_64`, puis `import_binary`. Légende : **[sûr]** lu dans
le code ; **[hyp.]** déduit.

## Les quatre programmes du clavier  [sûr]

Le clavier annonce un « mode logiciel » (`Zevs::ESoftwareMode`, `S_GetModeString`) :

| n° | nom | où |
|---|---|---|
| 0 | OS | image 1 de `os.cab` |
| 1 | TP | image 2 de `os.cab` (programme de test usine : LCD, MIDI, LED, n° de série) |
| 2, 3 | Reserved1 / Reserved2 | — |
| 4 | **Update** | **absent de `os.cab`**, dans la flash du clavier |
| 5 | **Boot** | **absent de `os.cab`**, dans la flash du clavier |

Le programme de mise à jour (4) et le chargeur (5) ne font pas partie du fichier. Une mise
à jour d'OS ne les réécrit donc pas **[hyp. forte]** : rien dans le protocole ne transmet
leur code. L'image 2 ne contient aucune routine d'effacement ni de réception de mise à
jour.

## Déroulé d'une mise à jour  [sûr]

Protocole USB à deux couches : `Ctrl` (version, reboot, boot) et `IT` (transfert).

1. **Connexion** (`DeviceConnected`, état 0) : demande de version pour chacun des quatre
   programmes (`SendRemoteVersionRequest`, `OnVersionReply`).
2. **Départ** (`StartSending`) : `CQryVersion`. Si le clavier répond en mode 4 (Update),
   on passe à 3. Sinon, `CReqReboot` (message Ctrl n° 4, un octet = mode visé, ici **4**),
   attente de la reconnexion, nouvelle demande. Si le clavier n'est toujours pas en
   mode 4 : « ERROR: Synth is still not in update mode after reboot. »
3. **Information** (`CRpyInfo`) : le clavier donne la taille de sa zone et la taille d'un
   secteur. Fichier plus gros → « File is too big! Memory is only %d KB ».
4. **Effacement** (`CReqErase`, un secteur à la fois) : autant de secteurs que la taille
   du fichier l'exige (`taille du fichier / taille de secteur`, arrondi). « Freeing space
   for update… », puis « Erase sector %d failed » en cas d'échec. **C'est le clavier qui
   choisit où se trouve cette zone.**
5. **Transfert** (`SendBinFileSection` pour chaque section, `XfrBegin` / `XfrData` /
   `XfrEnd`).
6. **Fin** (`ITProtocolFinished`) : `CReqReboot` avec le mode **0** (OS). Après la
   reconnexion, la version annoncée doit être celle du fichier : « Update completed
   successfully », sinon « Update seems to have failed ».

`CReqBoot` (message Ctrl n° 5, une adresse sur 32 bits) fait démarrer le clavier à une
adresse donnée (`ITProtocolFinished_BootAtAddress`, « BIN-file code section started »).
Il sert au transfert de fichiers `.bin` bruts (`SendResourceBin`).

Le protocole définit aussi `CReqMemDump` / `CReqMemWrite` (lecture et écriture de
mémoire) et `CReqChecksum`. Le programme Mac ne s'en sert pas : ses gestionnaires sont
vides. **On ne sait pas si le programme Update du clavier les accepte.** Si oui, ce
serait une voie de lecture de la flash par USB. À ne tester qu'après la sauvegarde
matérielle.

## Sûreté : ce que ça implique

- **Checksums : résolus** (`docs/oscab-format.md`). Un `os.cab` modifié peut porter des
  sommes justes.
- **Coupure pendant la mise à jour** : la zone de l'OS est effacée avant le transfert.
  Nord doit donc prévoir qu'un clavier sans OS valide reste récupérable, sinon toute
  coupure USB le rendrait inutilisable. **[hyp.]** Le chargeur vérifie l'OS au démarrage
  et reste en mode Update si l'OS est invalide.
- **OS modifié qui démarre puis plante** : c'est le vrai risque. Le reboot en mode Update
  passe normalement par l'OS (`CReqReboot`). Il faut donc un moyen d'entrer en mode
  Update sans l'OS : **allumer en tenant Shift + Store**. **Confirmé sur le Lead 4**
  (2026-11-18) : l'écran affiche « RDY » et Nord OS Update reconnaît le clavier.
- **Dernier recours, matériel** : sauvegarde de la flash SPI au programmateur (U38,
  Micron N25Q032, connecteur P5 probable : `docs/hardware.md`), ou démarrage par UART
  depuis la ROM de l'AM1705 (broches de mode de démarrage).

## Reste à faire pour l'étape 3

1. ~~Entrer en mode Update sans l'OS~~ : fait.
2. Lire la vérification du fichier côté Mac (« OS BinFile seems broken »).
3. Test de continuité P5 ↔ U38, puis sauvegarde complète de U38 au programmateur. Elle
   donne aussi le code des programmes Boot et Update, donc les vraies règles de
   récupération.
