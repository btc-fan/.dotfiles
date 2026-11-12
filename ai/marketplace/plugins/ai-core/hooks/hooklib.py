"""hooklib: shared helpers for router.py: shell command parsing, the gates, and the project knowledge status
(the Map and Libraries blocks of the repo AGENTS.md; Serena and graphify only where a project enabled them).

Gates catch honest mistakes. They are not a sandbox against an adversary (known limits: README.md).

Shell parsing (parse_command): a small tokenizer that knows quotes, escapes, heredocs, $( ), `...`,
<( ), redirections and the operators && || ; | & ( ). Each simple command becomes a Stage:
  exe (basename), args, quoted flags, env assignments, wrappers (sudo, env, timeout, xargs, ...),
  op (the operator after it), nxt (the next stage at the same level).
"bash -c '...'", "sh -c", "eval" arguments are parsed one level deeper.
Quoted words are never read as commands, so a commit message or echo text cannot trigger a gate.
"""
import json
import os
import re
import time

DAY = 86400
OPS = {"&&", "||", ";;", "|&", ";", "|", "&", "(", ")"}
SHELLS = re.compile(r"^(ba|z|da|k|fi)?sh$")
INTERPRETERS = re.compile(r"^((ba|z|da|k|fi)?sh|python[\d.]*|node|perl|ruby|php)$")
WRAPPERS_WITH_VALUES = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "--user", "--group"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "--unset", "--chdir"},
    "xargs": {"-n", "-I", "-L", "-P", "-d", "-a", "-E", "-s", "--max-args", "--max-procs", "--delimiter"},
    "nice": {"-n"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
}
PLAIN_WRAPPERS = {"command", "time", "nohup", "exec", "then", "do", "else", "!", "builtin", "stdbuf"}


# ---------------------------------------------------------------- shell parsing

class Stage(object):
    def __init__(self, words, op):
        self.words = words            # [(text, quoted)]
        self.op = op                  # operator after this stage, or ""
        self.nxt = None
        self.env = {}
        self.wrappers = []
        self.inner_text = ""          # the -c / eval text for shells
        rest = strip_wrappers(list(words), self)
        self.exe = os.path.basename(rest[0][0]) if rest else ""
        self.args = [w for w, _q in rest[1:]]
        self.quoted = [q for _w, q in rest[1:]]

    def text(self):
        """Command text without quoted words (for rule regexes)."""
        if not self.exe:
            return ""
        return " ".join([self.exe] + [a for a, q in zip(self.args, self.quoted) if not q])


def parse_command(cmd, depth=0):
    """Flat list of Stages (inner -c / eval stages after their parent). Never raises."""
    try:
        toks = tokenize(cmd or "")
    except Exception:
        toks = [(w, False) for w in (cmd or "").split()]
    stages = split_stages(toks)
    out = []
    for st in stages:
        out.append(st)
        inner = shell_inner_text(st)
        if inner is not None and depth < 2:
            st.inner_text = inner
            out.extend(parse_command(inner, depth + 1))
    return out


def command_text(stages):
    """Normalized text: stages joined by their operators, quoted words dropped."""
    parts = []
    for st in stages:
        t = st.text()
        if t:
            parts.append(t)
            if st.op and st.op not in ("(", ")"):
                parts.append(st.op)
    return " ".join(parts)


def tokenize(s):
    toks = []
    cur, state = [], {"quoted": False, "have": False}
    heredocs = []
    in_bt = False
    i, n = 0, len(s)

    def flush():
        if state["have"]:
            toks.append(("".join(cur), state["quoted"]))
        del cur[:]
        state["quoted"] = state["have"] = False

    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 < n and s[i + 1] == "\n":
                i += 2
                continue
            if i + 1 < n:
                cur.append(s[i + 1])
                state["have"] = True
            i += 2
            continue
        if c == "'":
            j = s.find("'", i + 1)
            j = n if j < 0 else j
            cur.append(s[i + 1:j])
            state["quoted"] = state["have"] = True
            i = j + 1
            continue
        if c == '"':
            j, buf = i + 1, []
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j + 1])
                    j += 2
                    continue
                buf.append(s[j])
                j += 1
            cur.append("".join(buf))
            state["quoted"] = state["have"] = True
            i = j + 1
            continue
        if c in " \t\r":
            flush()
            i += 1
            continue
        if c == "\n":
            flush()
            toks.append((";", None))
            i += 1
            for delim in heredocs:          # skip heredoc bodies
                m = re.compile(r"^[ \t]*" + re.escape(delim) + r"[ \t]*$", re.M).search(s, i)
                i = m.end() if m else n
            heredocs = []
            continue
        if c == "#" and not state["have"]:
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "$" and s.startswith("$(", i) and not s.startswith("$((", i):
            flush()
            toks.append(("(", None))
            i += 2
            continue
        if c == "`":
            flush()
            toks.append((")" if in_bt else "(", None))
            in_bt = not in_bt
            i += 1
            continue
        if c in "<>":
            if s.startswith("<<", i) and not s.startswith("<<<", i):
                flush()
                j = i + 2 + (1 if s.startswith("<<-", i) else 0)
                m = re.match(r"\s*(['\"]?)([\w.-]+)\1", s[j:])
                if m:
                    heredocs.append(m.group(2))
                    i = j + m.end()
                    continue
            if s.startswith("<(", i) or s.startswith(">(", i):
                flush()
                toks.append(("(", None))
                i += 2
                continue
            word = "".join(cur)
            if state["have"] and not state["quoted"] and word.isdigit():
                del cur[:]
                state["have"] = False
            else:
                flush()
            j = i
            while j < n and s[j] in "<>&":
                j += 1
            toks.append((s[i:j], "redir"))
            i = j
            continue
        if c in "&|;()":
            flush()
            two = s[i:i + 2]
            if two == "&>":
                toks.append((two, "redir"))
                i += 2
            elif two in ("&&", "||", ";;", "|&"):
                toks.append((two, None))
                i += 2
            else:
                toks.append((c, None))
                i += 1
            continue
        cur.append(c)
        state["have"] = True
        i += 1
    flush()
    return toks


def split_stages(toks):
    stages, words, skip_next = [], [], False
    for text, kind in toks:
        if skip_next and kind is not None and kind != "redir" and text not in OPS:
            skip_next = False
            continue
        skip_next = False
        if kind == "redir":
            skip_next = True
            continue
        if kind is None and text in OPS:
            stages.append(Stage(words, text))
            words = []
            continue
        words.append((text, bool(kind)))
    stages.append(Stage(words, ""))
    stages = [s for s in stages if s.exe or s.op in ("(",)]
    for a, b in zip(stages, stages[1:]):
        a.nxt = b
    return stages


