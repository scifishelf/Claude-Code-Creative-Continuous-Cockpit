import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from fivec import cli, mitteilung

A = "aaaaaaaa-2222-3333-4444-555555555555"
B = "bbbbbbbb-2222-3333-4444-555555555555"
REPO = Path(__file__).resolve().parent.parent


def zeile(sid, zustand, name="", tty="ttys001", waiting_for=None, prompts=("Baue den Index",), cwd_kurz="~/x/projekt"):
    return {"sid": sid, "zustand": zustand, "name": name, "erste_prompts": list(prompts), "cwd_kurz": cwd_kurz,
            "lauf": {"tty": tty, "waitingFor": waiting_for}}


class Uhr:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class AusloeserTest(unittest.TestCase):
    def test_nur_aus_arbeitet_oder_haengt(self):
        vorher = {A: "arbeitet", B: "hängt vielleicht"}
        self.assertEqual([z["sid"] for z in mitteilung.ausloeser(vorher, [zeile(A, "wartet auf Dich"), zeile(B, "wartet auf Dich")])],
                         [A, B])
        for alt in ("startet", "wartet auf Dich", "ruht", None):
            self.assertEqual(mitteilung.ausloeser({A: alt} if alt else {}, [zeile(A, "wartet auf Dich")]), [], alt)
        self.assertEqual(mitteilung.ausloeser({A: "arbeitet"}, [zeile(A, "hängt vielleicht")]), [])


class TexteTest(unittest.TestCase):
    def test_freigabe_und_fertig(self):
        self.assertEqual(mitteilung.texte(zeile(A, "wartet auf Dich", "Refold P5", waiting_for="permission prompt")),
                         ("Braucht Deine Freigabe", "Refold P5", "~/x/projekt"))
        self.assertEqual(mitteilung.texte(zeile(A, "wartet auf Dich", "Refold P5"))[0], "Fertig, wartet auf Dich")
        self.assertEqual(mitteilung.texte(zeile(A, "wartet auf Dich", waiting_for="input needed"))[0],
                         "Braucht Deine Antwort", "Rückfrage ist keine Freigabe")
        self.assertEqual(mitteilung.texte(zeile(A, "wartet auf Dich", waiting_for="unbekannt"))[0], "Braucht Deine Antwort")

    def test_ohne_namen_erster_prompt_einzeilig_und_gekuerzt(self):
        _, untertitel, _ = mitteilung.texte(zeile(A, "wartet auf Dich", prompts=["Zeile eins\nZeile zwei " + "x" * 80]))
        self.assertNotIn("\n", untertitel)
        self.assertTrue(untertitel.startswith("Zeile eins Zeile zwei"))
        self.assertLessEqual(len(untertitel), 60)
        self.assertTrue(untertitel.endswith("…"))
        self.assertEqual(mitteilung.texte(zeile(A, "wartet auf Dich", prompts=[]))[1], "Ohne Namen")

    def test_antwort_vier_zeilen_oder_leer(self):
        text = mitteilung.antwort(zeile(A, "wartet auf Dich", "N"))
        self.assertEqual(text.split("\n"), [mitteilung.MARKE, "Fertig, wartet auf Dich", "N", "~/x/projekt"])
        self.assertEqual(mitteilung.antwort(zeile(A, "arbeitet", "N")), "", "inzwischen weiter: nichts melden")
        self.assertEqual(mitteilung.antwort(None), "")

    def test_app_kennt_dieselbe_marke(self):
        self.assertIn(f'item 1 of teile is "{mitteilung.MARKE}"', (REPO / "werkzeug" / "app_bauen.sh").read_text())

    def test_app_klick_auch_bei_reopen(self):
        """Läuft das Applet beim Klick auf die Mitteilung noch, kommt reopen statt run."""
        quelle = (REPO / "werkzeug" / "app_bauen.sh").read_text()
        self.assertIn("on reopen\n\tklick()", quelle)
        self.assertIn("on run\n\tklick()", quelle)


