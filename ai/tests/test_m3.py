#!/usr/bin/env python3
"""Tests for the owner decisions of 2026-11-14 (M3): caveman and byterover dropped (plugin, hooks, MCP in Claude
and Codex; saved and restored by undo), the off-by-default plugin list and ai-adopt --tools ui, the Serena take
over, RTK from the Homebrew formula (one rtk on PATH), OMX hooks moved off a versioned Cellar node, last30days on
by default with its contract and evals, and the matching ai-doctor checks.
Fake claude, codex and brew on a closed PATH, a temp HOME. Nothing is written outside the temp dir.

Run: python3 ai/tests/test_m3.py   (bash ai/tests/run.sh runs it too)
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
REPO = os.path.dirname(AI_DIR)
sys.dont_write_bytecode = True
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.join(AI_DIR, "lib"))
import aiconf  # noqa: E402
import test_resolve as tr  # noqa: E402

FAILS = []
SYS_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
STATE = os.path.join(".local", "state", "ai")
ENV_KEYS = tr.ENV_KEYS + ("HOME", "PATH", "CLAUDE_CONFIG_DIR", "CODEX_HOME")


def main():
    work = tempfile.mkdtemp(prefix="ai-m3-tests-")
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        for test in (t_drop_claude, t_drop_keeps_shared_marketplace, t_drop_codex_and_serena, t_off_plugins,
                     t_serena_take, t_rtk_brew, t_rtk_no_brew, t_omx_node_fix, t_last30days, t_doctor,
                     t_omc_companion, t_drop_failures, t_rtk_brew_mismatch, t_codex_restore_quoted,
                     t_yaml_top_set_block_list, t_skill_dups, t_omx_nvm_fix):
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            for k in tr.ENV_KEYS:
                os.environ.pop(k, None)
            try:
                d = os.path.join(work, test.__name__)
                os.makedirs(d)
                test(d)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
            except Exception as exc:        # a crash in one test must not stop the others
                FAILS.append("%s: %s: %s" % (test.__name__, type(exc).__name__, exc))
                print("FAIL %s: crashed: %s: %s" % (test.__name__, type(exc).__name__, exc))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(work, ignore_errors=True)
    print("%d m3 tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- helpers

write, read, stub, bash, upstream = tr.write, tr.read, tr.stub, tr.bash, tr.upstream
LIBS = tr.LIBS


def env_for(work, pins="", extra_path=""):
    """A closed PATH (fakes, then the system folders only: no real brew, rtk, serena or codex), a temp HOME."""
    env, home, bindir = tr.bash_env(work, pins)
    env["PATH"] = ":".join(p for p in (bindir, extra_path, SYS_PATH) if p)
    env["FAKE_LOG"] = os.path.join(work, "log")
    env["FAKE_REPOS"] = os.path.join(work, "up")
    return env, home, bindir


def claude_env(work, pins=""):
    env, home, bindir = env_for(work, pins)
    stub(os.path.join(bindir, "claude"), tr.FAKE_CLAUDE)
    return env, home, bindir


def jload(path):
    with open(path) as fh:
        return json.load(fh)


def entries(home):
    p = os.path.join(home, STATE, "managed-keys.json")
    return jload(p)["entries"] if os.path.exists(p) else []


def undo(home, only=""):
    args = [sys.executable, os.path.join(AI_DIR, "lib", "aiconf.py"), "--state",
            os.path.join(home, STATE, "managed-keys.json"), "undo"] + (["--only", only] if only else [])
    return args


def run_undo(env, home, only=""):
    res = subprocess.run(undo(home, only), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    return res.returncode, res.stdout.decode()


def set_settings(home, **keys):
    path = os.path.join(home, ".claude", "settings.json")
    data = jload(path) if os.path.exists(path) else {}
    data.update(keys)
    write(path, json.dumps(data))


def installed_plugins(home, names):
    write(os.path.join(home, ".claude", "plugins", "installed_plugins.json"),
          json.dumps({"version": 2, "plugins": {n: [{"scope": "user", "version": "1.0.0"}] for n in names}}))


FAKE_CODEX = r'''#!/usr/bin/env python3
# Fake `codex mcp get|add|remove|list` on $CODEX_HOME/config.toml (tables [mcp_servers.<name>] and sub-tables).
import json, os, re, sys
cfg = os.path.join(os.environ["CODEX_HOME"], "config.toml")
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write("codex " + " ".join(a) + "\n")
text = open(cfg).read() if os.path.exists(cfg) else ""
def tables(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if m:
            cur = m.group(1).strip()
        out.setdefault(cur, []).append(line)
    return out
def server(name):
    return [t for t in tables(text) if t and (t == "mcp_servers." + name or t.startswith("mcp_servers." + name + "."))]
if a[:2] == ["mcp", "get"]:
    found = server(a[2])
    if not found:
        sys.exit(1)
    print(json.dumps({"name": a[2], "raw": "\n".join("\n".join(tables(text)[t]) for t in found)}))
elif a[:2] == ["mcp", "remove"]:
    if os.environ.get("FAKE_CODEX_REMOVE_FAIL"):
        sys.exit(1)
    drop = set(server(a[2]))
    if not drop:
        sys.exit(1)
    keep = [l for t, ls in tables(text).items() if t not in drop for l in ls]
    open(cfg, "w").write("\n".join(keep).rstrip("\n") + "\n")
elif a[:2] == ["mcp", "add"]:
    name, rest = a[2], a[3:]
    body = ["", "[mcp_servers.%s]" % name]
    if rest[:1] == ["--url"]:
        body.append('url = "%s"' % rest[1])
    else:
        env = []
        while rest and rest[0] == "--env":
            env.append(rest[1].split("=", 1)); rest = rest[2:]
        rest = rest[1:] if rest[:1] == ["--"] else rest
        body.append('command = "%s"' % rest[0])
        body.append("args = %s" % json.dumps(rest[1:]))
        if env:
            body += ["", "[mcp_servers.%s.env]" % name] + ['%s = "%s"' % (k, v) for k, v in env]
    open(cfg, "w").write(text.rstrip("\n") + "\n" + "\n".join(body) + "\n")
elif a[:2] == ["mcp", "list"]:
    print("\n".join(sorted({t.split(".")[1] for t in tables(text) if t and t.startswith("mcp_servers.")})))
elif a[:2] == ["plugin", "list"]:
    pass
'''

FAKE_BREW = r'''#!/bin/sh
# Fake brew: --prefix prints $FAKE_BREW_PREFIX; `info --json=v2 rtk` reports $FAKE_BREW_TAP and
# $FAKE_BREW_STABLE; `upgrade rtk` installs $FAKE_BREW_RTK_NEW in the Cellar and links it.
echo "brew $* (HOMEBREW_NO_AUTO_UPDATE=${HOMEBREW_NO_AUTO_UPDATE:-})" >> "$FAKE_LOG"
case "$1" in
    --prefix) echo "$FAKE_BREW_PREFIX" ;;
    info) printf '{"formulae": [{"name": "rtk", "tap": "%s", "versions": {"stable": "%s"}}]}\n' \
        "${FAKE_BREW_TAP:-homebrew/core}" "${FAKE_BREW_STABLE:-$FAKE_BREW_RTK_NEW}" ;;
    upgrade)
        [ "$2" = rtk ] || exit 1
        mkdir -p "$FAKE_BREW_PREFIX/Cellar/rtk/$FAKE_BREW_RTK_NEW/bin"
        printf '#!/bin/sh\necho "rtk %s"\n' "$FAKE_BREW_RTK_NEW" > "$FAKE_BREW_PREFIX/Cellar/rtk/$FAKE_BREW_RTK_NEW/bin/rtk"
        chmod 755 "$FAKE_BREW_PREFIX/Cellar/rtk/$FAKE_BREW_RTK_NEW/bin/rtk"
        ln -sf "../Cellar/rtk/$FAKE_BREW_RTK_NEW/bin/rtk" "$FAKE_BREW_PREFIX/bin/rtk" ;;
    *) exit 0 ;;
esac
'''


def caveman_setup(work):
    """Fake claude with caveman@caveman installed from its own marketplace; settings.json with the two caveman hooks
    and a hook of another tool; ~/.claude.json with the dropped MCP servers and context7."""
    upstream(os.path.join(work, "up", "JuliusBrussee", "caveman"), "caveman", "caveman", ["1.0.0"])
    env, home, bindir = claude_env(work)
    code, out = bash("claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman "
                     "--scope user", env)
    assert code == 0, out
    node = "/opt/homebrew/Cellar/node/24.3.0/bin/node"
    hooks = {"SessionStart": [
        {"hooks": [{"type": "command", "command": '"%s" "%s/.claude/hooks/caveman-activate.js"' % (node, home)}]},
        {"matcher": "^(startup|resume)$", "hooks": [{"type": "command", "command": "sh '/x/herdr-app/session-note.sh'"}]}],
        "UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": '"%s" "%s/.claude/hooks/caveman-mode-tracker.js"' % (node, home)}]}]}
    set_settings(home, hooks=hooks)
    write(os.path.join(home, ".claude", "hooks", "caveman-activate.js"), "// vendor file\n")
    write(os.path.join(home, ".claude", ".claude.json"), json.dumps({"mcpServers": {
        "byterover-mcp": {"type": "http", "url": "https://mcp.byterover.dev"},
        "caveman-shrink": {"type": "stdio", "command": "npx", "args": ["-y", "caveman-shrink"]},
        "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}}))
    os.remove(os.path.join(work, "log"))
    return env, home


def snapshot(home):
    out = {}
    for rel in (".claude/settings.json", ".claude/.claude.json", ".claude/plugins/installed_plugins.json",
                ".claude/plugins/known_marketplaces.json"):
        out[rel] = read(os.path.join(home, rel))
    return out


# ---------------------------------------------------------------- tests

def t_drop_claude(work):
    """Item 1+2: caveman plugin (+ its marketplace), the two caveman hooks, and the caveman-shrink and byterover-mcp
    user MCP servers are removed; each saved in the undo folder and recorded; the vendor hook files stay and are
    reported; a dry run changes nothing; a second run changes nothing; undo restores all of it."""
    env, home = caveman_setup(work)
    tr.set_enabled(home, "caveman@caveman", False)
    script = LIBS + "claude_mcp; claude_drop_plugins; claude_drop_hooks"
    before = snapshot(home)
    code, out = bash(LIBS + "AI_DRY_RUN=1; claude_mcp; claude_drop_plugins; claude_drop_hooks", env)
    assert code == 0, out
    assert snapshot(home) == before and tr.mutations(work) == [], "dry run changed something: " + out
    assert "[dry-run] claude plugin uninstall caveman@caveman --keep-data" in out, out
    assert "[dry-run] claude plugin marketplace remove caveman" in out and "caveman-mode-tracker.js" in out, out
    code, out = bash(script, env)
    assert code == 0, out
    known, plugins = tr.claude_files(home)
    assert "caveman@caveman" not in plugins and "caveman" not in known, (known, plugins)
    st = jload(os.path.join(home, ".claude", "settings.json"))
    cmds = [h["command"] for gs in st["hooks"].values() for g in gs for h in g["hooks"]]
    assert cmds == ["sh '/x/herdr-app/session-note.sh'"], cmds
    assert set(jload(os.path.join(home, ".claude", ".claude.json"))["mcpServers"]) == {"context7"}
    assert os.path.exists(os.path.join(home, ".claude", "hooks", "caveman-activate.js")), "vendor files stay"
    assert "hook scripts left on disk" in out and "caveman-activate.js" in out, out
    blobs = sorted(os.listdir(os.path.join(home, STATE, "undo")))
    assert any("claude-user-mcp-byterover-mcp" in b for b in blobs) and any("caveman-shrink" in b for b in blobs), blobs
    assert sum(b.split(".", 1)[1].startswith("hook-") for b in blobs) == 2, blobs
    for b in blobs:
        assert os.stat(os.path.join(home, STATE, "undo", b)).st_mode & 0o077 == 0, "undo files are 0600"
    keys = [e["key"] for e in entries(home)]
    assert "cmd:claude-plugin-restore:caveman@caveman" in keys and "restore:claude-user-mcp:byterover-mcp" in keys, keys
    assert sum(k.startswith("hook:") for k in keys) == 2, keys
    os.remove(os.path.join(work, "log"))
    code, out = bash(script, env)
    assert code == 0 and tr.mutations(work) == [], (tr.mutations(work), out)
    code, out = run_undo(env, home)
    assert code == 0, out
    known, plugins = tr.claude_files(home)
    assert "caveman@caveman" in plugins and known["caveman"]["source"]["repo"] == "JuliusBrussee/caveman", (known, out)
    assert tr.enabled(home)["caveman@caveman"] is False, "the old enabledPlugins value comes back"
    st = jload(os.path.join(home, ".claude", "settings.json"))
    cmds = " ".join(h["command"] for gs in st["hooks"].values() for g in gs for h in g["hooks"])
    assert "caveman-activate.js" in cmds and "caveman-mode-tracker.js" in cmds and "herdr" in cmds, cmds
    assert set(jload(os.path.join(home, ".claude", ".claude.json"))["mcpServers"]) == \
        {"context7", "byterover-mcp", "caveman-shrink"}


def t_drop_keeps_shared_marketplace(work):
    """A dropped plugin whose marketplace another installed plugin uses: the marketplace stays."""
    env, home = caveman_setup(work)
    code, out = bash("claude plugin install other@caveman --scope user", env)
    assert code == 0, out
    code, out = bash(LIBS + "claude_drop_plugins", env)
    assert code == 0, out
    known, plugins = tr.claude_files(home)
    assert "caveman" in known and "other@caveman" in plugins and "caveman@caveman" not in plugins, (known, plugins)
    assert "marketplace remove" not in " ".join(tr.mutations(work)), tr.mutations(work)


def t_drop_codex_and_serena(work):
    """Item 2 (Codex) and item 4 (Codex side): codex_mcp removes byterover-mcp and caveman-shrink (TOML saved,
    restore recorded, undo puts the text back) and replaces a foreign serena entry by ours (saved, one serena)."""
    env, home, bindir = env_for(work)
    stub(os.path.join(bindir, "codex"), FAKE_CODEX)
    stub(os.path.join(bindir, "serena"), "#!/bin/sh\necho serena 1.0.0\n")
    cfg = os.path.join(home, ".codex", "config.toml")
    orig = ('model = "x"\n\n[mcp_servers.byterover-mcp]\nurl = "https://mcp.byterover.dev"\n\n'
            '[mcp_servers.caveman-shrink]\ncommand = "npx"\nargs = ["-y", "caveman-shrink"]\n\n'
            '[mcp_servers.serena]\ncommand = "uvx"\nargs = ["--from", "git+https://github.com/oraios/serena", "serena"]\n')
    write(cfg, orig)
    code, out = bash(LIBS + "codex_mcp", env)
    assert code == 0, out
    text = read(cfg)
    assert "byterover" not in text and "caveman-shrink" not in text, text
    assert text.count("[mcp_servers.serena]") == 1 and 'command = "serena"' in text and "uvx" not in text, text
    assert "--context=codex" in text, text
    keys = [e["key"] for e in entries(home)]
    for k in ("restore:codex-mcp:byterover-mcp", "restore:codex-mcp:caveman-shrink", "restore:codex-mcp:serena"):
        assert k in keys, keys
    blob = [e for e in entries(home) if e["key"] == "restore:codex-mcp:byterover-mcp"][0]["blob"]
    assert "mcp.byterover.dev" in read(blob), read(blob)
    code, out = run_undo(env, home, only="^restore:codex-mcp:(byterover-mcp|caveman-shrink)$")
    assert code == 0, out
    text = read(cfg)
    assert "[mcp_servers.byterover-mcp]" in text and "[mcp_servers.caveman-shrink]" in text, text


def t_off_plugins(work):
    """Item 3: installed plugins on AI_OFF_CLAUDE_PLUGINS get enabledPlugins false (recorded; undo puts true back);
    a listed plugin that is not installed gets no key; ai-adopt --tools ui turns ui-ux-pro-max on per project."""
    env, home, bindir = claude_env(work)
    installed_plugins(home, ["ui-ux-pro-max@ui-ux-pro-max-skill", "typesafe@typesafe-ai", "oh-my-claudecode@omc"])
    set_settings(home, enabledPlugins={"ui-ux-pro-max@ui-ux-pro-max-skill": True, "typesafe@typesafe-ai": True,
                                       "oh-my-claudecode@omc": True})
    code, out = bash(LIBS + "claude_plugins_off", env)
    assert code == 0, out
    en = tr.enabled(home)
    assert en["ui-ux-pro-max@ui-ux-pro-max-skill"] is False and en["typesafe@typesafe-ai"] is False, en
    assert en["oh-my-claudecode@omc"] is True and "claude-seo@agricidaniel-claude-seo" not in en, en
    assert "off at user scope: ui-ux-pro-max typesafe" in out, out
    code, out = run_undo(env, home)
    assert tr.enabled(home)["typesafe@typesafe-ai"] is True, out
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("ai_start_m3", os.path.join(AI_DIR, "bin", "ai-start"))
    spec = importlib.util.spec_from_loader("ai_start_m3", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    root = os.path.join(work, "proj")
    os.makedirs(root)
    path, text = mod.claude_plugins_plan(root, ["ui"])
    assert path.endswith(os.path.join(".claude", "settings.json"))
    assert json.loads(text)["enabledPlugins"] == {"ui-ux-pro-max@ui-ux-pro-max-skill": True}, text
    routing = read(os.path.join(AI_DIR, "routing.yaml"))
    assert "- id: ui\n    scope: opt-in" in routing, "ui is an opt-in routing id"


def t_skill_dups(work):
    """QA 2026-11-15 item 5: one copy of each skill name per Claude session. A skill the ai-core plugin ships is not
    linked into ~/.claude/skills (an old link goes; Codex keeps its link); a vendor plugin's copy of one of our
    names gets skillOverrides off; a project that links tdd turns the vendor tdd off in its settings; the
    marketplace mattpocock plugin is on the drop list."""
    env, home, bindir = claude_env(work)
    cdir = os.path.join(home, ".claude")
    omc = os.path.join(work, "omc-cache")
    for n in ("create-verification-skill", "tdd", "autopilot"):
        write(os.path.join(omc, "skills", n, "SKILL.md"), "---\nname: %s\n---\n" % n)
    core = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core")
    write(os.path.join(cdir, "plugins", "installed_plugins.json"), json.dumps({"version": 2, "plugins": {
        "oh-my-claudecode@omc": [{"scope": "user", "installPath": omc}],
        "ai-core@ai": [{"scope": "user", "installPath": core}]}}))
    set_settings(home, enabledPlugins={"oh-my-claudecode@omc": True, "ai-core@ai": True})
    own = os.path.join(AI_DIR, "skills", "prompting-claude-and-codex")
    os.makedirs(os.path.join(cdir, "skills"))
    os.symlink(own, os.path.join(cdir, "skills", "prompting-claude-and-codex"))
    assert sorted(aiconf.claude_skill_dups(cdir)) == ["prompting-claude-and-codex"], aiconf.claude_skill_dups(cdir)
    code, out = bash(LIBS + 'claude_skills; link_skills "$HOME/.agents/skills" "$(PLUGIN_DIR)/skills"; '
                     'link_skills "$HOME/.agents/skills"', env)
    assert code == 0, out
    assert not os.path.lexists(os.path.join(cdir, "skills", "prompting-claude-and-codex")), out
    assert os.path.islink(os.path.join(cdir, "skills", "create-verification-skill")), out
    assert os.readlink(os.path.join(home, ".agents", "skills", "prompting-claude-and-codex")) == own, "Codex link"
    offs = jload(os.path.join(cdir, "settings.json")).get("skillOverrides")
    assert offs == {"oh-my-claudecode:create-verification-skill": "off"}, offs
    assert aiconf.claude_skill_dups(cdir) == {}, aiconf.claude_skill_dups(cdir)
    os.environ["CLAUDE_CONFIG_DIR"] = cdir
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("ai_start_dups", os.path.join(AI_DIR, "bin", "ai-start"))
    spec = importlib.util.spec_from_loader("ai_start_dups", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    root = os.path.join(work, "proj")
    os.makedirs(root)
    path, text = mod.claude_plugins_plan(root, [], ["tdd", "to-spec"])
    assert json.loads(text) == {"skillOverrides": {"oh-my-claudecode:tdd": "off"}}, text
    write(path, text)
    assert mod.claude_plugins_plan(root, [], ["tdd"]) is None, "a rerun changes nothing"
    pins = read(os.path.join(AI_DIR, "pins.env"))
    assert "mattpocock-skills@claude-plugins-official" in [ln for ln in pins.splitlines()
                                                           if ln.startswith("AI_DROP_CLAUDE_PLUGINS=")][0], pins


def t_serena_take(work):
    """Item 4: with ai-serena@ai installed and enabled, a user-scope serena in ~/.claude.json is moved out (saved,
    restore recorded); not enabled: left alone."""
    env, home, bindir = claude_env(work)
    installed_plugins(home, ["ai-serena@ai"])
    cj = os.path.join(home, ".claude", ".claude.json")
    write(cj, json.dumps({"mcpServers": {"serena": {"command": "uvx", "args": ["serena"]}, "context7": {"url": "u"}}}))
    set_settings(home, enabledPlugins={"ai-serena@ai": False})
    code, out = bash(LIBS + "claude_take_serena", env)
    assert code == 0 and "serena" in jload(cj)["mcpServers"], out
    set_settings(home, enabledPlugins={"ai-serena@ai": True})
    code, out = bash(LIBS + "claude_take_serena", env)
    assert code == 0 and "serena" in jload(cj)["mcpServers"] and "serena not on PATH" in out, \
        "no serena binary: the plugin cannot run, the user copy stays: " + out
    stub(os.path.join(bindir, "serena"), "#!/bin/sh\necho serena 2.1.0\n")
    os.rename(os.path.join(bindir, "claude"), os.path.join(bindir, "claude-real"))
    stub(os.path.join(bindir, "claude"), '#!/bin/sh\nif [ "$1 $2" = "plugin list" ]; then\n'
         'printf "Installed plugins:\\n\\n  \\342\\235\\257 ai-serena@ai\\n    Scope: user\\n    Status: x %s\\n" "$FAKE_SERENA_STATUS"\n'
         'exit 0\nfi\nexec "$(dirname "$0")/claude-real" "$@"\n')
    code, out = bash(LIBS + "claude_take_serena", dict(env, FAKE_SERENA_STATUS="disabled"))
    assert code == 0 and "serena" in jload(cj)["mcpServers"], "listed disabled: kept: " + out
    code, out = bash(LIBS + "claude_take_serena", dict(env, FAKE_SERENA_STATUS="enabled"))
    assert code == 0, out
    assert set(jload(cj)["mcpServers"]) == {"context7"}, read(cj)
    assert "restore:claude-user-mcp:serena" in [e["key"] for e in entries(home)]
    code, out = run_undo(env, home)
    assert "serena" in jload(cj)["mcpServers"], out


RTK_RELEASES = [{"tag_name": "v1.2.0", "prerelease": False, "draft": False, "assets": []},
                {"tag_name": "v1.1.0", "prerelease": False, "draft": False, "assets": []},
                {"tag_name": "v0.49.0", "prerelease": False, "draft": False, "assets": []}]


def rtk_env(work, with_brew=True, hold=""):
    sha = "c" * 40
    fx = os.path.join(work, "fx.json")
    write(fx, json.dumps({"http": {"https://api.github.com/repos/rtk-ai/rtk/releases?per_page=100": RTK_RELEASES},
                          "git": {"https://github.com/rtk-ai/rtk --tags": "%s\trefs/tags/v1.2.0\n%s\trefs/tags/v1.1.0\n"
                                  % (sha, "d" * 40)}}))
    prefix = os.path.join(work, "brew")
    env, home, bindir = env_for(work, 'RTK_SOURCE="github rtk-ai/rtk stable"\n' + ("RTK_HOLD=%s\n" % hold if hold else ""),
                                extra_path=os.path.join(prefix, "bin") + ":" + os.path.join(work, "home", ".local", "bin"))
    env.update({"AI_RESOLVE_FIXTURES": fx, "FAKE_BREW_PREFIX": prefix, "FAKE_BREW_RTK_NEW": "1.2.0"})
    cellar = os.path.join(prefix, "Cellar", "rtk", "0.49.0", "bin", "rtk")
    stub(cellar, '#!/bin/sh\necho "rtk 0.49.0"\n')
    os.makedirs(os.path.join(prefix, "bin"))
    os.symlink("../Cellar/rtk/0.49.0/bin/rtk", os.path.join(prefix, "bin", "rtk"))
    if with_brew:
        stub(os.path.join(bindir, "brew"), FAKE_BREW)
    return env, home, bindir, prefix, sha


def t_rtk_brew(work):
    """Item 5: macOS with the Homebrew formula: an older rtk is moved by `brew upgrade rtk` after the source tag is
    audited (no Rust, no build); our earlier ~/.local/bin/rtk is moved to the backup folder (restore recorded), so
    one rtk stays on PATH; a dry run changes nothing; a second run does nothing."""
    env, home, bindir, prefix, sha = rtk_env(work)
    own = os.path.join(home, ".local", "bin", "rtk")
    stub(own, '#!/bin/sh\necho "rtk 0.40.0"\n')
    write(os.path.join(home, STATE, "rtk.build"), "v0.40.0 cargo-update=1\n")
    script = LIBS + 'git_source_audited() { echo "AUDIT $*"; }; tools_rtk'
    code, out = bash(LIBS + 'AI_DRY_RUN=1; git_source_audited() { echo "AUDIT $*"; }; tools_rtk', env)
    assert code == 0 and "[dry-run] env HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade rtk" in out and os.path.exists(own), out
    assert "brew upgrade" not in read(env["FAKE_LOG"]) and "cargo" not in out, out
    code, out = bash(script, env)
    assert code == 0, out
    assert "brew upgrade rtk (HOMEBREW_NO_AUTO_UPDATE=1)" in read(env["FAKE_LOG"]), read(env["FAKE_LOG"])
    assert "AUDIT rtk https://github.com/rtk-ai/rtk v1.2.0 %s" % sha in out, out
    res = subprocess.run([os.path.join(prefix, "bin", "rtk"), "--version"], stdout=subprocess.PIPE)
    assert res.stdout.decode().strip() == "rtk 1.2.0", res.stdout
    assert not os.path.exists(own) and not os.path.exists(os.path.join(home, STATE, "rtk.build")), out
    backups = os.listdir(os.path.join(home, STATE, "backup"))
    assert len(backups) == 1 and backups[0].startswith("rtk."), backups
    assert "cmd:bin:rtk-own-copy-removed" in [e["key"] for e in entries(home)], "undone with the tools"
    resolved = jload(os.path.join(home, STATE, "resolved.json"))
    assert resolved["tools"]["rtk"]["installed"]["version"] == "1.2.0", resolved
    assert "brew-upgrade 0.49.0 -> 1.2.0 (homebrew/core; tag v1.2.0 (%s) audited)" % sha in \
        read(os.path.join(home, STATE, "audit.log"))
    code, out = bash(LIBS + "type -ap rtk | sort -u | wc -l", env)
    assert out.strip() == "1", "one rtk on PATH: " + out
    os.remove(env["FAKE_LOG"])
    code, out = bash(script, env)
    assert code == 0 and "present (Homebrew formula, newest stable)" in out, out
    assert "upgrade" not in read(env["FAKE_LOG"]), read(env["FAKE_LOG"])
    code, out = run_undo(env, home, only="^cmd:bin:rtk-own-copy-removed$")
    assert os.path.exists(own), "undo puts our copy back: " + out


def t_rtk_no_brew(work):
    """Item 5: no brew on the machine: the source build as before (planned in a dry run), no brew call."""
    env, home, bindir, prefix, sha = rtk_env(work, with_brew=False)
    env["PATH"] = ":".join([bindir, SYS_PATH])
    stub(os.path.join(bindir, "cargo"), "#!/bin/sh\nexit 0\n")
    code, out = bash(LIBS + "AI_DRY_RUN=1; tools_rtk", env)
    assert code == 0, out
    assert "[dry-run] git clone --depth 1 --branch v1.2.0 https://github.com/rtk-ai/rtk" in out, out
    assert "brew upgrade" not in out and "Homebrew" not in out, out


def omx_hook(node):
    return '"%s" "/opt/homebrew/lib/node_modules/oh-my-codex/dist/scripts/codex-native-hook.js"' % node


def t_omx_node_fix(work):
    """Item 6: oh-my-codex hook commands on a versioned Cellar node point to <brew prefix>/opt/node/bin/node when it
    exists; other hooks untouched; a Codex trust hash that matched the old command moves along (others stay);
    recorded; idempotent; undo puts both back; no stable link: nothing changes."""
    env, home, bindir = env_for(work)
    prefix = os.path.join(work, "brew")
    env.update({"FAKE_BREW_PREFIX": prefix, "FAKE_BREW_RTK_NEW": "x", "AI_BREW_PREFIXES": ""})
    stub(os.path.join(bindir, "brew"), FAKE_BREW)
    cellar = os.path.join(prefix, "Cellar", "node", "26.5.0_1", "bin", "node")
    stub(cellar, "#!/bin/sh\n")
    hj = os.path.join(home, ".codex", "hooks.json")
    hooks = {"hooks": {
        "SessionStart": [{"matcher": "startup|resume|clear", "hooks": [{"type": "command", "command": omx_hook(cellar)}]},
                         {"hooks": [{"type": "command", "command": "sh '/x/herdr-app/session-note.sh'"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": omx_hook(cellar), "timeout": 30}]}],
        "PreToolUse": [{"hooks": [{"type": "command", "command": '"%s" /other/tool.js' % cellar}]}]}}
    write(hj, json.dumps(hooks))
    h_old = aiconf.codex_hook_hash("SessionStart", "startup|resume|clear", {"type": "command", "command": omx_hook(cellar)})
    cfg = os.path.join(home, ".codex", "config.toml")
    orig_cfg = ('model = "x"\n\n[hooks.state."%s:session_start:0:0"]\ntrusted_hash = "%s"\n\n'
                '[hooks.state."%s:stop:0:0"]\ntrusted_hash = "sha256:stale"\n' % (hj, h_old, hj))
    write(cfg, orig_cfg)
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    assert code == 0 and "no <brew prefix>/opt/node/bin/node" in out and read(hj) == json.dumps(hooks), out
    stable = os.path.join(prefix, "opt", "node", "bin", "node")
    stub(stable, "#!/bin/sh\n")
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    assert code == 0, out
    data = jload(hj)["hooks"]
    assert data["SessionStart"][0]["hooks"][0]["command"] == omx_hook(stable), data
    assert data["Stop"][0]["hooks"][0]["command"] == omx_hook(stable) and data["Stop"][0]["hooks"][0]["timeout"] == 30
    assert data["SessionStart"][1]["hooks"][0]["command"] == "sh '/x/herdr-app/session-note.sh'"
    assert data["PreToolUse"][0]["hooks"][0]["command"] == '"%s" /other/tool.js' % cellar, "only oh-my-codex hooks"
    h_new = aiconf.codex_hook_hash("SessionStart", "startup|resume|clear", {"type": "command", "command": omx_hook(stable)})
    text = read(cfg)
    assert 'trusted_hash = "%s"' % h_new in text and h_old not in text and '"sha256:stale"' in text, text
    assert any(e["key"].startswith("hook-cmd:%s:" % hj) for e in entries(home))
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    assert code == 0 and "no oh-my-codex hook on a versioned Cellar node" in out, out
    code, out = run_undo(env, home)
    assert code == 0 and jload(hj) == hooks and read(cfg) == orig_cfg, (out, read(cfg))
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    os.remove(cellar)                      # brew upgrade node removed the old Cellar folder
    code, out = run_undo(env, home)
    assert code == 0 and "no longer exists" in out, out
    assert jload(hj)["hooks"]["Stop"][0]["hooks"][0]["command"] == omx_hook(stable), "undo keeps the working path"


def t_omx_nvm_fix(work):
    """QA 2026-11-15 item 6 (old Mac): every oh-my-codex hook named a script in ~/.nvm/versions/node/v24.13.0, gone
    after an nvm update to v24.18.0. Install points it to the current node and the same script under the version
    that has it (recorded; idempotent; undo puts it back); other hooks stay; ai-doctor FAILs a missing path."""
    env, home, bindir = env_for(work)
    env["AI_BREW_PREFIXES"] = ""
    new = os.path.join(home, ".nvm", "versions", "node", "v24.18.0")
    stub(os.path.join(new, "bin", "node"), "#!/bin/sh\n")
    write(os.path.join(new, "lib", "node_modules", "oh-my-codex", "dist", "scripts", "codex-native-hook.js"), "")
    os.makedirs(os.path.join(home, ".nvm", "versions", "node", "v9.1.0"))
    env["PATH"] = os.path.join(new, "bin") + ":" + env["PATH"]
    script = "lib/node_modules/oh-my-codex/dist/scripts/codex-native-hook.js"
    old_cmd = 'node "%s/.nvm/versions/node/v24.13.0/%s"' % (home, script)
    hj = os.path.join(home, ".codex", "hooks.json")
    hooks = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": old_cmd}]}],
                       "PreToolUse": [{"hooks": [{"type": "command", "command": "rtk hook codex"}]}]}}
    write(hj, json.dumps(hooks))
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    assert code == 0, out
    want = '"%s/bin/node" "%s/%s"' % (new, new, script)
    data = jload(hj)["hooks"]
    assert data["Stop"][0]["hooks"][0]["command"] == want, (data, out)
    assert data["PreToolUse"][0]["hooks"][0]["command"] == "rtk hook codex"
    code, out = bash(LIBS + "codex_omx_node_fix", env)
    assert code == 0 and jload(hj)["hooks"]["Stop"][0]["hooks"][0]["command"] == want, out
    code, out = run_undo(env, home)
    assert code == 0 and jload(hj) == hooks, out
    os.environ.update({"HOME": home, "CODEX_HOME": os.path.join(home, ".codex"),
                       "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude")})
    write(os.path.join(home, ".claude", "settings.json"), json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "/gone/bin/python3 /x/hook.py"}]}]}}))
    doc = load_doctor(env)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        doc.check_hook_paths()
    text = buf.getvalue()
    assert "FAIL hook interpreter or script path missing" in text and "v24.13.0" in text and "/gone/bin/python3" in text, text


def t_last30days(work):
    """Item 7: last30days follows the newest stable tag through claude_git_plugin (audited first); a foreign
    marketplace without a tag is replaced (plugin data kept, restore recorded) and the plugin is on; strict intake
    files exist with the five contract sections and no em dash; the toolbox line and TOOLS.md entry exist."""
    up = os.path.join(work, "up", "mvanhorn", "last30days-skill")
    shas = upstream(up, "last30days-skill", "last30days", ["3.9.3", "3.9.4"])
    env, home, bindir = claude_env(work, 'LAST30DAYS_SOURCE="git %s stable"\n' % up)
    code, out = bash("claude plugin marketplace add mvanhorn/last30days-skill && "
                     "claude plugin install last30days@last30days-skill --scope user", env)
    assert code == 0, out
    tr.set_enabled(home, "last30days@last30days-skill", False)
    code, out = bash(LIBS + 'audit_ok() { return 1; }; claude_last30days', env)
    assert code == 0 and tr.enabled(home)["last30days@last30days-skill"] is False, "plugin step failed: not turned on"
    assert not os.path.exists(os.path.join(home, STATE, "last30days.on-once")), out
    os.remove(os.path.join(work, "log"))
    script = LIBS + 'audit_ok() { echo "AUDIT $*"; return 0; }; claude_last30days'
    code, out = bash(script, env)
    assert code == 0, out
    known, plugins = tr.claude_files(home)
    assert known["last30days-skill"]["source"] == {"source": "github", "repo": "mvanhorn/last30days-skill",
                                                   "ref": "v3.9.4"}, known
    assert plugins["last30days@last30days-skill"][0]["gitCommitSha"] == shas["3.9.4"], plugins
    assert "AUDIT dir" in out and "%s last30days" % shas["3.9.4"] in out, out
    assert tr.mutations(work)[0] == "claude plugin uninstall last30days@last30days-skill --keep-data", tr.mutations(work)
    assert tr.enabled(home)["last30days@last30days-skill"] is True
    keys = [e["key"] for e in entries(home)]
    assert "cmd:claude-marketplace-restore:last30days-skill" in keys, keys
    os.remove(os.path.join(work, "log"))
    code, out = bash(script, env)
    assert code == 0 and tr.mutations(work) == [], tr.mutations(work)
    tr.set_enabled(home, "last30days@last30days-skill", False)       # the owner turns it off later
    code, out = bash(script, env)
    assert code == 0 and tr.enabled(home)["last30days@last30days-skill"] is False and "off by your choice" in out, out
    pins = read(os.path.join(AI_DIR, "pins.env"))
    assert 'LAST30DAYS_SOURCE="git https://github.com/mvanhorn/last30days-skill stable"' in pins
    contract = read(os.path.join(AI_DIR, "rules", "last30days.md"))
    heads = [h.lower() for h in __import__("re").findall(r"^##+\s*(.+)$", contract, __import__("re").M)]
    for sec in ("vendor rules", "when", "enforcement", "proof", "setup checklist"):
        assert any(h.startswith(sec) for h in heads), sec
    assert "check-config.sh" in contract and "SETUP_COMPLETE=true" in contract and "Verify" in contract
    evals = read(os.path.join(AI_DIR, "evals", "last30days.md"))
    assert evals.count(" ; ") >= 3 and "NOT" in evals
    for text in (contract, evals):
        assert "\u2014" not in text, "no em dash"
    assert "last30days" in read(os.path.join(AI_DIR, "agents-md", "90-toolbox-and-vendor-rules.md"))
    assert "### last30days" in read(os.path.join(REPO, "docs", "TOOLS.md"))


def doctor_run(env, linux=None):
    """check_drops_and_defaults of ai-doctor with this env; returns its printed lines."""
    from importlib.machinery import SourceFileLoader
    import importlib.util
    old = dict(os.environ)
    os.environ.update(env)
    os.environ.pop("AI_PINS", None)        # the real ai/pins.env lists
    try:
        loader = SourceFileLoader("ai_doctor_m3", os.path.join(AI_DIR, "bin", "ai-doctor"))
        spec = importlib.util.spec_from_loader("ai_doctor_m3", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        if linux is not None:
            mod.LINUX = linux
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.check_drops_and_defaults()
        return buf.getvalue()
    finally:
        os.environ.clear()
        os.environ.update(old)


def t_doctor(work):
    """Item 8: ai-doctor FAILs each leftover (caveman plugin and hooks, byterover in Claude and Codex, a plugin on
    the off list that is on, a second serena, two rtk on PATH, an OMX hook on a Cellar node, last30days missing)
    and PASSes once the machine is clean."""
    env, home, bindir = claude_env(work)
    second = os.path.join(work, "bin2")
    stub(os.path.join(bindir, "rtk"), "#!/bin/sh\necho rtk 1.2.0\n")
    stub(os.path.join(second, "rtk"), "#!/bin/sh\necho rtk 0.40.0\n")
    env["PATH"] = ":".join([bindir, second, SYS_PATH])
    env["AI_PROFILE"] = "server"        # last30days is a server default (dev-mac has none)
    installed_plugins(home, ["caveman@caveman", "typesafe@typesafe-ai", "ai-serena@ai"])
    set_settings(home, enabledPlugins={"typesafe@typesafe-ai": True, "ai-serena@ai": True},
                 hooks={"SessionStart": [{"hooks": [{"type": "command", "command": "node caveman-activate.js"}]}]})
    write(os.path.join(home, ".claude", ".claude.json"),
          json.dumps({"mcpServers": {"byterover-mcp": {"url": "u"}, "serena": {"command": "uvx"}},
                      "projects": {"/w/p": {"mcpServers": {"caveman-shrink": {"command": "npx"}}}}}))
    write(os.path.join(home, ".codex", "config.toml"), '[mcp_servers.byterover-mcp]\nurl = "u"\n')
    write(os.path.join(home, ".codex", "hooks.json"), json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": omx_hook("/opt/homebrew/Cellar/node/26.5.0_1/bin/node")}]}]}}))
    out = doctor_run(env)
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
    for want in ("dropped Claude plugins gone", "dropped hooks gone", "dropped MCP servers gone", "one Serena",
                 "one rtk on PATH", "OMX Codex hooks start node", "last30days installed and on"):
        assert any(want in ln for ln in fails), (want, out)
    assert "claude:byterover-mcp" in out and "codex:byterover-mcp" in out, out
    assert any(ln.startswith("WARN typesafe off at user scope") for ln in out.splitlines()), out
    assert "WARN dropped MCP servers in project (local) scope: caveman-shrink (/w/p)" in out, out
    out = doctor_run(env, linux=True)
    assert any(ln.startswith("WARN rtk on PATH") for ln in out.splitlines()) and "one rtk" not in out, \
        "servers: a second rtk is a WARN, not a FAIL: " + out
    os.remove(os.path.join(second, "rtk"))
    installed_plugins(home, ["typesafe@typesafe-ai", "ai-serena@ai", "last30days@last30days-skill"])
    set_settings(home, enabledPlugins={"typesafe@typesafe-ai": False, "ai-serena@ai": True,
                                       "last30days@last30days-skill": True}, hooks={})
    write(os.path.join(home, ".claude", ".claude.json"), json.dumps({"mcpServers": {"context7": {"url": "u"}}}))
    write(os.path.join(home, ".codex", "config.toml"), 'model = "x"\n')
    write(os.path.join(home, ".codex", "hooks.json"), json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": omx_hook("/opt/homebrew/opt/node/bin/node")}]}]}}))
    out = doctor_run(env)
    bad = [ln for ln in out.splitlines() if ln.startswith(("FAIL", "WARN"))]
    assert not bad, out
    assert "PASS OMX Codex hooks do not use a versioned Cellar node" in out and "PASS one rtk on PATH" in out, out


def t_drop_failures(work):
    """A failing `claude mcp remove` / `codex mcp remove` is a warning: the install goes on (set -e), the entry
    stays, nothing is recorded. A failing plugin uninstall leaves its settings.json hooks alone."""
    env, home = caveman_setup(work)
    code, out = bash(LIBS + "claude_mcp; echo CONTINUED", dict(env, FAKE_MCP_REMOVE_FAIL="1"))
    assert code == 0 and "CONTINUED" in out and "WARN: claude mcp remove --scope user" in out, out
    assert {"byterover-mcp", "caveman-shrink"} <= set(jload(os.path.join(home, ".claude", ".claude.json"))["mcpServers"])
    assert not any(e["key"].startswith("restore:claude-user-mcp:") for e in entries(home)), entries(home)
    code, out = bash(LIBS + "claude_drop_plugins; claude_drop_hooks; echo CONTINUED", dict(env, FAKE_UNINSTALL_FAIL="1"))
    assert code == 0 and "CONTINUED" in out and "uninstall caveman@caveman failed" in out, out
    assert "still installed" in out and "caveman-activate.js" in read(os.path.join(home, ".claude", "settings.json"))
    assert not any(e["key"].startswith(("hook:", "cmd:claude-plugin-restore")) for e in entries(home)), entries(home)
    stub(os.path.join(env["PATH"].split(":")[0], "codex"), FAKE_CODEX)
    cfg = os.path.join(home, ".codex", "config.toml")
    write(cfg, '[mcp_servers.byterover-mcp]\nurl = "u"\n')
    code, out = bash(LIBS + 'aiconf codex-drop-mcp "$CODEX_DIR/config.toml" $AI_DROP_MCP; echo CONTINUED',
                     dict(env, FAKE_CODEX_REMOVE_FAIL="1"))
    assert code == 0 and "CONTINUED" in out and "WARN: codex mcp remove byterover-mcp failed" in out, out
    assert "byterover-mcp" in read(cfg) and not any(e["key"].startswith("restore:codex-mcp:") for e in entries(home))


def t_rtk_brew_mismatch(work):
    """HIGH review item: Homebrew's formula must be exactly the audited version from homebrew/core, else no brew
    upgrade (WARN, the installed rtk stays); RTK_HOLD counts as the audited version; RTK_BREW_MISMATCH=build takes
    the source build of the audited tag instead."""
    env, home, bindir, prefix, sha = rtk_env(work)
    script = LIBS + 'git_source_audited() { echo "AUDIT $*"; }; tools_rtk'
    code, out = bash(script, dict(env, FAKE_BREW_STABLE="1.3.0"))
    assert code == 0 and "Homebrew formula is homebrew/core 1.3.0, the audited version is 1.2.0" in out, out
    assert "upgrade" not in read(env["FAKE_LOG"]) and "AUDIT" not in out, read(env["FAKE_LOG"])
    code, out = bash(script, dict(env, FAKE_BREW_TAP="someone/tap"))
    assert code == 0 and "someone/tap 1.2.0" in out and "upgrade" not in read(env["FAKE_LOG"]), out
    stub(os.path.join(bindir, "cargo"), "#!/bin/sh\nexit 0\n")
    code, out = bash(LIBS + 'AI_DRY_RUN=1; RTK_BREW_MISMATCH=build; tools_rtk', dict(env, FAKE_BREW_STABLE="1.3.0"))
    assert code == 0 and "source build instead" in out and "[dry-run] git clone --depth 1 --branch v1.2.0" in out, out
    hold_work = os.path.join(work, "hold")
    os.makedirs(hold_work)
    env, home, bindir, prefix, sha = rtk_env(hold_work, hold="1.1.0")
    code, out = bash(script, env)                     # brew has 1.2.0, the hold is 1.1.0: no upgrade
    assert code == 0 and "audited version is 1.1.0" in out and "upgrade" not in read(env["FAKE_LOG"]), out
    code, out = bash(script, dict(env, FAKE_BREW_STABLE="1.1.0", FAKE_BREW_RTK_NEW="1.1.0"))
    assert code == 0 and "brew upgrade rtk" in read(env["FAKE_LOG"]) and "AUDIT rtk https://github.com/rtk-ai/rtk v1.1.0 " \
        + "d" * 40 in out, out
    code, out = bash(script, dict(env, FAKE_BREW_STABLE="1.1.0", FAKE_BREW_RTK_NEW="1.1.0"))
    assert code == 0 and "present (Homebrew formula, held version)" in out, out


def t_codex_restore_quoted(work):
    """Undo of a Codex MCP restore does not append a second copy when the entry is back under a quoted header."""
    env, home, bindir = env_for(work)
    stub(os.path.join(bindir, "codex"), "#!/bin/sh\nexit 0\n")
    cfg = os.path.join(home, ".codex", "config.toml")
    write(cfg, '[mcp_servers."byterover-mcp"]\nurl = "u"\n')
    blob = os.path.join(work, "blob.toml")
    write(blob, '[mcp_servers.byterover-mcp]\nurl = "u"\n')
    write(os.path.join(home, STATE, "managed-keys.json"), json.dumps({"version": 1, "entries": [
        {"kind": "codex-mcp-restore", "file": cfg, "name": "byterover-mcp", "blob": blob, "prefix": [],
         "key": "restore:codex-mcp:byterover-mcp"}]}))
    code, out = run_undo(env, home)
    assert code == 0 and read(cfg).count("byterover-mcp") == 1, (out, read(cfg))


OMC_COMPANION = "# OMC\n<!-- OMC:START -->\nomc rules here\n<!-- OMC:END -->\n"


def load_doctor(env):
    from importlib.machinery import SourceFileLoader
    import importlib.util
    old = dict(os.environ)
    os.environ.update(env)
    try:
        loader = SourceFileLoader("ai_doctor_omc", os.path.join(AI_DIR, "bin", "ai-doctor"))
        spec = importlib.util.spec_from_loader("ai_doctor_omc", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    finally:
        os.environ.clear()
        os.environ.update(old)
    mod.LINUX = False                      # the check is for macOS; this runs on every OS
    return mod


def companion_out(mod):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.check_omc_companion()
    return buf.getvalue()


def t_omc_companion(work):
    """`omc launch` reads only ~/.claude/CLAUDE-omc.md: install puts the same AI:core import block there, after
    <!-- OMC:END --> (OMC text untouched, recorded, idempotent, undo removes it); no file: nothing is created; a
    file with OMC:START but no OMC:END is left alone; ai-doctor FAILs without the block and PASSes with it; ai-sync
    adds the block when OMC created the file after install (macOS; Linux uses /etc/claude-code/CLAUDE.md)."""
    env, home, bindir = claude_env(work)
    want = 'want() { [ "$1" = claude ]; }; '
    comp = os.path.join(home, ".claude", "CLAUDE-omc.md")
    code, out = bash(LIBS + want + "base_rules_user", env)
    assert code == 0 and not os.path.exists(comp), out
    write(comp, "<!-- OMC:START -->\nbroken\n")
    code, out = bash(LIBS + want + "base_rules_user", env)
    assert code == 0 and read(comp) == "<!-- OMC:START -->\nbroken\n" and "without <!-- OMC:END -->" in out, out
    write(comp, OMC_COMPANION)
    mod = load_doctor(env)
    assert companion_out(mod).startswith("FAIL"), companion_out(mod)
    code, out = bash(LIBS + want + "base_rules_user", env)
    assert code == 0, out
    text = read(comp)
    assert text.startswith(OMC_COMPANION), "OMC text untouched: " + text
    tail = text[len(OMC_COMPANION):]
    assert "<!-- AI:core v1 START -->\n@~/.config/ai/AGENTS.md\n<!-- AI:core v1 END -->" in tail, text
    assert "@~/.config/ai/AGENTS.md" in read(os.path.join(home, ".claude", "CLAUDE.md"))
    assert "block:%s:core" % comp in [e["key"] for e in entries(home)]
    assert companion_out(mod).startswith("PASS"), companion_out(mod)
    code, out = bash(LIBS + want + "claude_omc_companion_block", env)
    assert code == 0 and read(comp) == text and "same" in out, out
    code, out = run_undo(env, home)
    assert code == 0 and read(comp) == OMC_COMPANION, (out, read(comp))
    # ai-sync (after a pull): OMC made the file after install.
    write(comp, OMC_COMPANION)
    uv = shutil.which("uv")                # ai-sync runs ai-render, which needs uv (or PyYAML)
    sync_env = dict(env, PATH=env["PATH"] + (":" + os.path.dirname(uv) if uv else ""))
    res = subprocess.run(["bash", os.path.join(AI_DIR, "bin", "ai-sync")], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=sync_env)
    out = res.stdout.decode()
    assert res.returncode == 0, out
    if sys.platform.startswith("linux"):
        assert read(comp) == OMC_COMPANION, "Linux: /etc/claude-code/CLAUDE.md carries the rules: " + out
    else:
        assert "<!-- AI:core v1 START -->" in read(comp)[len(OMC_COMPANION):], out
    dtext = read(os.path.join(AI_DIR, "bin", "ai-doctor"))
    assert "check_omc_companion()" in dtext



def t_yaml_top_set_block_list(work):
    """yaml-top-set replaces a block sequence written at column 0 ("key:\n- a\n- b", Serena 2.1's default_modes)
    and repairs a file an older install left broken (the flow value followed by stray "- a" lines)."""
    cfg = os.path.join(work, "serena_config.yml")
    state = os.path.join(work, "keys.json")
    run = [sys.executable, os.path.join(AI_DIR, "lib", "aiconf.py"), "--state", state, "yaml-top-set", cfg,
           "default_modes", "[no-memories]"]
    for start in ("base_modes:\ndefault_modes:\n- interactive\n- editing\n\nnext: 1\n",
                  "base_modes:\ndefault_modes: [no-memories]\n- interactive\n- editing\n\nnext: 1\n"):
        with open(cfg, "w") as fh:
            fh.write(start)
        subprocess.check_call(run, stdout=subprocess.DEVNULL)
        got = open(cfg).read()
        assert got == "base_modes:\ndefault_modes: [no-memories]\n\nnext: 1\n", repr(got)
    subprocess.check_call(run, stdout=subprocess.DEVNULL)
    assert open(cfg).read() == "base_modes:\ndefault_modes: [no-memories]\n\nnext: 1\n", "second run changes nothing"


if __name__ == "__main__":
    sys.exit(main())
