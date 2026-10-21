#!/usr/bin/env sh
# Start from any directory. Python 3.12 recommended.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.txt
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
printf '\nGuest menu: http://127.0.0.1:8000\nAdmin panel: http://127.0.0.1:8000/admin\nFirst-start admin password appears in the server output below.\n\n'
export HOST="${HOST:-127.0.0.1}"
exec .venv/bin/python backend/serve.py
