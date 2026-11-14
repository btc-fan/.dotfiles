#!/usr/bin/env python3
"""Profiles (owner decision 2026-11-14): server and dev-mac. Throwaway HOME, no network, no real home.

install.sh dry runs with a forced OS (AI_OS_FORCE), a fixed PATH (fake tools + a fixed list of system commands)
and a fixed resolved.json, compared with fixtures: the server plan must stay what it was.

Run: python3 ai/tests/test_profiles.py            (python3 ai/tests/test_profiles.py --regen rewrites the fixtures)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
REPO = os.path.dirname(AI_DIR)
FIX = os.path.join(TESTS, "fixtures", "profiles")
FAILS = []
REGEN = "--regen" in sys.argv

# System commands the installer may call; everything else is absent, so the plan is the same on every machine.
SYSTEM = ("bash sh env python3 jq git sed awk grep egrep cut tr sort head tail find ls cat dirname basename uname id "
          "mktemp date wc tee paste cksum readlink realpath mkdir rm ln chmod cp mv touch printf test expr xargs "
          "sleep diff cmp stat true false uniq comm od shasum sha256sum hostname whoami getconf locale").split()


def main():
    # A fixed-length work path: long paths are cut in the printed plan, the cut must not move.
    work = tempfile.mkdtemp(prefix="aiprof", dir="/tmp" if os.path.isdir("/tmp") else None)
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
    print("%d profile tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- helpers

def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)


def stub(bindir, name, body="#!/bin/sh\nexit 0\n"):
    write(os.path.join(bindir, name), body, 0o755)


def fake_env(work, name, tools=()):
    """A throwaway HOME with the fixed resolved.json, and a PATH of fakes + the fixed system commands."""
    root = os.path.join(work, name)
    home = os.path.join(root, "home")
    bindir = os.path.join(root, "bin")
    os.makedirs(os.path.join(home, ".local", "state", "ai"))
    os.makedirs(bindir)
    shutil.copy(os.path.join(FIX, "resolved.json"), os.path.join(home, ".local", "state", "ai", "resolved.json"))
    sysbin = os.path.join(root, "sysbin")
    os.makedirs(sysbin)
    for cmd in SYSTEM:
        path = shutil.which(cmd, path="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin")
        if path:
            os.symlink(path, os.path.join(sysbin, cmd))
    for t in tools:
        stub(bindir, t, "#!/bin/sh\n[ \"$1\" = --version ] && echo '%s 1.0.0'\nexit 0\n" % t)
    env = {"PATH": bindir + ":" + sysbin, "HOME": home, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "AI_RESOLVE_OFFLINE": "1", "AI_PROJ_AGENT_PATH": "/nonexistent/proj-agent",
           "AI_PROJ_AGENT_SOCK": "/nonexistent/proj-agent.sock", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "TMPDIR": os.path.join(root, "tmp")}
    os.makedirs(env["TMPDIR"])
    return env, home, bindir


def install(env, *args):
    res = subprocess.run(["bash", os.path.join(REPO, "install.sh")] + list(args), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env, timeout=300)
    out = res.stdout.decode("utf-8", "replace")
    out = out.replace(env["TMPDIR"], "$TMP").replace(env["HOME"], "~").replace(REPO, "$REPO")
    out = re.sub(r"/tmp/aiprof\w{8}", "$WORK", out)
    out = re.sub(r"\b20\d{6}-\d{6}\b", "YYYYMMDD-HHMMSS", out)
    out = re.sub(r"(\$TMP/[\w-]+\.)\w{6}\b", r"\1XXXXXX", out)
    return res.returncode, out


def compare(name, out):
    path = os.path.join(FIX, name)
    if REGEN or not os.path.exists(path):
        write(path, out)
        return
    want = open(path).read()
    if want != out:
        import difflib
        diff = "".join(list(difflib.unified_diff(want.splitlines(True), out.splitlines(True), "fixture", "now"))[:80])
        raise AssertionError("%s differs from the fixture:\n%s" % (name, diff))


# ---------------------------------------------------------------- tests

def t_server_plan_unchanged(work):
    """The server plan (Linux, user part and one-process run) is what it was before profiles existed."""
    tools = ("claude", "codex", "node", "npm", "uv", "guarddog", "skill-scanner", "osv-scanner")
    env, home, _ = fake_env(work, "srv-user", tools)
    code, out = install(dict(env, AI_OS_FORCE="linux"), "--user", "--dry-run", "--yes", "--agents", "claude,codex")
    assert code == 0, out
    compare("server-linux-user.txt", out)
    env, home, _ = fake_env(work, "srv-all", tools)
    code, out = install(dict(env, AI_OS_FORCE="linux"), "--dry-run", "--yes", "--agents", "claude,codex")
    assert code == 0, out
    compare("server-linux-all.txt", out)


TESTS_LIST = [t_server_plan_unchanged]

if __name__ == "__main__":
    sys.exit(main())
