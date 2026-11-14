#!/usr/bin/env python3
"""stop-check: run the project's check-fast before an agent says "done" (Claude Stop, Codex Stop).

Usage (hooks.json / codex-hooks.json):
  python3 stop-check.py --agent claude|codex SessionStart   < hook JSON   (records the tree baseline)
  python3 stop-check.py --agent claude|codex Stop           < hook JSON   (runs the check when files changed)

A separate script, not the router: the router never blocks a session; this hook must (owner plan, Tier 1 T2).
Python stdlib only (/usr/bin/python3 3.9 too). An internal error is logged and the hook stays silent: it is a
quality check, not a security gate (the gates are in the router).

Stop, in order:
  1. stop_hook_active (the agent is already continuing because a Stop hook blocked): silent. No loops.
  2. Only in an adopted repo (.ai/enabled), tier mvp or long, without a `no-stop-check` line.
  3. An oh-my-claudecode persistent mode (ralph, autopilot, ultragoal, team ...) is active for this session:
     silent. That mode owns the continuation; this check runs at the first stop after the mode ends.
     So the two hooks never both block one stop.
  4. The tree fingerprint (HEAD, git status, git diff, untracked file sizes and times) equals the session
     baseline or the last green tree: silent (nothing changed in this session, or already checked).
  5. The same tree failed twice already: no third block (Claude: one short note to the owner).
  6. `make check-fast` (or `just check-fast`), 55 s timeout. A timeout passes with a note.
     Exit 0 but 0 tests seen (minimum-input floor) is a failure. Long tier: then `ai-ratchet --only tests,skips`
     (test count may not drop, skip count may not grow).
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
TAIL_LINES = 40
OMC_MODES = ("ralph", "ultragoal", "autopilot", "ultrapilot", "pipeline", "team", "omc-teams", "ultrawork",
             "ultraqa")
OMC_STALE_S = 2 * 3600          # oh-my-claudecode ignores a mode state older than this (persistent-mode.mjs)
STATE_MAX_AGE = 7 * 86400
UNTRACKED_CAP = 2000
COUNT_RX = re.compile(r"\b(\d+) (?:tests? )?(?:passed|passing)\b|\bRan (\d+) tests?\b|^ok\s+\S+", re.M)
ZERO_RX = re.compile(r"no tests ran|collected 0 items|no test files|running 0 tests|no tests found|ran 0 tests",
                     re.I)


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
    if payload.get("stop_hook_active"):
        return None
    root = active_root(payload)
    if not root:
        return None
    session = str(payload.get("session_id") or "")
    if omc_mode_active(root, session):
        return None
    st = State(payload, root)
    fp = fingerprint(root)
    if not st.data.get("baseline"):         # no SessionStart seen (hook added mid-session): start from here
        st.data.update(baseline=fp, baseline_head=head(root), started=iso_now())
        st.save()
        return None
    if fp == st.data["baseline"] or fp in (st.data.get("last_ok") or []):
        return None
    tries = st.data.setdefault("tries", {})
    if tries.get(fp, 0) >= MAX_TRIES:
        told = st.data.setdefault("told", [])
        if fp in told:
            return None
        told.append(fp)
        st.save()
        return note(agent, "check-fast still fails after %d blocks on the same files; not blocking again. "
                           "Owner: run it yourself and decide." % MAX_TRIES)
    cmd = check_command(root)
    if not cmd:
        return None
    t0 = time.time()
    try:
        res = subprocess.run(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        st.data["last_ok"] = [fp, fingerprint(root)]
        st.save()
        return note(agent, "%s ran over %d s and was not judged (counted as a pass). Keep check-fast under 60 s."
                    % (" ".join(cmd), CHECK_TIMEOUT))
    except OSError as exc:
        return note(agent, "%s could not start: %s" % (" ".join(cmd), exc))
    output = res.stdout.decode("utf-8", "replace")
    problem = None
    if res.returncode != 0:
        problem = "%s failed (exit %d)" % (" ".join(cmd), res.returncode)
    elif tests_seen(output) == 0:
        problem = "%s passed but ran 0 tests (minimum-input floor: a check that checks nothing fails)" % " ".join(cmd)
    elif project_tier(root) == "long":
        left = max(5.0, CHECK_TIMEOUT - (time.time() - t0))
        ok, msg = ratchet(root, left)
        if not ok:
            problem, output = "ai-ratchet (tests and skips) failed", msg
    if problem is None:
        st.data["last_ok"] = [fp, fingerprint(root)]       # the check may touch files (caches, formatters)
        msg = ledger_stop_note(root, st, payload) if agent == "claude" and project_tier(root) == "long" else ""
        st.save()
        return note(agent, msg) if msg else None
    tries[fp] = tries.get(fp, 0) + 1
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

def active_root(payload):
    """The repo root when the stop check is on there: adopted, tier mvp or long, no `no-stop-check`."""
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


def check_command(root):
    for name, tool in (("Makefile", "make"), ("GNUmakefile", "make"), ("justfile", "just"), ("Justfile", "just")):
        text = read_text(os.path.join(root, name))
        if text and re.search(r"^@?check-fast\s*:(?!=)", text, re.M):
            return [tool, "check-fast"]
    return None


def git(root, *args):
    try:
        res = subprocess.run(["git", "--no-optional-locks", "-C", root] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return b""
    return res.stdout if res.returncode == 0 else b""


def head(root):
    return git(root, "rev-parse", "-q", "--verify", "HEAD").decode().strip()


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
    return 0 if ZERO_RX.search(output) else None


def ratchet(root, timeout):
    """ai-ratchet --only tests,skips --no-write (a missing baseline passes). (ok, message)."""
    exe = os.path.join(ai_home() or "/nonexistent", "ai", "bin", "ai-ratchet")
    if not os.path.isfile(exe):
        return True, ""
    try:
        res = subprocess.run([sys.executable, exe, "--dir", root, "--only", "tests,skips", "--no-write"],
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
