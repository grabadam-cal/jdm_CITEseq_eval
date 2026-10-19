"""Build reference_answer.json from the published source data (grader-only).

Usage (from the Assessment root):  eval/.venv/bin/python -I reference/grader/build_reference.py

Inputs: JCI_data/ (sdval H, Fig7A, sdt3), eval/data/sample_metadata.csv, reference/eval_id_map.csv.
Every reference value is derived here; see SETUP.md §5 for the rationale behind each rule.
"""
import json
from pathlib import Path

import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[2]
JCI = ROOT / "JCI_data" / "jci.insight.176963."
OUT = Path(__file__).resolve().parent / "reference_answer.json"

ALPHA = 0.05                             # nominal threshold used in the paper (hypothesis-generating screen)
UP_MODULES, DOWN_MODULES = {1}, {2, 5}   # IFN hub (up); ribosome/translation + cell death/stress (down)

# Grading version for associated_programs (SETUP.md §5.3):
#   "v1" = exact-set reference: all programs with nominal p < ALPHA, as in the paper (no optional items).
#   "v2" = threshold-tolerant revision: core = BH q < ALPHA, optional = nominal-only. Planned step-4 revision,
#          to be switched on only if a rollout shows a valid stricter analysis (e.g. BH) being penalized.
GRADING_VERSION = "v1"


def norm(s):
    return s.str.replace(r"[-.]", "_", regex=True)


def main():
    idmap = pd.read_csv(ROOT / "reference" / "eval_id_map.csv")
    to_eval = dict(zip(norm(idmap.original_program), idmap.eval_program))

    H = pd.read_csv(f"{JCI}sdval_H.csv").set_index("Paper_ID").drop(columns="sample_id")
    H.columns = norm(pd.Series(H.columns))
    meta = pd.read_csv(ROOT / "eval" / "data" / "sample_metadata.csv").set_index("sample").loc[H.index]
    network = list(norm(pd.read_csv(f"{JCI}sdval_Fig7A.csv", skiprows=1).iloc[:, 0]))  # 73 filtered nodes
    s3 = pd.read_csv(f"{JCI}sdt3_Supplemental_Table3.csv", usecols=["Type", "Program", "module"]).drop_duplicates()
    module = dict(zip(norm(s3.Type + "_" + s3.Program), s3.module))

    # disease-activity association: one-way ANOVA of each program's per-sample score by DA_group
    groups = meta.DA_group
    p = pd.Series({prog: stats.f_oneway(*[H.loc[groups == g, prog] for g in sorted(groups.unique())]).pvalue
                   for prog in network})
    q = pd.Series(multipletests(p, method="fdr_bh")[1], index=p.index)
    nominal, core = p.index[p < ALPHA], p.index[q < ALPHA]
    cell_types = sorted({x.split("_")[0] for x in core})
    assert cell_types == sorted({x.split("_")[0] for x in nominal}) and len(cell_types) == 6

    # opposing axes: up-axis (IFN hub) programs higher in TNJDM than HC; down-axis programs lower
    means = H.groupby(groups).mean()
    up = [x for x in nominal if module.get(x) in UP_MODULES]
    down = [x for x in nominal if module.get(x) in DOWN_MODULES]
    assert all(means.loc["TNJDM", x] > means.loc["HC", x] for x in up)
    assert all(means.loc["TNJDM", x] < means.loc["HC", x] for x in down)
    axes_r = float(H.corr().loc[up, down].values.mean())

    ev = lambda xs: sorted(to_eval[x] for x in xs)
    answer = {
        "disease_activity_architecture": "multi_population_coordinated_opposing_axes",
        "associated_programs": ({"core": ev(nominal), "optional": []} if GRADING_VERSION == "v1" else
                                {"core": ev(core), "optional": ev(set(nominal) - set(core))}),
        "upregulated_axis_theme": "type_I_interferon_response",
        "axes_correlation": round(axes_r, 2),
        "inference_strength": "hypothesis_generating_candidates",
    }
    rules = {
        "disease_activity_architecture": {"type": "categorical", "points": 2.0,
                                          "partial": {"multi_population_coordinated_single_axis": 0.5,
                                                      "multi_population_independent": 0.125}},
        "associated_programs": {"type": "core_set", "points": 1.0, "min_recall": 0.8, "min_precision": 0.8},
        "upregulated_axis_theme": {"type": "categorical", "points": 1.0,
                                   "partial": {"inflammatory_cytokine_signaling": 0.25}},
        "axes_correlation": {"type": "numeric", "points": 1.0, "abs_tol": 0.20, "require_sign": -1},
        "inference_strength": {"type": "categorical", "points": 1.0,
                               "partial": {"confirmatory_association": 0.25}},
    }
    hard_fail = [
        {"reason": "single dominant population claimed (associated programs span all six cell types)",
         "when": [{"field": "disease_activity_architecture", "in": ["single_population_dominant"]}]},
        {"reason": "mechanistic/causal driver claimed from correlational, hypothesis-generating data",
         "when": [{"field": "inference_strength", "in": ["mechanistic_driver_identified"]}]},
    ]
    provenance = {
        "source": "JCI_data/ sdval H (per-sample program scores), Fig7A (73-node filtered network), sdt3 (module labels)",
        "association": f"one-way ANOVA by DA_group; nominal p<{ALPHA}: {len(nominal)} programs; BH q<{ALPHA}: {len(core)}",
        "grading_version": GRADING_VERSION + (" (exact nominal set)" if GRADING_VERSION == "v1"
                                              else " (core = BH, optional = nominal-only)"),
        "cell_types": cell_types,
        "axes": f"up = module-1 DA programs ({len(up)}), down = module-2/5 DA programs ({len(down)}); "
                f"mean cross-axis Pearson r = {axes_r:.3f}",
        "theme": "module-1 theme from fgsea GO:BP (sdt3, msigdbr 7.4.1) and Fig 5B / 6A (type I IFN response)",
        "inference_strength": "exploratory, hypothesis-generating screen (27 samples); validated in independent cohort (Fig 8)",
    }
    ref = {"description": "Reference answer + scoring rules. Grader-only: never copy into eval/. "
                          "Generated by reference/grader/build_reference.py.",
           "answer": answer, "rules": rules, "hard_fail": hard_fail, "provenance": provenance}
    OUT.write_text(json.dumps(ref, indent=2) + "\n")
    print(json.dumps(answer, indent=1))
    print("\nprovenance:", json.dumps(provenance, indent=1))


if __name__ == "__main__":
    main()
