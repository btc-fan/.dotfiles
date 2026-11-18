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
import re
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
sys.path.insert(0, os.path.join(AI_DIR, "lib"))
import ownertext  # noqa: E402
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


def t_detect_python_no_manifest(work):
    """Ticket 16 (milu: 110 unittest tests left out): a tests/ folder of test_*.py files and no manifest is a
    Python repo. unittest files get the standard library runner, pytest files get pytest; the probe still runs."""
    unit = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n"
    repo = tree(work, "py-unittest", {"tests/test_a.py": unit, "tool.py": "x = 1\n"})
    res = run([sys.executable, os.path.join(BIN, "ai-check-detect"), "--dir", repo, "--json"])
    info = json.loads(res.stdout)
    assert info["ok"] and info["fast"] == ["python3 -m unittest discover -s tests"], info
    assert run(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=repo).returncode == 0
    repo = tree(work, "py-pytest-bare", {"tests/test_b.py": "import pytest\n\n\ndef test_b():\n    pass\n"})
    info = detect(repo)
    assert info["ok"] and info["fast"] == ["python3 -m pytest -x -q"], info


def t_detect_python_pip(work):
    repo = tree(work, "py-pip", {"requirements.txt": "flask==3.0\npytest==8.0\n", "app.py": "x = 1\n"})
    info = detect(repo)
    assert info["ok"] and info["fast"] == ["python3 -m pytest -x -q"], info
    write(os.path.join(repo, ".venv", "bin", "python"), "")
    info = detect(repo)
    assert info["fast"] == [".venv/bin/python -m pytest -x -q"], "a .venv: its python, not the system one: %s" % info
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
    pjust = tree(work, "plan-just-args", {"go.mod": "module x\n",
                                          "justfile": 'check-fast pkg="./...":\n    go test {{pkg}}\nv := "1"\n'})
    p = mod.plan(pjust, mod.detect(pjust), "mvp")
    assert p["kept"] == ["check-fast"] and "\ncheck-fast:" not in p["text"], "a recipe with parameters: %s" % p["text"]
    just = tree(work, "plan-just", {"go.mod": "module x\n", "justfile": "build:\n    go build\n"})
    p = mod.plan(just, mod.detect(just), "mvp")
    assert p["file"] == "justfile" and "\n    go vet ./...\n" in p["text"] and p["fast_cmd"] == "just check-fast", p


def t_plan_keeps_owner_flags(work):
    """QA 2026-11-17: a rerun replaced the managed block and dropped the owner's --durations=50 on the pytest line."""
    mod = load(os.path.join(BIN, "ai-check-detect"), "acd_flags")
    repo = tree(work, "plan-flags", {"pyproject.toml": "[project]\nname='x'\n[tool.ruff]\n", "uv.lock": "",
                                     "tests/test_a.py": "def test_a(): pass\n"})
    write(os.path.join(repo, "Makefile"), mod.plan(repo, mod.detect(repo), "mvp")["text"])
    edited = read(os.path.join(repo, "Makefile")).replace("\tuv run pytest -q\n", "\tuv run pytest -q --durations=50\n")
    assert "--durations=50" in edited, edited
    write(os.path.join(repo, "Makefile"), edited)
    assert mod.plan(repo, mod.detect(repo), "mvp")["text"] is None, "a rerun must keep the owner's flag"
    p = mod.plan(repo, mod.detect(repo), "long")
    assert "ai-ratchet" in p["text"] and "\tuv run pytest -q --durations=50\n" in p["text"], p["text"]


# ---------------------------------------------------------------- T1 + T5: ai-adopt

def t_adopt_own_done(work):
    repo, env = adopt_repo(work, "own-done", {
        "Makefile": "check:\n\tuv run pytest\n",
        "AGENTS.md": "# own\n\n## Done\n- tests pass\n- docs updated\n"})
    res = adopt(repo, env, "--tier", "try")
    assert "--tier is ignored" in res.stdout, res.stdout
    assert res.returncode == 0, res.stdout
    assert "keep: AGENTS.md has its own Done section" in res.stdout, res.stdout
    assert "keep: Makefile already has a check target" in res.stdout, res.stdout
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert agents.count("## Done") == 1 and "<!-- AI:done" not in agents, agents
    mk = read(os.path.join(repo, "Makefile"))
    assert mk.startswith("check:\n\tuv run pytest\n") and mk.count("\ncheck:") == 0 and "check-fast:" in mk, mk
    assert "tier: long" in read(os.path.join(repo, ".ai", "enabled")).splitlines(), "no tiers: always long"
    assert os.path.exists(os.path.join(repo, "docs", "REGRESSIONS.md")), "every project gets the ledger"
    assert "nothing to change" in adopt(repo, env).stdout, "a rerun changes nothing"


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
    # no tiers (owner 2026-11-15): an old --tier flag changes nothing
    res = adopt(repo, env, "--tier", "mvp")
    assert "--tier is ignored" in res.stdout and "nothing to change" in res.stdout, res.stdout
    assert "a line in docs/REGRESSIONS.md" in read(os.path.join(repo, "AGENTS.md")), "Done block lost the ledger"
    assert "ai-ratchet" in read(os.path.join(repo, "Makefile")), "check block lost the ratchet"


