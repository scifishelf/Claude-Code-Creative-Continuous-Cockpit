"""Index, Laufzeitstand, Git-Stand und 5C-Metadaten zu einer Liste zusammenführen.

Wird von `5c list` und vom Dienst geteilt. Ein Lock hält parallele Anfragen des
Dienstes davon ab, den Index-Cache gleichzeitig zu schreiben.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from . import gitstand, index, live, meta, pfade

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


def zustand_text(lauf: dict | None) -> str:
    if lauf is None:
        return "ruht"
    if lauf["zustand"] != "läuft":
        return "verwaist"
    if lauf.get("waitingFor"):
        return "wartet auf Dich"
    return {"busy": "arbeitet", "idle": "wartet auf Dich"}.get(lauf.get("status"), "läuft")


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


def sessions(stunden: float | None) -> list[dict]:
    """Neueste zuerst. Laufende Sessions stehen immer drin, auch außerhalb des Zeitraums."""
    with _lock:
        idx = index.aktualisieren(pfade.claude_home(), pfade.fivec_home() / "index.json")
        laeufe = live.laufende(pfade.claude_home())
        notizen = meta.laden()
        grenze = None if stunden is None else datetime.now(timezone.utc) - timedelta(hours=stunden)
        zeilen = []
        for sid, e in idx.items():
            lauf = laeufe.get(sid)
            letzte = zeit(e["letzter"])
            if grenze is not None and lauf is None and (letzte is None or letzte < grenze):
                continue
            cwd = e["cwd"] or (lauf or {}).get("cwd")
            notiz = notizen.get(sid, {})
            zeilen.append({
                **e,
                "cwd": cwd,
                "name": notiz.get("name", ""),
                "beschreibung": notiz.get("beschreibung", ""),
                "lauf": lauf,
                "zustand": zustand_text(lauf),
                "git": _git(cwd),
            })
    zeilen.sort(key=lambda z: z["letzter"] or "", reverse=True)
    return zeilen
