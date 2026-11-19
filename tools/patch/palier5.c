/* Palier 5 : Y (CC74) par note sur les canaux 2 à 16, appliqué comme un morph Wheel propre à
 * la voix. Remplace palier4.c (Y sur Velocity) : la vélocité de chaque note reste la sienne.
 *
 * 1. Quantités Wheel : le morph Wheel est calculé par le modèle de paramètres du programme,
 *    qui ne prévient le slot que pour Velocity. On interroge donc le modèle du slot
 *    (*(0xc04eb824[slot] + 0x1a4), lecteur fn_c0118c24, source 0 = Wheel [hyp. forte]) pour
 *    chaque destination, et on range la quantité dans wq[slot][entrée de morph].
 *    (1re version : enveloppe de prog_morph_amount_in, appelée seulement à l'édition : vide
 *    avec un programme d'usine non retouché.)
 * 2. CC74 des canaux membres : gardé dans g_y[canal], n'atteint pas le panneau (comme palier 4).
 * 3. synth_tick : pour chaque voix jouée sur un canal membre, quand son Y change, après un
 *    Note On, ou tous les 32 ticks (quantités relues, réglage du panneau rattrapé) :
 *    base += Y × qté Wheel sur les entrées de morph du slot, voice_apply_velocity(voix,
 *    vélocité de la note), puis base rendue. Le calcul partagé ne garde aucune trace.
 * La molette physique agit toujours (les deux s'ajoutent). Voir docs/patches.md.
 */
typedef unsigned char u8;
typedef signed char s8;
typedef unsigned int u32;

extern unsigned char g_mpe_on;                       /* palier2.c */
extern u8 voice_chan[32];                            /* palier3.c : canal + 1 de chaque voix */

void mpe_build_voices(void *mgr, int *ev);           /* palier3.c */
void mpe_note_event(void *mgr, int *ev);
u32  midi_cc_in_orig(void *self, u8 *msg);           /* c011ffc4 */
void synth_tick_orig(void);                          /* c0010c34 */
void voice_apply_velocity(u32 *voice, u32 vel);      /* c0032098 */
int  morph_get(u8 *model, int *ref, u32 src);         /* fn_c0118c24 : quantité de morph */

#define VOICES   ((u32 **)0xc04b0040)                /* 20 voix ; voix[0] = numéro */
#define DEST_TAB ((u8 *)0xc04ed3fc)                  /* 3 octets par destination ; [1] = entrée */
#define NDEST 78                                     /* 0xec octets avant la variable suivante */
#define SLOTOBJ ((u8 **)0xc04eb824)                  /* objet programme de chaque slot */
#define NENT 90                                      /* entrées de morph par voix (voice_ctor) */
#define SRC_WHEEL 0

static u8  g_y[16];                                  /* Y + 1 par canal ; 0 = pas encore reçu */
static u8  ylast[32];                                /* Y + 1 appliqué à chaque voix */
static s8  wq[4][NENT];                              /* quantité Wheel par slot et par entrée */
static u8  g_refresh, g_ticks;

#ifdef DIAG
/* Diagnostic (palier5diag.c) : hauteur normale tant que read_wheel n'a pas lu le slot (il le
 * lit dès qu'une note MPE reçoit un Y), puis toutes les notes du slot sont transposées :
 * +24 : pas de modèle ; +12 : aucune quantité, ni Wheel ni Velocity ; +7 : Velocity trouvée
 * mais pas Wheel ; +5 : quantités Wheel trouvées. Chaque résultat est un saut audible. */
static u8 diag[4];
int mpe_voice_pitch_offset(int *glide, int *bend);  /* palier3.c */

int mpe5_voice_pitch_offset(int *glide, int *bend)
{
    int v = mpe_voice_pitch_offset(glide, bend);
    u32 s = **(u32 **)((u8 *)glide - 0x590 + 4);     /* voix[1] = moteur, moteur[0] = slot */
    return s < 4 ? v + (diag[s] << 16) : v;
}
#endif

static void read_wheel(u32 s)                        /* quantités Wheel du programme du slot s */
{
    u8 *model = SLOTOBJ[s] ? *(u8 **)(SLOTOBJ[s] + 0x1a4) : 0;
#ifdef DIAG
    u32 n0 = 0, n1 = 0;
    diag[s] = 24;
#endif
    if (!model)
        return;
    int ref[2] = { *(int *)(model + 0x30), 0 };      /* {groupe, n° de paramètre}, comme c00eb378 */
    for (u32 i = 0; i < NENT; i++)
        wq[s][i] = 0;
    for (u32 id = 0; id < NDEST; id++) {
        u32 i = DEST_TAB[id * 3 + 1];                /* 'Z' (arpégiateur) ≥ NENT : ignoré */
        if (i >= NENT)
            continue;
        ref[1] = id;
        int a = morph_get(model, ref, SRC_WHEEL);
        if (a)                                       /* destinations sans entrée : 0 dans la table */
            wq[s][i] = a > 127 ? 127 : a < -127 ? -127 : a;   /* ±127 = pleine échelle */
#ifdef DIAG
        n0 += a != 0;
        n1 += morph_get(model, ref, 1) != 0;
#endif
    }
#ifdef DIAG
    diag[s] = n0 ? 5 : n1 ? 7 : 12;
#endif
}

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

void mpe5_build_voices(void *mgr, int *ev) { mpe_build_voices(mgr, ev); g_refresh = 1; }
void mpe5_note_event(void *mgr, int *ev)   { mpe_note_event(mgr, ev);   g_refresh = 1; }

static void apply_y(u32 *v, u32 y)
{
    u32 s = *(u32 *)v[1];                            /* voix[1] = moteur, moteur[0] = slot */
    int *desc = (int *)v[0x15];                      /* descripteur de morph du moteur */
    if (s >= 4 || !desc)
        return;
    u32 n = (u32)desc[0] < NENT ? (u32)desc[0] : NENT;
    int *e = (int *)desc[3];                         /* {base, qté vél., qté clavier, min, max} */
    int k = y ? (int)(y + 1) << 9 : 0;               /* (Y + 1) × (qté << 16) >> 7, comme la vélocité */
    for (u32 i = 0; i < n; i++)
        e[5 * i] += k * wq[s][i];
    voice_apply_velocity(v, v[0x14]);                /* v[0x14] = vélocité de la note */
    for (u32 i = 0; i < n; i++)
        e[5 * i] -= k * wq[s][i];
}

void mpe_synth_tick(void)
{
    synth_tick_orig();
    if (!g_mpe_on)
        return;
    u32 refresh = g_refresh || !(++g_ticks & 31), read = 0;   /* read : slots relus ce tick */
    g_refresh = 0;
    for (u32 i = 0; i < 20; i++) {
        u32 *v = VOICES[i];
        if (((u8 *)v)[8] != 3 || v[0] >= 32)         /* voix jouée (comme slot_set_param) */
            continue;
        u32 c = voice_chan[v[0]];
        if (c < 2 || c > 16 || !g_y[c - 1])
            continue;
        u8 y1 = g_y[c - 1];
        if (refresh || ylast[v[0]] != y1) {
            u32 s = *(u32 *)v[1];
            if (refresh && s < 4 && !(read & 1 << s)) {
                read |= 1 << s;
                read_wheel(s);
            }
            ylast[v[0]] = y1;
            apply_y(v, y1 - 1);
        }
    }
}
