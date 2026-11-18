# 16: ai-adopt edge cases found in the fixture experiment

**What to build:** each case below ends in a clean and correct project. All were seen on 2026-11-18 in fixture
repos (report `docs/reports/setup-deep-audit-2026-11-18.md`, section 12).

**Blocked by:** 15

**Status:** ready-for-agent

- [ ] husky repo: `graphify hook install` puts no file into the shared `.husky/` folder. Today 4 untracked hook
  files of 13 to 16 KB appear there.
- [ ] Monorepo: the adopt writes a check target, or the Done text does not ask for `check-fast`. Today
  `make check-fast` exits 2 and the Done text asks for it.
- [ ] A project with a hand-written `## Map` gets one Map section, not two headings.
- [ ] A project folder `.claude/skills/<name>` that has the name of a shared skill: Claude and Codex load the
  same skill. Today Claude keeps the project folder and Codex gets the shared link.
- [ ] On a feature branch the adopt commit does not mix with the feature. It stops, or it uses its own branch.
- [ ] Uncommitted work stays on the branch where the owner had it. Today the checkout moves to `ai-adopt` and
  carries the work along.
- [ ] After the adopt, `git status` shows no `__pycache__` from the test run.
- [ ] The Map does not keep a check time that was measured on a loaded machine (one run wrote "measured 45 s";
  the same repo needs 6 s).
- [ ] Each adopt adds one project entry to `~/.serena/serena_config.yml`. The entries of removed folders are
  cleaned by `ai-doctor`, or the adopt writes none. The experiment left 8 entries for temp folders.
