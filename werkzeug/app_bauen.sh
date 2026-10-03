#!/bin/sh
# Baut 5C.app (AppleScript-Applet) und registriert das Schema fivec://.
#   werkzeug/app_bauen.sh [Zielordner]      Standard: ~/Applications
# Die App ruft bin/5c mit einem festen Python auf: Ihr PATH ist minimal, und das
# System-Python (/usr/bin/python3, 3.9) kann den Code nicht ausführen.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ZIEL="${1:-$HOME/Applications}"
PY="$(command -v python3)"
APP="$ZIEL/5C.app"
PLIST="$APP/Contents/Info.plist"
BUDDY=/usr/libexec/PlistBuddy

"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "python3 ab 3.10 nötig: $PY"; exit 1; }

# AppleScript-Zeichenkette: Backslash und Anführungszeichen maskieren.
as_text() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
PY_AS="$(as_text "$PY")"
FIVEC_AS="$(as_text "$REPO/bin/5c")"

QUELLE="$(mktemp -t 5c-app).applescript"
cat > "$QUELLE" <<EOF
on open location theURL
	try
		set antwort to do shell script quoted form of "$PY_AS" & " " & quoted form of "$FIVEC_AS" & " open-url " & quoted form of theURL
	on error fehler
		set antwort to fehler
	end try
	if antwort is "" then return
	set teile to paragraphs of antwort
	if (count of teile) is 4 and item 1 of teile is "5C-MELDUNG" then
		display notification (item 4 of teile) with title (item 2 of teile) subtitle (item 3 of teile) sound name "Glass"
	else
		display notification antwort with title "5C"
	end if
end open location

-- Doppelklick auf die App oder Klick auf eine ihrer Mitteilungen: die zuletzt gemeldete
-- Session nach vorn (fivec/mitteilung.py), sonst die Übersicht. Läuft die App beim Klick
-- noch, schickt macOS reopen statt run.
on reopen
	klick()
end reopen

on run
	klick()
end run

on klick()
	try
		set antwort to do shell script quoted form of "$PY_AS" & " " & quoted form of "$FIVEC_AS" & " klick"
	on error fehler
		display notification fehler with title "5C"
		return
	end try
	if antwort is "seite" then do shell script "open http://127.0.0.1:4555/"
end klick
EOF

mkdir -p "$ZIEL"
rm -rf "$APP"
osacompile -o "$APP" "$QUELLE"
rm -f "$QUELLE"

$BUDDY -c "Set :CFBundleIdentifier dev.fivec.cockpit" "$PLIST" 2>/dev/null || $BUDDY -c "Add :CFBundleIdentifier string dev.fivec.cockpit" "$PLIST"
$BUDDY -c "Add :CFBundleName string 5C" "$PLIST" 2>/dev/null || $BUDDY -c "Set :CFBundleName 5C" "$PLIST"
$BUDDY -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null || $BUDDY -c "Set :LSUIElement true" "$PLIST"
GRUND="5C holt Deine Claude-Code-Sessions in iTerm2 nach vorn und setzt sie dort fort."
$BUDDY -c "Set :NSAppleEventsUsageDescription $GRUND" "$PLIST" 2>/dev/null || $BUDDY -c "Add :NSAppleEventsUsageDescription string $GRUND" "$PLIST"
$BUDDY -c "Delete :CFBundleURLTypes" "$PLIST" 2>/dev/null || true
$BUDDY -c "Add :CFBundleURLTypes array" "$PLIST"
$BUDDY -c "Add :CFBundleURLTypes:0 dict" "$PLIST"
$BUDDY -c "Add :CFBundleURLTypes:0:CFBundleURLName string 5C Session" "$PLIST"
$BUDDY -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "$PLIST"
$BUDDY -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string fivec" "$PLIST"

# Nach den Plist-Änderungen neu signieren (ad hoc), sonst verweigert macOS den Start.
codesign --force --sign - "$APP" >/dev/null 2>&1

/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "5C.app gebaut: $APP (fivec:// registriert, Python: $PY)"
