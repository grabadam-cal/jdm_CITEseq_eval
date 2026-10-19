#!/usr/bin/env bash
# Run one agent rollout on the eval and record everything needed for the take-home submission.
#
# Usage (from anywhere):  bash reference/rollouts/run_rollout.sh [label]
# Env options:
#   PERMISSION_MODE=<mode>       default bypassPermissions (unattended; the agent can run any command)
#   MAX_BUDGET_USD=<amount>      optional spend cap passed to --max-budget-usd
#   KEEP_OUTPUTS_IN_EVAL=1       don't restore eval/ after the run (default: restore it)
#
# Writes reference/rollouts/<timestamp>_<label>/:
#   prompt.txt        exact prompt given to the agent (= eval/task.txt)
#   trace.jsonl       raw Claude Code stream-json trace (every message, tool call and tool result)
#   trace.md          human-readable rendering of the trace
#   final.txt         the agent's final message
#   answer.json       parsed <EVAL_ANSWER> (absent if none was produced)
#   grade.json        grade at run time (against snapshot/grader/reference_answer.json)
#   grades/           every grading of this run, never overwritten: <grading_version>_<timestamp>.json + history.tsv
#                     (re-grade later with: python -I reference/rollouts/render_trace.py <run_dir>)
#   snapshot/         frozen copies of the eval inputs (task, answer format, README, vocabulary) and the grader
#                     (reference_answer.json, grade.py, build_reference.py) used for this run
#   audit.txt         accesses to anything outside eval/ (reference answers, paper, this conversation, ...)
#   outputs/          files the agent created or modified inside eval/ (intermediate outputs)
#   meta.json         CLI version, model, session id, cost/usage, checksums of the eval inputs
#   stderr.log        CLI stderr  (a readable live feed is printed to the terminal during the run)
#   settings.json     copy of the deny rules used for this run
#   session_transcript.jsonl  the agent's own Claude Code session transcript (includes compaction summaries)
#   compactions.md    each context-compaction summary (recap) verbatim, in order (only if compaction happened)
#   quarantined_memory_*/  auto-memory files moved out of ~/.claude/projects/<eval>/memory (only if any existed)
set -euo pipefail

# ---- rollout config (edit here; recorded in each run's meta.json) ----
MODEL="claude-sonnet-5"     # agent model (Sonnet 5.0; verified ID)
MAX_CONTEXT="200k"          # auto-compact window for --autocompact (auto, or 100k-1M): context is compacted at this size
GRADER_VERSION="v2"         # grade with reference/grader/versions/reference_answer_<version>.json (must match eval/eval_answer.json)
# ----------------------------------------------------------------------

# validate config before creating anything
if [[ ! "$MAX_CONTEXT" =~ ^(auto|[0-9]+[kKmM]?)$ ]]; then
  echo "MAX_CONTEXT must be auto or a size like 200k / 1M" >&2; exit 1
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVAL="$ROOT/eval"
REF="$ROOT/reference/grader/versions/reference_answer_${GRADER_VERSION}.json"
[[ -f "$REF" ]] || { echo "no reference for GRADER_VERSION=$GRADER_VERSION ($REF)" >&2; exit 1; }
# the grader's fields must be exactly the answer fields the agent is asked for
"$EVAL/.venv/bin/python" -I - "$REF" "$EVAL/eval_answer.json" <<'PY' || exit 1
import json, sys
ref, ans = (json.load(open(f)) for f in sys.argv[1:])
r, a = list(ref["rules"]), list(ans["answer"])
if r != a:
    sys.exit(f"GRADER_VERSION fields {r} != eval/eval_answer.json fields {a}")
PY
LABEL="${1:-run}"
# one rollout at a time: all runs share eval/ (snapshot -> run -> restore)
LOCK="$ROOT/reference/rollouts/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another rollout is running (lock $LOCK; remove it if no rollout is actually running)" >&2; exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
# never reuse a run folder: mkdir is atomic, so add _2, _3, ... if the name exists
base="$ROOT/reference/rollouts/$(date +%Y%m%d_%H%M%S)_${LABEL}"; RUN="$base"; n=2
until mkdir "$RUN" 2>/dev/null; do RUN="${base}_$n"; n=$((n + 1)); done
SESSION="$(uuidgen | tr 'A-Z' 'a-z')"
PERM="${PERMISSION_MODE:-bypassPermissions}"
mkdir -p "$RUN/outputs"

