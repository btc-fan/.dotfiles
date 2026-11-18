# 22: fixes from the review of PR #13

**What to build:** the security, spec and standards findings of the PR #13 review are fixed, each with a test that failed before the fix.

**Blocked by:** None (can start immediately)

**Status:** done

Security:
- [x] S1 merge-approval: a cd inside `( )`, a cd to a folder that is not a checkout, or a cd that may fail (not joined by `&&`) does not move the push check away from a session checkout on main. `cd <feature worktree> && git push` from a session on main stays allowed.
- [x] S2 pr-rules: `cd /nope; gh pr create ...` falls back to the session root; the verify-log, fix-PR test-file and size checks run.
- [x] S3 pr-rules: a body-file variable set twice, set to a value that is not a literal, or set as a command prefix makes the body file unread ("could not read the body file").
- [x] S4 secret-scan: `.env.example`, `*.sample` and config files are not fixture paths. There the generic rules stay on; only values with a clear fake marker pass. Test code keeps the ticket 11 behavior.
  Changed case: the ticket 11 `zps_` webhook value in `.env.example` has no clear fake marker, so it blocks now (case renamed "review S4: ..."). The owner confirms or names a marker for it.
- [x] S5 ai-adopt: the old `ai-adopt` branch is deleted only when its local and remote tips are the merged PR's `headRefOid`; else ai-adopt stops before any write.
- [x] S6 gitleaks: the sha256 of the pinned release archives is in `ai/pins.env`; the installer checks the archive against the pin.
- [x] S7 `app_code_state`: no symlink is followed; at most 1 MB of a file plus its size is read.
- [x] S8 merge OK: "merge 2 files" and "let's merge the docs" are not a merge OK; "merge 18", "merge #18", "merge the branches", "merge everything" still are.

Spec:
- [x] P1 hook 4: `gh pr edit N` and `gh pr ready N` (or a PR URL) judge the PR head from `gh pr view N --json headRefOid`; without it, the local HEAD, and the context says so.
- [x] P2 hook 4: a PR-gate deny caused by the verify proof is logged under the wall id `verify-pr`, also when the body has template problems.
- [x] P3 commit gate: a `db_writes: yes` log case is refused (test).

Standards:
- [x] T1 `ai/agents-md/50-pull-requests.md` says which parts block and which only warn; profile fixtures regenerated.
- [x] T2 `ai-precommit` honours the owner skip (`sudo ai-gate-skip verify-commit ...`), with a test.
- [x] T3 the verify-ai-setup tool reads run.log with `hooklib.verify_runs` (one parser).

Not in scope: hook 2's "first change" rule (the owner decides it separately).
