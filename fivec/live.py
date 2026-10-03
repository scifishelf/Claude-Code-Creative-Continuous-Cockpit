"""Welche Sessions laufen gerade? Quelle: ~/.claude/sessions/<pid>.json.

Gemessen am 03.10.2026 (docs/plans/2026-10-03-messungen-ist.md):
- `kill -9` lässt die Statusdatei liegen, also reicht "Datei da" nicht.
- Claude prüft selbst pid *und* Startzeit gegen `procStart`, um wiederverwendete
  PIDs zu erkennen. `procStart` steht in UTC, `ps -o lstart` liefert Ortszeit.
- Die `.key`-Dateien daneben liest 5C nie.
"""

import calendar
import json
import os
import subprocess
import time
from pathlib import Path

PS_FORMAT = "%a %b %d %H:%M:%S %Y"


def gleiche_startzeit(proc_start_utc: str, lstart_lokal: str) -> bool:
    """`procStart` (UTC) und `ps -o lstart` (Ortszeit) meinen dieselbe Sekunde?"""
    try:
        utc = calendar.timegm(time.strptime(proc_start_utc.strip(), PS_FORMAT))
        lokal = time.mktime(time.strptime(lstart_lokal.strip(), PS_FORMAT))
    except ValueError:
        return False
    return abs(utc - lokal) <= 1


def _lebt(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def prozess_info(pid: int) -> tuple[str, str] | None:
    """(tty, lstart) eines Prozesses, oder None, wenn es ihn nicht gibt."""
    try:
        aus = subprocess.run(
            ["ps", "-o", "tty=", "-o", "lstart=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5, env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    zeile = aus.stdout.strip()
    if aus.returncode != 0 or not zeile:
        return None
    tty, _, lstart = zeile.partition(" ")
    return tty, lstart.strip()


def laufende(claude_home: Path, prozess=prozess_info) -> dict:
    """Session-ID -> Laufzeitstand. `zustand` ist "läuft" oder "verwaist"."""
    ergebnis = {}
    for datei in (claude_home / "sessions").glob("*.json"):
        try:
            daten = json.loads(datei.read_text())
            pid = int(daten["pid"])
            sid = daten["sessionId"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        info = prozess(pid) if _lebt(pid) else None
        echt = info is not None and gleiche_startzeit(daten.get("procStart", ""), info[1])
        stand = {
            "pid": pid,
            "zustand": "läuft" if echt else "verwaist",
            "status": daten.get("status"),
            "waitingFor": daten.get("waitingFor"),
            "updatedAt": daten.get("updatedAt"),
            "statusUpdatedAt": daten.get("statusUpdatedAt"),
            "tty": info[0] if echt else None,
            "cwd": daten.get("cwd"),
            "statusdatei": str(datei),
        }
        # Hält dieselbe Session mehr als eine Datei, gewinnt die lebende.
        if sid not in ergebnis or (stand["zustand"] == "läuft" and ergebnis[sid]["zustand"] != "läuft"):
            ergebnis[sid] = stand
    return ergebnis
