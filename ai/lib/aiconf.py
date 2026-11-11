#!/usr/bin/env python3
"""aiconf: the small merge engine of the `ai` installer.

It changes only the keys, blocks, links and registrations that the installer owns, and it
records every change in a state file (default ~/.local/state/ai/managed-keys.json) so that
uninstall.sh can undo exactly that and nothing else.

Rules:
- Merge only. A file that a tool also writes is never replaced: one key, one block or one
  hook entry at a time.
- The first record of a key keeps the ORIGINAL previous value. Re-runs update only the new value.
- Undo restores a value only if it still equals what we set. Changed by the user = left alone.
- --dry-run prints the change and writes nothing (not even the state file).
- python3.9+ stdlib only (macOS /usr/bin/python3 is 3.9).
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

STATE_DEFAULT = os.path.expanduser("~/.local/state/ai/managed-keys.json")

# Hook commands that are "the same hook" even when the path differs (settings.json copy vs
# plugin copy). Used by claude-adopt-hooks to avoid duplicates.
ADOPT_SIGNATURES = [
    "claude-notify",
    "caffeinate -s -w",
    "graphify hook-guard",
    "serena-hook",   # vendor `serena-hooks activate` and our `hooks/serena-hook` wrapper
]

# Serena needs a different context per client (SPEC 4).
SERENA_CONTEXT = {"claude": "claude-code", "codex": "codex", "hermes": "ide", "opencode": "ide"}

DRY = False
STATE_PATH = STATE_DEFAULT


def main():
    global DRY, STATE_PATH
    p = argparse.ArgumentParser(prog="aiconf")
    p.add_argument("--state", default=STATE_DEFAULT)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("json-set", help="set one key (path a/b/c) to a JSON value")
    s.add_argument("file"); s.add_argument("path"); s.add_argument("value")
    s.add_argument("--jsonc", action="store_true", help="file may hold // and /* */ comments")
    s.add_argument("--mode", default="")

    s = sub.add_parser("json-add", help="add a JSON value to a list key if missing")
    s.add_argument("file"); s.add_argument("path"); s.add_argument("value")

    s = sub.add_parser("toml-set", help="set one key in one TOML table ('' = root)")
    s.add_argument("file"); s.add_argument("table"); s.add_argument("key"); s.add_argument("value")

    s = sub.add_parser("yaml-top-set", help="set one top-level YAML key (scalar or flow list)")
    s.add_argument("file"); s.add_argument("key"); s.add_argument("value")

    s = sub.add_parser("block-upsert", help="upsert a managed block <!-- AI:<name> v<N> START -->")
    s.add_argument("file"); s.add_argument("name"); s.add_argument("version"); s.add_argument("content_file")

    s = sub.add_parser("file-put", help="make a file hold exactly this content (backup kept)")
    s.add_argument("file"); s.add_argument("content_file"); s.add_argument("--mode", default="")

    s = sub.add_parser("link", help="symlink LINK -> TARGET (a non-link file is moved to backup)")
    s.add_argument("link"); s.add_argument("target")

    s = sub.add_parser("line-add", help="append a line if missing (recorded for undo)")
    s.add_argument("file"); s.add_argument("text")

    s = sub.add_parser("line-remove", help="remove lines equal to TEXT (recorded for undo)")
    s.add_argument("file"); s.add_argument("text")

    s = sub.add_parser("record-cmd", help="record an undo command; argv after --")
    s.add_argument("id"); s.add_argument("undo", nargs=argparse.REMAINDER)

    s = sub.add_parser("claude-adopt-hooks", help="drop settings.json hooks that the plugin now owns")
    s.add_argument("settings"); s.add_argument("plugin_hooks")

    s = sub.add_parser("claude-take-mcp", help="move user-scope MCP entries that our plugin now serves")
    s.add_argument("claude_json"); s.add_argument("mcp_json")

    s = sub.add_parser("mcp-register", help="register our MCP servers in codex | hermes")
    s.add_argument("agent", choices=["codex", "hermes"])
    s.add_argument("--mcp-json", required=True); s.add_argument("--plugin-root", required=True)
    s.add_argument("--prefix", default="", help="shell prefix, e.g. 'sudo -u hermes -H'")

    s = sub.add_parser("opencode-mcp", help="set our MCP servers in opencode.json")
    s.add_argument("file"); s.add_argument("--mcp-json", required=True); s.add_argument("--plugin-root", required=True)

    s = sub.add_parser("tree-hash", help="sha256 over a directory tree (change detection)")
    s.add_argument("dir")

    s = sub.add_parser("json-get", help="print a JSON value (path a/b/c), empty if absent")
    s.add_argument("file"); s.add_argument("path")

    s = sub.add_parser("hooks-diff", help="print hook commands in settings.json, one per line")
    s.add_argument("settings")

    s = sub.add_parser("undo", help="reverse every recorded change, newest first")
    s.add_argument("--keep-state", action="store_true")

    sub.add_parser("status", help="list recorded changes")

    a = p.parse_args()
    DRY = a.dry_run
    STATE_PATH = os.path.expanduser(a.state)
    fn = globals()["cmd_" + a.cmd.replace("-", "_")]
    sys.exit(fn(a) or 0)


# ---------------------------------------------------------------- commands

def cmd_json_set(a):
    data, raw = load_json(a.file, jsonc=a.jsonc)
    path = split_path(a.path)
    new = json.loads(a.value)
    had, old = get_path(data, path)
    if had and old == new:
        return say("same", a.file, a.path)
    if a.jsonc and raw and has_comments(raw):
        say("note", a.file, "comments are dropped on write (jsonc)")
    set_path(data, path, new)
    write_json(a.file, data, a.mode)
    record({"kind": "json", "file": a.file, "path": path, "had": had, "prev": old, "value": new},
           key="json:%s:%s" % (a.file, "/".join(path)))
    say("set", a.file, "%s = %s" % (a.path, short(new)))


def cmd_json_add(a):
    data, _ = load_json(a.file)
    path = split_path(a.path)
    item = json.loads(a.value)
    had, cur = get_path(data, path)
    if had and not isinstance(cur, list):
        return say("skip", a.file, "%s is not a list" % a.path)
    cur = list(cur) if had else []
    if item in cur:
        return say("same", a.file, a.path)
    cur.append(item)
    set_path(data, path, cur)
    write_json(a.file, data)
    record({"kind": "json-item", "file": a.file, "path": path, "item": item, "had_list": had},
           key="json-item:%s:%s:%s" % (a.file, "/".join(path), json.dumps(item)))
    say("add", a.file, "%s += %s" % (a.path, short(item)))


def cmd_toml_set(a):
    text = read_text(a.file)
    lines = text.splitlines()
    start, end = toml_table_span(lines, a.table)
    want = "%s = %s" % (a.key, a.value)
    key_re = re.compile(r"^\s*%s\s*=" % re.escape(a.key))
    prev = None
    created_table = False
    if start is None:
        created_table = bool(a.table)
        if a.table:
            if lines and lines[-1].strip():
                lines.append("")
            lines += ["[%s]" % a.table, want]
        else:
            first = next((i for i, l in enumerate(lines) if re.match(r"^\s*\[", l)), len(lines))
            lines.insert(first, want)
    else:
        idx = next((i for i in range(start, end) if key_re.match(lines[i])), None)
        if idx is not None:
            prev = lines[idx]
            if prev.strip() == want:
                return say("same", a.file, "[%s] %s" % (a.table, a.key))
            lines[idx] = want
        else:
            ins = end
            while ins > start and not lines[ins - 1].strip():
                ins -= 1
            lines.insert(ins, want)
    write_text(a.file, "\n".join(lines) + "\n")
    record({"kind": "toml", "file": a.file, "table": a.table, "key": a.key, "prev": prev, "value": want,
            "created_table": created_table},
           key="toml:%s:%s:%s" % (a.file, a.table, a.key), keep_first=("prev", "created_table"))
    say("set", a.file, "[%s] %s" % (a.table or "root", want))


def cmd_yaml_top_set(a):
    text = read_text(a.file)
    if text == "":
        return say("skip", a.file, "missing (run the tool's init first)")
    lines = text.splitlines()
    want = "%s: %s" % (a.key, a.value)
    idx = next((i for i, l in enumerate(lines) if re.match(r"^%s:" % re.escape(a.key), l)), None)
    prev_block = []
    if idx is None:
        lines.append(want)
    else:
        j = idx + 1
        while j < len(lines) and re.match(r"^\s+-\s|^\s+\S", lines[j]) and not re.match(r"^\S", lines[j]):
            j += 1
        prev_block = lines[idx:j]
        if prev_block == [want]:
            return say("same", a.file, a.key)
        lines[idx:j] = [want]
    write_text(a.file, "\n".join(lines) + "\n")
    record({"kind": "yaml", "file": a.file, "key": a.key, "prev": prev_block, "value": want},
           key="yaml:%s:%s" % (a.file, a.key))
    say("set", a.file, want)


def cmd_block_upsert(a):
    body = read_text(a.content_file).rstrip("\n")
    text = read_text(a.file)
    start = "<!-- AI:%s v%s START -->" % (a.name, a.version)
    endm = "<!-- AI:%s v%s END -->" % (a.name, a.version)
    block = "%s\n%s\n%s" % (start, body, endm)
    rx = block_regex(a.name)
    existed = bool(text.strip())
    m = rx.search(text)
    if m:
        if m.group(0) == block:
            return say("same", a.file, "block AI:%s" % a.name)
        new = text[:m.start()] + block + text[m.end():]
    elif not text:
        new = block + "\n"
    elif text.endswith("\n\n"):
        new = text + block + "\n"
    elif text.endswith("\n"):
        new = text + "\n" + block + "\n"
    else:
        new = text + "\n\n" + block + "\n"
    write_text(a.file, new)
    record({"kind": "block", "file": a.file, "name": a.name, "existed": existed},
           key="block:%s:%s" % (a.file, a.name))
    say("block", a.file, "AI:%s v%s (%d bytes)" % (a.name, a.version, len(body)))


def cmd_file_put(a):
    content = read_text(a.content_file)
    cur = read_text(a.file) if os.path.exists(a.file) else None
    if cur == content:
        return say("same", a.file, "")
    backup = None
    if cur is not None:
        backup = backup_path(a.file)
        if not DRY:
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copy2(a.file, backup)
    write_text(a.file, content, a.mode)
    record({"kind": "file", "file": a.file, "backup": backup, "sha": sha(content)}, key="file:%s" % a.file,
           keep_first=("backup",))
    say("write", a.file, "backup %s" % backup if backup else "new file")


def cmd_link(a):
    link, target = os.path.expanduser(a.link), os.path.expanduser(a.target)
    if os.path.islink(link) and os.readlink(link) == target:
        return say("same", link, "-> " + target)
    backup = None
    if os.path.lexists(link):
        if os.path.isdir(link) and not os.path.islink(link):
            return say("skip", link, "is a real directory, left alone")
        if not os.path.islink(link):
            backup = backup_path(link)
    if not DRY:
        os.makedirs(os.path.dirname(link), exist_ok=True)
        if backup:
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.move(link, backup)
        elif os.path.lexists(link):
            os.remove(link)
        os.symlink(target, link)
    record({"kind": "link", "file": link, "target": target, "backup": backup}, key="link:%s" % link,
           keep_first=("backup",))
    say("link", link, "-> %s%s" % (target, " (old file kept in %s)" % backup if backup else ""))


def cmd_line_add(a):
    text = read_text(a.file)
    if a.text in text.splitlines():
        return say("same", a.file, "line %r" % a.text)
    write_text(a.file, text + ("" if text.endswith("\n") or not text else "\n") + a.text + "\n")
    record({"kind": "line-added", "file": a.file, "text": a.text}, key="line-added:%s:%s" % (a.file, a.text))
    say("add", a.file, "line %r" % a.text)


def cmd_line_remove(a):
    text = read_text(a.file)
    lines = text.splitlines()
    hits = [i for i, l in enumerate(lines) if l.strip() == a.text.strip()]
    if not hits:
        return say("same", a.file, "no line %r" % a.text)
    for i in reversed(hits):
        del lines[i]
    write_text(a.file, "\n".join(lines) + ("\n" if lines else ""))
    record({"kind": "line-removed", "file": a.file, "text": a.text}, key="line:%s:%s" % (a.file, a.text))
    say("remove", a.file, "line %r" % a.text)


def cmd_record_cmd(a):
    undo = a.undo[1:] if a.undo and a.undo[0] == "--" else a.undo
    record({"kind": "cmd", "id": a.id, "undo": undo}, key="cmd:%s" % a.id)
    say("record", a.id, "undo: " + shlex.join(undo))


def cmd_claude_adopt_hooks(a):
    plugin, _ = load_json(a.plugin_hooks)
    owned = set()
    for event, groups in (plugin.get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks") or []:
                owned.add((event, signature(h.get("command", ""))))
    data, _ = load_json(a.settings)
    hooks = data.get("hooks") or {}
    removed = []
    for event in list(hooks.keys()):
        new_groups = []
        for gi, g in enumerate(hooks[event] or []):
            keep = []
            for hi, h in enumerate(g.get("hooks") or []):
                if (event, signature(h.get("command", ""))) in owned:
                    one = dict(g); one["hooks"] = [h]
                    removed.append((event, one, gi, hi))
                else:
                    keep.append(h)
            if keep:
                g2 = dict(g); g2["hooks"] = keep
                new_groups.append(g2)
        if new_groups:
            hooks[event] = new_groups
        else:
            del hooks[event]
    if not removed:
        return say("same", a.settings, "no hook duplicates the plugin")
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    write_json(a.settings, data)
    for event, group, gi, hi in removed:
        cmd = group["hooks"][0].get("command", "")
        record({"kind": "hook-removed", "file": a.settings, "event": event, "group": group, "gi": gi, "hi": hi},
               key="hook:%s:%s:%s" % (a.settings, event, cmd))
        say("adopt", a.settings, "%s hook %r now comes from the plugin" % (event, cmd))


def cmd_claude_take_mcp(a):
    ours, _ = load_json(a.mcp_json)
    names = list((ours.get("mcpServers") or {}).keys())
    data, _ = load_json(a.claude_json)
    user = data.get("mcpServers") or {}
    taken = [n for n in names if n in user]
    for n in taken:
        entry = user[n]
        undo = ["claude", "mcp", "add-json", "--scope", "user", n, json.dumps(entry)]
        run(["claude", "mcp", "remove", "--scope", "user", n])
        record({"kind": "cmd", "id": "claude-user-mcp:%s" % n, "undo": undo}, key="cmd:claude-user-mcp:%s" % n)
        say("move", a.claude_json, "user-scope MCP %r removed: the ai-core plugin serves it now" % n)
    if not taken:
        say("same", a.claude_json, "no user-scope MCP duplicates the plugin")


def cmd_mcp_register(a):
    prefix = shlex.split(a.prefix)
    for name, spec in mcp_specs(a.mcp_json, a.plugin_root, a.agent):
        if a.agent == "codex":
            codex_register(name, spec, prefix)
        else:
            hermes_register(name, spec, prefix)


def cmd_opencode_mcp(a):
    for name, spec in mcp_specs(a.mcp_json, a.plugin_root, "opencode"):
        if spec.get("url"):
            val = {"type": "remote", "url": spec["url"], "enabled": True}
        else:
            val = {"type": "local", "command": [spec["command"]] + spec["args"], "enabled": True}
            if spec["env"]:
                val["environment"] = spec["env"]
        ns = argparse.Namespace(file=a.file, path="mcp/" + name, value=json.dumps(val), jsonc=False, mode="")
        cmd_json_set(ns)


def cmd_tree_hash(a):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(a.dir):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__"))
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, a.dir).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    print(h.hexdigest())


def cmd_json_get(a):
    data, _ = load_json(a.file, jsonc=True)
    had, v = get_path(data, split_path(a.path))
    if had:
        print(v if isinstance(v, str) else json.dumps(v))


def cmd_hooks_diff(a):
    data, _ = load_json(a.settings)
    for event, groups in sorted((data.get("hooks") or {}).items()):
        for g in groups or []:
            for h in g.get("hooks") or []:
                print("%s\t%s" % (event, h.get("command", "")))


def cmd_status(a):
    st = load_state()
    for e in st["entries"]:
        print("%-13s %s %s" % (e["kind"], e.get("file") or e.get("id"), e.get("path") or e.get("key") or ""))
    print("%d recorded changes in %s" % (len(st["entries"]), STATE_PATH))


def cmd_undo(a):
    st = load_state()
    left = []
    for e in reversed(st["entries"]):
        try:
            ok = undo_entry(e)
        except Exception as ex:  # keep going: one broken entry must not stop the rest
            ok = False
            say("error", e.get("file") or e.get("id"), str(ex))
        if not ok:
            left.append(e)
    left.reverse()
    total = len(st["entries"])
    if not DRY and not a.keep_state:
        st["entries"] = left
        save_state(st)
    print("undo: %d of %d entries reversed, %d kept in the state file (failed)" % (total - len(left), total, len(left)))


# ---------------------------------------------------------------- undo

def undo_entry(e):
    k = e["kind"]
    f = e.get("file")
    if k == "json":
        data, _ = load_json(f)
        had, cur = get_path(data, e["path"])
        if not had or cur != e["value"]:
            return say("left", f, "/".join(e["path"]) + " changed since install") or True
        if e["had"]:
            set_path(data, e["path"], e["prev"])
        else:
            del_path(data, e["path"])
        write_json(f, data)
        return say("undo", f, "/".join(e["path"])) or True
    if k == "json-item":
        data, _ = load_json(f)
        had, cur = get_path(data, e["path"])
        if had and isinstance(cur, list) and e["item"] in cur:
            cur.remove(e["item"])
            if not cur and not e["had_list"]:
                del_path(data, e["path"])
            write_json(f, data)
        return say("undo", f, "/".join(e["path"]) + " item") or True
    if k == "toml":
        lines = read_text(f).splitlines()
        start, end = toml_table_span(lines, e["table"])
        idx = None
        if start is not None:
            idx = next((i for i in range(start, end) if lines[i].strip() == e["value"]), None)
        if idx is None:
            return say("left", f, e["key"] + " changed since install") or True
        if e["prev"] is None:
            del lines[idx]
        else:
            lines[idx] = e["prev"]
        if e.get("created_table"):
            start, end = toml_table_span(lines, e["table"])
            if start is not None and not any(l.strip() for l in lines[start:end]):
                first = start - 1
                while first > 0 and not lines[first - 1].strip():
                    first -= 1
                del lines[first:end]
        write_text(f, "\n".join(lines) + "\n")
        return say("undo", f, "[%s] %s" % (e["table"], e["key"])) or True
    if k == "yaml":
        lines = read_text(f).splitlines()
        idx = next((i for i, l in enumerate(lines) if l == e["value"]), None)
        if idx is None:
            return say("left", f, e["key"] + " changed since install") or True
        lines[idx:idx + 1] = e["prev"]
        write_text(f, "\n".join(lines) + "\n")
        return say("undo", f, e["key"]) or True
    if k == "block":
        text = read_text(f)
        new = block_regex(e["name"]).sub("", text, count=1)
        new = re.sub(r"\n{3,}", "\n\n", new).strip("\n")
        new = new + "\n" if new else ""
        if new == "" and not e.get("existed"):
            if not DRY and os.path.exists(f):
                os.remove(f)
        else:
            write_text(f, new)
        return say("undo", f, "block AI:" + e["name"]) or True
    if k == "file":
        if not os.path.exists(f) or sha(read_text(f)) != e["sha"]:
            return say("left", f, "changed since install") or True
        if e.get("backup") and os.path.exists(e["backup"]):
            if not DRY:
                shutil.copy2(e["backup"], f)
        elif not DRY:
            os.remove(f)
        return say("undo", f, "restored" if e.get("backup") else "removed") or True
    if k == "link":
        if os.path.islink(f) and os.readlink(f) == e["target"]:
            if not DRY:
                os.remove(f)
                if e.get("backup") and os.path.exists(e["backup"]):
                    shutil.move(e["backup"], f)
            return say("undo", f, "link removed") or True
        return say("left", f, "not our link any more") or True
    if k == "line-removed":
        text = read_text(f)
        if e["text"] not in text.splitlines():
            write_text(f, text + ("" if text.endswith("\n") or not text else "\n") + e["text"] + "\n")
        return say("undo", f, "line restored") or True
    if k == "line-added":
        lines = read_text(f).splitlines()
        if e["text"] in lines:
            lines.remove(e["text"])
            write_text(f, "\n".join(lines) + ("\n" if lines else ""))
        return say("undo", f, "line removed") or True
    if k == "hook-removed":
        data, _ = load_json(f)
        hooks = data.setdefault("hooks", {})
        groups = hooks.setdefault(e["event"], [])
        handler = e["group"]["hooks"][0]
        if any(handler in (g.get("hooks") or []) for g in groups):
            return say("same", f, "%s hook already there" % e["event"]) or True
        meta = {k: v for k, v in e["group"].items() if k != "hooks"}
        gi = e.get("gi", len(groups))
        # Same group still there (same matcher etc.)? Put the handler back in its old slot.
        target = groups[gi] if gi < len(groups) else None
        if target is not None and {k: v for k, v in target.items() if k != "hooks"} == meta:
            target.setdefault("hooks", []).insert(min(e.get("hi", 0), len(target["hooks"])), handler)
        else:
            groups.insert(min(gi, len(groups)), e["group"])
        write_json(f, data)
        return say("undo", f, "%s hook restored" % e["event"]) or True
    if k == "cmd":
        rc = run(e["undo"], check=False)
        return say("undo" if rc == 0 else "failed", e["id"], shlex.join(e["undo"])) or rc == 0
    return say("skip", f or e.get("id"), "unknown kind " + k) or False


# ---------------------------------------------------------------- MCP translation

def mcp_specs(mcp_json, plugin_root, agent):
    """Yield (name, {command, args, env, url}) from the plugin .mcp.json, resolved for one agent."""
    data, _ = load_json(mcp_json)
    for name, s in (data.get("mcpServers") or {}).items():
        def ex(v):
            v = v.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
            return re.sub(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}",
                          lambda m: os.environ.get(m.group(1), m.group(2) or ""), v)
        args = [ex(x) for x in s.get("args") or []]
        if name == "serena":
            args = [re.sub(r"^--context=.*", "--context=" + SERENA_CONTEXT[agent], x) for x in args]
        yield name, {
            "command": ex(s.get("command", "")),
            "args": args,
            "env": {k: ex(v) for k, v in (s.get("env") or {}).items()},
            "url": ex(s.get("url", "")) if s.get("url") else "",
        }


def codex_register(name, spec, prefix):
    got = capture(prefix + ["codex", "mcp", "get", name, "--json"])
    if got is not None and spec_matches(got, spec):
        return say("same", "codex mcp", name)
    if got is not None:
        run(prefix + ["codex", "mcp", "remove", name])
    if spec["url"]:
        add = ["codex", "mcp", "add", name, "--url", spec["url"]]
    else:
        add = ["codex", "mcp", "add", name]
        for k, v in spec["env"].items():
            add += ["--env", "%s=%s" % (k, v)]
        add += ["--", spec["command"]] + spec["args"]
    run(prefix + add)
    if got is None:
        record({"kind": "cmd", "id": "codex-mcp:%s" % name, "undo": prefix + ["codex", "mcp", "remove", name]},
               key="cmd:codex-mcp:%s" % name)
    say("mcp", "codex", "%s %s" % ("replaced" if got is not None else "added", name))


def hermes_register(name, spec, prefix):
    def sh(cmd):
        return prefix + ["bash", "-lc", shlex.join(cmd)] if prefix else cmd
    listing = capture(sh(["hermes", "mcp", "list"])) or ""
    known = re.search(r"(^|\W)%s(\W|$)" % re.escape(name), listing) is not None
    if spec["url"]:
        add = ["hermes", "mcp", "add", name, "--url", spec["url"]]
    else:
        add = ["hermes", "mcp", "add", name, "--command", spec["command"]]
        for k, v in spec["env"].items():
            add += ["--env", "%s=%s" % (k, v)]
        if spec["args"]:
            add += ["--args"] + spec["args"]
    if known:
        run(sh(["hermes", "mcp", "remove", name]), check=False)
    run(sh(add))
    if not known:
        record({"kind": "cmd", "id": "hermes-mcp:%s" % name, "undo": sh(["hermes", "mcp", "remove", name])},
               key="cmd:hermes-mcp:%s" % name)
    say("mcp", "hermes", "%s %s" % ("re-registered" if known else "added", name))


def spec_matches(got, spec):
    if spec["url"]:
        return spec["url"] in got
    needles = [spec["command"]] + spec["args"] + ["%s" % v for v in spec["env"].values()] + list(spec["env"].keys())
    return all(json.dumps(n)[1:-1] in got or n in got for n in needles)


# ---------------------------------------------------------------- helpers

def signature(cmd):
    for s in ADOPT_SIGNATURES:
        if s in cmd:
            return s
    return " ".join(cmd.split())


def block_regex(name):
    return re.compile(r"<!-- AI:%s v\d+ START -->.*?<!-- AI:%s v\d+ END -->" % (re.escape(name), re.escape(name)),
                      re.S)


def toml_table_span(lines, table):
    """Return (first line after header, end) of a table; root = before the first header."""
    hdr = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*(#.*)?$")
    if not table:
        end = next((i for i, l in enumerate(lines) if hdr.match(l)), len(lines))
        return 0, end
    for i, l in enumerate(lines):
        m = hdr.match(l)
        if m and m.group(1).strip() == table and not l.strip().startswith("[["):
            end = next((j for j in range(i + 1, len(lines)) if hdr.match(lines[j])), len(lines))
            return i + 1, end
    return None, None


def split_path(p):
    return [x for x in p.split("/") if x]


def get_path(d, path):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return False, None
        cur = cur[k]
    return True, cur


def set_path(d, path, v):
    cur = d
    for k in path[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    cur[path[-1]] = v


def del_path(d, path):
    chain = [d]
    for k in path[:-1]:
        chain.append(chain[-1].get(k, {}))
    chain[-1].pop(path[-1], None)
    for i in range(len(path) - 1, 0, -1):  # drop parents we emptied
        if chain[i] == {}:
            chain[i - 1].pop(path[i - 1], None)


def strip_jsonc(s):
    out, i, n, in_str = [], 0, len(s), False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True; out.append(c)
        elif s.startswith("//", i):
            while i < n and s[i] != "\n":
                i += 1
            continue
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def has_comments(raw):
    return strip_jsonc(raw) != re.sub(r",(\s*[}\]])", r"\1", raw)


def load_json(path, jsonc=False):
    raw = read_text(path)
    if not raw.strip():
        return {}, raw
    try:
        return json.loads(raw), raw
    except ValueError:
        if jsonc:
            return json.loads(strip_jsonc(raw)), raw
        raise SystemExit("aiconf: %s is not valid JSON, not touching it" % path)


def write_json(path, data, mode=""):
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", mode)


def read_text(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write_text(path, text, mode=""):
    path = os.path.expanduser(path)
    if DRY:
        return
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    old_mode = os.stat(path).st_mode & 0o7777 if os.path.exists(path) else None
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".aiconf.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mode:
        os.chmod(tmp, int(mode, 8))
    elif old_mode is not None:
        os.chmod(tmp, old_mode)
    else:
        os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def backup_path(path):
    base = os.path.join(os.path.dirname(STATE_PATH), "backup", time.strftime("%Y%m%d-%H%M%S"))
    return os.path.join(base, path.lstrip("/").replace("/", "__"))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short(v):
    s = json.dumps(v)
    return s if len(s) < 80 else s[:77] + "..."


def say(action, target, detail):
    print("  %s%-7s %s %s" % ("[dry-run] " if DRY and action not in ("same", "skip", "left") else "",
                              action, target, detail))


def run(argv, check=True):
    if DRY:
        print("  [dry-run] " + shlex.join(argv))
        return 0
    rc = subprocess.call(argv, stdin=subprocess.DEVNULL)
    if rc != 0 and check:
        raise SystemExit("aiconf: command failed (%d): %s" % (rc, shlex.join(argv)))
    return rc


def capture(argv):
    """Run a read-only command; return stdout or None when it fails or the binary is missing."""
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           universal_newlines=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


# ---------------------------------------------------------------- state

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {"version": 1, "entries": []}


def save_state(st):
    if DRY:
        return
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_PATH), prefix=".state.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATE_PATH)


def record(entry, key, keep_first=("prev", "had", "existed")):
    """Add or update one entry. The first record keeps the original previous value."""
    if DRY:
        return
    st = load_state()
    entry["key"] = key
    entry["time"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for i, e in enumerate(st["entries"]):
        if e.get("key") == key:
            for k in keep_first:
                if k in e:
                    entry[k] = e[k]
            st["entries"][i] = entry
            break
    else:
        st["entries"].append(entry)
    save_state(st)


if __name__ == "__main__":
    main()
