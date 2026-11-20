#!/usr/bin/env python3
"""Ship, merge and release flow (owner 2026-11-16): ai-docs-check, ai-precommit, ai-versions, and what ai-adopt now
writes (UI on by default, Project rules, the Design line, the pre-commit hook, the docs baseline). Scenario tests
on throwaway repos: a small new project, an existing messy repo, a web UI repo, a mobile repo, a repo that
evolves over many merges, and negative cases (bypass attempts).

Run: python3 ai/tests/test_flow.py [-v]   (bash ai/tests/run.sh runs it too)
Every test uses a throwaway HOME. Nothing touches the real home.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
BIN = os.path.join(AI_DIR, "bin")
HOOKS = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks")
ROUTER = os.path.join(HOOKS, "router.py")
IDENT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid", "GIT_COMMITTER_NAME": "t",
         "GIT_COMMITTER_EMAIL": "t@t.invalid", "GIT_CONFIG_NOSYSTEM": "1"}


def main(argv):
    verbose = "-v" in argv
    work = tempfile.mkdtemp(prefix="ai-flow-tests-")
    failed = 0
    try:
        build = os.path.join(work, "build")
        res = subprocess.run([sys.executable, os.path.join(BIN, "ai-render"), "--profile", "dev-mac", "--out", build],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert res.returncode == 0, res.stdout.decode()
        os.environ["AI_ROUTING_JSON"] = os.path.join(build, "routing.json")
        tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("t_") and callable(f)]
        for name, fn in tests:
            d = os.path.join(work, name)
            os.makedirs(d)
            try:
                fn(d)
                if verbose:
                    print("ok   " + name)
            except AssertionError as exc:
                failed += 1
                print("FAIL %s: %s" % (name, str(exc)[:1500]))
            except Exception as exc:     # a crash is a failure too, with its type
                failed += 1
                print("FAIL %s: %s: %s" % (name, type(exc).__name__, str(exc)[:1500]))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d flow tests failed" % failed)
    return 1 if failed else 0


# ---------------------------------------------------------------- helpers

def env_for(home, **extra):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "AI_GITHUB_OWNERS": "someone",
           "AI_STATE_DIR": os.path.join(home, ".local", "state", "ai"), "AI_RESOLVE_OFFLINE": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "LANG": "C.UTF-8",
           "AI_ROUTING_JSON": os.environ.get("AI_ROUTING_JSON", "")}
    env.update(IDENT)
    env.update(extra)
    return env


def run(argv, env=None, cwd=None, inp=None):
    res = subprocess.run(argv, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         input=inp.encode() if inp is not None else None, timeout=600)
    res.text = res.stdout.decode("utf-8", "replace")
    return res


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def git(repo, *args, env=None):
    return run(["git", "-C", repo] + list(args), env=env or env_for(os.path.dirname(repo)))


def new_repo(work, name, files, branch="main"):
    repo = os.path.join(work, name)
    os.makedirs(repo)
    env = env_for(work)
    run(["git", "init", "-q", "-b", branch, repo], env=env)
    for rel, text in files.items():
        write(os.path.join(repo, rel), text)
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-q", "--no-verify", "-m", "init", env=env)
    return repo, env


def adopt(repo, env, *extra):
    return run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes", "--no-onboard",
                "--no-measure"] + list(extra), env=env, cwd=repo)


def hook(event, payload, env, agent="claude"):
    res = run([sys.executable, ROUTER, "--agent", agent, event], env=env, cwd=payload.get("cwd"),
              inp=json.dumps(payload))
    return res.text


def decision(out):
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        p = d.get("hookSpecificOutput", {}).get("permissionDecision")
        if p:
            return p
    return "allow"


PY_APP = {"pyproject.toml": "[project]\nname = 'app'\nversion = '0.1.0'\n",
          "src/app/__init__.py": "", "src/app/core.py": "def add(a, b):\n    return a + b\n",
          "tests/test_core.py": "from app.core import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"}


# ---------------------------------------------------------------- ai-docs-check

def t_docs_check_places(work):
    repo, env = new_repo(work, "docs", {
        "README.md": "x", "AGENTS.md": "x", "GLOSSARY.md": "x", "docs/adr/0001-x.md": "x", "docs/anything.md": "x",
        "design-system/app/MASTER.md": "x", "src/README.md": "x", ".claude/commands/deploy.md": "x",
        ".github/pull_request_template.md": "x", "app.py": "x = 1\n"})
    res = run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env)
    assert res.returncode == 0, res.text
    write(os.path.join(repo, "NOTES.md"), "agent notes\n")
    write(os.path.join(repo, "src", "app", "PLAN.md"), "plan\n")
    res = run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env)
    assert res.returncode == 1 and "stray Markdown NOTES.md" in res.text and "src/app/PLAN.md" in res.text, res.text
    # an ignored file does not count (git does not see it)
    write(os.path.join(repo, ".gitignore"), "NOTES.md\nsrc/app/PLAN.md\n")
    res = run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env)
    assert res.returncode == 0, res.text


def t_docs_check_baseline(work):
    """An adopted messy repo: today's stray files pass (baseline), a new one fails."""
    repo, env = new_repo(work, "mess", {"TODO.md": "x", "notes/ideas.md": "x", "app.py": "x = 1\n"})
    dc = os.path.join(BIN, "ai-docs-check")
    assert run([sys.executable, dc, "--dir", repo], env=env).returncode == 1
    res = run([sys.executable, dc, "--dir", repo, "--init"], env=env)
    assert res.returncode == 0 and "2 file(s)" in res.text, res.text
    assert run([sys.executable, dc, "--dir", repo], env=env).returncode == 0
    write(os.path.join(repo, "SUMMARY.md"), "a new summary an agent left\n")
    res = run([sys.executable, dc, "--dir", repo], env=env)
    assert res.returncode == 1 and "SUMMARY.md" in res.text and "TODO.md" not in res.text, res.text


def t_docs_check_research_header(work):
    repo, env = new_repo(work, "research", {"docs/research/expo-push.md": "# Expo push\nsome text\n",
                                            "docs/research/ok.md": "# x\nDate: 2026-11-16\nSources: a\nStatus: current\n"})
    res = run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env)
    assert res.returncode == 0, "a missing header is a warning, never a failure: " + res.text
    assert "WARN docs/research/expo-push.md" in res.text and "ok.md" not in res.text, res.text


def t_docs_check_md(work):
    """--md (the check of a docs-only repo): placement, no em dash, relative links resolve."""
    repo, env = new_repo(work, "md", {
        "README.md": "# r\n\n[guide](docs/guide.md#step-1) [web](https://example.invalid/x) [top](#r)\n"
                     "[mail](mailto:a@example.invalid) ![img](docs/pic.png)\n\n```\n[not a link](nowhere.md)\n```\n",
        "docs/guide.md": "# Guide\n\n[back](../README.md) [missing](./gone.md)\n",
        "docs/pic.png": "png"})
    dc = [sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo]
    assert run(dc, env=env).returncode == 0, "without --md: placement only"
    res = run(dc + ["--md"], env=env)
    assert res.returncode == 1 and "docs/guide.md:3: broken link ./gone.md" in res.text, res.text
    assert "nowhere.md" not in res.text and "example.invalid" not in res.text, res.text
    write(os.path.join(repo, "docs", "guide.md"), "# Guide\n\nStep 1 \u2014 read.\n\n[back](../README.md)\n")
    res = run(dc + ["--md"], env=env)
    assert res.returncode == 1 and "docs/guide.md:3: em dash (U+2014)" in res.text, res.text
    write(os.path.join(repo, "docs", "guide.md"), "# Guide\n\nStep 1: read.\n\n[back](../README.md)\n")
    res = run(dc + ["--md"], env=env)
    assert res.returncode == 0, res.text


def t_scenario_docs_only_and_empty(work):
    """Spec story 25 and 30: a docs-only and an empty repo get a make check (the Markdown checks) that passes."""
    for name, files in (("docs-only", {"README.md": "# d\n\nSee [the guide](docs/guide.md).\n",
                                       "docs/guide.md": "# Guide\n"}), ("empty", {})):
        repo, env = new_repo(work, name, files)
        res = adopt(repo, env)
        assert res.returncode == 0, res.text
        mk = read(os.path.join(repo, "Makefile")) or ""
        assert "check:" in mk and "check-fast:" in mk and "ai-docs-check --md" in mk, (name, mk)
        assert "Makefile" in git(repo, "show", "--name-only", "--format=", "HEAD", env=env).text.split(), name
        res = run(["make", "-C", repo, "check"], env=dict(env, PATH=BIN + os.pathsep + env["PATH"]))
        assert res.returncode == 0 and "Markdown" in res.text, (name, res.text)
        assert "nothing to change" in adopt(repo, env).text, name


# ---------------------------------------------------------------- ai-precommit

