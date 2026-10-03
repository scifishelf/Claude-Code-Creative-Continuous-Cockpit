"""Gegenprobe der Tests: jede Mutation baut einen Fehler in eine Kopie des Repos ein,
die Tests müssen ihn fangen. Aufruf: python3 werkzeug/mutationen.py"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MUTATIONEN = [
    ("laufende Session ausblendbar", "fivec/web/logik.js",
     "return Boolean(zeile.ausgeblendet || zeile.projekt_ausgeblendet) && !laeuft(zeile);",
     "return Boolean(zeile.ausgeblendet || zeile.projekt_ausgeblendet);"),
    ("Projekt-Ausblenden wirkungslos", "fivec/web/logik.js",
     "return Boolean(zeile.ausgeblendet || zeile.projekt_ausgeblendet) &&", "return Boolean(zeile.ausgeblendet) &&"),
    ("Gruppen ohne Vorrang für laufende", "fivec/web/logik.js",
     "gruppen.sort((a, b) => Number(b.laufend > 0) - Number(a.laufend > 0) || neuer(a, b));", "gruppen.sort(neuer);"),
    ("eingeklappt versteckt laufende", "fivec/web/logik.js",
     "zeilen: zu ? liste.filter(laeuft) : liste,", "zeilen: zu ? [] : liste,"),
    ("Suche nach dem Gruppieren vergessen", "fivec/web/logik.js",
     "const passend = zeilen.filter((z) => passtZurSuche(z, suche));", "const passend = zeilen;"),
    ("Projekt beliebig ausblendbar", "fivec/dienst.py",
     'if cwd not in {e.get("cwd") for e in uebersicht.index_aktuell().values()} - {None}:', "if not cwd:"),
    ("ausgeblendet als beliebiger Wert", "fivec/meta.py",
     "    if not isinstance(wert, bool):\n", "    if False:\n"),
    ("Projekt-Flag nicht in der Liste", "fivec/uebersicht.py",
     '"projekt_ausgeblendet": cwd in projekte_aus,', '"projekt_ausgeblendet": False,'),
    ("Mitteilung beim ersten Blick", "fivec/mitteilung.py",
     'vorher.get(z["sid"]) in AUS]', 'vorher.get(z["sid"]) != NACH]'),
    ("Mitteilung ohne Sperre", "fivec/mitteilung.py",
     '        kandidaten = [z for z in kandidaten if t - self.gemeldet.get(z["sid"], -SPERRE_S - 1) > SPERRE_S]\n', ""),
    ("Mitteilung trotz Tab vorn", "fivec/mitteilung.py",
     "if vorn and vorn == iterm.tty_voll(", "if False and vorn == iterm.tty_voll("),
    ("Rückfrage als Freigabe", "fivec/mitteilung.py",
     '"input needed": "Braucht Deine Antwort",', '"input needed": "Braucht Deine Freigabe",'),
    ("fertig als Antwort", "fivec/mitteilung.py",
     '"": "Fertig, wartet auf Dich",', ""),
    ("Klick ohne reopen", "werkzeug/app_bauen.sh",
     "on reopen\n\tklick()\nend reopen\n", ""),
    ("Untertitel mehrzeilig", "fivec/mitteilung.py",
     'text = " ".join((text or "").split())', 'text = text or ""'),
    ("veraltete Meldung gezeigt", "fivec/mitteilung.py",
     'if not zeile or zeile["zustand"] != NACH:', "if not zeile:"),
    ("Klick-Merker nicht verbraucht", "fivec/mitteilung.py",
     "        pfad.unlink()\n", ""),
    ("Klick-Merker läuft nie ab", "fivec/mitteilung.py",
     ' or jetzt - float(daten.get("zeit", 0)) > KLICK_GILT_S:', ":"),
    ("Klick zeigt zweite Mitteilung", "fivec/cli.py",
     "        if code:\n            print(text)", "        print(text)"),
    ("Takt holt eigene Übersicht", "fivec/tabsync.py",
     "zeilen = uebersicht.sessions(0) if zeilen is None else zeilen", "zeilen = uebersicht.sessions(0)"),
    ("status waiting nicht wartend", "fivec/gesundheit.py",
     'if status in ("idle", "waiting"):', 'if status == "idle":'),
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
    ("Startsperre aus", "fivec/oeffnen.py",
     "if am_tty(gemerkt.get(\"tty\", \"\"), sid) or not sperre_nehmen(sid):", "if am_tty(gemerkt.get(\"tty\", \"\"), sid):"),
    ("Sperre nicht atomar", "fivec/oeffnen.py",
     "os.close(os.open(pfad, os.O_CREAT | os.O_EXCL | os.O_WRONLY))\n            return True",
     "if pfad.exists() and time.time() - pfad.stat().st_mtime < SPERRE_S:\n                return False\n            time.sleep(0.01)\n            pfad.touch()\n            return True"),
    ("TTY-Prüfung aus", "fivec/oeffnen.py",
     "if am_tty(gemerkt.get(\"tty\", \"\"), sid) or not", "if not"),
    ("cwd ungequotet", "fivec/oeffnen.py",
     'f"cd {shlex.quote(cwd)} && ', 'f"cd {cwd} && '),
    ("Sperre bleibt nach Fehlstart", "fivec/oeffnen.py",
     "_sperre(sid).unlink(missing_ok=True)", "pass"),
    ("URL-Filter ohne End-Anker", "fivec/oeffnen.py",
     '[0-9a-f]{12})/?$")', '[0-9a-f]{12})/?")'),
    ("Wert ins AppleScript", "fivec/iterm.py",
     'uid, _, tty = _osa(_STARTEN, befehl, titel, badge, PROFIL).partition("|")',
     'uid, _, tty = _osa(_STARTEN.replace("item 2 of argv", \'"\' + titel + \'"\'), befehl, "", badge, PROFIL).partition("|")'),
    ("Programme dürfen den Titel setzen", "fivec/iterm.py",
     '"Allow Title Setting": False,', '"Allow Title Setting": True,'),
    ("Start ohne Profil", "fivec/iterm.py",
     "    profil_sicherstellen()\n    uid", "    uid"),
    ("hängt schon bei einer Bedingung", "fivec/gesundheit.py",
     "busy_seit > HAENGT_NACH_S and still > HAENGT_NACH_S", "(busy_seit > HAENGT_NACH_S or still > HAENGT_NACH_S)"),
    ("hängt auch bei idle", "fivec/gesundheit.py",
     '    if status in ("idle", "waiting"):\n        return {"zustand": "wartet auf Dich", "still_s": None}\n', ""),
    ("startet zählt caffeinate mit", "fivec/prozesse.py",
     "        if not _ist_claude(p[\"command\"]):\n            continue\n", ""),
    ("App aus login-Argument", "fivec/prozesse.py",
     'return None if " -" in vorn else vorn + ".app"', 'return vorn + ".app"'),
    ("Tab-Abgleich fasst fremde Tabs an", "fivec/tabsync.py",
     "        if not uid or not emoji:\n            continue\n", "        if not emoji:\n            continue\n        uid = uid or 'fremd'\n"),
    ("Abgleich ohne Emoji", "fivec/tabsync.py",
     'soll.append((uid, f"{emoji} {name}", badge))', 'soll.append((uid, name, badge))'),
    ("Drossel ignoriert Änderungen", "fivec/tabsync.py",
     'if soll == _zuletzt["soll"] and t', 'if t'),
    ("keine Nachkontrolle", "fivec/tabsync.py",
     'and t - _zuletzt["zeit"] < NACHKONTROLLE_S:', ":"),
    ("startet nicht als aktiv", "fivec/uebersicht.py",
     'aktiv = g["zustand"] not in ("ruht", "verwaist")', 'aktiv = lauf is not None and lauf["zustand"] == "läuft"'),
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
