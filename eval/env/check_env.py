"""analysis-env — import every Python package and print versions. Run: .venv/bin/python -I env/check_env.py"""
import importlib
import sys
import warnings

MODULES = ["numpy", "pandas", "scipy", "statsmodels", "matplotlib", "seaborn", "networkx",
           "sklearn", "openpyxl", "xlrd", "igraph", "leidenalg", "jupyterlab", "ipykernel",
           "scanpy", "anndata", "numba", "decoupler", "pydeseq2", "umap", "harmonypy", "pingouin",
           "scikit_posthocs"]

print(sys.version.split()[0], sys.executable)
missing = []
for name in MODULES:
    try:
        mod = importlib.import_module(name)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            version = getattr(mod, "__version__", "?")
        print(f"  {name:16s} {version}")
    except ImportError:
        missing.append(name)
if missing:
    sys.exit(f"Missing Python modules: {', '.join(missing)}")
print(f"All {len(MODULES)} Python modules import.")
