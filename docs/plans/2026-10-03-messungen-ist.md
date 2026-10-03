# P0 Messungen - Ist

Stand: 03.10.2026, Claude Code 2.1.288, iTerm2 3.7.3, macOS (Darwin 27.0.0). Gemessen an einer Test-Session in `/tmp/5c-probe` (Session `64acb6d7-…`), gestartet und gesteuert per AppleScript aus iTerm2.

## Kurzfassung: was der Plan daraus übernimmt

| Befund | Folge für 5C |
|---|---|
| `claude-cli://` kann weder fortsetzen noch fokussieren | eigenes Schema `fivec://` bleibt |
| `status` ist `idle`, `busy` oder `waiting`; bei offener Freigabe steht `waiting` mit `waitingFor: "permission prompt"` (M1a) | Zustände „Arbeitet“ und „Wartet auf Dich“ direkt aus der Statusdatei |
| Vor der Vertrauensfrage gibt es nur `.key`, keine `.json` | neuer Zustand „Startet“: `claude` am TTY, aber noch keine Statusdatei |
| `kill -9` lässt `.json` liegen, bis sie offenbar eine andere laufende Claude-Instanz aufräumt (gemessen: weg nach etwa 2 min); SIGTERM räumt sofort auf | „Verwaist“ = Datei da, Prozess tot oder `procStart` passt nicht. Der Zustand ist kurzlebig, 5C darf sich nicht darauf verlassen, dass er lange sichtbar ist |
| `procStart` steht in **UTC**, `ps -o lstart` in **Ortszeit** | Vergleich nur nach Umrechnung, sonst gilt jede Session als verwaist |
| `cwd` in der Statusdatei ist aufgelöst (`/private/tmp/…` statt `/tmp/…`) | Pfade vor jedem Vergleich mit `realpath` normalisieren |
| Der abgeleitete `name` wechselt bei jedem Start (`5c-probe-03`, dann `5c-probe-6a`) | Namen nur aus 5C, wie in E4 entschieden |
| iTerm2-Sessions sind über `unique ID` und über `tty` auffindbar und lassen sich fokussieren | Doppelstart-Schutz wie geplant |
| Titel und Badge lassen sich live setzen, **ohne** ins TTY von `claude` zu schreiben | Name und Beschreibung am Tab wie geplant |
| Die Tab-Farbe lässt sich ohne Python-Paket **nicht** live ändern | Entscheidung E5 |
| Der Auto-Modus von Claude Code verbietet einer Session, per iTerm2 in eine andere Claude-Session zu tippen | 5C startet nur und fokussiert, tippt nie in eine laufende Session. Das ist ohnehin außerhalb von V1 |

## M1: Statusdatei `~/.claude/sessions/<pid>.json`

- **Werte von `status`:** nach dem Start `idle`, während eines Turns `busy`, danach wieder `idle` (gemessen: `busy` um …484551, `idle` um …490761, also etwa 6 s für einen kleinen Turn).
- **Felder** (aus dem Leser im Binary): `pid`, `sessionId`, `cwd`, `kind`, `entrypoint`, `status`, `waitingFor`, `updatedAt`, `statusUpdatedAt`, `name`, `nameSource`, `procStart`, `messagingSocketPath`, `logPath`, `jobId`, `parkedJobId`, `spare`, `state`, `detail`, `agent`.
- **`statusUpdatedAt`** wird nur bei einem Statuswechsel gesetzt, **`updatedAt`** bei jedem Schreiben. Im Leerlauf schreibt Claude nicht, `updatedAt` bleibt also stehen. Ein altes `updatedAt` bei `idle` ist deshalb normal und kein Zeichen von Hängen.
- **`waitingFor` (M1a, gemessen 03.10.2026):** Eine Session ohne Auto-Modus (`claude --permission-mode default "Lege die Datei probe.txt … an."`, Prompt als Argument, also ohne Eintippen) stand nach etwa 4 s auf `"status": "waiting"`, `"waitingFor": "permission prompt"`. `status` kennt damit einen **dritten Wert**, `waiting`; `statusUpdatedAt` springt beim Wechsel mit. 5C wertet `waitingFor` zuerst aus und zeigt „wartet auf Dich“; `waiting` ohne `waitingFor` zählt ebenso.
- **`peerFeatures`** enthält `notify_idle`: Claude kennt selbst eine Meldung beim Leerlauf. 5C baut darauf nicht auf, weil die Statusdatei genügt.
- **Vertrauensfrage:** Solange beim ersten Start in einem Ordner die Frage „Is this a project you … trust?“ offen ist, existiert nur `<pid>.<hash>.key`, noch keine `<pid>.json`.
- **Lebendprüfung:** Claude selbst hält einen Eintrag nur dann für lebendig, wenn der `pid` läuft **und** die Prozess-Startzeit zu `procStart` passt (Schutz gegen wiederverwendete PIDs). Gemessen: `procStart` = `Sat Oct  3 08:32:51 2026`, `ps -o lstart=` = `Sat Oct  3 10:32:51 2026`. Das ist dieselbe Sekunde, nur in UTC gegen Ortszeit.
- **Prozesskette bei `caffeinate -dims claude --resume <id>`:** `zsh` → `claude` (pid in der Statusdatei) → `caffeinate`. `caffeinate` ist also am TTY über `ps -t <tty>` erkennbar.
- **M1b offen:** Was passiert, wenn dieselbe Session ein zweites Mal mit `--resume` gestartet wird, während sie läuft? Claude erkennt laut Code einen „holder“. 5C verhindert den Fall ohnehin. Gemessen wird er später nur, wenn der Schutz einmal versagt.

