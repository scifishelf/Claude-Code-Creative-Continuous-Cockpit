# 5C - Claude Code Creative Continuous Cockpit

A local dashboard for every Claude Code session on your Mac. See at a glance which sessions are working, waiting for you or possibly stuck, resume any session in iTerm2 with one click, and give sessions your own names and descriptions. Those names also show up as the iTerm2 tab title and badge.

Everything runs locally: a small Python service with no dependencies, a static web page and an AppleScript app for the `fivec://` URL scheme. The UI is in German.

## Features

- **Overview** of all sessions from `~/.claude/projects`, **grouped by project** (working directory). Groups with running sessions come first, and the rest are sorted by last activity. Groups can be collapsed, but a collapsed group still shows its running sessions.
- **Live health** for every running session, refreshed every 2 s: working, waiting for you, possibly stuck, starting, orphaned, idle. Also shows CPU, memory, uptime, the host app (iTerm2, Cursor, …) and whether `caffeinate` is active.
- **One click to resume:** a running session's iTerm2 tab is brought to the front, or the host app is activated if it runs elsewhere. A stopped session is resumed in a new iTerm2 window with `caffeinate -dims claude --resume <id>`. Double starts are prevented.
- **Names and descriptions** per session, edited inline and stored by 5C only. The iTerm2 tab shows them as title and badge, prefixed by a status emoji (🟢 working, 🟡 waiting, 🟠 possibly stuck, 🔵 starting).
- **Notifications** when a session switches from working to waiting: "needs your permission", "needs your answer" or "done".
- **Hide** sessions or whole projects, with undo. Running sessions always stay visible.
- **Git status** of each working directory (uncommitted changes, last commit).

## Requirements

