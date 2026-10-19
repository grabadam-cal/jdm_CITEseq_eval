# Reference notes: eval built from Rabadam et al., JCI Insight 2024

- **Paper:** *Coordinated immune dysregulation in juvenile dermatomyositis revealed by single-cell genomics*,
  JCI Insight 2024;9(12):e176963 (`JCI_data/Rabadam_JCI_2024.pdf`).
- **Paper code:** github.com/grabadam-cal/jdm-DECIPHER-2024 (commit `1ba1398`).
- **Brief:** `[External] MOTS_L2 Takehome.docx`.

**This file contains paper context and grading details. It is kept outside `eval/`, and evaluation sessions should
stay scoped to `eval/`.**

## 1. Layout

```
LatchBio_Assessment_2026/
├── eval/        what the agent sees: task.txt, eval_answer.json, data/, README.md (build only), environment files
├── reference/   grader-only: grader/, rollouts/, eval_id_map.csv, functions/ (paper code), smoke/, converters, logs/
├── JCI_data/    paper PDF, original workbooks and exported CSVs (published results)
└── SETUP.md     this file
```

**Data is not in the git repo** (only the paper PDF is). `.gitignore` excludes `JCI_data/*` except the PDF, and
`eval/data/*.csv`. To rebuild: download the Supporting Data Values and Supplemental Tables 3/4 from the article page
into `JCI_data/`, run `reference/xlsx_to_csv.py` (sdval, sdt3) and `reference/export_sdt4.R` (sdt4), then
`python3 -I reference/build_eval_data.py` to write `eval/data/*.csv` (text copies with eval IDs from
`reference/eval_id_map.csv`; verified byte-identical to the originals).

## 2. Eval inputs (`eval/data/`)

| Eval file | Source | Notes |
|---|---|---|
| `sample_program_scores.csv` | sdval sheet **H**: per-sample mean NMF program scores, 27 samples × 89 programs | `cor(H)` reproduces Fig 4B (max \|Δ\| 5e-6) |
| `sample_metadata.csv` | `sample`, `DA_group` (HC 5 / Inactive 6 / Active 7 / TNJDM 9), `case_ctrl`, from Fig 7B | the only table mapping samples to groups |
| `program_gene_scores_<CellType>.csv` (×6) | Supplemental Table 4 (sdt4): signed marker-gene scores per program (the ranked lists fed to fgsea) | not raw NMF loadings |
| `vocabulary.json` | written for the eval | answer tokens + conventions (§5.2) |

To remove paper context from the inputs:
- **Neutral names:** files renamed, and the sample key is `sample`.
- **Neutral program IDs:** `<CellType>_P<nn>`, renumbered within each cell type, which hides rank K and the gaps
  left by dropped programs. Gene-score columns are `P<nn>`.
- **Mapping:** `reference/eval_id_map.csv` maps eval IDs back to the paper's names (e.g. `NK_P11` → `NK.R13_Program13`).
- **Values:** copied as text, so they are byte-identical to the source.
- **Paper code:** its DECIPHER-seq functions stay in `reference/functions/`, because they would reveal the method.

Accepted remaining hints in `eval/`:
- Package names in the environment files (e.g. `wTO`, `leidenalg`, `fgsea`), diluted by a generic single-cell
  toolkit.
- `JDM`/`HC` in sample labels.

## 3. Environment (`eval/`, named `analysis-env`)

```bash
cd eval && bash env/setup.sh && source env/activate.sh   # idempotent build; then activate in each new shell
Rscript env/check_env.R                 # 86 R packages load
.venv/bin/python -I env/check_env.py    # 23 Python modules import
```

