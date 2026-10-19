"""Readable live feed of a Claude Code stream-json trace (used by run_rollout.sh; stdlib only).

Reads stream-json lines on stdin and prints assistant messages, tool calls and short result previews.
Watching only: the full trace is saved separately by run_rollout.sh (tee -> trace.jsonl).
"""
import json
import sys
import time

DIM, BOLD, CYAN, YELLOW, RED, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[31m", "\033[0m"
RESULT_PREVIEW = 300
START = time.time()


def stamp():
    m, s = divmod(int(time.time() - START), 60)
    return f"{DIM}[{m:02d}:{s:02d}]{RESET}"


def tool_summary(name, inp):
    if name == "Bash":
        return inp.get("command", "")
    if name in ("Read", "Write", "Edit"):
        return inp.get("file_path", "")
    return json.dumps(inp)[:300]


def main():
    n_tools = 0
    for line in sys.stdin:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = e.get("type")
        text = ""
        if t == "user" and isinstance(e.get("message", {}).get("content"), (str, list)):
            c = e["message"]["content"]
            text = c if isinstance(c, str) else "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
        if (t == "system" and "compact" in str(e.get("subtype", ""))) or e.get("isCompactSummary") or \
                text.lstrip().startswith("This session is being continued from a previous conversation"):
            print(f"\n{stamp()} {YELLOW}{BOLD}--- context compacted ({e.get('subtype') or 'summary'}) ---{RESET}", flush=True)
            if text:
                print(f"{YELLOW}{text.strip()}{RESET}\n", flush=True)
        elif t == "system" and e.get("subtype") == "init":
            print(f"{stamp()} {BOLD}session {e.get('session_id')} · model {e.get('model')}{RESET}", flush=True)
        elif t == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    print(f"\n{stamp()} {BOLD}assistant:{RESET} {c['text'].strip()}", flush=True)
                elif c.get("type") == "tool_use":
                    n_tools += 1
                    print(f"{stamp()} {CYAN}tool {n_tools} {c.get('name')}:{RESET} {tool_summary(c.get('name'), c.get('input', {}))}",
                          flush=True)
        elif t == "user" and isinstance(e.get("message", {}).get("content"), list):
            for c in e["message"]["content"]:
                if c.get("type") == "tool_result":
                    body = c.get("content")
                    if isinstance(body, list):
                        body = "\n".join(x.get("text", "") for x in body if isinstance(x, dict))
                    body = (body or "").strip().replace("\n", "\n      ")
                    if len(body) > RESULT_PREVIEW:
                        body = body[:RESULT_PREVIEW] + " …"
                    color = RED if c.get("is_error") else DIM
                    print(f"      {color}{body}{RESET}", flush=True)
        elif t == "result":
            print(f"\n{stamp()} {YELLOW}{BOLD}done:{RESET} {e.get('subtype')} · turns {e.get('num_turns')} · "
                  f"tools {n_tools} · cost ${e.get('total_cost_usd') or 0:.2f}", flush=True)


if __name__ == "__main__":
    main()
