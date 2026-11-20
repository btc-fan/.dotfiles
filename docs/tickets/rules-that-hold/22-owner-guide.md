# 22: The owner guide: use it, extend it, try it on a project, recover

**What to build:** One short page, `docs/OWNER.md`, that the owner reads first. It says what runs where (the 6 layers in 10 lines). It shows how to add a rule, a skill, a plugin and a project rule. It shows how to try the branch on one machine and go back, with 2 commands each way. It says how to recover when a gate blocks everything, and how to read the numbers of `ai-doctor --numbers`. The stale statements of E2, section 6, are fixed or removed.

**Why:** `docs/GUIDE.md` has more than 700 lines, and parts of it are not true (E2, section 6). Examples: `README.md` says "Stop rules: diagnosing-bugs and tdd", but no row has `strength: stop`. `README.md` and `docs/GUIDE.md` name `sudo ai-gate-skip`, which `dev-mac` does not install. `docs/GUIDE.md` lists `PROFILE_AUDIT_GATE`, which nothing reads. The owner asked for a guide to use, extend and try the setup.

**Solution:**
- `docs/OWNER.md`, under 150 lines. `README.md` links to it in its first lines. `docs/GUIDE.md` keeps the long reference.
- What runs where: L1 GitHub, L2 repo, L3 session gates, L4 self-check, L5 the rules file, L6 skills and tools. One line each, plus what holds with no agent.
- Extend: the 4 recipes of `docs/EXTENDING.md` (ticket 21), as 1 line each with a link.
- Try the branch: `git -C "$AI_HOME" switch rules-that-hold && "$AI_HOME/install.sh"`. Go back: `git -C "$AI_HOME" switch ai && "$AI_HOME/install.sh"`.
- The page lists what the install changes on that machine: the rendered rules file, the plugin cache, settings keys, the hook files and the Codex hook trust.
- Recover: `claude --settings '{"disableAllHooks": true}'` for one Claude run. For Codex: `codex --disable hooks`. Then fix, and start a normal session.
- Read the numbers: one line per number of the README table, with its baseline and target.
- Fix or remove each statement of E2 section 6 (10 promises and 10 unexplained behaviours). The PR has a table: statement, file, fixed or removed.

**Rules kept:** No rule moves. The page names the home of each rule family once and links to it. It holds no rule text of its own, so it cannot drift from the homes.

**Edge cases:**
1. A second machine: the try and back commands run per machine. The page says that each machine needs its own switch, and that `ai-sync` on a pull renders again.
2. A project adopted with the old layer: switching back does not restore its old blocks. The page says to run `ai-adopt` in that project after the switch back.
3. A project adopted on the branch and opened after the switch back: the old router reads no block text, so it works. `ai-doctor --project` says that the layer is older or newer.
4. `disableAllHooks` also stops the safety gates. The page says to use it for one run only, and never in a project settings file.
5. The owner's token is admin on GitHub: the page says that an admin can still edit the ruleset (ticket 04).
6. A machine without `gh`, `gitleaks` or `uv`: the page lists which check then degrades and what `ai-doctor` prints.
7. A session that is open during the switch keeps its old context until its next start. The page says to start new sessions after the install.

**Owner steps:** None.

**Blocked by:** 15, 16, 20, 21

**Status:** ready-for-agent

**Size:** S

- [ ] `docs/OWNER.md` exists, has under 150 lines, and `README.md` links to it.
- [ ] The try and back commands run on a temp copy of the setup and print the files they changed (evidence).
- [ ] The recovery commands are in the page, and the Claude one is tested in a headless run.
- [ ] Each statement of E2 section 6 is fixed or removed (table in the PR).
- [ ] `ai-docs-check --md` passes on the new page (no em dash, sentences under 25 words, links work).

**Verify:**
- Unit: `ai-docs-check --md` in `make check`; `ai/tests/test_commands.py` gets `t_owner_page_links`.
- Drive: `$H drive install dev-mac` on the branch and again after the back command, with the 2 file lists as evidence; `$H drive merge installed`.
- Behaviour scenario: none for the page. The 12 gate scenarios of ticket 02 still pass after the stale-text fixes.

**Rollback:** Revert. The page is a doc; the stale-text fixes are each a small revert.