## M2: Was bleibt nach dem Beenden liegen?

| Weg | `.json` | `.key` | gemessen |
|---|---|---|---|
| SIGTERM (`kill -TERM`) | entfernt | entfernt | ja |
| `kill -9` | **bleibt** | **bleibt** | ja: `9549.json` lag nach dem Abschuss um 10:35 noch da, war um 10:37 weg. Aufgeräumt hat sehr wahrscheinlich die einzige andere laufende Claude-Instanz (pid 72366), 5C löscht nichts. Wer genau aufräumt, ist nicht belegt |
| `/exit` | - | - | **offen (M2a)**, braucht eine Eingabe in die Session, siehe unten |
| Ctrl-C (zweimal) | - | - | **offen (M2a)** |

`caffeinate` endet mit dem `claude`-Prozess, auch bei `kill -9`.

## M3: Kann `claude-cli://` fortsetzen oder fokussieren?

**Nein.** Der Parser im Binary kennt genau zwei Aktionen:

| Aktion | Parameter | Wirkung |
|---|---|---|
| `claude-cli://open` | `cwd`, `repo` (`owner/repo`), `q` (vorbefüllter Prompt) | neue Session in Terminal.app oder iTerm2 öffnen |
| `claude-cli://install-plugin` | `plugin`, `marketplace` | Plugin installieren |

Jede andere Aktion endet mit `Unknown deep link action`. Brauchbar als Vorbild: Claude prüft `cwd` auf Steuerzeichen sowie unsichtbare und bidirektionale Zeichen und begrenzt die Länge. 5C übernimmt das für Namen und Beschreibungen.

## M4: iTerm2 per AppleScript finden und fokussieren

- **Starten:** `create window with default profile`, dann `write text "cd … && claude …"`. Das läuft in der Login-Shell, `claude` und `caffeinate` werden gefunden. Rückgabe: Fenster-ID (`360`), `unique ID` der Session (`37FAB72D-…`), `tty` (`/dev/ttys017`).
- **Finden und fokussieren:** Alle Fenster, Tabs und Sessions durchlaufen, auf `unique ID` (oder `tty`) prüfen, dann `select` auf Fenster, Tab und Session und `activate`. Ergebnis: `frontmost` = `true`.
- **Unzuverlässig:** `is at shell prompt` meldete `false`, obwohl die Shell bereit war. Das braucht die Shell-Integration von iTerm2. 5C entscheidet stattdessen über `ps -t <tty>`.
- **Nicht gemessen:** Vollbild und geteilte Bereiche. Das wird in P4 mitgeprüft.
- **Freigabe:** Das erste AppleScript an iTerm2 löst die macOS-Abfrage „… möchte iTerm steuern“ aus. Wird sie abgelehnt, kommt sie nicht wieder (Fehler `-1743`). Zurück geht es nur über die Systemeinstellungen oder `tccutil reset AppleEvents <bundle-id>`. **`install.sh` (P6) muss das ankündigen und `-1743` mit einer klaren Anleitung abfangen.**

## M5: Titel, Badge und Tab-Farbe live

| Element | Weg | Ergebnis |
|---|---|---|
| **Titel** | AppleScript `set name to "…"` | geht live. iTerm2 hängt den laufenden Job an („5C Probe (claude)“). Ob sich das im Profil abschalten lässt, wird in P4 geprüft |
| **Badge** | Profil mit Badge-Vorlage `\(user.fivec_badge)`, dann AppleScript `set variable named "user.fivec_badge"` | geht live, ohne ins TTY zu schreiben (gemessen: `variable named "badge"` = gesetzter Text) |
| **Tab-Farbe fest** | im Profil (`Use Tab Color`, `Tab Color`) | geht |
| **Tab-Farbe live** | AppleScript: keine Eigenschaft. `invoke API expression`: keine eingebaute Funktion dafür (`iterm2.set_name`, `iterm2.set_title`, `iterm2.set_status` …, aber keine Farbe) | geht **nicht** ohne die Python-API (Paket `iterm2`) oder Steuersequenzen ins TTY |

