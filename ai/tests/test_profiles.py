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
    # The rendered rules in the repo follow this machine's own profile (a dry run does not render): size only.
    out = re.sub(r"(AI:core v\d+) \(\d+ bytes\)", r"\1 (N bytes)", out)
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


def seed_records(home, keys):
    """managed-keys.json entries as an earlier install recorded them (record-cmd: kind cmd, key cmd:<id>)."""
    entries = [{"kind": "cmd", "id": k, "undo": ["echo", "undo", k], "key": "cmd:" + k} for k in keys]
    write(os.path.join(home, ".local", "state", "ai", "managed-keys.json"),
          json.dumps({"version": 1, "entries": entries}))


def t_devmac_plan(work):
    """dev-mac dry run (macOS forced, fake tools): skill-scanner is the only scanner (first install unaudited, one
    info line); guarddog, osv-scanner and opencode installed earlier are undone; packages say "audit skipped";
    no box; the profile is shown and saved."""
    env, home, bindir = fake_env(work, "devmac", ("claude", "codex", "node", "npm", "uv"))
    seed_records(home, ["uv:guarddog", "bin:osv-scanner", "npm:opencode"])
    code, out = install(dict(env, AI_OS_FORCE="macos"), "--dry-run", "--yes")
    assert code == 0, out
    compare("devmac-macos-all.txt", out)
    assert "Profile: dev-mac (default for macos)." in out, out
    assert "[dry-run] write   ~/.config/ai/profile new file" in out, out
    assert "skill-scanner 2.3.2: first install, not audited (profile dev-mac audits no packages)" in out, out
    assert "uv tool install --force --no-build --managed-python -p 3.12 cisco-ai-skill-scanner==2.3.2" in out, out
    assert "audit skipped: profile dev-mac (pypi serena-agent 2.1.0)" in out, out
    assert "box MCP: not installed (profile dev-mac)" in out and "ai-box" not in out, out
    assert "last30days: not installed (profile dev-mac)" in out and "last30days-skill at" not in out, out
    for gone in ("cmd:uv:guarddog", "cmd:bin:osv-scanner", "cmd:npm:opencode"):
        assert "undo %s" % gone.split(":", 1)[1] in out or gone in out, (gone, out)
    assert "scanners not used by profile dev-mac removed: guarddog osv-scanner" in out, out
    assert "agents not used by profile dev-mac, undone: opencode" in out, out
    head = [ln for ln in out.splitlines() if ln.startswith("AI setup")][0]
    assert "Agents: claude,codex." in head, head
    assert "(newest stable, audit skipped, wheels only)" in out, out
    for word in ("guarddog 3.2.0", "osv-scanner_", "opencode-ai@", "codex mcp add box", "agent-audit npm", "agent-audit pypi"):
        assert word not in out, (word, out)


