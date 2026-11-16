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
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
}
PLAIN_WRAPPERS = {"command", "time", "nohup", "exec", "then", "do", "else", "!", "builtin"}
# RTK (managed hook) rewrites commands to `rtk <cmd>`, and agents type it too: `rtk git commit`, `rtk gh pr
# create`, `rtk proxy <cmd>` run the same program. Every gate sees the command without it (Fable readiness B1).
RTK_WRAPPERS = {"rtk"}


# ---------------------------------------------------------------- shell parsing

class Stage(object):
    def __init__(self, words, op, redirs=()):
        self.words = words            # [(text, quoted)]
        self.op = op                  # operator after this stage, or ""
        self.redirs = list(redirs)    # [(operator, target)], e.g. (">>", "AGENTS.md")
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
    stages, words, redirs, redir_op = [], [], [], None
    for text, kind in toks:
        if redir_op is not None and kind is not None and kind != "redir" and text not in OPS:
            redirs.append((redir_op, text))      # the redirection target is not a command word
            redir_op = None
            continue
        redir_op = None
        if kind == "redir":
            redir_op = text
            continue
        if kind is None and text in OPS:
            stages.append(Stage(words, text, redirs))
            words, redirs = [], []
            continue
        words.append((text, bool(kind)))
    stages.append(Stage(words, "", redirs))
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
        if base in RTK_WRAPPERS and not quoted and len(words) > 1:
            stage.wrappers.append("rtk")
            words.pop(0)
            if words and words[0][0] == "proxy" and len(words) > 1:
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


def write_targets(stages, cwd):
    """Files a shell command writes: redirections (> >> &>), tee, sed -i, and the destination of cp and mv.
    shortcut: perl -i, dd of=, a script or an interpreter (python -c) are not seen; add them when one shows up."""
    out = []
    for st in stages:
        out += [t for op, t in st.redirs if op.lstrip("&") in (">", ">>")]
        if st.exe == "tee":
            out += [a for a in st.args if a and not a.startswith("-")]
        elif st.exe == "sed" and any(a.startswith("--in-place") or re.match(r"^-[a-zA-Z]*i", a) for a in st.args):
            out += sed_files(st.args)
        elif st.exe in ("cp", "mv"):
            out += copy_targets(st.args, cwd)
    return out


def sed_files(args):
    """The file arguments of sed: the first free word is the script unless -e or -f gave it."""
    files, script_given, it = [], False, iter(args)
    for a in it:
        if a in ("-e", "-f", "--expression", "--file"):
            script_given = True
            next(it, None)
        elif a.startswith(("--expression=", "--file=")):
            script_given = True
        elif a and not a.startswith("-"):
            files.append(a)
    return files if script_given else files[1:]


def copy_targets(args, cwd):
    """cp and mv: the destination, or each source name inside the destination folder (-t DIR, a folder)."""
    folder, paths, it = None, [], iter(args)
    for a in it:
        if a in ("-t", "--target-directory"):
            folder = next(it, None)
        elif a.startswith("--target-directory="):
            folder = a.split("=", 1)[1]
        elif a and not a.startswith("-"):
            paths.append(a)
    if folder is None:
        if len(paths) < 2:
            return []
        folder = paths.pop()
        if not (folder.endswith("/") or os.path.isdir(os.path.join(cwd, os.path.expanduser(folder)))):
            return [folder]
    return [os.path.join(folder, os.path.basename(p.rstrip("/"))) for p in paths]


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


def run_mark(targets):
    """Package runners (uvx, npx, ...) fetch and run without an install: eco "<eco>-run" (ask unless audited)."""
    return [(eco + "-run", name, ver) if eco in ("pypi", "npm") else (eco, name, ver) for eco, name, ver in targets]


def runner_spec(args, value_opts, pkg_opts):
    """The package specs a runner fetches: --from/--package values, else its first positional word."""
    specs, i, first = [], 0, None
    while i < len(args):
        a = args[i]
        opt, eq, val = a.partition("=")
        if opt in pkg_opts:
            specs.append(val if eq else (args[i + 1] if i + 1 < len(args) else ""))
            i += 1 if eq else 2
            continue
        if a in value_opts:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        first = a
        break
    return [s for s in specs if s] or ([first] if first else [])


def stage_targets(exe, args, st, cwd):
    if exe == "uvx" or (exe == "uv" and args[:2] == ["tool", "run"]):
        rest = args if exe == "uvx" else args[2:]
        specs = runner_spec(rest, UV_VALUE_OPTS | {"--with", "-w", "--with-requirements"}, {"--from"})
        withs = uv_targets(with_opts(rest), cwd)
        return run_mark([pip_spec_target(re.sub(r"^([\w.-]+)@([\w.+-]+)$", r"\1==\2", s), cwd)
                         for s in specs] + withs)
    if exe == "uv" and args[:1] == ["run"]:
        withs = run_mark(uv_targets(with_opts(args[1:]), cwd))
        rest = skip_options(args[1:], UV_VALUE_OPTS | UV_TARGET_OPTS)
        return withs + (stage_targets(os.path.basename(rest[0]), rest[1:], st, cwd) if rest else [])
    if exe in ("npx", "bunx") or (exe in ("pnpm", "yarn") and args[:1] == ["dlx"]) or (exe == "npm" and args[:1] == ["exec"]):
        rest = args if exe in ("npx", "bunx") else args[1:]
        if "--" in rest:
            rest = rest[:rest.index("--")]
        specs = runner_spec(rest, {"-c", "--call", "--registry", "--cache"}, {"-p", "--package"})
        return run_mark([npm_or_path(s, cwd) for s in specs])
    if exe == "pipx" and args[:1] == ["run"]:
        specs = runner_spec(args[1:], {"--python", "--pip-args", "--index-url"}, {"--spec"})
        return [("pipx", s, "") for s in specs] or [("pipx", "", "")]
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


def with_opts(args):
    """Only the --with / -w / --with-requirements options (and their values) before the command word."""
    out, i = [], 0
    while i < len(args):
        a = args[i]
        opt, eq, _v = a.partition("=")
        if opt in ("--with", "-w", "--with-requirements"):
            out.extend(args[i:i + (1 if eq else 2)])
            i += 1 if eq else 2
            continue
        if a in UV_VALUE_OPTS or opt == "--from":
            i += 1 if eq else 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
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
        if eco.endswith("-run"):
            # A runner (uvx, npx, pnpm dlx, bunx, uv run --with): a local bin of the project is fine; an
            # audited package is fine; anything else asks (the sandbox is the boundary, this is the habit check).
            base = eco[:-4]
            if base == "npm" and os.path.exists(os.path.join(ctx.cwd or ".", "node_modules", ".bin", name)):
                continue
            if audit_status(base, name, version) != "PASS":
                asks.append("%s runs %s %s%s, fetched without an audit. Run: %s" % (
                    "package runner", base, name, ("@" + version) if version else "", audit_hint(base, name, version)))
            continue
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

# Body template (owner 2026-11-15): Matt Pocock's `pr` skill (Summary, Evidence, Merge Danger) plus a required
# Mermaid diagram. Fields: Evidence, Door, Blast Radius, Docs, Changed guards and (fix: PRs) Ledger. No tiers
# (removed 2026-11-15, every project is long). A fix: PR needs a test file in its diff; over 400 changed
# lines (lockfiles and generated files left out) is a warning, never a block.
PR_FILL = {"--fill", "--fill-first", "--fill-verbose", "--web", "-f", "-w"}
PR_FIELDS = ("Evidence", "Door", "Blast Radius", "Docs", "Changed guards")
PR_FIELD_HELP = {"Evidence": "Before and After: the check command and the tail of its output",
                 "Door": "one-way or two-way, with a reason", "Blast Radius": "what can break",
                 "Docs": "the docs changed, or \"none, because ...\"",
                 "Changed guards": "every edited or removed test with the reason, or \"none\"",
                 "Ledger": "R-NNN and the test path (docs/REGRESSIONS.md)"}
PR_PLACEHOLDER = re.compile(r"^(<[^>]*>|todo|tbd|\.{2,}|xxx+|\?+|-+|n/?a|fill (it )?in|placeholder|same|see above|"
                            r"(add|describe|write)\b.*\bhere)\W*$", re.I)
