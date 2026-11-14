#!/usr/bin/env python3
"""Tier 1 tests: ai-check-detect, ai-adopt check targets / tier / Done, the ai-doctor budget checks.

Offline: throwaway repos and HOME, fake uv / claude on PATH. Nothing touches the real home.
Run: python3 ai/tests/test_tier1.py   (bash ai/tests/run.sh runs it too)
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
from contextlib import redirect_stdout

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
BIN = os.path.join(AI_DIR, "bin")
HOOKS = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks")
FAILS = []
FAKE_UV = "#!/bin/sh\necho \"3 passed in 0.02s\"\n"


def main():
    work = tempfile.mkdtemp(prefix="ai-tier1-tests-")
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
    print("%d tier1 tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- T1: ai-check-detect

def t_detect_python_uv(work):
    repo = tree(work, "py-uv", {"pyproject.toml": "[project]\nname='x'\n[tool.ruff]\nline-length=100\n",
                                "uv.lock": "", "tests/test_a.py": "def test_a(): pass\n"})
    info = detect(repo)
    assert info["ok"] and info["fast"] == ["uv run ruff check .", "uv run pytest -x -q"], info
    assert info["full"] == ["uv run ruff check .", "uv run pytest -q"] and info["runner"] == "make", info


def t_detect_python_pip(work):
    repo = tree(work, "py-pip", {"requirements.txt": "flask==3.0\npytest==8.0\n", "app.py": "x = 1\n"})
    info = detect(repo)
    assert info["ok"] and info["fast"] == ["python3 -m pytest -x -q"], info
    assert any("no ruff config" in n for n in info["notes"]), info
    repo2 = tree(work, "py-notest", {"pyproject.toml": "[project]\nname='x'\n"})
    info = detect(repo2)
    assert not info["ok"] and "no test or lint command" in info["refuse"], info


def t_detect_node(work):
    scripts = {"lint": "eslint .", "test": "vitest run", "typecheck": "tsc --noEmit"}
    for lock, pm, want in (("package-lock.json", "npm", "npm run test"), ("pnpm-lock.yaml", "pnpm", "pnpm run test"),
                           ("yarn.lock", "yarn", "yarn test"), ("bun.lockb", "bun", "bun run test")):
        repo = tree(work, "node-" + pm, {"package.json": json.dumps({"scripts": scripts}), lock: ""})
        info = detect(repo)
        assert info["ok"] and info["fast"][-1] == want and len(info["full"]) == 3, (pm, info)
    repo = tree(work, "node-placeholder", {"package.json": json.dumps(
        {"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}})})
    assert not detect(repo)["ok"], "the npm placeholder test script must not count"


def t_detect_go_rust(work):
    info = detect(tree(work, "go", {"go.mod": "module x\n", ".golangci.yml": ""}))
    assert info["fast"] == ["go vet ./...", "go test -short ./..."] and "golangci-lint run" in info["full"], info
    info = detect(tree(work, "rust", {"Cargo.toml": "[package]\nname='x'\n"}))
    assert info["fast"][-1] == "cargo test -q" and "clippy" in info["fast"][0], info


def t_detect_monorepo(work):
    for name, files in (("pnpm-ws", {"package.json": "{}", "pnpm-workspace.yaml": "packages: ['a']\n"}),
                        ("npm-ws", {"package.json": json.dumps({"workspaces": ["packages/*"]})}),
                        ("go-work", {"go.work": "go 1.22\n", "go.mod": "module x\n"}),
                        ("nested", {"apps/web/package.json": "{}", "apps/api/pyproject.toml": "[project]\n"})):
        repo = tree(work, "mono-" + name, files)
        res = run([sys.executable, os.path.join(BIN, "ai-check-detect"), "--dir", repo])
        assert res.returncode == 2 and "monorepo" in res.stdout, (name, res.stdout)


def t_plan_keeps_targets(work):
    mod = load(os.path.join(BIN, "ai-check-detect"), "acd")
    repo = tree(work, "plan-keep", {"go.mod": "module x\n", "Makefile": "check-fast:\n\tgo test ./pkg/...\n"})
    p = mod.plan(repo, mod.detect(repo), "mvp")
    assert p["kept"] == ["check-fast"] and "check-fast:" not in p["text"].split(mod.BLOCK_START)[1], p
    assert p["text"].startswith("check-fast:\n\tgo test ./pkg/...\n"), "owner target changed: " + p["text"]
    write(os.path.join(repo, "Makefile"), p["text"])
    assert mod.plan(repo, mod.detect(repo), "mvp")["text"] is None, "a rerun must change nothing"
    p = mod.plan(repo, mod.detect(repo), "long")
    assert "ai-ratchet" in p["text"] and "ai-ledger --check" in p["text"], "long tier adds ledger and ratchet"
    just = tree(work, "plan-just", {"go.mod": "module x\n", "justfile": "build:\n    go build\n"})
    p = mod.plan(just, mod.detect(just), "mvp")
    assert p["file"] == "justfile" and "\n    go vet ./...\n" in p["text"] and p["fast_cmd"] == "just check-fast", p


# ---------------------------------------------------------------- T1 + T5: ai-adopt

def t_adopt_try_tier_own_done(work):
    repo, env = adopt_repo(work, "own-done", {
        "Makefile": "check:\n\tuv run pytest\n",
        "AGENTS.md": "# own\n\n## Done\n- tests pass\n- docs updated\n"})
    res = adopt(repo, env, "--tier", "try")
    assert res.returncode == 0, res.stdout
    assert "keep: AGENTS.md has its own Done section" in res.stdout, res.stdout
    assert "keep: Makefile already has a check target" in res.stdout, res.stdout
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert agents.count("## Done") == 1 and "<!-- AI:done" not in agents, agents
    mk = read(os.path.join(repo, "Makefile"))
    assert mk.startswith("check:\n\tuv run pytest\n") and mk.count("\ncheck:") == 0 and "check-fast:" in mk, mk
    assert "tier: try" in read(os.path.join(repo, ".ai", "enabled")).splitlines()
    assert not os.path.exists(os.path.join(repo, "docs", "REGRESSIONS.md")), "try tier gets no ledger"
    assert "nothing to change" in adopt(repo, env).stdout, "rerun keeps the tier and changes nothing"


def t_adopt_long_tier(work):
    repo, env = adopt_repo(work, "long", {})
    res = adopt(repo, env, "--tier", "long")
    assert res.returncode == 0, res.stdout
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    for rel in ("docs/REGRESSIONS.md", "Makefile", ".ai/enabled", ".ai/ratchet.json"):
        assert rel in files, "%s not committed: %s" % (rel, files)
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert "a line in docs/REGRESSIONS.md" in agents, agents
    assert "ai-ratchet" in read(os.path.join(repo, "Makefile"))
    # tier change: the managed Done block and the check block follow the new tier
    res = adopt(repo, env, "--tier", "mvp")
    assert "a line in docs/REGRESSIONS.md" not in read(os.path.join(repo, "AGENTS.md")), "Done block not updated"
    assert "ai-ratchet" not in read(os.path.join(repo, "Makefile")), "check block not updated"


def t_adopt_monorepo_refused(work):
    repo, env = adopt_repo(work, "mono", {"pnpm-workspace.yaml": "packages: ['a']\n", "package.json": "{}"})
    res = adopt(repo, env)
    assert res.returncode == 0 and "skip check targets: monorepo" in res.stdout, res.stdout
    assert not os.path.exists(os.path.join(repo, "Makefile")), "monorepo: nothing written"


# ---------------------------------------------------------------- mattpocock opt-in skills per project

OPTIN = ("grill-with-docs", "domain-modeling", "to-spec", "to-tickets", "tdd", "codebase-design", "code-review", "pr",
         "diagnosing-bugs", "improve-codebase-architecture")
DEFAULT_LINKS = ["grill-with-docs", "domain-modeling", "to-spec", "to-tickets", "tdd", "codebase-design", "code-review"]


def fake_plugin_src(work, name, skip=()):
    base = os.path.join(work, "plugins-" + name)
    for n in OPTIN:
        if n not in skip:
            write(os.path.join(base, "mattpocock-skills", n, "SKILL.md"), "---\nname: %s\n---\n" % n)
    return base


def links(repo, sub):
    d = os.path.join(repo, sub)
    return sorted(n for n in os.listdir(d) if os.path.islink(os.path.join(d, n))) if os.path.isdir(d) else []


def t_adopt_project_skills(work):
    repo, env = adopt_repo(work, "skills-mvp", {})
    env["AI_PLUGIN_SRC"] = fake_plugin_src(work, "mvp", skip=("pr",))
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    enabled = read(os.path.join(repo, ".ai", "enabled")).splitlines()
    assert "skills: grill-with-docs, domain-modeling, to-spec, to-tickets, tdd" in enabled, enabled
    for sub in (".claude/skills", ".agents/skills"):
        assert links(repo, sub) == sorted(DEFAULT_LINKS), (sub, links(repo, sub))
    target = os.readlink(os.path.join(repo, ".agents", "skills", "tdd"))
    assert target == os.path.join(env["AI_PLUGIN_SRC"], "mattpocock-skills", "tdd"), target
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    assert "docs/agents/issue-tracker.md" in files and "docs/agents/domain.md" in files, files
    assert not any(f.startswith((".claude/skills", ".agents/skills")) for f in files), "machine links committed: %s" % files
    assert "docs/tickets/" in read(os.path.join(repo, "docs", "agents", "issue-tracker.md"))
    assert run(["git", "-C", repo, "status", "--porcelain"]).stdout.strip() == "", run(["git", "-C", repo, "status"]).stdout
    assert "nothing to change" in adopt(repo, env).stdout, "a rerun changes nothing"
    # the owner narrows the list: our other links go, a project's own folder stays
    write(os.path.join(repo, ".agents", "skills", "pr", "SKILL.md"), "own\n")
    res = adopt(repo, env, "--skills", "tdd,pr")
    assert "skip skill links pr: not installed" in res.stdout, res.stdout
    assert links(repo, ".agents/skills") == ["code-review", "codebase-design", "tdd"], links(repo, ".agents/skills")
    assert read(os.path.join(repo, ".agents", "skills", "pr", "SKILL.md")) == "own\n", "the project's own folder"
    assert "skills: tdd, pr" in read(os.path.join(repo, ".ai", "enabled")).splitlines()


def t_adopt_try_no_skills(work):
    repo, env = adopt_repo(work, "skills-try", {})
    env["AI_PLUGIN_SRC"] = fake_plugin_src(work, "try")
    res = adopt(repo, env, "--tier", "try")
    assert res.returncode == 0, res.stdout
    assert "skills: none" in read(os.path.join(repo, ".ai", "enabled")).splitlines()
    assert links(repo, ".claude/skills") == [] and links(repo, ".agents/skills") == [], "try tier: plain grilling only"
    assert not os.path.exists(os.path.join(repo, "docs", "agents")), "no tracker docs without to-spec/to-tickets"


# ---------------------------------------------------------------- T5: ai-doctor budget

def t_doctor_budget(work):
    doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc")
    sys.path.insert(0, HOOKS)
    import hooklib
    repo = tree(work, "doc-budget", {".ai/enabled": "tier: long\n", "Makefile": "check-fast:\n\ttrue\ncheck:\n\ttrue\n",
                                     "AGENTS.md": "# x\n\n## Done\n" + "".join("%d. item\n" % i for i in range(1, 9))
                                     + "\n## Lessons\n" + "".join("- lesson %d\n" % i for i in range(16))})
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_tier1(repo, hooklib, read(os.path.join(repo, "AGENTS.md")))
    text = out.getvalue()
    for want in ("WARN AGENTS.md Done section (8 of 6 lines)", "WARN AGENTS.md Lessons section (16 of 15 lines)",
                 "PASS project tier long; check-fast and check targets", "WARN ratchet baseline .ai/ratchet.json",
                 "PASS root rules + repo AGENTS.md"):
        assert want in text, "%r not in:\n%s" % (want, text)
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_destroy_smoke()
    assert out.getvalue().startswith("PASS no-destroy blocks"), out.getvalue()
    big = tree(work, "doc-big", {"AGENTS.md": "# x\n" + "y" * 40000})
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_tier1(big, hooklib, read(os.path.join(big, "AGENTS.md")))
    assert "FAIL root rules + repo AGENTS.md" in out.getvalue() and "WARN repo AGENTS.md size" in out.getvalue(), \
        out.getvalue()


# ---------------------------------------------------------------- T2: stop-check

STOP = os.path.join(HOOKS, "stop-check.py")
STOP_MAKEFILE = "check-fast:\n\t@echo run >> \"$$MARK\"\n\t@sh check.sh\n"
PASS_SH = "echo '3 passed in 0.01s'\n"
FAIL_SH = "echo 'FAILED tests/test_a.py::test_price - assert 1 == 2'\necho '1 failed, 2 passed'\nexit 1\n"


def stop_repo(work, name, check_sh=FAIL_SH, enabled="tier: mvp\n"):
    repo = tree(work, name, {"Makefile": STOP_MAKEFILE, "check.sh": check_sh, "src/app.py": "x = 1\n"})
    if enabled is not None:
        write(os.path.join(repo, ".ai", "enabled"), enabled)
    run(["git", "init", "-q", repo])
    env = git_env(work, name)
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "init"], env=env)
    return repo, env


def git_env(work, name):
    home = os.path.join(work, "home-" + name)
    os.makedirs(home, exist_ok=True)
    return {"HOME": home, "AI_STATE_DIR": os.path.join(home, "state"), "MARK": os.path.join(home, "mark"),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid", "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t.invalid", "AI_HOME": os.path.dirname(AI_DIR)}


def hook(repo, env, event, agent="claude", session="s1", **extra):
    payload = dict({"session_id": session, "cwd": repo, "hook_event_name": event}, **extra)
    res = run([sys.executable, STOP, "--agent", agent, event], env=env, stdin=json.dumps(payload), timeout=90)
    assert res.returncode == 0, "stop-check exit %d: %s" % (res.returncode, res.stdout)
    out = res.stdout.strip()
    return json.loads(out) if out else None


def runs(env):
    return len((read(env["MARK"]) or "").splitlines())


def t_stop_no_change_no_run(work):
    repo, env = stop_repo(work, "stop-nochange")
    write(os.path.join(repo, "src", "dirty.py"), "y = 1\n")     # dirty before the session: not the agent's
    assert hook(repo, env, "SessionStart") is None, "SessionStart must print nothing"
    assert hook(repo, env, "Stop") is None and runs(env) == 0, "no change since the baseline: no run"
    assert hook(repo, env, "SessionStart", source="compact") is None
    assert hook(repo, env, "Stop") is None and runs(env) == 0, "compact keeps the first baseline"


def t_stop_blocks_twice_then_stops(work):
    repo, env = stop_repo(work, "stop-fail")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    for i in (1, 2):
        out = hook(repo, env, "Stop")
        assert out and out.get("decision") == "block", "try %d: %s" % (i, out)
        assert "make check-fast failed (exit 2)" in out["reason"] and "FAILED tests/test_a.py" in out["reason"], out
        assert "block %d of 2" % i in out["reason"], out["reason"]
    out = hook(repo, env, "Stop")
    assert out and "decision" not in out and "not blocking again" in out.get("systemMessage", ""), out
    assert hook(repo, env, "Stop") is None, "told once: silent after"
    assert runs(env) == 2, "the check ran %d times, want 2" % runs(env)
    write(os.path.join(repo, "src", "app.py"), "x = 3\n")       # new files: a new try count
    assert hook(repo, env, "Stop")["decision"] == "block"


def t_stop_hook_active_silent(work):
    repo, env = stop_repo(work, "stop-active")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    assert hook(repo, env, "Stop", stop_hook_active=True) is None and runs(env) == 0, "stop_hook_active: no run"


def t_stop_success_silent_both_agents(work):
    for agent in ("claude", "codex"):
        repo, env = stop_repo(work, "stop-ok-" + agent, check_sh=PASS_SH)
        hook(repo, env, "SessionStart", agent=agent)
        write(os.path.join(repo, "new_file.py"), "z = 1\n")        # untracked file counts as a change
        assert hook(repo, env, "Stop", agent=agent) is None and runs(env) == 1, agent
        assert hook(repo, env, "Stop", agent=agent) is None and runs(env) == 1, "green tree is not checked again"
        write(os.path.join(repo, "new_file.py"), "z = 22\n")       # an edit of an untracked file is a change
        assert hook(repo, env, "Stop", agent=agent) is None and runs(env) == 2, agent


def t_stop_codex_block_and_timeout(work):
    repo, env = stop_repo(work, "stop-codex")
    hook(repo, env, "SessionStart", agent="codex")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    out = hook(repo, env, "Stop", agent="codex", turn_id="t1")
    assert out and out["decision"] == "block" and set(out) == {"decision", "reason"}, out
    slow, env2 = stop_repo(work, "stop-slow", check_sh="sleep 5\n")
    env2["AI_STOP_CHECK_TIMEOUT"] = "1"
    hook(slow, env2, "SessionStart")
    write(os.path.join(slow, "src", "app.py"), "x = 2\n")
    out = hook(slow, env2, "Stop")
    assert out and "ran over 1 s" in out.get("systemMessage", "") and "decision" not in out, out
    write(os.path.join(slow, "src", "app.py"), "x = 3\n")
    assert hook(slow, env2, "Stop", agent="codex") is None, "Codex: a timeout prints nothing"


def t_stop_floor_zero_tests(work):
    repo, env = stop_repo(work, "stop-floor", check_sh="echo 'collected 0 items'\necho 'no tests ran in 0.01s'\n")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    out = hook(repo, env, "Stop")
    assert out and out["decision"] == "block" and "ran 0 tests" in out["reason"], out
    lint_only, env2 = stop_repo(work, "stop-lintonly", check_sh="echo 'All checks passed!'\n")
    hook(lint_only, env2, "SessionStart")
    write(os.path.join(lint_only, "src", "app.py"), "x = 2\n")
    assert hook(lint_only, env2, "Stop") is None, "no test runner output: cannot tell, so it passes"


def t_stop_off_switches(work):
    for name, enabled in (("stop-try", "tier: try\n"), ("stop-optout", "no-stop-check\n"), ("stop-noadopt", None)):
        repo, env = stop_repo(work, name, enabled=enabled)
        hook(repo, env, "SessionStart")
        write(os.path.join(repo, "src", "app.py"), "x = 2\n")
        assert hook(repo, env, "Stop") is None and runs(env) == 0, name


def omc_state(repo, session, mode="ralph", age_s=0, scoped=True):
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(time_now() - age_s, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    d = os.path.join(repo, ".omc", "state", "sessions", session) if scoped else os.path.join(repo, ".omc", "state")
    write(os.path.join(d, "%s-state.json" % mode), json.dumps(
        {"active": True, "session_id": session, "iteration": 1, "max_iterations": 10, "started_at": ts,
         "last_checked_at": ts}))


def time_now():
    import time
    return time.time()


def t_stop_omc_coexistence(work):
    """oh-my-claudecode persistent modes block Stop themselves (and never when stop_hook_active). While one is
    active for this session, stop-check stays silent: one stop never gets two blocks, and the chain ends."""
    repo, env = stop_repo(work, "stop-omc")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    omc_state(repo, "s1")
    assert hook(repo, env, "Stop") is None and runs(env) == 0, "OMC ralph active: OMC owns this stop"
    assert hook(repo, env, "Stop", stop_hook_active=True) is None, "the continuation stop: both silent"
    omc_state(repo, "other-session")
    os.remove(os.path.join(repo, ".omc", "state", "sessions", "s1", "ralph-state.json"))
    out = hook(repo, env, "Stop")
    assert out and out["decision"] == "block", "another session's OMC mode must not silence this one: %s" % out
    omc_state(repo, "s1", age_s=3 * 3600)                     # stale: OMC ignores it, so we check
    write(os.path.join(repo, "src", "app.py"), "x = 3\n")
    assert hook(repo, env, "Stop")["decision"] == "block", "stale OMC state must not silence the check"
    omc_state(repo, "s1", mode="autopilot", scoped=False)     # legacy (unscoped) state of this session
    write(os.path.join(repo, "src", "app.py"), "x = 4\n")
    assert hook(repo, env, "Stop") is None, "legacy OMC state with this session id"


# ---------------------------------------------------------------- T3: regression ledger

LEDGER = """# Regressions
## Ledger
R-012 | 2026-11-12 | area: src/billing/ | symptom: double refund | cause: retry path skipped the lock |
        test: tests/regressions/test_r012_refund_once.py | reopened: 1
