# 03: The router suite tests the rules that the machines load

**What to build:** `bash ai/tests/run.sh` tests the routing that each machine renders: the `dev-mac` profile. A second pass tests the `server` render while that profile exists. A coverage check fails when a rule of a render has no case that fires and no case that does not fire.

**Why:** `ai/tests/test_router.py` renders `--profile server` (spec, section 2, cause 5). So the main suite runs rows that no machine loads, and it never runs the `dev-mac` render (file E2, section 2). The 3 server-only gates have 199 cases (`no-destroy` 101, `audit-before-install` 66, `no-sudo` 32). The 9 gates that `dev-mac` loads are tested only by chance, through the server render.

**Solution:**
- `test_router.py` renders with `--profile dev-mac` for the main pass, and with `--profile server` for a second pass.
- The profile is always passed on the command line. The test clears `AI_PROFILE` and never uses the OS default.
- A case file whose rule id is not in a render runs only in the pass that has the rule. The test prints which files ran in which pass.
- A coverage check: each rule id in each render has at least 1 fire case and 1 no-fire case. The check fails with the rule id.
- A golden fixture of the `dev-mac` render: `ai/tests/fixtures/profiles/agents-dev-mac.md`, next to `agents-server.md`.
- The server pass is removed by ticket 18, in the same commit that removes the profile.

**Rules kept:** No rule changes. Each of the 39 rows stays in `ai/routing.yaml`. Only the test that reads them changes.

**Edge cases:**
1. The Linux OS default picks `server` today (`profile.sh`, `ai_profile.py`). A CI runner on Ubuntu (ticket 04) would test the server render by accident. The explicit `--profile` flag stops this, and a test asserts it.
2. A developer with `AI_PROFILE=server` in the shell: the test clears the variable, so the result is the same on each machine.
3. Rows with `profiles: [server]` (3 today) render only in the server pass. A new row with a profile list gets the same treatment, with no code change.
4. `ask-first` is in every profile. It must run in both passes, and the coverage check proves it.
5. Run time: two renders and two passes. The test prints the time of each pass. When the suite gets more than 20% slower, the ticket says so in its evidence.
6. The golden fixture holds the L0 table today. Tickets 11, 13 and 14 change that text, so each of them updates the fixture in the same commit.
7. A case that passes only because the server render holds a gate that `dev-mac` does not hold: the dev-mac pass shows it as a failure. Each such case is fixed or moved, never skipped.

**Owner steps:** None.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** S

- [ ] `test_router.py` prints 2 passes: `dev-mac` and `server`.
- [ ] The main pass renders `dev-mac`, and a test fails when the render command has no `--profile` flag.
- [ ] The coverage check fails for a rule with no fire case, and names the rule. A test proves it with a throwaway rule.
- [ ] `ai/tests/fixtures/profiles/agents-dev-mac.md` exists, and the suite compares the render with it.
- [ ] `bash ai/tests/run.sh` passes on a macOS machine and on a Linux machine with no `~/.config/ai/profile` file.

**Verify:**
- Unit: `bash ai/tests/run.sh`, plus new functions `t_router_profile_flag`, `t_router_coverage` and `t_router_dev_mac_golden` in `ai/tests/test_router.py`.
- Drive: `$H drive install dev-mac` (the dry-run render) and `$H drive hook --agent claude PreToolUse '<git push origin main payload>'`. The evidence shows the dev-mac routing in use.
- Behaviour scenario: none needed. The gate scenarios of ticket 02 must still pass.

**Rollback:** Revert the commit. The suite goes back to the server render.
