/* Palier 11 : palier 10, avec les options MPE encore manquantes au menu MIDI (bits du
 * réglage 0x21, détail dans palier10.c sous PALIER11) :
 *   E  MPE (anciennement P)
 *   y  destination de Y : Wheel (nO), Velocity (vE), Filter Freq direct (Fr), Off
 *   P  destination de Z : volume (LE), Wheel, Velocity, Filter Freq, Off, vélocité du volume (vL)
 *   C, H  courbe de Y, de Z : linéaire, carrée, douce
 *   v  Z multiplié par la vélocité de la note
 *   canaux A–D sur un canal membre ignorés en mode MPE (palier2.c)
 * Les destinations Wheel / Velocity / Filter Freq passent toutes par le chemin paramètre par
 * paramètre du palier 7 : écart ajouté à la base de l'entrée de morph le temps de
 * voice_morph_eval, puis voice_param_handler. Y et Z vers des paramètres sont appliqués
 * ensemble (sinon l'un effacerait l'autre). Volume : la méthode du volume par voix (n° 0,
 * c0036dbc) ignore la valeur passée ; elle lit la vélocité en voix+0x42c (copie de
 * voix+0x3c, relevé du diagnostic), range le gain en voix+0x3b0 et l'envoie par
 * c005ee84 (SHARC DM 0x9248a). LE : ce gain × Z, renvoyé par c005ee84 (de 0 au volume
 * normal). vL : Z à la place de la vélocité en voix+0x42c, puis la méthode (≈ 6 dB
 * d'ampleur au plus, essai du 2026-11-20). Le gain des paliers 6 à 10 (amp_gain_write,
 * DM 0x9245c) et le paramètre n° 0 seul (2ᵉ version) n'avaient aucun effet.
 * Défauts (tous les bits à 0) : comme le palier 10, sauf Level. Voir docs/patches.md, « Palier 11 en détail ».
 */
#define PALIER11 1
#include "palier10.c"

#define CUTOFF 0x15             /* Filter Freq : table des noms {n°, groupe, nom, unité}, 0xc01c9d38 */
#define OUTLEVEL 0x00           /* Output Level (même table) ; méthode par voix c0036dbc : gain */
#define VEL_LEVEL (0x42c / 4)   /* vélocité lue par c0036dbc ; voice_push_params y recopie voix+0x3c */
void voice_level_write(u32 dsp_voice, u32 gain);   /* c005ee84 : gain de volume (8.23) au SHARC */

static u32 curve(u32 c, u32 q)                       /* q : 0…65532 ≈ 0…1 */
{
    if (c == C_SQ)
        return q * q >> 16;
    if (c == C_SOFT) {                               /* 1 − (1 − q)² : monte vite, puis s'aplatit */
        u32 r = 65535 - q;
        return 65535 - (r * r >> 16);
    }
    return q;
}

/* Écart de la base de l'entrée i pour une source de destination d et de valeur q (0…65535). */
static int term(u32 d, u32 s, int *e, u32 i, u32 q, u32 vel, u32 *hit)
{
    if (d == D_WHEEL && wq[s][i]) {                  /* comme la molette (palier 7) */
        *hit = 1;
        return (int)q * wq[s][i];                    /* q ≤ 65535, |wq| ≤ WQ_MAX : tient sur 31 bits */
    }
    if (d == D_VEL && e[5 * i + 1]) {
        /* voice_morph_eval ajoute qté × (vél + 1) / 128 : on remplace (vél + 1) / 128 par q */
        *hit = 1;
        return (int)((long long)e[5 * i + 1] * ((int)q - (int)((vel + 1) << 9)) >> 16);
    }
    if (d == D_CUT && i == CUTOFF) {                 /* q = 1 : toute la plage au-dessus du réglage */
        *hit = 1;
        return (int)(((long long)e[5 * i + 4] - e[5 * i + 3]) * q >> 16);
    }
    return 0;
}

