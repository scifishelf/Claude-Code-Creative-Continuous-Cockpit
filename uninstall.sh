#!/bin/sh
# 5C entfernen: Dienst, 5C.app und iTerm2-Profil. Namen, Beschreibungen und Index
# in ~/Library/Application Support/5C bleiben, außer mit --alles.
set -e
LABEL="dev.fivec.cockpit.dienst"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Applications/5C.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -gc >/dev/null 2>&1 || true
rm -f "$HOME/Library/Application Support/iTerm2/DynamicProfiles/5c.json"

if [ "$1" = "--alles" ]; then
  rm -rf "$HOME/Library/Application Support/5C" "$HOME/Library/Logs/5C"
  echo "5C entfernt, samt Namen, Beschreibungen und Logs."
else
  echo "5C entfernt. Namen und Beschreibungen liegen weiter in ~/Library/Application Support/5C (--alles löscht sie)."
fi
