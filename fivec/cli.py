"""Kommandozeile: `5c list`, `5c dienst`, `5c open`, dazu `open-url` und `klick` für 5C.app."""

import argparse
import json
import sys
from datetime import datetime

from . import dienst, iterm, mitteilung, oeffnen, pfade, uebersicht


def _protokoll(zeile: str) -> None:
    """Aufrufe aus 5C.app und launchd haben kein Terminal; ihre Spur steht hier."""
    pfad = pfade.fivec_home() / "5c.log"
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with open(pfad, "a") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {zeile}\n")
    except OSError:
        pass


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
    parser = argparse.ArgumentParser(prog="5c", description="Claude Code Creative Continuous Cockpit")
    sub = parser.add_subparsers(dest="befehl", required=True)
    ls = sub.add_parser("list", help="Sessions auflisten")
    ls.add_argument("--stunden", type=float, default=48, help="nur Sessions mit Aktivität in diesem Zeitraum (Standard 48)")
    ls.add_argument("--alle", action="store_true", help="ohne Zeitfilter")
    ls.add_argument("--json", action="store_true", help="als JSON ausgeben")
    ds = sub.add_parser("dienst", help="lokalen Webserver starten")
    ds.add_argument("--port", type=int, default=dienst.PORT)
    op = sub.add_parser("open", help="Session nach vorn holen oder in iTerm2 fortsetzen")
    op.add_argument("sid")
    ou = sub.add_parser("open-url", help="für 5C.app: fivec://open/<id> wie open, fivec://melden/<id> liefert den Text einer Mitteilung")
    ou.add_argument("url")
    sub.add_parser("klick", help="für 5C.app: zuletzt gemeldete Session nach vorn, sonst 'seite'")
    args = parser.parse_args(argv)

    if args.befehl == "dienst":
        dienst.starten(args.port)
        return 0
    if args.befehl == "open-url" and mitteilung.URL.match(args.url.strip()):
        sid = mitteilung.URL.match(args.url.strip()).group(1)
        zeile = next((z for z in uebersicht.sessions(0) if z["sid"] == sid), None)
        text = mitteilung.antwort(zeile)
        _protokoll(f"melden {sid}: {text.splitlines()[1] if text else 'nichts mehr zu melden'}")
        print(text)
        return 0
    if args.befehl == "klick":
        sid = mitteilung.zuletzt_nehmen()
        if sid is None:
            _protokoll("klick: keine frische Mitteilung, Übersicht")
            print("seite")
            return 0
        try:
            text, code = oeffnen.oeffnen(sid)["text"], 0
        except (oeffnen.OeffnenFehler, iterm.ItermFehler) as e:
            text, code = str(e), 1
        _protokoll(f"klick {sid}: {text}")
        if code:
            print(text)
        return code
    if args.befehl in ("open", "open-url"):
        ziel = args.sid if args.befehl == "open" else args.url
        try:
            sid = ziel if args.befehl == "open" else oeffnen.sid_aus_url(ziel)
            text, code = oeffnen.oeffnen(sid)["text"], 0
        except (oeffnen.OeffnenFehler, iterm.ItermFehler) as e:
            text, code = str(e), 1
        _protokoll(f"{args.befehl} {ziel!r}: {text}")
        print(text)
        return code
    zeilen = uebersicht.sessions(None if args.alle else args.stunden)
    if args.json:
        json.dump(zeilen, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(_tabelle(zeilen))
    return 0