def t_adopt_ignores_global_excludes(work):
    """M3 2026-11-15: a personal global ignore (core.excludesFile) hides AGENTS.md, CLAUDE.md and .claude/: the
    adopt commit must still hold them (only the repo's .gitignore counts)."""
    repo, env = adopt_repo(work, "global-ignore", {})
    excl = os.path.join(work, "global-ignore-excludes")
    write(excl, "AGENTS.md\n**/CLAUDE.md\n.claude/\n.serena/\n")
    env = dict(env, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.excludesFile", GIT_CONFIG_VALUE_0=excl)
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    for rel in ("AGENTS.md", "CLAUDE.md"):
        assert rel in files, "%s not committed under a global ignore: %s" % (rel, files)


def t_adopt_monorepo_refused(work):
    repo, env = adopt_repo(work, "mono", {"pnpm-workspace.yaml": "packages: ['a']\n", "package.json": "{}"})
    res = adopt(repo, env)
    assert res.returncode == 0 and "skip check targets: monorepo" in res.stdout, res.stdout
    assert not os.path.exists(os.path.join(repo, "Makefile")), "monorepo: nothing written"


def t_detect_probe_drops_missing_tool(work):
    """QA 2026-11-15 (scriptube): `.venv/bin/python -m ruff` failed, so check-fast failed on a tool not installed."""
    repo = tree(work, "py-probe", {"pyproject.toml": "[project]\nname='x'\n[tool.ruff]\n[tool.mypy]\n",
                                   "tests/test_a.py": "def test_a(): pass\n",
                                   ".venv/bin/python": "#!/bin/sh\ncase \"$2\" in ruff|mypy) exit 1;; esac\nexit 0\n"})
    os.chmod(os.path.join(repo, ".venv", "bin", "python"), 0o755)
    mod = load(os.path.join(BIN, "ai-check-detect"), "acd_probe")
    assert mod.detect(repo)["fast"][0] == ".venv/bin/python -m ruff check .", "no probe: from the files only"
    info = mod.detect(repo, probe=True)
    assert info["fast"] == [".venv/bin/python -m pytest -x -q"], info
    assert info["full"] == [".venv/bin/python -m pytest -q"], info
    assert any("-m ruff --version` fails here" in n and "pip install ruff" in n for n in info["notes"]), info
    res = run([sys.executable, os.path.join(BIN, "ai-check-detect"), "--dir", repo])
    assert "check-fast: .venv/bin/python -m pytest -x -q\n" in res.stdout and "Suggestion" in res.stdout, res.stdout
    write(os.path.join(repo, ".venv", "bin", "python"), "#!/bin/sh\nexit 1\n")
    info = mod.detect(repo, probe=True)
    assert not info["ok"] and "no test or lint command" in info["refuse"] and len(info["notes"]) >= 2, info


FAIL_UV = "#!/bin/sh\ncase \"$*\" in *--version*) exit 0;; esac\necho \"1 failed\"\nexit 1\n"


def t_adopt_failing_check_turns_stop_off(work):
    """QA 2026-11-15: check-fast failed at adopt time, the armed Stop hook then blocked every owner session."""
    repo, env = adopt_repo(work, "check-red", {})
    write(os.path.join(env["PATH"].split(os.pathsep)[0], "uv"), FAIL_UV)
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert "FAILS today" in res.stdout and "Stop hook off until check-fast is green: run make check-fast, fix, " \
        "then remove no-stop-check" in res.stdout, res.stdout
    enabled = read(os.path.join(repo, ".ai", "enabled"))
    assert "no-stop-check  # check-fast failed at adopt time" in enabled, enabled
    shown = run(["git", "-C", repo, "show", "HEAD:.ai/enabled"]).stdout
    assert "no-stop-check" in shown, "the off switch is committed: " + shown
    # Baseline 2026-11-16 (project-copy): the second run wrote .ai/enabled again without the comment, a new commit.
    head = run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout
    adopt(repo, env)
    assert read(os.path.join(repo, ".ai", "enabled")) == enabled, "second run rewrote .ai/enabled"
    assert run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout == head, "second run made a commit"
    env = dict(env, AI_HOME=os.path.dirname(AI_DIR), AI_PROFILE="server")    # Stop check: server profile only
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "new.py"), "y = 2\n")
    assert hook(repo, env, "Stop") is None, "no-stop-check: the Stop hook stays quiet"
    write(os.path.join(repo, ".ai", "enabled"), enabled.replace("no-stop-check", "# was"))
    hook(repo, env, "SessionStart", session="s2")
    write(os.path.join(repo, "src", "new2.py"), "y = 3\n")
    assert hook(repo, env, "Stop", session="s2"), "control: without the line the red check-fast blocks"


