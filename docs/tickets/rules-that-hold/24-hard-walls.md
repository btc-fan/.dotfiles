# 24: A project or an agent cannot switch the core off

**What to build:** Optional, only with D9. A root-owned managed settings file for Claude Code holds the core deny rules and the gate hook. `/etc/codex/requirements.toml` pins the Codex sandbox, the approval policy and the gate hook. The Claude sandbox is on, and it denies writes to the setup's state folder. Then a project file cannot switch the gates off, and an agent cannot forge the owner's merge OK.

**Why:** A project's `disableAllHooks`, or `enabledPlugins` with the core plugin off, wins over user settings today. Only managed settings are immune (file C, section 7; file I, section F, item 4). On Codex, only `/etc/codex/requirements.toml` is out of the agent's reach (file D, section 5). The merge OK lives in a state file that the agent can write (spec, Phase 8). The repo rule: no root-layer steps on a machine unless the owner asks.

**Solution:**
- `ai-hard-walls --dry-run` prints the 2 files and the 2 `sudo` commands. It never runs `sudo` itself.
- Claude: macOS `/Library/Application Support/ClaudeCode/managed-settings.json`, Linux `/etc/claude-code/managed-settings.json`. It holds the deny rules, the ai-core PreToolUse hook with `onFailure: "block"`, `enabledPlugins` with ai-core forced on, and `Bash(sudo *)` denied.
- Claude sandbox: `sandbox.enabled: true` and `filesystem.denyWrite` on the setup state folder.
- Codex: `allowed_sandbox_modes = ["read-only", "workspace-write"]`, `[features] hooks = true`, and the gate hook under `managed_dir`.
- The hook scripts that the managed files name are root-owned copies. Codex hashes the declaration, not the script (file D, section 2.9).
- The removal steps: 2 `sudo rm` commands, printed by `ai-hard-walls --undo`.

**Rules kept:** Each of the 12 gates keeps its logic. Their home grows: the managed hook runs them even when a project switches the plugin off. `merge-approval` gets a state file that only the hook writes. "Never run sudo" stays in the deny rule.

**Edge cases:**
1. The repo rule "no root-layer steps unless the owner asks": this ticket waits for D9. The agent only prepares the files and the commands.
2. A wrong managed file can block every session. Recovery: `sudo rm` of that file. `--safe-mode` still applies managed settings (file C, section 7), so it is not a way out. The owner guide adds the 2 recovery commands.
3. Plugin updates: the managed hook points to the root-owned copy, so a plugin update does not change it. `ai-doctor` warns when the copy is older than the repo hook.
4. A machine without `sudo`, or where the owner says no: the walls of tickets 04 to 09 still hold (GitHub and git hooks). `ai-doctor` prints "managed layer: off".
5. Passwordless or cached `sudo`: the agent could edit the files. The `Bash(sudo *)` deny rule and the sandbox stop the plain form. Other spellings remain a known limit (file C, section 13).
6. The sandbox breaks a tool that writes outside the work tree (`gh` auth, `uv` caches). The ticket lists each excluded path and why.
7. Codex `--dangerously-bypass-approvals-and-sandbox` with pinned requirements: not documented (file D, section 10, item 4). The test tries it, and the result goes into the ticket.
8. Claude Code refuses `bypassPermissions` under root. The files are written by the owner with `sudo`, and the agent runs as the normal user.

**Owner steps:** M6: the 2 `sudo` commands that `ai-hard-walls --dry-run` prints (one for Claude, one for Codex).

**Blocked by:** 23

**Status:** needs-owner (D9: root-owned settings on the machines; needs `sudo`)

**Size:** S

- [ ] `ai-hard-walls --dry-run` prints both files, and changes nothing (test with a temp root).
- [ ] With the managed file in place, a project `.claude/settings.json` with `"disableAllHooks": true` does not stop the `secret-scan` gate.
- [ ] A project setting that switches ai-core off does not stop a gate.
- [ ] A merge OK file written by hand does not open the `merge-approval` gate.
- [ ] A Codex session in `danger-full-access` mode is refused or clamped, and the result is written down.
- [ ] `ai-hard-walls --undo` prints the 2 removal commands.

**Verify:**
- Unit: `ai/tests/test_setup.py` gets `t_managed_settings_shape`, `t_codex_requirements_shape` and `t_merge_ok_forged` (with a temp root folder).
- Drive: a real Claude session drive with a project `disableAllHooks` file and the managed file in a test root. A Codex payload drive with the requirements file.
- Behaviour scenario: the 12 gate scenarios of ticket 02, with a project file that tries to switch the core off.

**Rollback:** The owner runs the 2 `sudo rm` commands that `ai-hard-walls --undo` prints.
