"""Score an agent answer against reference_answer.json (grader-only).

Usage (from the Assessment root):
  python3 -I reference/grader/grade.py <rollout_text_or_answer_json> [--reference PATH] [--out grade.json]

The input may be a full transcript / final message (the LAST <EVAL_ANSWER>...</EVAL_ANSWER> block is used)
or a bare JSON object. Prints per-field scores, hard-fail reasons and the total as JSON.

Rule types (set per field in reference_answer.json "rules"):
  categorical  exact token; optional "partial" {token: fraction}; checked against the vocabulary
  integer      exact integer; optional "partial" {"value": fraction}
  numeric      |given - expected| <= abs_tol; optional "require_sign" (-1/+1) must match
  one_of       given value must be in the expected list
  core_set     list answer; recall over expected["core"] >= min_recall and
               precision over core ∪ optional >= min_precision
Hard fails ("hard_fail"): every condition in "when" must hold ({"field", "in": [...]}, {"field", "lt": x} or {"field", "gt": x});
any triggered hard fail sets the total to 0.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOCAB = HERE.parents[1] / "eval" / "data" / "vocabulary.json"


def extract_answer(text):
    blocks = re.findall(r"<EVAL_ANSWER>\s*(.*?)\s*</EVAL_ANSWER>", text, flags=re.S)
    payload = blocks[-1] if blocks else text
    payload = re.sub(r"^```(?:json)?\s*|\s*```$", "", payload.strip())
    return json.loads(payload)


def allowed_tokens(field, rule, vocab):
    return vocab.get(rule.get("vocab_key", f"{field}_vocabulary"))


def score_field(field, value, expected, rule, vocab):
    kind = rule["type"]
    if kind == "categorical":
        allowed = allowed_tokens(field, rule, vocab)
        if allowed is not None and value not in allowed:
            return 0.0, f"{value!r} not in vocabulary"
        if value == expected:
            return 1.0, "match"
        frac = rule.get("partial", {}).get(value, 0.0)
        return frac, ("partial" if frac else "mismatch") + f" (expected {expected!r})"
    if kind == "integer":
        try:
            v = int(value)
        except (TypeError, ValueError):
            return 0.0, "not an integer"
        if v == int(expected):
            return 1.0, "match"
        frac = rule.get("partial", {}).get(str(v), 0.0)
        return frac, f"{v} vs {expected}"
    if kind == "numeric":
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 0.0, "not numeric"
        sign = rule.get("require_sign")
        if sign is not None and (v == 0 or (v > 0) != (sign > 0)):
            return 0.0, f"wrong sign ({v})"
        ok = abs(v - float(expected)) <= rule.get("abs_tol", 0.0)
        return (1.0, "within tolerance") if ok else (0.0, f"{v} vs {expected} (tol {rule.get('abs_tol', 0.0)})")
    if kind == "one_of":
        return (1.0, "accepted") if value in expected else (0.0, f"{value!r} not in {expected}")
    if kind == "core_set":
        got = value if isinstance(value, list) else [value]
        allowed = allowed_tokens(field, rule, vocab) if rule.get("vocab_key") else None
        if allowed is not None and any(v not in allowed for v in got):
            return 0.0, "token(s) not in vocabulary"
        got = set(got)
        core = set(expected["core"])
        ok_set = core | set(expected.get("optional", []))
        recall = len(got & core) / len(core) if core else 1.0
        precision = len(got & ok_set) / len(got) if got else 0.0
        ok = recall >= rule.get("min_recall", 1.0) and precision >= rule.get("min_precision", 1.0)
        return (1.0 if ok else 0.0), f"core_recall={recall:.2f} precision={precision:.2f} n={len(got)}"
    raise ValueError(f"unknown rule type: {kind}")


def condition_holds(answer, cond):
    v = answer.get(cond["field"])
    if "in" in cond:
        return v in cond["in"]
    if "lt" in cond:
        try:
            return float(v) < cond["lt"]
        except (TypeError, ValueError):
            return False
    if "gt" in cond:
        try:
            return float(v) > cond["gt"]
        except (TypeError, ValueError):
            return False
    raise ValueError(f"unknown condition: {cond}")


def grade(answer, reference, vocab):
    fields, total, max_total = {}, 0.0, 0.0
    for field, rule in reference["rules"].items():
        pts = rule.get("points", 1.0)
        max_total += pts
        if field not in answer:
            fields[field] = {"score": 0.0, "max": pts, "note": "missing"}
            continue
        frac, note = score_field(field, answer[field], reference["answer"][field], rule, vocab)
        fields[field] = {"score": round(frac * pts, 4), "max": pts, "note": note, "given": answer[field]}
        total += frac * pts
    hard = [h["reason"] for h in reference.get("hard_fail", []) if all(condition_holds(answer, c) for c in h["when"])]
    extra = sorted(set(answer) - set(reference["rules"]))
    return {"total": 0.0 if hard else round(total, 4), "max": max_total,
            "fraction": 0.0 if hard else round(total / max_total, 4),
            "hard_fail": hard, "unexpected_fields": extra, "fields": fields}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answer")
    ap.add_argument("--reference", default=str(HERE / "reference_answer.json"))
    ap.add_argument("--out")
    args = ap.parse_args()
    answer = extract_answer(Path(args.answer).read_text())
    reference = json.loads(Path(args.reference).read_text())
    vocab = json.loads(VOCAB.read_text()) if VOCAB.exists() else {}
    result = grade(answer, reference, vocab)
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    sys.exit(main())