def fake_tool(home, name, body):
    path = os.path.join(home, "bin", name)
    write(path, "#!/bin/sh\n" + body + "\n")
    os.chmod(path, 0o755)
    return os.path.join(home, "bin")


def t_precommit_python(work):
    repo, env = new_repo(work, "pc", dict(PY_APP))
    bindir = fake_tool(work, "ruff", 'for a in "$@"; do case "$a" in *bad.py) echo "bad.py:1: F401 unused import"; '
                                     'exit 1;; esac; done; exit 0')
    env = dict(env, PATH=bindir + os.pathsep + env["PATH"])
    write(os.path.join(repo, "src", "app", "good.py"), "x = 1\n")
    git(repo, "add", "src/app/good.py", env=env)
    res = run([sys.executable, os.path.join(BIN, "ai-precommit"), "--dir", repo], env=env)
    assert res.returncode == 0, res.text
    write(os.path.join(repo, "src", "app", "bad.py"), "import os\n")
    git(repo, "add", "src/app/bad.py", env=env)
    res = run([sys.executable, os.path.join(BIN, "ai-precommit"), "--dir", repo], env=env)
    assert res.returncode == 1 and "ruff check" in res.text and "F401" in res.text, res.text


def t_precommit_no_tools_no_block(work):
    """A stack without its tools installed: skipped and named, never a block."""
    repo, env = new_repo(work, "pc2", {"app.swift": "let x = 1\n"})
    env = dict(env, PATH="/usr/bin:/bin")
    write(os.path.join(repo, "b.swift"), "let y = 2\n")
    git(repo, "add", "b.swift", env=env)
    res = run([sys.executable, os.path.join(BIN, "ai-precommit"), "--dir", repo], env=env)
    assert res.returncode == 0 and "skipped" in res.text, res.text


# ---------------------------------------------------------------- verify hooks (verify-enforcement 02, 03, 04)
# Hook 1 (verify-tool-exists) and hook 2 (verify-tool-used): router Stop and SubagentStop, the change read from git.
# Hook 3: ai-precommit, driven by a real git commit. The proof is .verify/evidence/<run>/run.log (4-line contract).

VERIFY_SKILL = ("---\nname: verify-app\ndescription: drive the app\n---\n\n# verify-app\n\n## Launch\n\n```\n"
                ".agents/skills/verify-app/verify launch\n```\n\n## Doctor\n\n```\n.agents/skills/verify-app/verify "
                "doctor\n```\n\n## Drive\n\n```\n.agents/skills/verify-app/verify drive <feature>\n```\n\n## Cleanup\n\n"
                "```\n.agents/skills/verify-app/verify cleanup\n```\n")
LAUNCH = ".agents/skills/verify-app/verify launch"


def vh_repo(work, name, verify=True, files=None, adopted=True, old_commit=False):
    """An adopted Python app (optionally with a verify skill), committed; old_commit dates the commit 2 h back."""
    f = dict(PY_APP if files is None else files)
    if adopted:
        f[".ai/enabled"] = "tier: long\n"
    if verify:
        f[".agents/skills/verify-app/SKILL.md"] = VERIFY_SKILL
    f[".gitignore"] = ".verify/\n"
    repo, env = new_repo(work, name, f)
    if old_commit:
        import time
        stamp = "@%d +0000" % (time.time() - 7200)
        git(repo, "commit", "-q", "--amend", "--no-edit", "--no-verify", "--date", stamp,
            env=dict(env, GIT_COMMITTER_DATE=stamp))
    return repo, env


def run_log_ago(root, name, ago_s, doctor="PASS", db="no", lines=None):
    """A run folder with run.log; finished ago_s seconds back (the helper writes it in real use)."""
    import time
    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_s))
    rows = lines or ["commit: " + "a" * 40, "doctor: " + doctor, "db_writes: " + db, "finished: " + finished]
    write(os.path.join(root, ".verify", "evidence", name, "run.log"), "\n".join(rows) + "\n")


def shell_write(path, text, ago_s=0):
    """A write the router never sees as a tool call (the shell); the file time set ago_s seconds back."""
    import time
    write(path, text)
    if ago_s:
        os.utime(path, (time.time() - ago_s, time.time() - ago_s))


def stop(env, cwd, event="Stop", agent="claude", session="vh", **extra):
    payload = dict({"session_id": session, "cwd": cwd, "stop_hook_active": False}, **extra)
    out = hook(event, payload, env, agent=agent)
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("decision") == "block":
            return d.get("reason") or "block"
    return None


def prompt(env, cwd, session="vh"):
    hook("UserPromptSubmit", {"session_id": session, "cwd": cwd, "prompt": "change the add function"}, env)


def t_vh_exists_blocks_main_and_subagent(work):
    repo, env = vh_repo(work, "app", verify=False)
    prompt(env, repo)
    assert stop(env, repo) is None, "no app-code change yet: the turn ends"
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    why = stop(env, repo)
    assert why and "[ai router: verify-tool-exists]" in why and "create-verification-skill" in why, why
    assert "src/app/core.py" in why and "run.log" in why, why
    sub = stop(env, repo, event="SubagentStop", agent_id="sub1", agent_type="general-purpose")
    assert sub and "verify-tool-exists" in sub, "a subagent turn is blocked the same way: %s" % sub
    walls = read(os.path.join(env["AI_STATE_DIR"], "walls.jsonl")) or ""
    assert '"wall": "verify-tool-exists"' in walls, walls


def t_vh_exists_green_with_skill_and_one_run(work):
    repo, env = vh_repo(work, "app")
    prompt(env, repo)
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n", ago_s=600)
    why = stop(env, repo)
    assert why and "verify-tool-exists" in why and "verify-app" in why and LAUNCH in why, \
        "a skill without one valid run is not proven yet: %s" % why
    run_log_ago(repo, "20261118T100000Z-first", 60)
    assert stop(env, repo, session="vh2") is None, "skill + one valid run after the change: the turn ends"
    prompt(env, repo, session="vh4")
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return a + b + 0\n", ago_s=300)
    assert stop(env, repo, session="vh4") is None, "skill + a valid run after the change: the turn ends"


def t_vh_no_block_without_code_change(work):
    docs, env = vh_repo(work, "docs", verify=False, files={"README.md": "# docs\n"})
    prompt(env, docs)
    shell_write(os.path.join(docs, "README.md"), "# docs\n\nmore\n")
    assert stop(env, docs) is None, "a docs-only repo: no block"
    empty, env = vh_repo(work, "empty", verify=False, files={})
    prompt(env, empty)
    assert stop(env, empty) is None, "an empty repo: no block"
    wip, env = vh_repo(work, "wip", verify=False)
    shell_write(os.path.join(wip, "src", "app", "core.py"), "def add(a, b):\n    return 3\n")
    prompt(env, wip)
    assert stop(env, wip) is None, "app code dirty before the turn and untouched in it: no block"
    raw, env = vh_repo(work, "raw", verify=False, adopted=False)
    prompt(env, raw)
    shell_write(os.path.join(raw, "src", "app", "core.py"), "def add(a, b):\n    return 4\n")
    assert stop(env, raw) is None, "a repo that is not adopted (.ai/enabled missing): no block"


def t_vh_used_worktree_shell_write(work):
    """The ScripTube regression: a subagent writes a test by shell in a linked worktree and makes no new run."""
    repo, env = vh_repo(work, "app")
    run_log_ago(repo, "20261117T100000Z-old", 7200)
    prompt(env, repo)
    wt = os.path.join(work, "wt")
    git(repo, "worktree", "add", "-q", "-b", "ticket-1", wt, env=env)
    shell_write(os.path.join(wt, "tests", "test_more.py"), "def test_more():\n    assert 1\n", ago_s=300)
    why = stop(env, wt, event="SubagentStop", agent_id="sub1")
    assert why and "[ai router: verify-tool-used]" in why and "tests/test_more.py" in why, why
    assert LAUNCH in why and ".agents/skills/verify-app/verify doctor" in why and wt in why, why
    run_log_ago(repo, "20261118T100000Z-main-checkout", 60)
    assert stop(env, wt, event="SubagentStop", agent_id="sub2"), "a run of the main checkout is not the worktree's"
    run_log_ago(wt, "20261118T100500Z-ticket-1", 60)
    assert stop(env, wt, event="SubagentStop", agent_id="sub3") is None, "a valid run after the change: ends"
    # a commit in a worktree made in this turn is still a change of the turn (the reflog of the worktree HEAD)
    prompt(env, repo, session="vh6")
    wt2 = os.path.join(work, "wt2")
    git(repo, "worktree", "add", "-q", "-b", "ticket-2", wt2, env=env)
    shell_write(os.path.join(wt2, "src", "app", "core.py"), "def add(a, b):\n    return a - b\n", ago_s=30)
    git(wt2, "add", "src/app/core.py", env=env)
    git(wt2, "commit", "-q", "--no-verify", "-m", "x", env=env)
    why = stop(env, wt2, event="SubagentStop", agent_id="sub4", session="vh6")
    assert why and "src/app/core.py" in why, "committed in the turn, no run after it: %s" % why


