# NL4 M — MPE pour le Nord Lead 4

Lire d'abord `HANDOFF.md` (état, plan, procédure de reprise), puis `docs/voices-midi.md`.

Règles du projet :
- Le firmware, les logiciels et le manuel Clavia restent hors de git (`vendor/`,
  `ghidra/bin/`). On ne commite que des notes, des formats et nos outils.
- Ne jamais écrire sur le clavier ni flasher quoi que ce soit avant l'étape 3 du plan
  (checksums reproduits, mode Update par Shift + Store vérifié : tous deux faits).
  La sauvegarde matérielle de la flash n'est plus exigée : U38 est vide et la mémoire
  du firmware n'est pas accessible sans démonter la carte (dernier recours).
- Pour lire une puce SPI : `tools/spiprobe.py` (lecture seule). Pas de `flashrom -r`,
  qui tente de lever la protection en écriture.
- Conteneur Ghidra du projet : `pyghidra-nl4` (port 8003). Ne pas toucher aux autres
  conteneurs pyghidra (autres projets).
- Les noms de fonctions vont dans `tools/symbols.txt`, puis `tools/rebuild.sh` et
  réimport dans Ghidra.
- Remote : `github.com/nordseele/NL4-mod`, **privé**. Ne pas le rendre public sans accord.
  `hardware/` (photos de la carte) reste en local.
- L'utilisateur écrit en français.
