#!/usr/bin/env python3
"""Tests for ai/bin/ai-info: a throwaway HOME, fake agent binaries, no network.

Run: python3 ai/tests/test_info.py   (bash ai/tests/run.sh runs it too)
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
INFO = os.path.join(AI_DIR, "bin", "ai-info")
FAILS = []
SECRET = "ctx7sk-" + "q1w2e3r4-" * 4 + "notforprint"


def main():
    work = tempfile.mkdtemp(prefix="ai-info-tests-")
    try:
        home, fake, repo = setup(work)
        for test in (t_full, t_short, t_project_state, t_outside_repo, t_no_secrets_fast):
            try:
                test(home, fake, repo)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d ai-info tests failed" % len(FAILS))
    return 1 if FAILS else 0


def t_full(home, fake, repo):
    out = run(home, fake, repo).stdout
    for want in ("claude    2.1.5", "codex     0.120.0", "hermes    not installed",
                 "ai-core       on", "claude-seo    off / on here", "ai-serena     not installed",
                 "mattpocock: grilling, grill-me, wait-what, retro, writing-for-agents (missing)",
                 "context7 (global", "box (global, server boxes", "Gates: audit-before-install, secret-scan, no-sudo, pr-rules",
                 "sudo ai-gate-skip", "ai-adopt --tools serena", "ai-adopt --tools browser", "docs/SECURITY.md"):
        assert want in out, "%r not in output:\n%s" % (want, out)


def t_short(home, fake, repo):
    out = run(home, fake, repo, "--short").stdout
    lines = out.strip().splitlines()
    assert 6 <= len(lines) <= 10, "short output must be about 8 lines, got %d:\n%s" % (len(lines), out)
    assert lines[0].startswith("AI agents: claude 2.1.5, codex 0.120.0"), lines[0]
    assert "per project: claude-seo" in out and "ai-adopt --tools serena|graph" in out, out
    assert "More: ai-info" in out, out


def t_project_state(home, fake, repo):
    out = run(home, fake, repo).stdout
    assert "This project (proj): Map present (2 lines), Libraries not needed (no dependencies), enabled: seo" in out, out
    with open(os.path.join(repo, "pyproject.toml"), "w") as fh:
        fh.write('[project]\nname = "p"\nversion = "0"\ndependencies = ["httpx"]\n')
    out = run(home, fake, repo).stdout
    assert "Libraries missing (ai-libs --sync)" in out, out
    os.remove(os.path.join(repo, "pyproject.toml"))


def t_outside_repo(home, fake, repo):
    out = run(home, fake, home).stdout
    assert "Not inside a git repo" in out, out


def t_no_secrets_fast(home, fake, repo):
    start = time.time()
    res = run(home, fake, repo, extra_env={"CONTEXT7_API_KEY": SECRET})
    took = time.time() - start
    assert res.returncode == 0, res.stdout
    assert SECRET not in res.stdout and "notforprint" not in res.stdout, "a secret was printed"
    assert took < 5, "ai-info took %.1f s" % took


# ---------------------------------------------------------------- helpers

def setup(work):
    home = os.path.join(work, "home")
    fake = os.path.join(work, "bin")
    repo = os.path.join(work, "proj")
    for d in (home, fake, repo):
        os.makedirs(d)
    for name, ver in (("claude", "2.1.5 (Claude Code)"), ("codex", "codex-cli 0.120.0")):
        write(os.path.join(fake, name), "#!/bin/sh\necho '%s'\n" % ver, 0o755)
    write(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), json.dumps({"version": 2, "plugins": {
        "ai-core@ai": [{"scope": "user"}], "claude-seo@agricidaniel-claude-seo": [{"scope": "user"}]}}))
    write(os.path.join(home, ".claude", "settings.json"),
          json.dumps({"enabledPlugins": {"claude-seo@agricidaniel-claude-seo": False}}))
    write(os.path.join(home, ".config", "ai", "secrets.env"), "CONTEXT7_API_KEY=%s\n" % SECRET)
    for skill in ("grilling", "grill-me", "wait-what", "retro", "prompting-claude-and-codex"):
        write(os.path.join(home, ".agents", "skills", skill, "SKILL.md"), "---\nname: %s\n---\n" % skill)
    subprocess.run(["git", "init", "-q", repo], check=True)
    write(os.path.join(repo, "AGENTS.md"), "# proj\n\n<!-- AI:map START (ai-adopt) -->\n## Map\n- What: proj.\n"
          "- Run: x.\n<!-- AI:map END -->\n")
    write(os.path.join(repo, ".ai", "enabled"), "seo\n")
    write(os.path.join(repo, ".ai", "base-version"), "4\n")
    write(os.path.join(repo, ".claude", "settings.json"),
          json.dumps({"enabledPlugins": {"claude-seo@agricidaniel-claude-seo": True}}))
    return home, fake, repo


def run(home, fake, cwd, *args, extra_env=None):
    env = {"HOME": home, "PATH": fake + os.pathsep + "/usr/bin:/bin", "LANG": "C.UTF-8"}
    env.update(extra_env or {})
    res = subprocess.run([sys.executable, INFO] + list(args), cwd=cwd, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=30)
    res.stdout = res.stdout.decode("utf-8", "replace")
    return res


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)


if __name__ == "__main__":
    sys.exit(main())