# auto-memory for the eval/ project (the only state Claude Code loads into new sessions automatically).
# Quarantine (move, never delete) any memory files into the run folder so every rollout starts fresh.
MEMDIR="$HOME/.claude/projects/$(printf '%s' "$EVAL" | sed 's/[^A-Za-z0-9]/-/g')/memory"
quarantine_memory() {  # $1 = destination subfolder name; prints number of files moved
  local n=0
  if [[ -d "$MEMDIR" ]]; then
    n=$(find "$MEMDIR" -type f | wc -l | tr -d ' ')
    if [[ "$n" -gt 0 ]]; then mkdir -p "$RUN/$1" && mv "$MEMDIR"/* "$RUN/$1"/; fi
  fi
  echo "$n"
}
MEM_BEFORE=$(quarantine_memory quarantined_memory_before)
[[ "$MEM_BEFORE" -gt 0 ]] && echo "WARNING: quarantined $MEM_BEFORE pre-existing memory file(s) -> $RUN/quarantined_memory_before/"

# snapshot eval/ (excluding the venv) so the run can be diffed and eval/ restored afterwards
manifest() { (cd "$EVAL" && find . -path ./.venv -prune -o -type f -print0 | xargs -0 shasum -a 256 | LC_ALL=C sort); }
manifest > "$RUN/.before.sha256"
tar -C "$EVAL" --exclude ./.venv -cf "$RUN/.eval_snapshot.tar" .
cp "$EVAL/task.txt" "$RUN/prompt.txt"
# frozen copy of what this run was given and graded with, so later edits/revisions never change its record
mkdir -p "$RUN/snapshot/eval" "$RUN/snapshot/grader"
cp "$EVAL/task.txt" "$EVAL/eval_answer.json" "$EVAL/README.md" "$EVAL/data/vocabulary.json" "$RUN/snapshot/eval/"
cp "$REF" "$RUN/snapshot/grader/reference_answer.json"
cp "$ROOT/reference/grader/grade.py" "$ROOT/reference/grader/build_reference.py" "$RUN/snapshot/grader/"

# git: GIT_CEILING_DIRECTORIES (below) stops git in eval/ from finding the project repo (history holds SETUP.md
# and every reference answer); .git/ is also denied and any git command is flagged in audit.txt.
# deny rules (Read/Edit/Write) for everything outside eval/ that could leak answers; kept here, not in eval/,
# so the agent can't read the list of where the answers are. Bash is not covered -> audit.txt is the backstop.
SETTINGS="$ROOT/reference/rollouts/rollout_settings.json"
args=(-p "$(cat "$EVAL/task.txt")" --output-format stream-json --verbose
      --session-id "$SESSION" --permission-mode "$PERM" --settings "$SETTINGS")
args+=(--model "$MODEL")
[[ -n "${MAX_BUDGET_USD:-}" ]] && args+=(--max-budget-usd "$MAX_BUDGET_USD")
args+=(--autocompact "$MAX_CONTEXT")

cp "$SETTINGS" "$RUN/settings.json"
echo "rollout -> $RUN (session $SESSION, permission mode $PERM, model $MODEL, autocompact $MAX_CONTEXT, grader $GRADER_VERSION)"
start=$(date +%s)
set +e
# Ctrl-C stops the agent but still runs the cleanup below (restore eval/, save outputs, grade the partial trace)
trap 'echo; echo "interrupted: stopping agent, restoring eval/ and saving the partial run"' INT
# full trace -> trace.jsonl; readable live feed -> this terminal (watching only)
( cd "$EVAL" && source env/activate.sh >/dev/null && GIT_CEILING_DIRECTORIES="$ROOT" claude "${args[@]}" < /dev/null ) 2> "$RUN/stderr.log" \
  | tee "$RUN/trace.jsonl" | "$EVAL/.venv/bin/python" -u -I "$ROOT/reference/rollouts/live_view.py"
status=${PIPESTATUS[0]}
trap - INT
set -e
echo "agent exited with status $status after $(( $(date +%s) - start ))s"
# the agent's own session transcript: holds the full conversation, including compaction summaries (recaps)
TRANSCRIPT="$(dirname "$MEMDIR")/$SESSION.jsonl"
if [[ -f "$TRANSCRIPT" ]]; then cp -p "$TRANSCRIPT" "$RUN/session_transcript.jsonl"
else echo "note: session transcript not found at $TRANSCRIPT"; fi
MEM_DURING=$(quarantine_memory quarantined_memory_written_during_run)
[[ "$MEM_DURING" -gt 0 ]] && echo "WARNING: agent wrote $MEM_DURING memory file(s) during the run -> $RUN/quarantined_memory_written_during_run/"

# collect files the agent created/modified inside eval/
manifest > "$RUN/.after.sha256"
LC_ALL=C comm -13 "$RUN/.before.sha256" "$RUN/.after.sha256" | sed 's/^[0-9a-f]*  //' | while IFS= read -r f; do
  mkdir -p "$RUN/outputs/$(dirname "$f")" && cp -p "$EVAL/$f" "$RUN/outputs/$f"
done
if [[ "${KEEP_OUTPUTS_IN_EVAL:-0}" != "1" ]]; then
  LC_ALL=C comm -13 <(sed 's/^[0-9a-f]*  //' "$RUN/.before.sha256" | LC_ALL=C sort) \
                    <(sed 's/^[0-9a-f]*  //' "$RUN/.after.sha256" | LC_ALL=C sort) \
    | while IFS= read -r f; do rm -f "$EVAL/$f"; done
  find "$EVAL" -path "$EVAL/.venv" -prune -o -type d -empty -delete 2>/dev/null || true
  tar -C "$EVAL" -xf "$RUN/.eval_snapshot.tar"   # restores originals, including any pre-existing empty dirs
fi
rm -f "$RUN/.eval_snapshot.tar"

PY="$EVAL/.venv/bin/python"
"$PY" -I "$ROOT/reference/rollouts/render_trace.py" "$RUN" --session "$SESSION" --exit-status "$status" \
  --permission-mode "$PERM" --memory-before "$MEM_BEFORE" --memory-during "$MEM_DURING" --autocompact "$MAX_CONTEXT" --initial \
  --reference "$RUN/snapshot/grader/reference_answer.json"