def t_vh_used_needs_run_after_last_change(work):
    """Owner 2026-11-18: proof after the LAST change. Change A, a valid run, then change B: the turn is blocked
    until a new run finishes after B."""
    repo, env = vh_repo(work, "app")
    run_log_ago(repo, "20261117T100000Z-old", 7200)
    prompt(env, repo)
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n", ago_s=600)
    run_log_ago(repo, "20261118T100000Z-after-a", 300)
    shell_write(os.path.join(repo, "src", "app", "extra.py"), "def sub(a, b):\n    return a - b\n", ago_s=120)
    why = stop(env, repo, session="vh")
    assert why and "verify-tool-used" in why and "last change" in why, why
    run_log_ago(repo, "20261118T100500Z-after-b", 30)
    assert stop(env, repo, session="vh", stop_hook_active=True) is None, "a valid run after the last change: ends"


def t_vh_used_invalid_logs(work):
    repo, env = vh_repo(work, "app")
    run_log_ago(repo, "20261117T100000Z-old", 7200)
    prompt(env, repo)
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n", ago_s=600)
    run_log_ago(repo, "20261118T100000Z-fail", 60, doctor="FAIL")
    why = stop(env, repo, session="vh")
    assert why and "verify-tool-used" in why and "doctor FAIL" in why, why
    run_log_ago(repo, "20261118T100100Z-sql", 50, db="yes")
    why = stop(env, repo, session="vh")
    assert why and "db_writes yes" in why, why
    run_log_ago(repo, "20261118T100200Z-short", 40, lines=["doctor: PASS", "db_writes: no"])
    prompt(env, repo, session="vhb")      # same tree in a new turn would need a new change: new session instead
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a + 0\n", ago_s=500)
    why = stop(env, repo, session="vhb")
    assert why and "missing commit, finished" in why, why
    run_log_ago(repo, "20261118T100300Z-good", 30)
    assert stop(env, repo, session="vhb", stop_hook_active=True) is None, "valid: doctor PASS, db_writes no"


def t_vh_loop_limit(work):
    repo, env = vh_repo(work, "app")
    run_log_ago(repo, "20261117T100000Z-old", 7200)
    prompt(env, repo)
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    assert stop(env, repo), "block 1"
    assert stop(env, repo, stop_hook_active=True), "block 2 (same tree)"
    assert stop(env, repo, stop_hook_active=True) is None, "2 blocks on the same tree: no endless block"
    for i in range(3):      # a new tree each time: the chain cap of 4 still ends it
        shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return %d\n" % i)
        stop(env, repo, stop_hook_active=True)
    prompt(env, repo, session="vh5")
    shell_write(os.path.join(repo, "src", "app", "x.py"), "X = 1\n")
    outs = [stop(env, repo, session="vh5", stop_hook_active=i > 0) for i in range(6)]
    assert sum(1 for o in outs if o) <= 4 and outs[0], outs


def t_vh_symlink_does_not_hang(work):
    """Review S7: a code file that is a symlink to /dev/zero cannot hang the Stop hook. The hook does not follow
    links and reads at most 1 MB of a file; the new link still counts as a change."""
    repo, env = vh_repo(work, "app")
    prompt(env, repo)
    os.symlink("/dev/zero", os.path.join(repo, "src", "app", "zero.py"))
    payload = {"session_id": "vh", "cwd": repo, "stop_hook_active": False}
    try:
        res = subprocess.run([sys.executable, ROUTER, "--agent", "claude", "Stop"], env=env, cwd=repo,
                             input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=30)
    except subprocess.TimeoutExpired:
        raise AssertionError("the Stop hook ran over 30 s on a symlink to /dev/zero")
    out = res.stdout.decode("utf-8", "replace")
    assert "[ai router: verify-tool-" in out and "src/app/zero.py" in out, out


def t_vh_codex_stop_block(work):
    repo, env = vh_repo(work, "app", verify=False)
    hook("UserPromptSubmit", {"session_id": "cx", "cwd": repo, "prompt": "change add", "turn_id": "t1"}, env,
         agent="codex")
    shell_write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    why = stop(env, repo, agent="codex", session="cx", turn_id="t1")
    assert why and "verify-tool-exists" in why and "create-verification-skill" in why, why


def precommit_hook(repo):
    """The pre-commit hook ai-adopt installs, calling this checkout's ai-precommit (shared by linked worktrees)."""
    path = os.path.join(repo, ".git", "hooks", "pre-commit")
    write(path, "#!/bin/sh\nexec %s %s\n" % (sys.executable, os.path.join(BIN, "ai-precommit")))
    os.chmod(path, 0o755)


def commit(repo, env, rel, text):
    write(os.path.join(repo, rel), text)
    git(repo, "add", "-A", env=env)
    return git(repo, "commit", "-q", "-m", "add " + rel, env=env)


