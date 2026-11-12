#!/usr/bin/env python3
"""Router tests: hook JSON on stdin for every rule in routing.yaml (should-fire and should-not-fire).

Run: bash ai/tests/run.sh   (or python3 ai/tests/test_router.py [-k <name part>] [-v])

Each ai/tests/cases/<rule>.json holds {"rule": id, "cases": [...]}. A case:
  name     text
  expect   fire | nofire | log | deny | ask | allow | miss | nomiss
           (fire/nofire/log: did the rule fire in the LAST step; deny/ask/allow: the gate decision)
  steps    [{event, payload, transcript_append: [json rows]}]  (or one "event" + "payload")
  agent    claude (default) | codex
  project  {git: true, git_init: true, files: {rel: text}, stage: {rel: text}, commit: "<message>"}
  audit_log  lines for ~/.local/state/ai/audit.log
  ai_mcp   text for $AI_HOME/ai/mcp/context7.json, committed (secret-scan allowlist reads HEAD);
           ai_mcp_commit: false keeps it uncommitted
  secrets_env  text for ~/.config/ai/secrets.env
  env      extra environment for the router (e.g. AI_STATE_DIR pointing at a file: unwritable state)
  gate_skip  a line for the owner skip file (/etc/ai/gate-skip); {{SOON}} / {{PAST}} = expiry times
  contains / not_contains   text that must (not) be in the hook output
Placeholders: {{PROJ}} {{NOW}} {{OLD}} {{TRANSCRIPT}} and fake secrets {{GH_TOKEN}} {{CTX7_KEY}}
{{CTX7_OTHER}} {{PW}} {{ENVTOK}} {{NPM_TOKEN}} {{HF_TOKEN}} {{DBURL}}
(fake secrets are built here at run time, so no secret-looking string is stored in the repo).
Every run uses a throwaway HOME and state dir. Nothing touches the real home.
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
}
FIRE_KINDS = {"fire", "log", "deny", "ask", "miss"}
QUIET_KINDS = {"nofire", "allow", "nomiss"}


def main(argv):
    verbose = "-v" in argv
    only = argv[argv.index("-k") + 1] if "-k" in argv else None
    work = tempfile.mkdtemp(prefix="ai-router-tests-")
    try:
        build = os.path.join(work, "build")
        res = subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--out", build],
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
        print("\n%d cases, %d failed" % (total, len(failures)))
        for f in failures:
            if "->" not in f:
                print("FAIL " + f)
        return 1 if failures else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
    subs = dict(FAKE, **{"{{PROJ}}": proj, "{{NOW}}": NOW, "{{OLD}}": OLD, "{{TRANSCRIPT}}": transcript})

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

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "AI_STATE_DIR": state,
           "AI_ROUTING_JSON": os.path.join(build, "routing.json"), "AI_HOME": ai_home, "AI_NOTIFY_DRY": "1",
           "LANG": "C.UTF-8"}
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
    return judge(sub(case, subs), rule_id, agent, out, code, state, fired_before, misses_before)


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
    if expect in ("deny", "ask", "allow"):
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
