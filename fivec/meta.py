"""Name und Beschreibung je Session, nur in 5C gespeichert (E4).

Datei: <FIVEC_HOME>/meta.json, {session_id: {"name": …, "beschreibung": …}}.
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
    """Nur `name` und `beschreibung`, beide optional. Gibt den neuen Stand zurück."""
    if not UUID.match(sid):
        raise Ungueltig("keine gültige Session-ID")
    unbekannt = set(aenderung) - {"name", "beschreibung"}
    if unbekannt:
        raise Ungueltig(f"unbekannte Felder: {', '.join(sorted(unbekannt))}")
    neu = {}
    if "name" in aenderung:
        neu["name"] = pruefen(aenderung["name"], "Name", NAME_MAX, zeilen_erlaubt=False)
    if "beschreibung" in aenderung:
        neu["beschreibung"] = pruefen(aenderung["beschreibung"], "Beschreibung", BESCHREIBUNG_MAX, zeilen_erlaubt=True)
    with _lock:
        alles = laden()
        eintrag = {**alles.get(sid, {}), **neu}
        eintrag = {k: v for k, v in eintrag.items() if v}
        if eintrag:
            alles[sid] = eintrag
        else:
            alles.pop(sid, None)
        pfad = _pfad()
        pfad.parent.mkdir(parents=True, exist_ok=True)
        tmp = pfad.with_suffix(".tmp")
        tmp.write_text(json.dumps(alles, ensure_ascii=False, indent=1))
        os.replace(tmp, pfad)
    return eintrag
