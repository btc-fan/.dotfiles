#!/usr/bin/env python3
"""Router tests: hook JSON on stdin for every rule in routing.yaml (should-fire and should-not-fire).

Run: bash ai/tests/run.sh   (or python3 ai/tests/test_router.py [-k <name part>] [-v])

Each ai/tests/cases/<rule>.json holds {"rule": id, "cases": [...]}. A case:
  name     text
  expect   fire | nofire | log | deny | ask | allow | block | miss | nomiss
           (fire/nofire/log: did the rule fire in the LAST step; deny/ask/allow: the gate decision;
           block: a Stop hook block in the last step)
  steps    [{event, payload, transcript_append: [json rows], state_files: {rel: text}}]  (or one "event" + "payload")
  agent    claude (default) | codex
  project  {git: true, git_init: true, files: {rel: text}, stage: {rel: text}, commit: "<message>",
           dirty: {rel: text} (written after the commit), worktree: "../wt" (git worktree add), extra_commits: [{rel: text}, ...] (after the commit),
           age_days: {rel: days} (file mtime set back, e.g. a stale graph),
           setup_sh: "<bash script>" (run last in the project, e.g. branches and a merge in progress)}
  audit_log  lines for ~/.local/state/ai/audit.log
  ai_mcp   text for $AI_HOME/ai/mcp/context7.json, committed (secret-scan allowlist reads HEAD);
           ai_mcp_commit: false keeps it uncommitted
  secrets_env  text for ~/.config/ai/secrets.env
  state_files  {rel: text} written into the state dir (~/.local/state/ai) before the steps
  env      extra environment for the router (e.g. AI_STATE_DIR pointing at a file: unwritable state)
  gate_skip  a line for the owner skip file (/etc/ai/gate-skip); {{SOON}} / {{PAST}} = expiry times
  contains / not_contains   text that must (not) be in the hook output
Placeholders: {{PROJ}} {{HOME}} {{NOW}} {{OLD}} {{TRANSCRIPT}} and fake secrets {{GH_TOKEN}} {{CTX7_KEY}}
{{CTX7_OTHER}} {{PW}} {{ENVTOK}} {{NPM_TOKEN}} {{HF_TOKEN}} {{DBURL}} {{GH_REAL}} {{SK_LIVE_REAL}}
{{SK_LIVE_SAMPLE}} {{ADMINPASS}} {{AIZA_TEST}} {{ZPS_FAKE}} {{JWT_REAL}} {{DBURL_TEST}}
(fake secrets are built here at run time, so no secret-looking string is stored in the repo).
Every run uses a throwaway HOME and state dir. Nothing touches the real home.
The one-step Bash cases of secret-scan and pr-rules also run through `ai-check <rule> --command` (ticket 05):
the exit code must match the hook decision.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
ROUTER = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks", "router.py")
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
OLD = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 2 * 86400))
FAKE = {
    "{{GH_TOKEN}}": "ghp" + "_" + "Q7" * 18,
    "{{CTX7_KEY}}": "ctx7sk" + "-" + "a1b2c3d4-" * 4 + "test",
    "{{CTX7_OTHER}}": "ctx7sk" + "-" + "z9y8x7w6-" * 4 + "evil",
    "{{PW}}": "S3cr3t" + "Passw0rd9x",
    "{{ENVTOK}}": "abc123" + "def456ghi789jkl",
    "{{NPM_TOKEN}}": "npm" + "_" + "A1" * 18,
    "{{HF_TOKEN}}": "hf" + "_" + "kQ" * 17,
    "{{DBURL}}": "postgres://app:" + "Hunter2" * 2 + "@db:5432/x",
    # Real key shapes (provider prefix, real length, high entropy) and the fake test values of the 7-day audit.
    "{{GH_REAL}}": "ghp" + "_" + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6",
    "{{SK_LIVE_REAL}}": "sk" + "_live_" + "51HqZt8kLmP2vQ9xR4wN7yB3cD6f",
    "{{SK_LIVE_SAMPLE}}": "sk" + "_live_" + "TESTsample" + "0" * 14,
    "{{ADMINPASS}}": "admin" + "pass123",
    "{{AIZA_TEST}}": "AIza" + "SECRET-test-key",
    "{{ZPS_FAKE}}": "zps" + "_4f9a1c7e2b6d8e0f3a5c7b9d1e3f5a7c",
    "{{JWT_REAL}}": "q8Zr2LmX9v" + "Tn4KpW7sYb1HcJ6dFg3QeA",       # review S4: high entropy, no fake marker
    "{{DBURL_TEST}}": "postgres://app:" + "testpass123" + "@db/x",  # review S4: a fake-marked URL password
}
FIRE_KINDS = {"fire", "log", "deny", "ask", "miss", "block"}
QUIET_KINDS = {"nofire", "allow", "nomiss"}


def main(argv):
    verbose = "-v" in argv
    only = argv[argv.index("-k") + 1] if "-k" in argv else None
    work = tempfile.mkdtemp(prefix="ai-router-tests-")
    try:
        build = os.path.join(work, "build")
        res = subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--profile", "server", "--out", build],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if res.returncode != 0:
            print(res.stdout.decode())
            return 1
        routing = json.load(open(os.path.join(build, "routing.json")))
        failures, total, coverage = [], 0, {}
        for path in sorted(glob.glob(os.path.join(TESTS, "cases", "*.json"))):
            spec = json.load(open(path))
            for case in spec["cases"]:
                label = "%s: %s" % (spec["rule"], case["name"])
                if only and only not in label:
                    continue
                total += 1
                err = run_case(spec["rule"], case, work, build)
                coverage.setdefault(spec["rule"], set()).add(case["expect"])
                if err:
                    failures.append("%s -> %s" % (label, err))
                    print("FAIL " + label + "\n     " + err)
                elif verbose:
                    print("ok   " + label)
        if not only:
            failures.extend(check_coverage(routing, coverage))
            failures.extend(check_tiebreak_regex(routing))
            failures.extend(check_fail_closed(work))
            failures.extend(check_fail_closed_inputs(work, build))
        print("\nai-check: %d cases gave the same decision as the hook" % len(CHECKED))
        print("%d cases, %d failed" % (total, len(failures)))
        for f in failures:
            if "->" not in f:
                print("FAIL " + f)
        return 1 if failures else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


FAIL_CLOSED_PROBE = r"""
import io, json, sys, contextlib
sys.path.insert(0, sys.argv[1])
import router
def boom(ctx):
    raise RuntimeError("forced test crash")