## Quarantine
"""


def ledger_repo(work, name, ledger=LEDGER, extra=None):
    files = {"docs/REGRESSIONS.md": ledger, "src/billing/refund.py": "x = 1\n",
             "tests/regressions/test_r012_refund_once.py": "def test_refund_once(): pass\n",
             ".ai/enabled": "tier: long\n", "Makefile": STOP_MAKEFILE, "check.sh": PASS_SH}
    files.update(extra or {})
    repo = tree(work, name, files)
    env = git_env(work, name)
    run(["git", "init", "-q", repo])
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "init"], env=env)
    return repo, env


def ledger_check(repo, env):
    return run([sys.executable, os.path.join(BIN, "ai-ledger"), "--check", "--dir", repo], env=env)


def t_ledger_check_honest(work):
    import datetime
    repo, env = ledger_repo(work, "ledger-ok")
    res = ledger_check(repo, env)
    assert res.returncode == 0 and "1 rows" in res.stdout, res.stdout
    ledger = os.path.join(repo, "docs", "REGRESSIONS.md")
    cases = [
        ("missing test file", LEDGER.replace("test_r012_refund_once.py", "test_r012_gone.py"), "does not exist"),
        ("test name without the id", LEDGER.replace("test_r012_refund_once.py", "test_refund.py"), "does not carry"),
        ("row removed", "# Regressions\n## Ledger\n## Quarantine\n", "R-012 was removed"),
        ("reopened went down", LEDGER.replace("reopened: 1", "reopened: 0"), "reopened went down 1 -> 0"),
        ("malformed row", LEDGER.replace("## Quarantine", "R-013 | 2026-11-13 | symptom: x\n## Quarantine"),
         "row misses"),
        ("old quarantine date added", LEDGER + "- tests/test_a.py::test_x | since: 2026-01-01 | timing\n",
         "added with an old date"),
    ]
    for label, text, want in cases:
        write(ledger, text)
        res = ledger_check(repo, env)
        assert res.returncode == 1 and want in res.stdout, "%s: %s" % (label, res.stdout)
    today = datetime.date.today().isoformat()
    write(ledger, LEDGER + "- tests/test_a.py::test_x | since: %s | timing\n" % today)
    res = ledger_check(repo, env)
    assert res.returncode == 0, "a new quarantine line with today's date is fine: " + res.stdout
    write(ledger, LEDGER)
    write(os.path.join(repo, "tests", "regressions", "test_r099_orphan.py"), "def test_x(): pass\n")
    res = ledger_check(repo, env)
    assert res.returncode == 1 and "test_r099_orphan.py has no ledger row" in res.stdout, res.stdout


def t_ledger_quarantine_clock(work):
    old = LEDGER + "- tests/test_a.py::test_x | since: 2026-01-01 | timing\n"
    repo, env = ledger_repo(work, "ledger-q", ledger=old)
    res = ledger_check(repo, env)
    assert res.returncode == 0 and "WARN quarantine tests/test_a.py::test_x since 2026-01-01" in res.stdout, res.stdout
    write(os.path.join(repo, "docs", "REGRESSIONS.md"), old.replace("2026-01-01", "2026-11-14"))
    res = ledger_check(repo, env)
    assert res.returncode == 1 and "since changed" in res.stdout, res.stdout
    moved = LEDGER.replace("area: src/billing/", "area: src/payments/")
    write(os.path.join(repo, "docs", "REGRESSIONS.md"), moved)
    res = ledger_check(repo, env)
    assert res.returncode == 0 and "area src/payments/ matches no tracked file" in res.stdout, res.stdout


def t_ledger_stop_note(work):
    repo, env = ledger_repo(work, "ledger-stop")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "billing", "refund.py"), "x = 2\n")     # like sed -i: no Edit hook saw it
    out = hook(repo, env, "Stop")
    assert out and "R-012" in out.get("systemMessage", "") and "decision" not in out, out
    write(os.path.join(repo, "src", "billing", "refund.py"), "x = 3\n")
    assert hook(repo, env, "Stop") is None, "one note per area per session"
    repo2, env2 = ledger_repo(work, "ledger-stop-nudged")
    write(os.path.join(env2["AI_STATE_DIR"], "sessions", "s1.json"), json.dumps({"ledger_areas": ["src/billing/"]}))
    hook(repo2, env2, "SessionStart")
    write(os.path.join(repo2, "src", "billing", "refund.py"), "x = 2\n")
    assert hook(repo2, env2, "Stop") is None, "the edit nudge already named this area"
    assert hook(repo2, env2, "Stop", agent="codex") is None


# ---------------------------------------------------------------- T7: ai-ratchet

FAKE_RUFF = """#!/bin/sh
# ruff check --output-format json: one finding per LINT word under src/
n=$(grep -ro LINT src 2>/dev/null | wc -l | tr -d ' ')
printf '['; i=0
while [ "$i" -lt "$n" ]; do [ "$i" -gt 0 ] && printf ','; printf '{"code": "F401"}'; i=$((i+1)); done
printf ']\\n'
"""
PY_TESTS = """import pytest

