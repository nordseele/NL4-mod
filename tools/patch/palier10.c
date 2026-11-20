/* Palier 10 : palier 9, et le MPE se règle au menu MIDI au lieu de « canal global = 1 ».
 *
 * 2ᵉ version. La 1ʳᵉ ajoutait 4 réglages (n° 0x22 à 0x25) à la table des réglages
 * globaux : le clavier ne redémarrait plus. L'écouteur de ces réglages (fn_c00e3f70)
 * range des tableaux de 34 cases dans son propre objet ; nos n° écrasaient les champs
 * suivants (minuterie, pointeur de rappel). On ne touche donc plus au nombre de réglages.
 *
 * Les 4 options sont des champs du réglage 0x21, sauvegardé sur 31 bits mais de maximum 0
 * dans l'OS 1.32 (toujours 0, aucun lecteur) ; build.py passe son maximum à 0x1f :
 *   P  MPE           bit 0      Of / On   (zone basse : canaux 2 à 16, en plus du global)
 *   r  plage du bend bits 1–2   48 / 24 / 12 / 2 demi-tons
 *   y  Y → Wheel     bit 3      On / Of
 *   L  Z → Level     bit 4      On / Of
 * Tout à 0 = défauts. L'OS officiel lit une valeur > 0 hors bornes et la ramène à 0.
 * Entrées de menu clonées de PB Mode (MIDI 5), ajoutées après MIDI 8. Un changement relance
 * la création des zones (comme le canal global), qui relit le réglage.
 * Voir docs/patches.md, « Palier 10 en détail ».
 */
#define PALIER10 1
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

u32  global_get(u8 *app, u32 id);                    /* c00e270c */
static u32 mpe10_read(u8 *app);                      /* appelée par mpe_zone_setup */
int g_bend_unit = 384;                               /* 8192 × unité = plage << 16 */
#define BEND_UNIT g_bend_unit
static u8 g_y_off, g_z_off;
#ifdef PALIER11
static u8 g_ydest, g_zdest, g_ycurve, g_zcurve, g_zmul;   /* palier11.c */
enum { D_WHEEL, D_VEL, D_CUT, D_OFF, D_LEVEL, D_VLEV };   /* destinations de Y / Z */
enum { C_LIN, C_SQ, C_SOFT };                        /* courbes */
#endif

#include "palier2.c"
#include "palier3alias.c"
#include "palier9.c"

#define P_ID   0x21                                  /* réglage global qui porte nos options */
#ifdef PALIER11
#define NOURS  7
#else
#define NOURS  4
#endif

void *operator_new(u32 n);                                                       /* c0181b24 */
int   global_step(u8 *app, u32 id, u32 src, u32 clamp, int delta);               /* c00e2824 */
void  app_on_global_orig(u8 *app, u32 id, int *v);                               /* c00e0a1c */
void  app_routing_update(u8 *app);                                               /* c00e04cc */
int   menu_page_add(int *list, u32 page, void *entry);                           /* c0124cec */
void  menu_list_show_page_orig(int *list, u32 page, u32 x);                      /* c0124e7c */
void *pb_entry_ctor(void *e, u8 *app, void *display, const char *label);         /* c01001f8 */
u32   menu_entry_is_active(void *e);                                             /* c0125514 */
void  event_done(int *ev);                                                       /* c0130218 */

static const u16 bend_units[4] = { 384, 192, 96, 16 };            /* ±48, 24, 12, 2 */
#ifdef PALIER11
/* Palier 11 (bits du réglage 0x21 ; 0 = défaut = comportement du palier 10) :
 *   E MPE bit 0 · r bend bits 1–2 · y destination de Y bits 3–4 · P destination de Z bits 5–7
 *   C courbe de Y bits 8–9 · H courbe de Z bits 10–11 · v Z × vélocité bit 12
 * Ordre du menu = ordre du tableau. nO = molette (Wheel), vE = Velocity, Fr = Filter Freq,
 * LE = volume × Z, vL = Z à la place de la vélocité du volume (vL après Of : Of garde sa
 * valeur sauvegardée) ; Li = linéaire, CA = carrée, dO = douce. */
