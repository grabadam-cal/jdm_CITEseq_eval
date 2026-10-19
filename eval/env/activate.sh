# analysis-env — usage:  source env/activate.sh   (from anywhere)
_ENV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export ANALYSIS_ROOT="$_ENV_ROOT"
export RENV_PROJECT="$_ENV_ROOT"
export PATH="/Library/Frameworks/R.framework/Resources/bin:$PATH"
export RETICULATE_PYTHON="$_ENV_ROOT/.venv/bin/python"
source "$_ENV_ROOT/.venv/bin/activate"
cd "$_ENV_ROOT"
echo "analysis-env active: $(R --version | head -1) | $(python --version)"