def t_vh_commit_gate_python(work):
    repo, env = vh_repo(work, "app", old_commit=True)
    precommit_hook(repo)
    git(repo, "config", "diff.mnemonicPrefix", "true", env=env)     # the owner's config: i/ and w/, not a/ and b/
    run_log_ago(repo, "20261118T080000Z-before-head", 3 * 3600)
    res = commit(repo, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode != 0 and "verify-app" in res.text and LAUNCH in res.text, res.text
    assert "tests/test_more.py" in res.text and "test_more" in res.text, res.text
    assert '"wall": "verify-commit"' in (read(os.path.join(env["AI_STATE_DIR"], "walls.jsonl")) or "")
    run_log_ago(repo, "20261118T110000Z-bad", 60, doctor="FAIL")
    assert commit(repo, env, "tests/test_more.py", "def test_more():\n    assert 1\n").returncode != 0, \
        "an invalid run does not count"
    run_log_ago(repo, "20261118T110050Z-sql", 45, db="yes")       # review P3: a direct database write
    res = commit(repo, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode != 0 and "db_writes yes" in res.text, "a run with db_writes: yes does not count: " + res.text
    run_log_ago(repo, "20261118T110100Z-good", 30)
    res = commit(repo, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode == 0, res.text
    # the next new test needs a run newer than this commit
    res = commit(repo, env, "tests/test_again.py", "async def test_again():\n    assert 1\n")
    assert res.returncode != 0, "a fresh run is per commit: %s" % res.text


def t_vh_commit_gate_after_evidence_commit(work):
    """verify-evidence-in-git: a commit that adds only the run folder does not make the run older than HEAD."""
    repo, env = vh_repo(work, "appev", old_commit=True)
    write(os.path.join(repo, ".gitignore"), ".verify/*\n!.verify/evidence/\n")
    git(repo, "commit", "-qam", "chore: ignore", "--no-verify", "--date", "@%d +0000" % (time.time() - 3600),
        env=dict(env, GIT_COMMITTER_DATE="@%d +0000" % (time.time() - 3600)))
    precommit_hook(repo)
    run_log_ago(repo, "20261118T110100Z-good", 30)
    git(repo, "add", ".verify/evidence", env=env)
    git(repo, "commit", "-qm", "chore: verify evidence", "--no-verify", env=env)
    res = commit(repo, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode == 0, res.text


def t_vh_commit_gate_owner_skip(work):
    """Review T2: the commit gate honours the owner skip (sudo ai-gate-skip verify-commit <minutes> <why>) and logs
    it. The router's test-only skip file variables are not read here: an agent's command sets the env of git and
    its hooks. The root-owned file is stood in for in-process (hooklib.gate_skip_path)."""
    repo, env = vh_repo(work, "app", old_commit=True)
    skip = os.path.join(work, "gate-skip")
    write(skip, "verify-commit %d the owner drove it by hand\n" % (time.time() + 600))
    write(os.path.join(repo, "tests", "test_more.py"), "def test_more():\n    assert 1\n")
    git(repo, "add", "tests/test_more.py", env=env)
    precommit = os.path.join(BIN, "ai-precommit")
    res = run([sys.executable, precommit, "--dir", repo],
              env=dict(env, AI_GATE_SKIP_FILE=skip, AI_GATE_SKIP_INSECURE_TEST="1"))
    assert res.returncode != 0 and "verify-app" in res.text, "env variables opened the gate: " + res.text
    stand_in = ("import runpy, sys; sys.path.insert(0, %r); import hooklib; "
                "hooklib.gate_skip_path = lambda env_ok=True: (%r, True); "
                "sys.argv = ['ai-precommit', '--dir', %r]; runpy.run_path(%r, run_name='__main__')"
                % (HOOKS, skip, repo, precommit))
    res = run([sys.executable, "-c", stand_in], env=env)
    assert res.returncode == 0 and "skipped by the owner" in res.text, res.text
    gates = read(os.path.join(env["AI_STATE_DIR"], "gates.log")) or ""
    assert "SKIP verify-commit" in gates and "drove it by hand" in gates, gates


def t_vh_commit_edits_and_no_skill_pass(work):
    repo, env = vh_repo(work, "app")
    precommit_hook(repo)
    res = commit(repo, env, "tests/test_core.py",
                 "from app.core import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n")
    assert res.returncode == 0, "an edit of an existing test passes: %s" % res.text
    os.unlink(os.path.join(repo, "tests", "test_core.py"))
    git(repo, "add", "-A", env=env)
    res = git(repo, "commit", "-q", "-m", "drop", env=env)
    assert res.returncode == 0, "a deleted test passes: %s" % res.text
    res = commit(repo, env, "src/app/more.py", "def test_like_name_in_app():\n    pass\n")
    assert res.returncode != 0, "a test function is a test function, in any .py file"
    bare, env2 = vh_repo(work, "bare", verify=False)
    precommit_hook(bare)
    res = commit(bare, env2, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode == 0, "no verify skill: hook 1 covers it, the commit passes: %s" % res.text


def t_vh_commit_gate_js(work):
    files = {"package.json": "{}\n", "src/server.js": "module.exports = {};\n",
             "test/app.test.js": "const test = require('node:test');\ntest('home', () => {});\n"}
    repo, env = vh_repo(work, "web", files=files)
    precommit_hook(repo)
    res = commit(repo, env, "test/app.test.js",
                 "const test = require('node:test');\ntest('home', () => {});\ntest('about', () => {});\n")
    assert res.returncode != 0 and "about" in res.text, res.text
    git(repo, "reset", "-q", "--hard", env=env)
    res = commit(repo, env, "src/page.spec.ts", "describe('page', () => {\n  it('renders', () => {});\n});\n")
    assert res.returncode != 0 and "renders" in res.text, res.text
    git(repo, "reset", "-q", "--hard", env=env)
    res = commit(repo, env, "src/util.ts", "export const it = (x: number) => x;\nit(1);\n")
    assert res.returncode == 0, "it( outside a spec file is not a test: %s" % res.text


def t_vh_commit_gate_worktree(work):
    repo, env = vh_repo(work, "app", old_commit=True)
    precommit_hook(repo)
    wt = os.path.join(work, "wt")
    git(repo, "worktree", "add", "-q", "-b", "ticket-1", wt, env=env)
    run_log_ago(repo, "20261118T110000Z-main", 30)
    res = commit(wt, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode != 0 and wt in res.text, "the main checkout's run is not proof for the worktree: " + res.text
    run_log_ago(wt, "20261118T110100Z-wt", 20)
    res = commit(wt, env, "tests/test_more.py", "def test_more():\n    assert 1\n")
    assert res.returncode == 0, res.text


# ---------------------------------------------------------------- ai-versions

def t_versions_record(work):
    state = os.path.join(work, "state")
    env = env_for(work, AI_STATE_DIR=state, PATH=fake_tool(work, "graphify", "echo graphify 0.9.111")
                  + os.pathsep + "/usr/bin:/bin")
    v = os.path.join(BIN, "ai-versions")
    res = run([sys.executable, v, "--record"], env=env)
    assert res.returncode == 0 and not os.path.exists(os.path.join(state, "upgrades.json")), "first run only records"
    assert json.load(open(os.path.join(state, "versions.json")))["graphify"] == "0.9.111"
    fake_tool(work, "graphify", "echo graphify 0.9.120")
    res = run([sys.executable, v, "--record"], env=env)
    assert "graphify 0.9.111 -> 0.9.120" in res.text, res.text
    fake_tool(work, "graphify", "echo graphify 0.9.130")
    run([sys.executable, v, "--record"], env=env)
    pend = json.load(open(os.path.join(state, "upgrades.json")))["pending"]
    assert pend == [dict(pend[0], tool="graphify", old="0.9.111", new="0.9.130")], pend


def t_versions_upgrade_review(work):
    """Ticket rules-that-hold 11: --upgrade-review runs the skill once while rows are pending. Without claude the
    output names the command for the owner, and the exit code stays 0."""
    state, log = os.path.join(work, "state"), os.path.join(work, "claude.log")
    bindir = fake_tool(work, "graphify", "echo graphify 0.9.111")
    fake_tool(work, "claude", 'case "$1" in --version) echo "2.1.5 (Claude Code)";; '
                              '*) echo "$(pwd) $*" >> %s;; esac' % log)
    env = env_for(work, AI_STATE_DIR=state, AI_SRC_HOME=work, PATH=bindir + os.pathsep + "/usr/bin:/bin")
    rec = [sys.executable, os.path.join(BIN, "ai-versions"), "--record", "--upgrade-review"]
    run(rec, env=env)
    assert not os.path.exists(log), "no pending row: no review"

    fake_tool(work, "graphify", "echo graphify 0.9.120")
    res = run(rec, env=env)
    assert res.returncode == 0 and "graphify 0.9.111 -> 0.9.120" in res.text, res.text
    assert read(log) == "%s -p /upgrade-review\n" % os.path.realpath(work), read(log)

    os.remove(os.path.join(bindir, "claude"))
    fake_tool(work, "graphify", "echo graphify 0.9.130")
    res = run(rec, env=env)
    assert res.returncode == 0 and 'cd %s && claude -p "/upgrade-review"' % work in res.text, res.text


# ---------------------------------------------------------------- scenarios: ai-adopt

def t_scenario_small_new_project(work):
    """A small new Python project: UI on, project rules, pre-commit hook, the new default skill, docs clean."""
    files = dict(PY_APP)
    files["pyproject.toml"] += "\n[tool.ruff]\nline-length = 120\n"
    files[".gitignore"] = ".venv/\n"
    repo, env = new_repo(work, "small", files)
    venv_py = os.path.join(repo, ".venv", "bin", "python")     # the project venv: ruff and pytest "run" here
    write(venv_py, "#!/bin/sh\nexit 0\n")
    os.chmod(venv_py, 0o755)
    res = adopt(repo, env)
    assert res.returncode == 0, res.text
    enabled = read(os.path.join(repo, ".ai", "enabled"))
    assert "\nui\n" in enabled and "improve-codebase-architecture" in enabled, enabled
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert "## Project rules" in agents and "never loosen" in agents, agents
    assert "- Design: `design-system/small/MASTER.md`" in agents and "3 to 5 directions" in agents, agents
    assert "ui-ux-pro-max@ui-ux-pro-max-skill" in read(os.path.join(repo, ".claude", "settings.json"))
    assert "design-system/" in read(os.path.join(repo, "CODING_STANDARDS.md"))
    hook_text = read(os.path.join(repo, ".git", "hooks", "pre-commit")) or ""
    assert "ai-precommit" in hook_text and os.access(os.path.join(repo, ".git", "hooks", "pre-commit"), os.X_OK)
    msg_hook = os.path.join(repo, ".git", "hooks", "commit-msg")
    assert 'ai-precommit --commit-msg "$1"' in (read(msg_hook) or "") and os.access(msg_hook, os.X_OK), \
        "ticket rth-07: the commit-msg hook sits next to the pre-commit hook"
    assert not os.path.exists(os.path.join(repo, ".ai", "docs-allow")), "no stray Markdown: no baseline file"
    assert "ai-docs-check" in read(os.path.join(repo, "Makefile")), "make check runs the Markdown check"
    res = adopt(repo, env)
    assert "nothing to change" in res.text, "rerun must be idempotent: " + res.text


def t_scenario_adopt_existing_mess(work):
    """An existing messy repo: stray Markdown, its own Rules and Done sections, its own husky hooks."""
    files = dict(PY_APP)
    files.update({"NOTES.md": "x", "SUMMARY.md": "y", "src/app/TODO.md": "z",
                  "AGENTS.md": "# mess\n\n## Rules (mandatory)\n- never touch prod\n\n## Done means\n- tests pass\n"})
    repo, env = new_repo(work, "mess", files)
    git(repo, "config", "core.hooksPath", ".husky", env=env)
    res = adopt(repo, env)
    assert res.returncode == 0, res.text
    assert "core.hooksPath is .husky" in res.text, res.text
    assert not os.path.exists(os.path.join(repo, ".git", "hooks", "pre-commit"))
    allow = read(os.path.join(repo, ".ai", "docs-allow")) or ""
    for f in ("NOTES.md", "SUMMARY.md", "src/app/TODO.md"):
        assert f in allow, allow
    committed = git(repo, "show", "--name-only", "--format=", "HEAD", env=env).text.split()
    assert ".ai/docs-allow" in committed, committed
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert agents.count("Rules") == 1 or "## Project rules" not in agents, "own Rules section kept, no second one"
    assert "keep: AGENTS.md has its own Done section" in res.text, res.text
    assert run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env).returncode == 0
    write(os.path.join(repo, "PLAN.md"), "new stray\n")
    assert run([sys.executable, os.path.join(BIN, "ai-docs-check"), "--dir", repo], env=env).returncode == 1


def t_scenario_own_precommit_kept(work):
    repo, env = new_repo(work, "ownhook", dict(PY_APP))
    write(os.path.join(repo, ".git", "hooks", "pre-commit"), "#!/bin/sh\necho mine\n")
    res = adopt(repo, env)
    assert "pre-commit is the repo's own" in res.text, res.text
    assert read(os.path.join(repo, ".git", "hooks", "pre-commit")) == "#!/bin/sh\necho mine\n"


def t_scenario_web_ui(work):
    """A web UI repo with a design system: the Design line has no 'missing' note; the ui nudge points to it."""
    files = {"package.json": json.dumps({"name": "shop", "scripts": {"test": "vitest run", "lint": "eslint ."}}),
             "src/App.tsx": "export const App = () => null\n", "design-system/shop/MASTER.md": "# Master\n"}
    repo, env = new_repo(work, "shop", files)
    res = adopt(repo, env)
    assert res.returncode == 0, res.text
    agents = read(os.path.join(repo, "AGENTS.md"))
    line = [ln for ln in agents.splitlines() if ln.startswith("- Design:")]
    assert line and "missing" not in line[0], line
    out = hook("UserPromptSubmit", {"session_id": "w1", "cwd": repo, "prompt": "make the landing page layout nicer"},
               env)
    assert "ui-ux-pro-max" in out and "MASTER.md" in out, out


def t_scenario_mobile_no_serena(work):
    """A mobile repo where the owner turned Serena off: the navigation nudge names graphify only."""
    files = {"ios/App/AppDelegate.swift": "import UIKit\n", "android/app/src/Main.kt": "fun main() {}\n",
             ".ai/enabled": "tier: long\nno-serena\n", "graphify-out/graph.json": "{}"}
    repo, env = new_repo(work, "mobile", files)
    out = hook("PreToolUse", {"session_id": "m1", "cwd": repo, "tool_name": "Grep",
                              "tool_input": {"pattern": "AppDelegate"}}, env)
    assert "graphify query" in out and "Serena" not in out, out


def t_scenario_long_evolution(work):
    """Many merges over time: the session start no longer asks for the review (the ship skill names it)."""
    repo, env = new_repo(work, "evolve", dict(PY_APP))
    assert adopt(repo, env).returncode == 0
    git(repo, "switch", "-q", "main", env=env)      # the owner merges the ai-adopt branch (owner 2026-11-16)
    git(repo, "merge", "-q", "ai-adopt", env=env)
    start = {"session_id": "e0", "cwd": repo, "source": "startup"}
    for i in range(3):      # three features merged into main
        git(repo, "switch", "-q", "-c", "feat-%d" % i, env=env)
        write(os.path.join(repo, "src", "app", "f%d.py" % i), "x = %d\n" % i)
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-q", "--no-verify", "-m", "feat %d" % i, env=env)
        git(repo, "switch", "-q", "main", env=env)
        git(repo, "merge", "-q", "--no-ff", "-m", "merge %d" % i, "feat-%d" % i, env=env)
    out = hook("SessionStart", dict(start, session_id="e1"), env)
    assert "moved since the last architecture review" not in out, out


# ---------------------------------------------------------------- negative: trying to get around the rules

def t_negative_merge_paths(work):
    """Every way an agent might merge without the owner's OK is denied; the owner's OK lets one through."""
    repo, env = new_repo(work, "neg", dict(PY_APP))
    sess = {"session_id": "n1", "cwd": repo}
    attempts = ["gh pr merge 7 --squash", "gh pr merge --admin 7", "gh api -X PUT repos/o/r/pulls/7/merge",
                "git push origin HEAD:main", "git push origin feat:refs/heads/main", "git push --mirror origin",
                "sh -c 'gh pr merge 7'", "env FOO=1 gh pr merge 7", "rtk gh pr merge 7", "git push -f origin main"]
    for cmd in attempts:
        out = hook("PreToolUse", dict(sess, tool_name="Bash", tool_input={"command": cmd}), env)
        assert decision(out) == "deny", "%s was not denied: %s" % (cmd, out)
    hook("UserPromptSubmit", dict(sess, prompt="it is approved?"), env)
    assert decision(hook("PreToolUse", dict(sess, tool_name="Bash", tool_input={"command": "gh pr merge 7"}),
                         env)) == "deny", "a question is no OK"
    hook("UserPromptSubmit", dict(sess, prompt="ok, merge it"), env)
    assert decision(hook("PreToolUse", dict(sess, tool_name="Bash", tool_input={"command": "gh pr merge 7"}),
                         env)) == "allow"
    hook("UserPromptSubmit", dict(sess, prompt="now add dark mode"), env)
    assert decision(hook("PreToolUse", dict(sess, tool_name="Bash", tool_input={"command": "gh pr merge 8"}),
                         env)) == "deny", "the OK does not carry over to the next request"


def t_negative_skip_hooks(work):
    repo, env = new_repo(work, "neg2", dict(PY_APP))
    sess = {"session_id": "n2", "cwd": repo}
    for cmd in ("git commit --no-verify -m x", "git commit -anm x", "git push --no-verify origin feat",
                "bash -c 'git commit --no-verify -m x'"):
        out = hook("PreToolUse", dict(sess, tool_name="Bash", tool_input={"command": cmd}), env)
        assert decision(out) == "deny", "%s was not denied: %s" % (cmd, out)


def t_negative_codex_merge(work):
    repo, env = new_repo(work, "neg3", dict(PY_APP))
    out = hook("PreToolUse", {"session_id": "c1", "turn_id": "t", "cwd": repo, "tool_name": "Bash",
                              "tool_input": {"command": "gh pr merge 3"}}, env, agent="codex")
    assert '"decision": "block"' in out, out


def t_adopt_new_branch_pushes_upstream(work):
    """ai-adopt on a new branch (adopt, then a PR) pushes it with an upstream; main is not touched."""
    origin = os.path.join(work, "origin.git")
    run(["git", "init", "-q", "--bare", "-b", "main", origin], env=env_for(work))
    repo, env = new_repo(work, "branchy", dict(PY_APP))
    # the owner check reads the fetch URL (an owner repo); pushes go to the local bare repo (no network)
    git(repo, "remote", "add", "origin", "https://github.com/someone/branchy.git", env=env)
    git(repo, "config", "remote.origin.pushurl", origin, env=env)
    git(repo, "push", "-q", "origin", "main", env=env)
    main_before = git(origin, "rev-parse", "main", env=env).text.strip()
    git(repo, "fetch", "-q", origin, "main:refs/remotes/origin/main", env=env)
    # made from origin/main, so it tracks origin/main: a plain push would refuse (names differ)
    git(repo, "switch", "-q", "-c", "ai-setup", "--track", "origin/main", env=env)
    assert git(repo, "rev-parse", "--abbrev-ref", "@{u}", env=env).text.strip() == "origin/main"
    res = adopt(repo, env)
    assert res.returncode == 0, res.text
    heads = git(origin, "for-each-ref", "--format=%(refname)", "refs/heads", env=env).text
    assert "refs/heads/ai-setup" in heads, heads
    assert git(origin, "rev-parse", "main", env=env).text.strip() == main_before, "main moved"
    assert git(repo, "rev-parse", "--abbrev-ref", "@{u}", env=env).text.strip() == "origin/ai-setup"


def t_adopt_in_linked_worktree(work):
    """ai-adopt in a linked worktree (owner's open work stays in the main checkout): the Design line names the
    project, not the worktree folder; the main checkout's .venv is linked, so the check targets use it."""
    files = dict(PY_APP)
    files[".gitignore"] = ".venv/\n"
    repo, env = new_repo(work, "scriptube", files)
    venv_py = os.path.join(repo, ".venv", "bin", "python")
    write(venv_py, "#!/bin/sh\nexit 0\n")
    os.chmod(venv_py, 0o755)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return a - b  # open work\n")
    wt = os.path.join(work, "wt", "ai-setup-x")
    git(repo, "worktree", "add", "-q", "-b", "ai-setup-x", wt, env=env)
    res = adopt(wt, env)
    assert res.returncode == 0, res.text
    agents = read(os.path.join(wt, "AGENTS.md"))
    assert "design-system/scriptube/MASTER.md" in agents and "ai-setup-x" not in agents, agents
    assert os.path.islink(os.path.join(wt, ".venv")), "main checkout's venv not linked"
    assert ".venv/bin/python -m pytest" in read(os.path.join(wt, "Makefile")), read(os.path.join(wt, "Makefile"))
    assert "a - b  # open work" in read(os.path.join(repo, "src", "app", "core.py")), "open work in main touched"
    assert git(repo, "status", "--porcelain", env=env).text.strip() == "M src/app/core.py", "main checkout changed"


# ---------------------------------------------------------------- ticket 05: the PR gate proves the final tree

PR_BODY = ("## Summary\n```mermaid\ngraph TD; a-->b\n```\n## Evidence\n- **Before:** none\n  **After:** `make check`: "
           "3 passed\n## Merge Danger\n**Door:** two-way, small change\n**Blast Radius:** the add function\n"
           "Docs: none, because no docs change\nChanged guards: none\n<!-- author-sessions\nmain: pr1 dir: ~/w\n-->\n")
VERIFY_APP = {".agents/skills/verify-app/SKILL.md": "---\nname: verify-app\n---\n", ".gitignore": ".verify/\n"}


def run_log(root, name, sha, doctor="PASS", db="no", finished=None):
    finished = finished or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 2))
    write(os.path.join(root, ".verify", "evidence", name, "run.log"),
          "commit: %s\ndoctor: %s\ndb_writes: %s\nfinished: %s\n" % (sha, doctor, db, finished))


def pr_hook(env, cwd, cmd, session="pr1"):
    return hook("PreToolUse", {"session_id": session, "cwd": cwd, "hook_event_name": "PreToolUse",
                               "tool_name": "Bash", "tool_input": {"command": cmd}}, env)


def t_secret_scan_mnemonic_prefix(work):
    """The secret scan reads file paths from `+++ b/<path>`. With git config diff.mnemonicPrefix (c/, i/, w/) the
    path rules were lost: a fake test value under tests/ was judged as app code. The scan fixes the prefixes."""
    repo, env = new_repo(work, "mnemonic", dict(PY_APP))
    git(repo, "config", "diff.mnemonicPrefix", "true", env=env)
    fake = "pass" + "word = " + '"' + "admin" + "pass123" + '"'      # built at run time: the commit gate scans this file
    write(os.path.join(repo, "tests", "test_login.py"), fake + "\n\ndef test_login():\n    assert True\n")
    git(repo, "add", "tests/test_login.py", env=env)
    out = pr_hook(env, repo, "git commit -qm 'test: login'")
    assert decision(out) != "deny" or "secret" not in out, out


# ---------------------------------------------------------------- one entry for a check (ticket 05)

CHECK = os.path.join(BIN, "ai-check")


def check(env, cwd, *args):
    return run([sys.executable, CHECK] + list(args), env=env, cwd=cwd)


def t_check_three_callers(work):
    """The same staged diff goes to the agent hook, to ai-precommit and to ai-check: one decision from each.
    A fake key: all 3 refuse. A clean diff: all 3 pass. The key is built at run time (no secret in the repo)."""
    repo, env = new_repo(work, "three", dict(PY_APP))
    key = "ghp" + "_" + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6"
    for staged, want in (("TOKEN = '%s'\n" % key, "deny"), ("print('hello')\n", "allow")):
        write(os.path.join(repo, "src", "app", "config.py"), staged + "x = 1\n" * 1000)
        git(repo, "add", "-A", env=env)

        hook_says = decision(pr_hook(env, repo, "git commit -m 'add config'"))
        pre = run([sys.executable, os.path.join(BIN, "ai-precommit"), "--dir", repo], env=env, cwd=repo)
        start = time.time()
        cli = check(env, repo, "secret-scan", "--staged")
        print("     ai-check secret-scan --staged, 1,000-line diff: %.2f s" % (time.time() - start))

        got = {"hook": hook_says, "ai-precommit": "deny" if pre.returncode == 1 else "allow",
               "ai-check": "deny" if cli.returncode == 1 else "allow"}
        assert got == dict.fromkeys(got, want), (got, pre.text, cli.text)
        if want == "deny":
            assert "secret-scan" in pre.text and "github-token" in pre.text, pre.text
            assert "secret-scan" in cli.text and "github-token" in cli.text, cli.text
        assert cli.returncode != 2 and pre.returncode != 2, (cli.text, pre.text)


def t_check_cli_contract(work):
    """ai-check: --pr-body names the missing field; --list names each gate it does not offer and why; a session
    gate and bad usage exit 2; outside a git repo --staged exits 2; the text check refuses an em dash."""
    repo, env = new_repo(work, "cli", dict(PY_APP))
    body = os.path.join(work, "body.md")
    write(body, "## Summary\nno diagram\n## Evidence\n- **After:** make check-fast: 3 passed\n")
    res = check(env, repo, "pr-rules", "--pr-body", body)
    assert res.returncode == 1 and "mermaid" in res.text and "Door" in res.text, res.text

    res = check(env, repo, "--list")
    assert res.returncode == 0, res.text
    for gate in ("secret-scan", "pr-rules", "text", "merge-approval", "writing-for-agents", "ship", "ask-first",
                 "gh-write"):
        assert gate in res.text, (gate, res.text)
    assert "owner" in res.text.split("merge-approval", 1)[1].splitlines()[0], res.text

    for args in (("merge-approval", "--staged"), ("secret-scan",), ("nope", "--staged"),
                 ("secret-scan", "--pr-body", body)):
        res = check(env, repo, *args)
        assert res.returncode == 2, (args, res.returncode, res.text)

    plain = os.path.join(work, "not-a-repo")
    os.makedirs(plain)
    res = check(env, plain, "secret-scan", "--staged")
    assert res.returncode == 2 and "not a git repo" in res.text, res.text

    dash = chr(0x2014)
    write(os.path.join(repo, "README.md"), "one %s two\n" % dash)
    git(repo, "add", "README.md", env=env)
    res = check(env, repo, "text", "--staged")
    assert res.returncode == 1 and "README.md:1" in res.text, res.text
    write(body, "a line %s here\n" % dash)
    res = check(env, repo, "text", "--pr-body", body)
    assert res.returncode == 1 and "body.md:1" in res.text, res.text
    res = check(env, repo, "text", "--command", "echo plain")
    assert res.returncode == 0, res.text


def t_check_ci_inputs(work):
    """Ticket rth-06: CI gives the PR title and base branch. A fix: title with no test file in the diff fails;
    main: unknown fails with no session (the session rule); --title and --base need --pr-body."""
    repo, env = new_repo(work, "ci-inputs", dict(PY_APP))
    git(repo, "checkout", "-q", "-b", "feat", env=env)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(repo, "commit", "-qam", "change", "--no-verify", env=env)
    body = os.path.join(work, "ci-body.md")
    write(body, PR_BODY)
    res = check(env, repo, "pr-rules", "--pr-body", body, "--title", "feat: x", "--base", "main")
    assert res.returncode == 0, res.text
    res = check(env, repo, "pr-rules", "--pr-body", body, "--title", "fix: x", "--base", "main")
    assert res.returncode == 1 and "a test file in the diff" in res.text, res.text

    write(body, PR_BODY.replace("main: pr1 dir: ~/w", "main: unknown"))
    res = check(env, repo, "pr-rules", "--pr-body", body, "--base", "main")
    assert res.returncode == 1 and "a real main: line" in res.text, res.text

    for args in (("--staged", "--title", "fix: x"), ("--command", "gh pr create", "--base", "main")):
        res = check(env, repo, "pr-rules", *args)
        assert res.returncode == 2 and "--pr-body" in res.text, (args, res.text)


def t_check_reads_input_as_data(work):
    """--command is parsed, never run: a command that would write a file leaves no file."""
    repo, env = new_repo(work, "data", dict(PY_APP))
    marker = os.path.join(work, "ran")
    res = check(env, repo, "secret-scan", "--command", "touch %s && git commit -m x" % marker)
    assert res.returncode == 0 and not os.path.exists(marker), res.text


# ---------------------------------------------------------------- text lint at commit (ticket 07)
# The em dash is built at run time (chr(0x2014)): the repo holds no literal one.

DASH = chr(0x2014)
LONG_SENTENCE = " ".join(["word"] * 29) + " end."      # 30 words


def text_hooks(repo):
    """The 2 hooks that ai-adopt installs (pre-commit, commit-msg), calling this checkout's ai-precommit."""
    precommit_hook(repo)
    path = os.path.join(repo, ".git", "hooks", "commit-msg")
    write(path, '#!/bin/sh\nexec %s %s --commit-msg "$1"\n' % (sys.executable, os.path.join(BIN, "ai-precommit")))
    os.chmod(path, 0o755)


def t_precommit_em_dash(work):
    """A staged added line with the em dash is refused in each text file type, with the file and line. Old lines,
    deleted lines, a rename and a binary file pass. 2,000 added lines stay fast."""
    files = dict(PY_APP, **{"docs/old.md": "old %s line\n" % DASH, "docs/move.md": "moved %s line\n" % DASH})
    repo, env = new_repo(work, "dash", files)
    text_hooks(repo)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return a + b  # a %s b\n" % DASH)
    write(os.path.join(repo, "notes.txt"), "a %s b\n" % DASH)
    res = commit(repo, env, "conf/app.yaml", "key: 1\nname: a %s b\n" % DASH)
    assert res.returncode != 0, res.text
    for where in ("src/app/core.py:2", "notes.txt:1", "conf/app.yaml:2"):
        assert where in res.text, (where, res.text)
    assert "text-lint-allow" in res.text, "the refusal names the way out for a quote: " + res.text
    git(repo, "reset", "-q", "--hard", env=env)
    git(repo, "clean", "-qfd", env=env)

    res = commit(repo, env, "docs/old.md", "old %s line\nnew clean line\n" % DASH)
    assert res.returncode == 0, "an old line does not block: " + res.text
    res = commit(repo, env, "docs/old.md", "new clean line\n")
    assert res.returncode == 0, "a deleted line passes: " + res.text
    git(repo, "mv", "docs/move.md", "docs/moved.md", env=env)
    res = git(repo, "commit", "-qm", "rename", env=env)
    assert res.returncode == 0, "a rename adds no line: " + res.text
    with open(os.path.join(repo, "logo.bin"), "wb") as fh:
        fh.write(b"\x00\x01" + DASH.encode() + b"\x00")
    git(repo, "add", "logo.bin", env=env)
    res = git(repo, "commit", "-qm", "logo", env=env)
    assert res.returncode == 0, "a binary file is skipped: " + res.text

    write(os.path.join(repo, "big.txt"), "clean line\n" * 2000 + "last %s\n" % DASH)
    git(repo, "add", "big.txt", env=env)
    start = time.time()
    res = check(env, repo, "text", "--staged")
    print("     ai-check text --staged, 2,000-line diff: %.2f s" % (time.time() - start))
    assert res.returncode == 1 and "big.txt:2001" in res.text and time.time() - start < 5, res.text


def t_commit_msg_em_dash(work):
    """The commit-msg hook refuses a message with the em dash. The diff that git commit -v puts under the scissors
    line does not count. A clean message passes."""
    repo, env = new_repo(work, "msg", dict(PY_APP))
    text_hooks(repo)
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "a.txt", env=env)
    res = git(repo, "commit", "-qm", "feat: one %s two" % DASH, env=env)
    assert res.returncode != 0 and "COMMIT_EDITMSG:1" in res.text and "em dash" in res.text, res.text
    msg = os.path.join(work, "msg.txt")
    write(msg, "feat: clean\n\n# ------------------------ >8 ------------------------\n+a %s b\n" % DASH)
    res = run([sys.executable, os.path.join(BIN, "ai-precommit"), "--commit-msg", msg], env=env, cwd=repo)
    assert res.returncode == 0, "the text under the scissors line is not the message: " + res.text
    res = git(repo, "commit", "-qm", "feat: clean", env=env)
    assert res.returncode == 0, res.text


def t_ste_warning_only(work):
    """A Markdown sentence of 30 words gives a warning with the file and line, and the commit passes. The same
    sentence in a Python file gives nothing. AI_STE_STRICT=1 in the owner config makes the warning a failure."""
    repo, env = new_repo(work, "ste", dict(PY_APP))
    text_hooks(repo)
    res = commit(repo, env, "docs/guide.md", "# Guide\n\nShort one.\n%s\n" % LONG_SENTENCE)
    assert res.returncode == 0, res.text
    assert "warning" in res.text and "docs/guide.md:4" in res.text and "30 words" in res.text, res.text
    res = commit(repo, env, "src/app/note.py", "# %s\n" % LONG_SENTENCE)
    assert res.returncode == 0 and "30 words" not in res.text, res.text

    write(os.path.join(work, ".config", "ai", "config.env"), "AI_STE_STRICT=1\n")
    res = commit(repo, env, "docs/more.md", "%s\n" % LONG_SENTENCE)
    assert res.returncode != 0 and "docs/more.md:1" in res.text and "30 words" in res.text, res.text


def t_text_lint_allow(work):
    """A quote of another person: a glob in .ai/text-lint-allow lets it pass. Vendored and generated files pass
    by default (vendor/, node_modules/, lock files, graphify-out/, .verify/evidence/)."""
    repo, env = new_repo(work, "allow", dict(PY_APP))
    text_hooks(repo)
    for rel in ("ai/rules/vendor/up/SKILL.md", "node_modules/x/README.md", "package-lock.json",
                "graphify-out/GRAPH_REPORT.md", ".verify/evidence/run-1/01-cli.txt"):
        write(os.path.join(repo, rel), "a %s b\n" % DASH)
    res = commit(repo, env, "uv.lock", "a %s b\n" % DASH)
    assert res.returncode == 0, "vendored and generated files pass: " + res.text

    res = commit(repo, env, "docs/research/quote.md", "They wrote: a %s b.\n" % DASH)
    assert res.returncode != 0 and "docs/research/quote.md:1" in res.text, res.text
    write(os.path.join(repo, ".ai", "text-lint-allow"), "# quotes of other repos\ndocs/research/*\n")
    res = commit(repo, env, "docs/research/quote.md", "They wrote: a %s b.\n" % DASH)
    assert res.returncode == 0, res.text


def t_pr_gate_verify_log(work):
    """Red: app code on the PR head and only an older log: create, edit and ready are denied. Green: a valid log
    at the head SHA. An invalid log (doctor FAIL, db_writes yes, finished before the code commit) does not count."""
    files = dict(PY_APP, **VERIFY_APP)
    repo, env = new_repo(work, "prgate", files)
    body = os.path.join(work, "body.md")
    write(body, PR_BODY)
    git(repo, "switch", "-q", "-c", "feat", env=env)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(repo, "commit", "-qam", "feat: add", env=env)
    old = git(repo, "rev-parse", "main", env=env).text.strip()
    head = git(repo, "rev-parse", "HEAD", env=env).text.strip()
    run_log(repo, "r-old", old)
    create = "gh pr create --title 'feat: add' --body-file %s" % body
    for cmd in (create, "gh pr edit 3 --body-file %s" % body, "gh pr ready 3"):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "deny" and "verify-app" in out and head[:7] in out \
            and "run.log" in out, "%s: %s" % (cmd, out)
    walls = read(os.path.join(env["AI_STATE_DIR"], "walls.jsonl")) or ""
    assert walls.count('"wall": "verify-pr"') >= 3 and "verify-app" in walls, walls     # review P2: hook 4 alone
    for kw in ({"doctor": "FAIL"}, {"db": "yes"}, {"finished": "2001-01-01T00:00:00Z"}):
        shutil.rmtree(os.path.join(repo, ".verify"))
        run_log(repo, "r-bad", head, **kw)
        assert decision(pr_hook(env, repo, create)) == "deny", "invalid log %s counted" % kw
    run_log(repo, "r-head", head)
    for cmd in (create, "gh pr edit 3 --body-file %s" % body):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "allow", "%s: %s" % (cmd, out)
    hook("PostToolUse", {"session_id": "pr1", "cwd": repo, "tool_name": "Skill", "tool_input": {"skill": "ship"}}, env)
    out = pr_hook(env, repo, "gh pr ready 3")
    assert decision(out) == "allow", out


def t_pr_gate_evidence_commit(work):
    """verify-evidence-in-git: the run folder is committed after the run. That commit moves the PR head, but it
    changes only .verify/evidence/, so the log at the last code commit still counts."""
    files = dict(PY_APP, **VERIFY_APP)
    files[".gitignore"] = ".verify/*\n!.verify/evidence/\n"
    repo, env = new_repo(work, "previd", files)
    body = os.path.join(work, "body.md")
    write(body, PR_BODY)
    git(repo, "switch", "-q", "-c", "feat", env=env)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(repo, "commit", "-qam", "feat: add", env=env)
    code = git(repo, "rev-parse", "HEAD", env=env).text.strip()
    run_log(repo, "r-code", code)
    git(repo, "add", ".verify/evidence", env=env)
    git(repo, "commit", "-qm", "chore: verify evidence", "--no-verify", env=env)
    assert git(repo, "rev-parse", "HEAD", env=env).text.strip() != code
    out = pr_hook(env, repo, "gh pr create --title 'feat: add' --body-file %s" % body)
    assert decision(out) == "allow", out


def t_pr_gate_edit_without_body(work):
    """Hook 4 judges PR content: `gh pr edit` without --body or --body-file (a title or a label) is not gated, even
    with only an old log. An edit with a body is gated (t_pr_gate_verify_log)."""
    repo, env = new_repo(work, "predit", dict(PY_APP, **VERIFY_APP))
    git(repo, "switch", "-q", "-c", "feat", env=env)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(repo, "commit", "-qam", "feat: add", env=env)
    run_log(repo, "r-old", git(repo, "rev-parse", "main", env=env).text.strip())
    for cmd in ("gh pr edit 3 --title y", "gh pr edit 3 --add-label wip", "gh pr edit 3 --remove-label wip"):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "allow", "%s: %s" % (cmd, out)


def t_pr_gate_docs_only(work):
    """A PR without app code is not gated (no log at all)."""
    repo, env = new_repo(work, "prdocs", dict(PY_APP, **VERIFY_APP))
    body = os.path.join(work, "body.md")
    write(body, PR_BODY)
    git(repo, "switch", "-q", "-c", "docs", env=env)
    write(os.path.join(repo, "README.md"), "# app\n")
    git(repo, "add", "README.md", env=env)
    git(repo, "commit", "-qm", "docs: readme", env=env)
    out = pr_hook(env, repo, "gh pr create --title 'docs: readme' --body-file %s" % body)
    assert decision(out) == "allow", out


def t_pr_gate_reads_worktree(work):
    """`cd <worktree> && gh pr create`: root and HEAD come from the worktree, not the session's main checkout."""
    repo, env = new_repo(work, "prwt", dict(PY_APP, **VERIFY_APP))
    body = os.path.join(work, "body.md")
    write(body, PR_BODY)
    run_log(repo, "r-main", git(repo, "rev-parse", "HEAD", env=env).text.strip())
    wt = os.path.join(work, "wt-feat")
    git(repo, "worktree", "add", "-q", "-b", "feat", wt, env=env)
    write(os.path.join(wt, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(wt, "commit", "-qam", "feat: add", env=env)
    cmd = "cd %s && gh pr create --title 'feat: add' --body-file %s" % (wt, body)
    out = pr_hook(env, repo, cmd)
    assert decision(out) == "deny" and "verify-app" in out, out
    run_log(wt, "r-wt", git(wt, "rev-parse", "HEAD", env=env).text.strip())
    out = pr_hook(env, repo, cmd)
    assert decision(out) == "allow", out


def pr_feature(work, name):
    """A verify-app repo with app code changed on the branch feat (no run log). Returns repo, env, body, feat head."""
    repo, env = new_repo(work, name, dict(PY_APP, **VERIFY_APP))
    body = os.path.join(work, "body.md")
    write(body, PR_BODY)
    git(repo, "switch", "-q", "-c", "feat", env=env)
    write(os.path.join(repo, "src", "app", "core.py"), "def add(a, b):\n    return b + a\n")
    git(repo, "commit", "-qam", "feat: add", env=env)
    return repo, env, body, git(repo, "rev-parse", "HEAD", env=env).text.strip()


def t_pr_gate_failed_cd_uses_session_root(work):
    """Review S2: `cd <not a checkout>; gh pr create` gave no root and skipped the verify-log, test-file and size
    checks. The gate falls back to the session root."""
    repo, env, body, head = pr_feature(work, "prcd")
    for cmd in ("cd /nonexistent-ai-gate-test; gh pr create --title 'feat: add' --body-file %s" % body,
                "cd %s; gh pr create --title 'feat: add' --body-file %s" % (work, body)):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "deny" and "verify-app" in out and head[:7] in out, "%s: %s" % (cmd, out)


def t_pr_gate_pr_number_head(work):
    """Review P1: `gh pr edit N` and `gh pr ready N` (or a PR URL) judge the PR head that gh reports
    (gh pr view N --json headRefOid), not the local HEAD. When gh cannot answer, or the head is not in this
    checkout, the gate judges the local HEAD and says so."""
    repo, env, body, head = pr_feature(work, "prnum")
    git(repo, "switch", "-q", "main", env=env)
    bindir, log = os.path.join(work, "bin"), os.path.join(work, "gh.log")
    gh = os.path.join(bindir, "gh")
    write(gh, '#!/bin/sh\necho "$*" >> %s\n[ "$1 $2" = "pr view" ] || exit 1\ncat %s\n'
          % (log, os.path.join(work, "gh-answer")))
    os.chmod(gh, 0o755)
    env = dict(env, PATH=bindir + os.pathsep + env["PATH"])
    write(os.path.join(work, "gh-answer"), head + "\n")
    for cmd in ("gh pr edit 3 --body-file %s" % body, "gh pr ready https://github.com/o/r/pull/3"):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "deny" and "verify-app" in out and head[:7] in out, "%s: %s" % (cmd, out)
    calls = read(log) or ""
    assert "pr view 3 --json headRefOid -q .headRefOid" in calls, calls
    assert "pr view https://github.com/o/r/pull/3 --json headRefOid" in calls, calls
    run_log(repo, "r-head", head)
    out = pr_hook(env, repo, "gh pr edit 3 --body-file %s" % body)
    assert decision(out) == "allow", out
    write(os.path.join(work, "gh-answer"), "f" * 40 + "\n")        # a head this checkout does not have
    out = pr_hook(env, repo, "gh pr edit 3 --body-file %s" % body)
    assert "judged the local HEAD" in out, out
    os.unlink(os.path.join(work, "gh-answer"))                      # gh fails: no answer
    out = pr_hook(env, repo, "gh pr ready 3")
    assert "judged the local HEAD" in out, out


def t_pr_gate_wall_id(work):
    """Review P2: a deny caused by the verify proof is logged under the wall `verify-pr`, also when the body has
    template problems too; a deny for the body alone stays `pr-rules`."""
    repo, env, body, head = pr_feature(work, "prwall")
    walls = os.path.join(env["AI_STATE_DIR"], "walls.jsonl")
    out = pr_hook(env, repo, "gh pr create --title 'feat: add' --body-file %s" % body)
    assert decision(out) == "deny" and "verify proof" in out, out
    out = pr_hook(env, repo, "gh pr create --title 'feat: add' --body 'no template'")
    assert decision(out) == "deny" and "verify proof" in out and "mermaid" in out, out
    rows = [json.loads(ln) for ln in (read(walls) or "").splitlines() if ln.strip()]
    assert [r["wall"] for r in rows] == ["verify-pr", "verify-pr"], rows
    run_log(repo, "r-head", head)
    out = pr_hook(env, repo, "gh pr create --title 'feat: add' --body 'no template'")
    assert decision(out) == "deny" and "verify proof" not in out, out
    rows = [json.loads(ln) for ln in (read(walls) or "").splitlines() if ln.strip()]
    assert rows[-1]["wall"] == "pr-rules", rows


def t_herdr_picked_on_mac(work):
    """Ticket 08: herdr is picked on a Mac also when it is not installed yet, so tools_herdr puts it on PATH."""
    pick = ('eval "$(sed -n \'/^pick_agents()/,/^}/p; /^profile_agents()/,/^}/p\' %s)"; skip() { :; }; '
            'has() { case "$1" in claude|codex) return 0;; esac; return 1; }; hermes_exists() { return 1; }; '
            'AI_MODE=all; AGENTS=; AI_OS=macos; PROFILE_OPENCODE=0; pick_agents; echo $AGENTS'
            % os.path.join(os.path.dirname(AI_DIR), "install.sh"))
    res = run(["bash", "-c", pick])
    assert res.text.strip() == "claude,codex,herdr", res.text


def t_doctor_herdr(work):
    """Ticket 08: ai-doctor checks the herdr CLI: missing -> WARN; older than the newest stable in resolved.json
    -> WARN; current -> PASS."""
    state = os.path.join(work, "state")
    write(os.path.join(state, "resolved.json"),
          json.dumps({"tools": {"herdr": {"newest": {"version": "0.9.6"}, "source": "github herdrdev/herdr"}}}))
    bindir = os.path.join(work, "bin")
    env = {"AI_STATE_DIR": state, "AI_SYSTEM_STATE_DIR": os.path.join(work, "none"), "HOME": work,
           "PATH": "/usr/bin:/bin"}
    out = doctor_check(env, "check_herdr")
    assert "WARN" in out and "herdr CLI not on PATH" in out, out
    write(os.path.join(bindir, "herdr"), "#!/bin/sh\necho herdr 0.9.5\n")
    os.chmod(os.path.join(bindir, "herdr"), 0o755)
    env["PATH"] = bindir + ":/usr/bin:/bin"
    out = doctor_check(env, "check_herdr")
    assert "WARN" in out and "0.9.5" in out and "0.9.6" in out, out
    write(os.path.join(bindir, "herdr"), "#!/bin/sh\necho herdr 0.9.6\n")
    out = doctor_check(env, "check_herdr")
    assert "PASS" in out and "WARN" not in out and "herdr 0.9.6" in out, out


def doctor_check(env, name):
    """One ai-doctor check run in this process with env; returns what it printed."""
    import contextlib
    import importlib.machinery
    import importlib.util
    import io
    old = dict(os.environ)
    os.environ.update(env)
    try:
        loader = importlib.machinery.SourceFileLoader("ai_doctor_flow", os.path.join(BIN, "ai-doctor"))
        spec = importlib.util.spec_from_loader("ai_doctor_flow", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            getattr(mod, name)()
        return buf.getvalue()
    finally:
        os.environ.clear()
        os.environ.update(old)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
