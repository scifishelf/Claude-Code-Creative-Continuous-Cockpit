#!/bin/sh
# Prüfkette vor jedem Commit: Syntax, dann alle Tests.
set -e
cd "$(dirname "$0")"
python3 -m compileall -q fivec bin tests
python3 -m unittest discover -s tests -t . "$@"