def strip_wrappers(words, stage):
    """Drop env assignments and wrappers (sudo -u x, env A=1, timeout 5, xargs -n1, ...)."""
    while words:
        head, quoted = words[0]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", head, re.S)
        if m:
            stage.env[m.group(1)] = m.group(2)
            words.pop(0)
            continue
        base = os.path.basename(head)
        if base in PLAIN_WRAPPERS:
            words.pop(0)
            continue
        if base in WRAPPERS_WITH_VALUES:
            stage.wrappers.append(base)
            words.pop(0)
            value_opts = WRAPPERS_WITH_VALUES[base]
            while words and (words[0][0].startswith("-") or (base == "env" and "=" in words[0][0])):
                opt = words.pop(0)[0]
                if "=" in opt and base == "env":
                    k, v = opt.split("=", 1)
                    stage.env[k] = v
                if opt in value_opts and words:
                    words.pop(0)
            if base == "timeout" and words and re.match(r"^\d+[smhd]?$", words[0][0]):
                words.pop(0)
            continue
        break
    return words


def shell_inner_text(st):
    if st.exe == "eval":
        return " ".join(st.args)
    if SHELLS.match(st.exe):
        for i, a in enumerate(st.args):
            if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a) and i + 1 < len(st.args):
                return st.args[i + 1]
    return None


# ---------------------------------------------------------------- escape hatch (owner only)
# A gate is skipped only through the root-owned file /etc/ai/gate-skip, written by the owner with
# `sudo ai-gate-skip <gate> <minutes, max 60> <why>`. Agents have no sudo, so they cannot produce it.
# Line format: <gate> <expiry, unix seconds> <reason...>. The old in-command AI_GATE_SKIP=... is ignored.
GATE_SKIP_FILE = "/etc/ai/gate-skip"
GATE_SKIP_MAX_S = 3600


def gate_skip_path():
    """Tests only: AI_GATE_SKIP_FILE together with AI_GATE_SKIP_INSECURE_TEST=1 (the hook's own environment,
    which an agent's command cannot set)."""
    if os.environ.get("AI_GATE_SKIP_INSECURE_TEST") == "1" and os.environ.get("AI_GATE_SKIP_FILE"):
        return os.environ["AI_GATE_SKIP_FILE"], True
    return GATE_SKIP_FILE, False


def gate_skips(stages=None):
    """({gate: reason} valid now, [notes]). Only a root-owned file not writable by others counts."""
    skips, notes = {}, []
    if stages and any("AI_GATE_SKIP" in st.env for st in stages):
        notes.append("AI_GATE_SKIP in a command does nothing. Only the owner can skip a gate: "
                     "sudo ai-gate-skip <gate> <minutes> <why>.")
    path, test = gate_skip_path()
    try:
        st = os.stat(path)
    except OSError:
        return skips, notes
    if not test and (st.st_uid != 0 or st.st_mode & 0o022):
        notes.append("%s is not root-owned or is writable by others: ignored." % path)
        return skips, notes
    now = time.time()
    for line in (read_text(path) or "").splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or not re.match(r"^[a-z0-9-]+$", parts[0]):
            continue
        try:
            expiry = float(parts[1])
        except ValueError:
            continue
        if now < expiry <= now + GATE_SKIP_MAX_S:
            skips[parts[0]] = parts[2].strip()
    return skips, notes


# ---------------------------------------------------------------- audit-before-install

ASK_MANAGERS = ("brew", "cargo", "go", "gem", "pipx")
NPM_LIKE = ("npm", "pnpm", "yarn", "bun")
NPM_VALUE_OPTS = {
    "npm": {"--registry", "--prefix", "-w", "--workspace", "--tag", "--save-prefix", "--cache", "-C"},
    "pnpm": {"-C", "--dir", "--filter", "-F", "--registry", "--store-dir"},
    "yarn": {"--cwd", "--registry", "--cache-folder"},
    "bun": {"--cwd", "--registry", "-c", "--config"},
}
PIP_VALUE_OPTS = {"-c", "--constraint", "-i", "--index-url", "--extra-index-url", "-t", "--target",
                  "--prefix", "--root", "-f", "--find-links", "--python", "-p", "--src", "--trusted-host",
                  "--cache-dir", "--log", "--proxy", "--platform", "--python-version", "--implementation",
                  "--abi", "--only-binary", "--no-binary", "--progress-bar", "--report"}
UV_VALUE_OPTS = {"--group", "--optional", "--index", "--index-url", "--default-index", "--python", "-p",
                 "--package", "--extra", "--rev", "--tag", "--branch", "--directory", "--project",
                 "--with-editable", "--constraint", "-c", "--override"}
UV_TARGET_OPTS = {"--from", "--with", "-w", "--with-requirements"}


def runs_stdin_as_code(st):
    """True when an interpreter reads its PROGRAM from stdin: `sh`, `bash -s`, `python3`, `python3 -`, `node`.
    With an inline program (-c/-e), a module (-m) or a script file, stdin is only data (curl ... | python3 -c
    'import json...' reads metadata, it runs nothing downloaded)."""
    args = st.args
    if SHELLS.match(st.exe):
        if any(re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a) for a in args):
            return False
        return not [a for a in args if not a.startswith("-")] or any(re.match(r"^-[a-zA-Z]*s", a) for a in args)
    if any(a in ("-c", "-e", "-m", "-E", "--eval", "-p", "--print", "-r") or re.match(r"^-[a-zA-Z]*[cem]$", a)
           for a in args):
        return False
    positional = [a for a in args if not a.startswith("-") or a == "-"]
    return not positional or positional[0] == "-"


def curl_to_shell(stages):
    """True when a download is executed: curl|sh, curl|sudo bash, bash <(curl), sh -c "$(curl)"."""
    for st in stages:
        nxt = st.nxt
        if (st.exe in ("curl", "wget") and st.op in ("|", "|&") and nxt and INTERPRETERS.match(nxt.exe)
                and runs_stdin_as_code(nxt)):
            return True
        if SHELLS.match(st.exe) and st.op == "(" and nxt and nxt.exe in ("curl", "wget"):
            return True
        if st.inner_text and re.match(r"^\s*(\$\(|`)\s*(curl|wget)\b", st.inner_text):
            return True
    return False


def npx_latest(stages):
    for st in stages:
        if st.exe in ("npx", "bunx") or (st.exe in ("pnpm",) and st.args[:1] == ["dlx"]):
            if any(re.search(r"@(latest|next)$", a) for a in st.args if not a.startswith("-")):
                return True
    return False


def install_targets(stages, cwd):
    """(ecosystem, name, version) per package. ecosystem npm | pypi | dir (manifest/lockfile install) |
    unknown (cannot tell what gets installed) | brew | cargo | go | gem | pipx."""
    out = []
    for st in stages:
        out.extend(stage_targets(st.exe, list(st.args), st, cwd))
    return out


