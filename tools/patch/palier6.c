/* Palier 6 : remplace palier5.c. Sur les canaux 2 à 16, par note :
 *  - Y (CC74) → morph Wheel de la voix, comme le palier 5, avec deux corrections :
 *    quantités Wheel sur 16 bits (le palier 5 les bornait à ±127 : Y à 127 n'atteignait pas
 *    toujours l'effet de la molette à fond) et Y lissé voix par voix (128 pas de CC74
 *    s'entendaient sur une grande quantité ; la molette, elle, est lissée par le firmware) ;
 *  - Z (Channel Pressure) → Level : voice_push_params (c002f898) calcule le gain d'ampli de
 *    la voix (voix+0x334, 8.23, 0x800000 = 1) et l'envoie au SHARC par
 *    amp_gain_write(voix+0x35c = n° DSP de la voix, gain) (c0061a08 : SHARC n & 1,
 *    DM 0x9245c + (n >> 1) × 0x40). On renvoie ce gain × Z lissé.
 * Lissage : à chaque tick, la valeur appliquée fait 1/8 du chemin vers la cible ; une voix qui
 * commence prend sa cible tout de suite. Canal sans Y / Z reçu : comportement d'origine.
 * Variables au début du tas (build.py, heap_bss). Voir docs/patches.md.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

extern unsigned char g_mpe_on;                       /* palier2.c */
extern u8 voice_chan[32];                            /* palier3.c : canal + 1 de chaque voix */

void mpe_build_voices(void *mgr, int *ev);           /* palier3.c */
void mpe_note_event(void *mgr, int *ev);
u32  midi_cc_in_orig(void *self, u8 *msg);           /* c011ffc4 */
u32  midi_pressure_in_orig(void *self, u8 *msg);     /* c01202ac */
void synth_tick_orig(void);                          /* c0010c34 */
void voice_apply_velocity(u32 *voice, u32 vel);      /* c0032098 */
int  morph_get(u8 *model, int *ref, u32 src);        /* fn_c0118c24 : quantité de morph */
void amp_gain_write(u32 dsp_voice, u32 gain);        /* c0061a08 */

#define VOICES   ((u32 **)0xc04b0040)                /* 20 voix ; voix[0] = numéro */
#define DEST_TAB ((u8 *)0xc04ed3fc)                  /* 3 octets par destination ; [1] = entrée */
#define NDEST 78
#define SLOTOBJ ((u8 **)0xc04eb824)                  /* objet programme de chaque slot */
#define NENT 90                                      /* entrées de morph par voix */
#define SRC_WHEEL 0
#define WQ_MAX 16383                                 /* k ≤ 65536 : k × WQ_MAX tient sur 31 bits */

static u8  g_y[16], g_z[16];                         /* valeur + 1 par canal ; 0 = pas reçue */
static u16 ycur[20], zcur[20];                       /* valeur lissée appliquée, × 256, par voix */
static u32 g_was;                                    /* voix jouées sur un canal membre au tick d'avant */
static short wq[4][NENT];                            /* quantité Wheel par slot et par entrée */
static u8  g_refresh, g_ticks;
#ifdef PALIER8
static u8  zt[16], zwait[16];                        /* Z retenu par canal ; un 0 attend ZWAIT ticks */
#define ZWAIT 3
#endif

static void read_wheel(u32 s)                        /* quantités Wheel du programme du slot s */
{
    u8 *model = SLOTOBJ[s] ? *(u8 **)(SLOTOBJ[s] + 0x1a4) : 0;
    if (!model)
        return;
    int ref[2] = { *(int *)(model + 0x30), 0 };      /* {groupe, n° de paramètre} */
    for (u32 i = 0; i < NENT; i++)
        wq[s][i] = 0;
    for (u32 id = 0; id < NDEST; id++) {
        u32 i = DEST_TAB[id * 3 + 1];                /* 'Z' (arpégiateur) ≥ NENT : ignoré */
        if (i >= NENT)
            continue;
        ref[1] = id;
        int a = morph_get(model, ref, SRC_WHEEL);
        if (a)
            wq[s][i] = a > WQ_MAX ? WQ_MAX : a < -WQ_MAX ? -WQ_MAX : a;
    }
}

static u32 chan_value(u8 *msg, u8 *dst)              /* canal membre : garde la valeur, rend 1 */
{
    u32 ch = msg[5];
    if (!g_mpe_on || ch < 1 || ch >= 16)
        return 0;
    u32 v = *(u32 *)(msg + 12);
    dst[ch] = (v > 127 ? 127 : v) + 1;
    return 1;
}

u32 mpe_cc_in(void *self, u8 *msg)
{
    if (*(u32 *)(msg + 8) == 74 && chan_value(msg, g_y)) {
#ifdef PALIER10
        if (g_y_off)                                 /* Y coupé au menu : CC74 ignoré */
            g_y[msg[5]] = 0;
#endif
        return 1;
    }
    return midi_cc_in_orig(self, msg);
}

u32 mpe_pressure_in(void *self, u8 *msg)             /* +8 = -1 : Channel Pressure ; sinon Poly AT */
{
#ifdef PALIER8
    if (chan_value(msg, g_z))                        /* Poly AT aussi : une note par canal membre */
#else
    if (*(int *)(msg + 8) == -1 && chan_value(msg, g_z))
#endif
    {
#ifdef PALIER10
        if (g_z_off)                                 /* Z coupé au menu : pression ignorée */
            g_z[msg[5]] = 0;
#endif
        return 1;
    }
    return midi_pressure_in_orig(self, msg);
}