def t_adopt_leaves_tree_clean(work):
    """QA 2026-11-17: the check-fast timing, no-stop-check and the docs baseline were written after the commit."""
    # A docs-only repo (check-fast runs ai-docs-check --md) with stray Markdown under an untracked folder.
    repo, env = adopt_repo(work, "clean-docs", {})
    run(["git", "-C", repo, "rm", "-rq", "src", "tests", "uv.lock", "pyproject.toml"], env=env)
    run(["git", "-C", repo, "commit", "-qm", "docs only"], env=env)
    env["PATH"] = env["PATH"] + os.pathsep + BIN
    write(os.path.join(repo, "research_notes", "a.md"), "owner notes\n")
    res = adopt(repo, env)
    assert res.returncode == 0 and "check-fast passed" in res.stdout, res.stdout
    assert "no-stop-check  #" not in read(os.path.join(repo, ".ai", "enabled")), "baseline first: " + res.stdout
    status = run(["git", "-C", repo, "status", "--porcelain"]).stdout
    assert status == "?? research_notes/\n", "first run left changes: %r" % status
    # A rerun that rewrites the Makefile measures a red check-fast: the new seconds and no-stop-check are committed.
    repo, env = adopt_repo(work, "clean-rerun", {"AGENTS.md": "# x\n<!-- AI:map START -->\n## Map\n<!-- AI:map END -->\n"})
    adopt(repo, env)
    run(["git", "-C", repo, "rm", "-q", "Makefile"], env=env)
    run(["git", "-C", repo, "commit", "-qm", "no Makefile"], env=env)
    write(os.path.join(env["PATH"].split(os.pathsep)[0], "uv"), FAIL_UV.replace("echo", "sleep 1; echo"))
    res = adopt(repo, env)
    assert "FAILS today" in res.stdout, res.stdout
    status = run(["git", "-C", repo, "status", "--porcelain"]).stdout
    assert status == "", "rerun left changes: %r" % status
    shown = run(["git", "-C", repo, "show", "HEAD:.ai/enabled"]).stdout
    assert "no-stop-check  #" in shown, shown
    shown = run(["git", "-C", repo, "show", "HEAD:AGENTS.md"]).stdout
    assert "measured 1 s" in shown, shown


def t_adopt_commits_on_branch(work):
    """Owner 2026-11-16: never commit on main or master; a repo without a remote gets a warning, not a push."""
    repo, env = adopt_repo(work, "on-main", {})
    run(["git", "-C", repo, "branch", "-M", "main"])
    main_head = run(["git", "-C", repo, "rev-parse", "main"]).stdout
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert run(["git", "-C", repo, "branch", "--show-current"]).stdout.strip() == "ai-adopt", res.stdout
    assert run(["git", "-C", repo, "rev-parse", "main"]).stdout == main_head, "main moved"
    assert "chore(ai)" in run(["git", "-C", repo, "log", "-1", "--format=%s", "ai-adopt"]).stdout
    assert "merge the ai-adopt branch" in res.stdout, res.stdout
    assert "no remote: push and PR are not possible yet" in res.stdout, res.stdout

    repo, env = adopt_repo(work, "on-feature", {})
    run(["git", "-C", repo, "switch", "-q", "-c", "feat-x"])
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert run(["git", "-C", repo, "branch", "--show-current"]).stdout.strip() == "feat-x", "a feature branch stays"
    assert "merge the ai-adopt branch" not in res.stdout, res.stdout


def t_adopt_branch_exists_main_clean(work):
    """Review 2026-11-16 (D5): on main with an ai-adopt branch that already exists, ai-adopt stops BEFORE it
    writes a file, so main stays clean."""
    repo, env = adopt_repo(work, "branch-exists", {".ai/enabled": "no-serena\nno-graph\n"})
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "enabled"], env=env)
    run(["git", "-C", repo, "branch", "-M", "main"])
    run(["git", "-C", repo, "branch", "ai-adopt"])
    head = run(["git", "-C", repo, "rev-parse", "main"]).stdout
    res = adopt(repo, env)
    assert res.returncode == 1 and "ai-adopt" in res.stdout and "exists" in res.stdout, res.stdout
    assert "write " not in res.stdout, "a file was written: " + res.stdout
    status = run(["git", "-C", repo, "status", "--porcelain", "--ignored"]).stdout
    assert status == "", "main is not clean: " + status
    assert run(["git", "-C", repo, "rev-parse", "main"]).stdout == head, "main moved"
    assert run(["git", "-C", repo, "branch", "--show-current"]).stdout.strip() == "main", "the branch changed"


def t_adopt_old_branch(work):
    """Ticket 16 (ScripTube: remote ai-adopt 31a87c00 of merged PR #22): on main with an ai-adopt branch left,
    a merged PR means delete it (local and remote) and start fresh; an open PR means add the commit to it; an
    unknown state (gh fails, no PR) means stop before any write and name the commands. gh is a fake on PATH."""
    def setup(name, state, local):
        repo, env = adopt_repo(work, name, {".ai/enabled": "no-serena\nno-graph\n"})
        run(["git", "-C", repo, "branch", "-M", "main"])
        origin = os.path.join(work, "someone", name + ".git")      # owner "someone" (AI_GITHUB_OWNERS)
        run(["git", "init", "-q", "--bare", "-b", "main", origin])
        run(["git", "-C", repo, "remote", "add", "origin", origin])
        run(["git", "-C", repo, "push", "-q", "origin", "main"], env=env)
        run(["git", "-C", repo, "switch", "-q", "-c", "ai-adopt"])
        write(os.path.join(repo, "old.txt"), "old adopt\n")
        run(["git", "-C", repo, "add", "old.txt"], env=env)
        run(["git", "-C", repo, "commit", "-q", "-m", "old adopt"], env=env)
        run(["git", "-C", repo, "push", "-q", "origin", "ai-adopt"], env=env)
        old = run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout.strip()
        run(["git", "-C", repo, "switch", "-q", "main"])
        if not local:
            run(["git", "-C", repo, "branch", "-q", "-D", "ai-adopt"])
        fake = env["PATH"].split(os.pathsep)[0]
        write(os.path.join(fake, "gh"), '#!/bin/sh\n[ "$*" = "pr view ai-adopt --json state -q .state" ] || exit 1\n'
              + ('echo %s\n' % state if state else 'echo "no pull requests found" >&2; exit 1\n'))
        os.chmod(os.path.join(fake, "gh"), 0o755)
        return repo, env, origin, old

    def rev(d, ref):
        return run(["git", "-C", d, "rev-parse", "-q", "--verify", ref]).stdout.strip()

    repo, env, origin, old = setup("old-merged", "MERGED", local=True)
    main_head = rev(repo, "main")
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert rev(repo, "ai-adopt~1") == main_head and rev(origin, "ai-adopt") == rev(repo, "ai-adopt"), res.stdout
    assert not os.path.exists(os.path.join(repo, "old.txt")) and rev(repo, "main") == main_head, res.stdout

    repo, env, origin, old = setup("old-open", "OPEN", local=False)
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert rev(repo, "ai-adopt~1") == old and rev(origin, "ai-adopt") == rev(repo, "ai-adopt"), res.stdout

    repo, env, origin, old = setup("old-unknown", None, local=False)
    res = adopt(repo, env)
    assert res.returncode == 1 and "gh pr view ai-adopt" in res.stdout, res.stdout
    assert "git push origin --delete ai-adopt" in res.stdout and "write " not in res.stdout, res.stdout
    assert run(["git", "-C", repo, "status", "--porcelain"]).stdout == "" and rev(origin, "ai-adopt") == old


