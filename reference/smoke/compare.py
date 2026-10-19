"""Smoke tests (Python side), reference only: compare R recomputations to published tables.
Run from the Assessment root after smoke_tests.R:  eval/.venv/bin/python -I reference/smoke/compare.py"""
import numpy as np
import pandas as pd

D, OUT = "JCI_data/jci.insight.176963.", "reference/smoke/out/"
norm = lambda s: s.str.replace(r"[-.]", "_", regex=True)

def compare(name, ours, pub, cols):
    m = ours.merge(pub, on="program", suffixes=("", "_pub"))
    print(f"[{name}] matched {len(m)}/{len(pub)} published programs")
    for c in cols:
        diff = (m[c] - m[f"{c}_pub"]).abs()
        print(f"   {c:9s} max|diff| = {diff.max():.3g}   (published values are rounded to 3 s.f.)")
    return m

f7a = pd.read_csv(D + "sdval_Fig7A.csv", skiprows=1).rename(
    columns={"Unnamed: 0": "program", "effect_size.eta.2": "eta2"})
f7a["program"] = norm(f7a["program"])
compare("Fig7A ANOVA", pd.read_csv(OUT + "anova_DA_group.csv"), f7a, ["eta2", "p_value"])

f6c = pd.read_csv(D + "sdval_Fig6C.csv", skiprows=1).rename(
    columns={"Unnamed: 0": "program", "effect_size": "abs_est"})
f6c["program"] = norm(f6c["program"])
t = pd.read_csv(OUT + "ttest_case_ctrl.csv")
t["abs_est"] = t["estimate"].abs()
m = compare("Fig6C t-test", t, f6c, ["abs_est", "p_value"])
# published effect_size_sign = sign(mean HC - mean JDM) (e.g. CD4T17, lower in JDM, is +1);
# rstatix estimate with ref.group = "JDM" is mean JDM - mean HC, hence the minus sign
print(f"   sign agreement (published = -sign(JDM - HC)): {(-np.sign(m['estimate']) == m['effect_size_sign']).mean():.0%}")

ours = pd.read_csv(OUT + "fgsea_Bcells_R17_Program6.csv")
pub = pd.read_csv(D + "sdt3_Supplemental_Table3.csv")
pub = pub[(pub.Type == "Bcells") & (pub.Program == "R17_Program6")]
m = ours.merge(pub, on="pathway", suffixes=("", "_pub"))
print(f"[fgsea B6] sets: ours {len(ours)}, sdt3 {len(pub)}, shared {len(m)}")
print(f"   NES Pearson r = {m.NES.corr(m.NES_pub):.4f}; max|ES diff| = {(m.ES - m.ES_pub).abs().max():.2e}")
row = m[m.pathway == "GOBP_RIBOSOME_ASSEMBLY"].iloc[0]
print(f"   GOBP_RIBOSOME_ASSEMBLY NES {row.NES:.3f} vs {row.NES_pub:.3f}; padj {row.padj:.2e} vs {row.padj_pub:.2e}")
