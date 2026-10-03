# Handoff 5C - Claude Code Creative Continuous Cockpit

Stand: 03.10.2026, `5db324e` auf `main`, gepusht nach `github.com:scifishelf/Claude-Code-Creative-Continuous-Cockpit` (**öffentlich**).

## Wo was steht

| Frage | Datei |
|---|---|
| Bedienung, Einrichten, API, Gesundheit, Fortsetzen | [README.md](README.md) |
| Plan V1, Phasen P0 bis P6, Entscheidungen E1 bis E6, Ideen für danach | [docs/plans/2026-10-03-5c-v1-plan.md](docs/plans/2026-10-03-5c-v1-plan.md) |
| Messbefunde (Statusdateien, iTerm2, Titel, launchd, Schreibtisch-Freigabe) | [docs/plans/2026-10-03-messungen-ist.md](docs/plans/2026-10-03-messungen-ist.md) |
| Entwürfe der Oberfläche (Variante A gewählt) | Canvas https://claude.ai/artifact/1FVkuCvMRSmi3Y7RDKXbeS (privat) |

## Wo wir stehen

V1 ist fertig (P0 bis P6, je ein Commit) und auf diesem Mac eingerichtet:

- **Dienst** läuft als launchd-Agent `dev.fivec.cockpit.dienst` auf http://127.0.0.1:4555/, startet beim Login und nach Absturz neu (geprüft mit `kill -9`).
- **5C.app** in `~/Applications` öffnet `fivec://open/<session-id>` (geprüft: holt iTerm2 nach vorn).
- **iTerm2-Profil „5C“** unter `~/Library/Application Support/iTerm2/DynamicProfiles/5c.json`.
- macOS-Freigaben erteilt: Python → Schreibtisch, 5C → iTerm, Python/Cursor → iTerm.
- Die Probe-Session aus P0 bis P5 ist samt Ordnern aufgeräumt.

## Der nächste Schritt

**Nicht abgestimmt.** V1 ist abgeschlossen; was als Nächstes kommt, entscheidet der Nutzer. Kandidaten, ohne Reihenfolge:

1. **Offene Kleinmessungen** M1a (`waitingFor` in einer Session ohne Auto-Modus) und M2a (bleibt die Statusdatei nach `/exit` und zweimal Ctrl-C liegen?). Beide brauchen eine Eingabe des Nutzers in eine Session; Anleitung im Ist-Dokument, Abschnitt „Offen für den Nutzer“.
2. **Ideen aus dem Plan** (Abschnitt „Ideen für danach“): Mitteilung bei „wartet auf Dich“, automatischer Status Offen/Beendet/Unklar, Menüleisten-Symbol, Wiederaufnahmeprompt kopieren, ein Fenster je Projekt.
3. **Alte Testdaten in der Git-Historie** (Testdaten aus P3 und P4): nur per Umschreiben der Historie und Force-Push zu entfernen. Nur auf ausdrücklichen Wunsch.

## Was sofort zuschlägt

- **Prüfkette:** `./pruefen.sh` muss grün sein: **69 Python- und 11 JS-Tests**. Gegenprobe `python3 werkzeug/mutationen.py`: **38 von 38 gefangen**. Jeder Fix bekommt einen Test und eine Mutation, die ihn belegt.
- **Port 4555 gehört dem launchd-Dienst.** Ein zusätzlicher `bin/5c dienst` scheitert am Port. Zum Testen den Agent stoppen (`launchctl bootout gui/$(id -u)/dev.fivec.cockpit.dienst`) oder `--port` wählen; nach Codeänderungen `launchctl kickstart -k gui/$(id -u)/dev.fivec.cockpit.dienst`.
- **Der Auto-Modus blockt zweierlei:** in eine andere Claude-Session tippen (per iTerm2) und `npx`/fremden Code ausführen. Beides dem Nutzer als `! <befehl>` geben, nicht umgehen.
- **System-Python ist 3.9** und kann den Code nicht ausführen; App und Agent rufen fest `/opt/homebrew/bin/python3`. Nach einem Python-Upgrade fragt macOS vermutlich die Schreibtisch-Freigabe erneut ab, und `./install.sh` muss neu laufen.
- **Ein Pfadwechsel des Repos** braucht `./install.sh` neu (App und Agent enthalten den Pfad).

## Arbeitsweise

- Ein Posten, ein Commit, `./pruefen.sh` davor; Commit und Push nur nach Freigabe des Nutzers.
- Messbefunde ins Ist-Dokument, Entscheidungen in den Plan; der Nutzer wird geduzt, Umlaute, keine Gedankenstriche.
- UI-Änderungen: vorher Wortlaut und Gestaltung zur Auswahl vorlegen, danach Browserprobe (dunkel, hell, Handy) per Playwright aus `~/Desktop/coding/brandad-refold/oberflaeche/node_modules/@playwright/test`.
- Keine externen Quellen zur Laufzeit (CSP `default-src 'self'`, Schriften lokal).

## Einzeiliger Prompt für die nächste Sitzung

```
Lies ~/Desktop/coding/claude-code-creative-continuous-cockpit/HANDOFF.md und von dort README und Plan. 5C V1 ist fertig und eingerichtet; der nächste Schritt ist nicht abgestimmt, also lege mir ZUERST die Kandidaten aus dem Abschnitt „Der nächste Schritt“ mit Empfehlung vor und baue erst nach meiner Wahl. Je Posten ein Commit mit ./pruefen.sh davor; Prüfzahlen, Fallstricke und Arbeitsweise stehen im Handoff.
```