def stage_targets(exe, args, st, cwd):
    if exe == "uv" and args[:1] == ["run"]:
        rest = skip_options(args[1:], UV_VALUE_OPTS | UV_TARGET_OPTS)
        return stage_targets(os.path.basename(rest[0]), rest[1:], st, cwd) if rest else []
    if re.match(r"^python[\d.]*$", exe):
        rest = list(args)
        while rest and rest[0].startswith("-") and rest[0] != "-m":
            rest.pop(0)
        if rest[:2] == ["-m", "pip"]:
            exe, args = "pip", rest[2:]
        else:
            return []
    if re.match(r"^pip[\d.]*$", exe):
        exe = "pip"
    via_xargs = "xargs" in st.wrappers
    if exe in NPM_LIKE:
        vopts = NPM_VALUE_OPTS[exe]
        i = first_positional(args, vopts)
        if i is None:
            return []
        if exe == "yarn" and args[i] == "global":
            sub_args = args[i + 1:]
            j = first_positional(sub_args, vopts)
            if j is None or sub_args[j] != "add":
                return []
            pkgs = positional(sub_args[j + 1:], vopts)
        elif args[i] in ("i", "install", "add", "ci"):
            pkgs = positional(args[i + 1:], vopts) if args[i] != "ci" else []
        else:
            return []
        if via_xargs:
            return [("unknown", exe + " via xargs", "")]
        if not pkgs:
            return [dir_target(cwd)]
        return [npm_or_path(p, cwd) for p in pkgs]
    if exe == "pip":
        i = first_positional(args, PIP_VALUE_OPTS)
        if i is None or args[i] != "install":
            return []
        return [("unknown", "pip via xargs", "")] if via_xargs else pip_targets(args[i + 1:], cwd)
    if exe == "uv":
        if args[:1] == ["add"]:
            return uv_targets(args[1:], cwd)
        if args[:2] == ["pip", "install"]:
            return pip_targets(args[2:], cwd)
        if args[:2] == ["tool", "install"]:
            return uv_targets(args[2:], cwd)
        return []
    if exe in ("brew", "gem", "pipx") and args[:1] == ["install"]:
        return [(exe, p, "") for p in positional(args[1:], set())] or [(exe, "", "")]
    if exe == "cargo" and args[:1] and args[0] in ("add", "install"):
        return [("cargo", p, "") for p in positional(args[1:], {"--version", "--git", "--path"})] or [("cargo", "", "")]
    if exe == "go" and args[:1] == ["install"]:
        return [("go", p, "") for p in positional(args[1:], set())] or [("go", "", "")]
    return []


def pip_targets(args, cwd):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        m = re.match(r"^(-r|--requirement|-e|--editable)(=?)(.*)$", a)
        if m:
            out.append(dir_target(cwd))
            i += 1 if (m.group(3) or m.group(2)) else 2
            continue
        if a in PIP_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-") or a == "@":
            i += 1
            continue
        out.append(pip_spec_target(a, cwd))
        i += 1
    return out


def uv_targets(args, cwd):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        opt, eq, val = a.partition("=")
        if opt in UV_TARGET_OPTS:
            value = val if eq else (args[i + 1] if i + 1 < len(args) else "")
            if opt == "--with-requirements":
                out.append(dir_target(cwd))
            else:
                out.extend(pip_spec_target(v, cwd) for v in value.split(",") if v)
            i += 1 if eq else 2
            continue
        if a in UV_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        out.append(pip_spec_target(a, cwd))
        i += 1
    return out


def pip_spec_target(spec, cwd):
    if re.match(r"^[a-z+]+://", spec) or spec.startswith("git+"):
        return ("unknown", spec, "")
    if spec in (".", "..") or spec.startswith(("./", "/", "../", "~")) or spec.endswith((".whl", ".tar.gz", ".zip")):
        return dir_target(cwd)
    return ("pypi",) + pypi_spec(spec)


def npm_or_path(spec, cwd):
    if re.match(r"^(https?|git\+\w+|git|github|file):", spec):
        return ("unknown", spec, "")
    if spec.startswith(("./", "/", "../", "~")) or spec.endswith((".tgz", ".tar.gz")):
        return dir_target(cwd)
    return ("npm",) + npm_spec(spec)


def first_positional(args, value_opts):
    skip = False
    for i, a in enumerate(args):
        if skip:
            skip = False
            continue
        if a in value_opts:
            skip = True
            continue
        if a.startswith("-"):
            continue
        return i
    return None


def positional(args, value_opts):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in value_opts:
            skip = True
            continue
        if a.startswith("-") or a == "\\":
            continue
        out.append(a)
    return out


def skip_options(args, value_opts):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in value_opts else 1
    return args[i:]


def npm_spec(spec):
    at = spec.rfind("@")
    name, ver = (spec[:at], spec[at + 1:]) if at > 0 else (spec, "")
    if ver in ("latest", "next", "*"):
        ver = ""
    return (name.lower(), ver)


def pypi_spec(spec):
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(==\s*([^,;\s]+))?", spec)
    if not m:
        return (spec.lower(), "")
    return (norm_pypi(m.group(1)), m.group(4) or "")


