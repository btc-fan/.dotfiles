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
                     install_targets, iso_now, log_error, log_line, norm_pypi, one_line, parse_command, redact,
                     project_root, read_text, split_simple, state_path)

HOOK_DIR = os.path.dirname(os.path.realpath(__file__))
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


def parse_args(argv):
    agent, event = None, ""
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--agent" and args:
            agent = args.pop(0)
        elif a.startswith("--agent="):
            agent = a.split("=", 1)[1]
        else:
            event = a
    return agent, event


# ---------------------------------------------------------------- event handlers

def on_session_start(ctx):
    rotate_logs()
    prune_sessions()
    routing = ctx.routing
    parts = []
    if routing.get("layers", {}).get("L1_session_start") is not None or routing.get("rules"):
        l0 = read_text(first_existing(l0_candidates()))
        if l0:
            parts.append("[ai router L1] Routing table (also in your root rules; re-sent after compaction):\n" + l0.strip())
    for rule in rules_for(routing, "session_start"):
        if not rule_enabled(rule, ctx):
            continue
        state = rule.get("trigger", {}).get("state")
        if state and not check_state(state, ctx):
            continue
        parts.append("[ai router: %s] %s" % (rule["id"], rule["action"]))
        ctx.fired(rule, "SessionStart")
    if parts:
        ctx.add_context("\n\n".join(parts))


def on_user_prompt(ctx):
    prompt = ctx.payload.get("prompt") or ""
    if not prompt.strip():
        return
    routing = ctx.routing
    matched = []
    for rule in routing.get("rules", []):
        rx = rule.get("trigger", {}).get("prompt")
        if not rx or not search(rx, prompt):
            continue
        if not rule_enabled(rule, ctx):
            continue
        state = rule["trigger"].get("state")
        if state and not check_state(state, ctx):
            continue
        matched.append(rule)
    ties = match_tiebreaks(routing.get("tiebreaks", []), prompt)
    if not matched and not ties:
        return
    for rule in matched:
        ctx.fired(rule, "UserPromptSubmit")
    ctx.add_context(render_prompt_context(routing, matched, ties))


