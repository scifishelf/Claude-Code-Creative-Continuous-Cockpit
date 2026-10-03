"""Mitteilung, sobald eine Session fertig ist oder eine Freigabe braucht (Plan, E7).

Auslöser ist der Wechsel von „arbeitet“ oder „hängt vielleicht“ nach „wartet auf Dich“,
erkannt im Takt des Tab-Abgleichs (fivec/tabsync.py, kein zweites `ps`). Keine Mitteilung
- beim ersten Blick auf eine Session (Dienststart), sonst meldet jeder Neustart alles;
- nach „startet“: wer gerade fortsetzt, sitzt davor;
- wenn der iTerm2-Tab der Session vorn ist;
- öfter als einmal je Session in SPERRE_S.

Weg: `open -g fivec://melden/<id>` an 5C.app, damit die Mitteilung von 5C kommt (nicht vom
Skripteditor) und der Fokus bleibt, wo er ist. Die App fragt `5c open-url` nach dem Text.
Ein Klick auf die Mitteilung startet die App, `5c klick` holt dann die zuletzt gemeldete
Session nach vorn, sonst die Übersicht.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

from . import iterm, pfade

SPERRE_S = 30
KLICK_GILT_S = 600
URL = re.compile(r"^fivec://melden/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$")
MARKE = "5C-MELDUNG"
AUS = ("arbeitet", "hängt vielleicht")
NACH = "wartet auf Dich"
# waitingFor -> Titel. Gemessen 03.10.2026: "permission prompt" bei einer Freigabe, "input needed"
# bei einer Rückfrage (AskUserQuestion); leer, wenn der Turn einfach fertig ist.
TITEL = {
    "": "Fertig, wartet auf Dich",
    "permission prompt": "Braucht Deine Freigabe",
    "input needed": "Braucht Deine Antwort",
}


def ausloeser(vorher: dict, zeilen: list[dict]) -> list[dict]:
    """Zeilen, die seit dem letzten Takt von AUS nach NACH gewechselt sind."""
    return [z for z in zeilen if z["zustand"] == NACH and vorher.get(z["sid"]) in AUS]


def _einzeilig(text: str, maximal: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= maximal else text[: maximal - 1].rstrip() + "…"


def texte(zeile: dict) -> tuple[str, str, str]:
    """(Titel, Untertitel, Text). Einzeilig, weil die App die Antwort zeilenweise liest."""
    titel = TITEL.get((zeile.get("lauf") or {}).get("waitingFor") or "", "Braucht Deine Antwort")
    prompts = zeile.get("erste_prompts") or [""]
    name = zeile.get("name") or _einzeilig(prompts[0], 60) or "Ohne Namen"
    return titel, _einzeilig(name, 60), _einzeilig(zeile.get("cwd_kurz") or "", 80)


def antwort(zeile: dict | None) -> str:
    """Was `5c open-url fivec://melden/<id>` an 5C.app liefert: leer, wenn nichts (mehr) zu melden ist."""
    if not zeile or zeile["zustand"] != NACH:
        return ""
    return "\n".join([MARKE, *texte(zeile)])


# --- zuletzt gemeldet (für den Klick auf die Mitteilung) ----------------------

def _zuletzt_pfad() -> Path:
    return pfade.fivec_home() / "zuletzt-gemeldet.json"


def zuletzt_merken(sid: str, jetzt: float | None = None) -> None:
    pfad = _zuletzt_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps({"sid": sid, "zeit": jetzt if jetzt is not None else time.time()}))
    os.replace(tmp, pfad)


def zuletzt_nehmen(jetzt: float | None = None) -> str | None:
    """Die zuletzt gemeldete Session, höchstens KLICK_GILT_S alt; einmal genommen, ist sie weg.
    So öffnet ein späterer Doppelklick auf 5C.app wieder die Übersicht."""
    pfad = _zuletzt_pfad()
    try:
        daten = json.loads(pfad.read_text())
        pfad.unlink()
    except (OSError, ValueError):
        return None
    jetzt = jetzt if jetzt is not None else time.time()
    if not isinstance(daten, dict) or jetzt - float(daten.get("zeit", 0)) > KLICK_GILT_S:
        return None
    return daten.get("sid")


# --- Takt -------------------------------------------------------------------

def senden(sid: str) -> None:
    aus = subprocess.run(["open", "-g", f"fivec://melden/{sid}"], capture_output=True, text=True, timeout=10)
    if aus.returncode != 0:
        raise RuntimeError(f"Mitteilung: {aus.stderr.strip() or 'open scheiterte'} (ist 5C.app eingerichtet?)")


class Melder:
    def __init__(self, sende=senden, vorne_tty=iterm.vorne_tty, merken=zuletzt_merken, uhr=time.monotonic):
        self.vorher: dict = {}
        self.gemeldet: dict = {}
        self.sende, self.vorne_tty, self.merken, self.uhr = sende, vorne_tty, merken, uhr

    def takt(self, zeilen: list[dict]) -> list[str]:
        """Meldet die Wechsel dieses Takts. -> gemeldete Session-IDs."""
        kandidaten = ausloeser(self.vorher, zeilen)
        self.vorher = {z["sid"]: z["zustand"] for z in zeilen}
        t = self.uhr()
        kandidaten = [z for z in kandidaten if t - self.gemeldet.get(z["sid"], -SPERRE_S - 1) > SPERRE_S]
        if not kandidaten:
            return []
        try:
            vorn = self.vorne_tty()
        except Exception:
            vorn = ""  # lieber einmal zu oft melden als eine Freigabe verschweigen
        gemeldet = []
        for z in kandidaten:
            if vorn and vorn == iterm.tty_voll((z.get("lauf") or {}).get("tty")):
                continue
            self.gemeldet[z["sid"]] = t
            self.merken(z["sid"])
            self.sende(z["sid"])
            gemeldet.append(z["sid"])
        return gemeldet
