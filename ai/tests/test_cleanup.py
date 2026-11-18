#!/usr/bin/env python3
"""Tests for ticket 03 (cleanup of conflicts and noise, owner 2026-11-16): the short ~/.claude/CLAUDE.md (root rules
import, machine line, 3-line OMC note), the RTK hook wrapper that skips the rewrite in auto mode, and the ai-doctor
checks for the CLAUDE.md form, a bare RTK hook and a repo in the global autoMode.environment.
The router side (notifications are not owner prompts) lives in ai/tests/cases/ (feature-grill, merge-approval).
Fake rtk and claude on a closed PATH, a temp HOME. Nothing is written outside the temp dir.

Run: python3 ai/tests/test_cleanup.py   (bash ai/tests/run.sh runs it too)
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
sys.dont_write_bytecode = True
sys.path.insert(0, TESTS)
import test_m3 as m3  # noqa: E402

FAILS = []
WRAPPER = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks", "rtk-hook")
OMC_LONG = ("<!-- OMC:START -->\n<!-- OMC:VERSION:5.8.6 -->\n\n# oh-my-claudecode - Intelligent Multi-Agent "
            "Orchestration\n\nlong vendor text\n<!-- OMC:END -->\n\n")
NOTE = ["OMC and OMX are toolboxes.", "AGENTS.md and the gates win.", "Catalog: the omc-reference skill."]
FAKE_RTK = '#!/bin/sh\necho "rtk $*" >> "$FAKE_LOG"\ncat >> "$FAKE_LOG"\necho \'{"rewritten": true}\'\nexit 0\n'


def main():
    work = tempfile.mkdtemp(prefix="ai-cleanup-tests-")
    saved = {k: os.environ.get(k) for k in m3.ENV_KEYS}
    try:
        for test in (t_rtk_wrapper, t_rtk_install, t_rtk_managed, t_claude_md_short, t_claude_md_owner_text, t_claude_md_short_any_wiring, t_rtk_off_doctor_bare_hook,
                     t_rtk_off_install, t_rtk_off_doctor,
                     t_doctor_checks, t_doctor_owner_text):
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
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
        shutil.rmtree(work, ignore_errors=True)
    print("%d cleanup tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- tests

def t_rtk_wrapper(work):
    """Auto mode: no output, exit 0, rtk is not called. Any other mode: rtk hook claude gets the same stdin and its
    output is the hook output."""
    log = os.path.join(work, "log")
    rtk = os.path.join(work, "rtk")
    m3.stub(rtk, FAKE_RTK)
    env = dict(os.environ, FAKE_LOG=log)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"},
               "permission_mode": "auto"}
    res = run_wrapper(rtk, payload, env)
    assert res.returncode == 0 and res.stdout == b"" and not os.path.exists(log), res
    for mode in ("default", "acceptEdits", "plan", None):
        p = dict(payload, permission_mode=mode) if mode else {k: v for k, v in payload.items() if k != "permission_mode"}
        res = run_wrapper(rtk, p, env)
        assert res.returncode == 0 and b'"rewritten": true' in res.stdout, (mode, res)
        got = m3.read(log)
        assert got.startswith("rtk hook claude\n") and json.loads(got.split("\n", 1)[1]) == p, (mode, got)
        os.remove(log)


def t_rtk_install(work):
    """claude_rtk writes the wrapper as the PreToolUse Bash hook, drops the bare `rtk hook claude` of an older
    install, keeps other hooks, is idempotent, and undo puts the old hook back."""
    env, home, bindir = m3.claude_env(work)
    m3.stub(os.path.join(bindir, "rtk"), FAKE_RTK)
    env["FAKE_LOG"] = os.path.join(work, "rtk.log")
    settings = os.path.join(home, ".claude", "settings.json")
    other = {"matcher": "Edit", "hooks": [{"type": "command", "command": "/bin/echo other"}]}
    m3.write(settings, json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}, other]}}))
    code, out = m3.bash(m3.LIBS + "claude_rtk", env)
    assert code == 0, out
    cmds = hook_cmds(settings)
    want = '/usr/bin/python3 "%s" "%s"' % (WRAPPER, os.path.join(bindir, "rtk"))
    assert cmds == ["/bin/echo other", want], cmds
    assert not os.path.exists(env["FAKE_LOG"]), "no rtk init: it writes the bare hook back"
    before = m3.read(settings)
    code, out = m3.bash(m3.LIBS + "claude_rtk", env)
    assert code == 0 and m3.read(settings) == before, out
    code, out = m3.run_undo(env, home)
    assert code == 0 and "rtk hook claude" in hook_cmds(settings) and want not in hook_cmds(settings), \
        (out, hook_cmds(settings))


def t_rtk_managed(work):
    """Server: the managed RTK hook is the wrapper from the root-owned copy, with the absolute rtk."""
    env, home, bindir = m3.env_for(work)
    code, out = m3.bash(m3.LIBS + "AI_ROOT_REPO=/usr/local/lib/ai/repo; claude_managed_hooks /usr/local/bin/rtk", env)
    assert code == 0, out
    cmds = [h["command"] for g in json.loads(out)["PreToolUse"] for h in g["hooks"]]
    want = '/usr/bin/python3 "/usr/local/lib/ai/repo/ai/marketplace/plugins/ai-core/hooks/rtk-hook" "/usr/local/bin/rtk"'
    assert want in cmds and not any(c.endswith("rtk hook claude") for c in cmds), cmds


def t_claude_md_short(work):
    """The rules step leaves ~/.claude/CLAUDE.md as the root rules import, the machine line and the 3-line OMC note;
    OMC's long block goes (recorded); a second run changes nothing; undo puts the OMC block back.
    The step parts run one by one: base_rules_user stops early when ai/AGENTS.md is not built in this checkout."""
    env, home, bindir = m3.claude_env(work)
    env["AI_PROJECTS_DIR"] = "~/work"
    md = os.path.join(home, ".claude", "CLAUDE.md")
    m3.write(md, OMC_LONG + "<!-- AI:core v1 START -->\n@~/.config/ai/AGENTS.md\n<!-- AI:core v1 END -->\n")
    want = 'want() { [ "$1" = claude ]; }; claude_omc_note; base_host_block'
    src = m3.read(os.path.join(AI_DIR, "adapters", "base.sh"))
    assert "claude_omc_note\n" in src.split("base_rules_user() {", 1)[1].split("\n}\n", 1)[0], "the step calls it"
    code, out = m3.bash(m3.LIBS + want, env)
    assert code == 0, out
    text = m3.read(md)
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("<!-- AI:")]
    machine = [ln for ln in lines if ln.startswith("This machine: projects live in ~/work")]
    assert len(machine) == 1 and sorted(lines) == sorted(["@~/.config/ai/AGENTS.md"] + machine + NOTE), text
    assert "OMC:START" not in text and "long vendor text" not in text, text
    code, out = m3.bash(m3.LIBS + want, env)
    assert code == 0 and m3.read(md) == text, out
    code, out = m3.run_undo(env, home)
    assert code == 0 and "long vendor text" in m3.read(md) and NOTE[0] not in m3.read(md), (out, m3.read(md))


def t_claude_md_owner_text(work):
    """An old OMC CLI block (version 4.x, owner text before and after it) goes; every owner line stays unchanged."""
    env, home, bindir = m3.claude_env(work)
    md = os.path.join(home, ".claude", "CLAUDE.md")
    mine = ["# My rules", "never run `rtk init -g`", "## RTK (all projects)", "ALWAYS prefix commands with `rtk`"]
    old = "<!-- OMC:START -->\n<!-- OMC:VERSION:4.15.7 -->\n\n# oh-my-claudecode\n\nold vendor text\n<!-- OMC:END -->\n"
    m3.write(md, mine[0] + "\n" + mine[1] + "\n\n" + old + "\n" + mine[2] + "\n" + mine[3] + "\n")
    code, out = m3.bash(m3.LIBS + 'want() { [ "$1" = claude ]; }; claude_omc_note', env)
    text = m3.read(md)
    assert code == 0 and "OMC:" not in text and "old vendor text" not in text, (out, text)
    assert [ln for ln in text.splitlines() if ln in mine] == mine and NOTE[0] in text, text


def t_claude_md_short_any_wiring(work):
    """QA 2026-11-17: the root rules step writes the OMC note on every OMC wiring (plugin and npm CLI), also over an
    old CLI block; owner text outside our blocks stays; undo puts the vendor block back. A temp AI_HOME with a
    built ai/AGENTS.md: base_rules_user stops early without one."""
    mine = ["# My rules", "keep this line"]
    for wiring in ("plugin", "cli"):
        env, home, bindir = m3.claude_env(os.path.join(work, wiring))
        fake_home = os.path.join(work, wiring, "ai-home")
        m3.write(os.path.join(fake_home, "ai", "AGENTS.md"), "# rules\n")
        os.symlink(os.path.join(AI_DIR, "lib"), os.path.join(fake_home, "ai", "lib"))
        env["AI_OMC_WIRING"] = wiring
        md = os.path.join(home, ".claude", "CLAUDE.md")
        m3.write(md, mine[0] + "\n" + OMC_LONG + mine[1] + "\n")
        code, out = m3.bash(m3.LIBS + 'AI_HOME=%s; want() { [ "$1" = claude ]; }; base_rules_user' % fake_home, env)
        text = m3.read(md)
        assert code == 0 and "OMC:START" not in text and all(n in text for n in NOTE), (wiring, out, text)
        assert [ln for ln in text.splitlines() if ln in mine] == mine, (wiring, text)
        code, out = m3.run_undo(env, home)
        assert code == 0 and "long vendor text" in m3.read(md), (wiring, out, m3.read(md))


def t_rtk_off_install(work):
    """AI_RTK_HOOK=off (or "off" in ~/.config/ai/rtk-hook): claude_rtk writes no hook and removes nothing."""
    env, home, bindir = m3.claude_env(work)
    m3.stub(os.path.join(bindir, "rtk"), FAKE_RTK)
    settings = os.path.join(home, ".claude", "settings.json")
    other = {"matcher": "Edit", "hooks": [{"type": "command", "command": "/bin/echo other"}]}
    m3.write(settings, json.dumps({"hooks": {"PreToolUse": [other]}}))
    before = m3.read(settings)
    env["AI_RTK_HOOK"] = "off"
    code, out = m3.bash(m3.LIBS + "claude_rtk", env)
    assert code == 0 and m3.read(settings) == before and "off by owner choice" in out, out
    del env["AI_RTK_HOOK"]
    m3.write(os.path.join(home, ".config", "ai", "rtk-hook"), "off\n")
    code, out = m3.bash(m3.LIBS + "claude_rtk", env)
    assert code == 0 and m3.read(settings) == before, out


def t_rtk_off_doctor(work):
    """With the switch off and no RTK hook, ai-doctor says PASS; without the switch it still FAILs for a bare hook."""
    env, home, bindir = m3.claude_env(work)
    m3.write(os.path.join(home, ".claude", "settings.json"), json.dumps({"hooks": {}}))
    m3.write(os.path.join(home, ".config", "ai", "rtk-hook"), "off\n")
    assert line_of(doctor_out(env), "RTK hook").startswith("PASS"), doctor_out(env)
    assert "manual rtk" in line_of(doctor_out(env), "RTK hook")


def t_rtk_off_doctor_bare_hook(work):
    """QA 2026-11-17: the switch is off and the owner's own bare `rtk hook claude` stays (the installer removes
    nothing then): ai-doctor said FAIL. The switch wins, from the file (first line) or from AI_RTK_HOOK=off."""
    env, home, bindir = m3.claude_env(work)
    m3.write(os.path.join(home, ".claude", "settings.json"), json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]}}))
    assert line_of(doctor_out(env), "RTK hook").startswith("FAIL"), "control: no switch, bare hook"
    m3.write(os.path.join(home, ".config", "ai", "rtk-hook"), "off\n# manual rtk, OMC hooks conflict\n")
    assert line_of(doctor_out(env), "RTK hook").startswith("PASS"), doctor_out(env)
    os.remove(os.path.join(home, ".config", "ai", "rtk-hook"))
    os.environ["AI_RTK_HOOK"] = "off"
    try:
        out = doctor_out(env)
    finally:
        del os.environ["AI_RTK_HOOK"]
    assert line_of(out, "RTK hook").startswith("PASS"), out


def t_doctor_checks(work):
    """ai-doctor: FAIL when OMC's long block is back in ~/.claude/CLAUDE.md, PASS for the short form; FAIL for a
    bare `rtk hook claude` in settings.json; WARN when the global autoMode.environment names a repo path or a
    trusted repo (with the fix), PASS for organisation-wide entries."""
    env, home, bindir = m3.claude_env(work)
    md = os.path.join(home, ".claude", "CLAUDE.md")
    settings = os.path.join(home, ".claude", "settings.json")
    short = ("<!-- AI:core v1 START -->\n@~/.config/ai/AGENTS.md\n<!-- AI:core v1 END -->\n"
             "<!-- AI:omc v1 START -->\n%s\n<!-- AI:omc v1 END -->\n" % "\n".join(NOTE))
    m3.write(md, OMC_LONG + short)
    m3.write(settings, json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]},
        "autoMode": {"environment": ["$defaults", "Trusted repo: ~/work/example-app, push to its origin is fine"]}}))
    out = doctor_out(env)
    assert line_of(out, "CLAUDE.md").startswith("FAIL") and "install.sh" in line_of(out, "CLAUDE.md"), out
    assert line_of(out, "RTK hook").startswith("FAIL"), out
    auto = line_of(out, "autoMode.environment")
    assert auto.startswith("WARN") and ".claude/settings.local.json" in auto and "~/work/example-app" in auto, out
    # Ticket 12: a WARN or FAIL title states the problem, not the pass condition.
    assert "names one repo" in auto and "names no single repo" not in auto, auto
    assert "has OMC's long block" in line_of(out, "CLAUDE.md"), out
    # The exact move steps: which key in which file, in order (owner 2026-11-16: the file is not rewritten).
    for step in ("1. in %s" % settings, "remove", "2. in the repo", "add", '"$defaults"', "3."):
        assert step in auto, (step, auto)
    m3.write(md, short)
    m3.write(settings, json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": '/usr/bin/python3 "%s" rtk' % WRAPPER}]}]},
        "autoMode": {"environment": ["$defaults", "Source control: github.example.com/acme and all repos under it"]}}))
    out = doctor_out(env)
    for what in ("CLAUDE.md", "RTK hook", "autoMode.environment"):
        assert line_of(out, what).startswith("PASS"), (what, out)
    assert "names no single repo" in line_of(out, "autoMode.environment"), out
    assert "is short (rules import" in line_of(out, "CLAUDE.md"), out


def t_doctor_owner_text(work):
    """Owner text outside our blocks is a WARN, never a FAIL; the OMC long block (old 4.x style too) is a FAIL."""
    env, home, bindir = m3.claude_env(work)
    md = os.path.join(home, ".claude", "CLAUDE.md")
    short = "<!-- AI:core v1 START -->\n@~/.config/ai/AGENTS.md\n<!-- AI:core v1 END -->\n"
    m3.write(md, "## RTK (all projects)\nowner text\n" + short)
    warn = line_of(doctor_out(env), "CLAUDE.md")
    assert warn.startswith("WARN") and "has text outside the managed blocks" in warn and "is short" not in warn, warn
    m3.write(md, "<!-- OMC:START -->\n<!-- OMC:VERSION:4.15.7 -->\nold\n<!-- OMC:END -->\n## RTK\nowner text\n" + short)
    assert line_of(doctor_out(env), "CLAUDE.md").startswith("FAIL")


# ---------------------------------------------------------------- helpers

def run_wrapper(rtk, payload, env):
    return subprocess.run([sys.executable, WRAPPER, rtk], input=json.dumps(payload).encode(), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def hook_cmds(settings):
    data = m3.jload(settings)
    return [h["command"] for gs in (data.get("hooks") or {}).values() for g in gs for h in g["hooks"]]


def doctor_out(env):
    mod = m3.load_doctor(env)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.check_claude_cleanup()
    return buf.getvalue()


def line_of(out, needle):
    """The check line that names NEEDLE, with its detail line (ai-doctor prints the detail below)."""
    lines = out.splitlines() + [""]
    return next((ln + " " + lines[i + 1] for i, ln in enumerate(lines[:-1]) if needle in ln), "")


if __name__ == "__main__":
    sys.exit(main())
