# 5C - Claude Code Creative Continue Cockpit

Übersicht aller Claude-Code-Sessions auf diesem Mac: Fortsetzen per Klick in iTerm2, Status live, eigene Namen und Beschreibungen. Plan und Stand: [docs/plans/2026-10-03-5c-v1-plan.md](docs/plans/2026-10-03-5c-v1-plan.md), Messungen: [docs/plans/2026-10-03-messungen-ist.md](docs/plans/2026-10-03-messungen-ist.md).

## Stand: P1

```sh
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
