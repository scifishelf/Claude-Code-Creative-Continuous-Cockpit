import json
import os
import shlex
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from fivec import iterm, oeffnen

SID = "11111111-2222-3333-4444-555555555555"


class FalschesIterm:
    def __init__(self, gefunden="UID-1"):
        self.gefunden = gefunden
        self.fokus = []
        self.starts = []
        self._lock = threading.Lock()

    def fokussieren(self, uid, tty):
        self.fokus.append((uid, tty))
        return self.gefunden

    def starten(self, befehl, titel, badge):
        with self._lock:
            self.starts.append((befehl, titel, badge))
        time.sleep(0.05)  # damit ein paralleler Aufruf wirklich überlappt
        return f"UID-{len(self.starts)}", "/dev/ttys099"


class OeffnenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cwd = self.tmp / "projekt mit 'quote'"
        self.cwd.mkdir()
        self.env = mock.patch.dict(os.environ, {"FIVEC_HOME": str(self.tmp / "5c")})
        self.env.start()
        self.it = FalschesIterm()
        self.aktiviert = []

    def tearDown(self):
        self.env.stop()

    def lauf(self, sid=SID, laufende=None, cwd=None, app="/Applications/iTerm.app", am_tty=None):
        return oeffnen.oeffnen(
            sid, it=self.it, laufende=laufende or {},
            index={SID: {"sid": SID, "cwd": str(cwd or self.cwd)}},
            notizen={SID: {"name": "Refold P4", "beschreibung": "Zeile 1\nZeile 2"}},
            app_von=lambda pid: app, aktivieren=self.aktiviert.append,
            am_tty=am_tty or (lambda tty, sid: False),
        )

    # --- Starten -------------------------------------------------------------

    def test_startet_ruhende_session(self):
        e = self.lauf()
        self.assertEqual(e["ergebnis"], "gestartet")
        befehl, titel, badge = self.it.starts[0]
        self.assertEqual(titel, "🔵 Refold P4")
        self.assertEqual(badge, "Refold P4\nZeile 1")
        self.assertEqual(befehl, f"cd {shlex.quote(str(self.cwd))} && caffeinate -dims claude --resume {SID}")

    def test_befehl_ist_shell_sicher(self):
        boese = self.tmp / "a; rm -rf ~ $(whoami)"
        boese.mkdir()
        self.lauf(cwd=boese)
        befehl = self.it.starts[0][0]
        self.assertIn(shlex.quote(str(boese)), befehl)
        teile = shlex.split(befehl)
        self.assertEqual(teile[:3], ["cd", str(boese), "&&"])

    def test_kein_doppelstart_hintereinander(self):
        self.lauf()
        e = self.lauf()
        self.assertEqual(e["ergebnis"], "startet")
        self.assertEqual(len(self.it.starts), 1)
        self.assertEqual(self.it.fokus[-1], ("UID-1", None))

    def test_kein_doppelstart_gleichzeitig(self):
        ergebnisse = []
        faeden = [threading.Thread(target=lambda: ergebnisse.append(self.lauf()["ergebnis"])) for _ in range(5)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join()
        self.assertEqual(len(self.it.starts), 1, ergebnisse)
        self.assertEqual(sorted(ergebnisse), ["gestartet"] + ["startet"] * 4)

    def test_abgelaufene_sperre_erlaubt_neuen_start(self):
        self.lauf()
        sperre = Path(os.environ["FIVEC_HOME"]) / "sperren" / SID
        alt = time.time() - oeffnen.SPERRE_S - 1
        os.utime(sperre, (alt, alt))
        self.assertEqual(self.lauf()["ergebnis"], "gestartet")
        self.assertEqual(len(self.it.starts), 2)

    def test_langsamer_start_nach_ablauf_der_sperre(self):
        """Läuft am gemerkten TTY schon claude --resume, gibt es keinen zweiten Start."""
        self.lauf()
        sperre = Path(os.environ["FIVEC_HOME"]) / "sperren" / SID
        alt = time.time() - oeffnen.SPERRE_S - 1
        os.utime(sperre, (alt, alt))
        e = self.lauf(am_tty=lambda tty, sid: tty == "/dev/ttys099" and sid == SID)
        self.assertEqual(e["ergebnis"], "startet")
        self.assertEqual(len(self.it.starts), 1)

    def test_gescheiterter_start_sperrt_nicht(self):
        class Kaputt(FalschesIterm):
            def starten(self, *a):
                raise iterm.ItermFehler(iterm.KEINE_FREIGABE)
        self.it = Kaputt()
        with self.assertRaises(iterm.ItermFehler):
            self.lauf()
        self.it = FalschesIterm()
        self.assertEqual(self.lauf()["ergebnis"], "gestartet")

    def test_ordner_fehlt(self):
        with self.assertRaises(oeffnen.OeffnenFehler):
            self.lauf(cwd=self.tmp / "weg")
        self.assertEqual(self.it.starts, [])

    def test_unbekannt_und_ungueltig(self):
        with self.assertRaises(oeffnen.OeffnenFehler):
            self.lauf(sid="99999999-2222-3333-4444-555555555555")
        with self.assertRaises(oeffnen.OeffnenFehler):
            self.lauf(sid="../../etc")
        self.assertEqual(self.it.starts, [])

    # --- Laufende Sessions ---------------------------------------------------

    def test_laufend_in_iterm_wird_nach_vorn_geholt(self):
        lauf = {SID: {"zustand": "läuft", "pid": 42, "tty": "ttys003"}}
        e = self.lauf(laufende=lauf)
        self.assertEqual(e["ergebnis"], "vorn")
        self.assertEqual(self.it.fokus, [(None, "ttys003")])
        self.assertEqual(self.it.starts, [])

    def test_laufend_anderswo_aktiviert_die_app(self):
        lauf = {SID: {"zustand": "läuft", "pid": 42, "tty": "ttys003"}}
        e = self.lauf(laufende=lauf, app="/Applications/Cursor.app")
        self.assertEqual(e["ergebnis"], "anderswo")
        self.assertIn("Cursor", e["text"])
        self.assertEqual(self.aktiviert, ["/Applications/Cursor.app"])
        self.assertEqual(self.it.starts, [])

    def test_verwaist_wird_neu_gestartet(self):
        lauf = {SID: {"zustand": "verwaist", "pid": 42, "tty": None}}
        self.assertEqual(self.lauf(laufende=lauf)["ergebnis"], "gestartet")


class UrlTest(unittest.TestCase):
    def test_nur_open_mit_uuid(self):
        self.assertEqual(oeffnen.sid_aus_url(f"fivec://open/{SID}"), SID)
        self.assertEqual(oeffnen.sid_aus_url(f"fivec://open/{SID}/"), SID)
        for url in (f"fivec://start/{SID}", "fivec://open/../../x", f"fivec://open/{SID}?cwd=/tmp",
                    f"http://open/{SID}", f"fivec://open/{SID};rm"):
            with self.assertRaises(oeffnen.OeffnenFehler, msg=url):
                oeffnen.sid_aus_url(url)


class ItermSkriptTest(unittest.TestCase):
    def test_werte_gehen_als_argumente_nicht_ins_skript(self):
        aufrufe = []

        def falsch_run(befehl, **kw):
            aufrufe.append((befehl, kw.get("input", "")))
            return mock.Mock(returncode=0, stdout="UID|/dev/ttys001", stderr="")

        titel = 'x" & do shell script "boese'
        with mock.patch("fivec.iterm.subprocess.run", falsch_run), \
                mock.patch("fivec.iterm.profil_sicherstellen") as profil:
            iterm.starten("echo hallo", titel, "badge")
        profil.assert_called_once()
        befehl, skript = aufrufe[0]
        self.assertEqual(befehl[:2], ["osascript", "-"])
        self.assertEqual(befehl[2:], ["echo hallo", titel, "badge", iterm.PROFIL])
        self.assertNotIn("boese", skript)

    def test_profil_schuetzt_den_titel(self):
        datei = Path(tempfile.mkdtemp()) / "DynamicProfiles" / "5c.json"
        self.assertTrue(iterm.profil_sicherstellen(datei))
        self.assertFalse(iterm.profil_sicherstellen(datei), "unverändert: nicht neu schreiben")
        profil = json.loads(datei.read_text())["Profiles"][0]
        self.assertEqual(profil["Name"], iterm.PROFIL)
        self.assertIs(profil["Allow Title Setting"], False)
        self.assertEqual(profil["Title Components"], 1)
        self.assertEqual(profil["Badge Text"], r"\(user.fivec_badge)")

    def test_freigabe_fehlt_wird_erklaert(self):
        with mock.patch("fivec.iterm.subprocess.run",
                        return_value=mock.Mock(returncode=1, stdout="", stderr="execution error: (-1743)")):
            with self.assertRaises(iterm.ItermFehler) as ctx:
                iterm.fokussieren("x", None)
        self.assertIn("Automation", str(ctx.exception))

    def test_tty_voll(self):
        self.assertEqual(iterm.tty_voll("ttys003"), "/dev/ttys003")
        self.assertEqual(iterm.tty_voll("/dev/ttys003"), "/dev/ttys003")
        self.assertEqual(iterm.tty_voll(None), "")


if __name__ == "__main__":
    unittest.main()
