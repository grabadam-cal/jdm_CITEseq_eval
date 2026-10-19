# Build-cycle post-mortem

Brief target: a ~2-hour design → build → test → refine cycle. Actual: ~5.6 h active over two sessions
(2026-10-18 13:30 → 2026-10-19 12:00). Of that, the eval cycle itself took ~3 h and setup beyond the brief took ~2.6 h.

Note on the git history: the repo was initialised at the end (2026-10-19 10:53), so commits cover only the last hour.
Earlier work is visible only in the rollout 1 folder name (`20261018_184208`) and `reference/logs/`.

## Time spent

Active time comes from session timestamps, counting only gaps under 15 min.

| Phase | Clock time | Active | In brief scope? |
|---|---|---|---|
| Setup: source data → CSV, pinned R/Python environment, reproduction checks against the paper | 10-18 13:30–16:12 | ~2.6 h | no (chosen extra) |
| Eval design + build: task, vocabulary, answer fields, grader, tests, rollout tooling, rollout 1 | 10-18 16:12–18:47 | ~2.3 h | yes |
| Refine: rollout 1 review, revision v2, containment pre-flight | 10-19 10:00–12:00 | ~0.7 h | yes |

Cost drivers:
- **Environment:** an Intel Mac on an unsupported macOS (no Homebrew bottles, old Xcode), plus pins for renv,
  msigdbr and Seurat.
- **Answer-field scoping:** repeated rounds (12 → 8 → 5 fields).
- **Context exposure:** several rounds on how much `eval/` reveals (README, vocabulary, task wording).
- **Docs:** SETUP.md rewritten while the design was still changing.

## What the extra time bought

| Item | Value |
|---|---|
| Reference generated from the paper's source data | It can be checked, not hand-copied: the Fig 7A ANOVA reproduces 73/73 programs; fgsea reproduces Supplemental Table 3 exactly with msigdbr 7.4.1 |
| Byte-identical data rebuild (`reference/build_eval_data.py`) | Eval inputs can be traced back to the source data |
| Frozen grader versions; regrades never overwrite | v1 and v2 grades of the same rollout sit side by side |
| Field-2 diagnostics | They show *why* points were lost (by module, by direction, HC-dependent programs) |
| Containment pre-flight test | Found the git-history leak before rollout 2 |

## Where to cut (doing it again)

| Cut | Saves | Why it's safe |
|---|---|---|
| **Run a cheap rollout first**, then design fields around the observed failures | most of the field-scoping rounds | Rollout 1 exposed failure modes (HC exclusion, ordinal pooling, top-gene annotation) that the up-front design missed. The revision planned before the rollout (BH-tolerant scoring) would have *rewarded* the wrong method. |
| **Contain the agent in a container that mounts only `eval/`** | ~1 h of tooling | It replaces the deny rules, memory quarantine, git hiding and audit regexes, and it closes the Bash gap the current setup can only flag. |
| **Use a prebuilt image or standard environment**; pin only what changes the reference (msigdbr) | most of setup | The agent needs a working environment, not the paper's exact one. |
| **Set the context rule once at the start** (`eval/` = neutral data + token definitions only) | several review rounds | The same decision was re-made file by file. |
| **Write docs last** | repeated rewrites | The design changed after every rollout. |

## Containment gap found after rollout 2 (not fixed)

Claude Code adds the repo's git status and its 5 most recent commit messages to every session's context.
`GIT_CEILING_DIRECTORIES` and the `.git` deny rules don't affect this. Because the project repo was created before
rollout 2, that agent saw commit messages naming the v2 field and its weight ("downregulated_axis_theme (2 pts)"),
`notes/SETUP.md` and the containment changes. It saw no reference values. Rollout 1 instead saw a git status of the
home directory (file names only), because the home directory is a git repo.

- **Fix for future runs:** hide `.git` for the duration of a run (rename it, and restore it on exit), or run in a
  container that mounts only `eval/`. Then re-run the pre-flight test, checking the agent's session context as well
  as its tool access.
- **Lesson:** the pre-flight test checked what the agent can *access*, not what Claude Code *injects* into its
  context. Both need checking.

## With more time instead

- Several rollouts per grader version, to measure run-to-run variance (n = 1 now).
- A second agent model, for comparison.
- Scoring HC exclusion directly if a stronger signal exists (now reported, not scored: only 3 borderline programs).
