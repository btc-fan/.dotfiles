#!/usr/bin/env python3
"""Tests for ai-eval (the eval harness): fixtures, the install level on fake binaries, the stream scorer,
the router log reader, behaviour --dry, the child env and the case files.

Offline: throwaway folders and HOME, fake binaries on PATH, no agent session. Nothing touches the real home.
Run: python3 ai/tests/test_eval.py   (bash ai/tests/run.sh runs it too)
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
EVAL = os.path.join(AI_DIR, "bin", "ai-eval")
FAILS = []


def main():
    work = tempfile.mkdtemp(prefix="ai-eval-tests-")
    try:
        for test in TESTS_LIST:
            try:
                test(work)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
            except Exception as exc:        # a crash in one test must not stop the others
                FAILS.append("%s: %s: %s" % (test.__name__, type(exc).__name__, exc))
                print("FAIL %s: crashed: %s: %s" % (test.__name__, type(exc).__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d eval tests failed" % len(FAILS))
    return 1 if FAILS else 0


def t_fixtures(work):
    ev = load()
    root = os.path.join(work, "fx")
    notes = ev.make_fixtures(root)
    assert sorted(notes) == sorted(ev.FIXTURES), notes
    assert notes["project-copy"] == "skipped: AI_EVAL_PROJECT not set", notes

    assert os.path.isdir(os.path.join(root, "empty-git", ".git")), "empty-git: git init"
    assert os.listdir(os.path.join(root, "empty-git")) == [".git"], "empty-git: nothing but .git"
    assert git(os.path.join(root, "empty-git"), "rev-parse", "-q", "--verify", "HEAD").returncode != 0, "no commit"

    docs = os.path.join(root, "docs-only")
    assert git(docs, "ls-files").stdout.split() == ["README.md", "docs/faq.md", "docs/guide.md"], git(docs, "ls-files")

    assert not os.path.exists(os.path.join(root, "no-git", ".git"))
    assert os.listdir(os.path.join(root, "no-git")) == ["notes.txt"]

    files = git(os.path.join(root, "app"), "ls-files").stdout.split()
    for rel in ("Makefile", "pyproject.toml", "app/calc.py", "app/cli.py", "tests/test_calc.py",
                ".claude/skills/verify-app/SKILL.md"):
        assert rel in files, "%s not committed in app: %s" % (rel, files)
    assert read(os.path.join(root, "app", "Makefile")).startswith("check:\n"), "app: make check target"


def t_app_libraries(work):
    """The app fixture has the Libraries block ai-libs writes, so the docs-lookup case prompt fires the rule."""
    ev = load()
    root = os.path.join(work, "fx-libs")
    ev.make_fixtures(root)
    app = os.path.join(root, "app")
    loader = importlib.machinery.SourceFileLoader("ai_libs", os.path.join(AI_DIR, "bin", "ai-libs"))
    libs = types.ModuleType(loader.name)
    libs.__file__ = loader.path
    loader.exec_module(libs)
    want = libs.render(app, [{"lib": "pytest", "version": "?", "context7": "/pytest-dev/pytest", "note": ""}])
    assert want in read(os.path.join(app, "AGENTS.md")), "app AGENTS.md: not the ai-libs block: " + want
    check = run([sys.executable, os.path.join(AI_DIR, "bin", "ai-libs"), "--check", "--dir", app], None)
    assert check.returncode == 0, "ai-libs --check must pass, so ai-adopt keeps the block: " + check.stdout

    build = os.path.join(work, "libs-build")
    subprocess.check_call([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--out", build],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    case = [c for c in ev.load_cases() if c["id"] == "docs-lookup"][0]
    assert case["fixture"] == "app", case
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "t-libs", "cwd": app, "prompt": case["prompt"]}
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.path.join(work, "home-libs"),
           "AI_STATE_DIR": os.path.join(work, "state-libs"), "AI_ROUTING_JSON": os.path.join(build, "routing.json"),
           "AI_NOTIFY_DRY": "1", "LANG": "C.UTF-8", "AI_GRAPHIFY_BIN": os.path.join(work, "no-graphify")}
    router = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks", "router.py")
    res = subprocess.run([sys.executable, router, "--agent", "claude", "UserPromptSubmit"], cwd=app, env=env,
                         input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = res.stdout.decode()
    assert "docs-lookup" in out and "/pytest-dev/pytest" in out, "docs-lookup did not fire: " + out
    assert load().router_seen(env["AI_STATE_DIR"])["rules"] == ["docs-lookup"], "no docs-lookup row in fired.jsonl"


def t_fixture_project_copy(work):
    """A copy of an adopted project is a clone without remotes: ai-adopt in it can never push."""
    ev = load()
    src = os.path.join(work, "pc-src")
    ev.make_fixtures(src)
    project = os.path.join(src, "docs-only")
    git(project, "remote", "add", "origin", "https://github.com/someone/real.git")
    root = os.path.join(work, "pc")
    notes = ev.make_fixtures(root, project)
    copy = os.path.join(root, "project-copy")
    assert notes["project-copy"] is None, notes
    assert os.path.isfile(os.path.join(copy, "docs", "guide.md")), os.listdir(copy)
    assert git(copy, "remote").stdout.strip() == "", "remotes left: " + git(copy, "remote").stdout
    assert git(project, "remote").stdout.strip() == "origin", "the source keeps its remote"
    bad = ev.make_fixtures(os.path.join(work, "pc-bad"), os.path.join(work, "missing"))
    assert bad["project-copy"].startswith("skipped: git clone failed"), bad


def t_install_fake_bins(work):
    fake = os.path.join(work, "fakebin")
    for name, text in (("uv", "#!/bin/sh\necho '1 passed in 0.01s'\n"), ("serena", "#!/bin/sh\nexit 0\n"),
                       ("graphify", "#!/bin/sh\nexit 0\n"), ("claude", "#!/bin/sh\nexit 0\n")):
        write(os.path.join(fake, name), text)
        os.chmod(os.path.join(fake, name), 0o755)
    home = os.path.join(work, "home-install")
    out = os.path.join(work, "out-install")
    env = {"PATH": fake + os.pathsep + "/usr/bin:/bin", "HOME": home, "LANG": "C.UTF-8",
           "AI_CONTEXT7_URL": "http://127.0.0.1:9", "AI_GITHUB_OWNERS": "someone",
           "HERDR_PANE_ID": "p1", "HC_TERMINAL_ID": "t1"}
    res = run([sys.executable, EVAL, "install", "--out", out], env)
    assert res.returncode == 0, res.stdout
    assert "fixture" in res.stdout and "second-run diff" in res.stdout, res.stdout

    rows = {r["fixture"]: r for r in json.loads(read(os.path.join(out, "install.json")))}
    assert sorted(rows) == sorted(load().FIXTURES), rows
    assert rows["no-git"]["refused_rc"] == 1, "without --init a folder without git is refused: %s" % rows["no-git"]
    assert rows["project-copy"]["adopt_rc"] is None and "skipped" in rows["project-copy"]["notes"]
    assert rows["app"]["adopt_rc"] == 0, rows["app"]["output"]
    # owner 2026-11-17: owner rules outside and an owner line inside an AI block stay byte for byte over two runs
    assert rows["owner-rules"]["owner_text_kept"] is True, rows["owner-rules"]["notes"]
    for name in ("empty-git", "docs-only", "no-git", "app", "owner-rules"):
        row = rows[name]
        assert row["second_run_changed"] is False, "%s: second run changed %s" % (name, row["changed"])
        assert row["doctor_rc"] == 0 and row["uninstall_rc"] == 0, "%s: %s" % (name, row["notes"])
        assert row["pass"] is True, "%s: %s\n%s" % (name, row["notes"], row["output"])
    assert not os.path.exists(home), "ai-adopt ran with the harness HOME, not a throwaway one"

    inside = run([sys.executable, EVAL, "install", "--out", os.path.join(AI_DIR, "eval-out")], env)
    assert inside.returncode != 0 and "outside the repo" in inside.stdout, inside.stdout
    assert not os.path.exists(os.path.join(AI_DIR, "eval-out"))


def t_snapshot_skips_ignored(work):
    """Baseline 2026-11-16: the second run on app changed only gitignored graphify-out cache files (noise)."""
    ev = load()
    repo = os.path.join(work, "snap")
    write(os.path.join(repo, ".gitignore"), "graphify-out/\n")
    write(os.path.join(repo, "graphify-out", "cache", "a.json"), "{}")
    write(os.path.join(repo, "app.py"), "x = 1\n")
    git(repo, "init", "-q")
    snap = ev.snapshot(repo)
    assert "app.py" in snap and ".gitignore" in snap, snap
    assert not any(p.startswith("graphify-out") for p in snap), snap


def t_score_stream(work):
    ev = load()
    sample = "\n".join(json.dumps(e) for e in [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "start"},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "tdd"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/r/.claude/skills/writing-for-agents/SKILL.md"}},
            {"type": "tool_use", "name": "Read", "input": {
                "file_path": "/h/.claude/plugins/cache/omc/oh-my-claudecode/5.0.0/skills/tdd/SKILL.md"}},
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/r/.claude/skills/ship/SKILL.md"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "graphify query 'where is add used'"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {"type": "item.started", "item": {"type": "command_execution", "command": "cat x"}},
        {"type": "item.completed", "item": {"type": "command_execution",
                                            "command": "bash -lc 'cat .agents/skills/diagnosing-bugs/SKILL.md'"}},
        {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "context7", "tool": "query-docs",
                                            "arguments": {"libraryId": "/pytest-dev/pytest"}}},
    ]) + "\nnot json\n[1, 2]\n"
    seen = ev.score_stream(sample)
    assert seen["skills"] == ["tdd", "writing-for-agents", "oh-my-claudecode:tdd", "diagnosing-bugs"], seen["skills"]
    assert len(seen["tools"]) == 7, "item.started is not counted twice: %s" % seen["tools"]
    assert "Bash {\"command\": \"cat x\"}" not in seen["tools"], seen["tools"]
    seen["rules"] = ["docs-lookup"]
    assert ev.hit({"skills": ["tdd"]}, seen)
    assert not ev.hit({"skills": ["tdd"], "not_skills": ["oh-my-claudecode:tdd"]}, seen), "a losing skill is a miss"
    assert not ev.hit({"skills": ["ship"]}, seen), "an Edit of a SKILL.md is not a use"
    assert ev.hit({"tools": ["graphify (query|affected)", "context7"], "rules": ["docs-lookup"]}, seen)
    assert not ev.hit({"rules": ["nav-first"]}, seen)
    assert not ev.hit({"skills": ["tdd"], "not_rules": ["docs-lookup"]}, seen), "a rule that must not fire fired"
    assert not ev.hit({"not_tools": ["graphify (query|affected)"]}, seen), "a tool that must not run ran"
    assert ev.hit({"not_rules": ["nav-first"], "not_tools": ["^Write "], "not_skills": ["ship"]}, seen)


def t_router_seen(work):
    ev = load()
    state = os.path.join(work, "state-router")
    write(os.path.join(state, "fired.jsonl"), "\n".join([
        json.dumps({"kind": "rule", "rule": "docs-lookup", "event": "UserPromptSubmit"}),
        json.dumps({"kind": "rule", "rule": "docs-lookup", "event": "PreToolUse"}),
        json.dumps({"kind": "skill", "via": "tool", "skill": "ship"}),
        "broken line", "[1, 2]"]) + "\n")
    assert ev.router_seen(state) == {"rules": ["docs-lookup"], "skills": ["ship"]}
    assert ev.router_seen(os.path.join(work, "no-state")) == {"rules": [], "skills": []}


def t_behaviour_dry(work):
    fake = os.path.join(work, "fakebin-dry")
    mark = os.path.join(work, "agent-started")
    for name in ("claude", "codex"):
        write(os.path.join(fake, name), "#!/bin/sh\ntouch %s\n" % mark)
        os.chmod(os.path.join(fake, name), 0o755)
    env = {"PATH": fake + os.pathsep + "/usr/bin:/bin", "HOME": os.path.join(work, "home-dry"), "LANG": "C.UTF-8"}
    res = run([sys.executable, EVAL, "behaviour", "--dry", "--runs", "2"], env)
    assert res.returncode == 0, res.stdout
    cases = load().load_cases()
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(("claude ", "codex "))]
    assert len(lines) == len(cases) * 2 * 2, res.stdout
    for case in cases:
        for agent in ("claude", "codex"):
            assert sum(1 for ln in lines if ln.split()[:2] == [agent, case["id"]]) == 2, (agent, case["id"])
    claude = [ln for ln in lines if ln.startswith("claude ")]
    assert all("--output-format stream-json --verbose --max-turns 15" in ln and "--bare" not in ln for ln in claude)
    assert all("codex exec --json" in ln for ln in lines if ln.startswith("codex "))
    assert "runs planned, none started (--dry)" in res.stdout and not os.path.exists(mark), "no agent may start"
    res = run([sys.executable, EVAL, "behaviour", "--dry", "--agent", "codex", "--runs", "1"], env)
    assert sum(1 for ln in res.stdout.splitlines() if ln.startswith("codex ")) == len(cases), res.stdout
    assert run([sys.executable, EVAL, "behaviour", "--agent", "gpt"], env).returncode != 0, "a bad agent is refused"


def t_child_env(work):
    ev = load()
    old = dict(os.environ)
    os.environ.update(HERDR_PANE_ID="p1", HERDR_SOCKET="s", HC_TERMINAL_ID="t1", KEEP_ME="1")
    try:
        env = ev.child_env("/tmp/state-x")
    finally:
        os.environ.clear()
        os.environ.update(old)
    assert not any(k.startswith("HERDR_") or k == "HC_TERMINAL_ID" for k in env), sorted(env)
    assert env["AI_STATE_DIR"] == "/tmp/state-x" and env["KEEP_ME"] == "1", env


def t_cases_valid(work):
    ev = load()
    cases = ev.load_cases()
    ids = [c["id"] for c in cases]
    for want in ("writing-for-agents", "diagnosing-bugs", "graphify-first", "docs-lookup", "ship", "winner-tdd"):
        assert want in ids, "missing case %s: %s" % (want, ids)
    # EXTENDING section 6: English, Romanian and Russian should-fire cases, and a should-not-fire case.
    for base in ("writing-for-agents", "diagnosing-bugs", "graphify-first", "ship"):
        for want in (base + "-ro", base + "-ru", base + "-not"):
            assert want in ids, "missing case %s: %s" % (want, ids)
        neg = [c for c in cases if c["id"] == base + "-not"][0]["expect"]
        assert neg and all(k.startswith("not_") for k in neg), "%s-not expects only not_* items: %s" % (base, neg)
    assert len(set(ids)) == len(ids), ids
    for case in cases:
        assert set(case) == {"id", "fixture", "prompt", "expect"}, case
        assert case["fixture"] in ev.FIXTURES and case["prompt"].strip(), case
        assert case["expect"] and set(case["expect"]) <= {"skills", "tools", "rules", "not_skills", "not_rules",
                                                           "not_tools"}, case
    tdd = [c for c in cases if c["id"] == "winner-tdd"][0]
    assert tdd["expect"] == {"skills": ["tdd"], "not_skills": ["oh-my-claudecode:tdd"]}, tdd


# ---------------------------------------------------------------- helpers

def load():
    loader = importlib.machinery.SourceFileLoader("ai_eval", EVAL)
    spec = importlib.util.spec_from_loader("ai_eval", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    loader.exec_module(mod)
    return mod


def git(repo, *args):
    return run(["git", "-C", repo] + list(args), None)


def run(cmd, env, timeout=900):
    full = env if env is not None else dict(os.environ)
    res = subprocess.run(cmd, env=full, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         timeout=timeout)
    res.stdout = res.stdout.decode("utf-8", "replace")
    return res


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def t_copy_fixture_skips_socket(work):
    """Regression (first real baseline, 2026-11-16): git fsmonitor leaves a socket in .git and copytree crashed."""
    import socket
    ev = load()
    src = os.path.join(work, "sock-src")
    os.makedirs(os.path.join(src, ".git"))
    with open(os.path.join(src, "a.txt"), "w") as fh:
        fh.write("a\n")
    sock = socket.socket(socket.AF_UNIX)
    cwd = os.getcwd()
    os.chdir(os.path.join(src, ".git"))     # relative bind: a temp path can pass the 104-byte socket path limit
    try:
        sock.bind("fsmonitor--daemon.ipc")
    finally:
        os.chdir(cwd)
    try:
        dst = os.path.join(work, "sock-dst")
        ev.copy_fixture(src, dst)
    finally:
        sock.close()
    assert os.path.isfile(os.path.join(dst, "a.txt")), "the files are copied"
    assert not os.path.exists(os.path.join(dst, ".git", "fsmonitor--daemon.ipc")), "the socket is skipped"


def t_failed_run_is_error(work):
    """Regression (hard baseline, 2026-11-16): Codex hit its usage limit, exited 1 with no tool call, and 24 runs
    were scored as misses. A run that fails before any tool call is an error, out of the score."""
    ev = load()
    out = os.path.join(work, "err-out")
    os.makedirs(os.path.join(out, "fixtures", "app"))
    bin_dir = os.path.join(work, "err-bin")
    os.makedirs(bin_dir)
    fake = os.path.join(bin_dir, "codex")
    with open(fake, "w") as fh:
        fh.write("#!/bin/sh\necho '{\"type\":\"error\",\"message\":\"You have hit your usage limit.\"}'\nexit 1\n")
    os.chmod(fake, 0o755)
    case = {"id": "x", "fixture": "app", "prompt": "p", "expect": {"skills": ["ship"]}}
    old = os.environ["PATH"]
    os.environ["PATH"] = bin_dir + os.pathsep + old
    try:
        res = ev.run_case(out, {"app": None}, "codex", case, 1)
    finally:
        os.environ["PATH"] = old
    assert res["hit"] is None and res["rc"] == 1, res
    assert res["error"] == "You have hit your usage limit.", res


FAKE_AGENT = r"""#!/bin/sh
# Fake claude for the scenario test: acts on the prompt like a real session would, logs router rules.
mkdir -p "$AI_STATE_DIR"
case "$2" in
  *build*)
    git checkout -q -b feat-calc
    mkdir -p calc && printf 'def add(a, b):\n    return a + b\n' > calc/core.py
    sed -i.bak 's/^## Map$/## Map\n- calc\/core.py: add()/' AGENTS.md && rm -f AGENTS.md.bak
    git add -A && git -c user.name=t -c user.email=t@t commit -q -m "feat: calc"
    echo '{"kind": "rule", "rule": "feature-grill"}' >> "$AI_STATE_DIR/fired.jsonl"
    echo '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "git commit"}}]}}' ;;
  *where*)
    echo '{"kind": "rule", "rule": "merge-review"}' >> "$AI_STATE_DIR/fired.jsonl"
    echo '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "graphify query where is add"}}]}}' ;;
