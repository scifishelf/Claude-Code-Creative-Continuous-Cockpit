"""Gegenprobe der Tests: jede Mutation baut einen Fehler in eine Kopie des Repos ein,
die Tests müssen ihn fangen. Aufruf: python3 werkzeug/mutationen.py"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MUTATIONEN = [
    ("UTC-Umrechnung weg", "fivec/live.py",
     "utc = calendar.timegm(", "utc = time.mktime("),
    ("halbe Zeile mitlesen", "fivec/index.py",
     'ende = daten.rfind(b"\\n")', "ende = len(daten) - 1"),
    ("Cache ignoriert", "fivec/index.py",
     "alt = _cache_laden(cache_pfad)", "alt = {}"),
    ("Startzeit nicht geprüft", "fivec/live.py",
     "echt = info is not None and gleiche_startzeit(", "echt = info is not None or gleiche_startzeit("),
    (".key mitgelesen", "fivec/live.py",
     'glob("*.json")', 'glob("*")'),
    ("fehlender Ordner als kein Repo", "fivec/gitstand.py",
     'return {"art": "ordner_fehlt"}', 'return {"art": "kein_repo"}'),
    ("Host-Prüfung weg", "fivec/dienst.py",
     'return self.headers.get("Host", "") in', 'return True or self.headers.get("Host", "") in'),
    ("Token-Prüfung weg", "fivec/dienst.py",
     'return hmac.compare_digest(self.headers.get("X-5C-Token", ""), self.token)', "return True"),
    ("Origin-Prüfung weg", "fivec/dienst.py",
     "if origin is not None and origin not in", "if False and origin not in"),
    ("unbekannte Session erlaubt", "fivec/dienst.py",
     "if sid not in uebersicht.index_aktuell():", "if False:"),
    ("Bidi-Zeichen erlaubt", "fivec/meta.py",
     "if _VERBOTEN.search(text):", "if False:"),
    ("Steuerzeichen erlaubt", "fivec/meta.py",
     'if unicodedata.category(z) == "Cc" and', 'if False and'),
    ("Längengrenze weg", "fivec/meta.py",
     "if len(text) > maximal:", "if False:"),
    ("Pfad-Kürzung ohne Grenze", "fivec/uebersicht.py",
     'cwd == heim or cwd.startswith(heim + "/")', "cwd.startswith(heim)"),
    ("Google Fonts eingebunden", "fivec/web/app.css",
     'src: url("/schriften/geist.woff2")', 'src: url("https://fonts.gstatic.com/geist.woff2")'),
    ("Name als HTML", "fivec/web/app.js",
     "if (text !== undefined) e.textContent = text;", "if (text !== undefined) e.innerHTML = text;"),
    ("Inline-Style in der Seite", "fivec/web/index.html",
     '<div class="seite">', '<div class="seite" style="color:red">'),
    ("unbekannter Zustand warnfarbig", "fivec/web/logik.js",
     'return KLASSEN[zustand] ?? "ruht";', 'return KLASSEN[zustand] ?? "verwaist";'),
    ("Ordner fehlt nicht gesperrt", "fivec/web/logik.js",
     'return { text: "Ordner fehlt", art: "fehlt", gesperrt: true };', 'return { text: "Ordner fehlt", art: "fehlt", gesperrt: false };'),
    ("statische Datei per Pfad", "fivec/dienst.py",
     "if url.path in STATISCH:", "if url.path.lstrip('/') and (WEB / url.path.lstrip('/')).is_file():\n            return self._senden(HTTPStatus.OK, (WEB / url.path.lstrip('/')).read_bytes(), 'text/plain')\n        if url.path in STATISCH:"),
]

PRUEFUNGEN = [
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
    ["node", "--test", "tests/js/*.test.mjs"],
]

durch = 0
for name, datei, alt, neu in MUTATIONEN:
    ziel = Path(tempfile.mkdtemp()) / "repo"
    shutil.copytree(REPO, ziel, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    pfad = ziel / datei
    text = pfad.read_text()
    if alt not in text:
        print(f"VERALTET: {name} - Stelle in {datei} nicht gefunden")
        durch += 1
        continue
    pfad.write_text(text.replace(alt, neu, 1))
    gefangen = any(
        subprocess.run(befehl, cwd=ziel, capture_output=True, text=True).returncode != 0
        for befehl in PRUEFUNGEN
    )
    durch += not gefangen
    print(f"{'gefangen' if gefangen else 'DURCHGERUTSCHT'}: {name}")
sys.exit(1 if durch else 0)
