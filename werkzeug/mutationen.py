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
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                       cwd=ziel, capture_output=True, text=True)
    gefangen = r.returncode != 0
    durch += not gefangen
    print(f"{'gefangen' if gefangen else 'DURCHGERUTSCHT'}: {name}")
sys.exit(1 if durch else 0)
