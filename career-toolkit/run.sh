#!/usr/bin/env bash
# Convenience script for local runs. For a real always-on deploy, use the
# systemd service instead (see career-toolkit.service + README.md).
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "No .env found -- copy .env.example to .env and fill it in first."
  exit 1
fi

set -a
source .env
set +a

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