PR_DOOR = re.compile(r"\b(one|two)[- ]way\b", re.I)
PR_DOOR_UNFILLED = re.compile(r"\bone[- ]way\s*(or|/)\s*two[- ]way\b", re.I)    # the template text left in
PR_FIX_TITLE = re.compile(r"^\s*(fix|bugfix|hotfix)(\([^)]*\))?!?:", re.I)     # conventional titles only
PR_TEST_PATH = re.compile(r"(^|/)test_[^/]*\.py$|_test\.(go|py)$|\.(test|spec)\.[cm]?[jt]sx?$|"
                          r"(^|/)(tests?|spec|__tests__)/(.*/)?[^/]+\.(py|[cm]?[jt]sx?|go|rs|rb|java|kt|php|cs|swift)$")
PR_GENERATED = re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|Cargo\.lock|"
                          r"go\.sum|bun\.lockb?|composer\.lock|Gemfile\.lock)$|\.(lock|min\.js|min\.css|snap)$|"
                          r"(^|/)(dist|vendor|generated|__generated__)/")
PR_SIZE_WARN = 400


def gate_pr(ctx, cmd, stages):
    problems = []
    for st in stages:
        if st.exe != "gh" or st.args[:1] != ["pr"] or len(st.args) < 2 or st.args[1] not in ("create", "edit"):
            continue
        sub, args = st.args[1], st.args[2:]
        if sub == "create" and any(a.split("=")[0] in PR_FILL for a in args):
            problems.append("--fill / --web hide the body from this check: write the body and pass it with --body "
                            "or --body-file")
            continue
        body_flag = any(a.split("=")[0] in ("--body", "-b", "--body-file", "-F") for a in args)
        if sub == "edit" and not body_flag:
            continue
        text = pr_body_text(ctx, cmd, args)
        missing = []
        if "```mermaid" not in text:
            missing.append("a ```mermaid diagram")
        if "<!-- author-sessions" not in text:
            missing.append("the <!-- author-sessions block")
        root = project_root(ctx.cwd)
        fields = list(PR_FIELDS)
        fix = bool(PR_FIX_TITLE.match(flag_value(args, ("--title", "-t")) or ""))
        if fix:
            fields.append("Ledger")
        for name in fields:
            why = pr_field_problem(name, pr_field(text, name))
            if why:
                missing.append(why)
        if sub == "create" and root:
            diff_problems, files = pr_diff_checks(ctx, root, args, fix)
            missing.extend(diff_problems)
            why = pr_verify_evidence(root, pr_field(text, "Evidence"), files)
            if why:
                missing.append(why)
        problems.extend(m for m in missing if m not in problems)
    if not problems:
        return None
    return ("deny", "PR not ready, missing: %s. Body follows the pr skill template: ## Summary (with a ```mermaid "
            "diagram), ## Evidence (Before and After: command and output tail), ## Merge Danger (**Door:** one-way "
            "or two-way and why; **Blast Radius:** what can break). Also: Docs, Changed guards, Ledger "
            "on fix PRs. Author-sessions block at the end. Pass it with --body or --body-file."
            % "; ".join(problems))


def pr_body_text(ctx, cmd, args):
    text = "\n".join(args)     # one line per word: -b "Verify: ..." keeps its field at a line start
    for i, a in enumerate(args):
        opt, eq, val = a.partition("=")
        if opt in ("--body-file", "-F"):
            path = val if eq else (args[i + 1] if i + 1 < len(args) else "-")
            if path != "-":
                text += "\n" + (read_text(os.path.join(ctx.cwd, os.path.expanduser(path))) or "")
    if "<<" in cmd and "--body" in cmd:
        text += "\n" + cmd       # heredoc body inside $(cat <<EOF ...)
    return text


def flag_value(args, names):
    for i, a in enumerate(args):
        opt, eq, val = a.partition("=")
        if opt in names:
            return val if eq else (args[i + 1] if i + 1 < len(args) else "")
    return None


def pr_field(text, name):
    """The text after `Name:` (markdown bold, heading or list marks allowed before it), or the next lines when
    the label stands alone. Also the heading form: a `## Name` line (any level, optional colon) and the section
    body up to the next heading or `<!--`. None when the label is missing."""
    m = re.search(r"(?im)^[ \t>*#_-]*\**%s\**[ \t]*:\**[ \t]*(.*)$" % re.escape(name), text)
    if not m:
        return pr_heading_section(text, name)
    value = m.group(1).strip()
    if value:
        return value
    lines = []
    for ln in text[m.end():].splitlines():
        if re.match(r"^[ \t>*#_-]*\**[A-Z][\w ]{1,30}\**[ \t]*:", ln) or ln.startswith("<!--"):
            break
        if ln.strip():
            lines.append(ln.strip())
        if len(lines) >= 4:
            break
    return " ".join(lines)


def pr_heading_section(text, name):
    m = re.search(r"(?im)^[ \t]*#{1,6}[ \t]+%s[ \t]*:?[ \t]*$" % re.escape(name), text)
    if not m:
        return None
    lines, fenced = [], False
    for ln in text[m.end():].splitlines():
        if ln.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (re.match(r"^[ \t]*#{1,6}[ \t]", ln) or ln.startswith("<!--")):
            break
        if ln.strip():
            lines.append(ln.strip())
        if len(lines) >= 40:
            break
    return " ".join(lines)


def pr_field_problem(name, value):
    help_text = "%s: (%s)" % (name, PR_FIELD_HELP[name])
    if value is None:
        return help_text
    plain = re.sub(r"[`*_]", "", value).strip()
    bare = re.sub(r"<[^>]*>", "", plain)           # unfilled <...> template slots
    if name == "Evidence":
        bare = re.sub(r"(?i)\b(before|after)\b\s*:", "", bare)
    if len(re.sub(r"\W", "", bare)) < 3 or PR_PLACEHOLDER.match(plain):
        return "real text, not a placeholder, in " + help_text
    if name == "Door" and (PR_DOOR_UNFILLED.search(plain) or not PR_DOOR.search(plain)):
        return "one-way or two-way (pick one) in " + help_text
    if name == "Docs" and re.match(r"^none\b", plain, re.I) and \
            not re.search(r"\b(because|since|as)\b|[,:;]\s*\w{3,}", plain[4:], re.I):
        return "a reason after Docs: none (\"none, because ...\")"
    if name == "Ledger" and not re.search(r"\bR-\d+\b", plain):
        return "an R-NNN id in Ledger: (fix PRs)"
    return None


def pr_diff_checks(ctx, root, args, fix):
    """A fix: PR without a test file -> problem; size over PR_SIZE_WARN -> a warning in the context only."""
    base = flag_value(args, ("--base", "-B"))
    head = flag_value(args, ("--head", "-H")) or "HEAD"
    if ":" in head:
        head = "HEAD"           # owner:branch of a fork: compare the local HEAD
    candidates = ["origin/" + base, base] if base else []
    ref = (git_quick(root, ["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"]) or "").strip()
    candidates += ([ref] if ref else []) + ["origin/main", "origin/master", "main", "master"]
    base_ref = next((c for c in candidates if git_quick(root, ["rev-parse", "-q", "--verify", c + "^{commit}"])), None)
    numstat = git_quick(root, ["diff", "--numstat", "%s...%s" % (base_ref, head)]) if base_ref else None
    if numstat is None:
        ctx.add_context("[ai gate pr-rules] could not diff against the base branch: the test-file, size and "
                        "verify-evidence checks did not run.")
        return [], None
    files, lines = [], 0
    for row in numstat.splitlines():
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        files.append(parts[2])
        if not PR_GENERATED.search(parts[2]):
            lines += sum(int(x) for x in parts[:2] if x.isdigit())
    out = []
    if fix and not any(PR_TEST_PATH.search(f) for f in files):
        out.append("a test file in the diff of a fix: PR (tests/..., test_*.py, *_test.go, *.test.ts); none against %s"
                   % base_ref)
    if lines > PR_SIZE_WARN:
        ctx.add_context("[ai gate pr-rules] warning: %d changed lines against %s (generated files left out), over %d. "
                        "Split the PR or say in the body why it must stay one." % (lines, base_ref, PR_SIZE_WARN))
    return out, files


