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
import math
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


SCRIPT_INTERPRETER = re.compile(r"^(python|perl|node|ruby)[\d.]*$")
SCRIPT_RUNNERS = ("uv", "poetry", "pipenv")      # uv run python ...
SCRIPT_WRITE = re.compile(r"write_text|write_bytes|open\([^)]*['\"][wax]\+?['\"]|writeFileSync|appendFileSync"
                          r"|createWriteStream|File\.write")
SCRIPT_PATH = re.compile(r"(?<![\w.])[\w~./-]+\.[A-Za-z]\w*")


def script_writes(stages, cmd):
    """An interpreter stage (python, perl, node, ruby; also behind uv run) whose script writes: a write call in the
    raw text (heredoc bodies are not in the stages), or perl / ruby -i (in place)."""
    for st in stages:
        words = st.args[1:] if st.exe in SCRIPT_RUNNERS and st.args[:1] == ["run"] else [st.exe] + st.args
        if not words or not SCRIPT_INTERPRETER.match(os.path.basename(words[0])):
            continue
        if SCRIPT_WRITE.search(cmd) or (words[0].startswith(("perl", "ruby"))
                                        and any(re.match(r"^-[a-zA-Z]*i", a) for a in words[1:])):
            return True
    return False


def write_targets(stages, cwd, cmd=""):
    """Files a shell command writes: redirections (> >> &>), tee, sed -i, the destination of cp and mv, and for an
    interpreter that writes (script_writes) every file name in the command: a read-and-write script that names an
    agent document counts as its write. shortcut: dd of= and a script file (python fix.py) are not seen."""
    out = []
    if cmd and script_writes(stages, cmd):
        out += SCRIPT_PATH.findall(cmd)
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


def gate_skip_path(env_ok=True):
    """Tests only: AI_GATE_SKIP_FILE together with AI_GATE_SKIP_INSECURE_TEST=1 (the hook's own environment,
    which an agent's command cannot set). env_ok=False for a caller whose environment the agent sets (a git hook)."""
    if env_ok and os.environ.get("AI_GATE_SKIP_INSECURE_TEST") == "1" and os.environ.get("AI_GATE_SKIP_FILE"):
        return os.environ["AI_GATE_SKIP_FILE"], True
    return GATE_SKIP_FILE, False


def gate_skips(stages=None, env_ok=True):
    """({gate: reason} valid now, [notes]). Only a root-owned file not writable by others counts."""
    skips, notes = {}, []
    if stages and any("AI_GATE_SKIP" in st.env for st in stages):
        notes.append("AI_GATE_SKIP in a command does nothing. Only the owner can skip a gate: "
                     "sudo ai-gate-skip <gate> <minutes> <why>.")
    path, test = gate_skip_path(env_ok)
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

# The two bounds keep the patterns linear: with "*", a long run of name characters cost quadratic time (R-017).
# shortcut: a name with over 256 name characters beside the keyword gets no match, widen it when a real name is longer.
KEYWORD = r"(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|access[_-]?key|private[_-]?key|credential)"
NAME_TAIL = KEYWORD + r"[A-Za-z0-9_.-]{0,256}"      # a name from its keyword on: enough where the start of the name is free
NAME = r"[A-Za-z0-9_.-]{0,256}" + NAME_TAIL
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
    ("assigned-secret", re.compile(r"(?i)" + NAME_TAIL + r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']")),
    ("assigned-secret-unquoted",
     re.compile(r"(?i)(?:^\+?|[\s,{;])" + NAME + r"\s*[:=]\s*([^\s\"'#,;{}()\[\]]{16,})\s*(?:$|[#,;}])")),
]
PLACEHOLDER = re.compile(r"(?i)(x{4,}|\*{3,}|\.{3,}|changeme|change[_-]?me|example\S*|your[\w-]*|dummy\S*|redacted|"
                         r"placeholder\S*|todo|none|null|true|false|password|pass|secret|pwd|test|fake\S*|"
                         r"<[^>]*>|\$\{[^}]*\}|\$\(.*\)|\{\{.*\}\})")
# Test fixture paths (ticket 11): in test code only real key shapes block, never assigned words (password = "x").
FIXTURE_PATH = re.compile(r"(^|/)(tests?|__tests__|specs?|fixtures?|__fixtures__|testdata|test[_-]data|mocks?|"
                          r"__mocks__)/|(^|/)(test_[^/]*|[^/]*_test\.\w+|[^/]*\.(test|spec)\.\w+|conftest\.py)$", re.I)
FAKE_MARK = re.compile(r"(?i)test|fake|dummy|sample|example|mock|placeholder|x{4,}|0{6,}|123456")
# Review S4: config and sample files hold real values too, so they are never fixture paths. A sample file
# (.env.example, *.sample) and a config file in a test folder keep every rule; only a value with a clear fake
# marker passes there.
CONFIG_PATH = re.compile(r"(^|/)\.env[^/]*$|\.(properties|ya?ml|toml|ini|json|env|example|sample)$", re.I)
CLEAR_FAKE = re.compile(r"(?i)test|fake|dummy|example|sample|change[_-]?me|x{3,}|placeholder|redacted|^(.)\1+$")


def secret_path_kind(path):
    """"fixture" (test code: ticket 11 rules), "sample" (CLEAR_FAKE values pass) or "" (every rule)."""
    if CONFIG_PATH.search(path or ""):
        return "sample" if FIXTURE_PATH.search(path) or re.search(r"\.(example|sample)$", path, re.I) else ""
    return "fixture" if FIXTURE_PATH.search(path or "") else ""


class ScanTimeout(Exception):
    pass


class Budget(object):
    """Secret-scan time budget: total under 80 s (PreToolUse hook timeout 90 s); git 30 s and gitleaks 60 s per call
    (owner 2026-11-18: the 18 s budget timed out on big pushes)."""

    def __init__(self):
        self.end = time.time() + float(os.environ.get("AI_SCAN_BUDGET_S") or 75)

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
            text = merge_new_lines(repo, scan_git(repo, ["diff", "--cached", "--no-color", "-U0"], budget), budget)
            if act["worktree"]:
                text += scan_git(repo, ["diff", "--no-color", "-U0"], budget) + untracked_text(repo, budget)
            what.add("files to commit")
            hits.extend(gitleaks_scan(repo, "commit", None, allowed, budget, text))
            msg = message_text(act, repo)
            if msg:
                msg_hits = builtin_scan(as_added(msg), allowed)
                if msg_hits:
                    what.add("commit message")
                    hits.extend(msg_hits)
        else:
            text = scan_git(repo, ["log", "-p", "--no-color", "-U0", "-n", "300", "HEAD", "--not", "--remotes"], budget)
            what.add("unpushed commits")
            hits.extend(gitleaks_scan(repo, "push", "-n 300 HEAD --not --remotes", allowed, budget, text))
        hits.extend(builtin_scan(text, allowed))
    return hits, what


def scan_git(repo, args, budget):
    """git output for the scan; a timeout raises ScanTimeout (deny), other errors give "" (not a repo)."""
    import subprocess
    # The path rules read "+++ b/<path>": force the a/ b/ prefixes over the owner's diff config.
    fixed = ["-c", "diff.mnemonicPrefix=false", "-c", "diff.noprefix=false"]
    try:
        res = subprocess.run(["git", "-C", repo] + fixed + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=budget.take(30))
    except subprocess.TimeoutExpired:
        raise ScanTimeout()
    except OSError as exc:
        log_error("git", exc)
        return ""
    return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else ""


def is_diff_header(line):
    return bool(re.match(r"^\+\+\+ (a/|b/|/dev/null)", line))


def merge_new_lines(repo, diff, budget):
    """During a merge (MERGE_HEAD set), keep only the added lines that are new against the merged branch too:
    content already on the default branch (or on the other branch) is not scanned again."""
    head = scan_git(repo, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], budget).strip()
    if not head:
        return diff
    # shortcut: an octopus merge is compared with its first MERGE_HEAD only; upgrade if octopus merges show up.
    other = scan_git(repo, ["diff", "--cached", "--no-color", "-U0", head], budget)
    new = {ln for ln in other.splitlines() if ln.startswith("+") and not is_diff_header(ln)}
    return "\n".join(ln for ln in diff.splitlines() if not ln.startswith("+") or is_diff_header(ln) or ln in new)


def fake_value(value):
    """A provider-shaped value that is not a real key: a test word in it, or too little entropy."""
    if FAKE_MARK.search(value):
        return True
    counts = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    entropy = -sum(c / float(len(value)) * math.log(c / float(len(value)), 2) for c in counts.values())
    return entropy < 3.5


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
    hits, kind = [], ""
    for line in (diff or "").splitlines():
        if is_diff_header(line):
            kind = secret_path_kind(line[6:] if line.startswith("+++ b/") else "")
            continue
        if not line.startswith("+"):
            continue
        for name, rx in SECRET_PATTERNS:
            for mm in rx.finditer(line):
                value = mm.group(1) if rx.groups else mm.group(0)
                if value in allowed:
                    continue
                if kind == "fixture" and (name.startswith(("assigned-secret", "url-with-password"))
                                          or (name != "private-key" and fake_value(value))):
                    continue
                if kind == "sample" and name != "private-key" and CLEAR_FAKE.search(value):
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