macOS, [iTerm2](https://iterm2.com), Python 3.10 or newer (Homebrew), Claude Code, and Node.js for the test suite.

## Install

```sh
./install.sh      # builds 5C.app (fivec://), the iTerm2 profile "5C" and a launchd agent for the service
./uninstall.sh    # removes all of it; --alles also deletes names, descriptions and logs
```

Then open http://127.0.0.1:4555/, or double-click `~/Applications/5C.app`.

macOS asks for a few permissions the first time. Allow all of them:

1. **Python → Desktop** (Files and Folders), if the repo lives on the Desktop. Without it the service starts but never listens. The service also reads the Git status of repos there.
2. **5C → Desktop**, on the first `fivec://` link or notification. macOS asks again **after every rebuild of 5C.app**, because the ad-hoc signature changes. Until you allow it, neither links nor notifications get through.
3. **5C → iTerm** (Automation), on the first `fivec://` link.
4. **Python → iTerm** (Automation), on the first "Fortsetzen" (resume) or "Nach vorn" (bring to front) on the page.

Logs: `~/Library/Logs/5C/dienst.log` (service) and `~/Library/Application Support/5C/5c.log` (app calls, notifications, clicks).

## Command line

```sh
bin/5c dienst               # the service on http://127.0.0.1:4555/ (runs via launchd after install.sh)
bin/5c list                 # sessions active in the last 48 h, newest first
bin/5c list --stunden 240   # another time window
bin/5c list --alle --json   # everything, machine-readable
bin/5c open <session-id>    # bring to front, otherwise resume in iTerm2
bin/5c klick                # bring the last notified session to front (used by 5C.app)
werkzeug/app_bauen.sh       # rebuild ~/Applications/5C.app and register fivec://
```

After a code change, restart the service: `launchctl kickstart -k gui/$(id -u)/dev.fivec.cockpit.dienst`. Port 4555 belongs to the launchd agent, so a second `bin/5c dienst` needs `--port`.

## How it works

```
Browser ──http──▶ 5C service (127.0.0.1:4555) ◀── reads ── ~/.claude/projects/*/*.jsonl
                     │      │                             ~/.claude/sessions/*.json, ps, git
                     │      └─ osascript ─▶ iTerm2: find, focus, start, title and badge
                     ▼
5C.app (fivec://) ─▶ bin/5c ─▶ ~/Library/Application Support/5C/ (names, hidden items, iTerm2 IDs, index cache)
```

- **Reads only:** `~/.claude/projects/*/*.jsonl` (indexed incrementally by byte offset, cached in `index.json`) and the status files `~/.claude/sessions/<pid>.json`. The `.key` files next to them are never read. 5C never writes into `~/.claude`.
- **One tick, one `ps`:** the service builds the overview once every 2 s and uses it for liveness, process stats, iTerm2 tab sync and notifications.
- **Tab sync** (`fivec/tabsync.py`) only touches tabs that 5C started (with the profile "5C"). It calls `osascript` only when something changed, otherwise at most every 10 s, because one sync costs about 280 ms.
- **Notifications** (`fivec/mitteilung.py`) go through `open -g fivec://melden/<id>`, so they come from 5C and do not steal focus. 5C stays silent on service start, right after a session started, when the session's iTerm2 tab is in front, and for 30 s after notifying the same session. Clicking a notification is supposed to bring the session to the front; this is not verified yet.
- **Resume and focus** (`fivec/oeffnen.py`) take the working directory and command from the index, never from the URL. An atomic start lock (15 s) plus a look at the remembered TTY prevent double starts.

### Health states

| State (UI) | Condition | Tab |
|---|---|---|
| arbeitet (working) | running, `status: busy` | 🟢 |
| wartet auf Dich (waiting) | running, `status: idle` or `waiting`, or `waitingFor` set | 🟡 |
| hängt vielleicht (possibly stuck) | `busy` for over 10 min **and** no new transcript line for over 10 min | 🟠 |
| startet (starting) | `claude --resume <id>` runs, but there is no status file yet | 🔵 |
| verwaist (orphaned) | status file exists, but the process is dead or its start time does not match | |
| ruht (idle) | everything else | |

## Facts this is built on (measured 2026-10-03, Claude Code 2.1.288, iTerm2 3.7.3)

- `status` in the status file is `idle`, `busy` or `waiting`. `waitingFor` is `"permission prompt"` for a permission request and `"input needed"` for a question.
- `procStart` is UTC while `ps -o lstart` is local time. Compare them only after conversion, otherwise every session looks orphaned.
- `kill -9` leaves the status file behind, while SIGTERM removes it. Before the folder trust prompt is answered, only the `.key` file exists.
- The file mtime of transcripts is useless as "last activity" (all files can share one mtime). 5C uses the last `timestamp` inside the file.
- `claude-cli://` can neither resume nor focus a session, hence the own `fivec://` scheme.
- iTerm2 sessions can be found by `unique ID` and by `tty`. Title and badge can be set live via AppleScript without writing to Claude's TTY, but the tab color cannot be set without the Python API. Claude Code overwrites the tab title via escape sequences, which the profile "5C" blocks (`Allow Title Setting: false`).
- The system Python (`/usr/bin/python3`, 3.9) cannot run the code. App and agent use the Python that built them (`/opt/homebrew/bin/python3`). After a Python upgrade or moving the repo, run `./install.sh` again.

## API

| Call | Effect |
|---|---|
| `GET /api/sessions?stunden=48` (or `?alle=1`) | list as in `5c list --json`, including `name`, `beschreibung`, `ausgeblendet`, `projekt_ausgeblendet` |
| `PATCH /api/sessions/<id>` `{"name": …, "beschreibung": …, "ausgeblendet": true}` | sets any field; empty text or `false` clears it; stored in `meta.json` |
| `PATCH /api/projekte` `{"cwd": …, "ausgeblendet": true}` | hides or shows a project; the cwd must be in the index; stored in `projekte.json` |
| `POST /api/sessions/<id>/open` | bring to front or resume in iTerm2 |

Protection: the service binds to `127.0.0.1` only, and the `Host` header must be `127.0.0.1:4555` or `localhost:4555` (against DNS rebinding). Writing calls need the header `X-5C-Token` (delivered in the page as `<meta name="fivec-token">`, new on every start) and no foreign `Origin`. Names are limited to 60 characters on one line, descriptions to 2000. Control characters and invisible or bidirectional characters are rejected, because both end up in iTerm2 titles and badges.

## Web UI

`fivec/web/`: `index.html`, `app.css`, `app.js` (DOM and API), `logik.js` (pure functions, tested with `node --test`), `logo.svg`, `schriften/` (Geist and Geist Mono, SIL OFL, served locally). There is no build step and no runtime dependency, and nothing is loaded from external sources: the CSP is `default-src 'self'`, and tests forbid external URLs, inline styles and inserting text as HTML.

Click a name to edit it: Enter saves, Esc cancels, Cmd+Enter saves from the description. "Ausblenden" (hide) appears on hover in each row, "Projekt ausblenden" in each group header. The "N ausgeblendet" toggle shows hidden items dimmed with "Einblenden" (show). Hidden items are stored by 5C, collapsed groups by the browser.

## Development

```sh
./pruefen.sh                     # syntax, Python and JS tests; run before every commit
python3 werkzeug/mutationen.py   # mutation check: every injected bug must be caught by the tests
```

Every fix gets a test and a mutation that proves the test catches it. Tests redirect both data locations with `CLAUDE_HOME` and `FIVEC_HOME`.