def norm_pypi(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def dir_target(cwd):
    root = project_root(cwd) or cwd
    return ("dir", os.path.realpath(root), "")


def gate_audit(ctx, cmd, stages):
    blocks, asks, unknown = [], [], []
    if curl_to_shell(stages):
        blocks.append("a download piped or passed to a shell is not allowed. Download, check the checksum, audit, then run.")
    if npx_latest(stages):
        blocks.append("npx ...@latest is not allowed. Pin an exact version that passed agent-audit.")
    targets = install_targets(stages, ctx.cwd)
    if not targets and not blocks:
        return ("ask", "Install command, but the package could not be parsed. Run agent-audit on it first.")
    for eco, name, version in targets:
        if eco in ASK_MANAGERS:
            asks.append("%s install of %s: agent-audit cannot scan %s packages yet." % (eco, name or "?", eco))
        elif eco == "unknown":
            unknown.append(name)
        else:
            status = audit_status(eco, name, version)
            if status != "PASS":
                why = "the last agent-audit FAILED" if status == "FAIL" else "no agent-audit PASS in the last 24 h"
                blocks.append("%s for %s %s%s. Run: %s" % (why, eco, name, ("@" + version) if version else "",
                                                           audit_hint(eco, name, version)))
    if blocks:
        return ("deny", "Blocked: " + " | ".join(blocks))
    if unknown:
        asks.append("cannot tell which package gets installed (%s). Audit it first." % ", ".join(unknown)[:200])
    if asks:
        return ("ask", " | ".join(asks) + " Owner: confirm this install.")
    return None


def probe_audit(stages, cmd=""):
    return curl_to_shell(stages) or npx_latest(stages) or bool(install_targets(stages, "."))


def audit_status(eco, name, version):
    """Latest audit.log line for this package within 24 h: PASS, FAIL or None.
    Line format (agent-audit): <iso-time> <ecosystem> <name> <version|-> PASS|FAIL"""
    text = read_text(state_path("audit.log")) or ""
    want = norm_pypi(name) if eco == "pypi" else name
    now = time.time()
    for line in reversed(text.splitlines()):
        parts = line.split()
        if len(parts) < 5 or parts[1] != eco:
            continue
        ts, lname, lver, result = parts[0], parts[2], parts[3], parts[4]
        lname = norm_pypi(lname) if eco == "pypi" else (os.path.realpath(lname) if eco == "dir" else lname.lower())
        if lname != want:
            continue
        if version and lver not in ("-", "", version):
            continue
        return result if now - parse_iso(ts) <= DAY else None
    return None


def audit_hint(eco, name, version):
    if eco == "dir":
        return "agent-audit dir %s" % name
    return "agent-audit %s %s%s" % (eco, name, (" " + version) if version else "")


# ---------------------------------------------------------------- secret-scan

NAME = r"[A-Za-z0-9_.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|access[_-]?key|private[_-]?key|credential)[A-Za-z0-9_.-]*"
SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("pypi-token", re.compile(r"\bpypi-AgE[A-Za-z0-9_-]{50,}")),
    ("huggingface-token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("webhook-url", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"
                               r"|https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("llm-api-key", re.compile(r"\bsk-(?:ant-|proj-|or-v1-)?[A-Za-z0-9_-]{32,}\b")),
    ("stripe-live-key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}\b")),
    ("telegram-bot-token", re.compile(r"\b\d{8,10}:AA[0-9A-Za-z_-]{33}\b")),
    ("context7-key", re.compile(r"\bctx7sk-[A-Za-z0-9-]{20,}")),
    ("url-with-password", re.compile(r"\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@'\"]+:([^\s:/@'\"]{4,})@[^\s/'\"]+")),
    ("assigned-secret", re.compile(r"(?i)\b" + NAME + r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']")),
    ("assigned-secret-unquoted",
     re.compile(r"(?i)(?:^\+?|[\s,{;])" + NAME + r"\s*[:=]\s*([^\s\"'#,;{}()\[\]]{16,})\s*(?:$|[#,;}])")),
]
PLACEHOLDER = re.compile(r"(?i)(x{4,}|\*{3,}|\.{3,}|changeme|change[_-]?me|example\S*|your[\w-]*|dummy\S*|redacted|"
                         r"placeholder\S*|todo|none|null|true|false|password|pass|secret|pwd|test|fake\S*|"
                         r"<[^>]*>|\$\{[^}]*\}|\$\(.*\)|\{\{.*\}\})")


class ScanTimeout(Exception):
    pass


class Budget(object):
    """Secret-scan time budget: total under 20 s (hook timeout 25 s); git 5 s and gitleaks 10 s per call."""

    def __init__(self):
        self.end = time.time() + float(os.environ.get("AI_SCAN_BUDGET_S") or 18)

    def take(self, cap):
        left = self.end - time.time()
        if left <= 0.2:
            raise ScanTimeout()
        return min(cap, left)


def gate_secrets(ctx, cmd, stages):
    actions = git_actions(stages, ctx.cwd, cmd)
    if not actions:
        return None
    try:
        hits, what = scan_actions(actions, Budget())
    except ScanTimeout:
        return ("deny", "Secret scan timed out, nothing was checked. Run gitleaks yourself (gitleaks git --staged "
                "or gitleaks git). If it is clean, the owner can run: sudo ai-gate-skip secret-scan 10 <why>.")
    if not hits:
        return None
    return ("deny", "Secret scan found: %s. Remove it from the %s before you commit or push." % (
        ", ".join(sorted(set(hits))[:8]), " and ".join(sorted(what))))


def scan_actions(actions, budget):
    allowed = allowed_secrets()
    hits, what = [], set()
    for act in actions:
        repo = project_root(act["dir"])
        if repo is None:
            continue
        if act["sub"] == "commit":
            text = scan_git(repo, ["diff", "--cached", "--no-color", "-U0"], budget)
            if act["worktree"]:
                text += scan_git(repo, ["diff", "--no-color", "-U0"], budget) + untracked_text(repo, budget)
            what.add("files to commit")
            hits.extend(gitleaks_scan(repo, "commit", None, allowed, budget))
            msg = message_text(act, repo)
            if msg:
                msg_hits = builtin_scan(as_added(msg), allowed)
                if msg_hits:
                    what.add("commit message")
                    hits.extend(msg_hits)
        else:
            text = scan_git(repo, ["log", "-p", "--no-color", "-U0", "-n", "300", "HEAD", "--not", "--remotes"], budget)
            what.add("unpushed commits")
            hits.extend(gitleaks_scan(repo, "push", "-n 300 HEAD --not --remotes", allowed, budget))
        hits.extend(builtin_scan(text, allowed))
    return hits, what


def scan_git(repo, args, budget):
    """git output for the scan; a timeout raises ScanTimeout (deny), other errors give "" (not a repo)."""
    import subprocess
    try:
        res = subprocess.run(["git", "-C", repo] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=budget.take(5))
    except subprocess.TimeoutExpired:
        raise ScanTimeout()
    except OSError as exc:
        log_error("git", exc)
        return ""
    return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else ""


def probe_secrets(stages, cmd=""):
    return bool(git_actions(stages, "."))


GIT_GLOBAL_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
COMMIT_VALUE_LETTERS = set("mFCct")
COMMIT_LONG_VALUE = {"--message", "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash", "--author",
                     "--date", "--template", "--cleanup", "--trailer", "--pathspec-from-file", "-S", "--gpg-sign"}


def git_actions(stages, cwd, raw_cmd=""):
    """Ordered commit/push actions with their repo dir; commit.worktree = also scan unstaged + untracked files
    (git add earlier in the command, commit -a, or a commit pathspec). commit.messages = -m values,
    commit.message_files = -F paths ("-" = stdin: the raw command text is scanned, it holds the heredoc)."""
    base, saw_add, out = cwd, False, []
    for st in stages:
        if st.exe in ("cd", "pushd") and st.args:
            base = os.path.join(base, os.path.expanduser(st.args[0]))
            continue
        if st.exe != "git":
            continue
        args, gdir, i = st.args, base, 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] == "-C" and i + 1 < len(args):
                gdir = os.path.join(gdir, os.path.expanduser(args[i + 1]))
            i += 2 if args[i] in GIT_GLOBAL_VALUE else 1
        if i >= len(args):
            continue
        sub, rest = args[i], args[i + 1:]
        if sub == "add":
            saw_add = True
        elif sub == "commit":
            all_flag, pathspec = commit_flags(rest)
            messages, files = commit_messages(rest)
            out.append({"sub": "commit", "dir": gdir, "worktree": saw_add or all_flag or pathspec,
                        "messages": messages, "message_files": files, "raw": raw_cmd})
        elif sub == "push":
            out.append({"sub": "push", "dir": gdir, "worktree": False})
    return out


def commit_flags(rest):
    all_flag, pathspec, i = False, False, 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            pathspec = pathspec or i + 1 < len(rest)
            break
        if a.startswith("--"):
            if a in ("--all",):
                all_flag = True
            if a in COMMIT_LONG_VALUE:
                i += 1
        elif a.startswith("-") and len(a) > 1:
            for k, letter in enumerate(a[1:]):
                if letter == "a":
                    all_flag = True
                if letter in COMMIT_VALUE_LETTERS:
                    if k == len(a) - 2:
                        i += 1          # value is the next word
                    break               # else the value is attached
        else:
            pathspec = True
        i += 1
    return all_flag, pathspec


def commit_messages(rest):
    """-m/--message values and -F/--file paths of a git commit (attached forms too: -mtext, -Ffile, --file=x)."""
    msgs, files, i = [], [], 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            break
        nxt = rest[i + 1] if i + 1 < len(rest) else None
        opt, eq, val = a.partition("=")
        if opt in ("--message", "--file") and a.startswith("--"):
            value = val if eq else nxt
            if value is not None:
                (msgs if opt == "--message" else files).append(value)
            elif opt == "--file":
                files.append("-")
            i += 1 if eq else 2
            continue
        if a.startswith("-") and not a.startswith("--") and len(a) > 1:
            for k, letter in enumerate(a[1:]):
                if letter in COMMIT_VALUE_LETTERS:
                    attached = a[k + 2:]
                    value = attached if attached else nxt
                    if letter == "m" and value is not None:
                        msgs.append(value)
                    elif letter == "F":
                        files.append(value if value is not None else "-")   # -F <(...): the file is a pipe
                    if not attached:
                        i += 1
                    break
        i += 1
    return msgs, files


def message_text(act, repo, max_bytes=256 * 1024):
    """The commit message text the command will use: -m values, -F file contents, stdin heredoc (raw command)."""
    parts = list(act.get("messages") or [])
    for path in act.get("message_files") or []:
        # stdin, a pipe or a process substitution: the text is in the command itself (heredoc, <(echo ...)).
        if path in ("-", "/dev/stdin") or path.startswith(("/dev/fd/", "/proc/self/fd/")):
            parts.append(act.get("raw") or "")
            continue
        full = os.path.join(act["dir"] or repo, os.path.expanduser(path))
        try:
            with open(full, "rb") as fh:
                parts.append(fh.read(max_bytes).decode("utf-8", "replace"))
        except OSError:
            continue
    return "\n".join(p for p in parts if p)


def as_added(text):
    """Text as added diff lines, so builtin_scan reads every line."""
    return "\n".join("+" + ln for ln in text.splitlines())


def untracked_text(repo, budget, max_files=300, max_bytes=512 * 1024):
    names = scan_git(repo, ["ls-files", "-o", "--exclude-standard", "-z"], budget).split("\0")
    out = []
    for name in [n for n in names if n][:max_files]:
        try:
            with open(os.path.join(repo, name), "rb") as fh:
                data = fh.read(max_bytes)
        except OSError:
            continue
        if b"\0" in data:
            continue
        out.append("+++ b/%s" % name)
        out.extend("+" + ln for ln in data.decode("utf-8", "replace").splitlines())
    return "\n".join(out) + "\n"


def builtin_scan(diff, allowed):
    hits = []
    for line in (diff or "").splitlines():
        if not line.startswith("+") or re.match(r"^\+\+\+ (a/|b/|/dev/null)", line):
            continue
        for name, rx in SECRET_PATTERNS:
            for mm in rx.finditer(line):
                value = mm.group(1) if rx.groups else mm.group(0)
                if value in allowed:
                    continue
                if name.startswith(("assigned-secret", "url-with-password")) and not looks_secret(value, name):
                    continue
                hits.append(name.replace("-unquoted", ""))
    return hits


def looks_secret(value, name):
    """Filter for name=value hits: placeholders, variables and plain identifiers are not secrets."""
    if PLACEHOLDER.fullmatch(value) or value[:1] in "$%<{":
        return False
    if name == "url-with-password":
        return True
    if name == "assigned-secret-unquoted":     # .env / YAML: must look random (letters + digits, no code)
        return bool(re.search(r"\d", value) and re.search(r"[A-Za-z]", value) and not re.search(r"[.(/]", value))
    return not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_.]+|[A-Z_][A-Z0-9_]*", value)