def gitleaks_scan(repo, mode, log_opts, allowed, budget, added=""):
    """gitleaks findings that are in the added lines the builtin scan read (a merge does not scan the default
    branch again); in test code only a real key shape counts (no generic rule, no fake value); in a sample or
    test config file a value with a clear fake marker passes (secret_path_kind)."""
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
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=budget.take(60))
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
    out = []
    for f in data:
        secret, rule = f.get("Secret") or "", f.get("RuleID") or "?"
        if secret in allowed or (secret.splitlines() or [""])[0] not in added:
            continue
        kind = secret_path_kind(f.get("File") or "")
        if kind == "fixture" and (rule.startswith("generic") or fake_value(secret)):
            continue
        if kind == "sample" and CLEAR_FAKE.search(secret):
            continue
        out.append("gitleaks:%s" % rule)
    return out


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
PR_FIELDS = ("Evidence", "Door", "Blast Radius")              # these block (ticket 13: the core template)
PR_WARN_FIELDS = ("Docs", "Changed guards")                    # these warn only (and Ledger on fix PRs)
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
                          r"(^|/)(tests?|spec|__tests__)/(.*/)?[^/]+\.(py|[cm]?[jt]sx?|go|rs|rb|java|kt|php|cs|swift)$|"
                          # data-driven test cases (this repo: ai/tests/cases/<rule>.json); fixture JSON does not count
                          r"(^|/)tests?/cases/[^/]+\.json$")
PR_GENERATED = re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|Cargo\.lock|"
                          r"go\.sum|bun\.lockb?|composer\.lock|Gemfile\.lock)$|\.(lock|min\.js|min\.css|snap)$|"
                          r"(^|/)(dist|vendor|generated|__generated__)/|(^|/)\.verify/evidence/")
PR_SIZE_WARN = 400
PR_GATED = ("create", "edit", "ready")      # ticket 05: the verify log on all 3


def gate_pr(ctx, cmd, stages):
    problems, warnings, here, verify = [], [], ctx.cwd or ".", None
    for st in stages:
        if st.exe in ("cd", "pushd", "popd"):
            to = cd_target(st, here)       # the folder the gh command runs in; a failed cd leaves the shell where it was
            here = to if to and os.path.isdir(to) else ctx.cwd or "."
            continue
        if st.exe != "gh" or st.args[:1] != ["pr"] or len(st.args) < 2 or st.args[1] not in PR_GATED:
            continue
        sub, args = st.args[1], st.args[2:]
        if sub == "ready" and "--undo" in args:
            continue
        root = project_root(here) or project_root(ctx.cwd or ".")     # review S2: never skip the checks below
        body_flag = any(a.split("=")[0] in ("--body", "-b", "--body-file", "-F") for a in args)
        content = sub != "edit" or body_flag    # a title or label edit changes no PR content: no proof needed
        diff = pr_diff(ctx, root, args, sub) if root and content else None
        if content:
            verify = verify or pr_verify_log(root, diff)
        if sub == "create" and any(a.split("=")[0] in PR_FILL for a in args):
            problems.append("--fill / --web hide the body from this check: write the body and pass it with --body "
                            "or --body-file")
            continue
        if sub == "ready" or (sub == "edit" and not body_flag):
            continue
        text, unread = pr_body_text(here, cmd, args, stages)
        if unread:
            problems.append("could not read the body file %s (write it before the gh command, or pass the body "
                            "with --body)" % unread)
            continue
        missing = []
        if "```mermaid" not in text:
            missing.append("a ```mermaid diagram")
        if "<!-- author-sessions" not in text:
            missing.append("the <!-- author-sessions block")
        if re.search(r"(?im)^\s*main:\s*unknown\b", text):     # CI has no session: the same rule, no hint
            line = session_line(ctx)
            missing.append("a real main: line in the author-sessions block" + (" (this session: %s)" % line
                                                                                 if line else ""))
        fix = bool(PR_FIX_TITLE.match(flag_value(args, ("--title", "-t")) or ""))
        for name in PR_FIELDS:
            why = pr_field_problem(name, pr_field(text, name))
            if why:
                missing.append(why)
        for name in PR_WARN_FIELDS + (("Ledger",) if fix else ()):
            why = pr_field_problem(name, pr_field(text, name))
            if why and why not in warnings:
                warnings.append(why)
        if sub == "create":
            missing.extend(pr_diff_checks(ctx, diff, fix))
        problems.extend(m for m in missing if m not in problems)
    if warnings:
        ctx.add_context("[ai gate pr-rules] warning, add to the PR body: %s." % "; ".join(warnings))
    wall = "verify-pr" if verify else None      # review P2: hook 4 has its own wall id in walls.jsonl
    if not problems:
        return ("deny", verify, wall) if verify else None
    return ("deny", "PR not ready, missing: %s. Body follows the pr skill template: ## Summary (with a ```mermaid "
            "diagram), ## Evidence (Before and After: command and output tail), ## Merge Danger (**Door:** one-way "
            "or two-way and why; **Blast Radius:** what can break). Author-sessions block at the end. Also "
            "(a warning only): Docs, Changed guards, Ledger on fix PRs. Pass it with --body or --body-file.%s"
            % ("; ".join(problems), "\n" + verify if verify else ""), wall)


def session_line(ctx):
    """The author-sessions `main:` line of this session, from the hook payload; "" without a session id.
    Without herdr the agent has no other way to learn its own session id."""
    if ctx.session in ("", "nosession"):
        return ""
    home, cwd = os.path.expanduser("~"), ctx.cwd or ""
    if home and (cwd == home or cwd.startswith(home + os.sep)):
        cwd = "~" + cwd[len(home):]
    return "main: %s dir: %s" % (ctx.session, cwd)


def pr_body_text(here, cmd, args, stages=()):
    """(body text, unreadable body file path or None). A body file path may use a variable that one simple
    `VAR=value` earlier in the same command sets ($VAR, "$VAR", ${VAR}); a heredoc in the command counts as
    the body (the file it writes does not exist yet)."""
    text, unread = "\n".join(args), None    # one line per word: -b "Evidence: ..." keeps its field at a line start
    heredoc = "<<" in cmd and "--body" in cmd
    for i, a in enumerate(args):
        opt, eq, val = a.partition("=")
        if opt in ("--body-file", "-F"):
            path = val if eq else (args[i + 1] if i + 1 < len(args) else "-")
            if path == "-":
                continue
            path = expand_vars(path, cmd, stages)
            body = None if "$" in path else read_text(os.path.join(here, os.path.expanduser(path)))
            if body is None and not heredoc:
                unread = path
            text += "\n" + (body or "")
    if heredoc:
        text += "\n" + cmd       # heredoc body inside $(cat <<EOF ...) or cat > file <<EOF
    return text, unread


SHELL_ASSIGN = re.compile(r"(?:^|[\s;&|(])([A-Za-z_]\w*)=(\"[^\"$`]*\"|'[^']*'|[^\s;&|()\"'$`]+)(?=[\s;&|)]|$)")


def expand_vars(path, cmd, stages=()):
    """$VAR / ${VAR} in a path, from the one simple VAR=value in the command (no $(...), no other variables).
    Review S3: a variable set twice, set to a value that is not a literal, or set as a prefix of a command
    (`B=x gh ...`: the shell expands $B before that) stays unexpanded, so the body file counts as unread."""
    found = {}
    for m in SHELL_ASSIGN.finditer(cmd):
        found[m.group(1)] = m.group(2).strip("\"'")
    prefix = {k for st in stages if st.exe for k in st.env}

    def value(m):
        name = m.group(1) or m.group(2)
        sets = len(re.findall(r"(?:^|[\s;&|(])%s=" % re.escape(name), cmd))
        return found[name] if name in found and sets == 1 and name not in prefix else m.group(0)
    return re.sub(r"\$\{(\w+)\}|\$(\w+)", value, path)


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