esac
"""


def scenario_fixture(work, name):
    repo = os.path.join(work, name)
    os.makedirs(repo)
    write(os.path.join(repo, "AGENTS.md"), "# x\n\n## Map\n- What: nothing yet.\n")
    ev = load()                 # its git() turns off the owner's global ignore, which may hide AGENTS.md
    ev.git(repo, "init", "-q", "-b", "ai-adopt")
    ev.git(repo, "add", "-A")
    ev.git(repo, "commit", "-q", "-m", "adopt")
    return repo


def t_scenario_fake_agent(work):
    """A scenario runs its steps in order on one repo copy: sessions (scored like a case), harness git steps and
    state checks. The step results and the run pass come back; a failed check fails the run."""
    ev = load()
    fake = os.path.join(work, "fakebin-scenario")
    write(os.path.join(fake, "claude"), FAKE_AGENT)
    os.chmod(os.path.join(fake, "claude"), 0o755)
    os.environ["PATH"] = fake + os.pathsep + os.environ["PATH"]
    out = os.path.join(work, "scenario-out")
    os.makedirs(os.path.join(out, "fixtures"))
    ev.copy_fixture(scenario_fixture(work, "scen-src"), os.path.join(out, "fixtures", "empty-git"))
    sc = {"id": "evo", "fixture": "empty-git", "steps": [
        {"git": [["checkout", "-q", "-B", "main"]]},
        {"session": "build calc", "expect": {"rules": ["feature-grill"]}},
        {"check": {"map_contains": "calc/core.py", "branch": "feat-calc"}},
        {"git": [["checkout", "-q", "main"], ["merge", "-q", "--squash", "feat-calc"],
                 ["commit", "-q", "-m", "feat: calc (#1)"]]},
        {"session": "where is add?", "expect": {"rules": ["merge-review"], "tools": ["graphify (query|affected)"]}},
        {"check": {"map_contains": "calc/core.py", "branch": "main"}}]}
    res = ev.run_scenario(out, {"empty-git": ""}, "claude", sc, 1)
    assert res["pass"] is True, json.dumps(res, indent=1)[:1500]
    assert [st["kind"] for st in res["steps"]] == ["git", "session", "check", "git", "session", "check"], res
    sc["steps"][-1] = {"check": {"map_contains": "no-such-module"}}
    res = ev.run_scenario(out, {"empty-git": ""}, "claude", sc, 2)
    assert res["pass"] is False and res["steps"][-1]["ok"] is False, res["steps"][-1]


def t_scenario_dry(work):
    """scenario --dry lists the runs and starts no agent; every scenario file has steps of a known kind."""
    fake = os.path.join(work, "fakebin-scen-dry")
    mark = os.path.join(work, "scen-agent-started")
    for name in ("claude", "codex"):
        write(os.path.join(fake, name), "#!/bin/sh\ntouch %s\n" % mark)
        os.chmod(os.path.join(fake, name), 0o755)
    env = {"PATH": fake + os.pathsep + "/usr/bin:/bin", "HOME": os.path.join(work, "home-scen"), "LANG": "C.UTF-8"}
    res = run([sys.executable, EVAL, "scenario", "--dry", "--runs", "3"], env)
    assert res.returncode == 0, res.stdout
    scs = load().load_scenarios()
    assert any(sc["id"] == "evolution" for sc in scs), scs
    for sc in scs:
        assert all(len(st) == 1 or "expect" in st for st in sc["steps"]), sc["id"]
        assert all(next(iter(st)) in ("git", "session", "check", "write") for st in sc["steps"]), sc["id"]
        assert set(sc.get("agents", ["claude", "codex"])) <= {"claude", "codex"}, sc["id"]
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(("claude ", "codex "))]
    assert len(lines) == sum(len(sc.get("agents", ["claude", "codex"])) for sc in scs) * 3, res.stdout
    assert all(ln.split()[0] in sc.get("agents", ["claude", "codex"]) for sc in scs for ln in lines
               if ln.split()[1] == sc["id"]), "a scenario runs only for its agents"
    assert "none started (--dry)" in res.stdout and not os.path.exists(mark), "no agent may start"
    res = run([sys.executable, EVAL, "scenario", "--dry", "--only", "evolution", "--runs", "1"], env)
    assert [ln.split()[1] for ln in res.stdout.splitlines() if ln.startswith(("claude ", "codex "))] == \
        ["evolution", "evolution"], res.stdout
    assert run([sys.executable, EVAL, "scenario", "--dry", "--only", "no-such"], env).returncode != 0


# Fake claude for the checkout scenario test: logs its argv and AI_HOME, acts on the prompt.
FAKE_CHECKOUT_AGENT = r"""#!/bin/sh
mkdir -p "$AI_STATE_DIR"
printf '%s\n' "$@" > "$AI_STATE_DIR/argv"
echo "$AI_HOME" > "$AI_STATE_DIR/ai_home"
echo '{"type": "system", "subtype": "init", "session_id": "fake-sess-1"}'
case "$2" in
  *change*)
    printf 'def add(a, b):\n    return b + a\n' > app/calc.py
    echo '{"type": "user", "message": {"content": [{"type": "tool_result", "content": "[ai router: verify-tool-exists] no tool"}]}}' ;;
  *prove*)
    sleep 1
    mkdir -p .agents/skills/verify-app .verify/evidence/r1
    printf -- '---\nname: verify-app\n---\n' > .agents/skills/verify-app/SKILL.md
    printf 'commit: %s\ndoctor: PASS\ndb_writes: no\nfinished: %s\n' "$(git rev-parse HEAD)" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .verify/evidence/r1/run.log
    gh pr create --title t ;;
