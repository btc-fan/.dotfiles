# herdr

Pin: 0.9.5. License Apache-2.0. Sources: https://herdr.dev/tui/docs, https://github.com/herdrdev/herdr

## Vendor rules
No CLAUDE.md or AGENTS.md text found. The docs point to https://herdr.dev/agent-guide.md. It was not fetched: UNVERIFIED. Fetch it at build and decide whether to import it.
Our own rule is the owner block A.5 (PR author-sessions note). It sits in `ai/agents-md/50-pull-requests.md`.

## When / when not
- Use: run several agents in panes. Read an agent session id for the PR block. Status hooks for Claude and Codex. Hand a prompt to another agent: `herdr agent prompt <target> <text> [--wait] [--until STATUS] [--timeout MS]`.
- Do not use: as an agent-config surface (it has none). As a harness (no non-interactive model call).
- CLI: `herdr agent list|get|read|send-keys|prompt|rename|focus|wait|attach|start|explain`. JSON: `agent get`, `agent explain --json`, `session list --json`, `machine list --json`.
- `herdr agent get` gives `.result.agent.agent_session.value` and `.result.agent.cwd`.

## Enforcement
- L0: block A.5. L1: herdr integration hooks (status) run beside ours. L3: the `prompting-others` nudge.
- L4: the `pr-rules` gate blocks a PR body without the `<!-- author-sessions` block. This is the enforcement.
- L7: ai-doctor checks `herdr --version` is 0.9.5, `herdr integration status claude` and `codex` are installed, `HERDR_PANE_ID` is set in a pane, `[update]` flags are false.

## Proof
- Should fire (EN): "Create a PR for this branch". `gh pr create` with the author-sessions block, main id from `herdr agent get`.
- Should fire (RU): "Создай PR и добавь сессии агентов".
- Should not fire: "list files". No herdr call.
- Signal: Bash `herdr agent get`. The block in the PR body. `pr-resume` parses it.

## Setup checklist
1. Install (no checksum or signature exists for any route): download the install script, record its sha, read it, then run it with `HERDR_INSTALL_DIR=/usr/local/bin`. `curl ... | sh` is blocked by the gate. Or `brew install herdr` (macOS). Or `mise use -g herdr` (pin form UNVERIFIED). Run `agent-audit` first.
2. Config (merge only) `~/.config/herdr/config.toml`: `[update]` `version_check = false`, `manifest_check = false`. Telemetry key: not found (say "not found", not "none"). Never run `herdr update`.
3. Integrations (throwaway HOME first, read the diff): `herdr integration install claude`, `herdr integration install codex`. The Codex one sets `[features] hooks = true` in `config.toml` (OMX manages that file too).
4. Verify: `herdr --version`. `herdr integration status claude` and `codex`. In a pane: `herdr agent get "$HERDR_PANE_ID" | jq -r '.result.agent.agent_session.value'` is not empty.
5. Cleanup: `herdr integration uninstall claude|codex` (Codex leaves `hooks = true`: remove it by hand if nothing else needs it). Remove the binary and `~/.config/herdr/`.
Open: herdr with tmux (OMC and OMX team runtimes use tmux) is UNVERIFIED. Test on the server. Keep the OMX herdr transport off.
Intake audit owed (installer without checksum).
