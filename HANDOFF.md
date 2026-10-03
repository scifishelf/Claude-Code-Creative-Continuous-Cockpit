# Handoff 5C - Claude Code Creative Continuous Cockpit

Stand: 03.10.2026, `eb65018` auf `main`, gepusht nach `github.com:scifishelf/Claude-Code-Creative-Continuous-Cockpit` (**öffentlich**).

## Wo was steht

| Frage | Datei |
|---|---|
| Bedienung, Einrichten, API, Gesundheit, Fortsetzen | [README.md](README.md) |
| Plan V1, Phasen P0 bis P6, Entscheidungen E1 bis E8, Ideen für danach | [docs/plans/2026-10-03-5c-v1-plan.md](docs/plans/2026-10-03-5c-v1-plan.md) |
| Messbefunde (Statusdateien, iTerm2, Titel, launchd, Schreibtisch-Freigabe, Mitteilung) | [docs/plans/2026-10-03-messungen-ist.md](docs/plans/2026-10-03-messungen-ist.md) |
| Entwürfe der Oberfläche (Variante A gewählt) | Canvas https://claude.ai/artifact/1FVkuCvMRSmi3Y7RDKXbeS (privat) |

## Wo wir stehen

V1 ist abgeschlossen und in Nutzung: P0 bis P6, danach M1a (Statuswert `waiting`), E7 (Mitteilung bei „wartet auf Dich“) und E8 (Gruppen nach Projekt, Ausblenden), je ein Commit. Eingerichtet auf diesem Mac:

- **Dienst** läuft als launchd-Agent `dev.fivec.cockpit.dienst` auf http://127.0.0.1:4555/, startet beim Login und nach Absturz neu (geprüft mit `kill -9`).
- **5C.app** in `~/Applications` öffnet `fivec://open/<session-id>` (geprüft: holt iTerm2 nach vorn).
- **iTerm2-Profil „5C“** unter `~/Library/Application Support/iTerm2/DynamicProfiles/5c.json`.
- macOS-Freigaben erteilt: Python → Schreibtisch, 5C → iTerm, Python/Cursor → iTerm.
- 5C.app nach E7 neu gebaut, Dienst neu gestartet, „5C → Schreibtisch“ erlaubt.
- Probe-Sessions beendet; `/tmp/5c-probe` mit `probe2.txt` und deren Verläufe unter `~/.claude/projects/-private-tmp-5c-probe/` liegen noch.

## Der nächste Schritt

**Nicht abgestimmt.** Der Nutzer will 5C jetzt nutzen; Neues nur auf seinen Wunsch. Kandidaten, ohne Reihenfolge:

1. **Klick auf die Mitteilung belegen** (Ist-Dokument, Nachtrag E7): Mitteilung anklicken, dann `5c.log` lesen. Fehlt `klick`, leitet macOS den Klick nicht an das Applet weiter. Der Nutzer hält Mitteilungen für nachrangig.
2. **5C.app über die API des Dienstes** statt über `bin/5c`: Dann fragt nicht mehr jeder Neubau die Schreibtisch-Freigabe ab.
3. **M2a** (`/exit` und zweimal Ctrl-C, bleibt die Statusdatei liegen?): braucht eine Eingabe des Nutzers in eine Session.
4. **Ideen aus dem Plan** (Abschnitt „Ideen für danach“).
5. **Alte Testdaten in der Git-Historie** (P3, P4): nur per Umschreiben der Historie und Force-Push, nur auf ausdrücklichen Wunsch.

## Was sofort zuschlägt

- **Prüfkette:** `./pruefen.sh` muss grün sein: **93 Python- und 15 JS-Tests**. Gegenprobe `python3 werkzeug/mutationen.py`: **59 von 59 gefangen**. Jeder Fix bekommt einen Test und eine Mutation, die ihn belegt.
- **Port 4555 gehört dem launchd-Dienst.** Ein zusätzlicher `bin/5c dienst` scheitert am Port. Zum Testen den Agent stoppen (`launchctl bootout gui/$(id -u)/dev.fivec.cockpit.dienst`) oder `--port` wählen; nach Codeänderungen `launchctl kickstart -k gui/$(id -u)/dev.fivec.cockpit.dienst`.
- **Jeder Neubau von 5C.app** (`install.sh`, `werkzeug/app_bauen.sh`) fragt „5C → Schreibtisch“ neu ab; bis zur Antwort hängt das Applet (`UserNotificationCenter` vorn). Der Agent sieht den Dialog nicht: den Nutzer bitten.
- **Eine Probe-Session ohne Eintippen:** in iTerm2 per `write text` `claude --permission-mode default "<Prompt>"` starten, der Prompt als Argument. So entstanden M1a und die E7-Proben. Danach den Fokus zurückgeben (`open -a Cursor`), sonst unterdrückt 5C die Mitteilung, weil der Tab vorn ist.
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
Lies ~/Desktop/coding/claude-code-creative-continuous-cockpit/HANDOFF.md und von dort README und Plan. 5C V1 ist abgeschlossen, eingerichtet und in Nutzung (dazu M1a und E7 Mitteilung); der nächste Schritt ist nicht abgestimmt, also lege mir ZUERST die Kandidaten aus dem Abschnitt „Der nächste Schritt“ mit Empfehlung vor und baue erst nach meiner Wahl. Je Posten ein Commit mit ./pruefen.sh davor; Prüfzahlen, Fallstricke und Arbeitsweise stehen im Handoff.
```
