# 18: The server profile lives in its own branch

**What to build:** The units that only the `server` profile reaches move to their own branch. The core keeps one profile, `dev-mac`, and Linux picks it by default. The 3 server gates `no-destroy`, `no-sudo` and `audit-before-install` stay available as optional gates, because they denied 26 commands in the logs.

**Why:** No machine runs the `server` profile, but it holds about 4,580 code lines and about 6,190 test lines (E2, section 2). The main test suite tested it instead of the real profile (ticket 03). The Linux OS default still picks `server` when the profile file is missing (`profile.sh`, `ai_profile.py`; E2, list 3, item 1). The 3 gates denied commands: `no-destroy` 18, `no-sudo` 7, `audit-before-install` 1.

**Solution:**
- Step 1: the Linux default becomes `dev-mac` in `profile.sh` and `ai_profile.py`. Each `${PROFILE_X:-1}` default becomes the `dev-mac` value (E2, list 3, item 2).
- Step 2: the server-only units of E2 section 2 move to the branch `server-profile`: the root layer, the scanners, `agent-audit`, managed settings, Hermes, the box, opencode, last30days.
- Step 3: the 3 gates stay in `ai/routing.yaml` with `optional: true`. A machine turns one on in the owner config; a project turns one on in `.ai/enabled`. Their case files stay in the suite.
- `audit-before-install` needs `agent-audit`. So the gate and the tool stay together, and the gate is offered only where `agent-audit` is installed.
- Each move is one commit. The second router pass of ticket 03 goes in the same commit as the profile.
- The migration steps that undo old server-era installs stay one more release, then go (E2, section 7).

**Rules kept:** `no-destroy`, `no-sudo` and `audit-before-install` stay gates, off by default and on by choice. "Never run sudo" (E1 row 80) and the audit rules (E1 rows 57 to 62) stay in the gate deny texts. The `server` profile rules text moves with the branch.

**Edge cases:**
1. A Linux machine that still uses the `server` profile: `ai-doctor` FAILs with the 2 steps: switch the profile file, or check out the `server-profile` branch. Nothing is removed from that machine by a pull.
2. Tests and fixtures that exist only for the server units (`test_box.py`, the server profile fixtures, `t_sandbox_policy`): they move with their units. The PR lists each file and where it went.
3. Shared helpers inside `no-destroy` (`project_tier`, `cd_target`, `git_sub`, `current_branch`, `short_flags`) are used by other gates. They stay in the core (E2, list 5, item 1).
4. Docs: `README.md`, `docs/GUIDE.md` and the rules files name the server units. A grep for each moved name is in the PR, with 0 stale hits.
5. Old installs: `scanners_drop`, `agents_drop_user` and the last30days uninstall clean old copies. Removing them too early leaves old copies on a machine. They stay one release.
6. A machine that is one commit behind runs `ai-sync` after the pull. The new default profile applies at that run. `ai-doctor` shows the profile it found.
7. The gate-skip escape (`/etc/ai/gate-skip`) is server-only. Each deny text that names `sudo ai-gate-skip` changes to the dev-mac text (E2, section 6, items 3 and 6).
8. macOS and Linux: after step 1, both pick `dev-mac`. A test runs the resolver with no profile file on both OS names.

**Owner steps:** None after D8.

**Blocked by:** 03

**Status:** needs-owner (D8: move the `server` profile to its own branch)

**Size:** L

- [ ] With no profile file, `ai_profile.py` and `profile.sh` pick `dev-mac` on Linux and on macOS (test).
- [ ] The branch `server-profile` exists and holds the moved units.
- [ ] The core has no `server.env`, and `ai-render` has no profile filter.
- [ ] `no-destroy` turned on in a project's `.ai/enabled` denies `rm -rf data/` (case file).
- [ ] The PR shows the lines removed from the core: code and tests.
- [ ] `ai-doctor` FAILs on a fixture HOME whose profile file says `server`, and names the 2 steps.

**Verify:**
- Unit: `bash ai/tests/run.sh`; `ai/tests/test_profiles.py` gets `t_linux_default_dev_mac`; the 3 gate case files run with the optional gate on.
- Drive: `$H drive install dev-mac` (no server step in the plan); `$H drive hook --agent claude PreToolUse` with `no-destroy` on in the fixture; a Codex payload drive of the same.
- Behaviour scenario: the 12 gate scenarios of ticket 02, with the 3 optional gates on.

**Rollback:** Merge the branch back, or revert each move commit. Step 1 is its own commit.
