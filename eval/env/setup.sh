#!/usr/bin/env bash
# analysis-env — idempotent environment rebuild. Run from anywhere:  bash env/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

R_BIN="/Library/Frameworks/R.framework/Resources/bin/Rscript"
PY_BIN="$(brew --prefix python@3.12)/bin/python3.12"

echo "== [1/4] Homebrew (Brewfile; existing formulae are not upgraded)"
brew bundle install --file=Brewfile --no-upgrade

echo "== [2/4] R project library (renv)"
"$R_BIN" --version | head -1
if [[ -f renv.lock ]]; then
  "$R_BIN" -e 'renv::restore(prompt = FALSE)'
else
  "$R_BIN" env/bootstrap_renv.R
fi

echo "== [3/4] Python venv (.venv, prompt analysis-env)"
[[ -x .venv/bin/python ]] || "$PY_BIN" -m venv --prompt analysis-env .venv
.venv/bin/python -m pip install --quiet --upgrade pip
if [[ -f env/requirements.lock.txt ]]; then
  .venv/bin/python -m pip install --quiet -r env/requirements.lock.txt
else
  .venv/bin/python -m pip install --quiet -r requirements.txt
  .venv/bin/python -m pip freeze > env/requirements.lock.txt
fi

echo "== [4/4] Jupyter kernel"
.venv/bin/python -m ipykernel install --user --name analysis-env --display-name "analysis-env (py3.12)"

echo "== Checks"
"$R_BIN" env/check_env.R
.venv/bin/python -I env/check_env.py
echo "analysis-env ready. In new shells: source env/activate.sh"
