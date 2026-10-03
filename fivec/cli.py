"""Kommandozeile: `5c list`, `5c dienst`."""

import argparse
import json
import sys

from . import dienst, uebersicht


def _git_text(git: dict) -> str:
    if git["art"] == "ordner_fehlt":
        return "Ordner fehlt"
    if git["art"] == "kein_repo":
        return "-"
    return "sauber" if git["uncommittet"] == 0 else f"{git['uncommittet']} offen"


def _tabelle(zeilen: list[dict]) -> str:
    kopf = ["Zustand", "Name", "Projekt", "Letzte Aktivität", "Nachr.", "Git", "Session-ID"]
    daten = []
    for z in zeilen:
        t = uebersicht.zeit(z["letzter"])
        daten.append([
            z["zustand"],
            z["name"] or "-",
            z["cwd_kurz"],
            t.astimezone().strftime("%d.%m. %H:%M") if t else "?",
            str(z["nachrichten"]),
            _git_text(z["git"]),
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
    ds = sub.add_parser("dienst", help="lokalen Webserver starten")
    ds.add_argument("--port", type=int, default=dienst.PORT)
    args = parser.parse_args(argv)

    if args.befehl == "dienst":
        dienst.starten(args.port)
        return 0
    zeilen = uebersicht.sessions(None if args.alle else args.stunden)
    if args.json:
        json.dump(zeilen, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(_tabelle(zeilen))
    return 0
