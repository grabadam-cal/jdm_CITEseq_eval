"""Post-process / re-grade a rollout directory written by run_rollout.sh.

Initial render (called by run_rollout.sh with --initial): reads <run_dir>/trace.jsonl (Claude Code stream-json) and
writes trace.md, final.txt, answer.json, audit.txt, meta.json and grade.json (the grade at run time).

Re-grade (run by hand, no --initial):  python -I reference/rollouts/render_trace.py <run_dir> [--reference PATH]
Grades the saved answer against the CURRENT reference (or --reference) and writes a NEW file
grades/<grading_version>_<timestamp>.json plus a line in grades/history.tsv. Nothing existing is overwritten:
grade.json, meta.json and the trace stay as they were at run time.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "reference" / "grader"))
import grade as grader  # noqa: E402

MAX_RESULT_CHARS = 4000
# anything an eval agent should never touch: paper, published results, reference answers, this repo's notes,
# the paper's code, and Claude Code transcripts/memory (which contain the design discussion)
FORBIDDEN = [r"JCI_data", r"reference/", r"SETUP\.md", r"Takehome", r"Rabadam", r"jci\.insight", r"176963",
             r"DECIPHER", r"grabadam", r"\.claude/projects", r"eval_id_map", r"reference_answer",
             r"LatchBio_Assessment_2026/(?!eval)", r"(^|[\s'\"=])\.\.(/|\s|$)", r"\.git\b", r"(^|[\s;&|('\"])git\s"]


def events(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "unparsed", "raw": line}


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(c.get("text", c.get("content", ""))) if isinstance(c, dict) else str(c) for c in content)
    return json.dumps(content)


SUMMARY_PREFIX = "This session is being continued from a previous conversation"


def message_text(e):
    c = e.get("message", {}).get("content", "")
    if isinstance(c, str):
        return c
    return "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text") if isinstance(c, list) else ""


def is_compaction(e):
    """Compaction marker or summary, in either the stream-json trace or the session transcript."""
    if e.get("isCompactSummary") or "compact" in str(e.get("subtype", "")):
        return True
    return e.get("type") == "user" and message_text(e).lstrip().startswith(SUMMARY_PREFIX)


def compaction_summaries(run, stream_events):
    """One entry per compaction: {"meta": marker metadata, "ts": ..., "text": verbatim recap or ""}.
    Uses the session transcript if present (it holds the recap text), else the stream-json trace.
    A marker (compact_boundary) and the summary message that follows it are merged into one entry."""
    tp = run / "session_transcript.jsonl"
    src, evs = ("session_transcript.jsonl", list(events(tp))) if tp.exists() else ("trace.jsonl", stream_events)
    out = []
    for e in evs:
        if not is_compaction(e):
            continue
        text = message_text(e) if e.get("type") == "user" else ""
        if text and out and not out[-1]["text"]:
            out[-1]["text"] = text                      # summary that follows its marker
        else:
            out.append({"meta": e.get("compact_metadata", {}), "ts": e.get("timestamp", ""), "text": text})
    return src, out


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grade_and_record(run, ref_path):
    """Grade run/answer.json against ref_path; save grades/<version>_<ts>.json and append grades/history.tsv."""
    reference = json.loads(ref_path.read_text())
    version = reference.get("provenance", {}).get("grading_version", "unversioned").split()[0]
    vocab = json.loads((ROOT / "eval" / "data" / "vocabulary.json").read_text())
    try:
        grade = grader.grade(json.loads((run / "answer.json").read_text()), reference, vocab)
    except Exception as exc:  # no/invalid EVAL_ANSWER
        grade = {"total": 0.0, "max": sum(r.get("points", 1.0) for r in reference["rules"].values()),
                 "hard_fail": [], "error": f"no valid <EVAL_ANSWER>: {exc}"}
    ts = time.strftime("%Y%m%d_%H%M%S")
    grade = {"grading_version": version, "graded_at": ts, "reference": str(ref_path),
             "reference_sha256": sha(ref_path), **grade}
    gdir = run / "grades"
    gdir.mkdir(exist_ok=True)
    out = gdir / f"{version}_{ts}.json"
    k = 2
    while out.exists():
        out = gdir / f"{version}_{ts}_{k}.json"
        k += 1
    out.write_text(json.dumps(grade, indent=2) + "\n")
    hist = gdir / "history.tsv"
    if not hist.exists():
        hist.write_text("graded_at\tgrading_version\ttotal\tmax\thard_fail\tfile\treference_sha256\n")
    with hist.open("a") as fh:
        fh.write(f"{ts}\t{version}\t{grade.get('total')}\t{grade.get('max')}\t{'; '.join(grade.get('hard_fail') or []) or '-'}"
                 f"\t{out.name}\t{grade['reference_sha256'][:12]}\n")
    return grade


def regrade(run, ref_path):
    grade = grade_and_record(run, ref_path)
    print(f"{run.name}: {grade['grading_version']} -> {grade.get('total')}/{grade.get('max')}"
          f"{'  HARD FAIL: ' + '; '.join(grade['hard_fail']) if grade.get('hard_fail') else ''}")
    print(f"saved {run / 'grades'}; history:\n" + (run / "grades" / "history.tsv").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--session")
    ap.add_argument("--exit-status", type=int)
    ap.add_argument("--permission-mode")
    ap.add_argument("--memory-before", type=int, default=0)
    ap.add_argument("--memory-during", type=int, default=0)
    ap.add_argument("--initial", action="store_true", help="first render, called by run_rollout.sh")
    ap.add_argument("--autocompact", default="default")
    ap.add_argument("--reference", default=str(ROOT / "reference" / "grader" / "reference_answer.json"))
    args = ap.parse_args()
    run = Path(args.run_dir)
    if not args.initial:
        return regrade(run, Path(args.reference))
    evs = list(events(run / "trace.jsonl"))

    md, final, init, result, audit = [f"# Rollout trace: {run.name}\n"], "", {}, {}, []
    md.append("## Prompt\n\n```\n" + (run / "prompt.txt").read_text() + "\n```\n")
    n_tool, n_compact = 0, 0
    src, summaries = compaction_summaries(run, evs)
    for e in evs:
        t = e.get("type")
        if is_compaction(e):
            if message_text(e) and n_compact and not e.get("subtype"):
                continue                                # summary for a marker already rendered
            n_compact += 1
            entry = summaries[n_compact - 1] if n_compact <= len(summaries) else {"meta": {}, "text": message_text(e)}
            meta = e.get("compact_metadata") or entry["meta"]
            md.append(f"---\n**context compacted #{n_compact}** ({json.dumps(meta)}). Recap the agent continues from:\n"
                      + (f"\n```\n{entry['text']}\n```\n" if entry["text"] else "\n_(no recap text captured)_\n") + "---\n")
        elif t == "system" and e.get("subtype") == "init":
            init = e
            md.append(f"_session {e.get('session_id')} · model {e.get('model')} · cwd {e.get('cwd')}_\n")
        elif t == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    md.append("### Assistant\n\n" + c["text"].strip() + "\n")
                    final = c["text"]
                elif c.get("type") == "thinking" and c.get("thinking", "").strip():
                    md.append("<details><summary>thinking</summary>\n\n" + c["thinking"].strip() + "\n\n</details>\n")
                elif c.get("type") == "tool_use":
                    n_tool += 1
                    inp = json.dumps(c.get("input", {}), indent=2)
                    md.append(f"### Tool call {n_tool}: `{c.get('name')}`\n\n```json\n{inp}\n```\n")
                    for pat in FORBIDDEN:
                        if re.search(pat, inp):
                            audit.append(f"tool call {n_tool} ({c.get('name')}): matches {pat!r}: {inp[:300]}")
        elif t == "user":
            content = e.get("message", {}).get("content", [])
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_result":
                    body = text_of(c.get("content", ""))
                    shown = body if len(body) <= MAX_RESULT_CHARS else body[:MAX_RESULT_CHARS] + f"\n... [{len(body) - MAX_RESULT_CHARS} chars truncated; full text in trace.jsonl]"
                    tag = " (error)" if c.get("is_error") else ""
                    md.append(f"<details><summary>result{tag}</summary>\n\n```\n{shown}\n```\n\n</details>\n")
        elif t == "result":
            result = e
            if e.get("result"):
                final = e["result"]

    if summaries:
        out = [f"# Context compactions: {run.name}\n", f"_source: {src}; {len(summaries)} compaction(s)_\n"]
        for k, c in enumerate(summaries, 1):
            out.append(f"## Compaction {k}{' (' + c['ts'] + ')' if c['ts'] else ''}\n\n{json.dumps(c['meta'])}\n\n"
                       + (f"```\n{c['text']}\n```\n" if c["text"] else "_(no recap text captured)_\n"))
        (run / "compactions.md").write_text("\n".join(out))
        n_compact = max(n_compact, len(summaries))
    (run / "final.txt").write_text(final)
    md.append("## Final message\n\n" + final + "\n")
    (run / "trace.md").write_text("\n".join(md))

    try:
        answer = grader.extract_answer(final)
        (run / "answer.json").write_text(json.dumps(answer, indent=2) + "\n")
    except Exception:  # no/invalid EVAL_ANSWER
        pass
    grade = grade_and_record(run, Path(args.reference))
    (run / "grade.json").write_text(json.dumps(grade, indent=2) + "\n")

    if args.memory_during:
        audit.append(f"agent wrote {args.memory_during} auto-memory file(s) during the run "
                     "(quarantined to quarantined_memory_written_during_run/)")
    (run / "audit.txt").write_text(
        ("OUT-OF-SCOPE ACCESS DETECTED (review before trusting this rollout):\n" + "\n".join(audit) + "\n")
        if audit else "No access outside eval/ detected in tool calls.\n")

    try:
        cli = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    except OSError:
        cli = None
    inputs = [ROOT / "eval" / "task.txt", ROOT / "eval" / "eval_answer.json", *sorted((ROOT / "eval" / "data").glob("*"))]
    meta = {"run": run.name, "session_id": args.session or init.get("session_id"), "claude_cli": cli,
            "model": init.get("model"), "permission_mode": args.permission_mode, "exit_status": args.exit_status,
            "num_turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
            "total_cost_usd": result.get("total_cost_usd"), "usage": result.get("usage"),
            "n_tool_calls": n_tool, "autocompact": args.autocompact, "n_compactions": n_compact, "is_error": result.get("is_error"), "stop_reason": result.get("subtype"),
            "score": grade.get("total"), "max": grade.get("max"), "hard_fail": grade.get("hard_fail"),
            "out_of_scope_access": len(audit),
            "memory_files_quarantined_before_run": args.memory_before,
            "memory_files_written_during_run": args.memory_during,
            "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs if p.is_file()}}
    (run / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({k: meta[k] for k in ("model", "num_turns", "n_tool_calls", "total_cost_usd", "score", "max",
                                           "hard_fail", "out_of_scope_access")}, indent=1))


if __name__ == "__main__":
    main()
