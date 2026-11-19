/* Palier 4 : Y (CC74) par note sur les canaux 2 à 16, envoyé à l'entrée vélocité de la voix.
 *
 * 1. midi_cc_in : le CC74 d'un canal membre est gardé dans g_y[canal] et n'atteint pas le
 *    panneau (sinon Filter Freq bougerait pour tout le slot). Canal 1 : inchangé.
 * 2. synth_tick (où le firmware démarre déjà les voix) : pour chaque voix jouée sur un canal
 *    membre, si son entrée vélocité (voix[0x14]) diffère du dernier Y de ce canal, on rappelle
 *    voice_apply_velocity(voix, Y) : tout le morph Velocity de la voix est recalculé, sans
 *    redéclencher les enveloppes. Comparer à voix[0x14] couvre aussi le Note On (qui y remet
 *    la vélocité de la note) : le Y courant du canal reprend la main au tick suivant.
 * Limite : la courbe de vélocité de l'ampli (voix+0x40) suit aussi Y. Voir docs/patches.md.
 */
typedef unsigned char u8;
typedef unsigned int u32;

extern unsigned char g_mpe_on;                       /* palier2.c */
extern u8 voice_chan[32];                            /* palier3.c : canal + 1 de chaque voix */

u32  midi_cc_in_orig(void *self, u8 *msg);           /* c011ffc4 */
void synth_tick_orig(void);                          /* c0010c34 */
void voice_apply_velocity(u32 *voice, u32 vel);      /* c0032098 */

#define VOICES ((u32 **)0xc04b0040)                  /* 20 voix ; voix[0] = numéro */

static u8 g_y[16];                                   /* Y + 1 par canal ; 0 = pas encore reçu */

u32 mpe_cc_in(void *self, u8 *msg)
{
    u32 ch = msg[5];
    if (g_mpe_on && ch >= 1 && ch < 16 && *(u32 *)(msg + 8) == 74) {
        u32 v = *(u32 *)(msg + 12);
        g_y[ch] = (v > 127 ? 127 : v) + 1;
        return 1;
    }
    return midi_cc_in_orig(self, msg);
}

void mpe_synth_tick(void)
{
    synth_tick_orig();
    if (!g_mpe_on)
        return;
    for (u32 i = 0; i < 20; i++) {
        u32 *v = VOICES[i];
        if (((u8 *)v)[8] != 3 || v[0] >= 32)         /* voix jouée (comme slot_set_param) */
            continue;
        u32 c = voice_chan[v[0]];
        if (c < 2 || c > 16 || !g_y[c - 1])
            continue;
        u32 y = g_y[c - 1] - 1;
        if (v[0x14] != y)
            voice_apply_velocity(v, y);
    }
}
