#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir/backend"

if [[ ! -f .venv-unix/bin/python ]]; then
  echo 'Сначала выполните: bash setup-unix.sh' >&2
  exit 1
fi

exec .venv-unix/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