def gitleaks_scan(repo, mode, log_opts, allowed, budget):
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which("gitleaks")
    if not exe:
        return []
    fd, report = tempfile.mkstemp(prefix="ai-gitleaks-", suffix=".json")
    os.close(fd)
    try:
        args = [exe, "git", "--no-banner", "--exit-code", "0", "--report-format", "json", "--report-path", report]
        args += ["--staged", "--pre-commit"] if mode == "commit" else ["--log-opts", log_opts]
        args.append(repo)
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=budget.take(10))
        data = json.loads(read_text(report) or "[]")
    except subprocess.TimeoutExpired:
        raise ScanTimeout()
    except Exception as exc:
        log_error("gitleaks", exc)
        return []
    finally:
        try:
            os.unlink(report)
        except OSError:
            pass
    return ["gitleaks:%s" % f.get("RuleID", "?") for f in data if f.get("Secret") not in allowed]


def allowed_secrets():
    """The one owner-approved public key (SPEC 13), exact value only: ctx7sk-... values committed (HEAD) in
    our own MCP config, plus CONTEXT7_API_KEY in ~/.config/ai/secrets.env. Working-tree edits never count."""
    keys = set()
    home = ai_home()
    if home:
        rels = ["ai/marketplace/plugins/ai-core/.mcp.json", "ai/marketplace/plugins/ai-core/mcp", "ai/mcp"]
        names = git_out(home, ["ls-tree", "-r", "--name-only", "HEAD", "--"] + rels).split()
        for name in names[:200]:
            keys.update(re.findall(r"ctx7sk-[A-Za-z0-9-]{20,}", git_out(home, ["show", "HEAD:" + name])))
    env = read_text(os.path.expanduser("~/.config/ai/secrets.env")) or ""
    keys.update(re.findall(r"^\s*(?:export\s+)?CONTEXT7_API_KEY=[\"']?(ctx7sk-[A-Za-z0-9-]{20,})", env, re.M))
    return keys


# ---------------------------------------------------------------- pr-rules

