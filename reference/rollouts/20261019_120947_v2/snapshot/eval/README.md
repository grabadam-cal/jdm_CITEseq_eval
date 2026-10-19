# analysis-env

R + Python environment. All paths are relative to this folder.

**The environment is already built for this session; don't rebuild it.** If `python` doesn't resolve to
`.venv/bin/python`, run `source env/activate.sh`. The build steps below are for setting it up from scratch.

## Prerequisites
- macOS with Homebrew and working Xcode Command Line Tools (`xcrun --version`)
- CRAN R 4.2.3 at `/Library/Frameworks/R.framework`
- Network access (CRAN, CRAN archive, Bioconductor, PyPI)

## Build

```bash
bash env/setup.sh
```

This installs the `Brewfile` (`--no-upgrade`), restores R packages from `renv.lock`, creates `.venv` from
`env/requirements.lock.txt`, and registers the Jupyter kernel `analysis-env`. It's safe to re-run.

## Activate (each new shell)

```bash
source env/activate.sh
```

## Verify

```bash
Rscript env/check_env.R               # "All 86 R packages load."
.venv/bin/python -I env/check_env.py  # "All 23 Python modules import."
```

Start R from this folder so `.Rprofile` activates the renv library.
