"""Build the eval CSVs (eval/data/*.csv) from the exported source CSVs in JCI_data/ (stdlib only).

Usage (from the Assessment root):  python3 -I reference/build_eval_data.py [out_dir]   (default: eval/data)

Values are copied as text (never parsed as floats), so they stay byte-identical to the source. Only headers change:
program names -> eval ids from reference/eval_id_map.csv, and neutral key columns (`sample`, `gene`).
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JCI = ROOT / "JCI_data" / "jci.insight.176963."
CELL_TYPES = ["Bcells", "CD4Tcells", "CD8Tcells", "gdT", "Myeloid", "NK"]


def read(path):
    with open(path, newline="") as fh:
        return list(csv.reader(fh))


def write(path, rows):
    with open(path, "w", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "eval" / "data"
    out.mkdir(parents=True, exist_ok=True)
    idmap = list(csv.DictReader(open(ROOT / "reference" / "eval_id_map.csv", newline="")))

    # per-sample program scores: sdval sheet H, keyed by Paper_ID (sample_id dropped)
    H = read(f"{JCI}sdval_H.csv")
    to_eval = {r["original_program"]: r["eval_program"] for r in idmap}
    assert H[0][:2] == ["sample_id", "Paper_ID"] and set(H[0][2:]) == set(to_eval)
    write(out / "sample_program_scores.csv", [["sample"] + [to_eval[c] for c in H[0][2:]]] + [r[1:] for r in H[1:]])

    # sample metadata: DA_group and case_ctrl from Fig 7B, in H's sample order
    B = read(f"{JCI}sdval_Fig7B.csv")
    assert B[0][:3] == ["Paper_ID", "DA_group", "case_ctrl"]
    labels = {r[0]: r[1:3] for r in B[1:]}
    write(out / "sample_metadata.csv", [["sample", "DA_group", "case_ctrl"]] + [[r[1]] + labels[r[1]] for r in H[1:]])

    # per-gene program scores: Supplemental Table 4, one sheet per cell type
    for ct in CELL_TYPES:
        G = read(f"{JCI}sdt4_{ct}.csv")
        cols = {r["original_marker_column"]: r["eval_marker_column"] for r in idmap if r["cell_type"] == ct}
        assert G[0][0] == "genes" and set(G[0][1:]) == set(cols)
        write(out / f"program_gene_scores_{ct}.csv", [["gene"] + [cols[c] for c in G[0][1:]]] + G[1:])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
