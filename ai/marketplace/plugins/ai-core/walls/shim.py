#!/usr/bin/env python3
"""ai-core walls: the git and gh wrapper (rules-that-hold 25).

Usage (from the launchers in walls/bin):  python3 shim.py git|gh <args>

The session start puts walls/bin first on PATH for each agent Bash command. The wrapper gets the real argv after
the shell parsed everything, so nesting (bash -c, a here-document, eval, xargs, a Python subprocess) cannot hide
a call from it. Outside agent mode (AI_AGENT is not 1) it runs the real tool at once.

In agent mode it refuses a hook skip (-c core.hooksPath, alias.*, hook.*, GIT_CONFIG_* entries, --no-verify and its
abbreviations, commit -n, a core.hooksPath outside the repository) and a shell alias. A command that can change
something (git commit, push, merge; a gh write) then goes through the gates of the PreToolUse hook (router.py
on_pre_tool), so no gate logic lives here. A read does not load the gates: it stays fast.
"""
import os
import sys

WALLS = os.path.dirname(os.path.realpath(__file__))
HOOKS = os.path.join(os.path.dirname(WALLS), "hooks")


def main(argv):
    tool, args = argv[0], argv[1:]
    real = real_tool(tool)
    if not real:
        sys.stderr.write("[ai wall] no real %s found on PATH after %s\n" % (tool, os.path.join(WALLS, "bin")))
        return 127
    if os.environ.get("AI_AGENT") == "1":
        problem = check_git(real, args) if tool == "git" else check_gh(args)
        if problem:
            sys.stderr.write("[ai wall] %s\n" % problem)
            return 1
    os.execv(real, [real] + args)


def check_git(real, args):
    problem = env_config_skip()
    if problem:
        return problem
    globals_, cwd, sub, rest, problem = split_globals(args)
    if problem or sub is None:
        return problem
    sub, rest, problem = resolve_alias(real, globals_, cwd, sub, rest)
    if problem:
        return problem
    problem = no_verify_skip(sub, rest) or remote_ref_skip(sub, rest) or config_skip(real, globals_, cwd, sub, rest)
    if problem:
        return problem
    if sub not in READS:
        problem = hooks_path_skip(real, globals_, cwd)
        if problem:
            return problem
    if sub in GATED:
        return ask_gates(cwd, ["git", sub] + rest, ["git"] + args)
    return None


def check_gh(args):
    if gh_read(args):
        return None
    return ask_gates(os.getcwd(), ["gh"] + args, ["gh"] + args)


# ---------------------------------------------------------------- the real tool

def real_tool(tool):
    """The next `tool` on PATH that is not a walls launcher. A second plugin copy on PATH is skipped too, so the
    wrapper never calls itself."""
    own = os.path.realpath(os.path.join(WALLS, "bin"))
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or os.path.realpath(d) == own or os.path.isfile(os.path.join(d, "..", "shim.py")):
            continue
        path = os.path.join(d, tool)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def run_real(real, globals_, cwd, args):
    """(exit code, stdout) of a real git call that only reads."""
    import subprocess
    try:
        res = subprocess.run([real] + globals_ + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return 1, ""
    return res.returncode, res.stdout.decode("utf-8", "replace").strip()


# ---------------------------------------------------------------- git global options, config entries and aliases

GLOBAL_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path",
                "--super-prefix", "--attr-source", "--list-cmds")
SKIP_KEY_MSG = ("%s sets %s, which can skip the git hooks or hide the real command. Agents never do that: run the "
                "plain git command, and fix what the hook reports.")


def split_globals(args):
    """(global options, cwd, subcommand, its args, problem) of a git argv."""
    out, cwd, i = [], os.getcwd(), 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        name, eq, val = a.partition("=")
        if a in GLOBAL_VALUE and i + 1 < len(args):
            name, val, step = a, args[i + 1], 2
        else:
            step = 1
        if name == "-C" and step == 2:
            cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(val)))
        elif name in ("-c", "--config-env") and (step == 2 or eq) and skip_key(val.partition("=")[0]):
            return out, cwd, None, [], SKIP_KEY_MSG % ("git " + name, val.partition("=")[0])
        if name != "-C":
            out.extend(args[i:i + step])
        i += step
    if i >= len(args):
        return out, cwd, None, [], None
    return out, cwd, args[i], args[i + 1:], None


def skip_key(key):
    key = key.lower()
    return key == "core.hookspath" or key.startswith("alias.") or key.startswith("hook.")


