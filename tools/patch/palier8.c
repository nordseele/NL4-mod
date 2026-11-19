/* Palier 8 : palier 7, et Z → Level rendu jouable :
 *  - Poly AT accepté comme Z sur les canaux membres (le LinnStrument en envoie par défaut) ;
 *  - courbe Z² (volume perçu ; linéaire, presque toute la course sonnait fort) ;
 *  - Z remplace la vélocité pour le volume (gain = Z², 1 à Z = 127), dès que le canal a reçu
 *    une pression ; un canal sans pression garde le volume d'origine ;
 *  - un Z = 0 n'est appliqué qu'après ZWAIT ticks : le LinnStrument en envoie un juste avant
 *    chaque Note Off, ce qui rendait la relâche muette.
 * Voir docs/patches.md. */
#define PER_PARAM 1
#define PALIER8 1
#include "palier6.c"
