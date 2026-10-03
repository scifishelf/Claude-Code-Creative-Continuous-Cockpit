"""Git-Stand eines Session-Ordners: uncommittete Änderungen und letzter Commit."""

import subprocess
from pathlib import Path


def _git(cwd: str, *args: str) -> str | None:
    try:
        aus = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return aus.stdout if aus.returncode == 0 else None


def stand(cwd: str | None) -> dict:
    """`ordner_fehlt` (z. B. gelöschter Worktree), `kein_repo` oder Zahl und letzter Commit."""
    if not cwd or not Path(cwd).is_dir():
        return {"art": "ordner_fehlt"}
    status = _git(cwd, "status", "--porcelain")
    if status is None:
        return {"art": "kein_repo"}
    letzter = _git(cwd, "log", "-1", "--format=%h %s") or ""
    return {
        "art": "repo",
        "uncommittet": sum(1 for z in status.splitlines() if z.strip()),
        "letzter_commit": letzter.strip(),
    }