def gate_pr(ctx, cmd, stages):
    missing_all = []
    for st in stages:
        if st.exe != "gh" or st.args[:1] != ["pr"] or len(st.args) < 2 or st.args[1] not in ("create", "edit"):
            continue
        args = st.args[2:]
        body_flag = any(a.split("=")[0] in ("--body", "-b", "--body-file", "-F", "--fill", "--fill-first",
                                            "--fill-verbose") for a in args)
        if st.args[1] == "edit" and not body_flag:
            continue
        text = " ".join(args)
        for i, a in enumerate(args):
            opt, eq, val = a.partition("=")
            if opt in ("--body-file", "-F"):
                path = val if eq else (args[i + 1] if i + 1 < len(args) else "-")
                if path != "-":
                    text += "\n" + (read_text(os.path.join(ctx.cwd, os.path.expanduser(path))) or "")
        if "<<" in cmd and "--body" in cmd:
            text += "\n" + cmd       # heredoc body inside $(cat <<EOF ...)
        missing = []
        if "```mermaid" not in text:
            missing.append("a ```mermaid diagram")
        if "<!-- author-sessions" not in text:
            missing.append("the <!-- author-sessions block")
        missing_all.extend(m for m in missing if m not in missing_all)
    if not missing_all:
        return None
    return ("deny", "PR body is missing %s. Body needs: summary, Mermaid diagram of the change, one-way or "
            "two-way door, blast radius, author-sessions block at the end. Pass it with --body or --body-file."
            % " and ".join(missing_all))


def probe_pr(stages, cmd=""):
    return any(st.exe == "gh" and st.args[:1] == ["pr"] and st.args[1:2] in (["create"], ["edit"]) for st in stages)


# ---------------------------------------------------------------- no-sudo

ROOT_TOOLS = {"sudo", "doas", "pkexec", "sudoedit", "su", "run0"}


def root_calls(cmd, depth=0):
    """[(tool, next words)] for every privilege tool at a command position, also inside bash -c / eval.
    Quoted words are text, never commands. Leading NAME=value words and plain wrappers are skipped."""
    out = []
    try:
        toks = tokenize(cmd or "")
    except Exception:
        toks = [(w, False) for w in (cmd or "").split()]
    at_cmd, after_wrapper = True, False
    for i, (text, kind) in enumerate(toks):
        if kind is None and text in OPS:
            at_cmd, after_wrapper = True, False
            continue
        if kind == "redir":
            continue
        if not at_cmd:
            continue
        if not kind and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", text):
            continue
        if after_wrapper and not kind and (text.startswith("-") or re.match(r"^\d+(\.\d+)?[smhd]?$", text)):
            continue        # wrapper options and values: timeout 5, nice -n 10, env -i
        base = os.path.basename(text)
        if not kind and base in PLAIN_WRAPPERS | {"env", "nice", "timeout", "xargs", "stdbuf"}:
            after_wrapper = True
            continue
        at_cmd = False
        if not kind and base in ROOT_TOOLS:
            rest = [t for t, k in toks[i + 1:i + 5] if k is not None and k != "redir" or (k is None and t not in OPS)]
            out.append((base, rest))
    if depth < 2:
        for st in parse_command(cmd):
            if st.inner_text:
                out.extend(root_calls(st.inner_text, depth + 1))
    return out


def gate_sudo(ctx, cmd, stages):
    """House rule 45-no-root: agents never use sudo. The one exception, on a Linux server only, is
    `sudo proj-agent <subcommand>` (the hosting rules). Everything else: give the owner the command.
    Containment is the sudoers file; this gate catches the honest attempt early."""
    import sys as _sys
    calls = root_calls(cmd)
    if not calls:
        return None
    linux = _sys.platform.startswith("linux")

    def is_proj_agent(rest):
        words = list(rest)
        while words and words[0] in ("-n", "--non-interactive"):    # sudo -n proj-agent ... (no prompt)
            words.pop(0)
        return words[:1] == ["proj-agent"] and len(words) > 1
    bad = [t for t, rest in calls if not (linux and t == "sudo" and is_proj_agent(rest))]
    if not bad:
        return None
    return ("deny", "No sudo for agents (%s). Do not try another way to get root. Give the owner the exact command "
            "to run himself.%s" % (", ".join(sorted(set(bad))),
                                   " Only `sudo proj-agent <subcommand>` is allowed on this server." if linux else ""))


def probe_sudo(stages, cmd=""):
    return bool(root_calls(cmd)) or any("sudo" in st.wrappers or st.exe in ROOT_TOOLS for st in stages)


GATES = {"audit-before-install": gate_audit, "secret-scan": gate_secrets, "pr-rules": gate_pr, "no-sudo": gate_sudo}
GATE_PROBES = {"audit-before-install": probe_audit, "secret-scan": probe_secrets, "pr-rules": probe_pr,
               "no-sudo": probe_sudo}


# ---------------------------------------------------------------- project knowledge (router placeholders)
# Project knowledge lives in the repo AGENTS.md (read every session, no tool call): a Map block (<= 60 lines)
# and a Libraries block (context7 IDs + lockfile hashes), both written by ai-adopt / ai-libs. The router only
# says whether they exist and are current. Every git call: 2 s timeout, fails open (no text).

CODE_EXT = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".kts",
    ".rb", ".php", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".swift", ".scala", ".sh", ".bash",
    ".zsh", ".lua", ".vue", ".svelte", ".ex", ".exs", ".dart", ".m", ".mm", ".sql", ".r", ".jl", ".zig",
    ".erl", ".clj", ".fs", ".ml", ".hs", ".pl", ".ps1", ".tf",
}
MAP_RX = re.compile(r"<!-- AI:map START -->\n?(.*?)<!-- AI:map END -->", re.S)
LIBS_RX = re.compile(r"<!-- AI:libraries START([^>]*)-->\n?(.*?)<!-- AI:libraries END -->", re.S)
MAP_CAP_LINES = 60
# Same list as ai/bin/ai-libs (its lock line records these, sha256 first 12 hex).
LOCKFILES = ("uv.lock", "poetry.lock", "requirements.txt", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
             "go.sum", "Cargo.lock")
MANIFESTS = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "Gemfile", "composer.json")
KNOWLEDGE_CAP = 600


def is_code_file(path):
    return os.path.splitext((path or "").rstrip("/:"))[1].lower() in CODE_EXT


def is_dep_file(path):
    base = os.path.basename(path or "")
    return base in LOCKFILES or base in MANIFESTS or re.match(r"^requirements.*\.txt$", base) is not None


def git_quick(repo, args, timeout=2):
    """git output or None (timeout, error, not a repo). Never raises."""
    import subprocess
    try:
        res = subprocess.run(["git", "-C", repo] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=timeout)
    except Exception:
        return None
    return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else None


def git_history(repo, limit=500):
    """[(sha, commit_time, [(status, path)])], newest first, or None."""
    out = git_quick(repo, ["log", "-n", str(limit), "--no-color", "--format=%x00%H %ct", "--name-status",
                           "--no-renames"])
    if out is None:
        return None
    commits = []
    for chunk in out.split("\0")[1:]:
        lines = chunk.strip("\n").splitlines()
        if not lines:
            continue
        head = lines[0].split()
        if len(head) < 2:
            continue
        files = []
        for ln in lines[1:]:
            parts = ln.split("\t")
            if len(parts) >= 2:
                files.append((parts[0][:1], parts[-1]))
        try:
            commits.append((head[0], int(head[1]), files))
        except ValueError:
            continue
    return commits


