#!/usr/bin/env python3
"""Tests for ai-evidence-prune (spec docs/specs/verify-evidence-in-git.md): it removes committed verify run folders
older than the cut (7 days by default) and keeps the newest run of each feature. It refuses main and master.
A temp git repo; nothing is written outside the temp dir.

Run: python3 ai/tests/test_evidence.py   (bash ai/tests/run.sh runs it too)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

TESTS = os.path.dirname(os.path.realpath(__file__))
PRUNE = os.path.join(os.path.dirname(TESTS), "bin", "ai-evidence-prune")
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
DAY = 86400


def main():
    work = tempfile.mkdtemp(prefix="ai-evidence-tests-")
    fails = []
    try:
        for test in (t_prune_old_keeps_newest_per_feature, t_prune_refuses_main, t_prune_dry_run):
            d = os.path.join(work, test.__name__)
            os.makedirs(d)
            try:
                test(d)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                fails.append(test.__name__)
                print("FAIL %s: %s" % (test.__name__, exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d evidence tests failed" % len(fails))
    return 1 if fails else 0


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), env=ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)


def run_folder(repo, name, ago_days, finished=True):
    d = os.path.join(repo, ".verify", "evidence", name)
    os.makedirs(d)
    rows = ["commit: " + "a" * 40, "doctor: PASS", "db_writes: no"]
    if finished:
        rows.append("finished: " + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_days * DAY)))
    with open(os.path.join(d, "run.log"), "w") as fh:
        fh.write("\n".join(rows) + "\n")


def repo_with_runs(work, branch="chore-prune"):
    repo = os.path.join(work, "r")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    run_folder(repo, "feat-pay_checkout_01-11-2026_10-00-00", 18)
    run_folder(repo, "feat-pay_checkout_05-11-2026_10-00-00", 14)
    run_folder(repo, "fix-total_checkout_17-11-2026_10-00-00", 2)     # same feature, other branch
    run_folder(repo, "feat-cart_02-11-2026_10-00-00", 17)             # no feature part: the branch is the key
    run_folder(repo, "20261103T100000Z-feat-cart", 16)                # the old name form still parses
    run_folder(repo, "feat-login_login_04-11-2026_10-00-00", 15, finished=False)   # the name time counts
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "evidence")
    if branch:
        git(repo, "switch", "-q", "-c", branch)
    return repo


def tracked(repo):
    out = git(repo, "ls-files", ".verify/evidence").stdout.split()
    return sorted({p.split("/")[2] for p in out})


def t_prune_old_keeps_newest_per_feature(work):
    repo = repo_with_runs(work)
    res = subprocess.run([sys.executable, PRUNE, "--dir", repo], env=ENV, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, universal_newlines=True)
    assert res.returncode == 0, res.stdout
    # checkout: 2 old ones go, the 2-day run stays. feat-cart: both old, the newest stays. login: one run, it stays.
    assert tracked(repo) == ["20261103T100000Z-feat-cart", "feat-login_login_04-11-2026_10-00-00",
                             "fix-total_checkout_17-11-2026_10-00-00"], tracked(repo)
    assert "feat-pay_checkout_01-11-2026_10-00-00" in res.stdout and "3 run folders" in res.stdout, res.stdout


def t_prune_refuses_main(work):
    repo = repo_with_runs(work, branch=None)
    res = subprocess.run([sys.executable, PRUNE, "--dir", repo], env=ENV, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, universal_newlines=True)
    assert res.returncode != 0 and "main" in res.stdout, res.stdout
    assert len(tracked(repo)) == 6


def t_prune_dry_run(work):
    repo = repo_with_runs(work)
    res = subprocess.run([sys.executable, PRUNE, "--dir", repo, "--dry-run", "--days", "15"], env=ENV,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    assert res.returncode == 0 and "would remove" in res.stdout, res.stdout
    assert len(tracked(repo)) == 6, "dry run changes nothing"


if __name__ == "__main__":
    sys.exit(main())