def env_config_skip():
    """GIT_CONFIG_COUNT / GIT_CONFIG_KEY_<n> and GIT_CONFIG_PARAMETERS (the -c of a parent git) in the environment."""
    import re
    for name, value in os.environ.items():
        if re.match(r"^GIT_CONFIG_KEY_\d+$", name) and skip_key(value.strip()):
            return SKIP_KEY_MSG % ("the environment entry " + name, value.strip())
    params = os.environ.get("GIT_CONFIG_PARAMETERS", "").lower()
    m = re.search(r"'(core\.hookspath|alias\.[^'=]*|hook\.[^'=]*)'", params)
    if m:
        return SKIP_KEY_MSG % ("the environment entry GIT_CONFIG_PARAMETERS", m.group(1))
    return None


def resolve_alias(real, globals_, cwd, sub, rest):
    """(subcommand, args, problem) after config aliases. An alias never hides a git command, so only an unknown
    name costs a config read."""
    import shlex
    seen = set()
    while sub not in BUILTINS and sub not in seen and len(seen) < 10:
        seen.add(sub)
        code, value = run_real(real, globals_, cwd, ["config", "--get", "alias." + sub])
        if code != 0 or not value:
            break
        if value.startswith("!"):
            return sub, rest, ("git %s is a shell alias (%s). Agents do not run shell aliases: run the commands it "
                               "holds one by one." % (sub, value))
        try:
            words = shlex.split(value)
        except ValueError:
            return sub, rest, "git %s is an alias that does not parse: %s" % (sub, value)
        if not words:
            break
        sub, rest = words[0], words[1:] + rest
    return sub, rest, None


# ---------------------------------------------------------------- --no-verify and commit -n

NO_VERIFY_SUBS = {"commit", "merge", "push", "am", "rebase", "cherry-pick", "pull"}
# Options that take the next word as their value, so a value such as -m "-n is a flag" is not read as a flag.
SHORT_VALUE = {"commit": "mFCctSu", "merge": "msX", "pull": "sX", "push": "o", "rebase": "sXx", "cherry-pick": "mX"}
OPTIONAL_ATTACHED = "Su"        # commit -S<key>, -u<mode>: the value is attached or absent
LONG_VALUE = {"--message", "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash", "--author",
              "--date", "--template", "--cleanup", "--trailer", "--pathspec-from-file", "--strategy",
              "--strategy-option", "--into-name", "--push-option", "--receive-pack", "--exec", "--repo", "--onto",
              "--mainline"}
NO_VERIFY_MSG = ("git %s %s skips the git hooks (pre-commit, commit-msg, pre-push). Agents never skip them: fix what "
                 "the hook reports, git add the files, and run the command again without it.")


def no_verify_skip(sub, rest):
    if sub not in NO_VERIFY_SUBS:
        return None
    letters = SHORT_VALUE.get(sub, "")
    i = 0
    while i < len(rest):
        a = rest[i]
        i += 1
        if a == "--":
            break
        if a.startswith("--"):
            name = a.partition("=")[0]
            if len(name) >= len("--no-v") and "--no-verify".startswith(name):
                return NO_VERIFY_MSG % (sub, a)
            if name in LONG_VALUE and "=" not in a:
                i += 1
            continue
        if not a.startswith("-") or a == "-":
            continue
        for j, ch in enumerate(a[1:]):
            if ch == "n" and sub == "commit":
                return NO_VERIFY_MSG % (sub, a)
            if ch in letters:
                if ch not in OPTIONAL_ATTACHED and j == len(a) - 2:
                    i += 1          # the value is the next word
                break               # the rest of the cluster is the value
    return None


# ---------------------------------------------------------------- remote-tracking refs

def remote_ref_skip(sub, rest):
    """git update-ref on refs/remotes/: a forged remote-tracking ref would make the hook take a move of a protected
    branch for a pull. fetch and push still update these refs."""
    if sub != "update-ref":
        return None
    if "--stdin" in rest:
        return ("git update-ref --stdin reads its refs from standard input, which the wrapper cannot see. Agents run "
                "git update-ref with the ref on the command line.")
    words, i = [], 0
    while i < len(rest):
        if rest[i] == "-m":
            i += 2
            continue
        if not rest[i].startswith("-") or rest[i] == "--":
            words.append(rest[i])
        i += 1
    words = [w for w in words if w != "--"]
    if words and words[0].startswith("refs/remotes/"):
        return ("git update-ref %s writes a remote-tracking ref by hand. Only git fetch and git push update it."
                % words[0])
    return None


# ---------------------------------------------------------------- core.hooksPath

def config_skip(real, globals_, cwd, sub, rest):
    """git config that sets core.hooksPath to a folder outside the repository (or /dev/null)."""
    if sub != "config":
        return None
    keys = [i for i, a in enumerate(rest) if a.lower() == "core.hookspath"]
    if not keys or keys[0] + 1 >= len(rest):
        return None
    value = rest[keys[0] + 1]
    if hooks_inside(real, globals_, cwd, value):
        return None
    return ("git config core.hooksPath %s points git away from this repository's hooks. Agents never move the hooks: "
            "keep core.hooksPath inside the repository." % value)