def t_adopt_unborn_main(work):
    """Review 2026-11-16 (D5): a repo with no commit yet (unborn main) gets its first commit on ai-adopt."""
    repo = tree(work, "unborn", {"src/app.py": "x = 1\n", ".ai/enabled": "no-serena\nno-graph\n"})
    run(["git", "init", "-q", "-b", "main", repo])
    env = {"HOME": os.path.join(work, "home-unborn"), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "AI_GITHUB_OWNERS": "someone", "AI_CONTEXT7_URL": "http://127.0.0.1:9",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"}
    res = adopt(repo, env, "--no-measure", "--tier", "mvp")
    assert res.returncode == 0, res.stdout
    assert run(["git", "-C", repo, "branch", "--show-current"]).stdout.strip() == "ai-adopt", res.stdout
    assert run(["git", "-C", repo, "log", "-1", "--format=%s"]).stdout.startswith("chore(ai)"), res.stdout
    assert run(["git", "-C", repo, "rev-parse", "-q", "--verify", "refs/heads/main"]).returncode != 0, \
        "main got a commit"


def t_adopt_init(work):
    """Spec story 31: a folder without git is refused unless --init; never git init in $HOME or /."""
    folder = tree(work, "no-git", {"notes.md": "# Notes\n"})
    env = {"HOME": os.path.join(work, "home-no-git"), "AI_GITHUB_OWNERS": "someone",
           "AI_CONTEXT7_URL": "http://127.0.0.1:9", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"}
    write(os.path.join(folder, ".ai", "enabled"), "no-serena\nno-graph\n")
    argv = [sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", folder, "--yes", "--no-onboard", "--no-knowledge"]
    res = run(argv, env=env)
    assert res.returncode == 1 and "--init" in res.stdout, res.stdout
    assert not os.path.exists(os.path.join(folder, ".git")), "no git init without --init"
    res = run(argv + ["--init"], env=env)
    assert res.returncode == 0, res.stdout
    assert run(["git", "-C", folder, "log", "-1", "--format=%s"]).stdout.startswith("chore(ai)"), res.stdout
    for refused in (env["HOME"], "/"):
        os.makedirs(refused, exist_ok=True)
        res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", refused, "--init", "--yes"], env=env)
        assert res.returncode == 1 and "refused" in res.stdout, (refused, res.stdout)
    assert not os.path.exists(os.path.join(env["HOME"], ".git")), "git init ran in HOME"


def t_adopt_decline_undoes_intent_to_add(work):
    """QA 2026-11-15: N at the commit prompt left the `git add -N` entries (` A` in git status)."""
    repo, env = adopt_repo(work, "decline", {})
    write(os.path.join(repo, ".ai", "enabled"), "no-serena\nno-graph\n")
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--no-onboard", "--no-knowledge",
               "--no-measure", "--tier", "mvp"], env=env, cwd=repo, stdin="n\n")
    assert "files written, not committed" in res.stdout, res.stdout
    status = run(["git", "-C", repo, "status", "--porcelain"]).stdout
    assert status and not any(ln.startswith(" A") or ln.startswith("A") for ln in status.splitlines()), status
    assert "?? Makefile" in status and "?? .ai/" in status, status


def t_typed_only_skill_paths(work):
    """QA 2026-11-15: typed-only skills (disable-model-invocation) cannot go through the Skill tool: the hints
    give the SKILL.md path to read, the project link per agent first, then the machine copy."""
    hooklib = load(os.path.join(HOOKS, "hooklib.py"), "hooklib_typed")
    typed = "---\nname: %s\ndisable-model-invocation: true\n---\n"
    repo = tree(work, "typed", {".claude/skills/create-verification-skill/SKILL.md": typed % "c",
                                ".agents/skills/create-verification-skill/SKILL.md": typed % "c"})
    line = hooklib.verify_status_line(repo)
    assert "run /create-verification-skill (typed-only; agent: read %s/.claude/skills/create-verification-skill/" \
        "SKILL.md and follow it)." % repo in line, line
    assert "/.agents/skills/create-verification-skill/SKILL.md" in hooklib.verify_status_line(repo, "codex")
    home = os.path.join(work, "home-typed")
    write(os.path.join(home, ".agents", "skills", "to-spec", "SKILL.md"), typed % "to-spec")
    write(os.path.join(home, ".claude", "skills", "grilling", "SKILL.md"), "---\nname: grilling\n---\n")
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        note = hooklib.typed_skills_note(repo, ["to-spec", "grilling", "missing"])
    finally:
        os.environ["HOME"] = old
    assert note == (" Typed-only skills (no Skill tool call): read the file, follow it, and tell the owner the typed "
                    "form: /to-spec = %s/.agents/skills/to-spec/SKILL.md." % home), note


# ---------------------------------------------------------------- mattpocock opt-in skills per project

OPTIN = ("grill-with-docs", "domain-modeling", "to-spec", "to-tickets", "tdd", "codebase-design", "code-review", "pr",
         "diagnosing-bugs", "improve-codebase-architecture", "implement", "implement-spec", "research", "handoff",
         "wayfinder", "prototype", "triage", "wizard", "to-questionnaire", "teach", "setup-matt-pocock-skills")
# The defaults (owner 2026-11-15) plus callees, without "pr" (the fake source below skips it).
DEFAULT_LINKS = ["grill-with-docs", "domain-modeling", "to-spec", "to-tickets", "tdd", "codebase-design", "code-review",
                 "diagnosing-bugs", "improve-codebase-architecture", "implement", "research", "handoff", "wayfinder",
                 "prototype"]


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
    assert "skills: grill-with-docs, domain-modeling, to-spec, to-tickets, tdd, pr, diagnosing-bugs, improve-codebase-architecture, implement, research, handoff, wayfinder, prototype" in enabled, enabled
    assert "## Wayfinding operations" in read(os.path.join(repo, "docs", "agents", "issue-tracker.md"))
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


def t_adopt_skills_none(work):
    repo, env = adopt_repo(work, "skills-none", {})
    env["AI_PLUGIN_SRC"] = fake_plugin_src(work, "none")
    res = adopt(repo, env, "--skills", "none")
    assert res.returncode == 0, res.stdout
    assert "skills: none" in read(os.path.join(repo, ".ai", "enabled")).splitlines()
    assert links(repo, ".claude/skills") == [] and links(repo, ".agents/skills") == [], "--skills none: plain grilling only"
    assert not os.path.exists(os.path.join(repo, "docs", "agents")), "no tracker docs without to-spec/to-tickets"


# ---------------------------------------------------------------- verification skills (pstack)

def t_verify_skills_copy(work):
    """ai/skills/{create,maintain}-verification-skill = the fixed transform of the vendor copy (nothing hand-edited),
    MIT notice kept, project path .agents/skills."""
    out = os.path.join(work, "pstack-out")
    vendor = os.path.join(AI_DIR, "rules", "vendor", "pstack-verification")
    commit = [ln.split(": ", 1)[1] for ln in read(os.path.join(vendor, "SOURCE.md")).splitlines()
              if ln.startswith("commit: ")][0]
    res = run([sys.executable, os.path.join(AI_DIR, "lib", "pstack_adapt.py"), vendor, out, commit])
    assert res.returncode == 0, res.stdout
    for name in ("create-verification-skill", "maintain-verification-skill"):
        mine = os.path.join(AI_DIR, "skills", name)
        for dirpath, _d, files in os.walk(os.path.join(out, name)):
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), out)
                assert read(os.path.join(out, rel)) == read(os.path.join(AI_DIR, "skills", rel)), "%s differs" % rel
        text = read(os.path.join(mine, "SKILL.md"))
        assert ".cursor/skills" not in text and "Lauren Tan" in read(os.path.join(mine, "LICENSE")), name
        assert "disable-model-invocation: true" in text and "RO:" in text and "RU:" in text, name
    assert ".agents/skills/verify-<app>/" in read(os.path.join(AI_DIR, "skills", "create-verification-skill", "SKILL.md"))