def pr_diff(ctx, root, args, sub="create"):
    """(base ref, head ref, [(added, deleted, path)]) of the PR against its base branch, or None (no base found).
    The base is the one the command names (--base), else origin/HEAD, main or master. The head: --head of a create,
    the PR head of `edit N` or `ready N` (pr_head), else the local HEAD."""
    base = flag_value(args, ("--base", "-B"))
    head = flag_value(args, ("--head", "-H")) if sub == "create" else pr_head(ctx, root, args)
    head = head or "HEAD"
    if ":" in head:
        head = "HEAD"           # owner:branch of a fork: compare the local HEAD
    if base:     # the base the command names, never main instead (ticket 13: --base ai)
        candidates = ["origin/" + base, base]
    else:
        ref = (git_quick(root, ["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"]) or "").strip()
        candidates = ([ref] if ref else []) + ["origin/main", "origin/master", "main", "master"]
    base_ref = next((c for c in candidates if git_quick(root, ["rev-parse", "-q", "--verify", c + "^{commit}"])), None)
    if base_ref is None and base and re.match(r"^[\w./-]+$", base):
        git_quick(root, ["fetch", "-q", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (base, base)], timeout=5)
        if git_quick(root, ["rev-parse", "-q", "--verify", "origin/%s^{commit}" % base]):
            base_ref = "origin/" + base
    numstat = git_quick(root, ["diff", "--numstat", "%s...%s" % (base_ref, head)]) if base_ref else None
    if numstat is None:
        ctx.add_context("[ai gate pr-rules] could not diff against the base branch: the test-file, size and "
                        "verify-log checks did not run.")
        return None
    rows = [tuple(row.split("\t", 2)) for row in numstat.splitlines() if row.count("\t") >= 2]
    return base_ref, head, rows


PR_BOOL_FLAGS = {"--undo", "--remove-milestone"}       # gh pr edit / ready flags without a value


def pr_head(ctx, root, args):
    """Review P1: the head commit of the PR that `gh pr edit|ready <number|URL|branch>` names, from
    `gh pr view <it> --json headRefOid` (read only, 5 s). None without a PR argument. When gh gives no commit,
    or the commit is not in this checkout: None, and the context says the local HEAD was judged."""
    import subprocess
    ref, skip = None, False
    for a in args:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = "=" not in a and a not in PR_BOOL_FLAGS
        else:
            ref = a
            break
    if not ref:
        return None
    argv = ["gh", "pr", "view", ref, "--json", "headRefOid", "-q", ".headRefOid"]
    repo = flag_value(args, ("--repo", "-R"))
    try:
        res = subprocess.run(argv + (["--repo", repo] if repo else []), cwd=root, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=5)
        oid = res.stdout.decode("utf-8", "replace").strip() if res.returncode == 0 else ""
    except Exception:
        oid = ""
    if re.fullmatch(r"[0-9a-f]{40}", oid) and git_quick(root, ["cat-file", "-e", oid + "^{commit}"]) is not None:
        return oid
    ctx.add_context("[ai gate pr-rules] %s: judged the local HEAD, not the PR head." % (
        "the head %s of PR %s is not in this checkout (git fetch it)" % (oid[:12], ref) if oid
        else "gh pr view %s gave no head commit" % ref))
    return None


def pr_diff_checks(ctx, diff, fix):
    """A fix: PR without a test file -> problem; size over PR_SIZE_WARN -> a warning in the context only."""
    if diff is None:
        return []
    base_ref, _head, rows = diff
    files = [r[2] for r in rows]
    lines = sum(int(x) for r in rows if not PR_GENERATED.search(r[2]) for x in r[:2] if x.isdigit())
    out = []
    if fix and not any(PR_TEST_PATH.search(f) for f in files):
        out.append("a test file in the diff of a fix: PR (tests/..., test_*.py, *_test.go, *.test.ts, tests/cases/*.json); none against %s"
                   % base_ref)
    if lines > PR_SIZE_WARN:
        ctx.add_context("[ai gate pr-rules] warning: %d changed lines against %s (generated files left out), over %d. "
                        "Split the PR or say in the body why it must stay one." % (lines, base_ref, PR_SIZE_WARN))
    return out


def pr_verify_log(root, diff):
    """Ticket 05 (hook 4): a PR that changes app code in a project with a verify-<app> skill needs a valid run log
    (valid_verify_logs) at the PR head SHA that finished after the last app-code commit. None = pass."""
    info = verify_skill(root) if diff else None
    if not info:
        return None
    base_ref, head, rows = diff
    code = [r[2] for r in rows if is_code_file(r[2]) and not PR_TEST_PATH.search(r[2])
            and not r[2].startswith(info["path"] + "/")]
    if not code:
        return None
    sha = code_head(root, head)       # an evidence-only commit on top does not move the proven code
    # shortcut: the newest commit that touched the first 500 app-code paths; enough for one PR.
    last = (git_quick(root, ["--literal-pathspecs", "log", "-1", "--format=%H %ct", "%s..%s" % (base_ref, head),
                             "--"] + code[:500]) or "").split()
    last_ct = int(last[1]) if len(last) == 2 else 0
    logs = valid_verify_logs(root)
    if any(c == sha and fin > last_ct for c, fin in logs):
        return None
    newest = max(logs, key=lambda x: x[1]) if logs else None
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_ct)) if last_ct else "?"
    return ("verify proof: the PR changes app code (%s) and this project has %s, but no valid run log is at the PR "
            "head %s with a finish after the last app-code commit %s (%s). %s Run %s on this checkout (launch, "
            "doctor, drive the changed features, cleanup), then retry. Valid .verify/evidence/<run>/run.log: "
            "commit: %s, doctor: PASS, db_writes: no, finished: after %s."
            % (", ".join(code[:3]) + (" ..." if len(code) > 3 else ""), info["name"], sha[:12],
               last[0][:12] if last else "?", when,
               "Newest valid log: commit %s." % newest[0][:12] if newest else "No valid log in this checkout.",
               info["name"], sha, when))


def code_head(root, ref="HEAD"):
    """The newest commit at or before `ref` that changes a path outside .verify/evidence/ (verify-evidence-in-git:
    a commit of the run folder moves HEAD but not the driven code). "" without commits."""
    sha = (git_quick(root, ["log", "-1", "--format=%H", ref, "--", ".", ":(exclude).verify/evidence"],
                     timeout=5) or "").strip()
    return sha or (git_quick(root, ["rev-parse", "-q", "--verify", ref + "^{commit}"]) or "").strip()


def valid_verify_logs(root):
    """[(commit, finished epoch)] of the valid runs of `root` (one parser for the log contract: verify_runs)."""
    return [(r["commit"], r["ts"]) for r in verify_runs(root) if r["valid"]]


def probe_pr(stages, cmd=""):
    return any(st.exe == "gh" and st.args[:1] == ["pr"] and st.args[1:2] in (["create"], ["edit"]) for st in stages)


def probe_pr_gate(stages, cmd=""):
    return any(st.exe == "gh" and st.args[:1] == ["pr"] and st.args[1:2] in [[s] for s in PR_GATED] for st in stages)


# ---------------------------------------------------------------- merge-approval (owner 2026-11-16)
# Every PR goes through the owner. The agent merges only after the owner's latest prompt says so ("merge",
# "merge it", "approve", "lgtm", RO "aprob", RU "мержи"). The router stores that word per session at
# UserPromptSubmit (merge_ok); a later prompt without it clears it. A push to main or master skips the PR, so
# it needs the same OK. The owner merges on GitHub at any time; this gate only stops the agent.

MERGE_OK_RX = re.compile(
    r"^\W*(merge|approved?|lgtm|ship it)\W*$"
    r"|\bmerge\s+(it|this|them|that|the\s+prs?|prs?\b|pr\s*#?\d+|#?\d+\b(?!\s+(?!(now|please|and|too|go|then)\b)[a-z])|now|please|all|everything)\b"
    r"|\bmerge\s+the\s+branch(es)?\b|\blet'?s\s+merge\b(?!\s+[a-z])"   # ticket 12: "merge 18", "lets merge everything"
    # review S8: a number or "let's merge" before a word ("merge 2 files", "let's merge the docs") is not an OK
    r"|\b(please|go\s+ahead\s+and|go\s+ahead,?|you\s+can|ok(ay)?,?|yes,?|now)\s+merge\b"
    r"|^\W*merge\W+(go\s+ahead|do\s+it)\b"          # R-009: "merge go ahead", "merge, go ahead"
    r"|\b(approved?|lgtm|ship\s+it)\b"
    r"|\baprob\w*|\bmergeaz[aă]\b|\bf[aă] merge\b"
    r"|(?<!\w)(смерж\w*|мерж\w*|одобр\w*|сливай)",
    re.I)
NO_MERGE_RX = re.compile(
    r"\b(don'?t|do\s+not|never|not|no|without|before|stop|wait|nu|не)\b\W+(\w+\W+){0,3}?"
    r"(merge|approv|aprob|мерж|смерж|одобр|слив)", re.I)


def owner_merge_ok(prompt):
    """True when the owner's prompt gives the OK to merge. A question ("is it approved?") or a negation
    ("don't merge yet") is not an OK; "merge it?" is."""
    text = (prompt or "").strip()
    if re.search(r"\bmerge\s+(it|this|them|now)\b", text, re.I):
        text = text.rstrip("?")
    return owner_said(text, MERGE_OK_RX, NO_MERGE_RX)


def owner_said(prompt, ok_rx, no_rx):
    """The owner's prompt matches ok_rx, has no negation (no_rx) and is not a question."""
    text = (prompt or "").strip()
    return bool(text) and not text.endswith("?") and not no_rx.search(text) and bool(ok_rx.search(text))


