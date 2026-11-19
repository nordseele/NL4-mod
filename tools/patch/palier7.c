/* Palier 7 : palier 6, mais Y n'applique à la voix que les paramètres qui ont une quantité
 * Wheel, un par un (voice_morph_eval + voice_param_handler, le chemin de slot_set_param),
 * au lieu de tout recalculer par voice_apply_velocity. Voir docs/patches.md. */
#define PER_PARAM 1
#include "palier6.c"
