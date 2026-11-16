#!/usr/bin/env python3
"""stop-check: run the project's check-fast before an agent says "done" (Claude Stop, Codex Stop).

Usage (hooks.json / codex-hooks.json):
  python3 stop-check.py --agent claude|codex SessionStart   < hook JSON   (records the tree baseline)
  python3 stop-check.py --agent claude|codex Stop           < hook JSON   (runs the check when files changed)

A separate script, not the router: the router must stay fast and blocks a Stop only for a missing must-use
skill (strength stop); this hook runs the project's check, up to 55 s (owner plan, Tier 1 T2).
Python stdlib only (/usr/bin/python3 3.9 too). An internal error is logged and the hook stays silent: it is a
quality check, not a security gate (the gates are in the router).

Stop, in order:
  1. Only in an adopted repo (.ai/enabled), tier mvp or long, without a `no-stop-check` line.
  2. An oh-my-claudecode persistent mode (ralph, autopilot, ultragoal, team ...) is active for this session:
     silent. That mode owns the continuation; this check runs at the first stop after the mode ends.
     OMC itself never blocks when stop_hook_active is set, so one stop never gets a block from both.
  3. The tree fingerprint (HEAD, git status, git diff, untracked file sizes and times) equals the session
     baseline or the last green tree: silent. No SessionStart baseline (hook timed out, added mid-session):
     the baseline is the clean HEAD, so any uncommitted change counts.
  4. Loop limits: at most 2 blocks on the same tree, and at most 4 blocks in one stop chain (stops while
     stop_hook_active is set; a new user turn starts a new chain). Then one note to the owner (Claude).
     stop_hook_active does not skip the check: the continuation is where the agent's fix gets checked.
  5. The check-fast recipe changed since the session start: a block (the owner decides on a weaker check).
  6. `make check-fast` (or `just check-fast`) in its own process group, 55 s budget in all (a timeout kills
     the group and passes with a note). Exit 0 with 0 tests seen, or only skipped tests, fails
     (minimum-input floor). Long tier: then `ai-ratchet --only tests,skips --base <session start commit>`.
  7. Failure: JSON {"decision": "block", "reason": <command, exit code, last 40 lines>}. Success: no output.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from hooklib import (ai_home, iso_now, ledger_hits, ledger_note, log_line, project_root, project_tier,  # noqa: E402
                     read_text, state_path)

CHECK_TIMEOUT = float(os.environ.get("AI_STOP_CHECK_TIMEOUT") or 55)   # env: tests only (the hook's own env)
MAX_TRIES = 2
MAX_CHAIN = 4                   # blocks in one chain of continuation stops
TAIL_LINES = 40
OMC_MODES = ("ralph", "ultragoal", "autopilot", "ultrapilot", "pipeline", "team", "omc-teams", "ultrawork",
             "ultraqa")
OMC_STALE_S = 2 * 3600          # oh-my-claudecode ignores a mode state older than this (persistent-mode.mjs)
STATE_MAX_AGE = 7 * 86400
UNTRACKED_CAP = 2000
COUNT_RX = re.compile(r"\b(\d+) (?:tests? )?(?:passed|passing)\b|\bRan (\d+) tests?\b|^ok\s+\S+", re.M)
ZERO_RX = re.compile(r"no tests ran|collected 0 items|no test files|running 0 tests|no tests found|ran 0 tests",
                     re.I)
SKIPPED_RX = re.compile(r"\b\d+ (?:tests? )?skipped\b", re.I)
TARGET_RX = r"^@?check-fast(?:[ \t][^\n]*?)?:(?!=)"     # make: check-fast:; just: check-fast arg="1":


def main(argv):
    agent, event = parse_args(argv)
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    event = event or payload.get("hook_event_name", "")
    try:
        if event == "SessionStart":
            on_session_start(payload)
        elif event == "Stop":
            out = on_stop(payload, agent)
            if out:
                sys.stdout.write(json.dumps(out) + "\n")
    except Exception as exc:      # a broken check must never trap the agent in a loop
        log_line("router-errors.log", "%s stop-check %s %s: %s" % (iso_now(), event, type(exc).__name__, exc))
    return 0


def parse_args(argv):
    agent, event, args = "claude", "", list(argv)
    while args:
        a = args.pop(0)
        if a == "--agent" and args:
            agent = args.pop(0)
        elif a.startswith("--agent="):
            agent = a.split("=", 1)[1]
        else:
            event = a
    return agent, event


# ---------------------------------------------------------------- events

def on_session_start(payload):
    root = active_root(payload)
    if not root:
        return
    prune_states()
    st = State(payload, root)
    if not st.data.get("baseline"):         # resume / compact keep the first baseline of the session
        st.data.update(baseline=fingerprint(root), baseline_head=head(root), started=iso_now())
        st.save()


def on_stop(payload, agent):
    t0 = time.time()
    root = active_root(payload)
    if not root:
        return None
    session = str(payload.get("session_id") or "")
    if omc_mode_active(root, session):
        return None
    st = State(payload, root)
    continuing = bool(payload.get("stop_hook_active"))
    if not continuing:
        st.data["chain"], st.data["chain_told"] = 0, False   # a new user turn: a new chain of continuation stops
    fp = fingerprint(root)
    if not st.data.get("baseline"):         # no SessionStart baseline: the clean HEAD is the baseline
        h = head(root)
        st.data.update(baseline=clean_fingerprint(h), baseline_head=h, started=iso_now())
    if fp == st.data["baseline"] or fp in (st.data.get("last_ok") or []):
        st.save()
        return None
    tries = st.data.setdefault("tries", {})
    if tries.get(fp, 0) >= MAX_TRIES or st.data.get("chain", 0) >= MAX_CHAIN:
        told = st.data.setdefault("told", [])
        if fp in told or st.data.get("chain_told"):
            st.save()
            return None
        told.append(fp)
        st.data["chain_told"] = st.data.get("chain", 0) >= MAX_CHAIN
        st.save()
        return note(agent, "check-fast still fails after %d blocks; not blocking again. Owner: run it yourself "
                           "and decide." % max(tries.get(fp, 0), st.data.get("chain", 0)))
    cmd = check_command(root)
    if not cmd:
        st.save()
        return None
    problem, output = None, ""
    changed = recipe_changed(root, st.data.get("baseline_head"))
    if changed:
        problem, output = ("the check-fast recipe in %s changed in this session: a weaker check is the owner's "
                           "call. Put it back, or stop and tell the owner why it must change" % changed), ""
    else:
        rc, output, timed_out = run_group(cmd, root, CHECK_TIMEOUT - (time.time() - t0))
        if timed_out:
            st.data["last_ok"] = [fp, fingerprint(root)]
            st.save()
            return note(agent, "%s ran over %d s and was not judged (counted as a pass). Keep check-fast under 60 s."
                        % (" ".join(cmd), CHECK_TIMEOUT))
        if rc is None:
            st.save()
            return note(agent, "%s could not start: %s" % (" ".join(cmd), output))
        if rc != 0:
            problem = "%s failed (exit %d)" % (" ".join(cmd), rc)
        elif tests_seen(output) == 0:
            problem = ("%s passed but ran 0 tests, or only skipped ones (minimum-input floor: a check that checks "
                       "nothing fails)" % " ".join(cmd))
        elif project_tier(root) == "long":
            left = CHECK_TIMEOUT - (time.time() - t0)
            if left >= 3:                   # the hook timeout is 60 s: never start what cannot finish
                ok, msg = ratchet(root, left, st.data.get("baseline_head"))
                if not ok:
                    problem, output = "ai-ratchet (tests and skips) failed", msg
    if problem is None:
        st.data["last_ok"] = [fp, fingerprint(root)]       # the check may touch files (caches, formatters)
        msg = ledger_stop_note(root, st, payload) if agent == "claude" and project_tier(root) == "long" else ""
        st.save()
        return note(agent, msg) if msg else None
    tries[fp] = tries.get(fp, 0) + 1
    st.data["chain"] = st.data.get("chain", 0) + 1
    st.save()
    tail = "\n".join(output.rstrip().splitlines()[-TAIL_LINES:])
    reason = ("[ai stop-check] %s. Last %d lines:\n%s\n\nFix the cause, then finish. Do not delete, skip or weaken a "
              "test to get green. If it cannot pass, say why and stop (block %d of %d for these files)."
              % (problem, TAIL_LINES, tail, tries[fp], MAX_TRIES))
    return {"decision": "block", "reason": reason}


def ledger_stop_note(root, st, payload):
    """Files changed in this session (Bash edits too: sed -i, formatters) that lie in a regression-ledger area
    the edit nudge did not name yet: one line for the owner."""
    names = set()
    for e in git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0"):
        if len(e) > 3 and e[2:3] == b" ":
            names.add(e[3:].decode("utf-8", "replace"))
    if st.data.get("baseline_head"):
        names |= set(git(root, "diff", "--name-only", st.data["baseline_head"], "HEAD").decode().splitlines())
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or "nosession"))[:120]
    try:
        router = json.loads(read_text(state_path(os.path.join("sessions", sid + ".json"))) or "{}")
    except ValueError:
        router = {}
    seen = set(router.get("ledger_areas") or []) | set(st.data.get("ledger_told") or [])
    hits = [h for rel in sorted(names) for h in ledger_hits(root, rel) if h[1] not in seen]
    if not hits:
        return ""
    st.data.setdefault("ledger_told", []).extend(sorted({h[1] for h in hits}))
    return "Files changed in a regression area this session (Bash edits too). " + ledger_note(hits)


def note(agent, text):
    """A message for the owner that does not block. Codex: Stop output must be empty or a decision."""
    if agent == "claude":
        return {"systemMessage": "[ai stop-check] " + text}
    return None


# ---------------------------------------------------------------- project state

def profile_guards():
    """False on a profile with PROFILE_GUARDS=0 (dev-mac): no Stop check there. Any error: the check stays on."""
    try:
        sys.path.insert(0, os.path.join(ai_home(), "ai", "lib"))
        import ai_profile
        name, _from = ai_profile.resolve()
        return ai_profile.load(name).get("PROFILE_GUARDS", "1") != "0"
    except Exception:
        return True


def active_root(payload):
    """The repo root when the stop check is on there: adopted, tier mvp or long, no `no-stop-check`."""
    if not profile_guards():
        return None          # profile dev-mac: no Stop check (owner 2026-11-15)
    root = project_root(str(payload.get("cwd") or os.getcwd()))
    if not root:
        return None
    text = read_text(os.path.join(root, ".ai", "enabled"))
    if text is None:
        return None
    ids = {ln.split("#", 1)[0].strip().lower() for ln in text.splitlines()}
    if "no-stop-check" in ids or project_tier(root) == "try":
        return None
    return root


RECIPE_FILES = (("Makefile", "make"), ("GNUmakefile", "make"), ("justfile", "just"), ("Justfile", "just"))


def check_command(root):
    for name, tool in RECIPE_FILES:
        text = read_text(os.path.join(root, name))
        if text and re.search(TARGET_RX, text, re.M):
            return [tool, "check-fast"]
    return None


def recipe(text):
    """The check-fast target line and its indented recipe lines, or ''."""
    m = re.search(TARGET_RX, text or "", re.M)
    if not m:
        return ""
    lines = [text[m.start():].split("\n", 1)[0]]
    for ln in text[m.end():].split("\n")[1:]:
        if ln[:1] in ("\t", " ") and ln.strip():
            lines.append(ln.rstrip())
        elif ln.strip():
            break
    return "\n".join(lines)


def recipe_changed(root, base):
    """The file name when the check-fast recipe differs from the one at the session start commit, else ''."""
    if not base:
        return ""
    for name, _tool in RECIPE_FILES:
        now = read_text(os.path.join(root, name))
        if now is None:
            continue
        old = git(root, "show", "%s:%s" % (base, name)).decode("utf-8", "replace")
        if recipe(now) and old and recipe(now) != recipe(old):
            return name
    return ""


def run_group(cmd, root, timeout):
    """(exit code or None, output, timed out). The command runs in its own process group: a timeout kills the
    whole group (make's children too), not only make."""
    import signal
    try:
        proc = subprocess.Popen(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as exc:
        return None, str(exc), False
    try:
        out, _ = proc.communicate(timeout=max(1.0, timeout))
        return proc.returncode, out.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.communicate()
        return None, "", True


def git(root, *args):
    try:
        res = subprocess.run(["git", "--no-optional-locks", "-C", root] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return b""
    return res.stdout if res.returncode == 0 else b""


def head(root):
    return git(root, "rev-parse", "-q", "--verify", "HEAD").decode().strip()


def clean_fingerprint(h):
    """The fingerprint of a clean tree at commit h (what fingerprint() gives with nothing changed)."""
    x = hashlib.sha256()
    x.update(h.encode() or b"no-head")
    return x.hexdigest()


def fingerprint(root):
    """HEAD + status + diff against HEAD + size and mtime of untracked files: changes when anything changes."""
    h = hashlib.sha256()
    h.update(head(root).encode() or b"no-head")
    status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    h.update(status)
    h.update(git(root, "diff", "HEAD", "--no-color", "--no-ext-diff", "--binary") if head(root)
             else git(root, "diff", "--cached", "--binary") + git(root, "diff", "--binary"))
    entries = [e for e in status.split(b"\0") if e.startswith(b"?? ")][:UNTRACKED_CAP]
    for e in entries:
        rel = e[3:].decode("utf-8", "replace")
        try:
            s = os.stat(os.path.join(root, rel))
            h.update(("%s %d %d\n" % (rel, s.st_size, s.st_mtime_ns)).encode())
        except OSError:
            continue
    return h.hexdigest()


def tests_seen(output):
    """Tests the output reports as run: a number, 0 (a runner said it ran none), or None (cannot tell)."""
    total = 0
    for m in COUNT_RX.finditer(output):
        total += int(m.group(1) or m.group(2) or 1)
    if total:
        return total
    return 0 if ZERO_RX.search(output) or SKIPPED_RX.search(output) else None


def ratchet(root, timeout, base=None):
    """ai-ratchet --only tests,skips --no-write against the baseline committed at the session start commit (an
    edit of .ai/ratchet.json in this session does not count). A missing baseline passes. (ok, message)."""
    exe = os.path.join(ai_home() or "/nonexistent", "ai", "bin", "ai-ratchet")
    if not os.path.isfile(exe):
        return True, ""
    extra = ["--base", base] if base else []
    try:
        res = subprocess.run([sys.executable, exe, "--dir", root, "--only", "tests,skips", "--no-write"] + extra,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return True, ""
    return res.returncode == 0, res.stdout.decode("utf-8", "replace")


def omc_mode_active(root, session):
    """True when an oh-my-claudecode persistent mode will block this stop itself (same files it reads)."""
    bases = [os.path.join(root, ".omc", "state")]
    custom = os.environ.get("OMC_STATE_DIR")
    if custom and os.path.isdir(custom):
        bases += [os.path.join(custom, d, "state") for d in sorted(os.listdir(custom))[:200]]
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session)
    for base in bases:
        for mode in OMC_MODES:
            paths = [os.path.join(base, "%s-state.json" % mode)]
            if safe:
                paths.insert(0, os.path.join(base, "sessions", safe, "%s-state.json" % mode))
            for i, p in enumerate(paths):
                try:
                    data = json.loads(read_text(p) or "null")
                except ValueError:
                    continue
                if not isinstance(data, dict) or not data.get("active") or omc_stale(data):
                    continue
                owner = data.get("session_id")
                if owner == session or (owner is None and p != paths[-1]):
                    return True
    return False


def omc_stale(data):
    from datetime import datetime
    newest = 0.0
    for key in ("last_checked_at", "updated_at", "started_at"):
        v = data.get(key)
        if isinstance(v, str) and v:
            try:
                newest = max(newest, datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
            except ValueError:
                continue
    return not newest or time.time() - newest > OMC_STALE_S


class State(object):
    """<state>/stop/<session>-<repo hash>.json: baseline, last_ok trees, tries per tree."""

    def __init__(self, payload, root):
        sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or "nosession"))[:100]
        key = hashlib.sha1(os.path.realpath(root).encode()).hexdigest()[:10]
        self.path = state_path(os.path.join("stop", "%s-%s.json" % (sid, key)))
        try:
            self.data = json.loads(read_text(self.path) or "{}")
        except ValueError:
            self.data = {}
        if not isinstance(self.data, dict):
            self.data = {}

    def save(self):
        d = os.path.dirname(self.path)
        os.makedirs(d, mode=0o700, exist_ok=True)
        tmp = "%s.%d.tmp" % (self.path, os.getpid())
        with open(tmp, "w") as fh:
            json.dump(self.data, fh)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)


def prune_states():
    d = state_path("stop")
    if not os.path.isdir(d):
        return
    now = time.time()
    for f in os.listdir(d):
        p = os.path.join(d, f)
        try:
            if now - os.path.getmtime(p) > STATE_MAX_AGE:
                os.unlink(p)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
