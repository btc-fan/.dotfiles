# box (our MCP server for project boxes)

Pin: part of the ai-core plugin (this repo). Server `box` in `ai/marketplace/plugins/ai-core/.mcp.json`; tools `mcp__plugin_ai-core_box__<name>`. It runs the root-owned `/usr/local/sbin/proj-agent` for the agent, so no agent needs sudo or a socket.

## Vendor rules
NOT FOUND: our own server. The rules are in this file and in the hosting rules of the `ubuntu-server` branch.

## When / when not
- All box work on a server. Tools (`mcp__plugin_ai-core_box__<name>`; Codex and Hermes: server `box`):
  - `list`, `status`, `doctor`, `help`: read the state.
  - `new`: `name`, `tier` (`try` or `mvp`), optional `docker`, `pg`.
  - `exec`: `command` (a bash string, run with `bash -lc` in the box: pipes and `&&` work) or `argv` (a list); optional `cwd`, `timeout` (up to 3600 s).
  - `logs`: `box` or `unit`, optional `lines`. `restart`: a service in a box. `ports`, `url`: how to reach the app. `snapshot`: before a risky change.
- Claude, Codex and Hermes all use the tool. Codex is told: the tool, or plain `proj-agent <subcommand>` without sudo where it is not sandboxed. Hermes the same.
- One wording everywhere: box work = the box tool (MCP server `box`: list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help); outside a sandbox also plain `proj-agent <subcommand>`; never sudo. The no-sudo gate denies `sudo proj-agent`; its message names the box tools (Claude) or the tools and plain `proj-agent` (Codex, Hermes).
- Not for long-tier boxes, wiping, restoring or touching another project: those are owner-only (`proj` as admin). The tool refuses them; tell the owner the exact command.
- Not on macOS (no boxes there).
- Code is edited in the workspace with the normal tools; it runs only inside the box (`exec`).

## Knowledge home, freshness, maintenance
- Home: none here. The box registry lives on the server (`/srv/proj/REGISTRY.json`, root-owned). Ask the tool (`list`, `status`) each time; do not cache box state in AGENTS.md.

## Enforcement
- L0: root AGENTS.md "No root" part and the hosting rules (server).
- L4: `no-sudo` gate denies `sudo proj-agent` and every other sudo; its message names this tool.
- The tool itself checks the subcommand allow-list and the calling user.
- L7: `/var/log/proj-agent.log` (admin reads it), `gates.log` for denied sudo calls.

## Proof
- Should fire (EN): "create a test box for a small web page". Expect the tool's `new` call.
- Should fire (RO): "porneste o cutie noua pentru botul de Telegram". Expect `new`.
- Should fire (RU): "покажи логи коробки btc-page". Expect `logs`.
- Should not fire: "list the files in this folder". On a Mac the server lists no tools.
- Signal: tool_use `mcp__plugin_ai-core_box__*`; a line in `/var/log/proj-agent.log`; no `sudo proj-agent` in the transcript.

## Setup checklist
1. Server installs only. Claude: the ai-core plugin, allow rule `mcp__plugin_ai-core_box__*`. Codex: `codex mcp add box` with `tool_timeout_sec = 3720` and `default_tools_approval_mode = "approve"`. Hermes: `hermes mcp add`. `proj-agent` comes from the `ubuntu-server` branch (step 70-hosting) at `/usr/local/sbin/proj-agent` (the only path).
2. Keys: none. Telemetry: none (local only).
3. Verify: `/mcp` in a Claude session on the server lists `box`; the tool's `help` and `list` answer; `ai-doctor` shows the server connected.
4. Cleanup: removed with the ai-core plugin.
