/* Palier 2 : un slot écoute aussi les canaux MIDI 2 à 16 (zone MPE basse), sans expression.
 *
 * Hook : l'unique appel à la création des zones de notes (fn_c00df898, depuis 0xc00e0540)
 * est redirigé vers mpe_zone_setup, qui appelle l'original puis ajoute, pour chaque slot,
 * des zones « suivent le canal global » (comme le canal global lui-même) pour les canaux
 * 2 à 16. Actif seulement si le canal global vaut 1 (index 0) ; sinon, comportement d'origine.
 * Voir docs/patches.md.
 */
typedef unsigned char u8;
typedef unsigned int u32;

unsigned char g_mpe_on;                              /* zone MPE active (lu par le palier 3) */

void zone_setup_orig(u8 *app);                       /* fn_c00df898 */
void zone_add_follow(u8 *target, u32 port, u32 ch);  /* fn_c0112b2c : zone (port, canal), drapeau 1 */

__attribute__((section(".text.entry")))
void mpe_zone_setup(u8 *app)
{
    zone_setup_orig(app);
#ifdef PALIER10
    g_mpe_on = mpe10_read(app);              /* option MPE du menu MIDI (palier10.c) */
#else
    g_mpe_on = *(u32 *)(app + 0x1e8) == 0;
#endif
    if (!g_mpe_on)                           /* canal global ≠ 1 : rien de plus */
        return;
    for (u32 slot = 0; slot < 4; slot++) {
        u8 *notes = *(u8 **)(app + 0x160 + 4 * slot) + 0x430;
        u8 *other = *(u8 **)(app + 0x180 + 4 * slot);
        for (u32 port = 0; port < 2; port++) {
            if (!app[0x1fc + port])          /* port MIDI désactivé */
                continue;
            for (u32 ch = 1; ch < 16; ch++) {
#ifdef PALIER10
                if (ch == *(u32 *)(app + 0x1e8))  /* canal global : a déjà sa zone */
                    continue;
#endif
                zone_add_follow(notes, port, ch);
                zone_add_follow(other, port, ch);
            }
        }
    }
}
