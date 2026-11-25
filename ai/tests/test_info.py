#!/usr/bin/env python3
"""Tests for ai/bin/ai-info and ai-doctor --numbers: a throwaway HOME, fake agent binaries, no network.

Run: python3 ai/tests/test_info.py   (bash ai/tests/run.sh runs it too)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
INFO = os.path.join(AI_DIR, "bin", "ai-info")
DOCTOR = os.path.join(AI_DIR, "bin", "ai-doctor")
FAILS = []
SECRET = "ctx7sk-" + "q1w2e3r4-" * 4 + "notforprint"


def main():
    work = tempfile.mkdtemp(prefix="ai-info-tests-")
    try:
        home, fake, repo = setup(work)
        for test in (t_full, t_short, t_project_state, t_off_here, t_outside_repo, t_no_secrets_fast, t_devmac,
                     t_numbers_fixture_logs, t_numbers_temp_rows_left_out, t_numbers_no_logs, t_numbers_json_schema,
                     t_numbers_live):
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
                 "mattpocock global: grilling, grill-me, wait-what, retro, writing-for-agents (missing), ask-matt (missing)",
                 "context7 (global", "box (global, server boxes", "Gates: audit-before-install, secret-scan, no-sudo, no-destroy, pr-rules",
                 "sudo ai-gate-skip", "On by default in every project: serena, graph", "ai-adopt --tools browser",
                 "serena (global", "docs/SECURITY.md"):
        assert want in out, "%r not in output:\n%s" % (want, out)


def t_devmac(home, fake, repo):
    """Profile dev-mac: no box, no audit gate, no gate skip; the profile is shown with where it came from."""
    out = run(home, fake, repo, extra_env={"AI_PROFILE": "dev-mac",
                                           "AI_ROUTING_JSON": os.path.join(home, "..", "routing-dev-mac.json")}).stdout
    assert "Profile: dev-mac (AI_PROFILE)" in out, out
    assert "box (global" not in out and "audit-before-install" not in out and "ai-gate-skip" not in out, out
    assert "Gates: secret-scan, pr-rules" in out and "the owner runs a blocked command himself" in out, out
    write(os.path.join(home, ".config", "ai", "profile"), "server\n")
    out = run(home, fake, repo, "--short", extra_env={"AI_PROFILE": ""}).stdout
    os.remove(os.path.join(home, ".config", "ai", "profile"))
    assert "(profile server (~/.config/ai/profile))" in out.splitlines()[0], out


def t_short(home, fake, repo):
    out = run(home, fake, repo, "--short").stdout
    lines = out.strip().splitlines()
    assert 6 <= len(lines) <= 10, "short output must be about 8 lines, got %d:\n%s" % (len(lines), out)
    assert lines[0].startswith("AI agents: claude 2.1.5, codex 0.120.0"), lines[0]
    assert "per project: claude-seo" in out and "Every project: serena, graph" in out, out
    assert "--tools serena" not in out and "|graph" not in out, out
    assert "More: ai-info" in out, out


def t_project_state(home, fake, repo):
    out = run(home, fake, repo).stdout
    assert "This project (proj): Map present (2 lines), Libraries not needed (no dependencies), enabled: seo" in out, out
    with open(os.path.join(repo, "pyproject.toml"), "w") as fh:
        fh.write('[project]\nname = "p"\nversion = "0"\ndependencies = ["httpx"]\n')
    out = run(home, fake, repo).stdout
    assert "Libraries missing (ai-libs --sync)" in out, out
    os.remove(os.path.join(repo, "pyproject.toml"))


def t_off_here(home, fake, repo):
    """Ticket rules-that-hold 11: an adopted project lists the opt-in tools it did not enable."""
    line = next((ln for ln in run(home, fake, repo).stdout.splitlines() if ln.startswith("  Off here: ")), "")
    off = line[len("  Off here: "):].split(" (")[0].split(", ")
    assert "blog" in off and "browser" in off, line
    assert "seo" not in off and "serena" not in off and "graph" not in off, line
    assert line.endswith("(ai-adopt --tools <id> turns one on)."), line


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


def t_numbers_fixture_logs(home, fake, repo):
    """ai-doctor --numbers: the 6 sections, each count as the fixture below states, and exit 0 (plain ai-doctor FAILs
    in this throwaway HOME)."""
    res = numbers(home, fake, repo)
    out = res.stdout
    assert res.returncode == 0, out
    assert not [ln for ln in out.splitlines() if ln.startswith(("FAIL", "PASS", "WARN"))], "no check may run:\n" + out
    for n in range(1, 7):
        assert "\n%d. " % n in out, "section %d missing:\n%s" % (n, out)
    want = [
        "global rules (~/.config/ai/AGENTS.md)  10",     # section 1
        "Codex rules (~/.codex/AGENTS.md)  5",
        "project AGENTS.md  %d" % len(PROJECT_AGENTS.split()),
        "project CLAUDE.local.md  missing",
        "hook total  5",                                  # section 2: 3 + 2 words
        "Codex start text  not measured",
        "Claude hook commands  9",          # section 3: settings 3, demo 5, listed 1, the off plugin not counted
        "Claude SessionStart  listed 1, settings 2",
        "Claude PreToolUse  demo 3, settings 1",
        "Claude hook processes for one Bash call  3",
        "Codex hook commands  1",
        "skill descriptions (2 entries)  6",              # section 4
        "agent descriptions (2 entries)  3",
        "MCP instructions (1 servers)  3",
        "deferred tool names  2 names, 5 characters",
        "MCP tool schemas  not measured",
        "gate denies  3",                                 # section 5: pr-rules 2, secret-scan 1
        "pr-rules  2",
        "repeated denies  1 command(s), 2 denies",
        "tdd  fired claude 3, codex 1  missed claude 2, codex 0",     # section 6
        "docs-lookup  fired claude 2, codex 0  missed claude 1, codex 0",   # the miss is in misses.jsonl.1
        "rows from temp folders left out  4",
    ]
    for line in want:
        assert squash(line) in squash(out), "%r not in output:\n%s" % (line, out)


def t_numbers_temp_rows_left_out(home, fake, repo):
    """Rows whose cwd (repo for walls, session for gates.log) is a temp or .verify folder are not counted."""
    out = squash(numbers(home, fake, repo).stdout)
    assert squash("secret-scan  1") in out and "temp-only" not in out, out
    assert squash("rows from temp folders left out  4 (fired 1, misses 1, walls 1, gates.log 1)") in out, out


def t_numbers_no_logs(home, fake, repo):
    """A new machine: no logs, no transcript, no git repo. Each count is 0 with "no log"; nothing crashes."""
    empty = os.path.join(home, "..", "state-empty")
    os.makedirs(empty, exist_ok=True)
    res = numbers(home, fake, home, state=empty)
    out = squash(res.stdout)
    assert res.returncode == 0, res.stdout
    for line in ("gate denies  0 (no log)", "reminder fires  0 (no log)", "reminder misses  0 (no log)",
                 "project AGENTS.md  not adopted", "session-start text  not measured: no Claude transcript",
                 "rows from temp folders left out  0"):
        assert squash(line) in out, "%r not in output:\n%s" % (line, res.stdout)
    assert "Traceback" not in out, res.stdout


def t_numbers_json_schema(home, fake, repo):
    res = numbers(home, fake, repo, "--json")
    assert res.returncode == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["version"] == 1 and "commit" in data, data
    for key in ("rules_files", "start_text", "hooks", "descriptions", "gate_denies", "reminders"):
        assert isinstance(data.get(key), dict), "section %s missing: %s" % (key, data)
    assert data["rules_files"]["global"] == 10 and data["rules_files"]["project_claude_local"] == "missing", data
    assert data["start_text"]["total"] == 5 and data["start_text"]["codex"].startswith("not measured"), data
    assert data["hooks"]["claude_bash_processes"] == 3 and data["hooks"]["claude_total"] == 9, data
    assert data["gate_denies"]["total"] == 3 and data["gate_denies"]["by_wall"] == {"pr-rules": 2, "secret-scan": 1}
    assert data["reminders"]["rules"]["tdd"] == {"fired": {"claude": 3, "codex": 1}, "missed": {"claude": 2, "codex": 0}}
    assert data["left_out_temp_rows"]["total"] == 4, data
    with open(os.path.join(home, "..", "routing-server.json")) as fh:
        nudges = len([r for r in json.load(fh)["rules"] if r.get("strength") == "nudge"])
    assert data["reminders"]["reminder_rules"] == nudges, data


def t_numbers_live(home, fake, repo):
    """Ticket rules-that-hold 27: --live runs one claude -p session in the project and prints its start tokens (all
    input tokens) and cost; without --live no model call is made."""
    live = os.path.join(home, "..", "bin-live")
    calls = os.path.join(home, "..", "live-calls.txt")
    write(os.path.join(live, "claude"), "#!/bin/sh\n[ \"$1\" = -p ] || { echo '2.1.5 (Claude Code)'; exit 0; }\n"
          "pwd >> '%s'; echo \"$*\" >> '%s'\n"
          "echo '{\"type\":\"result\",\"total_cost_usd\":0.0123,\"usage\":{\"input_tokens\":40,"
          "\"cache_creation_input_tokens\":2000,\"cache_read_input_tokens\":40342,\"output_tokens\":3}}'\n"
          % (calls, calls), 0o755)
    path = live + os.pathsep + fake
    res = numbers(home, path, repo)
    assert res.returncode == 0 and not os.path.exists(calls), "no --live, no model call:\n" + res.stdout
    assert "Live session" not in res.stdout, res.stdout
    res = numbers(home, path, repo, "--live")
    out = squash(res.stdout)
    assert res.returncode == 0, res.stdout
    assert squash("start tokens (measured)  42382") in out and squash("cost  0.0123 USD") in out, res.stdout
    with open(calls) as fh:
        lines = fh.read().splitlines()
    assert len(lines) == 2 and os.path.realpath(lines[0]) == os.path.realpath(repo), lines
    assert lines[1].startswith("-p Reply with the word OK only.") and "--output-format json" in lines[1], lines
    data = json.loads(numbers(home, path, repo, "--live", "--json").stdout)
    assert data["live"] == {"start_tokens": 42382, "cost_usd": 0.0123}, data["live"]


# ---------------------------------------------------------------- helpers

PROJECT_AGENTS = "# proj\n\n<!-- AI:map START (ai-adopt) -->\n## Map\n- What: proj.\n- Run: x.\n<!-- AI:map END -->\n"


def numbers(home, fake, cwd, *args, state=None):
    """ai-doctor --numbers with the fixture state, Claude and Codex folders of numbers_fixture()."""
    work = os.path.dirname(home)
    if not os.path.isdir(os.path.join(work, "state")):
        numbers_fixture(work, home, cwd)
    env = {"HOME": home, "PATH": fake + os.pathsep + "/usr/bin:/bin", "LANG": "C.UTF-8",
           "HERMES_USER": "ai-test-no-such-user", "AI_PROFILE": "server",
           "AI_ROUTING_JSON": os.path.join(work, "routing-server.json"),
           "AI_STATE_DIR": state or os.path.join(work, "state"),
           "CLAUDE_CONFIG_DIR": os.path.join(work, "claude"), "CODEX_HOME": os.path.join(home, ".codex")}
    res = subprocess.run([sys.executable, DOCTOR, "--numbers"] + list(args), cwd=cwd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    res.stdout = res.stdout.decode("utf-8", "replace")
    return res


def numbers_fixture(work, home, repo):
    """The counts that t_numbers_* expect: rules files, one transcript, hook files and 7 days of logs."""
    write(os.path.join(home, ".config", "ai", "AGENTS.md"), "one two three four five six seven eight nine ten\n")
    write(os.path.join(home, ".codex", "AGENTS.md"), "a b c d e\n")
    write(os.path.join(home, ".codex", "hooks.json"), json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "codex-start"}]}]}}))
    claude = os.path.join(work, "claude")
    write(os.path.join(claude, "CLAUDE.md"), "x y z\n")

    def hooks(spec):
        return {ev: [{"matcher": m, "hooks": [dict(type="command", command=c, **extra) for c, extra in cmds]}
                     for m, cmds in items] for ev, items in spec.items()}
    write(os.path.join(claude, "settings.json"), json.dumps({
        "enabledPlugins": {"demo@m": True, "off@m": False, "listed@m": True},
        "hooks": hooks({"PreToolUse": [("Bash", [("rtk", {})])], "SessionStart": [("", [("a", {}), ("b", {})])]})}))
    plugins = {}
    for name, spec in (("demo", {"PreToolUse": [("*", [("r", {})]), ("Edit|Write", [("e", {})]),
                                                ("Bash", [("g", {"if": "Bash(git push *)"})])],
                                 "PostToolUse": [("Bash|Read", [("p", {})])], "Stop": [("", [("s", {})])]}),
                       ("off", {"PreToolUse": [("*", [("x", {})])]})):
        path = os.path.join(work, "plugins", name)
        write(os.path.join(path, "hooks", "hooks.json"), json.dumps({"hooks": hooks(spec)}))
        plugins[name + "@m"] = [{"scope": "user", "installPath": path}]
    listed = os.path.join(work, "plugins", "listed")       # hooks named in plugin.json, not in hooks/hooks.json
    write(os.path.join(listed, ".claude-plugin", "plugin.json"), json.dumps({"hooks": ["./hooks/start.json"]}))
    write(os.path.join(listed, "hooks", "start.json"), json.dumps({"hooks": hooks({"SessionStart": [("", [("l", {})])]})}))
    plugins["listed@m"] = [{"scope": "user", "installPath": listed}]
    write(os.path.join(claude, "plugins", "installed_plugins.json"), json.dumps({"version": 2, "plugins": plugins}))

    root = os.path.realpath(repo)
    att = [{"type": "hook_success", "hookEvent": "SessionStart", "command": "start-one", "content": "a b c"},
           {"type": "hook_success", "hookEvent": "SessionStart", "command": "start-two", "content": "",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "d e"}})},
           {"type": "skill_listing", "content": "- s1: one\n- s2: two", "skillCount": 2},
           {"type": "agent_listing_delta", "addedTypes": ["x", "z"], "addedLines": ["x y", "z"]},
           {"type": "mcp_instructions_delta", "addedNames": ["m"], "addedBlocks": ["m n o"]},
           {"type": "deferred_tools_delta", "addedNames": ["Aa", "Bbb"]}]
    rows = [{"type": "attachment", "attachment": a} for a in att] + [{"type": "assistant"}]
    write(os.path.join(claude, "projects", re.sub(r"[^A-Za-z0-9]", "-", root), "s1.jsonl"),
          "".join(json.dumps(r) + "\n" for r in rows))

    now, tmp = time.time(), os.path.join(os.path.realpath(tempfile.gettempdir()), "run-x")
    ts = lambda ago=3600: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - ago))   # noqa: E731
    row = lambda rule, agent="claude", cwd="/work/p", **kw: json.dumps(dict(   # noqa: E731
        ts=kw.pop("t", ts()), session=kw.pop("session", "s1"), agent=agent, cwd=cwd, kind="rule", rule=rule, **kw))
    state = os.path.join(work, "state")
    write(os.path.join(state, "fired.jsonl"), "\n".join(
        [row("tdd")] * 3 + [row("tdd", "codex"), row("docs-lookup"), row("docs-lookup"),
                            row("tdd", log_only=True), row("tdd", t=ts(8 * 86400)),
                            row("tdd", cwd=tmp, session="tmp-s"),
                            row("x").replace('"kind": "rule"', '"kind": "skill"')]) + "\n")
    write(os.path.join(state, "misses.jsonl"), "\n".join([row("tdd")] * 2 + [row("tdd", cwd=tmp, session="tmp-s")]) + "\n")
    write(os.path.join(state, "misses.jsonl.1"), row("docs-lookup") + "\n")
    wall = lambda w, repo="/work/p", t=None: json.dumps(   # noqa: E731
        {"ts": t or ts(), "host": "h", "repo": repo, "wall": w, "reason": "r"})
    write(os.path.join(state, "walls.jsonl"), "\n".join(
        [wall("pr-rules"), wall("pr-rules"), wall("secret-scan"), wall("temp-only", tmp),
         wall("pr-rules", t=ts(9 * 86400))]) + "\n")
    write(os.path.join(state, "gates.log"), "".join(
        "%s %s %s session=%s cmd=%s\n" % (ts(), kind, rule, sess, cmd) for kind, rule, sess, cmd in (
            ("DENY", "pr-rules", "s1", "gh pr create"), ("DENY", "pr-rules", "s1", "gh pr create"),
            ("DENY", "secret-scan", "s1", "git commit"), ("DENY", "pr-rules", "tmp-s", "gh pr create"),
            ("SKIP", "pr-rules", "s1", "gh pr create"))))


def squash(text):
    return re.sub(r"[ \t]+", " ", text)



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
    for prof in ("server", "dev-mac"):           # the routing table of each profile (ai-render --profile)
        out = os.path.join(work, "render-" + prof)
        subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-render"), "--profile", prof, "--out", out],
                       stdout=subprocess.DEVNULL, check=True)
        shutil.copy(os.path.join(out, "routing.json"), os.path.join(work, "routing-%s.json" % prof))
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
    env = {"HOME": home, "PATH": fake + os.pathsep + "/usr/bin:/bin", "LANG": "C.UTF-8",
           "HERMES_USER": "ai-test-no-such-user",      # a server has a real hermes user: never read it here
           "AI_PROFILE": "server", "AI_ROUTING_JSON": os.path.join(home, "..", "routing-server.json")}
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
