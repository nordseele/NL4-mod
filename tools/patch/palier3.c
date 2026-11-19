/* Palier 3 : bend par note (±48 demi-tons, linéaire) sur les canaux 2 à 16.
 *
 * 1. Garder le canal : target_note_on (le canal y est encore connu) est enveloppé pour
 *    poser g_chan ; slot_queue_note_on (même pile d'appel) note chan_of[slot][note].
 * 2. Relier voix et canal : après note_on_build_voices / note_event_handler (types 3 et 4,
 *    qui démarrent les voix), on relit dans la table des notes les voix de (slot, note).
 * 3. Bend : midi_bend_in garde la valeur des canaux 2 à 16 pour soi (le slot ne la voit
 *    pas) ; voice_pitch_offset, réécrite, ajoute ce bend à la hauteur de la voix.
 * Rien ne change si la zone MPE est inactive (canal global ≠ 1). Voir docs/patches.md.
 */
typedef unsigned char u8;
typedef unsigned int u32;

extern unsigned char g_mpe_on;                       /* palier2.c */

int  target_note_on_orig(void *t, u32 port, u32 ch, u32 note, u32 vel);   /* c011129c */
void slot_queue_note_on_orig(u32 slot, int *notes, u32 count, u32 *mask);  /* c0028780 */
void build_voices_orig(void *mgr, int *ev);                                /* c00268d0 */
void note_event_orig(void *mgr, int *ev);                                  /* c00263b4 */
u32  midi_bend_in_orig(void *self, u8 *msg);                               /* c0120398 */
int  notemap_has(void *map, int *key);                                     /* c0016504 */
u8  *notemap_get(void *map, int *key);                                     /* c0016464 */

#define NOTEMAP ((void *)0xc040f470)
#define VOICES  ((u32 **)0xc04b0040)                 /* 20 voix ; voix[0] = numéro */
#define BEND_UNIT 384                                /* 8192 × 384 = 48 << 16 */

static int g_chan = -1;                              /* canal de la note en cours */
static u8  chan_of[4][128];                          /* canal + 1 de (slot, note) */
u8         voice_chan[32];                           /* canal + 1 de chaque voix */
static int g_bend[16];                               /* bend par canal, −8192…8191 */
#ifdef ALIAS
int        g_off;                                    /* palier9.c : note − numéro joué */
static signed char off_of[4][128], voice_off[32];   /* même écart par (slot, note), par voix */
#endif

int mpe_target_note_on(void *t, u32 port, u32 ch, u32 note, u32 vel)
{
    int saved = g_chan;
    g_chan = ch;
    int r = target_note_on_orig(t, port, ch, note, vel);
    g_chan = saved;
    return r;
}

void mpe_queue_note_on(u32 slot, int *notes, u32 count, u32 *mask)
{
    if (slot < 4)
        for (u32 i = 0; i < count; i++)
        {
            chan_of[slot][notes[2 * i] & 0x7f] = g_chan < 0 ? 0 : g_chan + 1;
#ifdef ALIAS
            off_of[slot][notes[2 * i] & 0x7f] = g_off;
#endif
        }
    slot_queue_note_on_orig(slot, notes, count, mask);
}

static void bind_voices(int *ev)
{
    int key[2] = { ev[2], ev[3] };                   /* {slot, note} */
    if ((u32)key[0] >= 4 || !notemap_has(NOTEMAP, key))
        return;
    u8 *entry = notemap_get(NOTEMAP, key);
    u32 n = *(u32 *)(entry + 0x44);
    for (u32 i = 0; i < n && i < 20; i++) {
        u32 vidx = *(u32 *)(entry + 0x48 + i * 0x18);
        if (vidx < 20) {
            u32 num = VOICES[vidx][0];
            if (num < 32) {
                voice_chan[num] = chan_of[key[0]][key[1] & 0x7f];
#ifdef ALIAS
                voice_off[num] = off_of[key[0]][key[1] & 0x7f];
#endif
            }
        }
    }
}

void mpe_build_voices(void *mgr, int *ev) { build_voices_orig(mgr, ev); bind_voices(ev); }
void mpe_note_event(void *mgr, int *ev)   { note_event_orig(mgr, ev);   bind_voices(ev); }

u32 mpe_bend_in(void *self, u8 *msg)
{
    u32 ch = msg[5];
    if (g_mpe_on && ch >= 1 && ch < 16) {            /* canal membre : gardé pour les voix */
        g_bend[ch] = *(int *)(msg + 8);
        return 1;
    }
    return midi_bend_in_orig(self, msg);
}

/* Remplace voice_pitch_offset (c001ccf4) : formule d'origine + bend de la voix. */
int mpe_voice_pitch_offset(int *glide, int *bend)
{
    int v = *(int *)(bend[0] + 0x14) + bend[4] + (*(int *)(glide[0] + 0x10) >> 8);
    if (g_mpe_on) {
        u32 num = *(u32 *)((u8 *)glide - 0x590);    /* glide = voix + 0x590 */
        if (num < 32) {
            u32 c = voice_chan[num];
            if (c >= 2 && c <= 16)
#ifdef ALIAS
                v += g_bend[c - 1] * BEND_UNIT + (voice_off[num] << 16);
#else
                v += g_bend[c - 1] * BEND_UNIT;
#endif
        }
    }
    return v;
}
