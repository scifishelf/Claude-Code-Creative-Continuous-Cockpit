"""Zustand einer Session (Plan, Abschnitt "Gesundheit: die Zustände").

arbeitet         läuft, status busy
wartet auf Dich  läuft, status idle oder waitingFor gesetzt
hängt vielleicht läuft, busy seit über 10 Min. UND seit über 10 Min. keine neue Zeile im Verlauf
startet          `claude --resume <id>` läuft, aber noch ohne Statusdatei (z. B. offene Vertrauensfrage)
verwaist         Statusdatei da, Prozess tot oder Startzeit passt nicht
ruht             nichts davon

Die letzte Zeile im Verlauf zählt über ihren timestamp, nicht über die mtime der Datei
(gemessen am 03.10.2026: alle mtimes können gleichzeitig springen).
"""

from datetime import datetime, timezone

HAENGT_NACH_S = 600

EMOJI = {
    "arbeitet": "🟢",
    "wartet auf Dich": "🟡",
    "hängt vielleicht": "🟠",
    "startet": "🔵",
}


def _sekunden_seit_ms(ms, jetzt: datetime) -> float | None:
    if not isinstance(ms, (int, float)):
        return None
    return jetzt.timestamp() - ms / 1000


def _sekunden_seit_iso(iso: str | None, jetzt: datetime) -> float | None:
    if not iso:
        return None
    try:
        return (jetzt - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return None


def bewerten(lauf: dict | None, startend: bool, letzter: str | None, jetzt: datetime | None = None) -> dict:
    """-> {"zustand": …, "still_s": Sekunden ohne Ausgabe oder None}."""
    jetzt = jetzt or datetime.now(timezone.utc)
    if lauf is None:
        return {"zustand": "startet" if startend else "ruht", "still_s": None}
    if lauf["zustand"] != "läuft":
        return {"zustand": "startet" if startend else "verwaist", "still_s": None}
    if lauf.get("waitingFor"):
        return {"zustand": "wartet auf Dich", "still_s": None}
    status = lauf.get("status")
    if status == "idle":
        return {"zustand": "wartet auf Dich", "still_s": None}
    if status == "busy":
        busy_seit = _sekunden_seit_ms(lauf.get("statusUpdatedAt"), jetzt)
        still = _sekunden_seit_iso(letzter, jetzt)
        if busy_seit is not None and still is not None and busy_seit > HAENGT_NACH_S and still > HAENGT_NACH_S:
            return {"zustand": "hängt vielleicht", "still_s": round(still)}
        return {"zustand": "arbeitet", "still_s": None}
    return {"zustand": "läuft", "still_s": None}
