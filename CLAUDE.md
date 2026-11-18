# NL4 — MPE pour le Nord Lead 4

Lire d'abord `HANDOFF.md` (état, plan, procédure de reprise), puis `docs/voices-midi.md`.

Règles du projet :
- Le firmware, les logiciels et le manuel Clavia restent hors de git (`vendor/`,
  `ghidra/bin/`). On ne commite que des notes, des formats et nos outils.
- Ne jamais écrire sur le clavier ni flasher quoi que ce soit avant l'étape 3 du plan
  (checksums reproduits, sauvegarde de la flash au programmateur).
- Conteneur Ghidra du projet : `pyghidra-nl4` (port 8003). Ne pas toucher aux autres
  conteneurs pyghidra (autres projets).
- Les noms de fonctions vont dans `tools/symbols.txt`, puis `tools/rebuild.sh` et
  réimport dans Ghidra.
- Dépôt local uniquement, pas de remote.
- L'utilisateur écrit en français.