def t_profile_choice(work):
    """--profile > ~/.config/ai/profile > OS default; an unknown name stops before anything runs."""
    env, home, _ = fake_env(work, "choice", ("claude", "uv"))
    base = dict(env, AI_OS_FORCE="macos")
    write(os.path.join(home, ".config", "ai", "profile"), "server\n")
    code, out = install(base, "--user", "--dry-run", "--yes", "--agents", "claude")
    assert "Profile: server (~/.config/ai/profile)." in out, out
    code, out = install(base, "--user", "--dry-run", "--yes", "--agents", "claude", "--profile", "dev-mac")
    assert "Profile: dev-mac (--profile)." in out and "~/.config/ai/profile dev-mac" not in out, out
    assert "[dry-run] write   ~/.config/ai/profile" in out, out
    os.remove(os.path.join(home, ".config", "ai", "profile"))
    code, out = install(dict(env, AI_OS_FORCE="linux"), "--user", "--dry-run", "--yes", "--agents", "claude")
    assert "Profile: server (default for linux)." in out, out
    code, out = install(base, "--user", "--dry-run", "--yes", "--profile", "laptop")
    assert code != 0 and 'unknown profile "laptop"' in out and "[1/" not in out, out
    # bash 3.2 helper on its own
    script = ('. "%s/ai/lib/profile.sh"; AI_PROFILE_FILE=/nonexistent; ai_profile_resolve "%s/ai" macos; '
              'echo "$AI_PROFILE $AI_PROFILE_FROM $PROFILE_SCANNERS"; profile_has_scanner guarddog || echo no-guarddog'
              % (REPO, REPO))
    res = subprocess.run(["/bin/bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.stdout.decode().split("\n")[:2] == ["dev-mac default skill-scanner", "no-guarddog"], res.stdout


def t_render_profiles(work):
    """ai-render per profile: server AGENTS.md is the fixture (today's text plus the skill-scanner line); dev-mac
    drops the agent-audit bullet, the gate skip, the box line, opencode and Hermes, and the audit gate row; the
    router then lets a package install through on dev-mac (gates come only from routing rows)."""
    out = {}
    for prof in ("server", "dev-mac"):
        d = os.path.join(work, "render-" + prof)
        res = subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--profile", prof, "--out", d],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert res.returncode == 0, res.stdout
        out[prof] = (open(os.path.join(d, "AGENTS.md")).read(), json.load(open(os.path.join(d, "routing.json"))))
    srv, dev = out["server"][0], out["dev-mac"][0]
    compare("agents-server.md", srv)
    assert "skill-scanner HIGH or CRITICAL finding is never installed" in srv and "<!-- profiles" not in srv
    assert "skill-scanner HIGH or CRITICAL finding is never installed" in dev and "<!-- profiles" not in dev
    for gone in ("agent-audit npm|pypi|dir|skill", "sudo ai-gate-skip", "the box tool (MCP server box: list", "opencode", "Hermes",
                 "- last30days (Claude, on everywhere)",
                 "audit-before-install"):
        assert gone in srv and gone not in dev, gone
    assert "A blocked gate is final for you: the owner runs it himself." in dev, dev
    ids = lambda r: [x["id"] for x in r["rules"]]
    assert "audit-before-install" in ids(out["server"][1]) and "audit-before-install" not in ids(out["dev-mac"][1])
    assert all("profiles" not in x for x in out["server"][1]["rules"]), "the profiles key is not rendered"
    res = subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--profile", "laptop", "--out",
                          os.path.join(work, "render-bad")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.returncode == 1 and b"unknown profile" in res.stdout, res.stdout
    router = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks", "router.py")
    proj = os.path.join(work, "router-proj")
    os.makedirs(proj)
    payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "p", "cwd": proj, "tool_name": "Bash",
                          "tool_input": {"command": "npm install left-pad@1.3.0"}})
    for prof, denied in (("server", True), ("dev-mac", False)):
        env = {"HOME": work, "PATH": "/usr/bin:/bin", "AI_STATE_DIR": os.path.join(work, "rs-" + prof),
               "AI_ROUTING_JSON": os.path.join(work, "render-" + prof, "routing.json")}
        res = subprocess.run(["/usr/bin/python3", router, "PreToolUse"], input=payload.encode(), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        text = res.stdout.decode()
        assert ('"deny"' in text and "audit-before-install" in text) == denied, (prof, text)


def t_doctor_devmac(work):
    """ai-doctor on dev-mac: FAIL for guarddog/osv-scanner from this setup, the audit gate row, a box registration;
    PASS when they are absent (absence is never a failure)."""
    home = os.path.join(work, "doc-home")
    state = os.path.join(home, ".local", "state", "ai")
    render = {}
    for prof in ("server", "dev-mac"):
        d = os.path.join(work, "doc-render-" + prof)
        subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--profile", prof, "--out", d],
                       stdout=subprocess.DEVNULL, check=True)
        render[prof] = os.path.join(d, "routing.json")
    code = ("import importlib.machinery, importlib.util, sys; sys.dont_write_bytecode = True; "
            "l = importlib.machinery.SourceFileLoader('doctor', %r); s = importlib.util.spec_from_loader('doctor', l); "
            "m = importlib.util.module_from_spec(s); l.exec_module(m); m.check_profile()" % os.path.join(AI_DIR, "bin", "ai-doctor"))

    def doctor(routing):
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "AI_STATE_DIR": state, "AI_PROFILE": "dev-mac",
               "AI_ROUTING_JSON": routing, "CODEX_HOME": os.path.join(home, ".codex")}
        res = subprocess.run([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return res.stdout.decode()

    os.makedirs(state)
    out = doctor(render["dev-mac"])
    assert "profile dev-mac (AI_PROFILE)" in out and "FAIL" not in out, out
    seed_records(home, ["uv:guarddog", "bin:osv-scanner"])
    write(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), json.dumps({"plugins": {"ai-box@ai": []}}))
    write(os.path.join(home, ".codex", "config.toml"), "[mcp_servers.box]\ncommand = \"x\"\n")
    out = doctor(render["server"])
    fails = [ln for ln in out.splitlines() if "FAIL" in ln]
    assert len(fails) == 4, out
    for want in ("no guarddog from this setup", "no osv-scanner from this setup", "no audit-before-install gate row",
                 "box MCP server not registered"):
        assert any(want in ln for ln in fails), (want, out)
    assert "Claude plugin ai-box@ai" in out and "Codex mcp_servers.box" in out, out
    # A default plugin skill-scanner rejected (resolved.json "rejected", written by audit_ok on exit 4) and not
    # installed is a WARN, not a FAIL; other rejected items are listed as WARN too.
    write(os.path.join(state, "resolved.json"), json.dumps({"version": 1, "tools": {
        "last30days": {"rejected": {"version": "3.39.0", "sha": "f" * 40, "findings": "HIGH: x", "by": "skill-scanner"}},
        "ponytail": {"rejected": {"version": "5.3.4", "sha": "e" * 40, "findings": "CRITICAL: y", "by": "skill-scanner"}}}}))
    stub = os.path.join(work, "doc-bin")
    write(os.path.join(stub, "claude"), "#!/bin/sh\nexit 0\n", 0o755)
    code2 = code.replace("m.check_profile()", "m.check_drops_and_defaults()")
    for prof, want in (("server", "WARN"), ("dev-mac", None)):
        env = {"HOME": home, "PATH": stub + ":/usr/bin:/bin", "AI_STATE_DIR": state, "AI_PROFILE": prof,
               "CODEX_HOME": os.path.join(home, ".codex")}
        res = subprocess.run([sys.executable, "-c", code2], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = res.stdout.decode()
        assert "last30days installed and on" not in text, (prof, text)
        if want:
            assert "rejected by skill-scanner: last30days 3.39.0" in text, text
        else:       # dev-mac: last30days is not a default there, so no line about it being missing
            assert "rejected by skill-scanner: last30days" not in text, text
        assert "rejected by skill-scanner: ponytail 5.3.4" in text, text


TESTS_LIST = [t_doctor_devmac, t_render_profiles, t_server_plan_unchanged, t_devmac_plan, t_profile_choice]

if __name__ == "__main__":
    sys.exit(main())
