#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir/backend"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 не найден. Установите Python с https://www.python.org/downloads/' >&2
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit('Нужен Python 3.11 или новее.')
PY

python3 -m venv .venv-unix
.venv-unix/bin/python -m pip install --upgrade pip
.venv-unix/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv-unix/bin/python -m app.train
echo 'Готово. Запустите: bash run-unix.sh'
