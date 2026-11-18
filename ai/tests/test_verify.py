#!/usr/bin/env python3
"""verify-ai-setup helper (ticket 21), driven through its CLI on a copy of this checkout with a fake claude.

The fake claude logs its argv and env, answers `auth status`, and pushes to its fixture remote when the prompt
says "push". Two session drives run in parallel: only the session that pushed reports a remote change.

Run: python3 ai/tests/test_verify.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
REPO = os.path.dirname(AI_DIR)
SKILL = os.path.join(".agents", "skills", "verify-ai-setup")
FAILS = []

FAKE_CLAUDE = r"""#!/bin/sh
if [ "$1 $2" = "auth status" ]; then echo '{"loggedIn": true}'; exit 0; fi
log="%s/claude-$$"
case "$2" in
  *push*) git commit -q --allow-empty -m pushed && git push -q origin HEAD:refs/heads/side ;;
  *) sleep 3 ;;
esac
python3 -c 'import json, sys; json.dump({"argv": sys.argv[2:]}, open(sys.argv[1], "w"))' \
    "$log.$(basename "$PWD")" "$@"
echo '{"type":"system","subtype":"init","plugins":[]}'
echo '{"type":"result","result":"ok"}'
"""
FAKE_CODEX = '#!/bin/sh\n[ "$1 $2" = "login status" ] && echo "Logged in using ChatGPT"\nexit 0\n'


def main():
    work = tempfile.mkdtemp(prefix="ai-verify-tests-")
    try:
        for test in (t_parallel_sessions,):
            try:
                test(os.path.join(work, test.__name__))
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d verify tests failed" % len(FAILS))
    return 1 if FAILS else 0


def t_parallel_sessions(work):
    """Ticket 21: a session pushes while a parallel session in another fixture waits. Only the pusher reports
    `remote heads changed: yes`. Every Claude session may run gh (the fake gh), gets this checkout's env.list
    (OMC_CONTEXT_GUARD_THRESHOLD=94) in its settings env, and takes --max-turns, an extra --plugin-dir and an
    extra --allow rule."""
    root, env, logs = checkout_copy(work)
    helper = os.path.join(root, SKILL, "verify")
    run(env, root, helper, "launch", "--label", "t", "empty", "docs-only")
    out = run(env, root, helper, "doctor")
    assert "doctor: PASS" in out, out

    extra = os.path.join(work, "stand-in-plugin")
    wait = subprocess.Popen([helper, "drive", "session", "claude", "--fixture", "docs-only", "wait here"],
                            env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    push = run(env, root, helper, "drive", "session", "claude", "--fixture", "empty", "--max-turns", "120",
               "--plugin-dir", extra, "--allow", "Bash", "push now")
    waited = wait.communicate(timeout=120)[0]
    assert "remote heads changed: yes" in push, push
    assert "remote heads changed: no" in waited, "the waiting session judged the other session's push:\n" + waited
    assert "01-session" in waited + push and "02-session" in waited + push, (waited, push)

    argv = {}
    for name in os.listdir(logs):
        argv[name.rsplit(".", 1)[1]] = json.load(open(os.path.join(logs, name)))["argv"]
    for kind, args in argv.items():
        tools = args[args.index("--allowedTools") + 1:]
        assert "Bash(gh *)" in tools, (kind, args)
        settings = json.loads(args[args.index("--settings") + 1])
        assert settings["enabledPlugins"] == {"ai-core@ai": False}, settings
        assert settings["env"]["OMC_CONTEXT_GUARD_THRESHOLD"] == "94", settings
        assert settings["env"]["OMC_SKIP_HOOKS"] == "keyword-detector", settings
    assert argv["empty"][argv["empty"].index("--max-turns") + 1] == "120", argv["empty"]
    assert extra in argv["empty"] and extra not in argv["docs-only"], argv
    assert "Bash" in argv["empty"] and "Bash" not in argv["docs-only"], argv
    run(env, root, helper, "cleanup")


def checkout_copy(work):
    """A git repo with this checkout's ai/ and the verify skill; fake claude and codex first on PATH."""
    root = os.path.join(work, "checkout")
    shutil.copytree(AI_DIR, os.path.join(root, "ai"), ignore=shutil.ignore_patterns("build", "__pycache__", "tests"))
    shutil.copytree(os.path.join(REPO, SKILL), os.path.join(root, SKILL))
    with open(os.path.join(root, ".gitignore"), "w") as fh:
        fh.write(".verify/\nai/AGENTS.md\n")
    logs = os.path.join(work, "logs")
    bindir = os.path.join(work, "bin")
    os.makedirs(logs)
    os.makedirs(bindir)
    for name, text in (("claude", FAKE_CLAUDE % logs), ("codex", FAKE_CODEX)):
        with open(os.path.join(bindir, name), "w") as fh:
            fh.write(text)
        os.chmod(os.path.join(bindir, name), 0o755)
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    env.pop("AI_HOME", None)
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "copy"]):
        subprocess.check_call(["git", "-C", root] + args, env=env, stdout=subprocess.DEVNULL)
    return root, env, logs


def run(env, cwd, *cmd):
    res = subprocess.run(list(cmd), env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         timeout=300)
    assert res.returncode == 0, "%s: rc %s\n%s" % (" ".join(cmd), res.returncode, res.stdout)
    return res.stdout


if __name__ == "__main__":
    sys.exit(main())