def repo_agents_md(root):
    return read_text(os.path.join(root, "AGENTS.md")) if root else None


def map_block(root):
    """The Map section text of the repo AGENTS.md, or None."""
    m = MAP_RX.search(repo_agents_md(root) or "")
    return m.group(1) if m else None


def enabled_ids(root):
    """Opt-in ids of the project (.ai/enabled) plus `serena` when the project enables the ai-serena plugin."""
    text = read_text(os.path.join(root, ".ai", "enabled")) if root else ""
    ids = {ln.split("#", 1)[0].strip().lower() for ln in (text or "").splitlines() if ln.split("#", 1)[0].strip()}
    for rel in (".claude/settings.json", ".claude/settings.local.json"):
        try:
            data = json.loads(read_text(os.path.join(root, rel)) or "{}") if root else {}
        except ValueError:
            continue
        if isinstance(data, dict) and (data.get("enabledPlugins") or {}).get("ai-serena@ai") is True:
            ids.add("serena")
    return ids


def graph_status(root, history):
    """'fresh' | 'stale' | 'missing' for graphify-out/graph.json against the last commit that touched code."""
    g = os.path.join(root, "graphify-out", "graph.json")
    if not os.path.isfile(g):
        return "missing"
    last = next((ct for _sha, ct, files in (history or []) if any(is_code_file(p) for _st, p in files)), None)
    if last is None:
        return "fresh"
    return "fresh" if os.path.getmtime(g) >= last else "stale"


def libs_doc(root):
    """The Libraries block of the repo AGENTS.md: {"locks": {file: hash prefix}, "rows": {lib: {version, context7}}}
    or None. Format (ai-libs --sync): `<!-- AI:libraries START lock: uv.lock sha256:<12 hex> ... -->`, then a table
    lib | version | context7 | note ("?" = not looked up, "-" = no match or not sent)."""
    m = LIBS_RX.search(repo_agents_md(root) or "")
    if not m:
        return None
    doc = {"locks": dict(re.findall(r"(\S+) sha256:([0-9a-f]{6,64})", m.group(1))), "rows": {}}
    header = None
    for line in m.group(2).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        row = dict(zip(header, cells))
        name = row.get("lib") or row.get("library") or ""
        if name:
            doc["rows"][name.lower()] = {"version": row.get("version", ""), "context7": row.get("context7", "")}
    return doc


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def docs_map_status(root):
    """'matches <locks>' | 'stale' | 'missing' | '' (no lockfile: nothing to say)."""
    locks = [f for f in LOCKFILES if os.path.isfile(os.path.join(root, f))]
    doc = libs_doc(root)
    if doc is None:
        return "missing" if locks else ""
    if not locks:
        return ""
    for name in locks:
        want = doc["locks"].get(name)
        got = file_sha256(os.path.join(root, name))
        if not want or got is None or not got.startswith(want):
            return "stale"
    return "matches " + ", ".join(locks)


def knowledge_index(root):
    """One pointer line (<= 600 chars) for the session start: the Map and Libraries blocks of AGENTS.md, and
    Serena / graph only where the project enabled them. Empty outside a git repo."""
    if not root:
        return ""
    bits = []
    mp = map_block(root)
    if mp is None:
        bits.append("Map: missing (ai-adopt writes it).")
    else:
        n = len([ln for ln in mp.splitlines() if ln.strip()])
        bits.append("Map: present (%d lines%s)." % (n, ", over the 60-line cap" if n > MAP_CAP_LINES else ""))
    d = docs_map_status(root)
    bits.append("Libraries: " + {"missing": "missing (run ai-libs --sync).", "": "no lockfile.",
                                 "stale": "stale, run ai-libs --sync."}.get(d, "match the lockfiles."))
    ids = enabled_ids(root)
    if "serena" in ids:
        bits.append("Serena on.")
    if "graph" in ids or "graphify" in ids:
        g = graph_status(root, git_history(root))
        bits.append("Graph: " + {"fresh": "fresh.", "stale": "stale, run graphify update .",
                                 "missing": "missing, run GRAPHIFY_BACKEND=none graphify extract . --code-only"}[g]
                    + ("" if g == "fresh" else "."))
    return " ".join(bits)[:KNOWLEDGE_CAP]


def head_commit_files(root, max_age=600):
    """[(status, path)] of HEAD when HEAD was committed in the last max_age seconds, else None."""
    out = git_quick(root, ["show", "-s", "--format=%ct", "HEAD"])
    try:
        ct = int((out or "").strip())
    except ValueError:
        return None
    if time.time() - ct > max_age:
        return None
    names = git_quick(root, ["show", "--no-color", "--format=", "--name-status", "--no-renames", "HEAD"])
    if names is None:
        return None
    files = []
    for ln in names.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 2:
            files.append((parts[0][:1], parts[-1]))
    return files


def graphify_hook_installed(root):
    hooks = git_quick(root, ["rev-parse", "--git-path", "hooks"])
    if not hooks:
        return False
    d = hooks.strip()
    if not os.path.isabs(d):
        d = os.path.join(root, d)
    return any("graphify" in (read_text(os.path.join(d, n)) or "") for n in ("post-commit", "post-checkout"))


def knowledge_delta(root, new_docs_ids=False):
    """One combined nudge after a fresh commit, or '' when nothing applies."""
    if not root:
        return ""
    files = head_commit_files(root)
    if files is None:
        return ""
    todo = []
    if any(st in "AD" and is_code_file(p) for st, p in files):
        todo.append("update the Map section in AGENTS.md (code files were added, removed or renamed)")
    if any(is_dep_file(p) for _st, p in files) or new_docs_ids:
        todo.append("run ai-libs --sync and commit AGENTS.md")
    ids = enabled_ids(root)
    if ("graph" in ids or "graphify" in ids) and any(is_code_file(p) for _st, p in files) \
            and not graphify_hook_installed(root):
        todo.append("run graphify update .")
    if not todo:
        return ""
    return "After this commit: " + "; ".join(todo) + "."


CONTEXT7_ID_RX = re.compile(r"/[\w.-]{1,60}/[\w.-]{1,60}(?:/[\w.+-]{1,40})?")
LIB_NAME_RX = re.compile(r"[\w.@/+-]{1,80}")


