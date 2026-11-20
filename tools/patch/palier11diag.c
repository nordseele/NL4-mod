/* Palier 11 avec diagnostic au menu MIDI (DIAG11 dans palier10.c et palier11.c) : pour la
 * dernière note démarrée sur un canal membre, r = vélocité, y C P H = voix+0x3c (4 octets,
 * fort → faible), v = voix+0x3b0 >> 16, en hexadécimal. But : connaître l'échelle de
 * voix+0x3c, que la méthode du volume par voix (c0036dbc) lit par voix+0x42c. */
#define DIAG11 1
#include "palier11.c"