class MelderTest(unittest.TestCase):
    def setUp(self):
        self.gesendet, self.gemerkt, self.uhr = [], [], Uhr()
        self.vorn = ""
        self.melder = mitteilung.Melder(sende=self.gesendet.append, vorne_tty=lambda: self.vorn,
                                        merken=self.gemerkt.append, uhr=self.uhr)

    def test_erster_blick_meldet_nichts(self):
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich")]), [])

    def test_wechsel_meldet_einmal(self):
        self.melder.takt([zeile(A, "arbeitet")])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich")]), [A])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich")]), [])
        self.assertEqual((self.gesendet, self.gemerkt), ([A], [A]))

    def test_sperre_je_session(self):
        self.melder.takt([zeile(A, "arbeitet"), zeile(B, "arbeitet")])
        self.melder.takt([zeile(A, "wartet auf Dich"), zeile(B, "arbeitet")])
        self.uhr.t = mitteilung.SPERRE_S - 1
        self.melder.takt([zeile(A, "arbeitet"), zeile(B, "arbeitet")])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich"), zeile(B, "wartet auf Dich")]), [B],
                         "A innerhalb der Sperre, B nicht betroffen")
        self.uhr.t = mitteilung.SPERRE_S + 1
        self.melder.takt([zeile(A, "arbeitet")])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich")]), [A])

    def test_tab_vorn_meldet_nicht(self):
        self.vorn = "/dev/ttys001"
        self.melder.takt([zeile(A, "arbeitet"), zeile(B, "arbeitet", tty="ttys002")])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich"), zeile(B, "wartet auf Dich", tty="ttys002")]), [B])

    def test_ohne_blick_auf_iterm_lieber_melden(self):
        def kaputt():
            raise RuntimeError("iTerm2 antwortet nicht")
        self.melder.vorne_tty = kaputt
        self.melder.takt([zeile(A, "arbeitet")])
        self.assertEqual(self.melder.takt([zeile(A, "wartet auf Dich")]), [A])

    def test_ohne_kandidaten_kein_osascript(self):
        self.melder.vorne_tty = mock.Mock(return_value="")
        self.melder.takt([zeile(A, "arbeitet")])
        self.melder.takt([zeile(A, "arbeitet")])
        self.melder.vorne_tty.assert_not_called()


class ZuletztTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"FIVEC_HOME": tempfile.mkdtemp()})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_einmal_nehmen(self):
        mitteilung.zuletzt_merken(A, jetzt=1000)
        self.assertEqual(mitteilung.zuletzt_nehmen(jetzt=1000 + mitteilung.KLICK_GILT_S), A)
        self.assertIsNone(mitteilung.zuletzt_nehmen(jetzt=1001), "ein zweiter Doppelklick öffnet die Übersicht")

    def test_abgelaufen(self):
        mitteilung.zuletzt_merken(A, jetzt=1000)
        self.assertIsNone(mitteilung.zuletzt_nehmen(jetzt=1001 + mitteilung.KLICK_GILT_S))

    def test_cli_klick_ohne_meldung_seite(self):
        aus = io.StringIO()
        with redirect_stdout(aus):
            self.assertEqual(cli.main(["klick"]), 0)
        self.assertEqual(aus.getvalue().strip(), "seite")

    def test_cli_klick_holt_gemeldete_nach_vorn(self):
        mitteilung.zuletzt_merken(A)
        with mock.patch("fivec.cli.oeffnen.oeffnen", return_value={"text": "In iTerm2 nach vorn geholt."}) as auf, \
                redirect_stdout(io.StringIO()) as aus:
            self.assertEqual(cli.main(["klick"]), 0)
        auf.assert_called_once_with(A)
        self.assertEqual(aus.getvalue(), "", "nach dem Klick keine zweite Mitteilung")

    def test_cli_melden_url(self):
        with mock.patch("fivec.cli.uebersicht.sessions", return_value=[zeile(A, "wartet auf Dich", "N")]), \
                redirect_stdout(io.StringIO()) as aus:
            self.assertEqual(cli.main(["open-url", f"fivec://melden/{A}"]), 0)
        self.assertEqual(aus.getvalue().split("\n")[0], mitteilung.MARKE)

    def test_cli_melden_url_ohne_gueltige_id_wie_open(self):
        with redirect_stdout(io.StringIO()) as aus:
            self.assertEqual(cli.main(["open-url", "fivec://melden/../../etc"]), 1)
        self.assertIn("Unbekannter Link", aus.getvalue())


if __name__ == "__main__":
    unittest.main()
