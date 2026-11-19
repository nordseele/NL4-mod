"""Scénarios MIDI reproductibles pour essayer les paliers MPE sur le Nord Lead 4.

  python3 tools/mpe_test.py --list
  python3 tools/mpe_test.py same-note          # (port par défaut : « Nord Lead 4 »)
  python3 tools/mpe_test.py chord8 --port "Nord Lead 4" --seconds 20

Zone MPE basse : canal maître 1, canaux membres 2 à 16 (mido les numérote 0 et 1–15).
Côté clavier : canal MIDI global = 1. Le bend des canaux membres vaut ±48 demi-tons.
Chaque scénario finit par un « tout éteint » sur les 16 canaux, même après Ctrl-C.
"""
import argparse, math, time
import mido

MASTER = 0
RATE = 200                                   # messages de contrôle par seconde et par note


def semis(st):                               # demi-tons → valeur de bend (±48 = ±8191)
    return max(-8192, min(8191, round(st * 8191 / 48)))


class Zone:
    """Un canal membre par note, comme un contrôleur MPE."""
    def __init__(self, out):
        self.out, self.free = out, list(range(1, 16))

    def send(self, type, **kw):
        self.out.send(mido.Message(type, **kw))

    def on(self, note, vel=100, y=64, z=0, ch=None):
        ch = self.free.pop(0) if ch is None else ch
        self.send('pitchwheel', channel=ch, pitch=0)            # état initial avant le Note On
        self.send('control_change', channel=ch, control=74, value=y)
        self.send('aftertouch', channel=ch, value=z)
        self.send('note_on', channel=ch, note=note, velocity=vel)
        return ch

    def off(self, ch, note):
        self.send('note_off', channel=ch, note=note, velocity=64)
        self.free.append(ch)

    def sweep(self, seconds, fn):
        """Appelle fn(t) RATE fois par seconde pendant `seconds`."""
        t0 = time.monotonic()
        while (t := time.monotonic() - t0) < seconds:
            fn(t)
            time.sleep(1 / RATE)

    def panic(self):
        for ch in range(16):
            self.send('control_change', channel=ch, control=123, value=0)
            self.send('pitchwheel', channel=ch, pitch=0)


def say(msg):
    print(f'  · {msg}', flush=True)


def same_note(z, a):
    """Deux fois la même note sur deux canaux : vélocités, bend et relâchement séparés ?"""
    say('C4 canal 2, vélocité 30'); c1 = z.on(60, vel=30); time.sleep(1.5)
    say('C4 canal 3, vélocité 127'); c2 = z.on(60, vel=127); time.sleep(1.5)
    say('bend +7 demi-tons sur le canal 3 seulement')
    z.sweep(1.5, lambda t: z.send('pitchwheel', channel=c2, pitch=semis(7 * t / 1.5)))
    time.sleep(1)
    say('relâche le canal 2 : la note du canal 3 doit continuer'); z.off(c1, 60); time.sleep(2)
    z.off(c2, 60)


def bend(z, a):
    """Deux notes, glissés en sens contraires, puis relâchement pendant un glissé."""
    c1, c2 = z.on(60), z.on(67)
    say('canal %d monte de 12, canal %d descend de 12' % (c1 + 1, c2 + 1))
    z.sweep(3, lambda t: (z.send('pitchwheel', channel=c1, pitch=semis(12 * t / 3)),
                          z.send('pitchwheel', channel=c2, pitch=semis(-12 * t / 3))))
    say('relâche en plein glissé (la release suit encore le canal)'); z.off(c1, 60)
    z.sweep(2, lambda t: z.send('pitchwheel', channel=c2, pitch=semis(-12 + 24 * t / 2)))
    z.off(c2, 67)


def ytest(z, a):
    """Accord de 3 notes, Y (CC74) en sinusoïdes déphasées : chaque note bouge seule."""
    notes = [48, 55, 64]
    chans = [z.on(n, y=0) for n in notes]
    say('Y de chaque note en sinusoïde, périodes 1 s, 2 s, 3 s')
    z.sweep(a.seconds, lambda t: [z.send('control_change', channel=c, control=74,
                                         value=round(63.5 + 63.5 * math.sin(2 * math.pi * t / (i + 1))))
                                  for i, c in enumerate(chans)])
    for c, n in zip(chans, notes):
        z.off(c, n)


def chord8(z, a):
    """Charge : 8 notes, Y et bend en mouvement continu sur chacune."""
    notes = [36, 43, 48, 52, 55, 60, 64, 67]
    chans = [z.on(n) for n in notes]
    say(f'8 notes, Y + bend continus pendant {a.seconds} s : écouter saccades et notes perdues')
    def step(t):
        for i, c in enumerate(chans):
            ph = 2 * math.pi * (t / 2 + i / 8)
            z.send('control_change', channel=c, control=74, value=round(63.5 + 63.5 * math.sin(ph)))
            z.send('pitchwheel', channel=c, pitch=semis(0.5 * math.sin(3 * ph)))
    z.sweep(a.seconds, step)
    for c, n in zip(chans, notes):
        z.off(c, n)


def pressure(z, a):
    """Z (pression par canal) sur deux notes, en sens contraires. Pour le palier Z."""
    c1, c2 = z.on(60, z=0), z.on(64, z=127)
    say('pression : canal %d monte, canal %d descend' % (c1 + 1, c2 + 1))
    z.sweep(a.seconds, lambda t: (z.send('aftertouch', channel=c1, value=round(127 * min(t / a.seconds, 1))),
                                  z.send('aftertouch', channel=c2, value=round(127 * max(1 - t / a.seconds, 0)))))
    z.off(c1, 60); z.off(c2, 64)


def master(z, a):
    """Le canal maître agit sur toutes les notes (bend du programme, CC74 habituel)."""
    c1, c2 = z.on(60), z.on(64)
    say('bend du canal 1 (plage du programme) sur les deux notes')
    z.sweep(2, lambda t: z.send('pitchwheel', channel=MASTER, pitch=round(8191 * math.sin(math.pi * t / 2))))
    say('CC74 du canal 1 : Filter Freq du panneau')
    z.sweep(2, lambda t: z.send('control_change', channel=MASTER, control=74, value=round(127 * t / 2)))
    z.off(c1, 60); z.off(c2, 64)


SCENARIOS = {'same-note': same_note, 'bend': bend, 'y': ytest, 'chord8': chord8,
             'pressure': pressure, 'master': master}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scenario', nargs='?', choices=[*SCENARIOS, 'all'])
    p.add_argument('--port', default='Nord Lead 4', help='sous-chaîne du nom du port de sortie')
    p.add_argument('--seconds', type=float, default=8, help='durée des balayages (y, chord8, pressure)')
    p.add_argument('--list', action='store_true', help='lister les ports et les scénarios')
    a = p.parse_args()
    if a.list or not a.scenario:
        print('ports :', *mido.get_output_names(), sep='\n  ')
        print('scénarios :', *(f'{k:10} {f.__doc__.strip()}' for k, f in SCENARIOS.items()), sep='\n  ')
        return
    names = [n for n in mido.get_output_names() if a.port in n]
    if not names:
        raise SystemExit(f'aucun port ne contient « {a.port} » (--list)')
    with mido.open_output(names[0]) as out:
        z = Zone(out)
        try:
            for name in (SCENARIOS if a.scenario == 'all' else [a.scenario]):
                print(f'{name} → {names[0]}')
                SCENARIOS[name](z, a)
                time.sleep(1)
        finally:
            z.panic()


if __name__ == '__main__':
    main()