def pr_verify_evidence(root, evidence, files):
    """A project with a verify-<app> skill and a PR that changes app code: Evidence names the skill
    run, its evidence path and the e2e test (the Done order: check-fast, verify evidence, then e2e)."""
    if evidence is None or files is None:
        return None
    info = verify_skill(root)
    if not info or not any(is_code_file(f) and not PR_TEST_PATH.search(f) and not f.startswith(info["path"] + "/")
                           for f in files):
        return None
    tokens = re.findall(r"[\w.@~-]*/[\w./@~-]+", evidence)
    has_test = any(PR_TEST_PATH.search(t) for t in tokens)
    has_evidence = any(not PR_TEST_PATH.search(t) for t in tokens)
    if info["name"] in evidence and has_test and has_evidence:
        return None
    return ("Evidence: the %s run (its evidence path, e.g. artifacts/<feature>/...) and the e2e test it led to "
            "(a tests/... path): app code changed and this project has a verify skill" % info["name"])


def probe_pr(stages, cmd=""):
    return any(st.exe == "gh" and st.args[:1] == ["pr"] and st.args[1:2] in (["create"], ["edit"]) for st in stages)


# ---------------------------------------------------------------- merge-approval (owner 2026-11-16)
# Every PR goes through the owner. The agent merges only after the owner's latest prompt says so ("merge",
# "merge it", "approve", "lgtm", RO "aprob", RU "мержи"). The router stores that word per session at
# UserPromptSubmit (merge_ok); a later prompt without it clears it. A push to main or master skips the PR, so
# it needs the same OK. The owner merges on GitHub at any time; this gate only stops the agent.

MERGE_OK_RX = re.compile(
    r"^\W*(merge|approved?|lgtm|ship it)\W*$"
    r"|\bmerge\s+(it|this|them|that|the\s+prs?|prs?\b|pr\s*#?\d+|#\d+|now|please|all)\b"
    r"|\b(please|go\s+ahead\s+and|go\s+ahead,?|you\s+can|ok(ay)?,?|yes,?|now)\s+merge\b"
    r"|\b(approved?|lgtm|ship\s+it)\b"
    r"|\baprob\w*|\bmergeaz[aă]\b|\bf[aă] merge\b"
    r"|(?<!\w)(смерж\w*|мерж\w*|одобр\w*|сливай)",
    re.I)
NO_MERGE_RX = re.compile(
    r"\b(don'?t|do\s+not|never|not\s+yet|no|without|before|stop|wait|nu|не)\b\W+(\w+\W+){0,3}?"
    r"(merge|approv|aprob|мерж|смерж|одобр|слив)", re.I)


def owner_merge_ok(prompt):
    """True when the owner's prompt gives the OK to merge. A question ("is it approved?") or a negation
    ("don't merge yet") is not an OK."""
    text = (prompt or "").strip()
    if not text or NO_MERGE_RX.search(text) or not MERGE_OK_RX.search(text):
        return False
    if text.endswith("?") and not re.search(r"\bmerge\s+(it|this|them|now)\b", text, re.I):
        return False
    return True


def merge_calls(stages, cwd):
    """What in this command merges into, or pushes to, main/master: ["gh pr merge", ...]."""
    out = []
    for st in stages:
        if st.exe == "gh" and st.args[:2] == ["pr", "merge"]:
            out.append("gh pr merge")
        elif st.exe == "gh" and st.args[:1] == ["api"] and any(re.search(r"/pulls/\d+/merge\b", a)
                                                               for a in st.args):
            out.append("gh api .../pulls/N/merge")
        elif st.exe == "git":
            sub, rest, d = git_sub(st, cwd)
            if sub == "push" and push_targets_main(rest, d):
                out.append("git push to main/master")
    return out


MAIN_BRANCHES = ("main", "master")


def push_targets_main(rest, d):
    """A git push (args after `push`) that writes main or master: a refspec naming it, --all/--mirror, or a bare
    push while main or master is checked out."""
    if any(a in ("--all", "--mirror") for a in rest):
        return True
    pos = [a for a in rest if not a.startswith("-")]
    refspecs = pos[1:]
    if not refspecs:
        return current_branch(d) in MAIN_BRANCHES
    for spec in refspecs:
        dst = spec.lstrip("+").split(":")[-1]
        if dst.replace("refs/heads/", "") in MAIN_BRANCHES:
            return True
        if dst == "HEAD" and current_branch(d) in MAIN_BRANCHES:
            return True
    return False


def gate_merge(ctx, cmd, stages):
    calls = merge_calls(stages, ctx.cwd or ".")
    if not calls:
        return None
    if ctx.state.load().get("merge_ok"):
        return None
    return ("deny", "%s needs the owner's OK. Every PR goes through the owner: run the ship skill, then ask the "
            "owner. Merge only after the owner's latest message says merge (or approve). A push to main or master "
            "skips the PR: push the feature branch and open a PR instead." % ", ".join(calls))


def gate_no_verify(ctx, cmd, stages):
    """git commit --no-verify / -n and git push --no-verify skip the pre-commit check (lint, format) and the
    hooks: agents never skip them."""
    for st in stages:
        if st.exe != "git":
            continue
        sub, rest, _d = git_sub(st, ctx.cwd or ".")
        if sub not in ("commit", "push"):
            continue
        if "--no-verify" in rest or (sub == "commit" and "n" in short_flags(rest)):
            return ("deny", "git %s --no-verify skips the pre-commit check (lint and format on staged files). Fix "
                    "what the hook reports, git add the files, and commit again without --no-verify." % sub)
    return None


def probe_no_verify(stages, cmd=""):
    return any(st.exe == "git" and ("--no-verify" in st.args or any(a.startswith("-") and not a.startswith("--")
                                                                    and "n" in a for a in st.args))
               for st in stages)


def probe_merge(stages, cmd=""):
    return any((st.exe == "gh" and (st.args[:2] == ["pr", "merge"] or st.args[:1] == ["api"]))
               or (st.exe == "git" and "push" in st.args) for st in stages)


# ---------------------------------------------------------------- no-sudo

ROOT_TOOLS = {"sudo", "doas", "pkexec", "sudoedit", "su", "run0"}


def root_calls(cmd, depth=0):
    """[(tool, next words)] for every privilege tool at a command position, also inside bash -c / eval.
    A quoted word at a command position still runs (`'sudo' true`, `"sudo" -n true`); quoted words in
    argument positions are text (`echo "sudo"`, commit messages). Leading NAME=value words and plain
    wrappers are skipped."""
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
        if after_wrapper and (text.startswith("-") or re.match(r"^\d+(\.\d+)?[smhd]?$", text)):
            continue        # wrapper options and values: timeout 5, nice -n 10, env -i
        base = os.path.basename(text)
        if (base in PLAIN_WRAPPERS | RTK_WRAPPERS | {"env", "nice", "timeout", "xargs", "stdbuf"}
                or (text == "proxy" and i > 0 and os.path.basename(toks[i - 1][0]) == "rtk")):
            after_wrapper = True
            continue
        at_cmd = False
        if base in ROOT_TOOLS:
            rest = [t for t, k in toks[i + 1:i + 5] if k is not None and k != "redir" or (k is None and t not in OPS)]
            out.append((base, rest))
    if depth < 2:
        for st in parse_command(cmd):
            if st.inner_text:
                out.extend(root_calls(st.inner_text, depth + 1))
    return out


def gate_sudo(ctx, cmd, stages):
    """House rule 45-no-root: agents never use sudo, also not for proj-agent: box work goes through the box
    MCP tools (they run outside the sandbox and reach the root socket service), or a plain `proj-agent <sub>`
    where the agent is not sandboxed. Containment is the sudoers file; this gate catches the honest attempt."""
    import sys as _sys
    calls = root_calls(cmd)
    if not calls:
        return None
    # AI_GATE_PLATFORM: tests only (the hook's own environment, which an agent's command cannot set).
    linux = (os.environ.get("AI_GATE_PLATFORM") or _sys.platform).startswith("linux")

    def is_proj_agent(rest):
        words = list(rest)
        while words and words[0] in ("-n", "--non-interactive"):    # sudo -n proj-agent ... (no prompt)
            words.pop(0)
        return words[:1] and os.path.basename(words[0]) == "proj-agent"
    box = linux and any(t == "sudo" and is_proj_agent(rest) for t, rest in calls)
    if box:
        agent = getattr(ctx, "agent", "") or ""
        how = ("use the box MCP tools (list, new, exec, logs, ports, url, ...): they reach proj-agent without sudo"
               if agent == "claude" else
               "use the box MCP tools, or plain `proj-agent <subcommand>` without sudo where you are not sandboxed")
        return ("deny", "No sudo for proj-agent. Box work: %s." % how)
    return ("deny", "No sudo for agents (%s). Do not try another way to get root. Give the owner the exact command "
            "to run.%s" % (", ".join(sorted(set(t for t, _ in calls))),
                           " Box work: the box MCP tools." if linux else ""))


