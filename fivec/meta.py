"""Name, Beschreibung und „ausgeblendet“ je Session, ausgeblendete Projekte; nur in 5C gespeichert (E4, E8).

Dateien: <FIVEC_HOME>/meta.json, {session_id: {"name": …, "beschreibung": …, "ausgeblendet": true}},
und <FIVEC_HOME>/projekte.json, {cwd: {"ausgeblendet": true}}.
Beide Texte landen später im iTerm2-Titel und -Badge. Deshalb gelten dieselben
Regeln wie bei Claudes eigener Deep-Link-Prüfung: keine Steuerzeichen, keine
unsichtbaren oder bidirektionalen Zeichen, begrenzte Länge.
"""

import json
import os
import re
import threading
import unicodedata

from . import pfade

NAME_MAX = 60
BESCHREIBUNG_MAX = 2000
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Unsichtbar oder richtungsumkehrend: Zero-Width, Bidi-Steuerung, BOM.
_VERBOTEN = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")

_lock = threading.Lock()


class Ungueltig(ValueError):
    pass


def pruefen(text, feld: str, maximal: int, zeilen_erlaubt: bool) -> str:
    if not isinstance(text, str):
        raise Ungueltig(f"{feld} muss Text sein")
    text = text.strip()
    if len(text) > maximal:
        raise Ungueltig(f"{feld} ist länger als {maximal} Zeichen")
    if _VERBOTEN.search(text):
        raise Ungueltig(f"{feld} enthält unsichtbare oder richtungsumkehrende Zeichen")
    for z in text:
        if unicodedata.category(z) == "Cc" and not (zeilen_erlaubt and z == "\n"):
            raise Ungueltig(f"{feld} enthält Steuerzeichen")
    return text


def _pfad():
    return pfade.fivec_home() / "meta.json"


def laden() -> dict:
    try:
        daten = json.loads(_pfad().read_text())
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def setzen(sid: str, aenderung: dict) -> dict:
    """Nur `name`, `beschreibung` und `ausgeblendet`, alle optional. Gibt den neuen Stand zurück."""
    if not UUID.match(sid):
        raise Ungueltig("keine gültige Session-ID")
    unbekannt = set(aenderung) - {"name", "beschreibung", "ausgeblendet"}
    if unbekannt:
        raise Ungueltig(f"unbekannte Felder: {', '.join(sorted(unbekannt))}")
    neu = {}
    if "name" in aenderung:
        neu["name"] = pruefen(aenderung["name"], "Name", NAME_MAX, zeilen_erlaubt=False)
    if "beschreibung" in aenderung:
        neu["beschreibung"] = pruefen(aenderung["beschreibung"], "Beschreibung", BESCHREIBUNG_MAX, zeilen_erlaubt=True)
    if "ausgeblendet" in aenderung:
        neu["ausgeblendet"] = _wahrheit(aenderung["ausgeblendet"])
    with _lock:
        alles = laden()
        eintrag = {**alles.get(sid, {}), **neu}
        eintrag = {k: v for k, v in eintrag.items() if v}
        if eintrag:
            alles[sid] = eintrag
        else:
            alles.pop(sid, None)
        _schreiben(_pfad(), alles)
    return eintrag


def _wahrheit(wert) -> bool:
    if not isinstance(wert, bool):
        raise Ungueltig("ausgeblendet muss true oder false sein")
    return wert


def _schreiben(pfad, daten: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1))
    os.replace(tmp, pfad)


# --- Projekte -----------------------------------------------------------------

def _projekte_pfad():
    return pfade.fivec_home() / "projekte.json"


def projekte_laden() -> dict:
    try:
        daten = json.loads(_projekte_pfad().read_text())
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def ausgeblendete_projekte() -> set:
    return {cwd for cwd, e in projekte_laden().items() if isinstance(e, dict) and e.get("ausgeblendet")}


def projekt_setzen(cwd: str, aenderung: dict) -> dict:
    """Nur `ausgeblendet`. Ob es den cwd gibt, prüft der Aufrufer gegen den Index."""
    if not isinstance(cwd, str) or not cwd:
        raise Ungueltig("cwd fehlt")
    unbekannt = set(aenderung) - {"ausgeblendet"}
    if unbekannt:
        raise Ungueltig(f"unbekannte Felder: {', '.join(sorted(unbekannt))}")
    if "ausgeblendet" not in aenderung:
        raise Ungueltig("ausgeblendet fehlt")
    aus = _wahrheit(aenderung["ausgeblendet"])
    with _lock:
        alles = projekte_laden()
        if aus:
            alles[cwd] = {"ausgeblendet": True}
        else:
            alles.pop(cwd, None)
        _schreiben(_projekte_pfad(), alles)
    return {"cwd": cwd, "ausgeblendet": aus}
