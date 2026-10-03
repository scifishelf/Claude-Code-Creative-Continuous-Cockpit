"""iTerm2 per AppleScript: Session finden und nach vorn holen, Session starten.

Gemessen in P0 (docs/plans/2026-10-03-messungen-ist.md, M4 und M5):
- Sessions haben eine feste `unique ID` und ein `tty` (`/dev/ttys017`).
- `select` auf Fenster, Tab und Session plus `activate` holt sie nach vorn.
- Titel (`set name`) und Benutzervariablen (`set variable`) gehen live, ohne ins TTY
  von `claude` zu schreiben.
- Gemessen in P4: Claude Code setzt per Steuersequenz einen eigenen Tab-Titel und
  überschreibt damit `set name`. Deshalb startet 5C mit dem eigenen Profil „5C“:
  `Allow Title Setting: false` verbietet Programmen den Titel, `Title Components: 1`
  zeigt nur den Session-Namen, `Badge Text` liest die Variable `user.fivec_badge`.

Alle Werte gehen als Argumente an `osascript` (`on run argv`), nie in den Skripttext.
"""

import json
import os
import subprocess
from pathlib import Path

PROFIL = "5C"
PROFIL_DATEI = Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles" / "5c.json"
PROFIL_INHALT = {
    "Profiles": [{
        "Name": PROFIL,
        "Guid": "fivec-5c-profil",
        "Dynamic Profile Parent Name": "Default",
        "Badge Text": r"\(user.fivec_badge)",
        "Allow Title Setting": False,
        "Title Components": 1,
    }]
}


def profil_sicherstellen(datei: Path = PROFIL_DATEI) -> bool:
    """Legt das dynamische Profil an oder bringt es auf Stand. True, wenn geschrieben wurde."""
    text = json.dumps(PROFIL_INHALT, indent=2, ensure_ascii=False) + "\n"
    try:
        if datei.read_text() == text:
            return False
    except OSError:
        pass
    datei.parent.mkdir(parents=True, exist_ok=True)
    tmp = datei.with_suffix(".tmp")
    tmp.write_text(text)
    os.replace(tmp, datei)
    return True

KEINE_FREIGABE = (
    "5C darf iTerm2 noch nicht steuern. Erlaube es unter Systemeinstellungen, "
    "Datenschutz und Sicherheit, Automation."
)


class ItermFehler(RuntimeError):
    pass


def _osa(skript: str, *argumente: str, timeout: float = 20) -> str:
    try:
        aus = subprocess.run(
            ["osascript", "-", *argumente], input=skript, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ItermFehler("iTerm2 antwortet nicht") from e
    if aus.returncode != 0:
        if "-1743" in aus.stderr:
            raise ItermFehler(KEINE_FREIGABE)
        raise ItermFehler(aus.stderr.strip() or "AppleScript-Fehler")
    return aus.stdout.strip()


_FOKUSSIEREN = """
on run argv
  set uid to item 1 of argv
  set gesuchtesTty to item 2 of argv
  if application "iTerm2" is not running then return "nicht gefunden"
  tell application "iTerm2"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if (uid is not "" and unique ID of s is uid) or (gesuchtesTty is not "" and tty of s is gesuchtesTty) then
            select w
            select t
            select s
            activate
            return unique ID of s
          end if
        end repeat
      end repeat
    end repeat
  end tell
  return "nicht gefunden"
end run
"""

_STARTEN = """
on run argv
  set befehl to item 1 of argv
  set titel to item 2 of argv
  set badge to item 3 of argv
  set profil to item 4 of argv
  set warAn to application "iTerm2" is running
  tell application "iTerm2"
    activate
    set leer to missing value
    if not warAn then
      -- Beim Kaltstart öffnet iTerm2 selbst ein leeres Fenster; das schließen wir nach dem eigenen.
      repeat 50 times
        if (count of windows) > 0 then exit repeat
        delay 0.1
      end repeat
      if (count of windows) > 0 then set leer to current window
    end if
    try
      set w to (create window with profile profil)
    on error
      -- Profil noch nicht geladen (iTerm2 liest DynamicProfiles mit kurzer Verzögerung)
      delay 1
      try
        set w to (create window with profile profil)
      on error
        set w to (create window with default profile)
      end try
    end try
    if leer is not missing value then close leer
    tell current session of w
      set name to titel
      set variable named "user.fivec_badge" to badge
      write text befehl
      return (unique ID) & "|" & (tty)
    end tell
  end tell
end run
"""

_TITEL = """
on run argv
  set uid to item 1 of argv
  set titel to item 2 of argv
  if application "iTerm2" is not running then return "nicht gefunden"
  tell application "iTerm2"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if unique ID of s is uid then
            set name of s to titel
            return "ok"
          end if
        end repeat
      end repeat
    end repeat
  end tell
  return "nicht gefunden"
end run
"""


def tty_voll(tty: str | None) -> str:
    """`ps` liefert `ttys017`, iTerm2 `/dev/ttys017`."""
    if not tty:
        return ""
    return tty if tty.startswith("/dev/") else f"/dev/{tty}"


def fokussieren(unique_id: str | None = None, tty: str | None = None) -> str | None:
    """Gibt die unique ID der gefundenen Session zurück, oder None."""
    ergebnis = _osa(_FOKUSSIEREN, unique_id or "", tty_voll(tty))
    return None if ergebnis == "nicht gefunden" else ergebnis


def starten(befehl: str, titel: str, badge: str) -> tuple[str, str]:
    """Neues Fenster mit Profil 5C, Titel und Badge setzen, Befehl in der Login-Shell ausführen.
    -> (unique ID, tty)"""
    profil_sicherstellen()
    uid, _, tty = _osa(_STARTEN, befehl, titel, badge, PROFIL).partition("|")
    return uid, tty


def titel_setzen(unique_id: str, titel: str) -> bool:
    return _osa(_TITEL, unique_id, titel) == "ok"
