#!/usr/bin/env python3
"""ai-core router: one entry point for every hook event (Claude Code and Codex).

Usage (from hooks.json):  python3 router.py --agent claude|codex <EventName>  < hook JSON

It reads only ai/build/routing.json (rendered from ai/routing.yaml by ai-render).
Matching is deterministic: regex, globs and project state. No LLM, no network.
Python stdlib only, so the hook starts fast.

What each event does:
  SessionStart         L1: inject the L0 table + session_start rules whose state matches.
  UserPromptSubmit     L3 regex on the prompt; if a rule or a tie-break matched, L2 forced-eval text.
  PreToolUse           L4 gates (deny or ask) and context nudges (quiet windows, log-only rules).
  PostToolUse          nudges after edits/commands, docs lookups, Skill proof.
  UserPromptExpansion  Skill proof for a typed /skill.
  Stop                 miss log (rule fired, no matching tool or skill call), then claude-notify.
  SessionEnd           drop the session state file.

Never breaks a session: an internal error is logged to router-errors.log and the hook exits 0.
A gate decision made before an error is still sent; logging never raises (an unwritable state dir
does not lose a deny). Shell parsing and the gates live in hooklib.py; known limits in README.md.
Codex: deny also carries {"decision": "block"}; Codex has no "ask", so ask becomes deny there.
Agent = --agent, else Codex when the payload has turn_id / tool_use_id.
"""
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True      # no __pycache__ inside the (possibly read-only) plugin dir
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from hooklib import (GATES, GATE_PROBES, ai_home, append_jsonl, command_text, gate_skips,  # noqa: E402
                     iso_now, knowledge_delta, knowledge_index, libs_hits, log_error, log_line, one_line,
                     origin_slug, parse_command, prompt_libs, redact, project_root, read_text, repo_symbol,
                     state_path)

HOOK_DIR = os.path.dirname(os.path.realpath(__file__))
CONTEXT_CAP = 9500          # additionalContext is cut here (hook output caps: Claude 10,000 chars, Codex ~2,500 tokens)
PLACEHOLDER_MAX = {"knowledge_index": 600}   # worst-case length of a placeholder value (ai-render budget)
L0_RESEND_SOURCES = ("compact", "clear")    # SessionStart sources that get the L0 table again
L1_HEADER = "[ai router L1] Routing table (also in your root rules; re-sent after compaction):\n"
DAY = 86400
CODEX_HINTS = ("turn_id", "tool_use_id")
CODE_EXT = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".kts",
    ".rb", ".php", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".swift", ".scala", ".sh", ".bash",
    ".zsh", ".lua", ".vue", ".svelte", ".ex", ".exs", ".dart", ".m", ".mm", ".sql", ".r", ".jl", ".zig",
    ".erl", ".clj", ".fs", ".ml", ".hs", ".pl", ".ps1", ".tf",
}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__",
             ".tox", ".mypy_cache", ".next", "vendor", ".serena", "graphify-out"}


# ---------------------------------------------------------------- entry point

def main(argv):
    agent, event = parse_args(argv)
    if "--managed" not in argv and (agent or "claude") == "claude" and plugin_copy() and managed_router_present():
        # Linux server installs run this router from the root-owned copy as a managed hook (managed-settings
        # hooks, "--managed"). The plugin copy in ~/.claude/plugins/cache is user-writable, so it steps aside:
        # the gates never depend on a file the user (or anything running as the user) can change.
        return 0
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    event = event or payload.get("hook_event_name", "")
    if agent is None:
        agent = "codex" if any(k in payload for k in CODEX_HINTS) else "claude"
    ctx = Ctx(agent, event, payload, raw)
    handler = HANDLERS.get(event)
    if handler is None:
        return 0
    try:
        handler(ctx)
    except Exception as exc:  # never break the session; a decision made before the error still counts
        log_error(event, exc)
    try:
        return ctx.finish()
    except Exception as exc:
        log_error("finish", exc)
        return 0


