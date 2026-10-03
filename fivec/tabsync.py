"""Hält die iTerm2-Tabs der von 5C gestarteten Sessions auf Stand (E5).

Titel: Status-Emoji und Name (🟢 arbeitet, 🟡 wartet auf Dich, 🟠 hängt vielleicht, 🔵 startet).
Badge: Name und erste Zeile der Beschreibung. Der Abgleich setzt auch das „Chat“ zurück,
das iTerm2 beim Start von `claude` einmal vergibt (Messung, bis 8b14656 in docs/plans/2026-10-03-messungen-ist.md, Nachtrag P4).
Nur Sessions mit gemerkter iTerm2-ID (also von 5C gestartet, mit Profil 5C) werden angefasst.
"""

import threading
import time

from . import gesundheit, iterm, mitteilung, oeffnen, uebersicht

TAKT_S = 2.0


def soll_werte(zeilen: list[dict], gemerkt: dict) -> list[tuple[str, str, str]]:
    soll = []
    for z in zeilen:
        uid = gemerkt.get(z["sid"], {}).get("unique_id")
        emoji = gesundheit.EMOJI.get(z["zustand"])
        if not uid or not emoji:
            continue
        name, badge = oeffnen.name_und_badge(z)
        soll.append((uid, f"{emoji} {name}", badge))
    return soll


NACHKONTROLLE_S = 10.0  # gemessen: ein osascript-Abgleich kostet rund 280 ms

_zuletzt = {"soll": None, "zeit": 0.0}


def einmal(it=iterm, jetzt=time.monotonic, zeilen=None) -> int:
    """osascript nur bei geändertem Soll, sonst höchstens alle NACHKONTROLLE_S Sekunden
    (fängt Umbenennungen von außen, z. B. das „Chat“ beim Start)."""
    zeilen = uebersicht.sessions(0) if zeilen is None else zeilen
    soll = soll_werte(zeilen, oeffnen.iterm_gemerkt())
    t = jetzt()
    if soll == _zuletzt["soll"] and t - _zuletzt["zeit"] < NACHKONTROLLE_S:
        return 0
    _zuletzt.update(soll=soll, zeit=t)
    return it.abgleichen(soll)


def starten(stopp: threading.Event, protokoll=print) -> threading.Thread:
    """Ein Takt: eine Übersicht, daraus Tab-Abgleich und Mitteilungen (fivec/mitteilung.py)."""
    melder = mitteilung.Melder()

    def schleife():
        letzter_fehler = {}

        def fehler(name, e):
            if str(e) != letzter_fehler.get(name):
                protokoll(f"{name}: {e}")
                letzter_fehler[name] = str(e)

        while not stopp.wait(TAKT_S):
            try:  # der Dienst soll an keinem Schritt sterben
                zeilen = uebersicht.sessions(0)
            except Exception as e:
                fehler("Übersicht", e)
                continue
            for name, schritt in (("Tab-Abgleich", lambda: einmal(zeilen=zeilen)),
                                  ("Mitteilung", lambda: melder.takt(zeilen))):
                try:
                    schritt()
                    letzter_fehler.pop(name, None)
                except Exception as e:
                    fehler(name, e)

    faden = threading.Thread(target=schleife, name="5c-tabsync", daemon=True)
    faden.start()
    return faden
