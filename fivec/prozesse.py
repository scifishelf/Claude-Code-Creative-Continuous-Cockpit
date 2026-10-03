"""Eine Prozessliste je Takt: ein `ps`-Aufruf statt einem je Session.

Daraus: Lebendprüfung (tty, lstart), CPU, Speicher, Laufzeit, die App einer Session
(erste `.app` in der Elternkette), ob `caffeinate` mitläuft, und Sessions, die
gerade starten (`claude --resume <id>` läuft, aber noch ohne Statusdatei).
"""

import os
import re
import subprocess

SPALTEN = ["pid=", "ppid=", "pcpu=", "rss=", "etime=", "tty=", "lstart=", "command="]
RESUME = re.compile(r"--resume[ =]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def parsen(text: str) -> dict:
    """`ps`-Ausgabe -> {pid: {...}}. lstart sind immer 5 Wörter (`Sat Oct  3 09:55:37 2026`)."""
    tabelle = {}
    for zeile in text.splitlines():
        teile = zeile.split()
        if len(teile) < 12:
            continue
        try:
            pid, ppid = int(teile[0]), int(teile[1])
            cpu, rss = float(teile[2].replace(",", ".")), int(teile[3])
        except ValueError:
            continue
        tabelle[pid] = {
            "pid": pid, "ppid": ppid, "cpu": cpu, "rss_kb": rss,
            "etime": teile[4], "tty": teile[5],
            "lstart": " ".join(teile[6:11]),
            "command": " ".join(teile[11:]),
        }
    return tabelle


def tabelle() -> dict:
    try:
        aus = subprocess.run(["ps", "-axww", "-o", ",".join(SPALTEN)], capture_output=True, text=True,
                             timeout=10, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return parsen(aus.stdout) if aus.returncode == 0 else {}


def info_von(tab: dict):
    """Ersatz für live.prozess_info aus der Tabelle: pid -> (tty, lstart) oder None."""
    def info(pid: int):
        p = tab.get(pid)
        return None if p is None else (p["tty"], p["lstart"])
    return info


def _app_pfad(befehl: str) -> str | None:
    """Nur wenn das Programm selbst in einer `.app` liegt. `/usr/bin/login -fpl … /Applications/iTerm.app/…`
    nennt die App bloß als Argument und zählt nicht."""
    if not befehl.startswith("/") or ".app/" not in befehl:
        return None
    vorn = befehl[: befehl.index(".app/")]
    return None if " -" in vorn else vorn + ".app"


def app_fuer(pid: int, tab: dict) -> str | None:
    """Erste `.app` in der Elternkette, z. B. `/Applications/iTerm.app`."""
    gesehen = set()
    while pid in tab and pid not in gesehen and pid > 1:
        gesehen.add(pid)
        app = _app_pfad(tab[pid]["command"])
        if app:
            return app
        pid = tab[pid]["ppid"]
    return None


def _ist_claude(befehl: str) -> bool:
    erstes = befehl.split(" ", 1)[0]
    return erstes == "claude" or erstes.endswith("/claude")


def startende(tab: dict) -> dict:
    """Session-ID -> pid aller `claude --resume <id>`-Prozesse (ohne den caffeinate-Elternteil)."""
    gefunden = {}
    for p in tab.values():
        if not _ist_claude(p["command"]):
            continue
        treffer = RESUME.search(p["command"])
        if treffer:
            gefunden[treffer.group(1)] = p["pid"]
    return gefunden


def caffeinate_am_tty(tty: str, tab: dict) -> bool:
    return any(p["tty"] == tty and p["command"].startswith("caffeinate") for p in tab.values())


def kennzahlen(pid: int, tab: dict) -> dict | None:
    p = tab.get(pid)
    if p is None:
        return None
    app = app_fuer(pid, tab)
    return {
        "app": app.rsplit("/", 1)[-1].removesuffix(".app") if app else None,
        "app_pfad": app,
        "cpu": p["cpu"],
        "speicher_mb": round(p["rss_kb"] / 1024),
        "laufzeit": p["etime"],
        "caffeinate": caffeinate_am_tty(p["tty"], tab) if p["tty"] not in ("??", "") else False,
    }
