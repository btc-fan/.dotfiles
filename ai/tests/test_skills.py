#!/usr/bin/env python3
"""Skill tests (enforcement tickets 05 and 06): the skill card budget, the ai-doctor skill stats from the
router logs, and the ai-render checks of the require_skill and strength stop fields.

Router behaviour (card text, skill proof, the gates) is in ai/tests/cases/*.json (test_router.py).
Offline: throwaway state dirs and render output. Nothing touches the real home.
Run: python3 ai/tests/test_skills.py   (bash ai/tests/run.sh runs it too)
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
BIN = os.path.join(AI_DIR, "bin")
HOOKS = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks")
FAILS = []


def main():
    work = tempfile.mkdtemp(prefix="ai-skills-tests-")
    try:
        for test in TESTS_LIST:
            try:
                test(work)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d skills tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- ticket 05: skill card, stats

def t_card_fits_worst_case(work):
    render = load(os.path.join(BIN, "ai-render"), "airender_card")
    skills = rendered(work)["skills"]
    assert len(skills["typed_only"]) == 8, "all 8 typed-only skills: %s" % skills["typed_only"]
    assert not {"create-verification-skill", "maintain-verification-skill"} & set(skills["typed_only"]), \
        "the verification skills are model-invocable (verify-enforcement 01)"
    assert render.card_budget(skills) == "", render.card_budget(skills)
    long_when = dict(skills, must_use=skills["must_use"] + [{"name": "x", "when": "y" * 1500}])
    assert "skill card worst case" in render.card_budget(long_when), "an oversized card must fail ai-render"
    assert "needs a name" in render.card_budget({"must_use": [{"name": "x"}]})


def t_doctor_skill_stats(work):
    state = os.path.join(work, "doctor-state")
    os.makedirs(state)
    now, old = iso(time.time()), iso(time.time() - 40 * 86400)
    rows = [{"ts": now, "kind": "skill", "via": "tool", "skill": "ai-core:ship"},
            {"ts": now, "kind": "skill", "via": "read", "skill": "ship"},
            {"ts": now, "kind": "skill", "via": "expansion", "skill": "to-spec"},
            {"ts": old, "kind": "skill", "via": "tool", "skill": "retro"}]
    write(os.path.join(state, "fired.jsonl"), "".join(json.dumps(r) + "\n" for r in rows))
    rotated = {"ts": now, "kind": "skill", "via": "tool", "skill": "/To-Spec"}     # the log rotated at 5 MB
    write(os.path.join(state, "fired.jsonl.1"), json.dumps(rotated) + "\n")
    misses = [{"ts": now, "rule": "edit-agent-docs"}, {"ts": now, "rule": "edit-agent-docs"},
              {"ts": now, "rule": "docs-lookup"}, {"ts": old, "rule": "edit-agent-docs"}]
    write(os.path.join(state, "misses.jsonl"), "".join(json.dumps(r) + "\n" for r in misses))
    routing = os.path.join(work, "doctor-routing.json")
    write(routing, json.dumps({"rules": [{"id": "edit-agent-docs", "require_skill": "writing-for-agents"},
                                         {"id": "docs-lookup"}]}))
    os.environ["AI_ROUTING_JSON"] = routing
    try:
        doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc_skills")
        doctor.STATE = state
        out = io.StringIO()
        with redirect_stdout(out):
            doctor.report_logs()
    finally:
        del os.environ["AI_ROUTING_JSON"]
    text = out.getvalue()
    assert "last 30 days: skills used ship 2, to-spec 2" in text, text
    assert "retro" not in text.split("last 30 days: skills used")[1].splitlines()[0], "40 days old: not counted"
    assert "last 30 days: gated skill misses edit-agent-docs (writing-for-agents) 2" in text, text


# ---------------------------------------------------------------- ticket 06: require_skill and strength stop

def t_render_checks_skill_rules(work):
    render = load(os.path.join(BIN, "ai-render"), "airender_rules")
    skills = {"must_use": [{"name": "ship", "when": "before gh pr ready"}]}

    def errors(rule):
        return render.validate({"rules": [dict({"id": "r", "scope": "global"}, **rule)], "skills": skills})
    gate = {"strength": "gate", "require_skill": "ship", "trigger": {"tool_before": "Bash", "command": "gh pr ready"}}
    assert errors(gate) == [], "a skill gate needs no hooklib gate: %s" % errors(gate)
    stop = {"strength": "stop", "require_skill": "ship", "trigger": {"prompt": "slow"}}
    assert errors(stop) == [], errors(stop)
    assert any("stop" in e for e in errors(dict(stop, require_skill=None))), "stop without require_skill"
    assert any("prompt" in e for e in errors(dict(stop, trigger={"tool_before": "Bash"}))), "stop needs a prompt"
    assert any("must_use" in e for e in errors(dict(gate, require_skill="tdd"))), "skill not on the card"
    assert any("strength" in e for e in errors(dict(gate, strength="loud"))), "unknown strength"
    routing = rendered(work)
    gated = {r["id"]: (r["strength"], r["require_skill"]) for r in routing["rules"] if r.get("require_skill")}
    assert gated == {"writing-for-agents": ("gate", "writing-for-agents"), "ship": ("gate", "ship")}, gated
    hints = {r["id"]: r["strength"] for r in routing["rules"] if r["id"] in ("diagnosing-bugs", "tdd")}
    assert hints == {}, "rules-that-hold 12: the skill descriptions hold the trigger, no row: %s" % hints
    assert not [r["id"] for r in routing["rules"] if r["strength"] == "stop"], "no stop rule"
    assert [s["name"] for s in routing["skills"]["hints"]] == ["diagnosing-bugs", "tdd"], routing["skills"]
    l0 = open(os.path.join(work, sorted(d for d in os.listdir(work) if d.startswith("render-"))[-1], "L0.md")).read()
    assert "stop = the turn cannot end" not in l0, "no stop rule left: the L0 legend must not name stop"
    assert "| diagnosing-bugs" not in l0, "rules-that-hold 12: no diagnosing-bugs row: " + l0


def t_eval_turns_let_stop_fire(work):
    ev = load(os.path.join(BIN, "ai-eval"), "aieval_turns")
    cmd = ev.agent_cmd("claude", "x")
    turns = int(cmd[cmd.index("--max-turns") + 1])
    assert turns >= 12, "a Stop block needs turns after the first stop: --max-turns %d" % turns


# ---------------------------------------------------------------- ticket 18: verify-ai-setup helper

def t_verify_ai_setup_run(work):
    """The repo's own verify tool: launch, doctor (no agent sessions), one hook drive, cleanup. run.log holds
    exactly the 4 contract lines, the fixtures are gone and the evidence stays."""
    root = os.path.dirname(AI_DIR)
    helper = os.path.join(root, ".agents", "skills", "verify-ai-setup", "verify")
    assert os.access(helper, os.X_OK), "helper missing or not executable: %s" % helper

    def run(*args):
        res = subprocess.run([helper] + list(args), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=600)
        return res.returncode, res.stdout.decode()

    code, out = run("launch", "--label", "selftest", "empty")
    assert code == 0, out
    evidence = out.split("evidence: ", 1)[1].split()[0]
    try:
        fixtures = json.load(open(os.path.join(evidence, "state.json")))["tmp"]
        code, out = run("doctor", "--no-agents")
        assert code == 0 and "doctor: PASS" in out, out
        code, out = run("drive", "hook", "PreToolUse",
                        '{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}')
        assert code == 0 and "decision: deny" in out and "merge-approval" in out, out
        code, out = run("cleanup")
        assert code == 0, out

        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], stdout=subprocess.PIPE).stdout.decode().strip()
        lines = open(os.path.join(evidence, "run.log")).read().splitlines()
        assert len(lines) == 4 and lines[:3] == ["commit: " + head, "doctor: PASS", "db_writes: no"], lines
        assert lines[3].startswith("finished: ") and lines[3].endswith("Z") and "T" in lines[3], lines
        assert not os.path.exists(fixtures), "cleanup left the fixtures: " + fixtures
        assert any(n.endswith("-hook.txt") for n in os.listdir(evidence)), os.listdir(evidence)
    finally:
        shutil.rmtree(evidence, ignore_errors=True)       # the test's own run; real runs keep their evidence


# ---------------------------------------------------------------- ticket 17: wall log, 7-day table

def t_doctor_wall_table(work):
    """Two real fires (a router gate deny, an ai-adopt refusal) and an old row: ai-doctor shows a 7-day table
    per wall with the fires and the last 3 short reasons."""
    state = os.path.join(work, "walls-state")
    home = os.path.join(work, "walls-home")
    proj = os.path.join(home, "proj")
    os.makedirs(proj)
    subprocess.check_call(["git", "init", "-q", proj])
    env = dict(os.environ, AI_STATE_DIR=state, HOME=home, AI_NOTIFY_DRY="1")
    payload = {"hook_event_name": "PreToolUse", "session_id": "w1", "cwd": proj, "tool_name": "Bash",
               "tool_input": {"command": "git commit --no-verify -m wip"}}
    res = subprocess.run([sys.executable, os.path.join(HOOKS, "router.py"), "--agent", "claude", "PreToolUse"],
                         input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    assert b'"deny"' in res.stdout, res.stdout
    res = subprocess.run([sys.executable, os.path.join(BIN, "ai-start"), "--dir", home, "--init"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    assert res.returncode == 1 and b"refused" in res.stdout, res.stdout
    old = {"ts": iso(time.time() - 8 * 86400), "host": "m", "repo": "", "wall": "secret-scan", "reason": "old"}
    with open(os.path.join(state, "walls.jsonl"), "a") as fh:
        fh.write(json.dumps(old) + "\n")
    doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc_walls")
    doctor.STATE = state
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.report_walls()
    text = out.getvalue()
    assert "walls, last 7 days" in text, text
    rows = {ln.split()[0]: ln for ln in text.splitlines()[1:] if ln.strip()}
    assert set(rows) == {"no-verify", "ai-adopt"}, "8 days old: not counted: " + text
    assert rows["no-verify"].split()[1] == "1" and "--no-verify" in rows["no-verify"], text
    assert rows["ai-adopt"].split()[1] == "1" and "--init" in rows["ai-adopt"], text


# ---------------------------------------------------------------- helpers

def rendered(work):
    out = os.path.join(work, "render-%d" % len(os.listdir(work)))
    res = subprocess.run([sys.executable, os.path.join(BIN, "ai-render"), "--profile", "dev-mac", "--out", out],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.returncode == 0, res.stdout.decode()
    with open(os.path.join(out, "routing.json")) as fh:
        return json.load(fh)


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def load(path, name):
    sys.path.insert(0, HOOKS)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    loader.exec_module(mod)
    return mod


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def t_release_runs_maintain(work):
    """Ticket 06: the release skill runs maintain-verification-skill itself (model-invocable since ticket 01)."""
    def text(name):
        with open(os.path.join(AI_DIR, "skills", name, "SKILL.md"), encoding="utf-8") as fh:
            return fh.read()
    release = text("release")
    assert "maintain-verification-skill" in release and "verify-<app>" in release, "release skill: no maintain pass"
    head = text("maintain-verification-skill").split("\n---", 1)[0]
    assert "disable-model-invocation" not in head, "maintain-verification-skill must stay model-invocable"


# ---------------------------------------------------------------- rules-that-hold 12: triggers in skills

def t_feature_kickoff_skill(work):
    """feature-kickoff is model-invocable, its description holds the trigger words (EN, RO, RU) under 300
    characters, its body points to the skills of the flow, and no other skill in this repo has its name."""
    path = os.path.join(AI_DIR, "skills", "feature-kickoff", "SKILL.md")
    text = open(path, encoding="utf-8").read()
    head = text.split("---")[1]
    assert "name: feature-kickoff\n" in head and "disable-model-invocation" not in head, head
    desc = head.split("description:", 1)[1].strip().strip("'")
    assert len(desc) < 300, "description has %d characters (listing budget)" % len(desc)
    for word in ("add", "build", "implement", "feature", "endpoint", "page", "adaugă", "добавь"):
        assert word in desc, "trigger word %r missing from the description" % word
    for skill in ("grill-with-docs", "grilling", "to-spec", "to-tickets", "implement", "verify-<app>", "ship",
                  "worktree", "check-fast"):
        assert skill in text, "the flow does not name %s" % skill
    clash = []
    for root, _dirs, files in os.walk(os.path.dirname(AI_DIR)):
        if "SKILL.md" in files and os.path.join(root, "SKILL.md") != path and ".git" not in root:
            if "\nname: feature-kickoff\n" in open(os.path.join(root, "SKILL.md"), encoding="utf-8").read():
                clash.append(root)
    assert not clash, "another skill is named feature-kickoff: %s" % clash


def t_workflow_rows_left(work):
    """The 6 workflow rows send no prompt reminder: feature-grill, tdd and diagnosing-bugs are gone; ui, seo and
    blog stay only as the ai-adopt catalog (trigger: {}). Each has 1 index line in the rules file."""
    out = os.path.join(work, "rows-render")
    subprocess.check_call([sys.executable, os.path.join(BIN, "ai-render"), "--profile", "dev-mac", "--out", out],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rules = {r["id"]: r for r in json.load(open(os.path.join(out, "routing.json")))["rules"]}
    for rid in ("feature-grill", "tdd", "diagnosing-bugs", "project-knowledge"):
        assert rid not in rules, rid + " is still a router row"
    for rid in ("ui", "seo", "blog", "serena", "graph"):
        assert rules[rid]["scope"] == "opt-in" and rules[rid]["trigger"] == {} and "when" not in rules[rid], rules[rid]
    agents = open(os.path.join(out, "AGENTS.md"), encoding="utf-8").read()
    for line in ("the feature-kickoff skill.", "the tdd skill.", "the diagnosing-bugs skill.", "ui-ux-pro-max; read",
                 "the claude-seo skills.", "the claude-blog skills."):
        hit = [ln for ln in agents.splitlines() if line in ln]
        assert len(hit) == 1 and len(hit[0].split()) < 20, "index line %r: %s" % (line, hit)
    l0 = open(os.path.join(out, "L0.md"), encoding="utf-8").read()
    assert "| ui (opt-in)" not in l0 and "| serena (opt-in)" not in l0, "a catalog entry is not a table row"


TESTS_LIST = [t_release_runs_maintain, t_card_fits_worst_case, t_doctor_skill_stats, t_render_checks_skill_rules, t_eval_turns_let_stop_fire,
              t_verify_ai_setup_run, t_doctor_wall_table, t_feature_kickoff_skill, t_workflow_rows_left]

if __name__ == "__main__":
    sys.exit(main())