def libs_hits(root, names):
    """Cached docs IDs for the named libraries from the Libraries block of AGENTS.md, as one phrase, or ''."""
    doc = libs_doc(root)
    if not doc or not doc["rows"]:
        return ""
    hits = []
    for n in sorted(set(x.lower() for x in names or []))[:6]:
        row = doc["rows"].get(n) or doc["rows"].get(norm_pypi(n))
        if not row or not LIB_NAME_RX.fullmatch(n):
            continue
        ids = []
        # AGENTS.md is a committed file: only well-formed IDs reach the agent's context, never free text.
        if CONTEXT7_ID_RX.fullmatch(row.get("context7") or ""):
            ids.append("context7=" + row["context7"])
        hits.append("%s %s" % (n, " ".join(ids) if ids else "(no IDs yet)"))
    if not hits:
        return "Library IDs: the Libraries section of AGENTS.md."
    return "Cached IDs (Libraries in AGENTS.md): " + "; ".join(hits) + "."


def origin_slug(root):
    """'Repo: owner/name (origin remote).' or ''."""
    if not root:
        return ""
    url = (git_quick(root, ["remote", "get-url", "origin"]) or "").strip()
    m = re.search(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url)
    return "Repo: %s/%s (origin remote)." % (m.group(1), m.group(2)) if m else ""


def project_libs(root):
    """Library names this project uses: Libraries rows of AGENTS.md plus direct deps of the root manifests."""
    names = set()
    doc = libs_doc(root)
    if doc:
        names.update(doc["rows"])
    if not root:
        return names
    pkg = read_text(os.path.join(root, "package.json"))
    if pkg:
        try:
            data = json.loads(pkg)
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                names.update(k.lower() for k in (data.get(key) or {}))
        except ValueError:
            pass
    for rel, rx in (("pyproject.toml", r"^\s*[\"']([A-Za-z0-9][A-Za-z0-9._-]*)"),
                    ("requirements.txt", r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)"),
                    ("go.mod", r"^\s*(?:require\s+)?[\w.-]+\.[a-z]+/(?:[\w.-]+/)*([\w.-]+)\s+v\d")):
        text = read_text(os.path.join(root, rel)) or ""
        names.update(norm_pypi(x) for x in re.findall(rx, text, re.M))
    cargo = read_text(os.path.join(root, "Cargo.toml")) or ""
    m = re.search(r"^\[dependencies\]\s*$(.*?)(?=^\[|\Z)", cargo, re.M | re.S)
    if m:
        names.update(x.lower() for x in re.findall(r"^\s*([A-Za-z0-9_-]+)\s*=", m.group(1), re.M))
    return {n for n in names if len(n) >= 3}


# Popular libraries that are not plain English words (a prompt naming one is a docs question).
KNOWN_LIBS = {
    "react", "nextjs", "next.js", "vue", "nuxt", "svelte", "sveltekit", "angular", "solidjs", "astro", "remix",
    "tailwind", "tailwindcss", "shadcn", "vite", "webpack", "esbuild", "typescript", "nodejs", "deno", "bun",
    "fastapi", "django", "flask", "starlette", "pydantic", "sqlalchemy", "alembic", "celery", "pytest", "numpy",
    "pandas", "polars", "scipy", "matplotlib", "plotly", "streamlit", "langchain", "llamaindex", "openai",
    "anthropic", "transformers", "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn", "httpx", "aiohttp",
    "prisma", "drizzle", "sequelize", "typeorm", "mongoose", "postgres", "postgresql", "psycopg", "asyncpg",
    "redis", "kafka", "graphql", "apollo", "trpc", "zod", "axios", "jest", "vitest", "playwright", "puppeteer",
    "cypress", "electron", "tauri", "expo", "react-native", "flutter", "supabase", "firebase", "stripe",
    "tokio", "axum", "actix", "serde", "diesel", "gin", "fiber", "echo", "gorm", "spring", "hibernate", "rails",
    "laravel", "symfony", "kubernetes", "terraform", "docker", "ansible", "htmx", "alpinejs", "echarts",
    "chart.js", "d3", "three.js", "meilisearch", "elasticsearch", "opensearch", "dbos", "temporal", "typer",
    "click", "rich", "textual", "uvicorn", "gunicorn", "nginx", "caddy",
}
COMMON_WORDS = {"click", "rich", "echo", "fiber", "spring", "temporal", "express", "next", "gin"}


def prompt_libs(prompt, root):
    """Library names the prompt mentions (word-bounded, case-insensitive)."""
    text = (prompt or "").lower()
    if not text.strip():
        return set()
    names = project_libs(root) | (KNOWN_LIBS - COMMON_WORDS)
    hits = set()
    for n in names:
        if len(n) < 3 or n in COMMON_WORDS:
            continue
        if re.search(r"(?<![\w.@/-])" + re.escape(n) + r"(?![\w-])", text):
            hits.add(n)
    return hits


# ---------------------------------------------------------------- generic helpers

def project_root(start):
    d = os.path.abspath(start or ".")
    if os.path.isfile(d):
        d = os.path.dirname(d)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def ai_home():
    env = os.environ.get("AI_HOME")
    if env:
        return env
    here = os.path.dirname(os.path.realpath(__file__))
    guess = os.path.realpath(os.path.join(here, "..", "..", "..", "..", ".."))
    if os.path.isfile(os.path.join(guess, "ai", "routing.yaml")):
        return guess
    default = os.path.expanduser("~/.dotfiles-ai")
    return default if os.path.isdir(default) else None


def git_out(repo, args):
    import subprocess
    try:
        res = subprocess.run(["git", "-C", repo] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=10)
        return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else ""
    except Exception as exc:
        log_error("git", exc)
        return ""


def state_dir():
    return os.environ.get("AI_STATE_DIR") or os.path.expanduser("~/.local/state/ai")


def state_path(rel):
    return os.path.join(state_dir(), rel)


def log_line(rel, line):
    """Append one line to a state file. Never raises (an unwritable state dir must not change a decision)."""
    try:
        path = state_path(rel)
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.makedirs(d, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)   # state files are private
        try:
            if os.fstat(fd).st_mode & 0o077:
                os.fchmod(fd, 0o600)
            os.write(fd, (line.rstrip("\n") + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        pass


def redact(text):
    """Replace every secret-pattern match (and its value group) with [REDACTED], for logs."""
    for _name, rx in SECRET_PATTERNS:
        text = rx.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED]") if rx.groups and m.group(1)
                      else "[REDACTED]", text)
    return REDACT_ASSIGN.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)


# Looser than the scan patterns: any NAME=value in a command line (env prefix, export, --token=...).
REDACT_ASSIGN = re.compile(r"(?i)\b(" + NAME + r")(\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)")


def append_jsonl(rel, row):
    log_line(rel, json.dumps(row, ensure_ascii=False))


def log_error(where, exc):
    log_line("router-errors.log", "%s %s %s: %s" % (iso_now(), where, type(exc).__name__, exc))


def read_text(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_iso(ts):
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def one_line(s):
    return re.sub(r"\s+", " ", s or "").strip()