static const u8 shift[NOURS] = { 0, 1, 3, 8, 5, 10, 12 };
static const u8 fmask[NOURS] = { 1, 3, 3, 3, 7, 3, 1 };
static const u8 fmax[NOURS]  = { 1, 3, 3, 2, 5, 2, 1 };
/* E = MPE, P = Z (pression) : un Z s'afficherait comme un 2, déjà pris par Local. */
static const char labels[NOURS][2] = { "E", "r", "y", "C", "P", "H", "v" };
static const char names[NOURS][6][3] = {
    { "Of", "On" }, { "48", "24", "12", " 2" }, { "nO", "vE", "Fr", "Of" }, { "Li", "CA", "dO" },
    { "LE", "nO", "vE", "Fr", "Of", "vL" }, { "CA", "Li", "dO" }, { "Of", "On" } };

static u32 raw(u32 v, u32 k) { return v >> shift[k] & fmask[k]; }
static u32 field(u32 v, u32 k) { u32 f = raw(v, k); return f > fmax[k] ? 0 : f; }  /* hors plage : défaut */
#else
static const u8 shift[NOURS] = { 0, 1, 3, 4 }, fmax[NOURS] = { 1, 3, 1, 1 };
static const char labels[NOURS][2] = { "P", "r", "y", "L" };
static const char names[NOURS][4][3] = {
    { "Of", "On" }, { "48", "24", "12", " 2" }, { "On", "Of" }, { "On", "Of" } };

static u32 field(u32 v, u32 k) { return v >> shift[k] & fmax[k]; }
#define raw field
#endif
static u32 g_force;                                  /* valeur + 1 imposée par la molette ; 0 = lire */

#ifdef DIAG
static u8 g_setups;                                  /* créations des zones vues (diagnostic) */
#endif
#ifdef DIAG11
static u32 g_dvel, g_d3c, g_d3b0;                    /* dernière voix démarrée (palier11.c) */
#endif

static u32 mpe10_read(u8 *app)
{
#ifdef DIAG
    g_setups++;
#endif
    u32 v = g_force ? g_force - 1 : global_get(app, P_ID);
    g_bend_unit = bend_units[field(v, 1)];
#ifdef PALIER11
    static const u8 zdest[6] = { D_LEVEL, D_WHEEL, D_VEL, D_CUT, D_OFF, D_VLEV }, zcurve[3] = { C_SQ, C_LIN, C_SOFT };
    g_ydest = field(v, 2);                           /* D_WHEEL, D_VEL, D_CUT, D_OFF */
    g_ycurve = field(v, 3);                          /* C_LIN, C_SQ, C_SOFT */
    g_zdest = zdest[field(v, 4)];
    g_zcurve = zcurve[field(v, 5)];
    g_zmul = field(v, 6);
    g_y_off = g_ydest == D_OFF;
    g_z_off = g_zdest == D_OFF;
#else
    g_y_off = field(v, 2);
    g_z_off = field(v, 3);
#endif
    return field(v, 0);
}

/* Écouteur des réglages globaux de l'application (vtable 0xc03bf200). */
void mpe10_on_global(u8 *app, u32 id, int *v)
{
    if (id == P_ID) {
        app[0x1fe] = 1;                              /* zones à refaire, comme pour le canal global */
        app_routing_update(app);
        return;
    }
    app_on_global_orig(app, id, v);
}