def merge_calls(stages, cwd):
    """What in this command merges into, or pushes to, main/master: ["gh pr merge", ...]. A push is read in the
    checkout it acts on: `cd <dir>` earlier in the command and `git -C <dir>` (ticket 12), not the session folder.
    The shell may stay where it was, so (review S1): a cd inside ( ) does not move the stages after the `)`; a cd
    to a folder that is not a git checkout counts as the session folder; after a cd that may fail (joined by
    anything but &&) a push is read in the old folder and the new one, and either one on main/master counts."""
    out, heres, saved = [], [cwd], []
    for st in stages:
        if st.exe in ("cd", "pushd", "popd"):
            # shortcut: a cd to a variable or `-` falls back to the session folder; upgrade if such pushes show up.
            to = cd_target(st, heres[0])
            to = to if to and os.path.isdir(to) and project_root(to) else cwd
            heres = [to] if st.op == "&&" else list(dict.fromkeys([to] + heres))
        elif st.exe == "gh" and st.args[:2] == ["pr", "merge"]:
            out.append("gh pr merge")
        elif st.exe == "gh" and st.args[:1] == ["api"] and any(re.search(r"/pulls/\d+/merge\b", a)
                                                               for a in st.args):
            out.append("gh api .../pulls/N/merge")
        elif st.exe == "git":
            for here in heres:
                sub, rest, d = git_sub(st, here)
                if sub == "push" and push_targets_main(rest, d):
                    out.append("git push to main/master")
                    break
        if st.op == "(":
            saved.append(heres)
        elif st.op == ")" and saved:
            heres = saved.pop()
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


# ---------------------------------------------------------------- gh-write (owner 2026-11-16)
# gh reads run freely. The PR commands have their own gates (pr-rules, merge-approval, ship). Every other gh
# command can write to GitHub (or we cannot tell), so it asks the owner first.

GH_READS = {"pr": {"view", "list", "diff", "checks", "status", "checkout"}, "issue": {"view", "list", "status"},
            "repo": {"view", "list"}, "run": {"view", "list", "watch"}, "workflow": {"view", "list"},
            "auth": {"status"}, "search": None, "status": None, "version": None, "help": None, "--version": None}
GH_OWN_GATES = {"create", "edit", "ready", "merge"}       # gh pr <these>: the PR gates decide
GH_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
GH_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}


def gate_gh(ctx, cmd, stages):
    writes = [" ".join(["gh"] + st.args[:2]) for st in stages if st.exe == "gh" and gh_writes(st.args)]
    if not writes:
        return None
    return ("ask", "%s writes to GitHub. gh writes other than the PR commands need the owner's OK: say what it "
            "will do and why." % ", ".join(writes))


def gh_writes(args):
    if not args:
        return False
    group, sub = args[0], (args[1] if len(args) > 1 else "")
    if group == "api":
        return gh_api_writes(args[1:])
    if group == "pr" and sub in GH_OWN_GATES:
        return False
    if group in GH_READS:
        subs = GH_READS[group]
        return subs is not None and sub not in subs
    return True


def gh_api_writes(args):
    """gh api is a GET unless -X/--method says otherwise; fields (-f, -F, --input) make it a POST."""
    method = None
    for i, a in enumerate(args):
        opt, eq, val = a.partition("=")
        if opt in ("-X", "--method"):
            method = val if eq else (args[i + 1] if i + 1 < len(args) else "")
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:]
    if method is not None:
        return method.upper() in GH_WRITE_METHODS
    return any(a.partition("=")[0] in GH_FIELD_FLAGS for a in args)


def probe_gh(stages, cmd=""):
    return any(st.exe == "gh" for st in stages)


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


# ---------------------------------------------------------------- worktree-first (owner 2026-11-19)
# Every job runs in its own worktree beside the repo (../<repo>-<slug>), from main or master unless the owner names
# another base. An agent file edit in the checkout of an adopted repo while it is on main or master is denied.

def gate_worktree(ctx, path, stages):
    """Deny an Edit or Write of a tracked or new file in an adopted repo (.ai/) whose checkout is on main or master.
    Gitignored files (local state) and files outside a repo pass."""
    path = os.path.abspath(os.path.join(ctx.cwd or ".", os.path.expanduser(path)))
    folder = os.path.dirname(path)
    while folder and not os.path.isdir(folder):          # a new file in a new folder: ask the nearest real folder
        folder = os.path.dirname(folder) if os.path.dirname(folder) != folder else ""
    root = (git_quick(folder, ["rev-parse", "--show-toplevel"]) or "").strip() if folder else ""
    if not root or not os.path.isdir(os.path.join(root, ".ai")):
        return None
    branch = (git_quick(root, ["branch", "--show-current"]) or "").strip()
    if branch not in PROTECTED_BRANCHES:
        return None
    real = os.path.join(os.path.realpath(folder), os.path.relpath(path, folder))     # macOS: /var is /private/var
    if git_quick(root, ["check-ignore", "-q", "--", os.path.relpath(real, root)]) is not None:
        return None                                       # exit 0: ignored, local state
    repo = os.path.basename(root)
    return ("deny", "%s is on %s. Every job works in its own worktree beside the repo, not on %s. Make one, then "
            "edit the file there:\n  git -C %s fetch -q origin && git -C %s worktree add ../%s-<slug> -b <slug> "
            "origin/%s\nUse the feature slug (a fix: fix-<slug>). Base: origin/%s, unless the owner named another "
            "branch. After the merge, remove the worktree and the branch (ship skill)."
            % (root, branch, branch, root, root, repo, branch, branch), "worktree-first")


# ---------------------------------------------------------------- ask-first (owner 2026-11-20)
# A high-impact step waits for the owner: a service, container or server start, stop or restart; a boot, cron or
# unit change; a deploy; user and access changes; force push and hard reset; kills; SQL writes; rm -r outside safe
# folders. Agents restarted live servers to test their own work (docs/research/agent-behaviour-audit.md). Reads
# pass. Every profile, dev-mac too. The deny tells the agent to show the plan, the risk and the undo, then wait.

SERVICE_TOOLS = {"systemctl", "service", "launchctl"}
SERVICE_CHANGE = {"start", "stop", "restart", "reload", "try-restart", "reload-or-restart", "try-reload-or-restart",
                  "enable", "disable", "reenable", "mask", "unmask", "daemon-reload", "daemon-reexec", "reboot",
                  "poweroff", "halt", "kexec", "isolate", "kill", "set-default", "edit", "link", "preset", "revert",
                  "suspend", "hibernate", "set-property", "load", "unload", "bootstrap", "bootout", "kickstart",
                  "remove", "soft-reboot", "rescue", "emergency"}
POWER_TOOLS = {"reboot", "shutdown", "poweroff", "halt"}
CONTAINER_TOOLS = {"docker", "podman", "docker-compose", "podman-compose"}
CONTAINER_CHANGE = {"stop", "restart", "kill", "rm", "rmi", "down", "pause", "prune"}
KILL_TOOLS = {"kill", "pkill", "killall"}
PACKAGE_TOOLS = {"apt", "apt-get", "aptitude", "dnf", "yum", "snap", "pacman", "zypper"}
PACKAGE_CHANGE = {"install", "remove", "purge", "upgrade", "full-upgrade", "dist-upgrade", "autoremove", "reinstall",
                  "refresh", "erase"}
ACCESS_TOOLS = {"useradd", "userdel", "usermod", "groupdel", "groupmod", "passwd", "chpasswd", "ufw", "iptables",
                "ip6tables", "nft", "chattr", "visudo", "adduser", "deluser"}
# shortcut: a read flag passes even when a change flag is also given; split the flags when an agent does that.
ACCESS_READS = {"ufw": {"status", "show", "version"}, "passwd": {"-S", "--status"}, "nft": {"list"},
                "iptables": {"-L", "-S", "-nL", "-nvL", "-vnL", "-vL", "--list", "--list-rules"},
                "ip6tables": {"-L", "-S", "-nL", "-nvL", "-vnL", "-vL", "--list", "--list-rules"}}
DEPLOY_VERBS = {"wrangler": {"deploy", "publish"}, "fly": {"deploy"}, "flyctl": {"deploy"},
                "vercel": {"--prod", "deploy"}, "netlify": {"deploy"}, "kubectl": {"apply", "delete", "rollout", "scale"},
                "terraform": {"apply", "destroy"}, "helm": {"upgrade", "install", "uninstall"}}
START_VERBS = {"start", "stop", "restart", "enable", "disable", "deploy", "reload"}
# Programs whose own "start" or "stop" word is local work (dev servers, tests) or only text; shells and wrappers.
VERB_SKIP = {"git", "gh", "grep", "rg", "egrep", "echo", "printf", "cat", "sed", "awk", "npm", "npx", "pnpm", "yarn",
             "bun", "make", "uv", "cargo", "go", "pytest", "ls", "find", "head", "tail", "wc", "less", "jq", "test",
             "true", "false", "cd", "export", "read", "tmux", "claude", "codex", "graphify", "serena", "rtk",
             "docker", "podman", "brew", "pip", "pip3", "python", "python3", "node", "ruby", "perl", "deno", "bash",
             "sh", "zsh", "dash", "fish", "eval", "env", "nohup", "time", "timeout", "nice", "ssh", "xargs"}
