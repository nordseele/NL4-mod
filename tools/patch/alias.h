/* Même hauteur sur deux canaux membres (palier 9). Le firmware identifie une note par
 * (slot, numéro) : deux doigts sur la même hauteur feraient une seule note. Une note déjà
 * tenue sur un autre canal entre sous le numéro libre le plus proche (± 12), et la voix
 * corrige sa hauteur de l'écart. Le firmware appelle Note On et Note Off une fois par cible
 * (c011f62c) : les deux fonctions doivent rendre le même numéro à chaque appel d'un même
 * événement. Fonctions pures, testées par test_alias.c. */
static unsigned char owner[128];                     /* canal + 1 qui joue ce numéro */
static unsigned char alias_of[16][128];              /* numéro joué + 1 pour (canal, note) */

static unsigned alias_on(unsigned ch, unsigned n)    /* ch 0…15, n 0…127 : numéro à jouer */
{
    unsigned a = alias_of[ch][n] ? alias_of[ch][n] - 1u : n;   /* dernier numéro de (canal, note) */
    if (owner[a] && owner[a] != ch + 1)              /* pris par un autre canal : repartir de n */
        a = n;
    if (owner[a] && owner[a] != ch + 1)
        for (unsigned d = 1; d <= 12; d++) {
            if (n + d < 128 && !owner[n + d]) { a = n + d; break; }
            if (n >= d && !owner[n - d]) { a = n - d; break; }
        }
    owner[a] = ch + 1;
    alias_of[ch][n] = a + 1;
    return a;
}

static unsigned alias_off(unsigned ch, unsigned n)   /* numéro à éteindre */
{
    unsigned a = alias_of[ch][n] ? alias_of[ch][n] - 1u : n;   /* gardé : cibles suivantes */
    if (owner[a] == ch + 1)
        owner[a] = 0;
    return a;
}
