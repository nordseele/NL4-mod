/* cc -o /tmp/t tools/patch/test_alias.c && /tmp/t */
#include <assert.h>
#include <stdio.h>
#include "alias.h"
int main(void)
{
    assert(alias_on(1, 60) == 60);                   /* canal 2 : note 60 telle quelle */
    assert(alias_on(2, 60) == 61);                   /* canal 3, même hauteur : 61 */
    assert(alias_on(3, 60) == 59);                   /* canal 4 : 59 */
    assert(alias_on(4, 61) == 62);                   /* vraie note 61 ailleurs : décalée */
    assert(alias_off(2, 60) == 61);                  /* Note Off du canal 3 : éteint 61 */
    assert(alias_on(5, 60) == 61);                   /* 61 libre à nouveau */
    assert(alias_on(1, 60) == 60);                   /* même canal, même note : même numéro */
    assert(alias_off(1, 60) == 60 && alias_off(3, 60) == 59);
    assert(alias_off(7, 40) == 40);                  /* Note Off sans Note On : tel quel */
    assert(alias_on(1, 127) == 127 && alias_on(2, 127) == 126);   /* bord haut */
    /* Note On et Note Off répétés pour chaque cible (palier 9, 1re version : notes bloquées) */
    assert(alias_on(8, 70) == 70 && alias_on(8, 70) == 70);
    assert(alias_on(9, 70) == 71 && alias_on(9, 70) == 71);
    assert(alias_off(9, 70) == 71 && alias_off(9, 70) == 71);
    assert(alias_off(8, 70) == 70 && alias_off(8, 70) == 70);
    assert(alias_on(10, 70) == 70);                  /* tout est libre à nouveau */
    assert(alias_on(9, 71) == 71);                   /* 71 libre, plus aliasé */
    assert(alias_on(11, 70) == 69);                  /* 71 pris par le canal 10 : autre voisin */
    assert(alias_on(12, 70) == 72);                  /* 70, 71, 69 pris : 72 */
    puts("alias ok");
    return 0;
}