def on_pre_tool(ctx):
    tool = ctx.payload.get("tool_name") or ""
    tin = tool_input(ctx.payload)
    cmd = command_of(tin)
    ctx.set_command(cmd)
    for rule in ctx.routing.get("rules", []):
        trig = rule.get("trigger", {})
        if not trig.get("tool_before") or not tool_matches(trig["tool_before"], tool):
            continue
        if not rule_enabled(rule, ctx):
            continue
        if rule.get("strength") == "gate":
            probe = GATE_PROBES.get(rule["id"])
            if cmd and (conditions_match(rule, tool, tin, cmd, ctx) or (probe and probe(ctx.stages))):
                run_gate(rule, ctx, cmd)
            continue
        if not conditions_match(rule, tool, tin, cmd, ctx):
            continue
        if rule.get("log_only"):
            ctx.fired(rule, "PreToolUse", log_only=True)
            continue
        if ctx.state.allow_nudge(rule, nudge_key(rule, tool, tin, cmd)):
            ctx.fired(rule, "PreToolUse")
            ctx.add_context("[ai router: %s] %s" % (rule["id"], rule["action"]))


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
        ctx.state.add_docs_libs(docs_libraries(tin))
    if cmd:
        ctx.state.apply_resets(ctx.routing, ctx.cmd_text)
    for rule in ctx.routing.get("rules", []):
        trig = rule.get("trigger", {})
        if not trig.get("tool_after") or not tool_matches(trig["tool_after"], tool):
            continue
        if not rule_enabled(rule, ctx) or not conditions_match(rule, tool, tin, cmd, ctx):
            continue
        if rule.get("once_per") == "library_per_session":
            msg = dependency_nudge(rule, ctx, tool, tin, cmd)
            if msg:
                ctx.fired(rule, "PostToolUse")
                ctx.add_context(msg)
            continue
        if trig.get("content"):
            hits = content_hits(trig["content"], tin)
            if hits:
                ctx.fired(rule, "PostToolUse")
                ctx.add_context("[ai router: %s] %s (%s, %d line(s))" % (
                    rule["id"], rule["action"], file_of(tin) or "edited text", hits))
            continue
        if ctx.state.allow_nudge(rule, nudge_key(rule, tool, tin, cmd)):
            ctx.fired(rule, "PostToolUse")
            ctx.add_context("[ai router: %s] %s" % (rule["id"], rule["action"]))


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
            self.reasons.append("Codex cannot ask the owner. Stop and ask the owner; after an OK, rerun with "
                                "AI_GATE_SKIP='<rule>:<owner OK reason>'.")
        if self.decision == "deny":
            reason = "\n".join(self.reasons)
            # Codex (shape used by the audited oh-my-codex 0.22.6 hooks) also reads decision/reason.
            top = {"decision": "block", "reason": reason} if self.agent == "codex" else {}
            self.emit({"permissionDecision": "deny", "permissionDecisionReason": reason}, top)
            return 0
        if self.decision == "ask":
            self.emit({"permissionDecision": "ask", "permissionDecisionReason": "\n".join(self.reasons)})
            return 0
        if self.contexts:
            self.emit({})
        return 0

    def emit(self, extra, top=None):
        out = {"hookEventName": self.event}
        out.update(extra)
        if self.contexts:
            out["additionalContext"] = "\n\n".join(self.contexts)[:9500]
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
    for rule in matched:
        lines.append("- %s: %s" % (rule["id"], rule["action"]))
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
    - paths 'code' applies to file tools (file path) and to Bash (a code path in the arguments).
    - paths globs apply to file tools only (Bash relies on command).
    - a tool without a command and without a file path passes (e.g. Agent for prompting-others).
    """
    trig = rule.get("trigger", {})
    paths = trig.get("paths")
    if cmd:
        if trig.get("command") and not search(trig["command"], ctx.cmd_text or cmd):
            return False
        if paths == "code" and not bash_touches_code(cmd, ctx):
            return False
        return True
    if trig.get("command") and tool in ("Bash", "shell", "exec_command", "local_shell"):
        return False
    fpath = file_of(tin)
    if paths:
        if paths == "code":
            if tool in ("Grep", "Glob"):
                return search_targets_code(tin, ctx)
            return bool(fpath) and is_code_path(fpath)
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


def bash_touches_code(cmd, ctx):
    toks = split_simple(cmd)
    if any(is_code_path(t) for t in toks if not t.startswith("-")):
        return True
    head = [t for t in toks if not re.match(r"^\w+=", t)]
    if head and os.path.basename(head[0]) in ("grep", "rg", "ag", "ack"):
        dirs = [t for t in head[1:] if not t.startswith("-") and os.path.isdir(os.path.join(ctx.cwd, t))]
        if dirs or len(head) <= 3:
            return ctx.root is not None and ctx.state.has_code(ctx.root)
    return False


def search_targets_code(tin, ctx):
    pat = tin.get("pattern", "") if "glob" not in tin else tin.get("glob", "")
    if any(pat.endswith(e) for e in CODE_EXT) or re.search(r"\*\.\{?(py|ts|tsx|js|go|rs)", pat or ""):
        return True
    target = tin.get("path") or ctx.cwd
    if os.path.isfile(target):
        return is_code_path(target)
    root = project_root(target)
    return root is not None and ctx.state.has_code(root)


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
    for rel in (".mcp.json", ".codex/config.toml", ".claude/settings.json"):
        text = read_text(os.path.join(root, rel))
        if text and "playwright" in text.lower():
            return True
    return False


def enabled_tools(root):
    text = read_text(os.path.join(root, ".ai", "enabled")) if root else ""
    return {ln.split("#", 1)[0].strip().lower() for ln in (text or "").splitlines() if ln.split("#", 1)[0].strip()}


def rule_enabled(rule, ctx):
    if rule.get("scope", "global") != "opt-in":
        return True
    if ctx.root is None:
        return False
    names = enabled_tools(ctx.root)
    if rule["id"].lower() in names or str(rule.get("tool", "")).lower() in names:
        return True
    return rule["id"] == "browser" and playwright_enabled(ctx.root)


def _state_no_base(ctx):
    return ctx.root is not None and not os.path.exists(os.path.join(ctx.root, ".ai", "base-version"))


def _state_no_graph(ctx):
    return (ctx.root is not None
            and not os.path.exists(os.path.join(ctx.root, "graphify-out", "graph.json"))
            and ctx.state.has_code(ctx.root))


def _state_no_playwright(ctx):
    return not playwright_enabled(ctx.root or ctx.cwd)


# routing.yaml `state:` strings -> predicates. ai-render fails on a state string not listed here.
STATE_PREDICATES = {
    "git repo without .ai/base-version": _state_no_base,
    "git repo with code and no graphify-out/graph.json": _state_no_graph,
    "project without Playwright MCP": _state_no_playwright,
}


def check_state(name, ctx):
    pred = STATE_PREDICATES.get(name)
    return bool(pred and pred(ctx))


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
        ctx.add_context("[ai gate %s] skipped by AI_GATE_SKIP (logged)." % rule["id"])
        return
    decision, msg = verdict
    # Decide first: logging below never raises, and a failure there must not lose the decision.
    ctx.decide(decision, "[ai gate %s] %s\nEscape hatch (owner OK only): prefix the command with "
               "AI_GATE_SKIP='%s:<why>'. It is logged." % (rule["id"], msg, rule["id"]))
    log_line("gates.log", "%s %s %s session=%s cmd=%s" % (
        iso_now(), decision.upper(), rule["id"], ctx.session, redact(one_line(cmd))[:200]))
    ctx.fired(rule, "PreToolUse")


# ---------------------------------------------------------------- docs-on-dependency

def dependency_nudge(rule, ctx, tool, tin, cmd):
    libs = set()
    if cmd:
        for eco, name, _v in install_targets(ctx.stages, ctx.cwd):
            if eco in ("npm", "pypi", "cargo"):
                libs.add(name)
        for mm in re.finditer(r"\bgo get\s+(\S+)", cmd):
            libs.add(mm.group(1).split("@")[0])
    else:
        libs = manifest_libs(file_of(tin), tin)
    key = file_of(tin) or "cmd"
    new = ctx.state.new_dependency_libs(libs, key)
    if new is None:
        return None
    named = (": " + ", ".join(sorted(new)[:8])) if new else ""
    return "[ai router: %s] %s%s" % (rule["id"], rule["action"], named)


def manifest_libs(path, tin):
    new = "\n".join(t for t in (tin.get("content"), tin.get("new_string")) if isinstance(t, str))
    old = tin.get("old_string") if isinstance(tin.get("old_string"), str) else ""
    base = os.path.basename(path or "")
    if base == "package.json":
        rx = r'"(@?[a-z0-9][\w./-]*)"\s*:\s*"[~^<>=]*\d'
    elif base == "go.mod":
        rx = r"^\s*(?:require\s+)?([a-z0-9.-]+\.[a-z]+/[\w./-]+)\s+v\d"
    elif base == "Cargo.toml":
        rx = r"^\s*([a-z0-9_-]+)\s*=\s*[\"{]"
    else:   # pyproject.toml, requirements*.txt
        rx = r"^\s*[\"']?([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?:[=<>~!]=?|[\"',]|$)"
    found = set(re.findall(rx, new, re.M)) - set(re.findall(rx, old, re.M))
    ignore = {"name", "version", "description", "edition", "license", "requires-python", "python", "module",
              "go", "authors", "readme", "type", "main", "private", "scripts", "build-backend", "requires"}
    return {norm_pypi(x) if base != "package.json" else x.lower() for x in found if x.lower() not in ignore}


def is_docs_tool(tool):
    return tool.startswith("mcp__") and re.search(r"context7|docs", tool) is not None


def docs_libraries(tin):
    libs = set()
    for key in ("libraryName", "library", "libraryId", "context7CompatibleLibraryID", "name", "package"):
        v = tin.get(key)
        if isinstance(v, str) and v:
            libs.add(v.strip("/").split("/")[-1].lower())
            libs.add(norm_pypi(v.strip("/").split("/")[-1]))
    return libs


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

    def apply_resets(self, routing, cmd):
        d = self.load()
        for rule in routing.get("rules", []):
            rx = rule.get("reset_on")
            if rx and search(rx, cmd) and d.get("keys", {}).get(rule["id"]):
                d["keys"][rule["id"]] = []
                self.dirty = True

    def add_docs_libs(self, libs):
        if libs:
            d = self.load()
            d["docs_libs"] = sorted(set(d.get("docs_libs", [])) | set(libs))
            self.dirty = True

    def new_dependency_libs(self, libs, key):
        """Libraries not looked up and not nudged yet this session; None = stay quiet."""
        d = self.load()
        done = set(d.get("docs_libs", [])) | set(d.get("dep_nudged", []))
        if libs:
            new = sorted(set(libs) - done)
            if not new:
                return None
            d["dep_nudged"] = sorted(set(d.get("dep_nudged", [])) | set(new))
            self.dirty = True
            return new
        files = d.setdefault("dep_files", [])
        if key in files:
            return None
        files.append(key)
        self.dirty = True
        return []

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
    for rel in ("fired.jsonl", "misses.jsonl", "gates.log", "router-errors.log"):
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