def probe_sudo(stages, cmd=""):
    return bool(root_calls(cmd)) or any("sudo" in st.wrappers or st.exe in ROOT_TOOLS for st in stages)


# ---------------------------------------------------------------- no-destroy
# Target-based, not flag-based: `rm -rf node_modules` passes, `rm -rf ~` or `rm -rf .git` does not. The SQL rule
# fires only for the protected database names of the repo (.ai/destructive.txt), so test databases and text that
# only mentions SQL (`grep "DROP TABLE" docs/`) pass. Shell indirection (scripts on disk, find -delete,
# xargs rm) is out of reach: the sandbox and the database role are the real boundary (README known limits).

REBUILDABLE = {"node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache", ".ruff_cache",
               ".mypy_cache", "target", "graphify-out", ".next", ".nuxt", ".turbo", ".parcel-cache", "coverage",
               "htmlcov", ".tox", ".nox", ".cache", "out", ".gradle", ".svelte-kit", ".angular", ".eggs"}
DATA_NAMES = {"data", "pgdata", "postgres", "postgresql", "mysql", "volumes", "db", "database", "backup",
              "backups"}
DATA_EXT = (".sqlite", ".sqlite3", ".db")
PROTECTED_BRANCHES = {"main", "master"}
SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "duckdb", "pgcli", "mycli", "litecli", "clickhouse-client",
               "usql"}
DESTRUCTIVE_SQL = re.compile(r"\b(drop\s+(database|schema|table)\b|truncate\b|delete\s+from\s+[\w.\"`]+\s*(;|$))",
                             re.I | re.M)
DESTROY_EXES = {"rm", "git", "docker", "podman", "docker-compose", "podman-compose", "dropdb", "pg_restore",
                "kubectl"} | SQL_CLIENTS


def project_tier(root):
    """Tiers removed 2026-11-15 (owner): every project is long. Kept so callers still work."""
    return "long"


def destructive_config(root):
    """{"db": [protected database names], "cmd": [[word, ...] command prefixes]} from .ai/destructive.txt."""
    out = {"db": [], "cmd": []}
    text =(read_text(os.path.join(root, ".ai", "destructive.txt")) if root else None) or ""
    for ln in text.splitlines():
        ln = ln.split("#", 1)[0].strip()
        m = re.match(r"^(db|cmd)\s*:\s*(.+)$", ln)
        if m and m.group(1) == "db":
            out["db"].extend(n for n in re.split(r"[\s,]+", m.group(2)) if n)
        elif m:
            out["cmd"].append(m.group(2).split())
    return out


def gate_destroy(ctx, cmd, stages):
    cwd = ctx.cwd or "."
    root = project_root(cwd)
    conf = destructive_config(root)
    here = cwd                  # None after `cd $X` / `cd -`: the folder is unknown from here on
    for st in stages:
        if st.exe in ("cd", "pushd", "popd"):
            here = cd_target(st, here)
            continue
        why = (rm_rule(st, here, root) or git_destroy_rule(st, here or cwd) or compose_rule(st)
               or sql_rule(st, stages, cmd, here or cwd, conf["db"]) or repo_cmd_rule(st, conf["cmd"]))
        if why:
            return ("deny", "Destructive command blocked: %s. Do not rephrase it or work around it: give the owner the "
                    "exact command and the reason, and let the owner run it." % why)
    return None


def cd_target(st, here):
    """The folder after a cd stage: bare `cd` and `cd ~` = home; a variable, `-`, popd = unknown (None)."""
    if st.exe == "popd":
        return None
    args = [a for a in st.args if a not in ("-L", "-P", "-e", "-@", "--")]
    if not args:
        return os.path.expanduser("~")
    t = args[0]
    m = re.match(r"^(\$HOME|\$\{HOME\})(/.*)?$", t)
    if m:
        t = "~" + (m.group(2) or "")
    if t == "-" or "$" in t or "`" in t or here is None or (t.startswith("~") and not re.match(r"^~(/|$)", t)):
        return None
    return os.path.normpath(os.path.join(here, os.path.expanduser(t)))


def probe_destroy(stages, cmd=""):
    return True       # cheap; repo rules in .ai/destructive.txt may name any program


def home_dir():
    return os.path.realpath(os.path.expanduser("~"))


def temp_roots():
    roots = ["/tmp", "/private/tmp", "/var/tmp", "/var/folders", "/private/var/folders"]
    if os.environ.get("TMPDIR"):
        roots.append(os.path.realpath(os.environ["TMPDIR"]))
    return roots


def inside(path, base):
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def rm_rule(st, cwd, session_root=None):
    if st.exe != "rm":
        return None
    flags, targets, end = set(), [], False
    for a in st.args:
        if not end and a == "--":
            end = True
        elif not end and a.startswith("--"):
            flags.add(a)
        elif not end and a.startswith("-") and len(a) > 1:
            flags.update(a[1:])
        else:
            targets.append(a)
    if not ({"r", "R", "--recursive"} & flags):
        return None
    if st.op == "(":                        # rm -rf $(pwd), rm -rf `pwd`: the target is a command's output
        return "rm -r of a command substitution (cannot tell the target)"
    if cwd is None:
        bad = [t for t in targets if not rebuildable_name(t)]
        return "rm -r %s after cd to a folder that cannot be told (a variable or cd -)" % bad[0] if bad else None
    for t in targets:
        for alt in brace_expand(t):
            why = rm_target_problem(alt, cwd, session_root)
            if why:
                return "rm -r %s (%s)" % (t, why)
    return None


def rebuildable_name(t):
    base = os.path.basename(t.rstrip("/")) or t
    return base in REBUILDABLE or base.endswith(".egg-info")