router.HANDLERS["PreToolUse"] = boom
res = {}
for tool, inp in (("Bash", {"command": "echo hi"}), ("Read", {"file_path": "/tmp/x"})):
    sys.stdin = io.StringIO(json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool,
                                        "tool_input": inp, "cwd": "/tmp"}))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        router.main(["--agent", "claude", "--managed", "PreToolUse"])
    o = out.getvalue().strip()
    res[tool] = json.loads(o)["hookSpecificOutput"]["permissionDecision"] if o else "allow"
print(json.dumps(res))
"""


def check_fail_closed(work):
    """A crashing PreToolUse handler must deny a shell command (gates did not run) and leave Read alone."""
    hooks = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks")
    env = dict(os.environ, HOME=os.path.join(work, "home-fc"))
    res = subprocess.run([sys.executable, "-c", FAIL_CLOSED_PROBE, hooks], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env)
    try:
        got = json.loads(res.stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ["fail-closed probe gave no result: " + short(res.stderr.decode())]
    if got != {"Bash": "deny", "Read": "allow"}:
        return ["fail-closed: crashing gate gave %s, want Bash deny and Read allow" % got]
    return []


FAIL_CLOSED_UNITS = r"""
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
import hooklib, router

tmp = tempfile.mkdtemp()
good, bad, folder, empty = (os.path.join(tmp, n) for n in ("good.json", "bad.json", "folder.json", "empty.json"))
open(good, "w").write(json.dumps({"rules": [{"id": "x"}]}))
open(bad, "w").write("{not json")
open(empty, "w").write("{}")
os.mkdir(folder)

def load(*paths):
    router.routing_candidates = lambda: list(paths)
    routing = router.load_routing()
    return [len(routing["rules"]), bool(routing.get("broken"))]

res = {"bad then good": load(bad, good), "bad": load(bad), "folder": load(folder), "no rules list": load(empty),
       "missing": load(os.path.join(tmp, "none.json"))}