| Layer | Spec |
|---|---|
| R | CRAN R 4.2.3 (the paper's version), renv 1.0.9, Bioconductor 3.16; `renv.lock` (411 packages). msigdbr pinned to **7.4.1** |
| Python | 3.12.6 `.venv`, exact pins in `env/requirements.lock.txt` (numpy 2.3.5, numba 0.62.1/llvmlite 0.45.1 pinned for Intel-Mac wheels) |
| Homebrew | `python@3.12`, `pkgconf`, `gcc`, `gmp`, `glpk` (`Brewfile`, installed with `--no-upgrade`) |
| Packages | the paper's workflow packages plus a generic single-cell/stats toolkit (Seurat, scran/scater, limma/edgeR/DESeq2, GSVA/AUCell/decoupleR; scanpy, decoupler, pydeseq2, …) |

Machine caveats (Intel macOS 26.5.1):
- **Homebrew Tier 3:** no bottles, and Xcode 13.4 is too old for source builds, so the optional graphics libraries
  are commented out in the `Brewfile`. They aren't needed, because all R packages are pre-built.
- **Unlinked formulae:** `python@3.12` and `gcc` are unlinked; the project calls `/usr/local/opt/python@3.12`
  directly.
- **Library location:** the renv library lives under `~/Library/Caches/org.R-project.R/R/renv/library/eval-*/`.
- **Seurat:** loads only with the eval library's Dec-2023 `spatstat` binaries. Seurat in the system R library is
  likely broken; that library wasn't touched.

## 4. Verified facts the reference relies on

- **Reproduction:** from `H` + `DA_group`, a one-way ANOVA per program reproduces the published Fig 7A η² and p exactly
  (73/73 programs), and the case-control t-test reproduces Fig 6C. Check with `reference/smoke/` (run from the root:
  `Rscript reference/smoke/smoke_tests.R && eval/.venv/bin/python -I reference/smoke/compare.py`).
- **Program counts are nested, 89 ⊃ 78 ⊃ 73:**
  - **89** = all programs (`H`, unfiltered).
  - **78** = programs in modules that survived network filtering (sdt3; its `module` column is the pre-node-filter label).
  - **73** = the filtered network (Fig 7A). **The eval uses these 73.**
  - The paper text's "76" matches no table.
- **Association threshold:** nominal p < 0.05 (the paper's choice). There is no cross-program BH, because the analysis
  is hypothesis-generating (candidates were validated in an independent cohort, Fig 8), and the pipeline's
  corrections apply to other test families (fgsea FDR, permutation tests). Result: 26/73 programs at nominal p and
  15 at BH, with all 6 cell types under both.
- **Axes:**
  - The 11 associated IFN-hub programs (Module 1) are all higher in TNJDM than HC.
  - The 11 associated ribosome/translation and cell-death programs (Modules 2/5) are all lower.
  - Mean cross-axis Pearson r = −0.41; within-IFN r̄ = 0.61.
- **Themes:** fgsea on the sdt4 scores with msigdbr 7.4.1 reproduces Supplemental Table 3 exactly (identical ES;
  7.5.1 does not). Module 1 = type I IFN response.

## 5. Eval design: task, answer schema, grader, rollouts

Take-home brief: `[External] MOTS_L2 Takehome.docx`. It asks for a prompt, data, a reference answer with acceptable
uncertainty, an executable Python grader, rollouts and grading results, plus one justified revision.

### 5.1 Scope
The eval is scaled to the brief's 2-hour design → build → test → refine cycle: **one idea, 5 answer fields** (the brief's
example has 5; scBench evals 5–7). The idea: *is disease activity associated with one immune population or with
coordinated changes across populations, and what are the coordinated programs?* It needs a quantitative comparison
(which programs are associated, and how the up and down programs co-vary) and a scientific interpretation (what the
programs are, and how strong a claim the data support).

Cut during scoping (12 → 8 → 5 fields), each a separate finding or redundant:
- **Persistence in inactive disease:** a separate finding (Fig 6, remission), with the most complex reference definition.
- **Down-axis themes and the peak group:** already covered by the architecture call plus the negative cross-axis correlation.
- **Number of cell types:** derived from the program list (always 6).
- **Axis-relationship token:** given by the sign of the correlation.
- **Strongest program and its η²:** a near-tie (γδT8 0.631 vs γδT4 0.612) that needed special handling.
- **B–T extrafollicular coordination:** dropped to keep it simple (B9~CD4T10 r = 0.48, B14~CD4T1 r = 0.49,
  PRDM1/GATA3/CCR4 top-ranked, CXCR5/IL21 absent).
- **A treatment/design-confounder field:** treatment isn't in the metadata, and Active-on-treatment is the clinical
  point. Repeat visits mostly span different DA groups.

### 5.2 What the agent sees (`eval/`)
- `task.txt`: your prompt (context, question, `<EVAL_ANSWER>` schema). It names input files only. There is no
  method, threshold or "hypothesis-generating" framing; the claim-strength judgment is graded instead.
- `eval_answer.json`: the answer keys (5 in v1, 6 in v2) with type placeholders.
- `data/vocabulary.json`: token lists (`disease_activity_architecture`, `upregulated_axis_theme`, v2:
  `downregulated_axis_theme`, `inference_strength`), each with distractors, plus neutral `answer_conventions` for every field. `DA_group` labels
  are used as-is, by design: they are clinically meaningful and are not expanded.
- Wording: the data are *gene-expression programs*, while the question asks about *biological activity programs*.
  Bridging the two (functional annotation of `program_gene_scores_*`) is ungraded work the agent has to work out
  for itself.
- Question: "associated with changes in a single immune cell population, or with coordinated changes across
  populations" ("driven by" was dropped as a causal claim).

### 5.3 Answer fields, reference and scoring (v2: 6 fields, 8 points; v1: 5 fields, 6 points)
Reference values are **generated** by `reference/grader/build_reference.py` from `JCI_data/` (H, Fig7A, Fig5B, sdt3),
so they are reproducible. Program ids are eval ids (`reference/eval_id_map.csv`); module numbers are never used.

`reference_answer.json` is current: `GRADING_VERSION = "v2"` (§5.6); all tests pass (§5.4). v1 is at tag `v1-rollout1`.

| # | Field | Reference | Rule (pts) |
|---|---|---|---|
| 1 | `disease_activity_architecture` | `multi_population_coordinated_opposing_axes` | categorical (2); `…coordinated_single_axis` 1.0 pt, `multi_population_independent` 0.25 pt |
| 2 | `associated_programs` | the 26 programs with nominal p < 0.05 (one-way ANOVA by DA_group, 73-node network) | set (1): recall ≥ 0.8, precision ≥ 0.8 against those 26 |
| 3 | `upregulated_axis_theme` | `type_I_interferon_response` | categorical (1); `inflammatory_cytokine_signaling` 0.25 |
| 3b | `downregulated_axis_theme` (v2) | `ribosome_translation_protein_targeting` | categorical (2); `stress_response_cell_death` 0.5 pt |
| 4 | `axes_correlation` | −0.41 (mean Pearson r between up-axis and down-axis programs; within-IFN r̄ = 0.61) | numeric (1): ±0.20, must be negative; `null` scores 0 |
| 5 | `inference_strength` | `hypothesis_generating_candidates` | categorical (1); `confirmatory_association` 0.25 |

Hard fails (total → 0): `disease_activity_architecture = single_population_dominant`;
`inference_strength = mechanistic_driver_identified`.

Rules behind the reference:
- **Association threshold** (§4): nominal p < 0.05, as in the paper (hypothesis-generating; no cross-program BH).
- **Single-population hard fail and stricter thresholds.** All 6 cell types have associated programs under every
  reasonable analysis (nominal or BH; ANOVA or Kruskal–Wallis; 73 or 89 programs). The count drops to 1–2 only
  under Bonferroni, where just γδT programs (and sometimes one NK program) survive. The hard fail is **kept on
  purpose**: the Bonferroni survivors sit on opposite axes, and the co-variation across cell types holds regardless
  of per-program significance. So "single population" is a misreading, not just a stricter threshold.
- **Directionality** is captured by the architecture call (opposing axes), the up-axis theme, and the sign of the
  cross-axis correlation, not by a sign for the 4-level factor.

The revision made after rollout 1 is in §5.6. (A threshold-tolerant "core = BH / optional = nominal" v2, planned
before the rollout, is **dropped**; see §5.6.)

**Grading concepts: first pass (minimum needed to explain the grader).**

| Term | Definition |
|---|---|
| **Reference answer** | The canonical value for each answer field, derived from the published data by `build_reference.py`. |
| **Field test** | The rule that scores one field against the reference. Fields are scored independently and summed (v2: 8 points). |
| **Pass rule for the program list** | The list passes if it contains enough of the reference programs (**recall**) and few programs outside them (**precision**). All-or-nothing. |
| **Hard fail** | A scientifically disqualifying claim that sets the total to 0. |

**Additional terms (for refining in the live session).**

| Term | Definition |
|---|---|
| recall | \|answer ∩ reference\| / \|reference\| |
| precision | \|answer ∩ reference\| / \|answer\| |
| min_recall / min_precision | thresholds; both must be met |
| partial | fraction of a categorical field's points for a named near-miss token |
| tolerance (`abs_tol`), `require_sign` | numeric field: maximum \|given − reference\| for full points; required direction |
| brief test / extra test | `test_answers/` (correct must score 100%, plausible-incorrect < 50%) / `extra_tests/` (grading-assumption checks) |

Field 2 scoring examples:

| Agent's list | Field 2 (reference = 26 nominal) |
|---|---|
| all 26 nominal programs (paper-style) | recall 1.00, precision 1.00 → 1 |
| the 15 BH programs (double correction) | recall 0.58 → **0** |
| 21 of the 26 nominal | recall 0.81 → 1 |
| 26 nominal + 7 non-associated | precision 26/33 = 0.79 → **0** |
| IFN-axis programs only (misses the down axis) | recall ≤ 0.42 → **0** |

The 0.8 thresholds tolerate small differences in test choice but not a whole missing axis. 11 of the 26 nominal
programs are on the down axis.

How to refine a test:
1. Change the criterion or threshold in `build_reference.py` (constants at the top: `ALPHA`, `GRADING_VERSION`; the
   `rules` dict). Bump `GRADING_VERSION` for any change that alters scores.
2. Regenerate with `eval/.venv/bin/python -I reference/grader/build_reference.py`.
3. Re-run `bash reference/grader/test_grader.sh` (with `EXTRA=1` if the change touches thresholds or hard fails).
4. Re-grade existing rollouts without re-running them: `eval/.venv/bin/python -I reference/rollouts/render_trace.py
   reference/rollouts/<run>`.
5. Record the change and the reason here (the take-home asks for one justified revision).

### 5.4 Grader and tests (`reference/grader/`)
`build_reference.py` writes `reference_answer.json` (answer + rules + hard fails + provenance). It asserts its own
invariants: 6 cell types under both thresholds, and the axis directions. `grade.py` scores an answer against it.

Grader flow (`grade.py`):
```
answer = last <EVAL_ANSWER> block (JSON)
for each field: score = points × score_field(answer, reference, rule)
    categorical: exact = 1, named near-miss = partial, else 0
    numeric:     within abs_tol (and right sign) = 1, else 0
    core_set:    recall ≥ min_recall and precision ≥ min_precision = 1, else 0
total = 0 if any hard fail else sum(scores)
```

- **Brief test** (`bash reference/grader/test_grader.sh`): one correct and one plausible but scientifically incorrect
  answer. It asserts correct = 100% and plausible-incorrect < 50%.

  | Test answer | What it represents | v1 | v2 |
  |---|---|---|---|
  | `correct.txt` | **Correct.** Matches the paper's analysis: opposing-axes architecture; all 26 nominal programs; type I IFN up-axis; axes r = −0.38; `hypothesis_generating_candidates`; v2: ribosome/translation down-axis. | 6/6 | 8/8 (100%) |
  | `plausible_incorrect.txt` | **Plausible but scientifically incorrect: "one shared inflammatory signature".** Finds the IFN co-variation across cell types but treats it as a single axis, labels it from top genes instead of testing enrichment, misses the opposing down axis, and over-claims. Every claim is reasonable on its own, which is what makes it the hard negative. v2: down axis `no_coherent_theme`. | 1.5/6 (25%) | 1.5/8 (19%) |

  Result: **PASS** under v1 and v2 (v2: 100% vs 19%). Extra tests also match.

  Field by field for `plausible_incorrect`:

  | Field | Answer given (and the reasoning error it reflects) | Score |
  |---|---|---|
  | `disease_activity_architecture` | `multi_population_coordinated_single_axis`: sees the IFN co-variation across cell types but misses the opposing axis | 1/2 |
  | `associated_programs` | 9 IFN-axis programs + 3 non-associated (Myeloid_P02, CD4Tcells_P05, Bcells_P03); no down-axis programs | 0/1 |
  | `upregulated_axis_theme` | `inflammatory_cytokine_signaling`: labelled from top-loading genes, without enrichment | 0.25/1 |
  | `downregulated_axis_theme` (v2) | `no_coherent_theme`: top genes only, no enrichment or module aggregation | 0/2 |
  | `axes_correlation` | −0.05: never tests how the up and down programs relate | 0/1 |
  | `inference_strength` | `confirmatory_association`: over-claims from 27 samples | 0.25/1 |

- **Extra tests** (`reference/grader/extra_tests/`, run with `EXTRA=1 bash reference/grader/test_grader.sh`). These
  check grading assumptions:

  | Test answer | What it checks | v1 | v2 |
  |---|---|---|---|
  | `correct_strict.txt` | BH on top of a hypothesis-generating screen: the 15 BH programs only, axes r = −0.52; otherwise as `correct`. Penalized on field 2 **by design** (§4: no cross-program BH). | 5/6 | 7/8 |
  | `hard_fail.txt` | `correct` plus disqualifying claims (`single_population_dominant`; `mechanistic_driver_identified`). Hard fails override field credit. | 0/6 | 0/8 |

### 5.5 Rollouts (`reference/rollouts/`)
```bash
MAX_BUDGET_USD=<cap> bash reference/rollouts/run_rollout.sh <label>        # model + context are set in the script
eval/.venv/bin/python -I reference/rollouts/render_trace.py reference/rollouts/<run> [--reference PATH]   # re-grade
```
Config at the top of `run_rollout.sh`: `MODEL="claude-sonnet-5"` (Sonnet 5.0) and `MAX_CONTEXT="200k"` (auto-compact
window, `--autocompact`). `meta.json` records the resolved model, the window and `n_compactions`. Recaps come
from the session transcript, since the stream may carry only a compaction marker (shown live as a marker line). Ctrl-C stops the agent but still restores `eval/` and saves
and grades the partial run.

Run folder (nothing is ever overwritten; re-grades add files):

| File | Contents |
|---|---|
| `prompt.txt`, `trace.jsonl`, `trace.md`, `final.txt` | exact prompt; raw stream (every message, tool call, result); readable trace; final message |
| `session_transcript.jsonl`, `compactions.md` | the agent's own Claude Code transcript; each context compaction's recap, verbatim and in order (also inlined in `trace.md`) |
| `answer.json`, `grade.json` | parsed `<EVAL_ANSWER>`; grade **at run time** (against the snapshot) |
| `grades/` | every grading of this run: `<version>_<timestamp>.json` + `history.tsv`. A re-grade under a new grading version adds a file here and leaves `grade.json` unchanged |
| `snapshot/` | frozen copies of the eval inputs (task, answer format, README, vocabulary) and the grader (`reference_answer.json`, `grade.py`, `build_reference.py`) used for the run |
| `outputs/` | files the agent created or modified in `eval/` |
| `audit.txt`, `settings.json`, `meta.json` | out-of-scope access check; deny rules used; CLI, model, turns, cost, score, memory counts, SHA-256 of inputs |
| `quarantined_memory_*/` | only if auto-memory existed before, or was written during, the run |

**Containment (design decision).** The agent must not see answers, the paper or this design discussion. It needs
Bash and runs unattended (`bypassPermissions`), so containment has four layers:
1. **Scope:** working directory `eval/`, and the prompt names only `eval/` files. No `CLAUDE.md` loads.
2. **Deny rules** (`rollout_settings.json`, 18 rules): Read, Edit and Write are denied for `JCI_data/`, `reference/`,
   `SETUP.md`, the `.docx`, `~/.claude/projects/**` (transcripts, including this design conversation) and
   `~/.claude/plans/**`. The file is kept in `reference/`, not `eval/.claude/`, so the deny list itself doesn't point
   to the answers.
3. **Memory quarantine:** auto-memory for `eval/` (`~/.claude/projects/<eval>/memory/`) is moved into the run folder
   before and after each run. It's never deleted; memory written during a run is flagged in `audit.txt`.
4. **Audit (backstop):** deny rules don't cover Bash (`cat ../SETUP.md`). `audit.txt` flags tool calls matching the
   paper, the reference files, `../` and `.claude/projects`. **A flagged rollout is not scored as clean.**

Rejected: `--restricted` (removes Bash, so the task is impossible); `--bare` (needs `ANTHROPIC_API_KEY`); moving files
outside the project.

**Verified:**
- **Deny rules:** two Haiku probe runs ($0.05). Read of `SETUP.md`, `reference_answer.json`, `JCI_data/`, the
  transcript, and Read/Edit of `grade.py` were all denied; `eval/` files were allowed. Grep and Glob don't exist in
  CLI 2.1.292, so searching goes through Bash, which the audit covers.
- **Pipeline:** stub-`claude` runs (no API calls). A concurrent start is refused; two runs get separate folders;
  `eval/` is byte-identical after the runs; a re-grade under another reference adds `grades/<version>_*.json`
  and leaves `grade.json` unchanged; memory is quarantined before and after the run and flagged.
- **Rollout 1** (`20261018_184208_run`, v1): claude-sonnet-5, 20 turns, 19 tool calls, 4.3 min, $0.49, no compaction,
  audit clean. Score 5/6 (fails field 2). The agent wrote no files (inline `python -c`), so `outputs/` is empty and its
  intermediate results are in the trace's tool results.

### 5.6 Revision 1: grader v2 (implemented)
v1 and rollout 1 are frozen at tag `v1-rollout1`; v2 at tag `v2-grader`.

**Observations (rollout 1, v1 score 5/6).**
| Error | Evidence | Caught by v1? |
|---|---|---|
| HCs excluded; DA_group pooled as ordinal (Inactive < Active < TNJDM), Spearman + BH | reported set = exactly that pipeline's 13 programs | only in combination: field 2 recall 0.50. HC exclusion alone passes (patients-only ANOVA: recall 0.88, precision 0.92) |
| programs annotated from top 5–10 genes; no GSEA, no module aggregation | down axis called "heterogeneous, no coherent theme" | no: up-axis IFN is visible in top genes; down axis not graded |

- **Down-axis theme requires GSEA + module aggregation.** Module 2 top genes aren't ribosomal (AIM2/IGHG1, CYP1B1/PADI4,
  CD160/GZMM). Ribosome/translation is the top fgsea term in 4/11 down programs (sdt3), but is Module 2's module-level
  enrichment (Fig 5B, p = 1e-4). Module 5 = stress / cell death. Down axis: 7 programs in M2, 4 in M5.
