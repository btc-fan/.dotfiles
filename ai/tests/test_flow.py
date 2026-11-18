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
    # the session start says so, once per session start, until the skill clears it
    out = hook("SessionStart", {"session_id": "s1", "cwd": work, "source": "startup"}, env)
    assert "graphify 0.9.111 -> 0.9.130" in out and "upgrade-review" in out, out


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
    """Many merges over time: each move of main asks for the review once; recording it quiets it."""
    repo, env = new_repo(work, "evolve", dict(PY_APP))
    assert adopt(repo, env).returncode == 0
    git(repo, "switch", "-q", "main", env=env)      # the owner merges the ai-adopt branch (owner 2026-11-16)
    git(repo, "merge", "-q", "ai-adopt", env=env)
    start = {"session_id": "e0", "cwd": repo, "source": "startup"}
    out = hook("SessionStart", start, env)
    assert "moved since the last architecture review" not in out, "first session only sets the mark"
    for i in range(3):      # three features merged into main
        git(repo, "switch", "-q", "-c", "feat-%d" % i, env=env)
        write(os.path.join(repo, "src", "app", "f%d.py" % i), "x = %d\n" % i)
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-q", "--no-verify", "-m", "feat %d" % i, env=env)
        git(repo, "switch", "-q", "main", env=env)
        git(repo, "merge", "-q", "--no-ff", "-m", "merge %d" % i, "feat-%d" % i, env=env)
    out = hook("SessionStart", dict(start, session_id="e1"), env)
    assert "main moved since the last architecture review (6 new commits" in out, out
    assert "/improve-codebase-architecture" in out and "/retro" in out, out
    git(repo, "rev-parse", "main", env=env)
    write(os.path.join(repo, ".ai", "last-review"), git(repo, "rev-parse", "main", env=env).text.strip() + "\n")
    out = hook("SessionStart", dict(start, session_id="e2"), env)
    assert "moved since" not in out, out


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
    for cmd in (create, "gh pr edit 3 --title y", "gh pr ready 3"):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "deny" and "verify-app" in out and head[:7] in out \
            and "run.log" in out, "%s: %s" % (cmd, out)
    walls = read(os.path.join(env["AI_STATE_DIR"], "walls.jsonl")) or ""
    assert walls.count('"wall": "pr-rules"') >= 3 and "verify-app" in walls, walls
    for kw in ({"doctor": "FAIL"}, {"db": "yes"}, {"finished": "2001-01-01T00:00:00Z"}):
        shutil.rmtree(os.path.join(repo, ".verify"))
        run_log(repo, "r-bad", head, **kw)
        assert decision(pr_hook(env, repo, create)) == "deny", "invalid log %s counted" % kw
    run_log(repo, "r-head", head)
    for cmd in (create, "gh pr edit 3 --title y"):
        out = pr_hook(env, repo, cmd)
        assert decision(out) == "allow", "%s: %s" % (cmd, out)
    hook("PostToolUse", {"session_id": "pr1", "cwd": repo, "tool_name": "Skill", "tool_input": {"skill": "ship"}}, env)
    out = pr_hook(env, repo, "gh pr ready 3")
    assert decision(out) == "allow", out


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
