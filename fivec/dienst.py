"""Lokaler Webserver: liefert die Seite und die JSON-API.

Schutz (Plan, Abschnitt Sicherheit):
- nur an 127.0.0.1 gebunden;
- `Host` muss 127.0.0.1:<port> oder localhost:<port> sein (gegen DNS-Rebinding);
- schreibende Aufrufe brauchen den Kopf `X-5C-Token` mit dem Token, das nur die
  ausgelieferte Seite kennt, und ein fremder `Origin` wird abgewiesen.

API:
  GET   /api/sessions?stunden=48   (oder ?alle=1)
  PATCH /api/sessions/<id>         {"name": …, "beschreibung": …, "ausgeblendet": true|false}
  PATCH /api/projekte              {"cwd": …, "ausgeblendet": true|false}   (cwd muss im Index stehen)
  POST  /api/sessions/<id>/open    nach vorn holen oder in iTerm2 fortsetzen (fivec/oeffnen.py)
"""

import hmac
import json
import secrets
import threading
from http import HTTPStatus
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import iterm, meta, oeffnen, tabsync, uebersicht

PORT = 4555
MAX_KOERPER = 16 * 1024
WEB = Path(__file__).resolve().parent / "web"

# Feste Liste statt Dateisystem-Zugriff über den Pfad: so gibt es keinen Weg aus `web/` hinaus.
STATISCH = {
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logik.js": ("logik.js", "text/javascript; charset=utf-8"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
    "/schriften/geist.woff2": ("schriften/geist.woff2", "font/woff2"),
    "/schriften/geist-mono.woff2": ("schriften/geist-mono.woff2", "font/woff2"),
}
CSP = "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"


class Handler(BaseHTTPRequestHandler):
    server_version = "5C"
    token: str = ""
    port: int = PORT

    def log_message(self, *args):  # ruhig bleiben, der Dienst läuft unter launchd
        pass

    # --- Antworten ---------------------------------------------------------

    def _senden(self, status: int, koerper: bytes, typ: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(koerper)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(koerper)

    def _json(self, status: int, daten) -> None:
        self._senden(status, json.dumps(daten, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _fehler(self, status: int, text: str) -> None:
        self._json(status, {"fehler": text})

    # --- Prüfungen ---------------------------------------------------------

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def _schreiben_erlaubt(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is not None and origin not in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            return False
        return hmac.compare_digest(self.headers.get("X-5C-Token", ""), self.token)

    # --- Routen ------------------------------------------------------------

    def do_GET(self):
        if not self._host_ok():
            return self._fehler(HTTPStatus.FORBIDDEN, "fremder Host")
        url = urlsplit(self.path)
        if url.path == "/":
            seite = (WEB / "index.html").read_text().replace("{{TOKEN}}", self.token)
            return self._senden(HTTPStatus.OK, seite.encode(), "text/html; charset=utf-8")
        if url.path in STATISCH:
            datei, typ = STATISCH[url.path]
            return self._senden(HTTPStatus.OK, (WEB / datei).read_bytes(), typ)
        if url.path == "/api/sessions":
            q = parse_qs(url.query)
            try:
                stunden = None if q.get("alle") == ["1"] else float(q.get("stunden", ["48"])[0])
            except ValueError:
                return self._fehler(HTTPStatus.BAD_REQUEST, "stunden muss eine Zahl sein")
            return self._json(HTTPStatus.OK, uebersicht.sessions(stunden))
        self._fehler(HTTPStatus.NOT_FOUND, "nicht gefunden")

    def do_PATCH(self):
        if not self._host_ok():
            return self._fehler(HTTPStatus.FORBIDDEN, "fremder Host")
        if not self._schreiben_erlaubt():
            return self._fehler(HTTPStatus.FORBIDDEN, "Token fehlt oder fremder Origin")
        teile = urlsplit(self.path).path.strip("/").split("/")
        if teile == ["api", "projekte"]:
            return self._projekt_patch()
        if len(teile) != 3 or teile[:2] != ["api", "sessions"]:
            return self._fehler(HTTPStatus.NOT_FOUND, "nicht gefunden")
        sid = teile[2]
        if not meta.UUID.match(sid):
            return self._fehler(HTTPStatus.BAD_REQUEST, "keine gültige Session-ID")
        if sid not in uebersicht.index_aktuell():
            return self._fehler(HTTPStatus.NOT_FOUND, "Session unbekannt")
        daten = self._json_koerper()
        if daten is None:
            return
        try:
            eintrag = meta.setzen(sid, daten)
        except meta.Ungueltig as e:
            return self._fehler(HTTPStatus.BAD_REQUEST, str(e))
        self._json(HTTPStatus.OK, {"sid": sid, **eintrag})

    def _json_koerper(self) -> dict | None:
        """JSON-Objekt aus dem Körper, oder None nach bereits gesendeter Fehlerantwort."""
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge > MAX_KOERPER:
            self._fehler(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "zu groß")
            return None
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
            if not isinstance(daten, dict):
                raise ValueError
        except ValueError:
            self._fehler(HTTPStatus.BAD_REQUEST, "kein JSON-Objekt")
            return None
        return daten

    def _projekt_patch(self):
        daten = self._json_koerper()
        if daten is None:
            return
        cwd = daten.pop("cwd", None)
        if cwd not in {e.get("cwd") for e in uebersicht.index_aktuell().values()} - {None}:
            return self._fehler(HTTPStatus.NOT_FOUND, "Projekt unbekannt")
        try:
            ergebnis = meta.projekt_setzen(cwd, daten)
        except meta.Ungueltig as e:
            return self._fehler(HTTPStatus.BAD_REQUEST, str(e))
        self._json(HTTPStatus.OK, ergebnis)

    def do_POST(self):
        if not self._host_ok():
            return self._fehler(HTTPStatus.FORBIDDEN, "fremder Host")
        if not self._schreiben_erlaubt():
            return self._fehler(HTTPStatus.FORBIDDEN, "Token fehlt oder fremder Origin")
        teile = urlsplit(self.path).path.strip("/").split("/")
        if len(teile) != 4 or teile[:2] != ["api", "sessions"] or teile[3] != "open":
            return self._fehler(HTTPStatus.NOT_FOUND, "nicht gefunden")
        try:
            ergebnis = oeffnen.oeffnen(teile[2])
        except (oeffnen.OeffnenFehler, iterm.ItermFehler) as e:
            return self._fehler(HTTPStatus.CONFLICT, str(e))
        self._json(HTTPStatus.OK, ergebnis)


def server(port: int = PORT, token: str | None = None) -> ThreadingHTTPServer:
    """Server bauen, nicht starten. Port 0 wählt einen freien Port (für Tests)."""
    handler = type("FivecHandler", (Handler,), {"token": token or secrets.token_urlsafe(32)})
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    handler.port = srv.server_address[1]
    return srv


def starten(port: int = PORT) -> None:
    srv = server(port)
    stopp = threading.Event()
    tabsync.starten(stopp, protokoll=lambda text: print(text, flush=True))
    print(f"5C läuft auf http://127.0.0.1:{srv.server_address[1]}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stopp.set()
        srv.server_close()