def brace_expand(t):
    """{a,b} alternatives (nested, first group first); text without a group is itself."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", t)
    if not m:
        return [t]
    out = []
    for alt in m.group(1).split(","):
        out.extend(brace_expand(t[:m.start()] + alt + t[m.end():]))
    return out


TEMP_VARS = re.compile(r"^\$\{?(TMPDIR|TMP|TEMP|tmpdir|tmp|temp|tempdir|TEMPDIR)\}?(/.*)?$")


def rm_target_problem(t, cwd, session_root=None):
    rebuildable = rebuildable_name(t)
    if TEMP_VARS.match(t):
        return None                         # $TMPDIR/x, "$tmpdir": a temp folder by its name
    if "$" in t or "`" in t:
        m = re.match(r"^(\$HOME|\$\{HOME\})(/.*)?$", t)
        if m:
            t = "~" + (m.group(2) or "")
        elif rebuildable:
            return None
        else:
            return "a variable path: cannot tell what it points to"
    if t.startswith("~+"):
        t = cwd + t[2:]
    elif t.startswith("~") and not re.match(r"^~(/|$)", t):
        expanded = os.path.expanduser(t)
        if expanded == t:                   # ~- (OLDPWD) or an unknown user
            return None if rebuildable else "a ~ form that cannot be told (~-, ~user)"
        t = expanded
    home = home_dir()
    root = project_root(cwd)
    if root:
        root = os.path.realpath(root)
    if session_root and not root:         # `cd .. && rm -rf proj`: still the session's repo
        root = os.path.realpath(session_root)
    path = os.path.normpath(os.path.join(os.path.realpath(cwd), os.path.expanduser(t)))
    if path != "/":     # resolve the parent only: `rm -r link` removes the link, not its target
        path = os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))
    if re.search(r"[*?\[]", os.path.basename(path)):
        parent = os.path.dirname(path)
        if rebuildable:
            return None
        if parent in ("/", home) or (root and parent == root) or (root and inside(root, parent)) or \
                inside(home, parent):
            return "a wildcard at the repo root, the home folder or /"
        path = parent
    parts = path.split(os.sep)
    if path == "/" or inside(home, path):
        return "the home folder, / or a parent of them"
    if root and inside(root, path):
        return "the repo root or a parent of it"
    if ".git" in parts:
        sub = parts[parts.index(".git") + 1:]
        if sub and (sub[0].startswith("rebase-") or sub[0].endswith(".lock")):
            return None                     # a stuck rebase or a stale lock: git's own scratch state
        return "the git history (.git)"
    if root and inside(path, root):
        rel = os.path.relpath(path, root).split(os.sep)
        if any(p in REBUILDABLE or p.endswith(".egg-info") for p in rel):
            return None
        if (len(rel) == 1 and rel[0].lower() in DATA_NAMES) or rel[-1].lower().endswith(DATA_EXT):
            return "a data folder or database file"
        if os.path.isdir(path) and (git_quick(root, ["rev-parse", "-q", "--verify", "HEAD:" + "/".join(rel)])
                                    or git_quick(root, ["ls-files", "-z", "--", path])):
            return "a folder with git-tracked files (only rebuildable folders pass)"
        return None
    if root and is_worktree_of(root, path):
        return None                         # another git worktree of this repo
    if inside(path, home):
        return None if rebuildable else "a path outside this repo"
    if any(inside(path, os.path.realpath(r)) or inside(path, r) for r in temp_roots()):
        return None
    return "a path outside this repo"


def is_worktree_of(root, path):
    out = git_quick(root, ["worktree", "list", "--porcelain"]) or ""
    trees = [os.path.realpath(ln[9:]) for ln in out.splitlines() if ln.startswith("worktree ")]
    return any(os.path.realpath(path) == t and t != os.path.realpath(root) for t in trees)


def git_sub(st, cwd):
    """(subcommand, rest, dir) of a git stage, or (None, [], cwd)."""
    args, d, i = st.args, cwd, 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            d = os.path.normpath(os.path.join(d, os.path.expanduser(args[i + 1])))
        i += 2 if args[i] in GIT_GLOBAL_VALUE else 1
    if i >= len(args):
        return None, [], d
    return args[i], args[i + 1:], d


def current_branch(d):
    return (git_quick(d, ["symbolic-ref", "--short", "-q", "HEAD"]) or "").strip()


def short_flags(rest):
    out = set()
    for a in rest:
        if a.startswith("-") and not a.startswith("--") and len(a) > 1:
            out.update(a[1:])
    return out


def git_destroy_rule(st, cwd):
    if st.exe != "git":
        return None
    sub, rest, d = git_sub(st, cwd)
    if sub == "push":
        return push_rule(rest, d)
    if sub == "reset" and "--hard" in rest:
        branch = current_branch(d)
        if branch in PROTECTED_BRANCHES:
            dirty = git_quick(d, ["status", "--porcelain", "--untracked-files=no"])
            if dirty and dirty.strip():
                return "git reset --hard on %s with uncommitted changes (they would be lost)" % branch
        return None
    if sub == "clean":
        letters, longs = short_flags(rest), {a.split("=")[0] for a in rest if a.startswith("--")}
        if "n" in letters or "--dry-run" in longs:
            return None
        force = "f" in letters or "--force" in longs
        ignored = bool({"x", "X"} & letters)
        paths, skip = [], False
        for a in rest:
            if skip:
                skip = False
                continue
            if a in ("-e", "--exclude"):
                skip = True
                continue
            if a == "--" or a.startswith("-"):
                continue
            paths.append(a)
        root = project_root(d)
        top = bool(paths) and all(re.match(r"^:(/|\(top\))\.?/?$", p) for p in paths)   # :/ = the whole repo
        at_root = root and (top or os.path.realpath(d) == os.path.realpath(root))
        whole = not paths or top or all(p in (".", "./") for p in paths)
        if force and ignored and at_root and whole:
            return "git clean -x at the repo root (deletes ignored files: .env, local databases, caches)"
    return None


def push_rule(rest, d):
    letters, longs = short_flags(rest), {a.split("=")[0] for a in rest if a.startswith("--")}
    if "--mirror" in longs:
        return "git push --mirror (rewrites every branch on the remote)"
    force = "f" in letters or bool(longs & {"--force", "--force-with-lease", "--force-if-includes"})
    delete = "d" in letters or "--delete" in longs
    value_opts = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
    pos, skip = [], False
    for a in rest:
        if skip:
            skip = False
            continue
        if a in value_opts:
            skip = True
            continue
        if a.startswith("-"):
            continue
        pos.append(a)
    specs = pos[1:]
    if any(s.startswith("+") for s in specs):
        force = True
    if "--all" in longs or "--branches" in longs:
        dsts = set(PROTECTED_BRANCHES)
    elif specs:
        dsts = set()
        for s in specs:
            s = s.lstrip("+")
            if ":" in s:
                src, dst = s.split(":", 1)
                if not src:
                    delete = True
                s = dst
            s = re.sub(r"^refs/heads/", "", s)
            dsts.add(current_branch(d) if s in ("HEAD", "@") else s)   # HEAD / @ push the current branch
    else:
        dsts = {current_branch(d)}
    hit = sorted(dsts & PROTECTED_BRANCHES)
    if hit and force:
        return "force push to %s" % hit[0]
    if hit and delete:
        return "deleting %s on the remote" % hit[0]
    return None


COMPOSE_VALUE_OPTS = {"-f", "--file", "-p", "--project-name", "--profile", "--env-file", "--project-directory",
                      "--ansi", "--progress", "--parallel"}
DOCKER_VALUE_OPTS = {"-H", "--host", "-c", "--context", "--config", "-l", "--log-level"}


def first_word(args, value_opts):
    i = 0
    while i < len(args):
        a = args[i]
        if a in value_opts:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a, args[i + 1:]
    return None, []


def compose_rule(st):
    if st.exe in ("docker", "podman"):
        word, rest = first_word(st.args, DOCKER_VALUE_OPTS)
        if word == "volume":
            sub, _r = first_word(rest, set())
            if sub in ("rm", "remove", "prune"):
                return "%s volume %s (deletes stored data)" % (st.exe, sub)
            return None
        if word == "system":
            sub, r = first_word(rest, set())
            if sub == "prune" and "--volumes" in r:
                return "%s system prune --volumes (deletes stored data)" % st.exe
            return None
        if word != "compose":
            return None
        args = rest
    elif st.exe in ("docker-compose", "podman-compose"):
        args = st.args
    else:
        return None
    sub, rest = first_word(args, COMPOSE_VALUE_OPTS)
    if sub != "down":
        return None
    for a in rest:
        if a == "--volumes" or (a.startswith("-") and not a.startswith("--") and "v" in a[1:]):
            return "compose down -v (deletes the named volumes: database data)"
    return None


def sql_rule(st, stages, cmd, cwd, protected):
    if not protected:
        return None
    args = list(st.args)
    exe = st.exe
    if exe in ("docker", "podman", "kubectl"):
        idx = next((i for i, a in enumerate(args) if os.path.basename(a) in SQL_CLIENTS | {"dropdb", "pg_restore"}),
                   None)
        if idx is None:
            return None
        exe, args = os.path.basename(args[idx]), args[idx + 1:]
    names = " ".join(args + list(st.env.values()))
    hit = [n for n in protected if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", names)]
    if exe == "dropdb":
        return "dropdb %s (protected database in .ai/destructive.txt)" % hit[0] if hit else None
    if exe == "pg_restore":
        if hit and ("--clean" in args or "-c" in args):
            return "pg_restore --clean into %s (protected database)" % hit[0]
        return None
    if exe not in SQL_CLIENTS:
        return None
    text = [" ".join(args)]
    if "<<" in cmd:
        text.append(cmd)                     # heredoc bodies are dropped by the tokenizer
    for prev in stages:                      # echo "DROP ..." | psql
        if prev.nxt is st and prev.op in ("|", "|&"):
            text.append(" ".join(prev.args))
    files = [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-f", "--file")]
    files += [a.split("=", 1)[1] for a in args if a.startswith("--file=")]
    files += re.findall(r"<\s*([^\s<>|;&]+\.sql)\b", cmd)
    for f in files:
        data = read_text(os.path.join(cwd, os.path.expanduser(f)))
        if data is None:
            return "SQL from a file that cannot be read (%s) against a protected database" % f if hit else None
        text.append(data[:200 * 1024])
    sql = "\n".join(text)
    m = DESTRUCTIVE_SQL.search(sql)
    if not m:
        return None
    hit = hit or [n for n in protected if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", sql)]
    if hit:
        return "%s on the protected database %s (.ai/destructive.txt)" % (one_line(m.group(1)).upper(), hit[0])
    return None


def repo_cmd_rule(st, prefixes):
    words = [st.exe] + st.args
    for p in prefixes:
        if p and words[:len(p)] == [os.path.basename(p[0])] + p[1:]:
            return "%s (listed in .ai/destructive.txt)" % " ".join(p)
    return None


GATES = {"audit-before-install": gate_audit, "secret-scan": gate_secrets, "pr-rules": gate_pr, "no-sudo": gate_sudo,
         "no-destroy": gate_destroy, "merge-approval": gate_merge, "no-verify": gate_no_verify}
GATE_PROBES = {"audit-before-install": probe_audit, "secret-scan": probe_secrets, "pr-rules": probe_pr,
               "no-sudo": probe_sudo, "no-destroy": probe_destroy, "merge-approval": probe_merge,
               "no-verify": probe_no_verify}


# ---------------------------------------------------------------- regression ledger (docs/REGRESSIONS.md)
# One row per bug that reached main (Tier 1 T3, long tier):
#   R-012 | 2026-11-12 | area: crawler/gone | symptom: ... | cause: ... | test: tests/regressions/test_r012_x.py |
#           reopened: 0
# A row may wrap onto indented lines. Rows are read under "## Ledger" (the whole file when that heading is
# missing); "## Quarantine" holds `- <test id> | since: YYYY-MM-DD | why` lines. ai-ledger --check keeps it honest.

LEDGER_REL = os.path.join("docs", "REGRESSIONS.md")
LEDGER_ROW = re.compile(r"^(R-\d+)\s*\|")
QUARANTINE_ROW = re.compile(r"^\s*[-*]\s+(.+?)\s*\|\s*since:\s*(\d{4}-\d{2}-\d{2})\s*(?:\|\s*(.*))?$")


def parse_ledger(text):
    """{"rows": [{id, date, area: [prefixes], test, reopened (int or None), raw}], "quarantine": [{test, since,
    why}], "bad": [raw lines that start like a row but miss a field]}."""
    rows, quarantine, bad = [], [], []
    scoped = re.search(r"^##\s+Ledger\b", text or "", re.M) is not None
    section, cur = "", None
    for ln in (text or "").splitlines():
        h = re.match(r"^##\s+(.*)$", ln)
        if h:
            section, cur = h.group(1).strip().lower(), None
            continue
        if section.startswith("quarantine"):
            m = QUARANTINE_ROW.match(ln)
            if m:
                quarantine.append({"test": m.group(1).strip("` "), "since": m.group(2), "why": (m.group(3) or "")})
            continue
        if scoped and section != "ledger":
            continue
        if LEDGER_ROW.match(ln):
            cur = {"raw": ln.strip()}
            rows.append(cur)
        elif cur is not None and ln[:1] in (" ", "\t") and ln.strip():
            cur["raw"] += " " + ln.strip()
        else:
            cur = None
    out = []
    for r in rows:
        parts = [p.strip() for p in r["raw"].split("|")]
        row = {"id": parts[0], "date": parts[1] if len(parts) > 1 else "", "area": [], "test": "", "reopened": None,
               "raw": r["raw"]}
        for p in parts[2:]:
            key, sep, val = p.partition(":")
            key = key.strip().lower()
            if not sep:
                continue
            if key == "area":
                row["area"] = [a.strip().strip("`") for a in val.split(",") if a.strip()]
            elif key == "test":
                row["test"] = val.strip().strip("`")
            elif key == "reopened":
                row["reopened"] = int(val.strip()) if val.strip().isdigit() else None
        if not (row["area"] and row["test"] and row["reopened"] is not None and re.match(r"^\d{4}-\d{2}-\d{2}$",
                                                                                         row["date"])):
            bad.append(r["raw"])
        out.append(row)
    return {"rows": out, "quarantine": quarantine, "bad": bad}


def ledger_rows(root):
    return parse_ledger(read_text(os.path.join(root, LEDGER_REL)) if root else "")["rows"]


def ledger_hits(root, rel):
    """[(id, area, test)] for the ledger rows whose area prefix covers the repo-relative path rel."""
    rel = norm_rel(rel)
    out = []
    for row in ledger_rows(root):
        for area in row["area"]:
            a = norm_rel(area).rstrip("/")
            if a and (rel == a or rel.startswith(a + "/")):         # a folder or a file, never a name prefix
                out.append((row["id"], a, row["test"]))
                break
    return out


def norm_rel(path):
    path = path.replace(os.sep, "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def ledger_note(hits, max_ids=3):
    """One reminder line for hits [(id, area, test)], or ''."""
    if not hits:
        return ""
    ids = sorted({h[0] for h in hits}, key=lambda i: int(i.split("-")[1]))
    areas = sorted({h[1] for h in hits})
    tests = sorted({h[2] for h in hits if h[2]})
    shown = ", ".join(ids[:max_ids]) + (" +%d more" % (len(ids) - max_ids) if len(ids) > max_ids else "")
    return ("Regression area %s has %s (docs/REGRESSIONS.md): keep them green, run %s or the whole check."
            % (", ".join(areas[:3]), shown, " ".join(tests[:max_ids]) or "their tests"))


# ---------------------------------------------------------------- project skills: mattpocock opt-ins, verify-<app>
# `skills: a, b` in .ai/enabled lists the mattpocock opt-in skills of a project; ai-adopt links them into
# .claude/skills (Claude) and .agents/skills (Codex). A project verification skill (pstack create-verification-skill)
# lives in .agents/skills/verify-<app>/ (Codex reads it there) with a committed link in .claude/skills.

VERIFY_DIRS = (os.path.join(".agents", "skills"), os.path.join(".claude", "skills"), os.path.join(".cursor", "skills"))
VERIFY_STALE_COMMITS = 25       # code commits since the feature map last changed
VERIFY_STALE_DAYS = 30          # or this many days with at least one code commit since


def project_skills(root):
    """The mattpocock opt-in skills a project lists AND has linked (.claude/skills or .agents/skills)."""
    text = read_text(os.path.join(root, ".ai", "enabled")) if root else None
    names = []
    for ln in (text or "").splitlines():
        m = re.match(r"^\s*skills\s*:\s*(.*)$", ln.split("#", 1)[0], re.I)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip() and n.strip() != "none"]
    return [n for n in names if any(os.path.isfile(os.path.join(root, d, n, "SKILL.md"))
                                    for d in (os.path.join(".claude", "skills"), os.path.join(".agents", "skills")))]


def short_skill(name):
    """The bare skill name: "/ai-core:Ship" and "ship" are the same skill."""
    return str(name).strip().lstrip("/").split(":")[-1].lower()


def skill_md(root, name, agent="claude"):
    """The SKILL.md of skill `name` that exists for this agent: the project link first (.claude/skills for
    Claude, .agents/skills for Codex), then this machine's copy. None when it is not installed."""
    dirs = [os.path.join(".claude", "skills"), os.path.join(".agents", "skills")]
    if agent != "claude":
        dirs.reverse()
    for base in ([root] if root else []) + [os.path.expanduser("~")]:
        for d in dirs:
            path = os.path.join(base, d, name, "SKILL.md")
            if os.path.isfile(path):
                return path
    return None


