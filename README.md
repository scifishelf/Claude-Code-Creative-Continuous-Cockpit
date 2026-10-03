# 5C - Claude Code Creative Continuous Cockpit

Übersicht aller Claude-Code-Sessions auf diesem Mac: Fortsetzen per Klick in iTerm2, Status live, eigene Namen und Beschreibungen. Plan und Stand: [docs/plans/2026-10-03-5c-v1-plan.md](docs/plans/2026-10-03-5c-v1-plan.md), Messungen: [docs/plans/2026-10-03-messungen-ist.md](docs/plans/2026-10-03-messungen-ist.md).

## Einrichten

Voraussetzungen: macOS, iTerm2, Python ab 3.10 (Homebrew), Node für die Prüfkette, Claude Code.

```sh
./install.sh      # 5C.app (fivec://), iTerm2-Profil „5C“, Dienst als launchd-Agent (Login, Neustart nach Absturz)
./uninstall.sh    # alles wieder weg; --alles löscht auch Namen, Beschreibungen und Logs
```

Danach: http://127.0.0.1:4555/ oder 5C.app doppelklicken. Drei macOS-Abfragen beim ersten Mal, alle erlauben:
1. **Python → Schreibtisch** (Dateien und Ordner), wenn das Repo dort liegt: sonst startet der Dienst nicht und lauscht nicht. Der Dienst liest außerdem den Git-Stand der Repos dort.
2. **5C → iTerm** (Automation), beim ersten Klick auf einen `fivec://`-Link.
3. **Python → iTerm** (Automation), beim ersten „Fortsetzen“ oder „Nach vorn“ auf der Seite.

Logs: `~/Library/Logs/5C/dienst.log`, Aufrufe der App: `~/Library/Application Support/5C/5c.log`.

## Stand: V1 (P0 bis P6)

```sh
bin/5c dienst               # Übersicht auf http://127.0.0.1:4555/ (läuft nach install.sh per launchd)
bin/5c open <session-id>    # nach vorn holen, sonst in iTerm2 fortsetzen
werkzeug/app_bauen.sh       # baut ~/Applications/5C.app, registriert fivec://open/<session-id>
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

Aktualisiert sich alle 2 s (nicht im Hintergrund-Tab). Klick auf den Namen öffnet die Bearbeitung: Enter speichert, Esc bricht ab, Cmd+Enter speichert aus der Beschreibung.

## Gesundheit

| Zustand | Bedingung | Tab-Titel |
|---|---|---|
| arbeitet | läuft, `status: busy` | 🟢 |
| wartet auf Dich | läuft, `status: idle` oder `waiting`, oder `waitingFor` gesetzt (offene Freigabe) | 🟡 |
| hängt vielleicht | seit über 10 Min. `busy` **und** seit über 10 Min. keine neue Zeile im Verlauf | 🟠 |
| startet | `claude --resume <id>` läuft, aber noch ohne Statusdatei | 🔵 |
| verwaist | Statusdatei da, Prozess tot oder Startzeit passt nicht | |
| ruht | sonst | |

Ein `ps`-Aufruf je Takt liefert Lebendprüfung, CPU, Speicher, Laufzeit, App (erste `.app` in der Elternkette) und `caffeinate` (`fivec/prozesse.py`, `fivec/gesundheit.py`). Der Dienst hält Titel und Badge der von 5C gestarteten iTerm2-Tabs auf Stand (`fivec/tabsync.py`): `osascript` nur bei geändertem Soll, sonst höchstens alle 10 s als Nachkontrolle (ein Abgleich kostet gemessen rund 280 ms).

## Fortsetzen und nach vorn holen

„Fortsetzen“, „Nach vorn“, `5c open` und `fivec://open/<id>` laufen alle über `fivec/oeffnen.py`:
läuft die Session in iTerm2, wird ihr Tab gewählt (gemerkte iTerm2-ID oder TTY); läuft sie in einer anderen App (z. B. Cursor), wird diese App aktiviert; sonst startet ein neues iTerm2-Fenster mit Profil „5C“ `cd <cwd> && caffeinate -dims claude --resume <id>`. Eine atomare Startsperre (15 s) und ein Blick aufs gemerkte TTY verhindern den Doppelstart. cwd und Befehl kommen aus dem Index, nie aus der URL.

5C legt dafür das dynamische iTerm2-Profil `~/Library/Application Support/iTerm2/DynamicProfiles/5c.json` an (Titel nicht von Programmen überschreibbar, Badge aus Name und Beschreibung) und merkt sich iTerm2-IDs in `iterm.json`. Spur aller Aufrufe: `~/Library/Application Support/5C/5c.log`. Beim ersten Mal fragt macOS „… möchte iTerm steuern“: bestätigen.

## API

| Aufruf | Wirkung |
|---|---|
| `GET /api/sessions?stunden=48` (oder `?alle=1`) | Liste wie `5c list --json`, mit `name` und `beschreibung` |
| `PATCH /api/sessions/<id>` `{"name": …, "beschreibung": …}` | setzt eines oder beides, leerer Text löscht; gespeichert in `meta.json` |

Schutz: nur `127.0.0.1`, `Host` muss `127.0.0.1:4555` oder `localhost:4555` sein, schreibende Aufrufe brauchen den Kopf `X-5C-Token` (steht als `<meta name="fivec-token">` in der ausgelieferten Seite, neu bei jedem Start) und keinen fremden `Origin`. Name höchstens 60 Zeichen, eine Zeile; Beschreibung höchstens 2000; Steuerzeichen sowie unsichtbare und bidirektionale Zeichen werden abgewiesen, weil beides später in iTerm2-Titel und -Badge landet.