static void apply(u32 *v, u32 s, u32 yq, u32 zq)     /* valeur + 1 ; 0 = source absente */
{
    int *desc = (int *)v[0x15];                      /* descripteur de morph du moteur */
    if (!desc)
        return;
    u32 n = (u32)desc[0] < NENT ? (u32)desc[0] : NENT;
    int *e = (int *)desc[3];                         /* {base, qté vél., qté clavier, min, max} */
    u32 vel = v[0x14];
    for (u32 i = 0; i < n; i++) {                    /* entrée de morph i = paramètre n° i */
        u32 hit = 0;
        int d = 0;
        if (yq)
            d += term(g_ydest, s, e, i, yq - 1, vel, &hit);
        if (zq)
            d += term(g_zdest, s, e, i, zq - 1, vel, &hit);
        if (!hit)
            continue;
        method m;
        e[5 * i] += d;
        int val = voice_morph_eval(v + 0x12, i);     /* v + 0x12 = voix+0x48 */
        e[5 * i] -= d;
        voice_param_handler(&m, v, i);
        m.fn(m.obj, val);
    }
}

static u32 level(u32 c) { return 2 * c + (c >> 6); }    /* lissé × 256 (0…32512) → 0…65532 */

void mpe_synth_tick(void)
{
    synth_tick_orig();
    if (!g_mpe_on)
        return;
    u32 refresh = g_refresh || !(++g_ticks & 31), read = 0, now = 0;
    g_refresh = 0;
    for (u32 c = 1; c < 16; c++) {                   /* le LinnStrument envoie Z = 0 juste avant */
        u8 z = g_z[c];                               /* le Note Off : ne pas couper la relâche */
        if (z == 1 && zt[c] > 1 && zwait[c] < ZWAIT)
            zwait[c]++;
        else {
            zt[c] = z;
            zwait[c] = 0;
        }
    }
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
        u32 fresh = !(g_was & 1u << i), s = *(u32 *)v[1];
        if (s >= 4)
            continue;
#ifdef DIAG11
        if (fresh) {                                 /* palier11diag.c : affiché au menu */
            g_dvel = v[0x14];
            g_d3c = v[0x3c / 4];
            g_d3b0 = v[0x3b0 / 4];
        }
#endif
        u32 y1 = g_y[c - 1], z1 = fresh ? g_z[c - 1] : zt[c - 1];   /* une note qui commence prend le Z reçu */
        u32 ym = y1 && (follow(&ycur[i], y1, fresh) || fresh || refresh);
        u32 zm = z1 && (follow(&zcur[i], z1, fresh) || fresh || refresh);
        u32 yq = y1 ? curve(g_ycurve, level(ycur[i])) + 1 : 0;
        u32 zc = curve(g_zcurve, level(zcur[i]));
        u32 zq = z1 ? (g_zmul ? zc * (v[0x14] + 1) >> 7 : zc) + 1 : 0;   /* × (vél + 1) / 128 */
        if ((ym && g_ydest < D_OFF) || (zm && g_zdest < D_OFF)) {
            if (refresh && !(read & 1u << s)) {
                read |= 1u << s;
                read_wheel(s);
            }
            apply(v, s, g_ydest < D_OFF ? yq : 0, g_zdest < D_OFF ? zq : 0);
        }
        if (zm && g_zdest == D_LEVEL)                /* gain du firmware × Z ; voix+0x3b0 intact */
            voice_level_write(v[0x3d8 / 4], (v[0x3b0 / 4] >> 8) * (zq - 1) >> 8);
        if (zm && g_zdest == D_VLEV) {               /* Z à la place de la vélocité du volume */
            method m;
            v[VEL_LEVEL] = ((zq - 1) * 127 + 32768) >> 16;
            voice_param_handler(&m, v, OUTLEVEL);
            m.fn(m.obj, (int)&v[VEL_LEVEL]);         /* valeur ignorée par c0036dbc */
        }
    }
    g_was = now;
}