def typed_only(path):
    """True for a skill with `disable-model-invocation: true`: the Skill tool cannot run it."""
    m = re.match(r"^---\n(.*?)\n---", read_text(path) or "", re.S)
    return bool(m and re.search(r"(?m)^disable-model-invocation\s*:\s*true\s*$", m.group(1)))


def typed_skills_note(root, names, agent="claude"):
    """For the typed-only skills among `names`: read the file and follow it, and tell the owner the typed form.
    The model cannot call them through the Skill tool (owner QA 2026-11-15: the agent fell back). "" for none."""
    rows = []
    for n in names:
        path = skill_md(root, n, agent)
        if path and typed_only(path):
            rows.append("/%s = %s" % (n, path))
    if not rows:
        return ""
    return (" Typed-only skills (no Skill tool call): read the file, follow it, and tell the owner the typed form: "
            "%s." % "; ".join(rows))


# After a merge to main (owner 2026-11-16): the next session runs /improve-codebase-architecture and /retro.
# .ai/last-review (local, gitignored) holds the main commit of the last review. A missing file is set to the
# current main without a nudge (first session after ai-adopt). Repos without .ai/ (not adopted) get nothing.
REVIEW_REL = os.path.join(".ai", "last-review")


def main_commit(root):
    """(branch, sha) of the local main or master branch, or ("", "")."""
    for b in ("main", "master"):
        sha = (git_quick(root, ["rev-parse", "-q", "--verify", b + "^{commit}"]) or "").strip()
        if re.fullmatch(r"[0-9a-f]{7,64}", sha):
            return b, sha
    return "", ""


