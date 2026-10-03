#!/bin/sh
# 5C einrichten: 5C.app (fivec://), iTerm2-Profil „5C“ und den Dienst als launchd-Agent
# (startet beim Login, startet nach einem Absturz neu). Mehrfach ausführbar.
#   ./install.sh
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
LABEL="dev.fivec.cockpit.dienst"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGS="$HOME/Library/Logs/5C"
PORT=4555
PY="$(command -v python3 || true)"

echo "5C einrichten aus $REPO"

# --- Voraussetzungen ---------------------------------------------------------
[ -n "$PY" ] && "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || { echo "Fehlt: python3 ab 3.10 (z. B. brew install python). Gefunden: ${PY:-keins}"; exit 1; }
[ -d /Applications/iTerm.app ] || { echo "Fehlt: iTerm2 (brew install --cask iterm2)"; exit 1; }
CLAUDE="$(zsh -lic 'command -v claude' 2>/dev/null | tail -1 || true)"
[ -n "$CLAUDE" ] || echo "Hinweis: claude nicht in der Login-Shell gefunden. Fortsetzen braucht es dort."

# --- Prüfkette ---------------------------------------------------------------
"$REPO/pruefen.sh" >/dev/null 2>&1 || { echo "Die Prüfkette ist rot, Abbruch: $REPO/pruefen.sh"; exit 1; }

# --- 5C.app und Profil -------------------------------------------------------
"$REPO/werkzeug/app_bauen.sh"
"$PY" -c "import sys; sys.path.insert(0, '$REPO'); from fivec import iterm; iterm.profil_sicherstellen()"
echo "iTerm2-Profil „5C“ angelegt"

# --- launchd-Agent -------------------------------------------------------------
mkdir -p "$LOGS" "$(dirname "$AGENT")"
cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$REPO/bin/5c</string>
    <string>dienst</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/dienst.log</string>
  <key>StandardErrorPath</key><string>$LOGS/dienst.log</string>
</dict>
</plist>
EOF
plutil -lint "$AGENT" >/dev/null

# Ein von Hand gestarteter Dienst hielte den Port: der Agent liefe dann in Neustarts.
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1 && ! launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo "Port $PORT ist belegt (läuft „5c dienst“ noch von Hand?). Bitte beenden und erneut ausführen."
  exit 1
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"

# --- Abnahme -------------------------------------------------------------------
i=0
until curl -fsS -o /dev/null "http://127.0.0.1:$PORT/api/sessions?stunden=1"; do
  i=$((i + 1))
  [ $i -lt 30 ] || { echo "Der Dienst antwortet nicht. Log: $LOGS/dienst.log"; exit 1; }
  sleep 0.5
done

cat <<EOF

5C ist eingerichtet.
  Übersicht:   http://127.0.0.1:$PORT/   (oder 5C.app doppelklicken)
  Links:       fivec://open/<session-id>
  Dienst-Log:  $LOGS/dienst.log
  Aufrufe:     ~/Library/Application Support/5C/5c.log

Beim ersten „Fortsetzen“ fragt macOS, ob 5C (bzw. python3 für den Dienst) iTerm steuern darf: bitte erlauben.
Abgelehnt? Systemeinstellungen > Datenschutz und Sicherheit > Automation.
EOF