- **HC-dependent programs:** only 3 (CD4Tcells_P10, P13, P17; 4-group p ≤ 0.044, patients-only p ≥ 0.12).
- **The pre-rollout v2 (core = BH 15, optional = nominal 11) would score rollout 1 6/6** (BH-core recall 0.87). Dropped.

**Decision: revise the grader, not the task.** Both are capability failures; the inputs already allow the correct
analysis, and stating the method in the prompt would leak it.

**v2 changes** (`GRADING_VERSION = "v2"`):
1. **New field `downregulated_axis_theme`** (see the v2 scoring table). Partial token `stress_response_cell_death`
   = Module 5; it is added to both theme vocabularies. `build_reference.py` asserts the reference against sdt3 and
   Fig 5B.
   - **Weight 2 (vs 1 for the up-axis theme):** weight follows what the field discriminates. The up-axis theme is
     answerable from top genes; the down-axis theme requires program-level GSEA then module aggregation. Not weighted
     by module count (associated programs split 14 up / 12 down).
   - **Overlap:** missing the down axis also costs fields 1, 2 and 4, so the down axis is the most heavily weighted
     result. Intended: it is the less obvious half of the finding.

**v2 scoring:**

| Field | v1 pts | v2 pts | Full credit | Partial (points in v2) | 0 |
|---|---|---|---|---|---|
| `disease_activity_architecture` | 2 | 2 | `multi_population_coordinated_opposing_axes` | `…coordinated_single_axis` 1.0; `multi_population_independent` 0.25 | other tokens |
| `associated_programs` | 1 | 1 | recall ≥ 0.8 and precision ≥ 0.8 vs the 26 nominal programs | none (all-or-nothing) | either below 0.8 |
| `upregulated_axis_theme` | 1 | 1 | `type_I_interferon_response` | `inflammatory_cytokine_signaling` 0.25 | other tokens |
| `downregulated_axis_theme` | – | 2 | `ribosome_translation_protein_targeting` | `stress_response_cell_death` 0.5 | other tokens, incl. `no_coherent_theme` |
| `axes_correlation` | 1 | 1 | within ±0.20 of −0.41 and negative | none | outside, positive, or `null` |
| `inference_strength` | 1 | 1 | `hypothesis_generating_candidates` | `confirmatory_association` 0.25 | other tokens |
| **max** | 6 | 8 | | | |