UNIT_DIRS = re.compile(r"(^|/)(systemd/(system|user)|LaunchAgents|LaunchDaemons|cron\.d|crontabs)(/|$)"
                       r"|^/etc/(sudoers|pam\.d|fstab|ssh/|crontab|rc\.local|default/grub)")
SQL_WRITE = re.compile(r"\b(drop|delete\s+from|update\s+[\w.\"`]+\s+set|truncate|alter\s+table)\b", re.I)


def gate_ask_first(ctx, cmd, stages):
    d = ctx.state.load()
    cwd = ctx.cwd or "."
    why = ask_first_reason(stages, cmd, cwd) or gh_create_reason(stages, d)
    if not why and d.get("read_only"):
        why = read_only_reason(stages, cmd, cwd)
    if not why:
        return None

    # Ticket 04: the owner's typed OK covers every high-impact step for the rest of that turn.
    if d.get("ask_ok"):
        # Ticket 06: the Stop check asks the reply to name it.
        # shortcut: "ran" means the gate let it pass; a later permission refusal still counts. Upgrade at PostToolUse.
        ran = d.setdefault("ask_ran", [])
        if ask_name(why) not in ran:
            ran.append(ask_name(why))
            ctx.state.dirty = True
        return None

    return ("deny", "High-impact step: %s. Stop here. Show the owner the whole plan (every command of it), the risk "
            "(what runs there and what can break) and the undo. Then wait until the owner types go (or ok) once; it "
            "covers the plan for that turn. Never restart a service or a server only to test your own work: test with a dry "
            "run or a config check first. Do not rephrase the command or try another way." % why)


def ask_first_reason(stages, cmd, cwd):
    """The first high-impact stage of the command, as a short reason, or None."""
    for st in stages:
        why = ask_first_stage(st, cmd, cwd)
        if why:
            return why
    for target in write_targets(stages, cwd, cmd):
        if UNIT_DIRS.search(target or ""):
            return "a write to %s (boot, service, cron or access config)" % target
    return None


def ask_first_prompt(d, prompt):
    """UserPromptSubmit, the owner's typed text only: an OK lets every high-impact step pass for this turn; any
    other prompt ends it and tags the turn read-only or not. Records whether the owner asked for a PR, feature or
    fix. Returns the router note ("" for none)."""
    d["ask_ok"] = owner_ask_ok(prompt)
    d["ask_ran"] = []
    d["prompted"] = True
    if ASKED_CHANGE_RX.search(prompt or ""):
        d["asked_change"] = True
    d["read_only"] = read_only_prompt(prompt)
    return "read-only turn: report, then ask." if d["read_only"] else ""


# An OK word opens a prompt of at most 5 words, or an approval phrase is anywhere: "ok, now look at the logs" is
# a reply, not an approval.
# The whole prompt is OK words ("go", "yes do it", "go ahead please"): an OK word inside pasted output or a longer
# request ("the build was approved", "ok check the logs") is not an approval.
ASK_OK_RX = re.compile(r"^\W*((go|ahead|ok(ay)?|yes|yep|do|it|approved?|approve|proceed|please|now|da|fa-?l|да|"
                       r"давай)\W*)+$", re.I)
NO_ASK_RX = re.compile(r"(?<!\w)(don'?t|do\s+not|not|no|never|wait|hold\s+on|nu|нет|не|what|how|why|which|where)"
                       r"(?!\w)", re.I)
ASKED_CHANGE_RX = re.compile(r"\b(prs?|pull\s+requests?|features?|fix\w*|bugs?|issues?|release|implement\w*|build|"
                             r"add|ship)\b|(?<!\w)(repar\w*|adaug\w*|func[tț]i\w*|исправ\w*|добав\w*|фич\w*|"
                             r"релиз\w*)", re.I)


def owner_ask_ok(prompt):
    """True when the prompt is only OK words: go, ok, yes, do it, go ahead, approve, proceed (RO da, fa-l; RU да,
    давай). A negation or a question is not an OK."""
    return owner_said(prompt, ASK_OK_RX, NO_ASK_RX)


def ask_name(why):
    """How a reply names the step: the program and its main verb ("systemctl restart"), or the object of a
    reason that starts with "a " ("a write to /etc/x" gives "/etc/x")."""
    label = why.split(" (")[0].replace(":", "")
    return label.split()[-1] if label.startswith("a ") else " ".join(label.split()[:2])


def ask_first_unnamed(d, reply):
    """Stop: the approved high-impact steps of this turn that the reply does not name. Clears the list, so a
    turn blocks once."""
    ran, d["ask_ran"] = d.get("ask_ran") or [], []
    return [n for n in ran if n.lower() not in reply.lower()]


READ_VERB_RX = re.compile(r"^\W*(please\s+)?(audit|check|research|look\s+(at|into)|review|explain|investigate|"
                          r"verific\w*|analiz\w*|проверь|посмотри)(?!\w)", re.I)
CHANGE_VERB_RX = re.compile(r"\b(fix|add|build|install|deploy|restart|update|implement|change|remove)\b"
                            r"|(?<!\w)(repar\w*|adaug\w*|instaleaz\w*|исправ\w*|добав\w*|установ\w*|"
                            r"перезапуст\w*)", re.I)


def read_only_prompt(prompt):
    """Audit, check, research, look at, review, explain, investigate, or a question, with no change verb."""
    text = (prompt or "").strip()
    return bool(READ_VERB_RX.search(text) or text.endswith("?")) and not CHANGE_VERB_RX.search(text)


def read_only_reason(stages, cmd, cwd):
    """In a read-only turn every host change stops, also outside the classes: a write over ssh (redirect, tee,
    sed -i, cp, mv) and a local write outside the repo, the scratchpad and /tmp."""
    for st in stages:
        why = st.exe == "ssh" and ssh_reason(st, cmd, cwd, remote_write)
        if why:
            return why + " (a host change in a read-only turn)"
    for target in write_targets(stages, cwd, cmd):
        if not target.startswith("/dev/") and not safe_rm_target(target, cmd, cwd):
            return "a write to %s (outside the repo in a read-only turn)" % target
    return None


def remote_write(stages, cmd, cwd):
    return next((t for t in write_targets(stages, cwd, cmd) if not t.startswith("/dev/")), None)


GH_CREATE = {("pr", "create"), ("issue", "create"), ("release", "create")}


def gh_create_reason(stages, d):
    """gh pr, issue or release create when the owner did not ask for a PR, feature or fix in this session."""
    # shortcut: a session with no prompt seen yet (no state) passes, as the old gates did; upgrade if one shows up.
    if d.get("asked_change") or not d.get("prompted"):
        return None
    for st in stages:
        if st.exe == "gh" and tuple(st.args[:2]) in GH_CREATE:
            return "gh %s %s (the owner did not ask for a PR, feature or fix in this session)" % tuple(st.args[:2])
    return None


def probe_ask_first(stages, cmd=""):
    return bool(stages)