esac
"""


def t_scenario_checkout(work):
    """A scenario with "plugin": "checkout" drives this checkout's code, not the installed setup: the session
    loads this checkout's ai-core (--plugin-dir, AI_HOME), the pre-commit hook runs this checkout's ai-precommit,
    the stand-in skills are this checkout's copies, gh is a fake that logs. Write steps add files; a hook check
    replays the router on the end state of the last session (Stop: block, then allow after a valid run)."""
    ev = load()
    fake = os.path.join(work, "fakebin-checkout")
    write(os.path.join(fake, "claude"), FAKE_CHECKOUT_AGENT)
    os.chmod(os.path.join(fake, "claude"), 0o755)
    old = os.environ["PATH"]
    os.environ["PATH"] = fake + os.pathsep + old
    src = os.path.join(work, "checkout-src")
    write(os.path.join(src, "app", "calc.py"), "def add(a, b):\n    return a + b\n")
    write(os.path.join(src, ".ai", "enabled"), "serena graph\n")
    ev.git(src, "init", "-q", "-b", "main")
    ev.git(src, "add", "-A")
    ev.git(src, "commit", "-q", "-m", "init")
    write(os.path.join(src, ".git", "hooks", "pre-commit"), "#!/bin/sh\nexec ai-precommit\n")
    out = os.path.join(work, "checkout-out")
    ev.copy_fixture(src, os.path.join(out, "fixtures", "app"))
    sc = {"id": "co", "fixture": "app", "plugin": "checkout", "skills": ["create-verification-skill"],
          "agents": ["claude"], "steps": [
              {"write": {"pr-body.md": "body\n"}},
              {"session": "change the code", "expect": {"says": ["verify-tool-exists"]}},
              {"check": {"hook": {"event": "Stop", "decision": "block"}}},
              {"session": "prove it", "max_turns": 60, "expect": {"not_rules": ["x"]}},
              {"check": {"hook": {"event": "Stop", "decision": "allow"}, "gh_log": "pr create --title t",
                         "git_out": {"args": ["status", "--short"], "match": "app/calc.py"}}}]}
    try:
        res = ev.run_scenario(out, {"app": None}, "claude", sc, 1)
    finally:
        os.environ["PATH"] = old
    assert res["pass"] is True, json.dumps(res, indent=1)[:2500]
    assert [st["kind"] for st in res["steps"]] == ["write", "session", "check", "session", "check"], res
    base = os.path.join(out, "scenarios", "claude", "co-1")
    repo = os.path.join(base, "repo")
    argv = read(os.path.join(base, "state-2", "argv")).splitlines()
    plugin = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core")
    assert argv[argv.index("--plugin-dir") + 1] == plugin, argv
    assert '"ai-core@ai": false' in argv[argv.index("--settings") + 1] and "--strict-mcp-config" in argv, argv
    assert argv[argv.index("--max-turns") + 1] == "40", argv
    assert read(os.path.join(base, "state-2", "ai_home")).strip() == os.path.dirname(AI_DIR)
    assert os.path.join(AI_DIR, "bin", "ai-precommit") in read(os.path.join(repo, ".git", "hooks", "pre-commit"))
    argv4 = read(os.path.join(base, "state-4", "argv")).splitlines()
    assert argv4[argv4.index("--max-turns") + 1] == "60", argv4
    assert read(os.path.join(repo, ".claude", "skills", "create-verification-skill", "SKILL.md")) == \
        read(os.path.join(AI_DIR, "skills", "create-verification-skill", "SKILL.md"))
    assert ".claude/skills/create-verification-skill" in read(os.path.join(repo, ".git", "info", "exclude"))
    assert read(os.path.join(repo, "pr-body.md")) == "body\n"

    sc["steps"][-1] = {"check": {"hook": {"event": "Stop", "decision": "block"}}}
    os.environ["PATH"] = fake + os.pathsep + old
    try:
        res = ev.run_scenario(out, {"app": None}, "claude", sc, 2)
    finally:
        os.environ["PATH"] = old
    assert res["pass"] is False and res["steps"][-1]["got"]["hook"] == "allow", res["steps"][-1]
    sc["steps"][0] = {"write": {"../outside.txt": "x"}}
    res = ev.run_scenario(out, {"app": None}, "claude", sc, 3)
    assert res["steps"][0]["ok"] is False and not os.path.exists(os.path.join(base, "outside.txt")), res["steps"]


TESTS_LIST = [t_fixtures, t_app_libraries, t_fixture_project_copy, t_copy_fixture_skips_socket, t_snapshot_skips_ignored, t_score_stream, t_router_seen,
              t_child_env, t_cases_valid, t_behaviour_dry, t_install_fake_bins, t_failed_run_is_error,
              t_scenario_fake_agent, t_scenario_checkout, t_scenario_dry]

if __name__ == "__main__":
    sys.exit(main())