def verify_files(app="shop", features=("cart", "checkout")):
    files = {".agents/skills/verify-%s/SKILL.md" % app: "---\nname: verify-%s\n---\n" % app,
             ".agents/skills/verify-%s/features/README.md" % app: "index\n"}
    for f in features:
        files[".agents/skills/verify-%s/features/%s.md" % (app, f)] = "# %s\n" % f
    return files


def t_adopt_verify_link(work):
    repo, env = adopt_repo(work, "verify-link", verify_files())
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    link = os.path.join(repo, ".claude", "skills", "verify-shop")
    assert os.readlink(link) == os.path.join("..", "..", ".agents", "skills", "verify-shop"), os.readlink(link)
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    assert ".claude/skills/verify-shop" in files, "the verify link is committed: %s" % files
    agents = read(os.path.join(repo, "AGENTS.md"))
    assert "then verify-shop on the changed feature" in agents and "only then add e2e tests" in agents, agents
    assert "nothing to change" in adopt(repo, env).stdout


def t_verify_status_and_doctor(work):
    sys.path.insert(0, HOOKS)
    import hooklib
    doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc2")
    repo = tree(work, "verify-status", dict(verify_files(), **{".ai/enabled": "tier: mvp\n", "src/app.py": "x = 1\n"}))
    env = git_env(work, "verify-status")
    run(["git", "init", "-q", repo])
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "init"], env=env)
    line = hooklib.knowledge_index(repo)
    assert "Verify skill: verify-shop (2 features)." in line, line
    for i in range(hooklib.VERIFY_STALE_COMMITS):
        write(os.path.join(repo, "src", "app.py"), "x = %d\n" % i)
        run(["git", "-C", repo, "commit", "-qam", "c%d" % i], env=env)
    line = hooklib.knowledge_index(repo)
    assert "stale (25 code commits" in line and "/maintain-verification-skill" in line, line
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_verify_skill(repo, hooklib, "mvp")
    assert "WARN verify skill verify-shop (2 features), map stale" in out.getvalue(), out.getvalue()
    assert "WARN Claude link .claude/skills/verify-shop" in out.getvalue(), out.getvalue()
    write(os.path.join(repo, ".agents", "skills", "verify-shop", "features", "pay.md"), "# pay\n")
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-qm", "map"], env=env)
    assert "Verify skill: verify-shop (3 features)." in hooklib.knowledge_index(repo), "a map change resets it"
    bare = tree(work, "verify-none", {"src/app.py": "x = 1\n", ".ai/enabled": "tier: try\n"})
    run(["git", "init", "-q", bare])
    assert "missing, run /create-verification-skill" in hooklib.knowledge_index(bare)
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_verify_skill(bare, hooklib, "long")
    assert out.getvalue().count("WARN verify skill") == 1, "no tiers (every project is long): warn: " + out.getvalue()


