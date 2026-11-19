/* Palier 9 : palier 8, et la même hauteur peut être tenue sur plusieurs canaux membres.
 * Les enveloppes de target_note_on / target_note_off (le canal y est encore connu)
 * renumérotent une note déjà tenue sur un autre canal (alias.h). palier3alias.c retient
 * l'écart par voix et l'ajoute à la hauteur, comme le bend : la voix sonne à la bonne
 * hauteur, et l'entrée clavier du morph (voix[0x13] = hauteur) suit. Voir docs/patches.md.
 */
#define PER_PARAM 1
#define PALIER8 1
#include "palier6.c"
#include "alias.h"

extern int g_off;                                    /* palier3alias.c */
int mpe_target_note_on(void *t, u32 port, u32 ch, u32 note, u32 vel);     /* palier3.c */
int target_note_off_orig(void *t, u32 port, u32 ch, u32 note, u32 vel);   /* c0111424 */

static u32 member(u32 ch, u32 note) { return g_mpe_on && ch >= 1 && ch < 16 && note < 128; }

int mpe9_target_note_on(void *t, u32 port, u32 ch, u32 note, u32 vel)
{
    if (!member(ch, note))
        return mpe_target_note_on(t, port, ch, note, vel);
    u32 a = alias_on(ch, note);
    g_off = (int)note - (int)a;
    int r = mpe_target_note_on(t, port, ch, a, vel);
    g_off = 0;
    return r;
}

int mpe9_target_note_off(void *t, u32 port, u32 ch, u32 note, u32 vel)
{
    return target_note_off_orig(t, port, ch, member(ch, note) ? alias_off(ch, note) : note, vel);
}