tok = "ghp" + "_" + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6"
value = "s3cR3t" + "V4lu3XYZ123q"
res["cut keeps part of a key"] = tok[:10] in hooklib.redact("x " * (hooklib.REDACT_MAX // 2 - 25) + "y" * 40 + " " + tok + " and more text")
res["long name in clear text"] = value in hooklib.redact("x" * 80 + "_tok" + "en=" + value)
print(json.dumps(res))
"""


def check_fail_closed_inputs(work, build):
    """R-017: rules or a payload that the router cannot read must deny a shell command.
    A long denied command must not hold the hook until its timeout, because a timed-out hook does not block."""
    hooks = os.path.dirname(ROUTER)
    good = os.path.join(build, "routing.json")
    bad = os.path.join(work, "bad-routing.json")
    write(bad, "{not json")

    base = {"hook_event_name": "PreToolUse", "cwd": work, "session_id": "fail-closed-inputs"}
    tool = lambda name, tin: json.dumps(dict(base, tool_name=name, tool_input=tin))
    bash = lambda cmd: tool("Bash", {"command": cmd})
    probes = [      # name, agent, routing.json, event, stdin, wanted decision
        ("corrupt routing.json, Bash", "claude", bad, "PreToolUse", bash("gh pr merge 5 --squash"), "deny"),
        ("corrupt routing.json, Bash, Codex", "codex", bad, "PreToolUse", bash("gh pr merge 5 --squash"), "deny"),
        ("corrupt routing.json, Read", "claude", bad, "PreToolUse", tool("Read", {"file_path": "/tmp/x"}), None),
        ("payload is a JSON list", "claude", good, "PreToolUse", "[]", "deny"),
        ("payload is cut short", "claude", good, "PreToolUse", bash("echo hi")[:40], "deny"),
        ("payload is not UTF-8", "claude", good, "PreToolUse", b"\xff\xfe" + bash("echo hi").encode(), "deny"),
        ("payload is nested too deep", "claude", good, "PreToolUse", "[" * 200000, "deny"),
        ("Bash tool_input is a string", "claude", good, "PreToolUse", tool("Bash", "git commit --no-verify"), "deny"),
        ("Bash tool_input is an empty list", "claude", good, "PreToolUse", tool("Bash", []), "deny"),
        ("exec_command tool_input is a string", "codex", good, "PreToolUse", tool("exec_command", "git push"), "deny"),
        ("Bash without tool_input", "claude", good, "PreToolUse", json.dumps(dict(base, tool_name="Bash")), None),
        ("empty payload", "claude", good, "PreToolUse", "", None),
        ("SessionStart, payload is a JSON list", "claude", good, "SessionStart", "[]", None),
        ("16 KB denied command", "claude", good, "PreToolUse", bash("git commit --no-verify -m " + "a-" * 8000), "deny"),
    ]

    failures = []
    home = os.path.join(work, "home-fail-closed-inputs")
    for name, agent, routing, event, stdin, want in probes:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LANG": "C.UTF-8",
               "AI_STATE_DIR": os.path.join(home, "state"), "AI_ROUTING_JSON": routing,
               "AI_CLAUDE_MANAGED_SETTINGS": os.path.join(work, "no-managed-settings.json")}
        start = time.time()
        res = subprocess.run([sys.executable, ROUTER, "--agent", agent, event],
                             input=stdin if isinstance(stdin, bytes) else stdin.encode(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        elapsed = time.time() - start

        got = decision_of(res.stdout.decode(), res.returncode, agent)
        if res.returncode != 0:
            failures.append("fail-closed input (%s): exit %d: %s" % (name, res.returncode, short(res.stderr.decode())))
        elif got != want:
            failures.append("fail-closed input (%s): got %s, want %s" % (name, got, want))
        elif elapsed > 3:
            failures.append("fail-closed input (%s): took %.1f s, want under 3 s" % (name, elapsed))

    res = subprocess.run([sys.executable, "-c", FAIL_CLOSED_UNITS, hooks], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=dict(os.environ, HOME=home))
    want = {"bad then good": [1, False], "bad": [0, True], "folder": [0, True], "no rules list": [0, True],
            "missing": [0, False], "cut keeps part of a key": False, "long name in clear text": False}
    try:
        got = json.loads(res.stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        return failures + ["fail-closed units gave no result: " + short(res.stderr.decode())]
    failures.extend("fail-closed unit (%s): got %s, want %s" % (k, got.get(k), v) for k, v in want.items()
                    if got.get(k) != v)
    return failures


def check_coverage(routing, coverage):
    errs = []
    for rule in routing["rules"]:
        kinds = coverage.get(rule["id"], set())
        if not kinds & FIRE_KINDS:
            errs.append("coverage: rule %s has no should-fire case" % rule["id"])
        if not kinds & QUIET_KINDS:
            errs.append("coverage: rule %s has no should-not-fire case" % rule["id"])
    return errs


def check_tiebreak_regex(routing):
    return ["tie-break without match regex: %s" % t["trigger"] for t in routing["tiebreaks"] if not t.get("match")]


# ---------------------------------------------------------------- one case

def run_case(rule_id, case, work, build):
    tmp = tempfile.mkdtemp(dir=work)
    home = os.path.join(tmp, "home")
    state = os.path.join(home, ".local", "state", "ai")
    proj = os.path.join(tmp, "proj")
    ai_home = os.path.join(tmp, "aihome")
    os.makedirs(state)
    os.makedirs(proj)
    os.makedirs(os.path.join(ai_home, "ai", "mcp"))
    transcript = os.path.join(tmp, "transcript.jsonl")
    open(transcript, "w").close()
    subs = dict(FAKE, **{"{{PROJ}}": proj, "{{NOW}}": NOW, "{{OLD}}": OLD, "{{TRANSCRIPT}}": transcript,
                         "{{HOME}}": home})

    setup_project(proj, sub(case.get("project", {}), subs))
    if case.get("audit_log"):
        with open(os.path.join(state, "audit.log"), "w") as fh:
            fh.write("\n".join(sub(case["audit_log"], subs)) + "\n")
    if case.get("ai_mcp") is not None:
        with open(os.path.join(ai_home, "ai", "mcp", "context7.json"), "w") as fh:
            fh.write(sub(case["ai_mcp"], subs))
        if case.get("ai_mcp_commit", True):      # the allowlist reads HEAD, not the working tree
            git_env = dict(os.environ, HOME=home, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid",
                           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "mcp"]):
                subprocess.check_call(["git", "-C", ai_home] + args, env=git_env)
    if case.get("gate_skip"):           # owner skip file (root-owned in real use; test-only override below)
        skip_file = os.path.join(tmp, "gate-skip")
        write(skip_file, sub(case["gate_skip"], dict(subs, **{"{{SOON}}": str(int(time.time()) + 600),
                                                                "{{PAST}}": str(int(time.time()) - 60)})) + "\n")
    if case.get("secrets_env"):
        write(os.path.join(home, ".config", "ai", "secrets.env"), sub(case["secrets_env"], subs))
    for rel, text in case.get("state_files", {}).items():      # e.g. upgrades.json from ai-versions --record
        write(os.path.join(state, rel), sub(text, subs))
    if case.get("home_files_for_project"):      # Claude's per-project folder: ~/.claude/projects/<repo key>/
        import re as _re
        key = _re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(proj))
        for rel, text in case["home_files_for_project"].items():
            write(os.path.join(home, ".claude", "projects", key, rel), sub(text, subs))

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "AI_STATE_DIR": state,
           "AI_ROUTING_JSON": os.path.join(build, "routing.json"), "AI_HOME": ai_home, "AI_NOTIFY_DRY": "1",
           "LANG": "C.UTF-8",
           # never the host's /etc/claude-code/managed-settings.json (a server has real excludedCommands)
           "AI_CLAUDE_MANAGED_SETTINGS": os.path.join(tmp, "no-managed-settings.json"),
           "AI_GRAPHIFY_BIN": os.path.join(tmp, "no-graphify")}      # never start the host's graphify
    env.update(sub(case.get("env", {}), subs))
    if case.get("gate_skip"):
        env.update({"AI_GATE_SKIP_FILE": os.path.join(tmp, "gate-skip"), "AI_GATE_SKIP_INSECURE_TEST": "1"})
    agent = case.get("agent", "claude")
    steps = case.get("steps") or [{"event": case["event"], "payload": case.get("payload", {})}]
    session = "test-" + os.path.basename(tmp)
    fired_before, out, code, elapsed = 0, "", 0, 0.0
    for step in steps:
        for row in step.get("transcript_append", []):
            with open(transcript, "a") as fh:
                fh.write(json.dumps(row) + "\n")
        for rel, text in step.get("state_files", {}).items():      # e.g. an emptied fired.jsonl (log rotation)
            write(os.path.join(state, rel), sub(text, subs))
        payload = sub(step.get("payload", {}), subs)
        payload.setdefault("session_id", session)
        payload.setdefault("cwd", proj)
        payload.setdefault("transcript_path", transcript)
        payload.setdefault("hook_event_name", step["event"])
        fired_before = count_rows(state, "fired.jsonl", rule_id)
        misses_before = count_rows(state, "misses.jsonl", rule_id)
        t0 = time.time()
        res = subprocess.run([sys.executable, ROUTER, "--agent", agent, step["event"]],
                             input=json.dumps(payload).encode(), env=env, cwd=proj,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        elapsed = time.time() - t0
        out = res.stdout.decode() + res.stderr.decode()
        code = res.returncode
    errors = read(os.path.join(state, "router-errors.log"))
    if errors:
        return "router error: " + errors.strip().splitlines()[-1]
    if steps[-1]["event"] == "UserPromptSubmit" and elapsed > 1.0:
        return "UserPromptSubmit took %.2f s (limit 1 s)" % elapsed
    return (judge(sub(case, subs), rule_id, agent, out, code, state, fired_before, misses_before)
            or check_cli_same(rule_id, case, steps, payload, agent, env, proj, out, code, state))


# ---------------------------------------------------------------- ai-check gives the hook's decision (ticket 05)

CHECK_CLI = os.path.join(AI_DIR, "bin", "ai-check")
CHECK_RULES = ("secret-scan", "pr-rules")
CHECKED = []


def check_cli_same(rule_id, case, steps, payload, agent, env, proj, out, code, state):
    """The same command through `ai-check <rule> --command` must give the decision of the hook.
    Only one-step Bash cases without an owner skip compare: ai-check has no session and reads no skip."""
    cmd = (payload.get("tool_input") or {}).get("command") if isinstance(payload.get("tool_input"), dict) else None
    if rule_id not in CHECK_RULES or len(steps) != 1 or steps[0]["event"] != "PreToolUse" or not isinstance(cmd, str) \
            or case.get("gate_skip"):
        return None
    decision = decision_of(out, code, agent)
    if decision and not mentions(out, rule_id):
        return None         # another gate decided first: nothing to compare
    if "(this session: main:" in out:
        return None         # the main: line check needs the session id; ai-check has none (ticket 05, edge case 9)

    want = 1 if decision in ("deny", "deny-without-block") else 0
    res = subprocess.run([sys.executable, CHECK_CLI, rule_id, "--command", cmd, "--dir", payload["cwd"]],
                         env=env, cwd=proj, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    CHECKED.append(rule_id)
    errors = read(os.path.join(state, "router-errors.log"))
    if errors:
        return "ai-check error: " + errors.strip().splitlines()[-1]
    if res.returncode != want:
        return "ai-check exit %d, the hook gave %s; output: %s" % (res.returncode, decision or "allow",
                                                                   short(res.stdout.decode()))
    return None


def judge(case, rule_id, agent, out, code, state, fired_before, misses_before):
    expect = case["expect"]
    new_rows = rows(state, "fired.jsonl", rule_id)[fired_before:]
    fired = [r for r in new_rows if not r.get("log_only")]
    decision = decision_of(out, code, agent)
    if expect == "fire" and not (fired and mentions(out, rule_id)):
        return "expected rule to fire; output: %s" % short(out)
    if expect == "nofire" and (fired or mentions(out, rule_id)):
        return "expected no fire; output: %s" % short(out)
    if expect == "log" and not (new_rows and new_rows[0].get("log_only") and not mentions(out, rule_id)):
        return "expected a log-only row and no context; output: %s" % short(out)
    if expect in ("deny", "ask", "allow", "block"):
        want = None if expect == "allow" else expect
        if decision != want:
            return "expected %s, got %s; output: %s" % (expect, decision or "allow", short(out))
    if expect in ("miss", "nomiss"):
        got = count_rows(state, "misses.jsonl", rule_id) - misses_before
        if (expect == "miss") != (got > 0):
            return "expected %s, misses rows added: %d" % (expect, got)
    for text in as_list(case.get("contains")):
        if text not in out:
            return "output lacks %r; output: %s" % (text, short(out))
    for text in as_list(case.get("not_contains")):
        if text in out:
            return "output has %r" % text
    for name, text in case.get("state_contains", {}).items():
        if text not in (read(os.path.join(state, name)) or ""):
            return "state file %s lacks %r" % (name, text)
    for name, text in case.get("state_not_contains", {}).items():
        if text in (read(os.path.join(state, name)) or ""):
            return "state file %s has %r" % (name, text)
    return None


def decision_of(out, code, agent):
    for line in out.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if data.get("decision") == "block" and "hookSpecificOutput" not in data:
            return "block"          # a Stop hook block (Claude and Codex)
        if agent == "codex" and data.get("decision") == "block":
            return "deny"
        d = data.get("hookSpecificOutput", {}).get("permissionDecision")
        if agent == "codex" and d == "deny":
            return "deny-without-block"
        if d in ("deny", "ask"):
            return d
    return None


def mentions(out, rule_id):
    return ("[ai router: %s]" % rule_id in out or "- %s:" % rule_id in out or "[ai gate %s]" % rule_id in out)


# ---------------------------------------------------------------- setup helpers

def setup_project(proj, spec):
    if spec.get("git") or spec.get("git_init"):
        os.makedirs(os.path.join(proj, ".git"), exist_ok=True)
    if spec.get("git_init"):
        shutil.rmtree(os.path.join(proj, ".git"))
        subprocess.check_call(["git", "init", "-q", proj])
    for rel, text in spec.get("stage", {}).items():      # staged first, so "files" can change them after
        write(os.path.join(proj, rel), text)
        subprocess.check_call(["git", "-C", proj, "add", rel])
    for rel, text in spec.get("files", {}).items():
        write(os.path.join(proj, rel), text)
        if rel.startswith("bin/"):          # stub tools (fake gitleaks) are executable
            os.chmod(os.path.join(proj, rel), 0o755)
    if spec.get("commit"):                  # commit everything (knowledge-check reads HEAD)
        git_env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t",
                       GIT_COMMITTER_EMAIL="t@t.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.check_call(["git", "-C", proj, "add", "-A"], env=git_env)
        subprocess.check_call(["git", "-C", proj, "commit", "-q", "--no-verify", "-m", spec["commit"]], env=git_env)
    for i, files in enumerate(spec.get("extra_commits", [])):     # more commits (diff against HEAD~N)
        for rel, text in files.items():
            write(os.path.join(proj, rel), text)
        subprocess.check_call(["git", "-C", proj, "add", "-A"], env=git_env)
        subprocess.check_call(["git", "-C", proj, "commit", "-q", "--no-verify", "-m", "extra %d" % i], env=git_env)
    if spec.get("branch"):                  # the current branch name (main, master, a feature branch)
        subprocess.check_call(["git", "-C", proj, "symbolic-ref", "HEAD", "refs/heads/" + spec["branch"]])
    if spec.get("worktree"):                # a second git worktree of the same repo
        subprocess.check_call(["git", "-C", proj, "worktree", "add", "-q", "-b", "wt", spec["worktree"]],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for rel, text in spec.get("dirty", {}).items():     # changed after the commit (uncommitted work)
        write(os.path.join(proj, rel), text)
    for rel, days in spec.get("age_days", {}).items():
        old = time.time() - float(days) * 86400
        os.utime(os.path.join(proj, rel), (old, old))
    if spec.get("setup_sh"):
        git_env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t",
                       GIT_COMMITTER_EMAIL="t@t.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.check_call(["bash", "-ec", spec["setup_sh"]], cwd=proj, env=git_env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sub(obj, subs):
    if isinstance(obj, str):
        for k, v in subs.items():
            obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [sub(x, subs) for x in obj]
    if isinstance(obj, dict):
        return {sub(k, subs): sub(v, subs) for k, v in obj.items()}
    return obj


def rows(state, name, rule_id):
    out = []
    for line in (read(os.path.join(state, name)) or "").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("rule") == rule_id:
            out.append(row)
    return out


def count_rows(state, name, rule_id):
    return len(rows(state, name, rule_id))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def as_list(v):
    return [] if v is None else (v if isinstance(v, list) else [v])


def short(text):
    text = " ".join(text.split())
    return text[:300] if text else "(empty)"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