# ---------------------------------------------------------------- T5: ai-doctor budget

def t_doctor_budget(work):
    doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc")
    sys.path.insert(0, HOOKS)
    import hooklib
    repo = tree(work, "doc-budget", {".ai/enabled": "tier: long\n", "Makefile": "check-fast:\n\ttrue\ncheck:\n\ttrue\n",
                                     "AGENTS.md": "# x\n\n## Done\n" + "".join("%d. item\n" % i for i in range(1, 9))
                                     + "\n## Lessons\n" + "".join("- lesson %d\n" % i for i in range(16))})
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = work          # no ~/.codex here: the Codex cap is its default (32 KiB), the rules ours
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_tier1(repo, hooklib, read(os.path.join(repo, "AGENTS.md")))
    text = out.getvalue()
    for want in ("WARN AGENTS.md Done section (8 of 6 lines)", "WARN AGENTS.md Lessons section (16 of 15 lines)",
                 "PASS project tier long; check-fast and check targets", "WARN ratchet baseline .ai/ratchet.json",
                 "PASS Codex global rules + repo AGENTS.md"):
        assert want in text, "%r not in:\n%s" % (want, text)
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_destroy_smoke()
    # dev-mac (the repo build on the Macs): no-destroy is off, the check says so; server: the router blocks.
    assert out.getvalue().startswith(("PASS no-destroy blocks", "PASS no-destroy is off on this profile")), out.getvalue()
    big = tree(work, "doc-big", {"AGENTS.md": "# x\n" + "y" * 40000})
    out = io.StringIO()
    with redirect_stdout(out):
        doctor.check_tier1(big, hooklib, read(os.path.join(big, "AGENTS.md")))
    os.environ["HOME"] = old_home or ""
    assert "FAIL Codex global rules + repo AGENTS.md" in out.getvalue() and "WARN repo AGENTS.md size" in out.getvalue(), \
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
            "GIT_COMMITTER_EMAIL": "t@t.invalid", "AI_HOME": os.path.dirname(AI_DIR),
            "AI_PROFILE": "server"}    # the Stop check runs on profile server only (dev-mac: off, owner 2026-11-15)


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
    for i in (1, 2):    # the second stop is the continuation Claude makes after the first block
        out = hook(repo, env, "Stop", stop_hook_active=(i > 1))
        assert out and out.get("decision") == "block", "try %d: %s" % (i, out)
        assert "make check-fast failed (exit 2)" in out["reason"] and "FAILED tests/test_a.py" in out["reason"], out
        assert "block %d of 2" % i in out["reason"], out["reason"]
    out = hook(repo, env, "Stop", stop_hook_active=True)
    assert out and "decision" not in out and "not blocking again" in out.get("systemMessage", ""), out
    assert hook(repo, env, "Stop", stop_hook_active=True) is None, "told once: silent after"
    assert runs(env) == 2, "the check ran %d times, want 2" % runs(env)
    write(os.path.join(repo, "src", "app.py"), "x = 3\n")       # new files: a new try count
    assert hook(repo, env, "Stop")["decision"] == "block"


def t_stop_continuation_checks_the_fix(work):
    """stop_hook_active does not skip the check: the continuation after a block is where the fix is checked."""
    repo, env = stop_repo(work, "stop-active")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    assert hook(repo, env, "Stop")["decision"] == "block"
    write(os.path.join(repo, "check.sh"), PASS_SH)                 # the agent fixes the failure
    assert hook(repo, env, "Stop", stop_hook_active=True) is None and runs(env) == 2, "the fix is checked"


def t_stop_chain_cap(work):
    """A chain of continuation stops gets at most 4 blocks even when each one changes the files."""
    repo, env = stop_repo(work, "stop-chain")
    hook(repo, env, "SessionStart")
    outs = []
    for i in range(6):
        write(os.path.join(repo, "src", "app.py"), "x = %d\n" % (i + 10))
        outs.append(hook(repo, env, "Stop", stop_hook_active=(i > 0)))
    blocks = [o for o in outs if o and o.get("decision") == "block"]
    assert len(blocks) == 4 and "not blocking again" in (outs[4] or {}).get("systemMessage", "") and outs[5] is None, outs
    write(os.path.join(repo, "src", "app.py"), "x = 99\n")        # a new user turn: a new chain
    assert hook(repo, env, "Stop")["decision"] == "block"


def t_stop_no_baseline_uses_head(work):
    repo, env = stop_repo(work, "stop-nobase")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")         # SessionStart never ran (it timed out)
    out = hook(repo, env, "Stop")
    assert out and out["decision"] == "block", "the clean HEAD is the baseline: %s" % out