def plugin_copy():
    """True when Claude runs this file from its plugin copy (it sets CLAUDE_PLUGIN_ROOT for plugin hooks)."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or ""
    here = os.path.realpath(os.path.abspath(__file__))
    return bool(root) and here.startswith(os.path.realpath(root) + os.sep)


def managed_router_present():
    try:
        with open(MANAGED_SETTINGS) as f:
            hooks = json.load(f).get("hooks") or {}
    except (OSError, ValueError, AttributeError):
        return False
    return "router.py" in json.dumps(hooks) and "--managed" in json.dumps(hooks)


def parse_args(argv):
    agent, event = None, ""
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--managed":
            continue
        if a == "--agent" and args:
            agent = args.pop(0)
        elif a.startswith("--agent="):
            agent = a.split("=", 1)[1]
        else:
            event = a
    return agent, event


# ---------------------------------------------------------------- event handlers

# A Claude session started in the home folder: the sandbox would let commands write the whole home (PATH
# folders, shell start-up files, agent config), and project files are mixed with everything else. Refused:
# a hard warning at start, and every command or edit is denied until Claude runs inside a project folder.
HOME_MSG = ("This Claude session started in the home folder (%s). Start Claude inside a project folder "
            "instead: cd <project folder>; claude. Do not run commands or edit files here; tell the user this.")
HOME_TOOLS = {"Bash", "Edit", "Write", "MultiEdit", "NotebookEdit"}


def session_in_home(ctx):
    if ctx.agent != "claude":
        return ""
    home = os.environ.get("HOME") or ""
    cwd = str(ctx.payload.get("cwd") or "")
    if not home or not cwd:
        return ""
    try:
        same = os.path.realpath(cwd) == os.path.realpath(home)
    except OSError:
        return ""
    return home if same else ""


def on_session_start(ctx):
    rotate_logs()
    prune_sessions()
    routing = ctx.routing
    parts = []
    home = session_in_home(ctx)
    if home:
        parts.append("[ai router: home-folder] STOP. " + HOME_MSG % home)
    # Status lines first. The L0 table only after compact or clear (owner decision 2026-11-12): at startup and
    # resume it is already in the root rules (CLAUDE.md, Codex AGENTS.md), so sending it again only costs
    # tokens. A cut at CONTEXT_CAP loses only the table tail. ai-render checks the budget.
    for rule in rules_for(routing, "session_start"):
        if not rule_enabled(rule, ctx):
            continue
        state = rule.get("trigger", {}).get("state")
        if state and not check_state(state, ctx):
            continue
        text = render_action(rule, ctx)
        if not text:
            continue
        parts.append("[ai router: %s] %s" % (rule["id"], text))
        ctx.fired(rule, "SessionStart")
    resend = str(ctx.payload.get("source") or "") in L0_RESEND_SOURCES
    if resend and (routing.get("layers", {}).get("L1_session_start") is not None or routing.get("rules")):
        l0 = read_text(first_existing(l0_candidates()))
        if l0:
            parts.append(L1_HEADER + l0.strip())
    if parts:
        ctx.add_context("\n\n".join(parts))


EXPLICIT_DOCS = re.compile(r"\b(docs|documentation|api reference|changelog|release notes)\b", re.I)


def on_user_prompt(ctx):
    prompt = ctx.payload.get("prompt") or ""
    if not prompt.strip():
        return
    routing = ctx.routing
    matched = []
    for rule in routing.get("rules", []):
        trig = rule.get("trigger", {})
        rx = trig.get("prompt")
        if not rx:
            continue
        if not search(rx, prompt):
            if not trig.get("prompt_libs") or not ctx.prompt_libs(prompt):
                continue
        if not rule_enabled(rule, ctx):
            continue
        state = rule["trigger"].get("state")
        if state and not check_state(state, ctx):
            continue
        if rule["id"] == "docs-lookup" and not EXPLICIT_DOCS.search(prompt) and repo_symbol(prompt, ctx.root):
            continue        # the prompt is about code in this repo (Fable readiness: a false docs nudge)
        matched.append(rule)
    ties = match_tiebreaks(routing.get("tiebreaks", []), prompt)
    if not matched and not ties:
        return
    actions = []
    for rule in matched:
        text = render_action(rule, ctx)
        if text:
            actions.append((rule, text))
    if not actions and not ties:
        return
    for rule, _text in actions:
        ctx.fired(rule, "UserPromptSubmit")
    ctx.add_context(render_prompt_context(routing, actions, ties))


def on_pre_tool(ctx):
    tool = ctx.payload.get("tool_name") or ""
    tin = tool_input(ctx.payload)
    cmd = command_of(tin)
    ctx.set_command(cmd)
    home = session_in_home(ctx)
    if home and tool in HOME_TOOLS:
        ctx.decide("deny", "[ai router: home-folder] " + HOME_MSG % home)
        return
    for rule in ctx.routing.get("rules", []):
        trig = rule.get("trigger", {})
        if not trig.get("tool_before") or not tool_matches(trig["tool_before"], tool):
            continue
        if not rule_enabled(rule, ctx):
            continue
        if rule.get("strength") == "gate":
            probe = GATE_PROBES.get(rule["id"])
            if cmd and (conditions_match(rule, tool, tin, cmd, ctx) or (probe and probe(ctx.stages, cmd))):
                run_gate(rule, ctx, cmd)
            continue
        if not conditions_match(rule, tool, tin, cmd, ctx):
            continue
        text = render_action(rule, ctx)
        if text and ctx.state.allow_nudge(rule, nudge_key(rule, tool, tin, cmd)):
            ctx.fired(rule, "PreToolUse")
            ctx.add_context("[ai router: %s] %s" % (rule["id"], text))
    abs_rewrite(ctx, tool, tin, cmd)


# The commands that leave the sandbox (managed sandbox.excludedCommands, written by install.sh as absolute
# paths of root-owned programs) get that absolute path, so a copy planted on PATH is never the one that runs:
# `git push ...` becomes `/usr/bin/git push ...` and so on. Only an exact single command is rewritten (no
# operators, redirection or substitution); everything else is left alone and stays sandboxed. Box work is
# not rewritten: it goes through the box MCP tools (the no-sudo gate says so).
MANAGED_SETTINGS = os.environ.get("AI_CLAUDE_MANAGED_SETTINGS") or "/etc/claude-code/managed-settings.json"
SAFE_ARGS = r"((?:\s+[^;&|<>`$()\\\n]+)?)\s*"


READ_ONLY_WORDS = {"view", "list", "diff", "checks"}


def excluded_programs():
    try:
        with open(MANAGED_SETTINGS) as f:
            entries = (json.load(f).get("sandbox") or {}).get("excludedCommands") or []
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for e in entries:
        parts = str(e).split()
        if len(parts) >= 2 and parts[0].startswith("/") and parts[-1] == "*":
            out.append((parts[0], parts[1:-1]))
    return out


def abs_rewrite(ctx, tool, tin, cmd):
    if ctx.agent != "claude" or tool != "Bash" or not cmd or ctx.decision is not None:
        return
    for prog, words in excluded_programs():
        # `rtk git push` / `rtk proxy gh pr view` too: rtk would run the program from PATH inside the sandbox.
        rx = (r"\s*(?:rtk\s+(?:proxy\s+)?)?" + re.escape(os.path.basename(prog))
              + "".join(r"\s+" + re.escape(w) for w in words) + SAFE_ARGS)
        m = re.fullmatch(rx, cmd)
        if m and os.path.isfile(prog):
            ctx.updated_input = dict(tin, command=" ".join([prog] + words) + m.group(1).rstrip())
            # Read-only gh forms run unattended (they are on the allow list); git push, gh pr create/edit ask.
            kind = "allow" if words and words[-1] in READ_ONLY_WORDS and os.path.basename(prog) == "gh" else "ask"
            ctx.updated_decision = (kind, "runs outside the sandbox: absolute path of the root-owned program, "
                                          "not a copy found on PATH")
            return


def on_post_tool(ctx):
    tool = ctx.payload.get("tool_name") or ""
    tin = tool_input(ctx.payload)
    cmd = command_of(tin)
    ctx.set_command(cmd)
    if tool == "Skill":
        name = tin.get("skill") or tin.get("name") or tin.get("command") or ""
        if name:
            append_jsonl("fired.jsonl", ctx.row(kind="skill", via="tool", skill=name))
    if is_docs_tool(tool):
        log_docs_ids(ctx, tool, tin)
    for rule in ctx.routing.get("rules", []):
        trig = rule.get("trigger", {})
        if not trig.get("tool_after") or not tool_matches(trig["tool_after"], tool):
            continue
        if not rule_enabled(rule, ctx) or not conditions_match(rule, tool, tin, cmd, ctx):
            continue
        if trig.get("content"):
            hits = content_hits(trig["content"], tin)
            text = render_action(rule, ctx) if hits else ""
            if text:
                ctx.fired(rule, "PostToolUse")
                ctx.add_context("[ai router: %s] %s (%s, %d line(s))" % (
                    rule["id"], text, file_of(tin) or "edited text", hits))
            continue
        text = render_action(rule, ctx)
        if text and ctx.state.allow_nudge(rule, nudge_key(rule, tool, tin, cmd)):
            ctx.fired(rule, "PostToolUse")
            ctx.add_context("[ai router: %s] %s" % (rule["id"], text))


def on_prompt_expansion(ctx):
    name = ctx.payload.get("command_name") or ctx.payload.get("skill") or ""
    if name:
        append_jsonl("fired.jsonl", ctx.row(kind="skill", via="expansion", skill=name))


def on_stop(ctx):
    if not ctx.payload.get("stop_hook_active"):
        check_misses(ctx)
    run_notify(ctx)


def on_session_end(ctx):
    ctx.state.drop()


HANDLERS = {
    "SessionStart": on_session_start,
    "UserPromptSubmit": on_user_prompt,
    "PreToolUse": on_pre_tool,
    "PostToolUse": on_post_tool,
    "UserPromptExpansion": on_prompt_expansion,
    "Stop": on_stop,
    "SessionEnd": on_session_end,
}


# ---------------------------------------------------------------- context object and output

class Ctx(object):
    def __init__(self, agent, event, payload, raw):
        self.agent = agent
        self.event = event
        self.payload = payload
        self.raw = raw
        self.cwd = payload.get("cwd") or os.getcwd()
        self.session = str(payload.get("session_id") or "nosession")
        self.contexts = []
        self.decision = None      # None | "ask" | "deny"
        self.reasons = []
        self._routing = None
        self._state = None
        self._root = False
        self.stages = []          # parsed shell stages of the Bash command (hooklib.parse_command)
        self.cmd_text = ""        # the command with quoted words removed, for rule regexes
        self.skips = ({}, [])
        self.named_libs = None    # libraries named by the prompt or the dependency change ({libs_hits})
        self.updated_input = None  # PreToolUse rewrite to an absolute program path (abs_rewrite)
        self.updated_decision = ("allow", "")
        self._prompt_libs = None

    def prompt_libs(self, prompt):
        if self._prompt_libs is None:
            try:
                self._prompt_libs = prompt_libs(prompt, self.root)
            except Exception as exc:
                log_error("prompt_libs", exc)
                self._prompt_libs = set()
            if self.named_libs is None:
                self.named_libs = set(self._prompt_libs)
        return self._prompt_libs

    def set_command(self, cmd):
        if cmd:
            self.stages = parse_command(cmd)
            self.cmd_text = command_text(self.stages)
            self.skips = gate_skips(self.stages)

    @property
    def routing(self):
        if self._routing is None:
            self._routing = load_routing()
        return self._routing

    @property
    def state(self):
        if self._state is None:
            self._state = SessionState(self.session)
        return self._state

    @property
    def root(self):
        if self._root is False:
            self._root = project_root(self.cwd)
        return self._root

    def add_context(self, text):
        self.contexts.append(text)

    def decide(self, decision, reason):
        order = {None: 0, "ask": 1, "deny": 2}
        if order[decision] > order[self.decision]:
            self.decision = decision
        self.reasons.append(reason)

    def row(self, **kw):
        base = {"ts": iso_now(), "session": self.session, "agent": self.agent, "cwd": self.cwd}
        base.update(kw)
        return base

    def fired(self, rule, event, log_only=False):
        append_jsonl("fired.jsonl", self.row(kind="rule", rule=rule["id"], event=event, log_only=log_only))
        if rule.get("proof") and not log_only:
            self.state.add_pending(rule["id"], rule["proof"], self.payload.get("transcript_path"))

    def finish(self):
        if self._state is not None:
            try:
                self._state.save()
            except Exception as exc:
                log_error("state save", exc)
        if self.decision == "ask" and self.agent == "codex":
            # Codex has no ask prompt (an "ask" output fails and the tool runs): deny with a clear message.
            self.decision = "deny"
            self.reasons.append("Codex cannot ask the owner. Stop and ask the owner; only the owner can let it "
                                "through: sudo ai-gate-skip <gate> <minutes> <why>.")
        if self.decision == "deny":
            reason = "\n".join(self.reasons)
            # Codex (shape used by the audited oh-my-codex 0.22.6 hooks) also reads decision/reason.
            top = {"decision": "block", "reason": reason} if self.agent == "codex" else {}
            self.emit({"permissionDecision": "deny", "permissionDecisionReason": reason}, top)
            return 0
        if self.decision == "ask":
            self.emit({"permissionDecision": "ask", "permissionDecisionReason": "\n".join(self.reasons)})
            return 0
        if self.updated_input is not None:
            kind, why = self.updated_decision
            self.emit({"permissionDecision": kind, "updatedInput": self.updated_input, "permissionDecisionReason": why})
            return 0
        if self.contexts:
            self.emit({})
        return 0

    def emit(self, extra, top=None):
        out = {"hookEventName": self.event}
        out.update(extra)
        if self.contexts:
            out["additionalContext"] = "\n\n".join(self.contexts)[:CONTEXT_CAP]
        doc = dict(top or {})
        doc["hookSpecificOutput"] = out
        sys.stdout.write(json.dumps(doc) + "\n")


# ---------------------------------------------------------------- prompt rendering (L2 / L3)

def render_prompt_context(routing, matched, ties):
    layers = routing.get("layers", {})
    forced = layers.get("L2_forced_eval", {}).get("enabled", True)
    none_ok = layers.get("L2_forced_eval", {}).get("none_option", True)
    lines = []
    if forced:
        lines.append("[ai router L2] Before you act, answer YES or NO for each item in one short line, "
                     "then use every YES tool first."
                     + (' If nothing fits, answer "none needed".' if none_ok else ""))
    else:
        lines.append("[ai router L3]")
    for rule, text in matched:
        lines.append("- %s: %s" % (rule["id"], text))
    for tb in ties:
        lines.append("- tie-break (%s): use %s, not %s." % (tb["trigger"], tb["winner"], tb["loser"]))
    return "\n".join(lines)


def match_tiebreaks(tiebreaks, prompt):
    hits = []
    for tb in tiebreaks:
        rx = tb.get("match")
        if not rx or not search(rx, prompt):
            continue
        mirror = [h for h in hits if h["winner"] == tb["loser"] and h["loser"] == tb["winner"]]
        if mirror:      # the earlier, more specific row already decided this pair
            continue
        hits.append(tb)
    return hits


# ---------------------------------------------------------------- conditions

def tool_matches(pattern, tool):
    try:
        return re.fullmatch(pattern, tool) is not None
    except re.error:
        return tool in pattern.split("|")


def conditions_match(rule, tool, tin, cmd, ctx):
    """Rules combine tool + command + paths. Semantics:
    - command applies to tools that carry a shell command (Bash); other tools skip it.
    - paths globs apply to file tools only (Bash relies on command).
    - a tool without a command and without a file path passes (e.g. Agent for prompting-others).
    """
    trig = rule.get("trigger", {})
    paths = trig.get("paths")
    if cmd:
        if trig.get("command") and not search(trig["command"], ctx.cmd_text or cmd):
            return False
        return True
    if trig.get("command") and tool in ("Bash", "shell", "exec_command", "local_shell"):
        return False
    fpath = file_of(tin)
    if paths:
        return bool(fpath) and glob_match(paths, fpath, ctx.cwd)
    return True


def is_code_path(path):
    return os.path.splitext(path.rstrip("/:"))[1].lower() in CODE_EXT


def glob_match(globs, path, cwd):
    from fnmatch import fnmatch
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    base = os.path.basename(full)
    for g in expand_braces(globs):
        g = g.strip()
        if not g:
            continue
        tail = g[3:] if g.startswith("**/") else g
        if fnmatch(full, "*/" + tail) or fnmatch(base, tail) or fnmatch(full, g):
            return True
    return False


def expand_braces(globs):
    out = []
    for g in globs.split("|"):
        m = re.search(r"\{([^}]*)\}", g)
        if m:
            for alt in m.group(1).split(","):
                out.extend(expand_braces(g[:m.start()] + alt + g[m.end():]))
        else:
            out.append(g)
    return out


def content_hits(needle, tin):
    texts = []
    for key in ("content", "new_string", "new_source"):
        if isinstance(tin.get(key), str):
            texts.append(tin[key])
    for edit in tin.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            texts.append(edit["new_string"])
    return sum(1 for t in texts for line in t.splitlines() if needle in line)


def nudge_key(rule, tool, tin, cmd):
    """once_per: session = one nudge per session (until reset_on); default = once per file."""
    if rule.get("once_per") == "session":
        return rule["id"]
    return file_of(tin) or rule["id"]


# ---------------------------------------------------------------- project state

def has_code_files(root, limit=4000):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            seen += 1
            if is_code_path(f):
                return True
            if seen >= limit:
                return False
    return False


def playwright_enabled(root):
    if root and project_plugin_enabled(root, "ai-playwright@ai"):
        return True
    for rel in (".mcp.json", ".codex/config.toml", ".claude/settings.json"):
        text = read_text(os.path.join(root, rel))
        if text and "playwright" in text.lower():
            return True
    return False


def enabled_tools(root):
    text = read_text(os.path.join(root, ".ai", "enabled")) if root else ""
    return {ln.split("#", 1)[0].strip().lower() for ln in (text or "").splitlines() if ln.split("#", 1)[0].strip()}


# Claude-only skill packs, opt-in per project (owner decision 2026-11-12: about 12k tokens per session each).
# ON for a project: .ai/enabled lists the short id or the tool, or the project's .claude/settings.json /
# settings.local.json has enabledPlugins[<plugin id>] = true. Other agents never load them as plugins:
# they read the skill files on demand, so for them the packs count as ON everywhere.
CLAUDE_PACKS = {"claude-seo": ("seo", "claude-seo@agricidaniel-claude-seo"),
                "claude-blog": ("blog", "claude-blog@agricidaniel-blog")}


def project_plugin_enabled(root, plugin_id):
    on = None
    for rel in (".claude/settings.json", ".claude/settings.local.json"):     # local wins
        try:
            data = json.loads(read_text(os.path.join(root, rel)) or "{}")
        except ValueError:
            continue
        val = (data.get("enabledPlugins") or {}).get(plugin_id) if isinstance(data, dict) else None
        if isinstance(val, bool):
            on = val
    return bool(on)


def pack_enabled(tool, ctx):
    short, plugin_id = CLAUDE_PACKS[tool]
    if ctx.agent != "claude":
        return True
    if ctx.root is None:
        return False
    names = enabled_tools(ctx.root)
    return short in names or tool in names or project_plugin_enabled(ctx.root, plugin_id)


# Opt-in plugins of our own marketplace: ON when the project enables them (ai-adopt --tools serena writes it).
PROJECT_PLUGINS = {"serena": "ai-serena@ai", "browser": "ai-playwright@ai"}


def rule_enabled(rule, ctx):
    if rule.get("scope", "global") != "opt-in":
        return True
    tool = str(rule.get("tool", "")).lower()
    if tool in CLAUDE_PACKS:
        return pack_enabled(tool, ctx)
    if ctx.root is None:
        return False
    names = enabled_tools(ctx.root)
    if rule["id"].lower() in names or tool in names:
        return True
    pid = PROJECT_PLUGINS.get(rule["id"].lower())
    if pid and ctx.agent == "claude" and project_plugin_enabled(ctx.root, pid):
        return True
    return rule["id"] == "browser" and playwright_enabled(ctx.root)


def _state_no_base(ctx):
    return ctx.root is not None and not os.path.exists(os.path.join(ctx.root, ".ai", "base-version"))


def _state_no_playwright(ctx):
    return not playwright_enabled(ctx.root or ctx.cwd)


def _state_no_seo(ctx):
    return not pack_enabled("claude-seo", ctx)


def _state_no_blog(ctx):
    return not pack_enabled("claude-blog", ctx)


def _state_code_repo(ctx):
    return ctx.root is not None and ctx.state.has_code(ctx.root)


# routing.yaml `state:` strings -> predicates. ai-render fails on a state string not listed here.
STATE_PREDICATES = {
    "git repo without .ai/base-version": _state_no_base,
    "project without Playwright MCP": _state_no_playwright,
    "git repo with code": _state_code_repo,
    "project without claude-seo": _state_no_seo,
    "project without claude-blog": _state_no_blog,
}


def check_state(name, ctx):
    pred = STATE_PREDICATES.get(name)
    return bool(pred and pred(ctx))


# ---------------------------------------------------------------- action placeholders
# routing.yaml actions may hold {name}; the router fills them at fire time. Each value is a full phrase with
# its own label, or "" (then it disappears). An action that renders to empty text sends no message.

def _ph_knowledge_index(ctx):
    return knowledge_index(ctx.root)


def _ph_knowledge_delta(ctx):
    if ctx.event != "PostToolUse" or not commit_succeeded(ctx):
        return ""
    return knowledge_delta(ctx.root, bool(ctx.state.load().get("docs_ids_new")))


def _ph_libs_hits(ctx):
    if ctx.named_libs is None and ctx.event == "UserPromptSubmit":
        ctx.prompt_libs(ctx.payload.get("prompt") or "")
    return libs_hits(ctx.root, ctx.named_libs or ())


def _ph_origin_slug(ctx):
    return origin_slug(ctx.root)


def _ph_claude_handoff(ctx):
    return claude_handoff(ctx.agent)


PLACEHOLDERS = {
    "knowledge_index": _ph_knowledge_index,
    "knowledge_delta": _ph_knowledge_delta,
    "libs_hits": _ph_libs_hits,
    "origin_slug": _ph_origin_slug,
    "claude_handoff": _ph_claude_handoff,
}
PLACEHOLDER_RX = re.compile(r"\{([a-z_]+)\}")


def render_action(rule, ctx):
    """The rule action with placeholders filled; "" when nothing is left to say."""
    action = rule.get("action") or ""
    if "{" not in action:
        return action

    def fill(m):
        fn = PLACEHOLDERS.get(m.group(1))
        if fn is None:
            return m.group(0)
        try:
            return fn(ctx) or ""
        except Exception as exc:
            log_error("placeholder " + m.group(1), exc)
            return ""
    return re.sub(r"\s{2,}", " ", PLACEHOLDER_RX.sub(fill, action)).strip()


def commit_succeeded(ctx):
    """The Bash call was a git commit and did not report a failure (Claude: tool_response; Codex: exit code)."""
    resp = ctx.payload.get("tool_response")
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode", "returncode"):
            if isinstance(resp.get(key), int) and resp[key] != 0:
                return False
        if resp.get("interrupted"):
            return False
    return True


# Where the claude-seo and claude-blog skill files live for an agent that cannot run them as plugins.
SKILL_SOURCES = ("/opt/agent-plugins", os.path.expanduser("~/.local/share/ai/plugins"))


def claude_logged_in():
    """Cheap check: a claude binary plus stored credentials or a token in the environment. No network."""
    import shutil
    if not shutil.which("claude"):
        return False
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    if os.path.isfile(os.path.join(cfg, ".credentials.json")):
        return True
    for path in (os.path.join(cfg, ".claude.json"), os.path.expanduser("~/.claude.json")):
        text = read_text(path) or ""
        if '"oauthAccount"' in text:
            return True
    return False


def skill_paths():
    out = []
    for pack, entry in (("claude-seo", "skills/seo/SKILL.md"), ("claude-blog", "skills/blog/SKILL.md")):
        for base in SKILL_SOURCES:
            p = os.path.join(base, pack, entry)
            if os.path.isfile(p):
                out.append(p)
                break
    return out


def claude_handoff(agent):
    """How a non-Claude agent runs a Claude-only skill pack (owner decision 2026-11-12).
    Hermes: never hands off, follows the skill files itself.
    Codex: hands off only when claude is logged in for this user AND the owner approved a network run (the
    default sandbox has no network); otherwise the skill files.
    opencode and others: hand off only when claude is logged in for this user."""
    if agent == "claude":
        return ""
    paths = skill_paths()
    files = ("Skill files: %s (then the sub-skill it names, e.g. skills/seo-page/SKILL.md)." % ", ".join(paths)
             if paths else "The skill files are not installed for this user: tell the owner.")
    if agent == "hermes":
        return "Do not hand off to Claude. Follow the skill files yourself. " + files
    if agent == "codex":
        if not claude_logged_in():
            return "Claude Code is not logged in for this user: do not hand off. Follow the skill files yourself. " + files
        return ("Follow the skill files yourself. Hand off to Claude Code (claude -p \"<task>\" --output-format "
                "stream-json --verbose) only when the owner approved an escalated run with network for it: the "
                "default sandbox has no network. " + files)
    if claude_logged_in():
        return ("Not in Claude: hand it to Claude Code (claude -p \"<task>\" --output-format stream-json --verbose,"
                " no --bare). " + files)
    return "Claude Code is not logged in for this user: do not hand off. Follow the skill files yourself. " + files


# ---------------------------------------------------------------- docs IDs log (for ai-libs)

def log_docs_ids(ctx, tool, tin):
    """One row per docs lookup in docs-ids.jsonl: which library ID or name was used, in which repo."""
    lib = version = c7 = grounded = ""
    if re.search(r"query-docs|get-library-docs", tool):
        c7 = str(tin.get("libraryId") or tin.get("context7CompatibleLibraryID") or "")
        parts = c7.strip("/").split("/")
        lib = parts[1] if len(parts) >= 2 else (parts[0] if c7 else "")   # /org/project[/version]: the project
    elif re.search(r"resolve-library-id", tool):
        lib = str(tin.get("libraryName") or "")
    elif re.search(r"search_docs|list_versions|scrape", tool):
        lib = str(tin.get("library") or "")
        version = str(tin.get("version") or "")
        grounded = ("%s@%s" % (lib, version)) if lib and version else lib
    if not lib:
        return
    append_jsonl("docs-ids.jsonl", ctx.row(kind="docs-id", repo=ctx.root or "", tool=tool, lib=lib.lower(),
                                           version=version, context7=c7, grounded=grounded))
    d = ctx.state.load()
    if not d.get("docs_ids_new"):
        d["docs_ids_new"] = True
        ctx.state.dirty = True


# ---------------------------------------------------------------- gates (L4); logic lives in hooklib.py

def run_gate(rule, ctx, cmd):
    gate = GATES.get(rule["id"])
    if gate is None:
        return
    verdict = gate(ctx, cmd, ctx.stages)        # None = pass, ("deny"|"ask", message)
    if verdict is None:
        return
    skips, problems = ctx.skips
    for p in problems:
        if p not in ctx.contexts:
            ctx.add_context("[ai gate] " + p)
    if rule["id"] in skips:
        log_line("gates.log", "%s SKIP %s session=%s reason=%s cmd=%s" % (
            iso_now(), rule["id"], ctx.session, redact(skips[rule["id"]]), redact(one_line(cmd))[:200]))
        ctx.add_context("[ai gate %s] skipped by the owner (/etc/ai/gate-skip, logged)." % rule["id"])
        return
    decision, msg = verdict
    # Decide first: logging below never raises, and a failure there must not lose the decision.
    ctx.decide(decision, "[ai gate %s] %s\nOnly the owner can let it through, by running "
               "sudo ai-gate-skip %s <minutes, max 60> <why>. It is logged. Do not try to get around "
               "the gate." % (rule["id"], msg, rule["id"]))
    log_line("gates.log", "%s %s %s session=%s cmd=%s" % (
        iso_now(), decision.upper(), rule["id"], ctx.session, redact(one_line(cmd))[:200]))
    ctx.fired(rule, "PreToolUse")


# ---------------------------------------------------------------- docs-on-dependency

def is_docs_tool(tool):
    return tool.startswith("mcp__") and re.search(r"context7|docs", tool) is not None


# ---------------------------------------------------------------- miss log (L7) and notify

def check_misses(ctx):
    pending = ctx.state.take_pending()
    if not pending:
        return
    stream = transcript_events(pending)
    skills = recent_skills(ctx.session)
    for item in pending:
        rx = item.get("proof")
        if not rx:
            continue
        if any(search(rx, ev) for ev in stream[item.get("offset_key", "")]) or any(search(rx, s) for s in skills):
            continue
        append_jsonl("misses.jsonl", ctx.row(rule=item["rule"], fired_at=item["ts"], proof=rx))


def transcript_events(pending):
    """Assistant tool calls and text from the transcript since the rule fired, as short strings."""
    out = {}
    for item in pending:
        path, off = item.get("transcript"), int(item.get("offset") or 0)
        key = "%s:%d" % (path, off)
        item["offset_key"] = key
        if key in out:
            continue
        out[key] = []
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fh:
                fh.seek(off)
                data = fh.read(20 * 1024 * 1024).decode("utf-8", "replace")
        except OSError:
            continue
        for line in data.splitlines():
            out[key].extend(events_of_line(line))
    return out


def events_of_line(line):
    try:
        obj = json.loads(line)
    except ValueError:
        return []
    msg = obj.get("message") if isinstance(obj, dict) else None
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        return []
    content = msg.get("content")
    if isinstance(content, str):
        return ["text:" + content[:2000]]
    evs = []
    for c in content or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use":
            name = c.get("name", "")
            inp = c.get("input") if isinstance(c.get("input"), dict) else {}
            if name == "Skill":
                evs.append("skill:%s" % (inp.get("skill") or inp.get("name") or ""))
            evs.append("tool:%s %s" % (name, json.dumps(inp)[:2000]))
        elif c.get("type") == "text":
            evs.append("text:" + str(c.get("text", ""))[:2000])
    return evs


def recent_skills(session):
    text = read_text(state_path("fired.jsonl")) or ""
    out = []
    for line in text.splitlines()[-2000:]:
        if '"skill"' not in line or session not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") == "skill" and row.get("session") == session:
            out.append("skill:" + row.get("skill", ""))
    return out


def run_notify(ctx):
    import subprocess
    exe = first_existing([os.path.join(HOOK_DIR, "claude-notify"),
                          os.path.expanduser("~/.dotfiles/bin/claude-notify")])
    if not exe or not os.access(exe, os.X_OK):
        return
    env = dict(os.environ, AI_NOTIFY_AGENT=ctx.agent)
    try:
        subprocess.run([exe], input=ctx.raw.encode("utf-8"), env=env, timeout=12,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        log_error("notify", exc)


# ---------------------------------------------------------------- session state

class SessionState(object):
    """Per-session JSON in <state>/sessions/<id>.json, guarded by flock (hooks may run in parallel)."""

    def __init__(self, session):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session)[:120]
        self.path = state_path(os.path.join("sessions", safe + ".json"))
        self.data = None
        self.dirty = False
        self.lock_fh = None

    def load(self):
        if self.data is not None:
            return self.data
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            import fcntl
            self.lock_fh = open(self.path + ".lock", "a")
            fcntl.flock(self.lock_fh, fcntl.LOCK_EX)
        except (ImportError, OSError):
            self.lock_fh = None
        try:
            self.data = json.loads(read_text(self.path) or "{}")
        except ValueError:
            self.data = {}
        return self.data

    def save(self):
        if self.data is not None and self.dirty:
            tmp = self.path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(self.data, fh)
            os.replace(tmp, self.path)
        if self.lock_fh:
            self.lock_fh.close()
            self.lock_fh = None

    def drop(self):
        for p in (self.path, self.path + ".lock"):
            try:
                os.unlink(p)
            except OSError:
                pass

    def allow_nudge(self, rule, key):
        d = self.load()
        now = time.time()
        window = rule.get("quiet_window_s")
        if window:
            last = d.setdefault("last", {}).get(rule["id"], 0)
            if now - last < float(window):
                return False
            d["last"][rule["id"]] = now
        else:
            keys = d.setdefault("keys", {}).setdefault(rule["id"], [])
            if key in keys:
                return False
            keys.append(key)
        self.dirty = True
        return True

    def add_pending(self, rule_id, proof, transcript):
        d = self.load()
        offset = 0
        if transcript and os.path.isfile(transcript):
            offset = os.path.getsize(transcript)
        pend = d.setdefault("pending", [])
        if any(p["rule"] == rule_id for p in pend):
            return
        pend.append({"rule": rule_id, "proof": proof, "transcript": transcript, "offset": offset, "ts": iso_now()})
        self.dirty = True

    def take_pending(self):
        d = self.load()
        pend = d.pop("pending", [])
        if pend:
            self.dirty = True
        return pend

    def has_code(self, root):
        d = self.load()
        cache = d.setdefault("code", {})
        if root not in cache:
            cache[root] = has_code_files(root)
            self.dirty = True
        return cache[root]


# ---------------------------------------------------------------- helpers

def load_routing():
    path = first_existing(routing_candidates())
    if not path:
        return {"rules": [], "tiebreaks": [], "layers": {}}
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        log_error("routing", exc)
        return {"rules": [], "tiebreaks": [], "layers": {}}


ROUTING_OVERRIDE = None     # set by an embedding host (Hermes plugin) to its own routing.json copy


def routing_candidates():
    env = ROUTING_OVERRIDE or os.environ.get("AI_ROUTING_JSON")
    if env:
        return [env]
    home = ai_home()
    out = [os.path.join(home, "ai", "build", "routing.json")] if home else []
    return out + [os.path.join(HOOK_DIR, "routing.json")]


def l0_candidates():
    env = ROUTING_OVERRIDE or os.environ.get("AI_ROUTING_JSON")
    if env:
        return [os.path.join(os.path.dirname(env), "L0.md")]
    home = ai_home()
    out = [os.path.join(home, "ai", "build", "L0.md")] if home else []
    return out + [os.path.join(HOOK_DIR, "L0.md")]


def rules_for(routing, when):
    return [r for r in routing.get("rules", []) if r.get("when") == when]


def tool_input(payload):
    tin = payload.get("tool_input")
    return tin if isinstance(tin, dict) else {}


def command_of(tin):
    c = tin.get("command") or tin.get("cmd") or ""
    if isinstance(c, list):
        c = " ".join(str(x) for x in c)
    return c if isinstance(c, str) else ""


def file_of(tin):
    for key in ("file_path", "notebook_path"):
        v = tin.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def search(rx, text):
    try:
        return re.search(rx, text, re.IGNORECASE) is not None
    except re.error as exc:
        log_error("regex " + rx[:60], exc)
        return False


def rotate_logs(limit=5 * 1024 * 1024):
    for rel in ("fired.jsonl", "misses.jsonl", "gates.log", "router-errors.log", "docs-ids.jsonl"):
        p = state_path(rel)
        try:
            if os.path.getsize(p) > limit:
                os.replace(p, p + ".1")
        except OSError:
            pass


def prune_sessions(max_age=7 * DAY):
    d = state_path("sessions")
    if not os.path.isdir(d):
        return
    now = time.time()
    for f in os.listdir(d):
        p = os.path.join(d, f)
        try:
            if now - os.path.getmtime(p) > max_age:
                os.unlink(p)
        except OSError:
            pass


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
