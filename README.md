# 5C - Claude Code Creative Continue Cockpit

Übersicht aller Claude-Code-Sessions auf diesem Mac: Fortsetzen per Klick in iTerm2, Status live, eigene Namen und Beschreibungen. Plan und Stand: [docs/plans/2026-10-03-5c-v1-plan.md](docs/plans/2026-10-03-5c-v1-plan.md), Messungen: [docs/plans/2026-10-03-messungen-ist.md](docs/plans/2026-10-03-messungen-ist.md).

## Stand: P3

```sh
bin/5c dienst               # Übersicht auf http://127.0.0.1:4555/
bin/5c list                 # Sessions mit Aktivität in den letzten 48 h, neueste zuerst
bin/5c list --stunden 240   # anderer Zeitraum
bin/5c list --alle --json   # alles, maschinenlesbar
./pruefen.sh                # Syntax und Tests, vor jedem Commit
python3 werkzeug/mutationen.py   # Gegenprobe: eingebaute Fehler müssen die Tests fangen
```

- Python 3 ohne Abhängigkeiten.
- Liest `~/.claude/projects/*/*.jsonl` (inkrementell, Cache in `~/Library/Application Support/5C/index.json`) und `~/.claude/sessions/*.json`. Die `.key`-Dateien daneben liest 5C nie.
- Schreibt nur in den eigenen Ordner `~/Library/Application Support/5C/`, nie in `~/.claude`.
- Für Tests lassen sich beide Orte per `CLAUDE_HOME` und `FIVEC_HOME` umlenken.

## Oberfläche

`fivec/web/`: `index.html`, `app.css`, `app.js` (DOM und API), `logik.js` (reine Funktionen, mit `node --test` getestet), `logo.svg`, `schriften/` (Geist und Geist Mono, SIL OFL, lokal ausgeliefert). Kein Build-Schritt, keine Abhängigkeit, keine externe Quelle: die CSP ist `default-src 'self'`, Tests verbieten externe URLs, Inline-Styles und HTML-Einfügen von Text.

Aktualisiert sich alle 2 s (nicht im Hintergrund-Tab). Klick auf den Namen öffnet die Bearbeitung: Enter speichert, Esc bricht ab, Cmd+Enter speichert aus der Beschreibung. „Fortsetzen“ und „Nach vorn“ kommen mit P4.

## API

| Aufruf | Wirkung |
|---|---|
| `GET /api/sessions?stunden=48` (oder `?alle=1`) | Liste wie `5c list --json`, mit `name` und `beschreibung` |
| `PATCH /api/sessions/<id>` `{"name": …, "beschreibung": …}` | setzt eines oder beides, leerer Text löscht; gespeichert in `meta.json` |

Schutz: nur `127.0.0.1`, `Host` muss `127.0.0.1:4555` oder `localhost:4555` sein, schreibende Aufrufe brauchen den Kopf `X-5C-Token` (steht als `<meta name="fivec-token">` in der ausgelieferten Seite, neu bei jedem Start) und keinen fremden `Origin`. Name höchstens 60 Zeichen, eine Zeile; Beschreibung höchstens 2000; Steuerzeichen sowie unsichtbare und bidirektionale Zeichen werden abgewiesen, weil beides später in iTerm2-Titel und -Badge landet.