def ask_first_stage(st, cmd, cwd):
    exe, args = st.exe, st.args
    words = [a for a in args if not a.startswith("-")]
    if exe == "ssh":
        return ssh_reason(st, cmd, cwd)
    if exe in ("npx", "bunx", "uvx") or (exe in ("pnpm", "yarn") and args[:1] == ["dlx"]):
        # shortcut: a runner option with a value (npx -p x) hides the program; split them when agents use it.
        rest = [a for a in (args[1:] if exe in ("pnpm", "yarn") else args) if not a.startswith("-")][:1]
        if rest:
            i = args.index(rest[0])
            st = Stage([(re.sub(r"(.)@[^/]*$", r"\1", rest[0]), False)] + [(a, False) for a in args[i + 1:]], "")
            return ask_first_stage(st, cmd, cwd)
        return None
    if exe in SERVICE_TOOLS:
        verbs = [a for a in args if a in SERVICE_CHANGE]
        if exe == "service":
            verbs = [w for w in words[1:2] if w in SERVICE_CHANGE]      # service <name> <verb>
        if verbs:
            return "%s %s (a service change)" % (exe, verbs[0])
    if exe in POWER_TOOLS or (exe == "init" and words[:1] in (["0"], ["6"])):
        return "%s (a server power change)" % exe
    if exe in CONTAINER_TOOLS:
        sub = words[:3]
        if any(w in CONTAINER_CHANGE for w in sub) or ("up" in sub and ("-d" in args or "--detach" in args)):
            return "%s %s (a container change)" % (exe, " ".join(sub))
    if exe == "crontab" and "-l" not in args:
        return "crontab %s (a cron change)" % " ".join(args)
    if exe in KILL_TOOLS and not own_job_kill(st, cmd):
        return "%s %s (it stops a process)" % (exe, " ".join(args))
    if exe == "tmux" and words[:1] and words[0] in ("kill-session", "kill-server", "kill-window"):
        return "tmux %s (it stops a session and its processes)" % words[0]
    if exe in PACKAGE_TOOLS and any(w in PACKAGE_CHANGE for w in words[:2]):
        return "%s %s (a package change)" % (exe, " ".join(words[:2]))
    # brew install already waits for the owner in audit-before-install.
    if exe == "brew" and words[:1] in (["uninstall"], ["remove"], ["upgrade"], ["reinstall"]):
        return "brew %s (a package change)" % words[0]
    if exe == "brew" and words[:1] == ["services"] and any(w in START_VERBS for w in words[1:3]):
        return "brew %s (a service change)" % " ".join(words[:2])
    if exe in ACCESS_TOOLS and not ACCESS_READS.get(exe, set()) & set(args):
        return "%s (a user or access change)" % exe
    if exe == "git":
        why = git_high_impact(args)
        if why:
            return why
    if exe in DEPLOY_VERBS:
        if not any(a.split("=")[0] == "--dry-run" for a in args) and any(a in DEPLOY_VERBS[exe] for a in args):
            return "%s %s (a deploy)" % (exe, " ".join(words[:2]))
        return None
    if exe in SQL_CLIENTS and SQL_WRITE.search(" ".join(args)):
        return "a database write through %s" % exe
    if exe == "rm" and any(re.match(r"^-[a-zA-Z]*[rR]", a) or a == "--recursive" for a in args):
        bad = [t for t in words if not safe_rm_target(t, cmd, cwd)]
        if bad:
            return "rm -r %s (outside a temp, scratch or rebuildable folder)" % " ".join(bad[:3])
    if exe and exe not in VERB_SKIP and any(w in START_VERBS for w in words[:3]) and not local_test_program(st, cmd):
        return "%s %s (a program start or stop)" % (exe, " ".join(words[:3]))
    return None


def ssh_reason(st, cmd, cwd, judge=None):
    """The same rules as a local command (or judge), for each text an ssh stage runs on the other host that the
    gate can read. A script it cannot read passes, as a local `bash x.sh` does."""
    for text in remote_texts(st, cmd, cwd):
        # The remote folder is unknown: "/" makes a relative rm -r count as outside the repo.
        why = text and (judge or ask_first_reason)(parse_command(text), text, "/")
        if why:
            return why + " over ssh"
    return None


SSH_VALUE_OPTS = set("BbcDEeFIiJLlmOoPpQRSWw")      # ssh options that take the next word as their value
# A heredoc and the line text before it: the body feeds the stage that starts after the last ; & or |.
HEREDOC = re.compile(r"^([^\n]*?)(?<!<)<<(?!<)-?[ \t]*(['\"]?)([\w.-]+)\2[^\n]*\n(.*?)^[ \t]*\3[ \t]*$",
                     re.S | re.M)


def remote_texts(st, cmd, cwd):
    """The command texts of `ssh [opts] host <words>`: the words ssh joins with spaces, and the local text that a
    remote `bash -s` reads (None when the gate cannot read it). [] for an interactive login."""
    args, i = st.args, 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "--":
            i += 1
            break
        i += 2 if len(args[i]) == 2 and args[i][1] in SSH_VALUE_OPTS else 1
    remote = " ".join(args[i + 1:])
    if not remote:
        return []
    if not any(SHELLS.match(s.exe) and runs_stdin_as_code(s) for s in parse_command(remote)):
        return [remote]
    return [remote, stdin_text(st, cmd, cwd)]


def stdin_text(st, cmd, cwd):
    for op, target in st.redirs:
        if op == "<<<":
            return target
        if op == "<":
            path = os.path.join(cwd, os.path.expanduser(expand_vars(target, cmd)))
            # A device, a FIFO or a huge file would hang or kill the hook, and a dead hook lets the command run.
            if "$" in path or "`" in path or not os.path.isfile(path) or os.path.getsize(path) > 1_000_000:
                return None
            return read_text(path)
    # shortcut: a heredoc counts when an ssh stage starts it; with two ssh heredocs, both bodies count for each.
    bodies = [m.group(4) for m in HEREDOC.finditer(cmd) if re.search(r"\bssh\b", re.split(r"[;&|]", m.group(1))[-1])]
    return "\n".join(bodies) or None


def local_test_program(st, cmd):
    """A program the command itself defines or names by a variable (a test helper), or one that works on a temp
    folder (a throwaway database in the scratchpad): its start or stop touches nothing that runs for the owner."""
    if st.exe.startswith("$") or re.search(r"(^|[\s;{(])%s\s*\(\)" % re.escape(st.exe), cmd):
        return True
    return any(temp_path(a) for a in st.args)


def git_high_impact(args):
    words = [a for a in args if not a.startswith("-")]
    if "push" in words and ("f" in short_flags(args) or any(a == "--force" or a.startswith("--force-with-lease")
                                                          for a in args) or any(w.startswith("+") for w in words)):
        return "git push --force (it rewrites the remote history)"
    if "reset" in words and "--hard" in args:
        return "git reset --hard (it drops local changes)"
    if "branch" in words and any(a in ("-D", "--delete") for a in args) and PROTECTED_BRANCHES & set(words):
        return "git branch -D of main or master"
    return None


def own_job_kill(st, cmd):
    """kill of a job this command started ($!, %1) or a signal check (kill -0) is local test cleanup."""
    if st.exe != "kill":
        return False
    targets = [a for a in st.args if not a.startswith("-")]
    if "-0" in st.args or (targets and all(a.startswith("%") for a in targets)):
        return True
    return bool(targets) and "$!" in cmd and all(a.startswith("$") for a in targets)


def safe_rm_target(target, cmd, cwd):
    """A temp, scratchpad or rebuildable folder, or a path inside the current repo (not its root or .git)."""
    path = expand_vars(target, cmd)
    if "$" in path or "`" in path:
        return True     # shortcut: an unresolved variable passes (agents keep scratch paths in $S); the rule covers it
    path = os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))
    if temp_path(path) or rebuildable_name(path):
        return True
    root = project_root(cwd)
    return bool(root) and path.startswith(root.rstrip("/") + "/") and "/.git" not in path[len(root):]


def temp_path(path):
    """A path inside a temp root (the roots of no-destroy) or a scratchpad, not the root itself."""
    return "/scratchpad" in path or any(path.startswith(r.rstrip("/") + "/") for r in temp_roots())


FILE_GATES = {"worktree-first"}      # gates that judge the file of an Edit or Write, not a shell command
# shortcut: shell writes (sed -i, >) and Codex apply_patch on main are not judged; add them when agents use them.

GATES = {"audit-before-install": gate_audit, "secret-scan": gate_secrets, "pr-rules": gate_pr, "no-sudo": gate_sudo,
         "no-destroy": gate_destroy, "merge-approval": gate_merge, "no-verify": gate_no_verify, "gh-write": gate_gh,
         "worktree-first": gate_worktree, "ask-first": gate_ask_first}
GATE_PROBES = {"audit-before-install": probe_audit, "secret-scan": probe_secrets, "pr-rules": probe_pr_gate,
               "no-sudo": probe_sudo, "no-destroy": probe_destroy, "merge-approval": probe_merge,
               "no-verify": probe_no_verify, "gh-write": probe_gh, "ask-first": probe_ask_first}


# ---------------------------------------------------------------- one entry for a check (rules-that-hold 05)
# ai-check, ai-precommit and CI call run_check. It calls the gate function of the agent hook (GATES) with a
# context that has no session. The input (a command line, the staged diff, a PR body file) is data: it is
# parsed, never run.

CHECK_INPUTS = {"secret-scan": ("command", "staged"), "pr-rules": ("command", "pr-body"),
                "text": ("command", "staged", "pr-body")}
CHECK_NOT_OFFERED = {
    "merge-approval": "the owner's OK lives in the agent session",
    "writing-for-agents": "the proof is a skill load in the agent session",
    "ship": "the proof is a skill run in the agent session",
    "ask-first": "it asks the owner in the agent session",
    "gh-write": "it asks the owner in the agent session",
    "no-verify": "it judges an agent command; git skips its own hooks under --no-verify, so CI checks again",
    "no-sudo": "it judges an agent command before it runs; git and CI see no command",
    "no-destroy": "it judges an agent command before it runs; git and CI see no command",
    "audit-before-install": "it judges an agent install command before it runs; git and CI see no command",
    "worktree-first": "it judges an agent file edit before it happens; git and CI see no edit",
}
EM_DASH = "\u2014"      # the escape, never the character: the lint reads this file too
STE_WORDS = 25
MD_EXTS = (".md", ".markdown", ".mdx")
TEXT_LINT_ALLOW_REL = os.path.join(".ai", "text-lint-allow")
# Vendored and generated files: their text is not ours to fix. A project adds its own globs to .ai/text-lint-allow.
TEXT_LINT_DEFAULT = ("vendor/*", "*/vendor/*", "node_modules/*", "*/node_modules/*", "graphify-out/*",
                     ".verify/evidence/*", "*.lock", "*.lockb", "*-lock.json", "*-lock.yaml")