def hooks_path_skip(real, globals_, cwd):
    """The core.hooksPath that git will use (also from a config file edited by hand): /dev/null or a folder outside
    the repository is refused, unless it is the owner's global or system value."""
    code, out = run_real(real, globals_, cwd, ["config", "--show-scope", "--get", "core.hooksPath"])
    if code != 0 or not out:
        return None
    scope, _tab, value = out.partition("\t")
    if value != "/dev/null" and scope in ("global", "system"):
        return None
    if hooks_inside(real, globals_, cwd, value):
        return None
    return ("core.hooksPath is %s (%s config), so git would skip this repository's hooks. Remove it first: git config "
            "--%s --unset core.hooksPath" % (value, scope, scope if scope in ("local", "worktree") else "local"))


def hooks_inside(real, globals_, cwd, value):
    code, out = run_real(real, globals_, cwd, ["rev-parse", "--show-toplevel", "--git-common-dir"])
    lines = out.splitlines() if code == 0 else []
    if len(lines) < 2 or value.strip() in ("", "/dev/null"):
        return False
    top = os.path.realpath(lines[0])
    common = os.path.realpath(os.path.join(cwd, lines[1]))
    path = os.path.realpath(os.path.join(top, os.path.expanduser(value)))
    return any(path == d or path.startswith(d + os.sep) for d in (top, common))


# ---------------------------------------------------------------- the gates

ASK_MSG = ("The wrapper cannot ask the owner: run this command as a plain Bash command, not inside another command, "
           "so the owner can be asked.")


def ask_gates(cwd, words, raw):
    """The PreToolUse gates on one simple command (words). A deny is a refusal. An ask passes only with a fresh
    one-time pass that the PreToolUse hook recorded for the same command (raw argv) after it asked the owner.
    The no-verify gate is left out: it reads command text, and the argv check above is the exact form of it."""
    import shlex
    try:
        sys.path.insert(0, HOOKS)
        sys.dont_write_bytecode = True
        import router
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
                   "tool_input": {"command": shlex.join(words)},
                   "session_id": os.environ.get("AI_SESSION") or "nosession"}
        ctx = router.Ctx("claude", "PreToolUse", payload, "")
        routing = ctx.routing
        ctx._routing = dict(routing, rules=[r for r in routing.get("rules", []) if r.get("id") != "no-verify"])
        router.on_pre_tool(ctx)
        if ctx._state is not None and ctx._state.lock_fh:
            ctx._state.lock_fh.close()      # release the session lock; the wrapper saves no nudge state
        if ctx.decision == "ask":
            state = router.SessionState(ctx.session)
            try:
                if router.take_ask_pass(state, raw):
                    return None
            finally:
                state.save()
    except Exception as exc:
        return "the gates did not load (%s: %s), so this command was not run." % (type(exc).__name__, exc)
    if ctx.decision == "ask":
        return "\n".join(ctx.reasons + [ASK_MSG])
    if ctx.decision == "deny":
        return "\n".join(ctx.reasons)
    return None


# ---------------------------------------------------------------- command lists

# git: a read never moves a ref, so it needs no core.hooksPath check. config is judged by config_skip.
READS = {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "ls-remote", "cat-file", "blame",
         "grep", "describe", "shortlog", "for-each-ref", "show-ref", "rev-list", "merge-base", "help", "version",
         "var", "check-ignore", "check-attr", "name-rev", "whatchanged", "count-objects", "cherry", "range-diff",
         "show-branch", "diff-tree", "diff-files", "diff-index", "config", "--version", "--help"}
GATED = {"commit", "push", "merge"}
BUILTINS = READS | {
    "add", "am", "apply", "archive", "bisect", "branch", "bundle", "checkout", "cherry-pick", "clean", "clone",
    "commit", "commit-tree", "fetch", "format-patch", "fsck", "gc", "init", "maintenance", "merge", "mv", "notes",
    "pull", "push", "rebase", "reflog", "remote", "repack", "replace", "reset", "restore", "revert", "rm",
    "sparse-checkout", "stash", "submodule", "switch", "symbolic-ref", "tag", "update-index", "update-ref",
    "worktree", "hash-object", "mktree", "read-tree", "write-tree", "prune", "send-pack", "fetch-pack",
    "credential", "hook", "init-db", "verify-commit", "verify-tag"}

# gh: these read only. Each other gh call goes to the gates, which decide (gh-write, pr-rules, merge-approval).
GH_READS = {"pr": {"view", "list", "diff", "checks", "status"}, "issue": {"view", "list", "status"},
            "repo": {"view"}, "run": {"view", "list", "watch"}, "auth": {"status"},
            "search": None, "status": None, "version": None, "help": None, "--version": None, "--help": None}


def gh_read(args):
    if not args or args[0] not in GH_READS:
        return False
    subs = GH_READS[args[0]]
    return subs is None or (len(args) > 1 and args[1] in subs)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
