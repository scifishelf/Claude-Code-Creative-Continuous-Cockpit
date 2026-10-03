import unittest
from unittest import mock

from fivec import iterm, tabsync

A = "aaaaaaaa-2222-3333-4444-555555555555"
B = "bbbbbbbb-2222-3333-4444-555555555555"
C = "cccccccc-2222-3333-4444-555555555555"


def zeile(sid, zustand, name="", beschreibung="", cwd="/x/projekt"):
    return {"sid": sid, "zustand": zustand, "name": name, "beschreibung": beschreibung, "cwd": cwd}


class TabsyncTest(unittest.TestCase):
    def test_soll_nur_fuer_gemerkte_und_aktive(self):
        zeilen = [
            zeile(A, "hängt vielleicht", "Refold P5", "Zeile 1\nZeile 2"),
            zeile(B, "arbeitet"),          # nicht von 5C gestartet
            zeile(C, "ruht", "Alt"),       # ruht: kein Emoji, nichts anfassen
        ]
        gemerkt = {A: {"unique_id": "U-A"}, C: {"unique_id": "U-C"}}
        self.assertEqual(tabsync.soll_werte(zeilen, gemerkt), [("U-A", "🟠 Refold P5", "Refold P5\nZeile 1")])

    def test_ohne_namen_projekt_und_kurz_id(self):
        soll = tabsync.soll_werte([zeile(A, "wartet auf Dich")], {A: {"unique_id": "U"}})
        self.assertEqual(soll, [("U", "🟡 projekt aaaaaaaa", "projekt aaaaaaaa")])

    def test_abgleich_ein_aufruf_mit_flachen_argumenten(self):
        aufrufe = []

        def falsch_run(befehl, **kw):
            aufrufe.append(befehl)
            return mock.Mock(returncode=0, stdout="2", stderr="")

        with mock.patch("fivec.iterm.subprocess.run", falsch_run):
            n = iterm.abgleichen([("U1", "🟢 a", "a"), ("U2", "🟡 b", "b")])
        self.assertEqual(n, 2)
        self.assertEqual(len(aufrufe), 1)
        self.assertEqual(aufrufe[0][2:], ["U1", "🟢 a", "a", "U2", "🟡 b", "b"])

    def test_drossel_nur_bei_aenderung_oder_nachkontrolle(self):
        aufrufe = []
        falsch = mock.Mock(abgleichen=lambda soll: aufrufe.append(list(soll)) or 0)
        zeilen = [zeile(A, "arbeitet", "X")]
        uhr = iter([0.0, 2.0, 4.0, 4.1, 15.0])
        tabsync._zuletzt.update(soll=None, zeit=0.0)
        with mock.patch("fivec.tabsync.uebersicht.sessions", lambda s: zeilen), \
                mock.patch("fivec.tabsync.oeffnen.iterm_gemerkt", lambda: {A: {"unique_id": "U"}}):
            tabsync.einmal(falsch, jetzt=lambda: next(uhr))   # 0 s: erster Abgleich
            tabsync.einmal(falsch, jetzt=lambda: next(uhr))   # 2 s: unverändert, gedrosselt
            zeilen[0] = zeile(A, "wartet auf Dich", "X")
            tabsync.einmal(falsch, jetzt=lambda: next(uhr))   # 4 s: Zustand geändert
            tabsync.einmal(falsch, jetzt=lambda: next(uhr))   # 4,1 s: unverändert, gedrosselt
            tabsync.einmal(falsch, jetzt=lambda: next(uhr))   # 15 s: Nachkontrolle
        self.assertEqual([a[0][1] for a in aufrufe], ["🟢 X", "🟡 X", "🟡 X"])

    def test_nichts_zu_tun_kein_aufruf(self):
        with mock.patch("fivec.iterm.subprocess.run") as run:
            self.assertEqual(iterm.abgleichen([]), 0)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