void mpe5_build_voices(void *mgr, int *ev) { mpe_build_voices(mgr, ev); g_refresh = 1; }
void mpe5_note_event(void *mgr, int *ev)   { mpe_note_event(mgr, ev);   g_refresh = 1; }

static u32 follow(u16 *p, u32 v1, u32 snap)          /* rapproche *p de la cible ; 1 s'il a bougé */
{
    int t = (int)(v1 - 1) << 8, c = *p;
    if (snap)
        c = t;
    else if (c != t) {
        int d = (t - c) >> 3;
        c += d ? d : 1;                              /* d = 0 seulement quand t > c */
    }
    if (c == *p)
        return 0;
    *p = c;
    return 1;
}

#ifdef PER_PARAM
/* palier7.c : comme la molette (slot_set_param), seulement les paramètres morphés, voix par
 * voix ; voice_apply_velocity renvoyait ≈ 80 réglages au SHARC à chaque pas de Y. */
typedef struct { void *obj; void (*fn)(void *obj, int value); } method;
int  voice_morph_eval(u32 *o, u32 n);                /* c0033538 : valeur morphée du paramètre n */
void voice_param_handler(method *m, u32 *voice, u32 n);   /* c0029678 : méthode qui l'applique */
#endif

#ifndef PALIER11                                    /* palier11.c : Y et Z, destinations au choix */
static void apply_y(u32 *v, u32 s, u32 yc)
{
    int *desc = (int *)v[0x15];                      /* descripteur de morph du moteur */
    if (!desc)
        return;
    u32 n = (u32)desc[0] < NENT ? (u32)desc[0] : NENT;
    int *e = (int *)desc[3];                         /* {base, qté vél., qté clavier, min, max} */
    int k = 2 * yc + (yc >> 6);                      /* 127 × 256 → 65532 ≈ pleine quantité << 16 */
#ifdef PER_PARAM
    for (u32 i = 0; i < n; i++) {                    /* entrée de morph i = paramètre n° i */
        if (!wq[s][i])
            continue;
        method m;
        e[5 * i] += k * wq[s][i];
        int val = voice_morph_eval(v + 0x12, i);     /* v + 0x12 = voix+0x48 */
        e[5 * i] -= k * wq[s][i];
        voice_param_handler(&m, v, i);
        m.fn(m.obj, val);
    }
#else
    for (u32 i = 0; i < n; i++)
        e[5 * i] += k * wq[s][i];
    voice_apply_velocity(v, v[0x14]);                /* v[0x14] = vélocité de la note */
    for (u32 i = 0; i < n; i++)
        e[5 * i] -= k * wq[s][i];
#endif
}

void mpe_synth_tick(void)
{
    synth_tick_orig();
    if (!g_mpe_on)
        return;
    u32 refresh = g_refresh || !(++g_ticks & 31), read = 0, now = 0;
    g_refresh = 0;
#ifdef PALIER8
    for (u32 c = 1; c < 16; c++) {                   /* le LinnStrument envoie Z = 0 juste avant */
        u8 z = g_z[c];                               /* le Note Off : ne pas couper la relâche */
        if (z == 1 && zt[c] > 1 && zwait[c] < ZWAIT)
            zwait[c]++;
        else {
            zt[c] = z;
            zwait[c] = 0;
        }
    }
#endif
    for (u32 i = 0; i < 20; i++) {
        u32 *v = VOICES[i];
        if (((u8 *)v)[8] != 3 || v[0] >= 32)         /* voix jouée */
            continue;
        u32 c = voice_chan[v[0]];
        if (c < 2 || c > 16)
            continue;
        now |= 1u << i;
        /* shortcut: une voix volée sans repasser par un autre état glisse depuis la valeur de
         * la note d'avant au lieu de sauter ; à revoir si ça s'entend. */
        u32 fresh = !(g_was & 1u << i), pushed = 0, s = *(u32 *)v[1];
        if (s >= 4)
            continue;
        if (g_y[c - 1] && (follow(&ycur[i], g_y[c - 1], fresh) || fresh || refresh)) {
            if (refresh && !(read & 1u << s)) {
                read |= 1u << s;
                read_wheel(s);
            }
            apply_y(v, s, ycur[i]);
            pushed = 1;                              /* le recalcul a renvoyé le gain sans Z */
        }
#ifdef PALIER8
        u32 z1 = fresh ? g_z[c - 1] : zt[c - 1];     /* une note qui commence prend le Z reçu */
        if (z1 && (follow(&zcur[i], z1, fresh) || fresh || refresh || pushed)) {
            u32 q = 2 * zcur[i] + (zcur[i] >> 6);    /* 0…65532 ≈ 0…1 */
            amp_gain_write(v[0x35c / 4], (q * q >> 16) << 7);   /* Z², sans la vélocité */
        }
#else
        if (g_z[c - 1] && (follow(&zcur[i], g_z[c - 1], fresh) || fresh || refresh || pushed)) {
            u32 zc = zcur[i];
            amp_gain_write(v[0x35c / 4], ((v[0x334 / 4] >> 8) * (2 * zc + (zc >> 6))) >> 8);
        }
#endif
    }
    g_was = now;
}
#endif