Hard fails (total → 0, unchanged): `single_population_dominant`; `mechanistic_driver_identified`.

2. **Field-2 diagnostics in `grade.json`.** These are score-neutral. Each one is recall of the agent's list against
   a subset of the 26 reference programs; the subsets are stored in `reference_answer.json`.

| Diagnostic | Reference subset (n) | Detects | Rollout 1 |
|---|---|---|---|
| module M1 (IFN hub) | Bcells_P07, P09; CD4Tcells_P04, P10, P13; CD8Tcells_P07; Myeloid_P17; NK_P10, P11; gdT_P04, P12 (11) | up-axis core found | 9/11 |
| module M2 (ribosome/translation) | Bcells_P17; CD4Tcells_P17; Myeloid_P06, P10; NK_P07; gdT_P07, P10 (7) | down-axis core found | 3/7 |
| module M5 (stress/cell death) | CD8Tcells_P10; Myeloid_P01; NK_P06; gdT_P13 (4) | second down module found | 1/4 |
| modules M4, M6 | Bcells_P01, gdT_P03 (M4); Bcells_P02, gdT_P09 (M6) (2 each) | weaker, off-hub associations | 0/2, 0/2 |
| up axis | M1 + M4 + gdT_P09 (14) | directional bias | 9/14 |
| down axis | M2 + M5 + Bcells_P02 (12) | directional bias | 4/12 |
| HC-dependent | CD4Tcells_P10, P13, P17 (3): 4-group p ≤ 0.044, patients-only p ≥ 0.12 | HC exclusion (reported, not scored: 3 borderline programs) | 0/3 |
| extra programs | agent programs outside the 26, listed | false positives (precision side) | none |

**Scores (verified):** `correct` 8/8; `plausible_incorrect` 1.5/8 (19%, with `no_coherent_theme`); `correct_strict` 7/8;
`hard_fail` 0; rollout 1 regraded **5/8 (63%)**.
