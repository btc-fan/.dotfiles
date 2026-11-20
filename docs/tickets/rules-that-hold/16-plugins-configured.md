# 16: Each plugin is configured so that no job is done twice

**What to build:** The installer writes the plugin switches of file I, section E, from config. Each other plugin stays installed. A new Claude session then loads about half the fixed text of today, and 2 conflicts with the owner's rules go away. Each switch is its own commit, so one can be undone alone.

**Why:** The fixed cost of one new Claude session is about 22,790 tokens (file I, section B). With the switches it is about 10,780. Two conflicts: the OMX autonomy block in the Codex rules file contradicts the `ask-first` gate. The `skillOverrides` entries for 6 OMC skills do nothing, because Claude Code 2.1.325 does not apply them to plugin skills. The older ticket `docs/tickets/setup-audit/01-plugin-skill-overrides.md` found this; this ticket closes it.

**Solution:** The switches. Each one is written by `claude.sh`, `codex.sh` or `aiconf` with a recorded undo:
1. claude.ai connectors off: env `ENABLE_CLAUDEAI_MCP_SERVERS=false` at user scope (about 4,000 tokens).
2. OMC shell history off: `"bashHistory": false` in the OMC config.
3. OMC per-call text off: `env.OMC_SKIP_HOOKS` with the 6 tokens of file I, and `env.OMC_QUIET = "2"`, for Claude and Codex.
4. The ai-core plugin version goes up, so the plugin cache follows the repo (R-018).
5. Serena tools trimmed: `excluded_tools` with the 10 tools that have 0 calls (file I list).
6. Bundled skills `name-only`: the 10 skills of file I, in `skillOverrides` (it works for bundled skills).
7. The dead `skillOverrides` entries go, from the user settings and the `ai-adopt` template. Their losers become winner-gate rows.
8. The OMX autonomy block is cut from the rendered Codex rules file by `ai-sync`.

The other 2 rows of file I belong to other tickets: the output style (15) and the short rules file (14). The unused agent file is an owner file; the ticket prints its path, and the owner moves it.

**Rules kept:** No owner rule changes. The winner gate keeps its job and gets 2 more losers (`oh-my-claudecode:create-verification-skill`, `oh-my-claudecode:maintain-verification-skill`). The `ask-first` gate wins over the OMX text, as the global rule order says. "Knowledge lives in the repo only" is helped by switch 3 (`project-memory-posttool` off).

**Edge cases:**
1. A plugin update rewrites its config: the installer writes the switches on each run, and `ai-doctor` warns when one is missing.
2. A switch that does not exist in an older plugin version: the installer reads the installed version. It prints "switch X: not in version Y" and writes nothing for that switch.
3. The owner uses a connector in one project. For `disableClaudeAiConnectors`, "any-source-true wins": a project `false` cannot undo a user `true` (file I, section F). So switch 1 uses the env key `ENABLE_CLAUDEAI_MCP_SERVERS=false` at user scope. A project sets it to `true` in its own settings `env`. The owner guide (ticket 22) says how.
4. The stale plugin cache: switch 4 bumps the version. `ai-doctor` compares the cache hooks with the repo hooks (R-018 check).
5. `OMC_SKIP_HOOKS` also stops the OMC read budget and TODO lines (file I: "Low to medium" risk). The PR names what the owner loses.
6. OMX setup can write the autonomy block back. `ai-sync` cuts it again on each run, and `ai-doctor` warns when it is there.
7. A machine without OMX or Serena: each switch is written only when its tool is installed.
8. The installer runs while a Claude session is open: settings reload on change, and env keys apply to new sessions only. The PR says to start a new session.

**Owner steps:** None after D6. The owner moves the unused agent file if they want to.

**Blocked by:** 01

**Status:** needs-owner (D6: the switches of file I for the other plugins, each as its own commit)

**Size:** M

- [ ] Each of the 8 switches is one commit, and each is written by the installer from config.
- [ ] `ai-doctor --numbers` shows the fixed cost before and after, and the PR has both numbers.
- [ ] A new session has no claude.ai connector instructions and no OMC per-call lines.
- [ ] No `skillOverrides` entry names a plugin skill.
- [ ] The rendered Codex rules file has no autonomy block.
- [ ] `uninstall.sh` removes each switch (dry-run evidence).

**Verify:**
- Unit: `ai/tests/test_setup.py` gets one test per switch (written, recorded, undone); `ai/tests/test_commands.py` checks the winner table rows.
- Drive: `$H drive install dev-mac` lists each planned key; a real Claude session drive shows the start context.
- Behaviour scenario: the 12 gate scenarios and the reply-shape scenario of ticket 02.

**Rollback:** Revert the commit of one switch, and run the installer. Each switch has a recorded undo.