class CheckCtx(object):
    """The part of the router context that the offered gates read, for a run with no agent session."""

    def __init__(self, cwd):
        self.cwd = cwd
        self.session = "nosession"
        self.contexts = []

    def add_context(self, text):
        self.contexts.append(text)


def run_check(gate, cwd, cmd=None, staged=False, body=None, title=None, base=None):
    """(problem or None, notes) of one gate on one input. A problem means fail. CI gives the PR title and base."""
    import shlex
    import shutil
    ctx = CheckCtx(cwd)
    if gate == "text":
        return text_problem(ctx, cwd, cmd, staged, body), ctx.contexts

    if staged:
        cmd = "git commit"
    elif body is not None:
        cmd = "gh pr create --body-file " + shlex.quote(os.path.abspath(body)) + "".join(
            " %s %s" % (flag, shlex.quote(value)) for flag, value in (("--title", title), ("--base", base)) if value)
    if gate == "secret-scan" and not shutil.which("gitleaks"):
        ctx.add_context("gitleaks not found: built-in patterns only.")
    verdict = GATES[gate](ctx, cmd, parse_command(cmd))
    return (verdict[1] if verdict else None), ctx.contexts


def text_problem(ctx, cwd, cmd, staged, body):
    """The text gate (rules-that-hold 07) on the added lines of the staged diff, a PR text file or a command line.
    An em dash fails. A Markdown sentence over STE_WORDS words is a warning note; AI_STE_STRICT=1 makes it fail.
    In the staged diff, a path that matches the text-lint allow list is skipped."""
    if staged:
        diff = scan_git(cwd, ["diff", "--cached", "--no-color", "-U0"], Budget())
    elif body is not None:
        diff = "+++ b/%s\n" % os.path.basename(body) + as_added(read_text(body) or "")
    else:
        diff = "+++ b/command\n" + as_added(cmd or "")
    allow = text_lint_allow(cwd) if staged else ()
    problems = []
    hits = em_dash_lines(diff, allow)
    if hits:
        problems.append("the em dash character (U+2014) at %s. Use '-', ':' or a new sentence. A quote of another "
                        "person: add its file glob to %s." % (first_ten(hits), TEXT_LINT_ALLOW_REL))
    long = long_sentence_lines(diff, allow)
    if long:
        text = "a Markdown sentence over %d words (ASD-STE100) at %s. Split it." % (STE_WORDS, first_ten(long))
        if owner_config("AI_STE_STRICT") == "1":
            problems.append(text)
        else:
            ctx.add_context("warning: " + text)
    return " ".join(problems) or None


def em_dash_lines(diff, allow=()):
    """["path:line"] of the added lines in a -U0 diff that hold the em dash. The one copy of the check."""
    return ["%s:%d" % (path, n) for path, n, text in added_lines(diff)
            if EM_DASH in text and not text_lint_allowed(path, allow)]


def long_sentence_lines(diff, allow=()):
    """["path:line (N words)"] of the Markdown sentences over STE_WORDS words in the added lines of a -U0 diff.
    One run of added lines is one text."""
    # shortcut: an added line inside an old paragraph is read alone, upgrade when warnings on edits look wrong
    out = []
    for path, start, lines in added_runs(diff):
        if not path.lower().endswith(MD_EXTS) or text_lint_allowed(path, allow):
            continue
        for words in long_sentences("\n".join(lines), STE_WORDS):
            head = " ".join(words[:3])
            at = next((i for i, ln in enumerate(lines) if head in " ".join(ln.split())), 0)
            out.append("%s:%d (%d words)" % (path, start + at, len(words)))
    return out


def added_lines(diff):
    """(path, line number, text) of each added line in a -U0 diff. A binary file has none."""
    path, line_no = "", 1
    for line in diff.splitlines():
        if is_diff_header(line):
            path, line_no = (line[6:] if line.startswith("+++ b/") else ""), 1
        elif line.startswith("@@"):
            m = re.match(r"^@@ -\S+ \+(\d+)", line)
            line_no = int(m.group(1)) if m else 1
        elif line.startswith("+"):
            yield path, line_no, line[1:]
            line_no += 1


def added_runs(diff):
    """[(path, first line number, [text, ...])] of the runs of next-to-each-other added lines."""
    runs = []
    for path, n, text in added_lines(diff):
        if runs and runs[-1][0] == path and runs[-1][1] + len(runs[-1][2]) == n:
            runs[-1][2].append(text)
        else:
            runs.append((path, n, [text]))
    return runs


def text_lint_allow(root):
    """The globs of the files that the text lint skips: the defaults, then the lines of .ai/text-lint-allow."""
    lines = [ln.split("#", 1)[0].strip() for ln in (read_text(os.path.join(root, TEXT_LINT_ALLOW_REL)) or "").splitlines()]
    return TEXT_LINT_DEFAULT + tuple(ln for ln in lines if ln)


def text_lint_allowed(path, allow):
    import fnmatch
    return any(path == glob or fnmatch.fnmatch(path, glob) for glob in allow)


def first_ten(items):
    return ", ".join(items[:10]) + (" (%d more)" % (len(items) - 10) if len(items) > 10 else "")


def owner_config(key):
    """An owner value: the env, else a KEY=value line in ~/.config/ai/config.env, else None."""
    if os.environ.get(key):
        return os.environ[key]
    for line in (read_text(os.path.expanduser("~/.config/ai/config.env")) or "").splitlines():
        m = re.match(r"^\s*(?:export\s+)?%s\s*=\s*[\"']?([^\"'#]*)" % re.escape(key), line)
        if m:
            return m.group(1).strip()
    return None


MD_NOT_PROSE = re.compile(r"\A---\n.*?^---[^\n]*$|^[ \t]*```.*?^[ \t]*```[^\n]*$|^[ \t]*~~~.*?^[ \t]*~~~[^\n]*$|"
                          r"<!--.*?(?:-->|\Z)|^[ \t]*(#|\||>)[^\n]*$|^(    |\t)[^\n]*$", re.S | re.M)
MD_FENCE = re.compile(r"^[ \t]*(```|~~~)", re.M)
MD_MAX_CHARS = 200000
MD_LIST_ITEM = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]+", re.M)


def long_sentences(text, limit):
    """The sentences of Markdown prose with more than `limit` words, each as its list of words (ASD-STE100: 25 words
    at most in a description, 20 in an instruction). Not prose: the front matter, a code block, a table row, a
    heading, a quote, an HTML comment, a link target. Inline code is one word. A list item and a paragraph each end
    a sentence. Not checked: an odd number of fence lines (an edit inside a code block), a text over MD_MAX_CHARS."""
    if len(text) > MD_MAX_CHARS or len(MD_FENCE.findall(text)) % 2:
        return []
    text = MD_NOT_PROSE.sub("\n\n", text)
    text = re.sub(r"`[^`\n]*`", "code", text)
    text = re.sub(r"\]\([^)\s]*\)", "]", text)
    text = MD_LIST_ITEM.sub("\n\n", text)
    out = []
    for sentence in re.split(r"(?<=[.!?:])\s+|\n[ \t]*\n", text):
        words = [w for w in sentence.split() if re.search(r"\w", w)]
        if len(words) > limit:
            out.append(words)
    return out


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
    gone = gone_branches(root)
    trees = branch_worktrees(root)
    clean = (" Merged branches still here (remote branch gone): %s. Remove each worktree first (git worktree "
             "remove <path>), then git branch -D <name> and git worktree prune." % ", ".join(
                 "%s (git worktree remove %s)" % (b, trees[b]) if b in trees else b for b in gone[:10])) if gone else ""
    # verify-evidence-in-git: committed run folders older than 7 days leave main through a cleanup PR
    prune = (" Committed verify evidence: on a new branch from %s (chore-prune-evidence-<date>) run ai-evidence-prune "
             "(it removes runs older than 7 days and keeps the newest run of each feature), commit, push and open "
             "a PR for the owner." % branch) if git_quick(root, ["ls-files", "--", EVIDENCE_REL]) else ""
    return ("%s moved since the last architecture review (%s new commits after %s). Before new work: "
            "/improve-codebase-architecture on the area that changed, then /retro on the merged work. Findings "
            "become tickets or a PR for the owner, not direct edits on %s. Then record it: git rev-parse %s > "
            ".ai/last-review. The owner may say skip (record it the same way).%s%s%s"
            % (branch, count, last[:7], branch, branch, clean, prune,
               typed_skills_note(root, ["improve-codebase-architecture", "retro"], agent)))


def branch_worktrees(root):
    """{branch: path} of the linked worktrees of the repo (not the main checkout)."""
    out, path, first = {}, None, True
    for line in (git_quick(root, ["worktree", "list", "--porcelain"]) or "").splitlines():
        if line.startswith("worktree "):
            path = line[9:]
        elif line.startswith("branch refs/heads/") and path:
            if not first:
                out[line[18:]] = path
            first = False
    return out


