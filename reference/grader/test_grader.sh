#!/usr/bin/env bash
# Brief test: grade one correct answer and one plausible but scientifically incorrect answer,
# and confirm the grader distinguishes them. Writes test_answers/<name>.grade.json. Run from anywhere.
# Optional checks of grading assumptions (stricter threshold, hard fails): EXTRA=1 bash test_grader.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
G=reference/grader
score() {  # $1 = answer file -> prints "name total max fraction hard_fail"
  local out="${1%.txt}.grade.json"
  python3 -I $G/grade.py "$1" --out "$out" > /dev/null
  python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); print(f\"{sys.argv[2]:22s} {d['total']:5.2f} / {d['max']:.0f}  ({d['fraction']:.0%})  hard_fail={d['hard_fail'] or '-'}\")" "$out" "$(basename "$1" .txt)"
}
score $G/test_answers/correct.txt
score $G/test_answers/plausible_incorrect.txt
python3 -I - <<'PY'
import json
c = json.load(open("reference/grader/test_answers/correct.grade.json"))
w = json.load(open("reference/grader/test_answers/plausible_incorrect.grade.json"))
assert c["fraction"] == 1.0, f"correct answer not full credit: {c['fraction']}"
assert w["fraction"] < 0.5, f"plausible-incorrect answer scored too high: {w['fraction']}"
print(f"PASS: grader distinguishes them (correct {c['fraction']:.0%} vs plausible-incorrect {w['fraction']:.0%})")
PY
if [[ "${EXTRA:-0}" == "1" ]]; then
  echo "-- extra tests (grading assumptions) --"
  for f in $G/extra_tests/*.txt; do score "$f"; done
fi
