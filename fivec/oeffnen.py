"""`5c open <id>`: laufende Session nach vorn holen, sonst in iTerm2 fortsetzen.

Kein Doppelstart (Plan, Ablauf "Klick auf eine Session"):
1. Läuft die Session (Statusdatei, pid und procStart passen), wird ihr Fenster
   gesucht: in iTerm2 über die gespeicherte unique ID oder das TTY, sonst wird
   die App aktiviert, in der sie läuft (z. B. Cursor).
2. Eine Startsperre von 15 s fängt den Doppelklick ab, solange `claude` noch keine
   Statusdatei geschrieben hat.
3. Erst dann wird gestartet. cwd und Befehl kommen aus dem Index, nie aus der URL.
"""

import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from . import iterm, live, meta, pfade, uebersicht

SPERRE_S = 15
URL = re.compile(r"^fivec://open/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$")


class OeffnenFehler(ValueError):
    pass


def sid_aus_url(url: str) -> str:
    treffer = URL.match(url.strip())
    if not treffer:
        raise OeffnenFehler("Unbekannter Link. Erwartet: fivec://open/<session-id>")
    return treffer.group(1)


# --- gemerkte iTerm2-Sessions -----------------------------------------------

def _iterm_pfad() -> Path:
    return pfade.fivec_home() / "iterm.json"


def _iterm_laden() -> dict:
    try:
        return json.loads(_iterm_pfad().read_text())
    except (OSError, ValueError):
        return {}


def _iterm_merken(sid: str, uid: str, tty: str) -> None:
    alles = _iterm_laden()
    alles[sid] = {"unique_id": uid, "tty": tty}
    pfad = _iterm_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(alles, indent=1))
    os.replace(tmp, pfad)


# --- Startsperre -------------------------------------------------------------

def _sperre(sid: str) -> Path:
    return pfade.fivec_home() / "sperren" / sid


def sperre_nehmen(sid: str) -> bool:
    """Atomar (O_EXCL): von zwei gleichzeitigen Aufrufen, auch aus App und Dienst, gewinnt genau einer.
    Eine Sperre älter als SPERRE_S gilt als abgelaufen und wird neu genommen."""
    pfad = _sperre(sid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            os.close(os.open(pfad, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                alter = time.time() - pfad.stat().st_mtime
            except OSError:
                continue  # gerade gelöscht: noch einmal versuchen
            if alter < SPERRE_S:
                return False
            pfad.unlink(missing_ok=True)
    return False


# --- In welcher App läuft ein Prozess? ---------------------------------------

def app_von_prozess(pid: int) -> str | None:
    """Erste `.app` in der Elternkette, z. B. `/Applications/iTerm.app`."""
    for _ in range(30):
        try:
            aus = subprocess.run(["ps", "-o", "ppid=", "-o", "comm=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        zeile = aus.stdout.strip()
        if aus.returncode != 0 or not zeile:
            return None
        ppid, _, befehl = zeile.partition(" ")
        if ".app/" in befehl:
            return befehl[: befehl.index(".app/") + 4]
        pid = int(ppid)
        if pid <= 1:
            return None
    return None


def claude_am_tty(tty: str, sid: str) -> bool:
    """Läuft am TTY schon `claude --resume <sid>`? Fängt den Start ab, der länger als die Sperre braucht."""
    if not tty:
        return False
    try:
        aus = subprocess.run(["ps", "-t", tty.removeprefix("/dev/"), "-o", "command="],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(f"--resume {sid}" in z and "claude" in z for z in aus.stdout.splitlines())


def app_aktivieren(app: str) -> None:
    subprocess.run(["open", "-a", app], capture_output=True, timeout=10)


# --- Befehl, Titel, Badge ----------------------------------------------------

def startbefehl(cwd: str, sid: str) -> str:
    return f"cd {shlex.quote(cwd)} && caffeinate -dims claude --resume {shlex.quote(sid)}"


def titel_und_badge(zeile: dict) -> tuple[str, str]:
    name = zeile.get("name") or f"{Path(zeile.get('cwd') or '?').name} {zeile['sid'][:8]}"
    beschreibung = (zeile.get("beschreibung") or "").split("\n")[0]
    badge = f"{name}\n{beschreibung}" if beschreibung else name
    return f"🔵 {name}", badge


# --- Ablauf ------------------------------------------------------------------

def oeffnen(sid: str, *, it=iterm, laufende=None, index=None, notizen=None,
            app_von=app_von_prozess, aktivieren=app_aktivieren, am_tty=claude_am_tty) -> dict:
    """Ergebnis: {"ergebnis": "vorn" | "anderswo" | "startet" | "gestartet", "text": …}."""
    if not meta.UUID.match(sid):
        raise OeffnenFehler("Keine gültige Session-ID")
    idx = index if index is not None else uebersicht.index_aktuell()
    if sid not in idx:
        raise OeffnenFehler("Diese Session kennt 5C nicht")
    eintrag = idx[sid]
    laeufe = laufende if laufende is not None else live.laufende(pfade.claude_home())
    gemerkt = _iterm_laden().get(sid, {})
    lauf = laeufe.get(sid)

    if lauf and lauf["zustand"] == "läuft":
        app = app_von(lauf["pid"])
        if app is None or app.endswith("/iTerm.app"):
            uid = it.fokussieren(gemerkt.get("unique_id"), lauf.get("tty"))
            if uid:
                return {"ergebnis": "vorn", "text": "In iTerm2 nach vorn geholt."}
        if app is not None:
            aktivieren(app)
            name = Path(app).stem
            return {"ergebnis": "anderswo",
                    "text": f"Läuft in {name} ({lauf.get('tty') or 'ohne TTY'}). {name} ist jetzt vorn, den Tab wählst Du dort."}
        raise OeffnenFehler("Die Session läuft, ihr Fenster ist aber nicht zu finden.")

    cwd = eintrag.get("cwd") or (lauf or {}).get("cwd")
    if not cwd or not Path(cwd).is_dir():
        raise OeffnenFehler("Ordner fehlt: Die Session lässt sich nicht fortsetzen.")

    if am_tty(gemerkt.get("tty", ""), sid) or not sperre_nehmen(sid):
        if gemerkt.get("unique_id"):
            it.fokussieren(gemerkt["unique_id"], None)
        return {"ergebnis": "startet", "text": "Die Session startet gerade."}

    zeile = {**eintrag, **(notizen if notizen is not None else meta.laden()).get(sid, {})}
    titel, badge = titel_und_badge(zeile)
    try:
        uid, tty = it.starten(startbefehl(cwd, sid), titel, badge)
    except Exception:
        _sperre(sid).unlink(missing_ok=True)  # ein gescheiterter Start darf den nächsten Versuch nicht sperren
        raise
    _iterm_merken(sid, uid, tty)
    return {"ergebnis": "gestartet", "text": "In iTerm2 fortgesetzt."}