def gone_branches(root):
    """Local branches whose remote branch is gone (merged and deleted on the remote). Local refs only: no network."""
    out = git_quick(root, ["for-each-ref", "--format=%(refname:short) %(upstream:track)", "refs/heads"]) or ""
    return [line.split()[0] for line in out.splitlines() if line.endswith(" [gone]")]


def legacy_memory_dir(root):
    """Claude's auto memory folder for this repo (~/.claude/projects/<path with - for each non-alnum>/memory)."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    key = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(root))
    return os.path.join(base, "projects", key, "memory")


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
    Stale (time for maintain-verification-skill): >= VERIFY_STALE_COMMITS such commits, or >= VERIFY_STALE_DAYS
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
    """One phrase for the session-start status. A missing tool is an agent task (verify-enforcement 01)."""
    info = verify_skill(root)
    if not info:
        return ("Verify skill: missing. Agent task: build verify-<app> with create-verification-skill%s at the first "
                "feature task, and prove it with one real run." % read_and_follow(root, "create-verification-skill",
                                                                                   agent))
    stats = verify_staleness(root, info)
    line = "Verify skill: %s (%d features)" % (info["name"], info["features"])
    if verify_stale(stats):
        line += (", stale (%d code commits, %d days since the feature map changed). Agent task: run "
                 "maintain-verification-skill now" % stats)
        line += read_and_follow(root, "maintain-verification-skill", agent)
    return line + "."


# ---------------------------------------------------------------- verify evidence (verify-enforcement 02, 03, 04)
# The log contract (ai/rules/verification-skill.md): .verify/evidence/<run>/run.log in the root of the checkout
# that ran it, with `commit: <40 hex>`, `doctor: PASS|FAIL`, `db_writes: yes|no`, `finished: <UTC ISO 8601>`.

EVIDENCE_REL = os.path.join(".verify", "evidence")
RUN_LOG_KEYS = ("commit", "doctor", "db_writes", "finished")


def verify_runs(root):
    """Every run.log of the checkout `root`, newest `finished` first (unfinished last): dicts with the 4 fields,
    "run" (folder name), "ts" (finished, epoch; 0 when missing or bad), "valid" and "why" (why it does not count)."""
    base = os.path.join(root or "", EVIDENCE_REL)
    try:
        names = os.listdir(base)
    except OSError:
        return []
    out = []
    for name in names:
        text = read_text(os.path.join(base, name, "run.log"))
        if text is None:
            continue
        f = {}
        for ln in text.splitlines():
            key, sep, value = ln.partition(":")
            if sep and key.strip() in RUN_LOG_KEYS and key.strip() not in f:
                f[key.strip()] = value.strip()
        ts = parse_iso(f["finished"]) if f.get("finished") else 0.0
        missing = [k for k in RUN_LOG_KEYS if k not in f]
        why = ("missing %s" % ", ".join(missing) if missing
               else "commit is not a 40-hex sha" if not re.fullmatch(r"[0-9a-f]{40}", f["commit"])
               else "doctor %s" % f["doctor"] if f["doctor"] != "PASS"
               else "db_writes %s (a direct database write)" % f["db_writes"] if f["db_writes"] != "no"
               else "finished is not a UTC ISO 8601 time" if not ts else "")
        out.append(dict(f, run=name, ts=ts, valid=not why, why=why))
    return sorted(out, key=lambda r: r["ts"], reverse=True)


def verify_proof(root, since=0.0):
    """(True, "") when a valid run of `root` finished at or after `since` (epoch); else (False, a note on the runs
    that do not count, or "")."""
    runs = verify_runs(root)
    if any(r["valid"] and r["ts"] >= since for r in runs):
        return True, ""
    bad = [r for r in runs if not r["valid"] and (r["ts"] >= since or not r["ts"])][:3]
    return False, "; ".join("run %s does not count: %s" % (r["run"], r["why"]) for r in bad)


VERIFY_STEP_NAMES = ("launch", "doctor", "drive", "cleanup")


def verify_steps(root, info):
    """What to run, for a block message: the skill's SKILL.md and the first command of its Launch, Doctor, Drive
    and Cleanup sections (a code block line, else an inline `command`)."""
    path = os.path.join(root, info["path"], "SKILL.md")
    parts = []
    for sec in re.split(r"^##[ \t]+", read_text(path) or "", flags=re.M)[1:]:
        title, _nl, body = sec.partition("\n")
        name = title.strip().split(" ")[0].lower()
        m = re.search(r"```[^\n]*\n\s*([^\n]+)", body) or re.search(r"`([^`\n]+)`", body)
        if name in VERIFY_STEP_NAMES and m and name not in [p[0] for p in parts]:
            parts.append((name, m.group(1).strip()))
    steps = "; ".join("%s: %s" % p for p in parts) or "launch, doctor, drive the changed feature, cleanup"
    return ("In %s, run %s on the changed feature (read %s and follow it). %s. Its helper writes "
            ".verify/evidence/<run>/run.log; a run counts with doctor: PASS and db_writes: no."
            % (root, info["name"], path, steps))


def app_code_state(root, base):
    """{repo-relative path: content sha1, or "deleted"} of the code files of the checkout `root` that differ from
    commit `base` (committed since, staged, unstaged or untracked). Tests count; the verify skill does not."""
    skill = verify_skill(root)
    skip = tuple(os.path.join(d, "verify-") for d in VERIFY_DIRS) + (".verify/",) + \
        ((skill["path"] + "/",) if skill else ())
    names = (git_quick(root, ["diff", "--name-only", "-z", base, "--"], timeout=5) if base
             else git_quick(root, ["ls-files", "-z"], timeout=5)) or ""
    names += git_quick(root, ["ls-files", "-o", "--exclude-standard", "-z"], timeout=5) or ""
    out = {}
    for rel in names.split("\0"):
        if not rel or not is_code_file(rel) or rel.startswith(skip):
            continue
        out[rel] = file_digest(os.path.join(root, rel))
    return out


def file_digest(path, cap=1 << 20):
    """sha1 of a file for change checks, safe on any tree (review S7): a symlink is not followed (its target text
    counts), a file that is not regular counts by its type, and only the first `cap` bytes plus the size are read.
    "deleted" when it is gone."""
    import hashlib
    import stat
    try:
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            return hashlib.sha1(b"link:" + os.fsencode(os.readlink(path))).hexdigest()
        if not stat.S_ISREG(st.st_mode):
            return "special:%o" % stat.S_IFMT(st.st_mode)
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read(cap) + b"size:%d" % st.st_size).hexdigest()
    except OSError:
        return "deleted"


def head_at(root, ts):
    """HEAD of the checkout `root` at time `ts` (epoch), from its reflog: a worktree made later gives its first
    HEAD. Without ts or reflog: HEAD now. None without commits."""
    if ts:
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts - 1))    # 1 s back: a commit in the same second
        sha = (git_quick(root, ["rev-parse", "-q", "--verify", "HEAD@{%s}" % iso]) or "").strip()
        if sha:
            return sha
    return (git_quick(root, ["rev-parse", "-q", "--verify", "HEAD"]) or "").strip() or None


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
KNOWLEDGE_CAP = 800


def is_code_file(path):
    return os.path.splitext((path or "").rstrip("/:"))[1].lower() in CODE_EXT


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
    """Replace every secret-pattern match (and its value group) with [REDACTED], for logs.
    Only the first REDACT_MAX characters are kept, because a log line needs no more.
    A gate that logs a long command must answer before the hook timeout: a timed-out hook does not block (R-017)."""
    if len(text) > REDACT_MAX:
        # The cut can split a secret, and half a secret matches no pattern: drop the last word.
        # shortcut: a quoted value with spaces that the cut splits stays in clear text, handle it when a log shows one.
        text = text[:REDACT_MAX].rsplit(None, 1)[0]
    for _name, rx in SECRET_PATTERNS:
        text = rx.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED]") if rx.groups and m.group(1)
                      else "[REDACTED]", text)
    return REDACT_ASSIGN.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)


REDACT_MAX = 2000
# Looser than the scan patterns: any NAME=value in a command line (env prefix, export, --token=...).
REDACT_ASSIGN = re.compile(r"(?i)(" + NAME_TAIL + r")(\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)")


def append_jsonl(rel, row):
    log_line(rel, json.dumps(row, ensure_ascii=False))


def log_wall(wall, reason, repo=""):
    """One line per wall fire (a gate deny, a stop block, an ai-adopt or agent-audit refusal) in walls.jsonl.
    ai-doctor shows 7 days per wall (ticket 17). Never raises."""
    import socket
    try:
        host = socket.gethostname().split(".")[0]
    except OSError:
        host = "?"
    append_jsonl("walls.jsonl", {"ts": iso_now(), "host": host, "repo": repo or "", "wall": wall,
                                 "reason": redact(one_line(reason))[:160]})


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
