#!/bin/sh
# Prüfkette vor jedem Commit: Syntax, Python-Tests, JS-Tests der Oberfläche.
set -e
cd "$(dirname "$0")"
python3 -m compileall -q fivec bin tests
python3 -m unittest discover -s tests -t . "$@"
node --check fivec/web/app.js
node --test 'tests/js/*.test.mjs'