def t_stop_recipe_changed(work):
    repo, env = stop_repo(work, "stop-recipe")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "Makefile"), "check-fast:\n\t@echo '1 passed'\n")
    out = hook(repo, env, "Stop")
    assert out and out["decision"] == "block" and "check-fast recipe in Makefile changed" in out["reason"], out
    assert runs(env) == 0, "a changed recipe is not trusted to run"


def t_stop_skipped_only_and_group_kill(work):
    repo, env = stop_repo(work, "stop-skipped", check_sh="echo '5 skipped in 0.02s'\n")
    hook(repo, env, "SessionStart")
    write(os.path.join(repo, "src", "app.py"), "x = 2\n")
    out = hook(repo, env, "Stop")
    assert out and "only skipped" in out["reason"], out
    late = os.path.join(env["HOME"], "late")
    slow, env2 = stop_repo(work, "stop-group", check_sh="(sleep 3; touch %s) &\nwait\n" % late)
    env2["AI_STOP_CHECK_TIMEOUT"] = "1"
    hook(slow, env2, "SessionStart")
    write(os.path.join(slow, "src", "app.py"), "x = 2\n")
    out = hook(slow, env2, "Stop")
    assert out and "ran over 1 s" in out.get("systemMessage", ""), out
    import time
    time.sleep(4)
    assert not os.path.exists(late), "the timeout killed make only, its children kept running"


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
    for name, enabled in (("stop-optout", "no-stop-check\n"), ("stop-noadopt", None)):
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


def t_ledger_removed_in_last_commit(work):
    """On the main branch (HEAD is its own merge base) the check compares with HEAD~1: a row removed and
    committed is still caught."""
    repo, env = ledger_repo(work, "ledger-main")
    write(os.path.join(repo, "docs", "REGRESSIONS.md"), "# Regressions\n## Ledger\n## Quarantine\n")
    run(["git", "-C", repo, "commit", "-qam", "drop the row"], env=env)
    res = ledger_check(repo, env)
    assert res.returncode == 1 and "R-012 was removed" in res.stdout, res.stdout


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
    write(os.path.join(env2["AI_STATE_DIR"], "sessions", "s1.json"), json.dumps({"ledger_areas": ["src/billing"]}))
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
    py = tree(work, "ratchet-hidden", {
        "tests/test_mod.py": "import pytest\npytestmark = pytest.mark.skip(reason='x')\ndef test_a():\n    pass\n",
        "tests/conftest.py": "collect_ignore = ['test_old.py']\n",
        "pytest.ini": "[pytest]\naddopts = --deselect tests/test_mod.py::test_a\n"})
    res = ratchet(py, {}, "--show", "--only", "tests,skips")
    assert json.loads(res.stdout) == {"tests": 1, "skips": 3}, "pytestmark, collect_ignore, --deselect: " + res.stdout


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
    base = json.loads(read(os.path.join(repo, ".ai", "ratchet.json")))
    write(os.path.join(repo, ".ai", "ratchet.json"), json.dumps(dict(base, tests=base["tests"] - 1)))
    out = hook(repo, env, "Stop", stop_hook_active=True)
    assert out and out["decision"] == "block" and "committed at" in out["reason"], \
        "lowering the baseline file in the same session must not pass: %s" % out


# ---------------------------------------------------------------- add-only updates (owner 2026-11-17)

OWNER_RULES = "## Rules (mandatory for this repo)\n- Never touch the billing tables by hand.\n\nDone means: the owner saw it.\n"


def adopt_full(repo, env, *extra):
    """ai-adopt with the knowledge layer on (Map), no onboarding pass (no claude)."""
    enabled = os.path.join(repo, ".ai", "enabled")
    if not os.path.exists(enabled):
        write(enabled, "no-serena\nno-graph\n")
    return run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes", "--no-onboard"] + list(extra),
               env=env, cwd=repo)


def add_inside(text, block, line):
    """The owner adds `line` as the last line inside the AI block `block`."""
    end = re.search(r"^<!-- AI:%s\b[^>]*END[^>]*-->" % block, text, re.M)
    assert end, (block, text)
    return text[:end.start()] + line + "\n" + text[end.start():]


def t_adopt_owner_text_survives_rerun(work):
    """R-006: an owner line inside a managed block (Map, Done, a tool block) and an owner section outside them
    survive a rerun, also with --refresh-map."""
    repo, env = adopt_repo(work, "owner-text", {"AGENTS.md": "# demo\n\n" + OWNER_RULES})
    res = adopt_full(repo, env)
    assert res.returncode == 0, res.stdout
    path = os.path.join(repo, "AGENTS.md")
    text = read(path)
    for block, line in (("map", "- Deploy: only from the release branch."), ("done", "7. The owner saw it on staging."),
                        ("ui", "UI owner note: dark mode first.")):
        text = add_inside(text, block, line)
    write(path, text)
    run(["git", "-C", repo, "commit", "-qam", "owner lines"], env=env)
    before = ownertext.outside(text)
    for extra in ((), ("--refresh-map",)):
        res = adopt_full(repo, env, *extra)
        assert res.returncode == 0, res.stdout
        after = read(path)
        for line in ("- Deploy: only from the release branch.", "7. The owner saw it on staging.",
                     "UI owner note: dark mode first."):
            assert line in after, (extra, line, after)
        assert ownertext.outside(after) == before, (extra, after)
        assert OWNER_RULES in after, after


