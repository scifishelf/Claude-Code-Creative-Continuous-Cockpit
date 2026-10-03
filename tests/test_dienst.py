import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from fivec import dienst, meta

SID = "11111111-2222-3333-4444-555555555555"
TOKEN = "test-token"


class DienstTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        projekt = self.tmp / "claude" / "projects" / "-p"
        projekt.mkdir(parents=True)
        (self.tmp / "claude" / "sessions").mkdir()
        (projekt / f"{SID}.jsonl").write_text(json.dumps({
            "type": "user", "timestamp": "2026-10-03T10:00:00Z", "cwd": "/gibt/es/nicht",
            "message": {"content": "hallo"},
        }) + "\n")
        self.env = mock.patch.dict(os.environ, {
            "CLAUDE_HOME": str(self.tmp / "claude"), "FIVEC_HOME": str(self.tmp / "5c"),
        })
        self.env.start()
        self.srv = dienst.server(0, token=TOKEN)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.env.stop()

    def anfrage(self, methode, pfad, koerper=None, host=None, kopf=None):
        verb = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        k = {"Host": host or f"127.0.0.1:{self.port}", **(kopf or {})}
        daten = None if koerper is None else json.dumps(koerper).encode()
        if daten is not None:
            k["Content-Type"] = "application/json"
        verb.request(methode, pfad, body=daten, headers=k)
        antwort = verb.getresponse()
        inhalt = antwort.read()
        verb.close()
        return antwort.status, inhalt

    def patch(self, koerper, **kw):
        kopf = {"X-5C-Token": TOKEN, **kw.pop("kopf", {})}
        return self.anfrage("PATCH", f"/api/sessions/{SID}", koerper, kopf=kopf, **kw)

    # --- Lesen -------------------------------------------------------------

    def test_liste(self):
        status, inhalt = self.anfrage("GET", "/api/sessions?alle=1")
        self.assertEqual(status, 200)
        zeilen = json.loads(inhalt)
        self.assertEqual([z["sid"] for z in zeilen], [SID])
        self.assertEqual(zeilen[0]["git"], {"art": "ordner_fehlt"})

    def test_seite_traegt_token(self):
        status, inhalt = self.anfrage("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(f'content="{TOKEN}"'.encode(), inhalt)

    def test_statische_dateien(self):
        for pfad, typ in (("/app.js", "text/javascript"), ("/logik.js", "text/javascript"),
                          ("/app.css", "text/css"), ("/logo.svg", "image/svg+xml"),
                          ("/schriften/geist.woff2", "font/woff2")):
            verb = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            verb.request("GET", pfad, headers={"Host": f"127.0.0.1:{self.port}"})
            antwort = verb.getresponse()
            antwort.read()
            self.assertEqual(antwort.status, 200, pfad)
            self.assertTrue(antwort.getheader("Content-Type").startswith(typ), pfad)
            self.assertIn("default-src 'self'", antwort.getheader("Content-Security-Policy"))
            verb.close()

    def test_kein_weg_aus_web_hinaus(self):
        for pfad in ("/../dienst.py", "/%2e%2e/dienst.py", "/web/app.js", "/schriften/../app.js", "/index.html"):
            status, _ = self.anfrage("GET", pfad)
            self.assertEqual(status, 404, pfad)

    def test_seite_ohne_platzhalter(self):
        _, inhalt = self.anfrage("GET", "/")
        self.assertNotIn(b"{{TOKEN}}", inhalt)

    def test_fremder_host_wird_abgewiesen(self):
        for pfad in ("/", "/api/sessions"):
            status, _ = self.anfrage("GET", pfad, host="boese.example:4555")
            self.assertEqual(status, 403, pfad)
        status, _ = self.patch({"name": "x"}, host="boese.example:4555")
        self.assertEqual(status, 403)

    # --- Schreiben ---------------------------------------------------------

    def test_name_und_beschreibung_setzen_und_lesen(self):
        status, inhalt = self.patch({"name": "Refold P2", "beschreibung": "Zeile 1\nZeile 2"})
        self.assertEqual(status, 200, inhalt)
        zeile = json.loads(self.anfrage("GET", "/api/sessions?alle=1")[1])[0]
        self.assertEqual(zeile["name"], "Refold P2")
        self.assertEqual(zeile["beschreibung"], "Zeile 1\nZeile 2")
        # Leeren entfernt den Eintrag.
        self.patch({"name": "", "beschreibung": ""})
        self.assertEqual(meta.laden(), {})

    def test_ohne_token_verboten(self):
        status, _ = self.anfrage("PATCH", f"/api/sessions/{SID}", {"name": "x"})
        self.assertEqual(status, 403)
        status, _ = self.patch({"name": "x"}, kopf={"X-5C-Token": "falsch"})
        self.assertEqual(status, 403)
        self.assertEqual(meta.laden(), {})

    def test_fremder_origin_verboten(self):
        status, _ = self.patch({"name": "x"}, kopf={"Origin": "https://boese.example"})
        self.assertEqual(status, 403)
        status, _ = self.patch({"name": "x"}, kopf={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)

    def test_unbekannte_und_ungueltige_ids(self):
        status, _ = self.anfrage("PATCH", "/api/sessions/../../etc", {"name": "x"}, kopf={"X-5C-Token": TOKEN})
        self.assertIn(status, (400, 404))
        status, _ = self.anfrage("PATCH", "/api/sessions/keine-uuid", {"name": "x"}, kopf={"X-5C-Token": TOKEN})
        self.assertEqual(status, 400)
        andere = "99999999-2222-3333-4444-555555555555"
        status, _ = self.anfrage("PATCH", f"/api/sessions/{andere}", {"name": "x"}, kopf={"X-5C-Token": TOKEN})
        self.assertEqual(status, 404)

    def test_boese_texte(self):
        for koerper in (
            {"name": "a\nb"},
            {"name": "x" * (meta.NAME_MAX + 1)},
            {"name": "evil‮txt"},
            {"name": "null​breite"},
            {"beschreibung": "esc\x1b]1337;SetBadgeFormat=x\x07"},
            {"farbe": "rot"},
            {"name": 5},
        ):
            status, _ = self.patch(koerper)
            self.assertEqual(status, 400, koerper)
        self.assertEqual(meta.laden(), {})


    # --- Ausblenden (E8) ---------------------------------------------------

    def projekt(self, koerper, kopf=None):
        return self.anfrage("PATCH", "/api/projekte", koerper, kopf={"X-5C-Token": TOKEN} if kopf is None else kopf)

    def test_session_ausblenden_und_einblenden(self):
        status, inhalt = self.patch({"ausgeblendet": True})
        self.assertEqual(status, 200, inhalt)
        zeile = json.loads(self.anfrage("GET", "/api/sessions?alle=1")[1])[0]
        self.assertTrue(zeile["ausgeblendet"])
        self.assertFalse(zeile["projekt_ausgeblendet"])
        self.patch({"ausgeblendet": False})
        self.assertEqual(meta.laden(), {}, "einblenden räumt den Eintrag weg")

    def test_projekt_ausblenden_und_einblenden(self):
        status, inhalt = self.projekt({"cwd": "/gibt/es/nicht", "ausgeblendet": True})
        self.assertEqual(status, 200, inhalt)
        zeile = json.loads(self.anfrage("GET", "/api/sessions?alle=1")[1])[0]
        self.assertTrue(zeile["projekt_ausgeblendet"])
        self.assertFalse(zeile["ausgeblendet"])
        self.projekt({"cwd": "/gibt/es/nicht", "ausgeblendet": False})
        self.assertEqual(meta.projekte_laden(), {})

    def test_projekt_nur_aus_dem_index(self):
        status, _ = self.projekt({"cwd": "/etc", "ausgeblendet": True})
        self.assertEqual(status, 404)
        status, _ = self.projekt({"ausgeblendet": True})
        self.assertEqual(status, 404)
        self.assertEqual(meta.projekte_laden(), {})

    def test_projekt_ohne_token_oder_mit_boesen_werten(self):
        status, _ = self.projekt({"cwd": "/gibt/es/nicht", "ausgeblendet": True}, kopf={})
        self.assertEqual(status, 403)
        for koerper in ({"cwd": "/gibt/es/nicht", "ausgeblendet": "ja"},
                        {"cwd": "/gibt/es/nicht", "ausgeblendet": 1},
                        {"cwd": "/gibt/es/nicht"},
                        {"cwd": "/gibt/es/nicht", "ausgeblendet": True, "name": "x"}):
            status, _ = self.projekt(koerper)
            self.assertEqual(status, 400, koerper)
        self.assertEqual(meta.projekte_laden(), {})

    def test_session_ausgeblendet_nur_wahrheitswert(self):
        status, _ = self.patch({"ausgeblendet": "true"})
        self.assertEqual(status, 400)
        self.assertEqual(meta.laden(), {})


if __name__ == "__main__":
    unittest.main()
