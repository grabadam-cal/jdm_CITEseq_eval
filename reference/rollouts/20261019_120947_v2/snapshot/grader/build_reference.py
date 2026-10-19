"""Build reference_answer.json from the published source data (grader-only).

Usage (from the Assessment root):  eval/.venv/bin/python -I reference/grader/build_reference.py

Inputs: JCI_data/ (sdval H, Fig7A, Fig5B, sdt3), eval/data/sample_metadata.csv, reference/eval_id_map.csv.
Every reference value is derived here; see notes/SETUP.md §5 for the rationale behind each rule.
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
# GO:BP terms that define the ribosome/translation theme (Module 2; Fig 5B, Fig 7C)
RIBOSOME_RE = r"RIBOSOM|TRANSLATION|COTRANSLATIONAL|PROTEIN_TARGETING|PROTEIN_LOCALIZATION_TO_(?:MEMBRANE|ENDOPLASMIC)|NONSENSE_MEDIATED_DECAY"

# Grading versions (notes/SETUP.md §5.3, §5.6):
#   "v1" = 5 fields (6 pts); associated_programs = exact nominal set.
#   "v2" = revision 1: + downregulated_axis_theme (2 pts) and score-neutral associated_programs diagnostics.
GRADING_VERSION = "v2"


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
    # same test on patients only: programs whose association depends on the HC group
    pat = groups != "HC"
    p_pat = pd.Series({prog: stats.f_oneway(*[H.loc[pat & (groups == g), prog] for g in sorted(groups[pat].unique())]).pvalue
                       for prog in nominal})
    hc_dependent = list(p_pat.index[p_pat >= ALPHA])
    cell_types = sorted({x.split("_")[0] for x in core})
    assert cell_types == sorted({x.split("_")[0] for x in nominal}) and len(cell_types) == 6

    # opposing axes: up-axis (IFN hub) programs higher in TNJDM than HC; down-axis programs lower
    means = H.groupby(groups).mean()
    up = [x for x in nominal if module.get(x) in UP_MODULES]
    down = [x for x in nominal if module.get(x) in DOWN_MODULES]
    assert all(means.loc["TNJDM", x] > means.loc["HC", x] for x in up)
    assert all(means.loc["TNJDM", x] < means.loc["HC", x] for x in down)
    axes_r = float(H.corr().loc[up, down].values.mean())

    # down-axis theme = ribosome/translation: Module 2's module-level enrichment (Fig 5B), and the most frequent
    # top fgsea term class among the down-axis programs (sdt3, NES > 0)
    f5b = pd.read_csv(f"{JCI}sdval_Fig5B.csv", skiprows=1)
    assert f5b[f5b.module == "Module_2"].gene_set.str.contains(RIBOSOME_RE).all()
    fg = pd.read_csv(f"{JCI}sdt3_Supplemental_Table3.csv", usecols=["pathway", "padj", "NES", "Type", "Program"])
    fg["prog"] = norm(fg.Type + "_" + fg.Program)
    top = fg[fg.prog.isin(down) & (fg.NES > 0)].sort_values("padj").groupby("prog").pathway.first()
    top_class = top.where(~top.str.contains(RIBOSOME_RE), "ribosome_translation")
    assert top_class.value_counts().idxmax() == "ribosome_translation", top_class.value_counts()

    ev = lambda xs: sorted(to_eval[x] for x in xs)
    answer = {
        "disease_activity_architecture": "multi_population_coordinated_opposing_axes",
        "associated_programs": {"core": ev(nominal), "optional": []},
        "upregulated_axis_theme": "type_I_interferon_response",
        "downregulated_axis_theme": "ribosome_translation_protein_targeting",
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
        "downregulated_axis_theme": {"type": "categorical", "points": 2.0,
                                     "partial": {"stress_response_cell_death": 0.25}},
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
    # score-neutral diagnostics for associated_programs: recall on subsets of the reference set (notes/SETUP.md §5.6)
    by_module = {f"module_M{m}": ev(x for x in nominal if module.get(x) == m)
                 for m in sorted({module.get(x) for x in nominal})}
    diagnostics = {"associated_programs": {
        **by_module,
        "up_axis": ev(x for x in nominal if means.loc["TNJDM", x] > means.loc["HC", x]),
        "down_axis": ev(x for x in nominal if means.loc["TNJDM", x] < means.loc["HC", x]),
        "hc_dependent": ev(hc_dependent),
    }}
    provenance = {
        "source": "JCI_data/ sdval H (per-sample program scores), Fig7A (73-node filtered network), sdt3 (module labels)",
        "association": f"one-way ANOVA by DA_group; nominal p<{ALPHA}: {len(nominal)} programs; BH q<{ALPHA}: {len(core)}",
        "grading_version": GRADING_VERSION + " (exact nominal set; + downregulated_axis_theme, diagnostics)",
        "cell_types": cell_types,
        "axes": f"up = module-1 DA programs ({len(up)}), down = module-2/5 DA programs ({len(down)}); "
                f"mean cross-axis Pearson r = {axes_r:.3f}",
        "theme": "module-1 theme from fgsea GO:BP (sdt3, msigdbr 7.4.1) and Fig 5B / 6A (type I IFN response)",
        "down_theme": f"Module 2 enrichment (Fig 5B) = ribosome/translation; top fgsea term class per down program: "
                      f"{top_class.value_counts().to_dict()}",
        "hc_dependent": f"nominal programs with patients-only ANOVA p >= {ALPHA}: {len(hc_dependent)}",
        "inference_strength": "exploratory, hypothesis-generating screen (27 samples); validated in independent cohort (Fig 8)",
    }
    ref = {"description": "Reference answer + scoring rules. Grader-only: never copy into eval/. "
                          "Generated by reference/grader/build_reference.py.",
           "answer": answer, "rules": rules, "hard_fail": hard_fail, "diagnostics": diagnostics,
           "provenance": provenance}
    OUT.write_text(json.dumps(ref, indent=2) + "\n")
    # frozen per-version copy, selected by GRADER_VERSION in run_rollout.sh
    (OUT.parent / "versions" / f"reference_answer_{GRADING_VERSION}.json").write_text(json.dumps(ref, indent=2) + "\n")
    print(json.dumps(answer, indent=1))
    print("\nprovenance:", json.dumps(provenance, indent=1))


if __name__ == "__main__":
    main()
