"""Kommandozeile: `5c list`."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import gitstand, index, live, pfade


def _zeit(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _kurz_pfad(cwd: str | None) -> str:
    if not cwd:
        return "?"
    heim = str(Path.home())
    return "~" + cwd[len(heim):] if cwd.startswith(heim) else cwd


def zustand_text(lauf: dict | None) -> str:
    if lauf is None:
        return "ruht"
    if lauf["zustand"] != "läuft":
        return "verwaist"
    if lauf.get("waitingFor"):
        return "wartet auf Dich"
    return {"busy": "arbeitet", "idle": "wartet auf Dich"}.get(lauf.get("status"), "läuft")


def sessions(stunden: float | None) -> list[dict]:
    """Index und Laufzeitstand zusammengeführt, neueste zuerst."""
    home = pfade.claude_home()
    idx = index.aktualisieren(home, pfade.fivec_home() / "index.json")
    laeufe = live.laufende(home)
    grenze = None if stunden is None else datetime.now(timezone.utc) - timedelta(hours=stunden)
    git_cache: dict = {}
    zeilen = []
    for sid, e in idx.items():
        lauf = laeufe.get(sid)
        letzte = _zeit(e["letzter"])
        if grenze is not None and lauf is None and (letzte is None or letzte < grenze):
            continue
        cwd = e["cwd"] or (lauf or {}).get("cwd")
        if cwd not in git_cache:
            git_cache[cwd] = gitstand.stand(cwd)
        zeilen.append({**e, "cwd": cwd, "lauf": lauf, "zustand": zustand_text(lauf), "git": git_cache[cwd]})
    zeilen.sort(key=lambda z: z["letzter"] or "", reverse=True)
    return zeilen


def _git_text(git: dict) -> str:
    if git["art"] == "ordner_fehlt":
        return "Ordner fehlt"
    if git["art"] == "kein_repo":
        return "-"
    return "sauber" if git["uncommittet"] == 0 else f"{git['uncommittet']} offen"


def _tabelle(zeilen: list[dict]) -> str:
    kopf = ["Zustand", "Projekt", "Letzte Aktivität", "Nachr.", "Git", "Session-ID"]
    daten = []
    for z in zeilen:
        t = _zeit(z["letzter"])
        git = z["git"]
        daten.append([
            z["zustand"],
            _kurz_pfad(z["cwd"]),
            t.astimezone().strftime("%d.%m. %H:%M") if t else "?",
            str(z["nachrichten"]),
            _git_text(git),
            z["sid"],
        ])
    breiten = [max(len(r[i]) for r in [kopf, *daten]) for i in range(len(kopf))]
    fmt = "  ".join(f"{{:<{b}}}" for b in breiten)
    return "\n".join(fmt.format(*r) for r in [kopf, ["-" * b for b in breiten], *daten])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="5c", description="Claude Code Creative Continue Cockpit")
    sub = parser.add_subparsers(dest="befehl", required=True)
    ls = sub.add_parser("list", help="Sessions auflisten")
    ls.add_argument("--stunden", type=float, default=48, help="nur Sessions mit Aktivität in diesem Zeitraum (Standard 48)")
    ls.add_argument("--alle", action="store_true", help="ohne Zeitfilter")
    ls.add_argument("--json", action="store_true", help="als JSON ausgeben")
    args = parser.parse_args(argv)

    zeilen = sessions(None if args.alle else args.stunden)
    if args.json:
        json.dump(zeilen, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(_tabelle(zeilen))
    return 0
