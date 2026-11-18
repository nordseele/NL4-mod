# NL4 — MPE pour le Nord Lead 4

Étude du firmware du Nord Lead 4 (OS v1.32) pour comprendre l'allocation des voix et
évaluer l'ajout d'un MPE complet : pitch bend par note (±48), pression (Z), timbre
(Y, CC74).

Projet personnel d'interopérabilité, sans lien avec Clavia / Nord Keyboards. Le firmware,
le logiciel et le manuel Nord ne sont **pas** dans ce dépôt (voir `.gitignore`). Seuls
le savoir et nos propres outils le sont.

**Pour reprendre le travail : lire [HANDOFF.md](HANDOFF.md).**

## Arborescence

| Chemin | Contenu | Dans git |
|---|---|---|
| `tools/unpack_oscab.py` | lit `os.cab` et décompresse les sections LZO1X | oui |
| `tools/mkelf.py` | emballe des sections brutes en ELF ARM, avec des symboles de départ, pour Ghidra | oui |
| `tools/funcs_seed.txt` | adresses de départ de fonctions données à Ghidra | oui |
| `tools/find_func_starts.py` | génère `funcs_seed.txt` (cibles de `bl`, prologues, tables) | oui |
| `tools/find_ptr_tables.py` | génère `vtables.txt` (tables de pointeurs vers du code) | oui |
| `tools/vtables.txt` | tables de pointeurs vers du code (vtables et autres) | oui |
| `tools/symbols.txt` | noms donnés aux fonctions identifiées (portés par l'ELF) | oui |
| `tools/rebuild.sh` | régénère tout `ghidra/bin/` depuis le dmg | oui |
| `tools/dump_decomp.py` | pseudo-C de toutes les fonctions → `ghidra/bin/decomp.c` (conteneur jetable) | oui |
| `docs/oscab-format.md` | format de `os.cab`, sections, compression, checksums | oui |
| `docs/update-protocol.md` | protocole de mise à jour (programme Mac), modes du clavier, sûreté | oui |
| `docs/hardware.md` | carte mère : puces, flash SPI, connecteur P5, récupération | oui |
| `docs/faisabilite.md` | étape 2 : verdict, modifications, options Y/Z, plan du prototype | oui |
| `tools/spiprobe.py` | sonde de flash SPI en lecture seule (Pico `pico-serprog`) | oui |
| `tools/extract_sharc.py` | extrait les deux programmes SHARC de l'OS (`ghidra/bin/sharc/`) | oui |
| `docs/sharc.md` | code des SHARC : emplacement, format, import Ghidra | oui |
| `ghidra/sharc_work/` | projet Ghidra SHARC (jetable) | non |
| `docs/voices-midi.md` | réception MIDI, slots, voix, allocateur (notes de recherche) | oui |
| `vendor/` | dmg officiel, manuel PDF (+ `manual.txt`), binaire isolé | non |
| `ghidra/bin/` | `os.cab`, sections décompressées, ELF complet | non |
| `ghidra/nl4_ghidra.*` | projet Ghidra du conteneur `pyghidra-nl4` | non |
| `.mcp.json` | branche le serveur MCP Ghidra (`127.0.0.1:8003`) | oui |

## Mise en place

1. Mettre `Update Nord Lead 4 OS v1.32.dmg` (téléchargé sur nordkeyboards.com) dans `vendor/`.
2. `tools/rebuild.sh`
3. Conteneur Ghidra dédié (n'affecte pas les autres conteneurs pyghidra) :

```bash
docker run -d --name pyghidra-nl4 --restart unless-stopped -p 127.0.0.1:8003:8000 -e JAVA_TOOL_OPTIONS=-Duser.name=matthias -v "$PWD/ghidra":/projects ghcr.io/clearbluejar/pyghidra-mcp:sha-f43400b -t streamable-http -o 0.0.0.0 --project-path /projects/nl4_ghidra.gpr
```

4. Dans Claude Code, importer `/projects/bin/nl4_os132_full.elf` avec l'outil
   `import_binary` du serveur `pyghidra-nl4`.

## Précaution

Rien dans ce dépôt n'écrit sur le clavier. Flasher un firmware modifié peut rendre le
synthé inutilisable : voir la section risques de HANDOFF.md.