**Profil:** 5C legt ein dynamisches Profil `~/Library/Application Support/iTerm2/DynamicProfiles/5c.json` an (Elternprofil `Default`, Badge-Vorlage). Getestet mit `5c-probe.json`, das nach der Messung wieder entfernt wurde.

## Entscheidung E5: Status am Tab (entschieden 03.10.: Emoji im Titel)

Steuersequenzen ins TTY scheiden aus: Sie würden mitten in die Bildschirmausgabe von `claude` fallen und könnten dessen Darstellung zerstören. Bleiben drei Wege:

1. **Status als Zeichen im Titel (empfohlen):** z. B. `● 5C-Name`, mit `●` grün/gelb/orange gedacht, umgesetzt als Emoji `🟢 🟡 🟠`, live per `set name`. Ohne Abhängigkeit, sofort sichtbar in der Tab-Leiste.
2. **Python-API von iTerm2:** echte Tab-Farbe live. Braucht das Paket `iterm2` (bricht E3) und eine Freigabe in den iTerm2-Einstellungen.
3. **Feste Farbe je Profil:** z. B. alle 5C-Tabs in einer Farbe, Status nur auf der Seite.

## Offen für den Nutzer (braucht eine Eingabe in eine Session)

- **M2a `/exit` und Ctrl-C:** je einmal in einer Test-Session, danach `ls ~/.claude/sessions/`.

Das kann der Agent nicht selbst: Der Auto-Modus blockt, dass eine Claude-Session per iTerm2 in eine andere tippt.

## Hinterlassenschaften der Messung

- `~/.claude/sessions/9549.json` und `9549.*.key`: absichtlich verwaist (aus dem `kill -9`), um 10:37 von Claude selbst aufgeräumt. Für P5 wird ein Testfall künstlich angelegt (siehe `tests/test_live.py`).
- `~/.claude/projects/-private-tmp-5c-probe/`: Verlauf der Test-Session.
- `/tmp/5c-probe/`: leerer Testordner.

## Nachtrag P4 (03.10.2026): Befunde beim Bau von „Fortsetzen“ und „Nach vorn“

| Befund | Fundstelle | Folge |
|---|---|---|
| Claude Code setzt per Steuersequenz einen eigenen Tab-Titel („✳ probe.txt erstellen“) und überschreibt damit `set name` | Titel der Test-Session nach `5c open` | 5C startet mit eigenem dynamischem Profil „5C“: `Allow Title Setting: false`, `Title Components: 1` (nur Session-Name), `Badge Text: \(user.fivec_badge)`. Angelegt von `fivec/iterm.py` unter `~/Library/Application Support/iTerm2/DynamicProfiles/5c.json` |
| Gegenprobe: Mit dem Profil kommt ein `printf "\033]0;UEBERSCHRIEBEN\007"` nicht mehr an, ein Wechsel `🟢` → `🟡` per `set name` schon | Testfenster mit `sleep` | E5 (Status-Emoji im Titel) ist umsetzbar |
| Trotz Profil steht nach dem Start von `claude` einmal „Chat“ im Titel: `session.name` = `session.autoName` = „Chat“, `terminalWindowName` leer. Wer es setzt, ist nicht belegt; es ist keine Steuersequenz | `osascript`, Variablen der Session | Ein danach gesetzter Titel hält (nach 12 s gemessen). Der Dienst zieht den Titel in P5 bei jedem Zustandswechsel nach |
| `AppleScript` kann den Tab-Titel (`title of tab`) nicht setzen: Fehler `-10000` | `set title of t` | nur `set name` auf der Session |
| `/usr/bin/python3` ist 3.9 und kann den Code nicht ausführen (`str \| None`); der PATH eines Applets ist minimal | `python3 --version` | `werkzeug/app_bauen.sh` trägt das Python des Baus fest ein (`/opt/homebrew/bin/python3`) und bricht unter 3.10 ab |
| `osacompile` trägt englische Begründungstexte ein; ein `Add` auf `NSAppleEventsUsageDescription` scheitert still | `plutil -p` | Bauskript setzt den deutschen Text per `Set` |
| Der erste `fivec://`-Klick löst „5C möchte iTerm steuern“ aus; solange die Abfrage offen ist, passiert sichtbar nichts. Danach geht es | `5c.log`, vordere App | `install.sh` (P6) kündigt die Abfrage an |
| Zwei schnelle Klicks könnten in zwei Server-Threads oder in App und Dienst gleichzeitig „keine Sperre“ sehen | Code-Durchsicht | Startsperre atomar per `O_EXCL`; Test mit 5 parallelen Aufrufen, genau ein Start |
| Ein Start kann länger als die 15-s-Sperre dauern (z. B. offene Vertrauensfrage) | Ablauf | Zusätzlich: Läuft am gemerkten TTY schon `claude --resume <id>`, wird nicht erneut gestartet |