def test_a():
    assert 1

def test_b():
    assert 2

@pytest.mark.skip(reason="flaky")
def test_c():
    assert 3
"""


def ratchet(repo, env, *args):
    return run([sys.executable, os.path.join(BIN, "ai-ratchet"), "--dir", repo] + list(args), env=env)


def t_ratchet(work):
    repo = tree(work, "ratchet", {"pyproject.toml": "[project]\nname='x'\n[tool.ruff]\n", "tests/test_a.py": PY_TESTS,
                                  "src/app.py": "import os  # LINT\nimport sys  # LINT\n"})
    fake = os.path.join(work, "fakebin-ratchet")
    write(os.path.join(fake, "ruff"), FAKE_RUFF)
    os.chmod(os.path.join(fake, "ruff"), 0o755)
    env = {"PATH": fake + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")}
    res = ratchet(repo, env)
    assert res.returncode == 0 and "no baseline" in res.stdout, res.stdout
    assert ratchet(repo, env, "--init").returncode == 0
    base = json.loads(read(os.path.join(repo, ".ai", "ratchet.json")))
    assert base == {"tests": 3, "skips": 1, "lint": 2}, base
    tests = os.path.join(repo, "tests", "test_a.py")
    write(tests, PY_TESTS.replace("def test_b():\n    assert 2\n", ""))
    res = ratchet(repo, env)
    assert res.returncode == 1 and "tests 3 -> 2" in res.stdout, "deleting a test must fail: " + res.stdout
    write(tests, PY_TESTS.replace("def test_a():", "@pytest.mark.xfail\ndef test_a():"))
    res = ratchet(repo, env)
    assert res.returncode == 1 and "skips 1 -> 2" in res.stdout, "a new skip must fail: " + res.stdout
    write(tests, PY_TESTS)
    write(os.path.join(repo, "src", "app.py"), "import os  # LINT\nimport os\nimport sys  # LINT\n# LINT\n")
    res = ratchet(repo, env)
    assert res.returncode == 1 and "lint 2 -> 3" in res.stdout, "a new lint finding must fail: " + res.stdout
    write(os.path.join(repo, "src", "app.py"), "import os  # LINT\n")
    res = ratchet(repo, env)
    assert res.returncode == 0 and "tightened" in res.stdout, res.stdout
    assert json.loads(read(os.path.join(repo, ".ai", "ratchet.json")))["lint"] == 1, "fixing lint tightens the baseline"
    write(tests, PY_TESTS + "\ndef test_d():\n    assert 4\n")
    res = ratchet(repo, env, "--only", "tests,skips", "--no-write")
    assert res.returncode == 0 and json.loads(read(os.path.join(repo, ".ai", "ratchet.json")))["tests"] == 3, \
        "--no-write must not change the baseline"
    res = ratchet(repo, env, "--show")
    assert json.loads(res.stdout) == {"tests": 4, "skips": 1, "lint": 1}, res.stdout


def t_ratchet_other_languages(work):
    repo = tree(work, "ratchet-js", {
        "web/a.test.ts": "it('a', () => {})\ntest.each([1, 2])('b %d', () => {})\nit.skip('c', () => {})\n"
                         "xit('d', () => {})\nconst xtest = 1\n",
        "pkg/a_test.go": "func TestA(t *testing.T) {}\nfunc TestB(t *testing.T) { t.Skip(\"later\") }\n",
        "src/lib.rs": "#[test]\nfn a() {}\n#[tokio::test]\n#[ignore]\nasync fn b() {}\n"})
    res = ratchet(repo, {}, "--show", "--only", "tests,skips")
    assert json.loads(res.stdout) == {"tests": 6, "skips": 4}, res.stdout


def t_stop_ratchet_long_tier(work):
    repo, env = ledger_repo(work, "stop-ratchet", extra={"tests/test_a.py": PY_TESTS})
    assert ratchet(repo, env, "--init").returncode == 0
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "baseline"], env=env)
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "tests", "test_a.py"), PY_TESTS.replace("def test_b():\n    assert 2\n", ""))
    out = hook(repo, env, "Stop")
    assert out and out["decision"] == "block" and "ai-ratchet" in out["reason"] and "tests" in out["reason"], out
    assert not run(["git", "-C", repo, "status", "--porcelain", "--", ".ai/ratchet.json"]).stdout.strip(), \
        "the Stop hook must not write the baseline"


# ---------------------------------------------------------------- helpers

def detect(repo):
    res = run([sys.executable, os.path.join(BIN, "ai-check-detect"), "--dir", repo, "--json"])
    return json.loads(res.stdout)


def adopt_repo(work, name, files):
    base = {"src/app.py": "def main():\n    return 1\n", "uv.lock": "", "tests/test_app.py": "def test_x():\n    pass\n",
            "pyproject.toml": "[project]\nname = \"demo\"\n"}
    base.update(files)
    repo = tree(work, name, base)
    fake = os.path.join(work, "fakebin-" + name)
    os.makedirs(fake)
    write(os.path.join(fake, "uv"), FAKE_UV)
    os.chmod(os.path.join(fake, "uv"), 0o755)
    home = os.path.join(work, "home-" + name)
    os.makedirs(home)
    env = {"HOME": home, "PATH": fake + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
           "AI_GITHUB_OWNERS": "someone", "AI_CONTEXT7_URL": "http://127.0.0.1:9",
           "AI_STATE_DIR": os.path.join(home, "state"), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"}
    run(["git", "init", "-q", repo])
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "init"], env=env)
    return repo, env


def adopt(repo, env, *extra):
    # no-serena / no-graph: those tools are not under test here (and not on the test PATH)
    enabled = os.path.join(repo, ".ai", "enabled")
    if not os.path.exists(enabled):
        write(enabled, "no-serena\nno-graph\n")
    return run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes", "--no-onboard",
                "--no-knowledge"] + list(extra), env=env, cwd=repo)


def tree(work, name, files):
    repo = os.path.join(work, name)
    os.makedirs(repo)
    for rel, text in files.items():
        write(os.path.join(repo, rel), text)
    return repo


def load(path, name):
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


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def run(cmd, env=None, cwd=None, stdin=None, timeout=120):
    full = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
    full.update(env or {})
    res = subprocess.run(cmd, env=full, cwd=cwd, input=stdin.encode() if stdin is not None else None,
                         stdin=None if stdin is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=timeout)
    res.stdout = res.stdout.decode("utf-8", "replace")
    return res


TESTS_LIST = [t_adopt_project_skills, t_adopt_try_no_skills, t_detect_python_uv, t_detect_python_pip, t_detect_node, t_detect_go_rust, t_detect_monorepo,
              t_plan_keeps_targets, t_adopt_try_tier_own_done, t_adopt_long_tier, t_adopt_monorepo_refused,
              t_doctor_budget, t_stop_no_change_no_run, t_stop_blocks_twice_then_stops, t_stop_hook_active_silent,
              t_stop_success_silent_both_agents, t_stop_codex_block_and_timeout, t_stop_floor_zero_tests,
              t_stop_off_switches, t_stop_omc_coexistence, t_ledger_check_honest, t_ledger_quarantine_clock,
              t_ledger_stop_note, t_ratchet, t_ratchet_other_languages, t_stop_ratchet_long_tier]

if __name__ == "__main__":
    sys.exit(main())