def t_adopt_gitignore_makefile_owner_lines(work):
    """Owner lines inside the .gitignore and Makefile blocks survive a rerun."""
    repo, env = adopt_repo(work, "owner-lines", {})
    assert adopt(repo, env).returncode == 0
    gi, mk = os.path.join(repo, ".gitignore"), os.path.join(repo, "Makefile")
    write(gi, read(gi).replace("graphify-out/\n", "graphify-out/\n/secrets-local/\n"))
    write(mk, read(mk).replace("check-fast:\n", "check-fast:\n\t@echo owner step\n"))
    run(["git", "-C", repo, "commit", "-qam", "owner lines"], env=env)
    res = adopt(repo, env)
    assert res.returncode == 0, res.stdout
    assert "/secrets-local/" in read(gi), read(gi)
    assert "\t@echo owner step\n" in read(mk), read(mk)


def t_doctor_owner_text(work):
    """ai-doctor: WARN for a custom line inside an AI block (with file and line); FAIL when the ai-adopt commit at HEAD
    lost owner text compared with its parent; PASS for a clean adopt commit."""
    doctor = load(os.path.join(BIN, "ai-doctor"), "aidoc3")
    repo, env = adopt_repo(work, "doc-owner", {"AGENTS.md": "# demo\n\n" + OWNER_RULES})
    assert adopt(repo, env).returncode == 0

    def doctor_says(text):
        out = io.StringIO()
        with redirect_stdout(out):
            doctor.check_owner_text(repo, text)
        return out.getvalue()
    path = os.path.join(repo, "AGENTS.md")
    said = doctor_says(read(path))
    assert "PASS ai-adopt commit kept the owner text" in said and "WARN" not in said, said
    text = add_inside(read(path), "done", "- Ask Ana before a deploy.")
    n = text.splitlines().index("- Ask Ana before a deploy.") + 1
    said = doctor_says(text)
    assert "WARN AGENTS.md:%d custom line inside an AI block: move it under ## Project rules" % n in said, said
    write(path, read(path).replace("- Never touch the billing tables by hand.\n", ""))
    run(["git", "-C", repo, "commit", "-qam", "chore(ai): adopt base AI setup v4"], env=env)
    said = doctor_says(read(path))
    assert "FAIL ai-adopt commit lost owner text: AGENTS.md" in said, said


FORCE = ("import importlib.machinery, sys\n"
         "m = importlib.machinery.SourceFileLoader('ai_start', sys.argv[1]).load_module()\n"
         "m.upsert_project_rules = lambda a: a.replace('by hand', 'by script')\n"
         "sys.exit(m.main(sys.argv[2:]))\n")


def t_adopt_conflict_writes_nothing(work):
    """Fail closed: an update that would change owner text writes nothing, prints the diff and exits non-zero."""
    repo, env = adopt_repo(work, "owner-conflict", {"AGENTS.md": "# demo\n\n" + OWNER_RULES})
    write(os.path.join(repo, ".ai", "enabled"), "no-serena\nno-graph\n")
    before = {rel: read(os.path.join(repo, rel)) for rel in ("AGENTS.md", ".gitignore", "Makefile", ".ai/enabled")}
    res = run([sys.executable, "-c", FORCE, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes", "--no-onboard",
               "--no-knowledge"], env=env, cwd=repo)
    assert res.returncode != 0, res.stdout
    assert "owner text would change: nothing written" in res.stdout, res.stdout
    assert "-- Never touch the billing tables by hand." in res.stdout, res.stdout
    assert "+- Never touch the billing tables by script." in res.stdout, res.stdout
    for rel, text in before.items():
        assert read(os.path.join(repo, rel)) == text, rel


# ---------------------------------------------------------------- helpers

def detect(repo):
    res = run([sys.executable, os.path.join(BIN, "ai-check-detect"), "--dir", repo, "--json", "--no-probe"])
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


TESTS_LIST = [t_verify_skills_copy, t_adopt_verify_link, t_verify_status_and_doctor, t_adopt_project_skills, t_adopt_skills_none, t_detect_python_uv, t_detect_python_pip, t_detect_python_no_manifest, t_detect_node, t_detect_go_rust, t_detect_monorepo,
              t_detect_probe_drops_missing_tool, t_adopt_failing_check_turns_stop_off, t_adopt_leaves_tree_clean, t_adopt_commits_on_branch, t_adopt_init, t_adopt_decline_undoes_intent_to_add,
              t_adopt_branch_exists_main_clean, t_adopt_old_branch, t_adopt_unborn_main, t_typed_only_skill_paths,
              t_plan_keeps_targets, t_plan_keeps_owner_flags, t_adopt_owner_text_survives_rerun, t_adopt_gitignore_makefile_owner_lines,
              t_adopt_conflict_writes_nothing, t_doctor_owner_text, t_adopt_own_done, t_adopt_long_tier, t_adopt_ignores_global_excludes, t_adopt_monorepo_refused,
              t_doctor_budget, t_stop_no_change_no_run, t_stop_blocks_twice_then_stops, t_stop_continuation_checks_the_fix, t_stop_chain_cap, t_stop_no_baseline_uses_head,
              t_stop_recipe_changed, t_stop_skipped_only_and_group_kill,
              t_stop_success_silent_both_agents, t_stop_codex_block_and_timeout, t_stop_floor_zero_tests,
              t_stop_off_switches, t_stop_omc_coexistence, t_ledger_check_honest, t_ledger_removed_in_last_commit, t_ledger_quarantine_clock,
              t_ledger_stop_note, t_ratchet, t_ratchet_other_languages, t_stop_ratchet_long_tier]

if __name__ == "__main__":
    sys.exit(main())
