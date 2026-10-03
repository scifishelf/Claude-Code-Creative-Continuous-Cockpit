"""Index, Laufzeitstand, Gesundheit, Git-Stand und 5C-Metadaten zu einer Liste zusammenführen.

Wird von `5c list` und vom Dienst geteilt. Ein Lock hält parallele Anfragen des
Dienstes davon ab, den Index-Cache gleichzeitig zu schreiben. Je Aufruf gibt es
genau einen `ps`-Aufruf (fivec/prozesse.py).
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import gesundheit, gitstand, index, live, meta, pfade, prozesse

GIT_TTL = 10.0

_lock = threading.Lock()
_git_cache: dict = {}


def zeit(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def kurz_pfad(cwd: str | None) -> str:
    if not cwd:
        return "?"
    heim = str(Path.home())
    return "~" + cwd[len(heim):] if cwd == heim or cwd.startswith(heim + "/") else cwd


def _git(cwd: str | None) -> dict:
    jetzt = time.monotonic()
    treffer = _git_cache.get(cwd)
    if treffer and jetzt - treffer[0] < GIT_TTL:
        return treffer[1]
    stand = gitstand.stand(cwd)
    _git_cache[cwd] = (jetzt, stand)
    return stand


def index_aktuell() -> dict:
    with _lock:
        return index.aktualisieren(pfade.claude_home(), pfade.fivec_home() / "index.json")


def sessions(stunden: float | None, tab: dict | None = None) -> list[dict]:
    """Neueste zuerst. Laufende und startende Sessions stehen immer drin, auch außerhalb des Zeitraums."""
    with _lock:
        tab = prozesse.tabelle() if tab is None else tab
        idx = index.aktualisieren(pfade.claude_home(), pfade.fivec_home() / "index.json")
        laeufe = live.laufende(pfade.claude_home(), prozess=prozesse.info_von(tab))
        startend = prozesse.startende(tab)
        notizen = meta.laden()
        jetzt = datetime.now(timezone.utc)
        grenze = None if stunden is None else jetzt - timedelta(hours=stunden)
        zeilen = []
        for sid, e in idx.items():
            lauf = laeufe.get(sid)
            g = gesundheit.bewerten(lauf, sid in startend, e["letzter"], jetzt)
            aktiv = g["zustand"] not in ("ruht", "verwaist")
            letzte = zeit(e["letzter"])
            if grenze is not None and not aktiv and lauf is None and (letzte is None or letzte < grenze):
                continue
            pid = lauf["pid"] if lauf and lauf["zustand"] == "läuft" else startend.get(sid)
            cwd = e["cwd"] or (lauf or {}).get("cwd")
            notiz = notizen.get(sid, {})
            zeilen.append({
                **e,
                "cwd": cwd,
                "cwd_kurz": kurz_pfad(cwd),
                "name": notiz.get("name", ""),
                "beschreibung": notiz.get("beschreibung", ""),
                "lauf": lauf,
                "aktiv": aktiv,
                "zustand": g["zustand"],
                "still_s": g["still_s"],
                "prozess": prozesse.kennzahlen(pid, tab) if aktiv and pid else None,
                "git": _git(cwd),
            })
    zeilen.sort(key=lambda z: z["letzter"] or "", reverse=True)
    return zeilen