## Nachtrag P6 (03.10.2026): Einrichten als launchd-Agent

| Befund | Fundstelle | Folge |
|---|---|---|
| Der Dienst unter launchd startete, lauschte aber nicht und schrieb nichts ins Log. Stack: `pymain_get_importer`, also beim ersten Lesen von `bin/5c` auf dem Schreibtisch | `sample <pid>` | macOS schützt den Schreibtisch; ein launchd-Prozess braucht dafür eine eigene Freigabe (Dateien und Ordner → Python → Schreibtisch). Nach dem Erlauben lief er sofort. Die Freigabe ist ohnehin nötig, weil der Dienst den Git-Stand der Repos auf dem Schreibtisch liest |
| Die Freigabe gilt dem Homebrew-Python (`/opt/homebrew/Cellar/python@3.14/…/Python.app`), nicht 5C | `ps` des Dienstes | Nach einem Python-Upgrade fragt macOS vermutlich erneut (nicht gemessen) |
| `kill -9` auf den Dienst: launchd startet ihn neu (`runs = 2`, neue pid), die API antwortet wieder mit 200 | `launchctl print` | `KeepAlive` plus `ThrottleInterval 10` reichen |
| Der Dienst steuert iTerm2 selbst (Tab-Abgleich, Knopf „Nach vorn“) ohne weitere Abfrage | `POST /api/sessions/<id>/open`, `dienst.log` | |
| Ein von Hand laufender `5c dienst` hielte Port 4555; der Agent liefe dann in Neustarts | Ablauf | `install.sh` bricht mit Hinweis ab |

## Nachtrag E7 (03.10.2026): Mitteilung bei „wartet auf Dich“

| Befund | Fundstelle | Folge |
|---|---|---|
| Bei einer offenen Rückfrage (AskUserQuestion) steht `"status": "waiting"`, `"waitingFor": "input needed"`, bei einer Freigabe `"permission prompt"` | Statusdatei dieser Session, sekündlich mitgelesen | Titel der Mitteilung nach `waitingFor`: Freigabe, Antwort, fertig |
| `open -g fivec://melden/<id>` lässt den Fokus, wo er ist (vorher und nachher Cursor vorn) | `lsappinfo front` | Weg über 5C.app, die Mitteilung kommt von 5C |
| **Jeder Neubau von 5C.app fragt „5C → Schreibtisch“ neu ab.** Bis zur Antwort hängt das Applet, die URL kommt nicht an (`UserNotificationCenter` vorn, kein Eintrag in `5c.log`) | zweimal beobachtet nach `werkzeug/app_bauen.sh` | Die Ad-hoc-Signatur wechselt mit dem Skript. Nach `install.sh` oder `app_bauen.sh` die Abfrage erlauben. Abhilfe in den Ideen des Plans |
| Der Dienst meldet echt: `melden <id>: Braucht Deine Freigabe` (12:52:56, vor der Textkorrektur) und `Braucht Deine Antwort` (13:51:33) für eine Session in Cursor, während sie auf eine Rückfrage wartete | `5c.log` | Auslöser, Text und Weg stimmen |
| Ein Start der App (`open -a 5C.app`) mit frischem Merker ruft `5c klick` und holt die gemerkte Session nach vorn (`klick …: In iTerm2 nach vorn geholt.`) | `5c.log`, `lsappinfo front` | `on run` und `klick` arbeiten |
| **Offen:** Ob ein Klick auf die Mitteilung selbst bei 5C ankommt, ist nicht belegt. Nach dem Klick um 12:52 lag der Merker unverbraucht da, `klick` fehlt im Log. Seitdem ist `on reopen` ergänzt (läuft das Applet beim Klick noch, kommt reopen statt run) und jeder Klick wird protokolliert, auch „keine frische Mitteilung“. Danach nicht mehr geprobt | `5c.log` | Nächste Probe: Mitteilung anklicken, dann `tail ~/Library/Application\ Support/5C/5c.log`. Fehlt `klick`, leitet macOS den Klick nicht an ein Applet weiter |