def merge_review_note(root, agent="claude"):
    if not root or not os.path.isdir(os.path.join(root, ".ai")):
        return ""
    branch, sha = main_commit(root)
    if not sha:
        return ""
    path = os.path.join(root, REVIEW_REL)
    last = (read_text(path) or "").strip()
    if last == sha:
        return ""
    count = (git_quick(root, ["rev-list", "--count", "%s..%s" % (last, sha)]) or "").strip() if last else ""
    if not last or count == "0":
        try:
            with open(path, "w") as fh:
                fh.write(sha + "\n")
        except OSError:
            pass
        return ""
    count = count if count.isdigit() else "some"
    return ("%s moved since the last architecture review (%s new commits after %s). Before new work: "
            "/improve-codebase-architecture on the area that changed, then /retro on the merged work. Findings "
            "become tickets or a PR for the owner, not direct edits on %s. Then record it: git rev-parse %s > "
            ".ai/last-review. The owner may say skip (record it the same way).%s"
            % (branch, count, last[:7], branch, branch,
               typed_skills_note(root, ["improve-codebase-architecture", "retro"], agent)))


def legacy_memory_dir(root):
    """Claude's auto memory folder for this repo (~/.claude/projects/<path with - for each non-alnum>/memory)."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    key = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(root))
    return os.path.join(base, "projects", key, "memory")


def legacy_memory_note(root):
    """Session start: this repo still has Claude auto memory files. Auto memory is off (owner 2026-11-16: the
    repo is the one knowledge store), so they no longer load: move the durable facts into the repo once."""
    if not root:
        return ""
    d = legacy_memory_dir(root)
    try:
        files = sorted(f for f in os.listdir(d) if f.endswith(".md") and f != "MEMORY.md")
    except OSError:
        return ""
    if not files:
        return ""
    return ("This repo has %d old Claude memory file(s) in %s that no longer load (auto memory is off). Ask the "
            "owner, then move each durable fact into the repo on a branch with a PR: commands and paths to the Map, "
            "rules to ## Project rules, decisions to docs/adr, project facts to docs/agents/notes.md. No secrets, "
            "no personal data. After the merge, delete that folder." % (len(files), d))


def upgrade_note():
    """Session start: tools changed version (ai-versions --record wrote upgrades.json "pending")."""
    try:
        data = json.loads(read_text(state_path("upgrades.json")) or "{}")
    except ValueError:
        return ""
    rows = [p for p in (data.get("pending") or []) if isinstance(p, dict) and p.get("tool")][:8]
    if not rows:
        return ""
    return ("Tools upgraded: %s. When the owner's task allows, run the upgrade-review skill (release notes -> "
            "what breaks, what to use -> a dotfiles PR)." % ", ".join(
                "%s %s -> %s" % (p["tool"], p.get("old", "?"), p.get("new", "?")) for p in rows))


def nav_note(root, graph=True, serena=True):
    """The navigation order for a code search: graphify (wide), then Serena (exact). "" when neither is on."""
    parts = []
    if graph and os.path.isfile(os.path.join(root, "graphify-out", "graph.json")):
        parts.append('graphify query "<question>" --budget 1500 (where and how) or graphify affected '
                     '"<path>::<symbol>" (impact)')
    if serena:
        parts.append("Serena find_symbol / find_referencing_symbols (exact symbol, callers, edits)")
    if not parts:
        return ""
    return "Code search: %s first. rg only for text (strings, config, logs)." % ", then ".join(parts)


def verify_skill(root):
    """{"name", "path" (repo-relative skill folder), "features" (count), "features_dir"} or None."""
    if not root:
        return None
    for d in VERIFY_DIRS:
        base = os.path.join(root, d)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for n in names:
            folder = os.path.join(base, n)
            if not n.startswith("verify-") or not os.path.isfile(os.path.join(folder, "SKILL.md")):
                continue
            if os.path.islink(folder):          # the .claude link: report the real folder
                real = os.path.realpath(folder)
                if real.startswith(os.path.realpath(root) + os.sep):
                    folder = os.path.join(root, os.path.relpath(real, os.path.realpath(root)))
            feats = next((f for f in (os.path.join(folder, "features"), os.path.join(folder, "references", "features"))
                          if os.path.isdir(f)), None)
            count = len([f for f in os.listdir(feats) if f.endswith(".md") and f.lower() != "readme.md"]) if feats else 0
            return {"name": n, "path": os.path.relpath(folder, root), "features": count,
                    "features_dir": os.path.relpath(feats, root) if feats else None}
    return None


def verify_staleness(root, info):
    """(code commits since the feature map last changed, days since that change) or None (no git history).
    Stale (time for /maintain-verification-skill): >= VERIFY_STALE_COMMITS such commits, or >= VERIFY_STALE_DAYS
    days with at least one."""
    rel = info.get("features_dir") or info["path"]
    last = (git_quick(root, ["log", "-1", "--format=%H %ct", "--", rel]) or "").split()
    if len(last) < 2:
        return None
    out = git_quick(root, ["log", "--format=%x00%H", "--name-only", "%s..HEAD" % last[0]])
    if out is None:
        return None
    commits = 0
    for chunk in out.split("\0")[1:]:
        files = [ln for ln in chunk.splitlines()[1:] if ln.strip()]
        if any(is_code_file(f) and not f.startswith(info["path"] + "/") for f in files):
            commits += 1
    try:
        days = int((time.time() - int(last[1])) / DAY)
    except ValueError:
        days = 0
    return commits, days


def verify_stale(stats):
    return bool(stats) and (stats[0] >= VERIFY_STALE_COMMITS or (stats[1] >= VERIFY_STALE_DAYS and stats[0] >= 1))


def verify_status_line(root, agent="claude"):
    """One phrase for the session-start status."""
    info = verify_skill(root)
    if not info:
        optional = " (optional in tier try)" if project_tier(root) == "try" else ""
        return "Verify skill: missing, run /create-verification-skill%s%s." % (
            optional, read_and_follow(root, "create-verification-skill", agent))
    stats = verify_staleness(root, info)
    line = "Verify skill: %s (%d features)" % (info["name"], info["features"])
    if verify_stale(stats):
        line += ", stale (%d code commits, %d days since the feature map changed): run /maintain-verification-skill" \
            % stats
        line += read_and_follow(root, "maintain-verification-skill", agent)
    return line + "."


def read_and_follow(root, name, agent="claude"):
    """Short form for the status line: a typed-only skill the agent runs by reading its file."""
    path = skill_md(root, name, agent)
    return " (typed-only; agent: read %s and follow it)" % path if path and typed_only(path) else ""


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
# ai-adopt writes "<!-- AI:map START (ai-adopt; edit freely inside, ...) -->": accept any text after START.
MAP_RX = re.compile(r"<!-- AI:map START[^>]*-->\n?(.*?)<!-- AI:map END -->", re.S)
LIBS_RX = re.compile(r"<!-- AI:libraries START([^>]*)-->\n?(.*?)<!-- AI:libraries END -->", re.S)
MAP_CAP_LINES = 60
# Same list as ai/bin/ai-libs (its lock line records these, sha256 first 12 hex).
LOCKFILES = ("uv.lock", "poetry.lock", "requirements.txt", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
             "go.sum", "Cargo.lock")
MANIFESTS = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "Gemfile", "composer.json")
KNOWLEDGE_CAP = 800


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


# On by default in every project (owner decision 2026-11-12, evening); `no-serena` / `no-graph` in .ai/enabled
# turns one off for that project.
DEFAULT_ON = ("serena", "graph")


def with_defaults(ids):
    ids = set(ids)
    return ids | {d for d in DEFAULT_ON if "no-" + d not in ids}


def enabled_ids(root):
    """Opt-in ids of the project (.ai/enabled), the default-on tools, and `serena` when the project enables the
    ai-serena plugin."""
    text = read_text(os.path.join(root, ".ai", "enabled")) if root else ""
    ids = with_defaults({ln.split("#", 1)[0].strip().lower() for ln in (text or "").splitlines()
                         if ln.split("#", 1)[0].strip()})
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


def knowledge_index(root, agent="claude"):
    """One pointer line (<= 800 chars) for the session start: the Map and Libraries blocks of AGENTS.md, and
    Serena / graph only where the project enabled them. Empty outside a git repo."""
    if not root:
        return ""
    adopted = os.path.isfile(os.path.join(root, ".ai", "enabled"))
    bits = ["tier: %s." % (project_tier(root) if adopted else "none (not adopted; ai-adopt sets it)")]
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
    bits.append(verify_status_line(root, agent))
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


def knowledge_delta(root, new_docs_ids=False, graph_refreshing=False):
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
            and not graph_refreshing and not graphify_hook_installed(root):
        todo.append("run graphify update .")
    if not todo:
        return ""
    return "After this commit: " + "; ".join(todo) + "."


# ---------------------------------------------------------------- graph refresh after agent git calls
# The server's git guard turns git hooks off for agent git calls, so graphify's own post-commit hook does not
# run for them. After a successful commit, merge, pull, checkout, switch or rebase the router starts
# `graphify update <repo>` itself (graphify 0.9.105: code only, incremental, no LLM, no key): detached, nice 10,
# one run per repo at a time (a call during a run marks one more pass), output to ~/.local/state/ai.
GRAPH_GIT_SUBS = {"commit", "merge", "pull", "checkout", "switch", "rebase"}
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}


def graph_git_calls(stages, cwd):
    """Folders of the git calls that change the checked-out code (git [-C dir] commit|merge|pull|...)."""
    out = []
    for st in stages:
        if st.exe != "git":
            continue
        args, d, i = st.args, cwd, 0
        while i < len(args):
            a = args[i]
            if a in GIT_VALUE_OPTS and i + 1 < len(args):
                if a == "-C":
                    d = os.path.join(d, args[i + 1])
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            if a in GRAPH_GIT_SUBS:
                out.append(d)
            break
    return out


def graphify_bin():
    """graphify by absolute path, never a PATH lookup: a root-owned copy first, else the user's uv tool link
    (~/.local/bin, which sandboxed commands and agent edits cannot write)."""
    override = os.environ.get("AI_GRAPHIFY_BIN")
    if override:
        return override if os.path.isfile(override) else ""
    for d in ("/usr/local/bin", "/usr/bin"):
        p = os.path.join(d, "graphify")
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_uid == 0 and not st.st_mode & 0o022:
            return p
    p = os.path.expanduser("~/.local/bin/graphify")
    return p if os.path.isfile(p) else ""


GRAPH_RUNNER = r"""
import fcntl, os, subprocess, sys
root, gfy, lock, pending, log = sys.argv[1:6]
env = dict(os.environ, GRAPHIFY_BACKEND="none", GRAPHIFY_NO_TIPS="1")
os.nice(10)
with open(log, "a") as out:
    while True:
        f = open(lock, "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit(0)         # a run is going: it sees the pending mark and runs once more
        while os.path.exists(pending):
            os.remove(pending)
            try:
                subprocess.run([gfy, "update", root], cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=out,
                               stderr=out, timeout=1800)
            except Exception as exc:
                out.write("graph refresh failed: %s" % exc + chr(10))
        f.close()               # unlock, then look once more: a mark made while this run was ending is not lost
        if not os.path.exists(pending):
            break
"""


def start_graph_refresh(root, build=False):
    """Start the detached refresh for one repo. True when started (or handed to a running one).
    build: also when there is no graph yet (`graphify update` makes the first one)."""
    import hashlib
    import subprocess
    gfy = graphify_bin()
    if not gfy or not (build or os.path.isfile(os.path.join(root, "graphify-out", "graph.json"))):
        return False
    key = hashlib.sha1(os.path.realpath(root).encode("utf-8")).hexdigest()[:12]
    lock, pending = state_path("graph-%s.lock" % key), state_path("graph-%s.pending" % key)
    log = state_path("graphify-update.log")
    try:
        os.makedirs(os.path.dirname(log), mode=0o700, exist_ok=True)
        open(pending, "w").close()      # the request, made before the hook returns (a slow runner start loses none)
    except OSError:
        return False
    py = "/usr/bin/python3" if os.path.isfile("/usr/bin/python3") else sys_executable()
    try:
        subprocess.Popen([py, "-I", "-c", GRAPH_RUNNER, root, gfy, lock, pending, log], cwd=root,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    except OSError:
        return False
    return True


def sys_executable():
    import sys
    return sys.executable


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


# Library names that are also plain English words: a prompt with one is not a docs question.
COMMON_WORDS = {"click", "rich", "echo", "fiber", "spring", "temporal", "express", "next", "gin"}


def prompt_libs(prompt, root):
    """Libraries of the repo's Libraries block (AGENTS.md) that the prompt names (word-bounded, any case).
    Only that block (owner 2026-11-16): a global list of known libraries fired on prompts that were not
    docs questions."""
    text = (prompt or "").lower()
    if not text.strip():
        return set()
    doc = libs_doc(root) if root else None
    names = set(doc["rows"] if doc else ()) - own_names(root)
    hits = set()
    for n in names:
        if len(n) < 3 or n in COMMON_WORDS:
            continue
        if re.search(r"(?<![\w.@/-])" + re.escape(n) + r"(?![\w-])", text):
            hits.add(n)
    return hits


def own_names(root):
    """The project's own package names (a repo of library X is not a docs question about X)."""
    if not root:
        return set()
    out = {os.path.basename(os.path.abspath(root)).lower()}
    try:
        import tomllib
        with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
            name = ((tomllib.load(fh).get("project") or {}).get("name") or "")
        if name:
            out |= {name.lower(), name.lower().replace("-", "_"), name.lower().replace("_", "-")}
    except Exception:
        m = re.search(r"(?m)^name\s*=\s*[\"']([^\"']+)[\"']", read_text(os.path.join(root, "pyproject.toml")) or "")
        if m:
            out.add(m.group(1).lower())
    try:
        name = json.loads(read_text(os.path.join(root, "package.json")) or "{}").get("name") or ""
        if name:
            out.add(name.lower())
    except (ValueError, AttributeError):
        pass
    return out


SYMBOL_RX = re.compile(r"`([A-Za-z_][\w.]{2,60})(?:\(\))?`|\b([a-z][a-z0-9]*_[a-z0-9_]+|[a-z]+[A-Z]\w+|[A-Za-z_]\w{2,}\(\))")


def repo_symbol(prompt, root, timeout=0.4):
    """A code name from the prompt (`name`, snake_case, camelCase, name()) that the repo itself contains, or ""."""
    if not root:
        return ""
    names = []
    for m in SYMBOL_RX.finditer(prompt or ""):
        n = (m.group(1) or m.group(2) or "").rstrip("()").split(".")[-1]
        if len(n) >= 3 and n not in names:
            names.append(n)
    if not names:
        return ""
    import subprocess
    args = ["git", "-C", root, "grep", "--untracked", "-l", "-w", "-I", "-F", "--max-count=1"]
    for n in names[:6]:
        args += ["-e", n]
    try:
        res = subprocess.run(args + ["--", ".", ":!*.md"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return names[0] if res.returncode == 0 and res.stdout.strip() else ""


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