/* Entrée de menu : objet de PB Mode (0x60 octets) + n° de l'option (0…3) en +0x60. */
static void mpe10_format(u32 *e, u32 v, char *buf, u32 size)
{
    u32 k = e[0x18], i = 0;
    const char *s = k < NOURS ? names[k][field(v, k)] : "--";
#ifdef DIAG
    /* r : nombre de zones de la cible du slot A ; y : créations des zones (mod 16) + g_mpe_on */
    static const char hex[] = "0123456789ABCDEF";
    char d[3];
    u8 *app = (u8 *)e[0x15];
    if (k == 1 || k == 2) {
        u32 n = k == 1 ? *(u32 *)(*(u8 **)(app + 0x160) + 0x430 + 0xf4)
                       : (u32)(g_setups & 15) << 4 | g_mpe_on;
        d[0] = hex[n >> 4 & 15];
        d[1] = hex[n & 15];
        d[2] = 0;
        s = d;
    }
#endif
#ifdef DIAG11
    /* Dernière note démarrée sur un canal membre, en hexadécimal : r = vélocité (voix[0x14]),
     * y C P H = les 4 octets de voix+0x3c (fort → faible), v = voix+0x3b0 >> 16 (gain). */
    static const char hex[] = "0123456789AbCdEF";   /* b, d : B et D ne s'affichent pas */
    char d[3];
    if (k >= 1 && k < NOURS) {
        u32 n = k == 1 ? g_dvel : k == 6 ? g_d3b0 >> 16 : g_d3c >> (8 * (5 - k));
        d[0] = hex[n >> 4 & 15];
        d[1] = hex[n & 15];
        d[2] = 0;
        s = d;
    }
#endif
    for (; i + 1 < size && s[i]; i++)
        buf[i] = s[i];
    if (size)
        buf[i] = 0;
}

static void mpe10_show(u32 *e, char *buf, u32 size)
{
    mpe10_format(e, global_get((u8 *)e[0x15], P_ID), buf, size);
}

void mpe10_turn(u32 *e, int *ev)                     /* comme fn_c0100a20 (PB Mode) */
{
    if (!menu_entry_is_active(e) || ev[2] != 2 || !(ev[1] & 1))   /* molette + Shift */
        return;
    u32 k = e[0x18];
    u8 *app = (u8 *)e[0x15];
    if (k < NOURS) {
        u32 v = global_get(app, P_ID);
        int f = field(v, k), n = f + ev[3], r = raw(v, k);    /* r ≠ f : champ hors plage */
        n = n < 0 ? 0 : n > fmax[k] ? fmax[k] : n;
        if (n != r) {                                /* seul ce champ change */
            int d = (n - r) * (1 << shift[k]);
            global_step(app, P_ID, 0xc08ee8b8, 1, d);
            /* L'application n'est pas prévenue du n° 0x21 (essai du 2026-11-20 : P.On n'agissait
             * qu'après un redémarrage) : refaire les zones ici, avec la nouvelle valeur. */
            g_force = v + d + 1;
            app[0x1fe] = 1;
            app_routing_update(app);
            g_force = 0;
        }
    }
    event_done(ev);
}

__attribute__((naked)) void mpe10_turn_thunk(void)  /* sous-objet +0xc : la molette arrive ici */
{
    __asm__("sub r0, r0, #12\n\tb mpe10_turn");
}

/* Copies des vtables de PB Mode (0xc03c37b0, 0xc03c37f0 ; vérifiées par build.py), avec nos
 * méthodes en [5] (molette), [12] (formatage), [13] (affichage). */
static const void *const vt_main[16] = {
    0, 0, (void *)0xc000145c, (void *)0xc00fef50, (void *)0xc0100b80, (void *)0xc00fef48,
    (void *)0xc00fef4c, (void *)mpe10_turn, (void *)0xc00fde6c, (void *)0xc00fde78,
    (void *)0xc01252ec, (void *)0xc0125354, (void *)0xc0125320, (void *)0xc01252e4,
    (void *)mpe10_format, (void *)mpe10_show };
static const void *const vt_sub[4] = {
    (void *)0xfffffff4, 0, (void *)0xc00fde84, (void *)mpe10_turn_thunk };

/* Remplace le dernier appel de menus_build : nos entrées vont à la fin de la page MIDI. */
void mpe10_menus_done(int *list, u32 page, u32 x)
{
    u32 *m = (u32 *)list - 3;                        /* objet menus : liste en +0xc */
    u32 midi = *(u32 *)(m[0x30] + 0x234);
    for (u32 i = 0; i < NOURS; i++) {
        u32 *e = operator_new(0x64);
        pb_entry_ctor(e, (u8 *)m[0x2a], (void *)m[0x2c], labels[i]);
        e[0] = (u32)&vt_main[2];
        e[3] = (u32)&vt_sub[2];
        e[0x18] = i;
        menu_page_add(list, midi, e);
    }
    menu_list_show_page_orig(list, page, x);
}
