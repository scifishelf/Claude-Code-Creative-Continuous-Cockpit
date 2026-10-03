"""Wo 5C liest und schreibt. Beide Orte lassen sich für Tests per Umgebung umlenken."""

import os
from pathlib import Path


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))


def fivec_home() -> Path:
    return Path(os.environ.get("FIVEC_HOME", Path.home() / "Library" / "Application Support" / "5C"))
