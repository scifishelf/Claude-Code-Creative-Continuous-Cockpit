"""Index aller Sessions aus ~/.claude/projects/*/*.jsonl.

Die Dateien sind zusammen gut 1 GB groß. Der Index merkt sich deshalb je Datei
den Byte-Offset und liest beim nächsten Lauf nur das Angehängte. Maßgeblich für
"letzte Aktivität" ist der letzte `timestamp` in der Datei, nicht die mtime
(Messung, bis 8b14656 in docs/plans/2026-10-03-messungen-ist.md: alle mtimes können gleich sein).
"""

import json
import os
from pathlib import Path

CACHE_SCHEMA = 1
KURZ = 400


def kuerzen(text: str, n: int = KURZ) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + "…"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


def _ist_tool_result(content) -> bool:
    return isinstance(content, list) and any(
        isinstance(c, dict) and c.get("type") == "tool_result" for c in content
    )


def neuer_eintrag(sid: str, datei: Path) -> dict:
    return {
        "sid": sid,
        "datei": str(datei),
        "cwd": None,
        "erster": None,
        "letzter": None,
        "nachrichten": 0,
        "erste_prompts": [],
        "letzte_prompts": [],
        "letzte_antworten": [],
        "offset": 0,
        "inode": None,
    }


def aufnehmen(eintrag: dict, zeile: dict) -> None:
    """Eine JSONL-Zeile in den Eintrag einrechnen."""
    if zeile.get("cwd"):
        eintrag["cwd"] = zeile["cwd"]
    ts = zeile.get("timestamp")
    if isinstance(ts, str):
        if eintrag["erster"] is None or ts < eintrag["erster"]:
            eintrag["erster"] = ts
        if eintrag["letzter"] is None or ts > eintrag["letzter"]:
            eintrag["letzter"] = ts

    typ = zeile.get("type")
    if typ not in ("user", "assistant"):
        return
    eintrag["nachrichten"] += 1
    if zeile.get("isSidechain"):
        return
    content = (zeile.get("message") or {}).get("content")

    if typ == "user":
        if zeile.get("isMeta") or zeile.get("isCompactSummary") or _ist_tool_result(content):
            return
        text = _text(content).strip()
        if not text or text.startswith("<"):
            return
        text = kuerzen(text)
        if len(eintrag["erste_prompts"]) < 2:
            eintrag["erste_prompts"].append(text)
        eintrag["letzte_prompts"] = (eintrag["letzte_prompts"] + [text])[-3:]
    else:
        text = _text(content).strip()
        if text:
            eintrag["letzte_antworten"] = (eintrag["letzte_antworten"] + [kuerzen(text)])[-3:]


def _einlesen(eintrag: dict, datei: Path) -> None:
    """Ab `offset` lesen, nur vollständige Zeilen verarbeiten."""
    with open(datei, "rb") as f:
        f.seek(eintrag["offset"])
        daten = f.read()
    ende = daten.rfind(b"\n")
    if ende < 0:
        return
    for roh in daten[: ende + 1].splitlines():
        if not roh.strip():
            continue
        try:
            zeile = json.loads(roh)
        except ValueError:
            continue
        if isinstance(zeile, dict):
            aufnehmen(eintrag, zeile)
    eintrag["offset"] += ende + 1


def _cache_laden(pfad: Path) -> dict:
    try:
        daten = json.loads(pfad.read_text())
    except (OSError, ValueError):
        return {}
    if daten.get("schema") != CACHE_SCHEMA:
        return {}
    return daten.get("sessions", {})


def _cache_speichern(pfad: Path, sessions: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema": CACHE_SCHEMA, "sessions": sessions}, ensure_ascii=False))
    os.replace(tmp, pfad)


def aktualisieren(claude_home: Path, cache_pfad: Path) -> dict:
    """Index auf den Stand der Platte bringen und zurückgeben (Session-ID -> Eintrag)."""
    alt = _cache_laden(cache_pfad)
    neu = {}
    for datei in sorted((claude_home / "projects").glob("*/*.jsonl")):
        sid = datei.stem
        try:
            st = datei.stat()
        except OSError:
            continue
        eintrag = alt.get(sid)
        if (
            eintrag is None
            or eintrag.get("datei") != str(datei)
            or eintrag.get("inode") != st.st_ino
            or st.st_size < eintrag.get("offset", 0)
        ):
            eintrag = neuer_eintrag(sid, datei)
        eintrag["inode"] = st.st_ino
        if st.st_size > eintrag["offset"]:
            _einlesen(eintrag, datei)
        neu[sid] = eintrag
    _cache_speichern(cache_pfad, neu)
    return neu
