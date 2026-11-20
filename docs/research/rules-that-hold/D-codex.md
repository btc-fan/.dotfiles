# D: Codex CLI enforcement capability map (codex-cli 0.170.0)

Date: 2026-11-20. Scope: read-only research. No file under ~/.codex was changed.

## 0. Sources and method

- Installed version: `codex --version` prints `codex-cli 0.170.0`. Latest release on GitHub is `rust-v0.171.0` (`gh api repos/openai/codex/releases/latest`).
- Source: shallow clone of tag `rust-v0.170.0` (commit `72f97c309fb0f78b6f35cce455adf416e6a51571`) at
  `<scratch>/codex-src/`.
  All `codex-rs/...` paths below are relative to that folder.
- Official docs: `developers.openai.com/codex/<page>` now redirects to `learn.chatgpt.com/docs/...`. Markdown copies (fetched 2026-11-20) are in
  `<scratch>/plan-research/codex-docs/`.
  "hooks.md:L" means a line in that cached copy. The `docs/*.md` files in the repo are only stubs that link to the site (for example `docs/execpolicy.md`, `docs/agents_md.md`), except `docs/config.md`, which has one note on `allow_managed_hooks_only`.
- Real command output: `codex execpolicy check` runs with rules files in `plan-research/test.rules` and `plan-research/mitigate.rules`.
- No `codex exec` run was made (the brief allows only print-only commands). Statements about runtime behavior come from docs or source, and are marked so.
- Note for the owner: the shared folder `plan-research/docs/` holds Claude Code docs from another agent. My first download wrote five Codex files there with the same names (`hooks.md`, `skills.md`, `plugins.md`, `sandboxing.md`, `security.md`). I moved all Codex files to `codex-docs/` and downloaded the Claude Code versions of those five pages again from `code.claude.com/docs/en/<page>.md`. If the other agent had local edits in those five files, the edits are gone.

### Current state on this Mac (read-only look, for context)

- `~/.codex/AGENTS.md`: 44551 bytes, plain text (starts with an OMX "AUTONOMY DIRECTIVE"). `~/.codex/config.toml` has `project_doc_max_bytes = 65536`, no `approval_policy`, no `sandbox_mode` (defaults apply).
- `~/.codex/hooks.json`: PreToolUse `Bash` -> `rtk hook codex`; oh-my-codex `codex-native-hook.js` on most events; herdr `ask-hook.sh` on PermissionRequest (timeout 1800 s).
- Plugin `ai-core@ai` (cache `~/.codex/plugins/cache/ai/ai-core/1.0.0/hooks/codex-hooks.json`): `router.py --agent codex` on SessionStart, UserPromptSubmit, PreToolUse (matcher `Bash|apply_patch`), PostToolUse, Stop, SubagentStop, SessionEnd. This is where the owner's gates run today.
- `~/.codex/rules/default.rules` exists (6.7 KB). `/etc/codex` does not exist: no managed layer, no requirements.
- `codex features list`: `hooks stable true`, `plugins stable true`, `multi_agent deprecated true`, `multi_agent_v2 stable false`, `network_proxy experimental false`.

---

## 1. Instruction files (AGENTS.md)

| Item | Behavior | Source |
|---|---|---|
| Global file | `$CODEX_HOME/AGENTS.override.md`, else `$CODEX_HOME/AGENTS.md` (`CODEX_HOME` default `~/.codex`). First non-empty file only. | learn.chatgpt.com/docs/agent-configuration/agents-md (guides_agents-md.md:11); `codex-rs/codex-home/src/instructions/mod.rs:43-78` |
| Global size | The global file is NOT counted against `project_doc_max_bytes`. The loader reads the whole file and trims it. | `codex-home/src/instructions/mod.rs:57-73` (no budget code) |
| Symlink | Works: the loader uses `tokio::fs::metadata` (follows symlinks) and `is_file()`. So `~/.codex/AGENTS.md -> ~/.config/ai/AGENTS.md` is valid. | `codex-home/src/instructions/mod.rs:45-46` |
| `@file` imports | Not supported. Codex concatenates raw text. A line `@~/.config/ai/AGENTS.md` (Claude style) is passed as literal text. | Not documented; no import code in `core/src/agents_md.rs` |
| Project files | From the project root (default marker `.git`, key `project_root_markers`) down to cwd. Per directory: `AGENTS.override.md`, then `AGENTS.md`, then each name in `project_doc_fallback_filenames`. At most one file per directory. Root first, cwd last. | guides_agents-md.md:12-13; `core/src/agents_md.rs:1-18` |
| Separator | Global and project text are joined with `\n\n--- project-doc ---\n\n`. | `core/src/agents_md.rs:49` |
| Budget | `project_doc_max_bytes` (default 32 KiB). A file over the remaining budget is truncated and Codex adds a warning; later files are skipped. `0` disables project docs. | guides_agents-md.md:15; `core/src/agents_md.rs:65-173` |
| Untrusted project | Project AGENTS.md files are NOT loaded when the project is untrusted (`config.active_project.is_untrusted()`). This includes the `trust_level = "untrusted"` entry that the docs recommend as the replacement for the retired `approval_policy = "untrusted"`. | `core/src/agents_md.rs:65`; agent-approvals-security.md:34-46 |
| When loaded | Once per run; TUI: at session start. No cache. | guides_agents-md.md:10, 199 |
| `codex exec` | Same loader (core). The doc shows `codex exec` and `codex --ask-for-approval never` checks. | guides_agents-md.md:194-199 |
| Subagents | Not documented. Source: every thread that one `ThreadManager` creates gets the same `user_instructions_provider` (`core/src/thread_manager.rs:2236`), and spawned agents are threads of that manager. So the global file reaches subagents (inferred). Custom agents add `developer_instructions`. | subagents.md:338-360 |
| See what loaded | No `/instructions` command. Docs: run with `-c log_dir=./.codex-log` and read `codex-tui.log`, or read the latest `session-*.jsonl`. | guides_agents-md.md:198 |
| Managed instructions | `additional_developer_instructions` in `requirements.toml`: a separate developer message, limit 10,000 estimated tokens. The agent cannot change it. | config-reference.md:2268-2272 |

Minimal example:

```toml
# ~/.codex/config.toml
project_doc_max_bytes = 65536
project_doc_fallback_filenames = ["CLAUDE.md"]   # a directory with AGENTS.md still wins
```

Limit: a project `CLAUDE.md` that contains only `@AGENTS.md` adds nothing on Codex, and Codex reads AGENTS.md directly anyway.

---

## 2. Hooks

### 2.1 Where hooks are defined

| Scope | Location | Trust | Source |
|---|---|---|---|
| System (macOS, Linux) | `/etc/codex/hooks.json`, or `[hooks]` in `/etc/codex/config.toml` | Managed: "trusted by policy", cannot be disabled from `/hooks` | hooks.md:36-41, 78-79; `hooks/src/engine/discovery.rs:1032` (`System => (HookSource::System, true)`) |
| Requirements | `[hooks]` in `/etc/codex/requirements.toml` (also MDM `requirements_toml_base64`, cloud) | Managed | hooks.md:342-382 |
| User | `$CODEX_HOME/hooks.json` or `[hooks]` in `~/.codex/config.toml` | Needs review and trust | hooks.md:40, 67-72 |
| Project | `.codex/hooks.json` or `.codex/config.toml` `[hooks]`, from project root to cwd, trusted projects only. In a linked worktree, a project layer can read hooks from the main checkout. | Needs trust | hooks.md:41, 52-55 |
| Plugin | `hooks/hooks.json` in the plugin root, or `hooks` in `.codex-plugin/plugin.json` (path, array of paths, inline object). Env: `PLUGIN_ROOT`, `PLUGIN_DATA`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`. | Needs trust; plugin content is hashed too | hooks.md:384-419 |
| Session flags | `-c` overrides | Not managed | `discovery.rs:1037` (`SessionFlags => (.., false)`) |

- All matching hooks from all sources run. Matching command hooks for one event start concurrently. The same command in two files runs twice. hooks.md:16-18, 62-65.
- Kill switch: `[features] hooks = false` (alias `codex_hooks`), or `--disable hooks` on the command line. Only `requirements.toml` `[features].hooks = true` stops a user from turning hooks off. hooks.md:317-328, 345-347.
- `allow_managed_hooks_only = true` works only in `requirements.toml`; it skips user, project, session and plugin hooks. `docs/config.md` in the repo; hooks.md:380-382.

### 2.2 Events

| Event | When it fires | Can block? | matcher on | Source |
|---|---|---|---|---|
| SessionStart | startup, resume, clear, compact, fork; also after a root compaction, before the next model request | `continue:false` ends the turn (after compact) | `source` | hooks.md:660-694 |
| SessionEnd | main thread ends (close, archive, delete, 30 min idle). Not for subagents. Always synchronous. | No (advisory) | `reason` (always `other`) | hooks.md:696-731 |
| UserPromptSubmit | before a prompt goes to the model | Yes: `decision:"block"` or exit 2 | not used | hooks.md:1024-1060 |
| PreToolUse | before a local tool call | Yes: deny, legacy block, exit 2; can rewrite with `updatedInput` | tool name and aliases | hooks.md:763-843 |
| PermissionRequest | when Codex is about to ask for approval (escalation, managed network) | Yes: allow or deny; no decision = normal prompt | tool name | hooks.md:845-903 |
| PostToolUse | after a tool returns, also after a non-zero Bash exit | Cannot undo. `decision:"block"`/exit 2 replaces the tool result with feedback; `continue:false` stops normal processing | tool name | hooks.md:905-956 |
| PreCompact / PostCompact | around compaction | `continue:false` stops before / after compaction | `manual`/`auto` | hooks.md:988-1022 |
| SubagentStart | spawned subagent starts | No (`continue:false` parsed, ignored) | `agent_type` | hooks.md:733-761 |
| SubagentStop | subagent turn ends | `decision:"block"` continues the subagent | `agent_type` | hooks.md:1062-1094 |
| Stop | root turn ends | `decision:"block"` makes a new continuation prompt from `reason` | not used | hooks.md:1096-1128 |
| Interrupt | user interrupts an active main-thread turn | No. Timeout 1 s default, 1 to 3 s | not used | hooks.md:1130-1147 |
| PreModelRequest / PostModelRequest | each model request attempt | No (diagnostic) | not supported | hooks.md:972-986 |

### 2.3 Matcher syntax

- Regex string. `"*"`, `""` or no matcher = all. hooks.md:423-425.
- Matcher aliases: `apply_patch` also matches `Edit` and `Write`; `spawn_agent` also matches `Agent`. The hook input keeps the canonical name. hooks.md:445, 469; `core/src/tools/hook_names.rs:28-50`.
- MCP names: `mcp__<server>__<tool>`, for example `mcp__filesystem__.*`. hooks.md:452-453.

### 2.4 Tool names and payloads

| Tool path | `tool_name` | `tool_input` | Source |
|---|---|---|---|
| Shell / unified exec (`exec_command`) | `Bash` | `{"command": "<the cmd string>"}`. The `workdir` argument is not in `tool_input`; it is resolved into the hook `cwd`. | `core/src/tools/handlers/unified_exec/exec_command.rs:336-347`; hooks.md:465-466 |
| `apply_patch` | `apply_patch` | `{"command": "<full patch text>"}` (file paths are in the `*** Update File:` / `*** Add File:` lines) | hooks.md:780; `core/src/tools/handlers/apply_patch.rs:370` |
| MCP tool | `mcp__server__tool` | the MCP arguments | hooks.md:468, 780 |
| Other local function tools | function name (for example `update_plan`, `spawn_agent`) | the JSON arguments | hooks.md:469; `core/src/tools/registry.rs:173-183` |
| `tool_response` (PostToolUse) | MCP: the MCP call result; others: the model-facing output | | hooks.md:925 |

Common input fields: `session_id` (subagents send the parent session id), `transcript_path`, `cwd`, `hook_event_name`, `model`, plus `turn_id` and `permission_mode` (`default`, `acceptEdits`, `plan`, `dontAsk`, `bypassPermissions`) on most events. hooks.md:479-504.

### 2.5 Tool calls with NO hook

| Path | Why | Source |
|---|---|---|
| `write_stdin` (input to a running unified-exec process, or a poll) | `pre_tool_use_payload` returns `None`. A command typed into an interactive shell that the agent started gets no PreToolUse and no execpolicy check. | `core/src/tools/handlers/unified_exec/write_stdin.rs:141-146`; hooks.md:472-474 |
| Code-mode `wait` | returns `None` for Pre and Post | `core/src/tools/code_mode/wait_handler.rs:233-249` |
| Hosted tools (for example `WebSearch`) | not on the local function-tool path | hooks.md:470 |
| Any tool whose payload is not `ToolPayload::Function` (`Custom`, `ToolSearch`) and that does not override the default | default `pre_tool_use_payload` returns `None` | `core/src/tools/registry.rs:173-176`; `codex-rs/tools/src/tool_payload.rs:7-11` |
| Internal subagents (for example the auto-review reviewer) | "Internal/system subagents skip start hooks"; Stop is not dispatched for them | `core/src/hook_runtime.rs:137-154, 421-422` |
| Background (`async: true`) hooks | run, but cannot block or rewrite | hooks.md:644-646; `hooks/src/engine/mod.rs:207-209` |

The docs say it directly: "Some specialized tool paths can opt out of the default hook path. Treat tool hooks as a useful guardrail, not a complete enforcement boundary." hooks.md:476-477.

### 2.6 Exit codes, JSON and failure modes (PreToolUse)

From `codex-rs/hooks/src/events/pre_tool_use.rs:199-317`:

| Hook result | Status | Tool runs? |
|---|---|---|
| exit 0, empty stdout | Completed | yes |
| exit 0, valid JSON `permissionDecision:"deny"` + non-empty `permissionDecisionReason` | Blocked | NO |
| exit 0, legacy `{"decision":"block","reason":"..."}` | Blocked | NO |
| exit 2 + non-empty stderr | Blocked | NO |
| exit 2 + empty stderr | Failed ("exited with code 2 but did not write a blocking reason") | YES (fail open) |
| exit 0, `permissionDecision:"deny"` with empty or missing reason | Failed (invalid) | YES (`output_parser.rs:461-471`) |
| exit 0, `permissionDecision:"ask"`, `"allow"` without `updatedInput`, legacy `approve`, `continue`, `stopReason`, `suppressOutput` | Failed | YES (hooks.md:841-843; `output_parser.rs:441-480`) |
| exit 0, JSON with an unknown field | `deny_unknown_fields` on every output struct, so parse fails, then "invalid pre-tool-use JSON output", Failed | YES (inferred from `hooks/src/schema.rs:128-141` and `output_parser.rs:345-357`; not tested with a live run) |
| exit 0, plain text (not JSON) | ignored | yes |
| exit 1 or any code other than 0 and 2 | Failed ("hook exited with code N") | YES |
| crash / killed by signal (no exit code) | Failed ("hook exited without a status code") | YES |
| timeout | Failed ("hook timed out after Ns"), process group killed | YES (`hooks/src/engine/command_runner.rs:226-232, 333-398`) |
| input serialization error | not blocked | YES (`pre_tool_use.rs:319-327`) |

Conclusion: PreToolUse FAILS OPEN on every error. There is no Codex equivalent of Claude Code `onFailure: "block"`. The cloud-hooks doc says the same: "A `PreToolUse` error, timeout, or malformed response can let the tool run." hooks.md:340.

Other events (same pattern, non-zero exit other than 2 = Failed and ignored): `user_prompt_submit.rs:247`, `post_tool_use.rs:282`, `session_start.rs:317`, `interrupt.rs:158`.

PermissionRequest: deny wins over allow; a failed hook gives no decision, so the normal approval prompt shows (fail to human, not to allow). Returning `updatedInput`, `updatedPermissions` or `interrupt` "fail closed today". `hooks/src/events/permission_request.rs:153-170, 259-288`; hooks.md:897-903.

Model-visible block text: `Command blocked by PreToolUse hook: <reason>. Command: <command>` (Bash, apply_patch) or `Tool call blocked by PreToolUse hook: <reason>. Tool: <name>`. `core/src/hook_runtime.rs:249-259`.

Ordering: PreToolUse runs in the tool registry before the handler, so before execpolicy and the sandbox approval logic. `core/src/tools/registry.rs:1118-1150`.

### 2.7 Timeouts and output limits

- `timeout` in seconds. Default 600 s, minimum 1. SessionEnd and Interrupt: default 1 s, clamped to 1 to 3 s. `hooks/src/engine/discovery.rs` `normalize_command_hook` (near line 950); hooks.md:187-189.
- MCP-tool hooks: the shorter of the hook and server timeout; errors, missing servers or tools do not block. hooks.md:304-312.
- `additionalContext` over ~2,500 tokens spills to `<temp_dir>/hook_outputs/<session_id>/<uuid>.txt`; `additionalContextLimit` changes the limit. hooks.md:539-578.
- Up to 8 background hooks per session. hooks.md:650-656.

### 2.8 How the hook process runs

- `$SHELL -lc "<command>"` (login shell; `/bin/sh` if `SHELL` is unset), cwd = session cwd. `hooks/src/engine/command_runner.rs:444-505`. The spawn has no sandbox wrapper: hooks run with full user rights, outside the Codex sandbox (inferred from the plain `tokio::process::Command`; not documented).
- Login shell means `~/.zprofile` / `~/.bash_profile` run on each hook call (startup cost, environment drift).

### 2.9 Trust model

- `/hooks` in the TUI lists sources, shows new or changed hooks, trusts them, or disables a non-managed hook. hooks.md:74-76.
- State lives in `config.toml` under `[hooks.state."<key>"]` with `enabled` and `trusted_hash` (and `trusted_content_hash` for plugins). `codex-rs/config/src/hook_config.rs:20-37`.
- Key format: `<source>:<event_snake_case>:<group_index>:<handler_index>`, for example `~/.codex/hooks.json:pre_tool_use:0:0` or `ai-core@ai:hooks/codex-hooks.json:pre_tool_use:0:0`. `hooks/src/lib.rs:125-135`; real keys in `~/.codex/config.toml`.
- Hash: `sha256` of the normalized hook declaration (event, matcher, handler config incl. the command string and timeout), NOT the script file content. `hooks/src/engine/discovery.rs:973-997`. Plugin hooks add a hash of the plugin content: "If a plugin update changes a bundled script, Codex requires a new review even if the hook definition stays the same." hooks.md:418-419; `discovery.rs:836-840`.
- Status: managed = `Managed`; same hash = `Trusted`; other hash = `Modified`; no hash = `Untrusted`. Only `Managed` and `Trusted` handlers run (or all, with `--dangerously-bypass-hook-trust`). `discovery.rs:917-929, 1001-1016`.
- Consequences:
  - A changed declaration (or a changed plugin script) is SKIPPED until someone re-trusts it in `/hooks`. A gate turns off silently except for a startup warning. Fail open.
  - A user-level hook whose script body changes (same command string) stays trusted and runs the new body. The script file is the real trust object; protect it with file permissions.
  - `codex exec` has no `/hooks` UI. New hooks must be trusted once in the TUI, or be managed, or run with `--dangerously-bypass-hook-trust`.

### 2.10 Hooks in `codex exec` and subagents

- `codex exec`: same core engine. Flag `--dangerously-bypass-hook-trust` exists on `exec` (`codex exec --help`). Hook events are NOT written to `--json` output: `ServerNotification::HookStarted | HookCompleted => CodexStatus::Running` (dropped). `exec/src/event_processor_with_jsonl_output.rs:477-479`. In human mode they go to stderr as `hook: PreToolUse Blocked` (`exec/src/event_processor_with_human_output.rs:273-290`).
- Subagents: PreToolUse, PermissionRequest and PostToolUse carry a `subagent` context for thread-spawned agents (`core/src/hook_runtime.rs:209, 285, 329`), so the parent's hooks apply to subagent tool calls. SubagentStart and SubagentStop fire. SessionEnd and Interrupt do not. hooks.md:27-29.

---

## 3. Approval policy and sandbox

| Key | Values | Source |
|---|---|---|
| `approval_policy` | `on-request`, `never`, `{ granular = { sandbox_approval, rules, mcp_elicitations, request_permissions, skill_approval } }`. `untrusted` is retired (it can stop the client from starting). `on-failure` is deprecated. | config-reference.md:92-96, 161-195 |
| Stricter command approval | omit `approval_policy` and set `[projects."<path>"] trust_level = "untrusted"`. Side effect: project config, project rules, project hooks AND project AGENTS.md are off. | agent-approvals-security.md:34-46; `core/src/agents_md.rs:65` |
| `approvals_reviewer` | `user` (default) or `auto_review` (reviewer agent; prompt-build, review and parse failures fail closed) | agent-approvals-security.md:310-353 |
| `sandbox_mode` | `read-only`, `workspace-write`, `danger-full-access` | config-reference.md:221-225 |
| `[sandbox_workspace_write]` | `writable_roots` (array), `network_access` (bool, default off), `exclude_tmpdir_env_var`, `exclude_slash_tmp` | config-reference.md:227-249 |
| `allow_login_shell` | default `true`; `false` rejects `login = true` | config-reference.md:205-209 |
| Permission profiles | beta replacement for `sandbox_mode` (`default_permissions`, `allowed_permission_profiles`, 0.138.0+) | config-reference.md:90; managed doc :423-425 |
| CLI | `-s/--sandbox`, `-a/--ask-for-approval`, `--add-dir`, `--dangerously-bypass-approvals-and-sandbox` (`--yolo`) | `codex exec --help`; agent-approvals-security.md:355-364 |

Read-only inside `workspace-write` (recursive): `<root>/.git` (dir or file, plus the resolved gitdir of a pointer file), `<root>/.agents`, `<root>/.codex`, `<root>/.aws`. agent-approvals-security.md:289-298; `codex-rs/protocol/src/permissions.rs:50-62`.
Effect for the gates: inside the sandbox `git commit` cannot write `.git`, and `git push` / `gh` have no network. Both need an escalation, which goes to the approval flow and the PermissionRequest hook (unless `approval_policy = "never"`, which auto-rejects).

Network: off by default in `workspace-write`; on with `network_access = true`; `features.network_proxy` constrains enabled traffic to domain rules. agent-approvals-security.md:99-160.

Linux: the sandbox sets `PR_SET_NO_NEW_PRIVS` when seccomp or Landlock filesystem limits apply, which "prevents setuid privilege elevation", so `sudo` fails inside the sandbox. `codex-rs/linux-sandbox/src/seccomp.rs:67-74`. macOS: Seatbelt (agent-approvals-security.md:422+). Test with `codex sandbox macos [--log-denials] <cmd>`.

Which layer is the real boundary (documented):
- "OS-level mechanisms enforce sandbox policies." agent-approvals-security.md:68.
- "Treat tool hooks as a useful guardrail, not a complete enforcement boundary." hooks.md:476-477.
- "If the container is your intended security boundary, run Codex with `--sandbox ...`" agent-approvals-security.md:465.
So: sandbox (OS) + requirements are the boundary; hooks and rules are guardrails.

Subagents inherit the parent turn's sandbox and approval settings, including `/permissions` and `--yolo`; a custom agent file cannot change them. subagents.md:313-316, 357-360.

---

## 4. Rules (execpolicy)

- Location: `rules/*.rules` next to every active config layer: `~/.codex/rules/`, `<repo>/.codex/rules/` (trusted projects only), system `/etc/codex/rules/` (via the System config layer folder), Team Config. TUI "always allow" writes `~/.codex/rules/default.rules`. rules.md:14-38; `core/src/exec_policy.rs:746-767`.
- Requirements: `[rules] prefix_rules = [...]` in `requirements.toml`, decision must be `prompt` or `forbidden`; merges with `.rules`, most restrictive wins. enterprise_managed-configuration.md:717-735.
- Syntax (Starlark): `prefix_rule(pattern=[...], decision="allow"|"prompt"|"forbidden", justification="...", match=[...], not_match=[...])`. A list inside `pattern` is a union of literals at that position. Strictest decision wins: forbidden > prompt > allow. rules.md:49-62.
- `match` / `not_match` are checked at load time. A failing example fails the parse (real output below).
- Meaning: `allow` = run outside the sandbox without a prompt; `prompt` = ask each time; `forbidden` = reject. With `approval_policy = "never"`, a `prompt` rule becomes a rejection. rules.md:57-60; `core/src/exec_policy.rs:449-460`.
- Shell splitting at runtime: the model's command string is run as `[shell, "-lc"|"-c", cmd]` (`core/src/tools/handlers/unified_exec.rs:151-175`). Codex splits that script into plain commands only when it is "plain words joined by `&&`, `||`, `;`, `|`". Otherwise the whole `[shell, -lc, script]` is one command. rules.md:64-118; `core/src/exec_policy.rs:971-1000`; `codex-rs/shell-command/src/bash.rs:106-127` (only `bash`, `zsh`, `sh` with `-c`/`-lc`).
- Absolute paths: the runtime matches with `resolve_host_executables: true`, so `/usr/bin/git` matches a `git` rule. `core/src/exec_policy.rs:397-400`. The `codex execpolicy check` CLI needs `--resolve-host-executables` for the same result.
- Parse errors FAIL OPEN. If any `.rules` file fails to parse, Codex logs a warning and uses ONLY the requirements policy. All user and project rules are dropped. `core/src/exec_policy.rs:731-742`.
- `codex exec --ignore-rules` skips user and project `.rules`; system-layer rules and requirements rules stay. `core/src/exec_policy.rs:746-756`.
- Prefix only: no regex, no "flag anywhere", no environment, no cwd condition.

### 4.1 Test: the 8 forms (real output)

Rules file `plan-research/test.rules`:

```python
prefix_rule(pattern=["git","push"], decision="forbidden", justification="No push from the agent.",
            match=[["git","push","origin","main"]], not_match=[["git","status"]])
prefix_rule(pattern=["git","commit",["--no-verify","-n"]], decision="forbidden")
```

| Command (argv given to `codex execpolicy check`) | CLI result | Runtime result (from source) |
|---|---|---|
| `git push origin main` | `{"matchedPrefix":["git","push"],"decision":"forbidden"}` | forbidden |
| `git push` | forbidden | forbidden |
| `git -C . push origin main` | `{"matchedRules":[]}` | NOT stopped (prefix breaks at `-C`) |
| `/usr/bin/git push origin main` | `{"matchedRules":[]}`; with `--resolve-host-executables`: forbidden, `"resolvedProgram":"/usr/bin/git"` | forbidden (runtime resolves host executables) |
| `bash -lc "git push origin main"` | `{"matchedRules":[]}` (the CLI does not split) | forbidden when it is the top-level wrapper and the script is plain. If the model writes `bash -lc "..."` itself, Codex sees `zsh -lc "bash -lc '...'"`: the outer split gives `["bash","-lc","git push origin main"]`, which is NOT split again, so NOT stopped. |
| `sh -c 'git push origin main'` | `{"matchedRules":[]}` | NOT stopped (nested shell, same reason) |
| `git commit --no-verify -m x` | forbidden (`["git","commit","--no-verify"]`) | forbidden |
| `git commit -n -m x` | forbidden (`["git","commit","-n"]`) | forbidden |
| extra: `git commit -m x --no-verify` | `{"matchedRules":[]}` | NOT stopped (flag after the prefix) |

Also not stopped: `env git push`, `command git push`, `xargs git push` (all `{"matchedRules":[]}`), any script with `$VAR`, `>`, `$(...)` around the command, a script file, an alias, `git -c core.hooksPath=/dev/null commit` (skips git hooks without `--no-verify`), and commands typed via `write_stdin` into an interactive shell.

### 4.2 Mitigation rules (real output, `plan-research/mitigate.rules`)

```python
prefix_rule(pattern=["git", ["-C","-c","--git-dir","--work-tree"]], decision="prompt")
prefix_rule(pattern=[["sh","bash","zsh"], ["-c","-lc"]], decision="prompt")
prefix_rule(pattern=["sudo"], decision="forbidden")
prefix_rule(pattern=["gh","pr",["create","edit","ready","merge"]], decision="prompt")
```

- `git -C . push origin main` -> prompt; `git -c core.hooksPath=/dev/null commit -m x` -> prompt; `sh -c 'git push origin main'` -> prompt; `/usr/bin/sudo rm -rf /` -> forbidden (resolved); `gh pr merge 5 --squash` -> prompt.
- Cost: the `[sh|bash|zsh] -c` rule also matches the top-level wrapper when the script is not plain (redirects, `$VAR`, globs). So it prompts on many normal commands. Not tested in a live session.

Failing `match` example, real output:

```
Error: failed to parse policy at bad.rules
Caused by:
    expected every example to match at least one rule. ... unmatched examples: ["git -C . push"]
```

---

## 5. Managed configuration

| Item | Value | Source |
|---|---|---|
| `requirements.toml` (macOS and Linux) | `/etc/codex/requirements.toml`; Windows `%ProgramData%\OpenAI\Codex\requirements.toml` | enterprise_managed-configuration.md:1127-1135 |
| Requirements precedence (low to high) | system file < cloud Agent Security < legacy `managed_config.toml` < macOS MDM `com.openai.codex:requirements_toml_base64` | enterprise_managed-configuration.md:1129-1138 |
| Defaults (not enforced) | `/etc/codex/config.toml` (lowest config layer); legacy `/etc/codex/managed_config.toml`; MDM `config_toml_base64` | config-basic.md:30-38; enterprise_managed-configuration.md:1368-1390 |
| Keys | `allowed_approval_policies`, `allowed_approvals_reviewers`, `allowed_sandbox_modes`, `allowed_permission_profiles`, `default_permissions`, `allowed_web_search_modes`, `[features]` (pin values, for example `hooks = true`), `[hooks]` + `managed_dir`, `allow_managed_hooks_only`, `[rules] prefix_rules`, `[mcp_servers.*] identity`, `additional_developer_instructions`, `auto_review.*`, `allow_login_shell`, `remote_sandbox_config` | config-reference.md:2063-2600; enterprise_managed-configuration.md:487-494, 717-735 |
| Conflict | a config value (file, profile, `-c`) that conflicts with a requirement is rejected; "users can't override" | enterprise_managed-configuration.md:416-420 |
| Hook scripts | Codex does not distribute them; use absolute paths under `managed_dir` | hooks.md:371-382 |

Minimal personal setup (one owner, one machine; needs `sudo` once):

```toml
# /etc/codex/requirements.toml  (root:wheel, 0644)
allowed_approval_policies = ["on-request"]          # blocks -a never
allowed_sandbox_modes = ["read-only", "workspace-write"]   # blocks danger-full-access and --yolo
allow_managed_hooks_only = false                    # keep plugin and user hooks too

[features]
hooks = true                                        # --disable hooks cannot turn them off

[hooks]
managed_dir = "/usr/local/libexec/codex-gates"

[[hooks.PreToolUse]]
matcher = "^(Bash|apply_patch)$"
[[hooks.PreToolUse.hooks]]
type = "command"
command = "/usr/bin/python3 /usr/local/libexec/codex-gates/pre_tool_use.py"
timeout = 30

[rules]
prefix_rules = [
  { pattern = [{ token = "git" }, { token = "push" }], decision = "prompt", justification = "Owner OK needed." },
  { pattern = [{ token = "sudo" }], decision = "forbidden", justification = "No sudo." },
]
```

Can one user pin settings that the agent cannot change? Yes, under these conditions:
- The files are root-owned and the agent has no root. `/etc/codex` is outside every writable root, so in `read-only` or `workspace-write` the sandbox blocks writes, and `sudo` fails inside the Linux sandbox (`no_new_privs`).
- On <server>, `sudo` works without a password (CLAUDE.local.md). An escalated command (approved by the owner, or by a PermissionRequest hook `allow`, or under `danger-full-access`) could rewrite `/etc/codex`. So `allowed_sandbox_modes` must exclude `danger-full-access`, and a rule must forbid `sudo`.
- The hook scripts must also be root-owned, because trust does not hash script content.
- Not documented: whether a pinned `allowed_approval_policies` also stops `codex exec --dangerously-bypass-approvals-and-sandbox`. The managed doc says `allowed_sandbox_modes` without `danger-full-access` blocks `--yolo` (enterprise_managed-configuration.md:489-494).

---

## 6. Skills, plugins, subagents

Skills:
- Locations: `$CWD/.agents/skills` up to `$REPO_ROOT/.agents/skills`; user `$HOME/.agents/skills`; admin `/etc/codex/skills`; bundled system skills. skills.md (table "Where Codex loads local skills"). Source also scans `$CODEX_HOME/skills` (`codex-rs/exec-server/src/discoverV2/capability_locations.rs:73-76`); the owner has skills in `~/.codex/skills` today. Symlinked skill folders are followed.
- Trigger: progressive disclosure. The model sees name, description and path (budget 2% of context or 8,000 chars; `skills.max_context_tokens` up to 10,000 tokens); it reads SKILL.md when it decides to. Explicit: `$skill-name` or `/skills`. `agents/openai.yaml` `policy.allow_implicit_invocation: false` stops implicit use.
- Disable: `[[skills.config]] path=... enabled=false` (or `name=`); `[skills.bundled] enabled=false`.
- Edits to `.agents/skills/*/SKILL.md` inside a writable root need escalation, because `.agents` is a protected path.

Plugins:
- Structure: root `plugin.json` (portable), optional `.codex-plugin/plugin.json` overlay, `skills/`, `mcp.json`, `hooks/hooks.json`, `assets/`. Claude-compatible manifests are accepted. plugins_build.md:556-600, 675-680.
- Marketplaces: `codex plugin marketplace add owner/repo[@ref] | URL | ./dir` (`--ref`, `--sparse`), `list`, `upgrade [name]`, `remove name`; `codex plugin add|list|remove`. plugins_build.md:182-210; `codex plugin --help`.
- Cache: installed copy at `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/` (`local` for local plugins); Codex loads the cache, not the source. Update a Git marketplace with `codex plugin marketplace upgrade`; for local plugins, update the source dir and restart. A changed bundled hook script needs a new `/hooks` review. plugins_build.md:330-349, 545-548; hooks.md:418-419.
- Per repo: `[plugins."name@marketplace"] enabled = true|false` in a trusted `.codex/config.toml`. plugins_build.md:352-375.

Subagents:
- Built-in agents `default`, `worker`, `explorer`; custom agents are TOML files in `~/.codex/agents/` or `.codex/agents/` with `name`, `description`, `developer_instructions`. subagents.md:332-345.
- Inherit: sandbox, approval, provider, MCP servers, skills (a custom agent can disable skills and features `shell_tool`, `apps`, `plugins`, `memories`, `request_permissions_tool`). Cannot override `sandbox_mode`, `approval_policy`, `mcp_servers`. subagents.md:346-405.
- `[agents] enabled = false` turns multi-agent tools off. subagents.md:366-381.
- In non-interactive runs, an action that needs a new approval fails and the error goes back to the parent. subagents.md:309-311.

---

## 7. Profiles and `codex exec`

- Profiles: `--profile name` overlays `$CODEX_HOME/name.config.toml` on `~/.codex/config.toml`. `[profiles.x]` tables and `profile = "x"` are no longer read (0.134.0+). config-advanced.md (section "Profiles").
- Order (high to low): CLI flags and `-c` > project `.codex/config.toml` (trusted) > profile file > user config > cloud defaults > `/etc/codex/config.toml` > built-in. Requirements constrain all of them. config-basic.md:30-38.
- `codex exec` flags for a setup test (from `codex exec --help`): `--json`, `-o FILE`, `-s read-only|workspace-write|danger-full-access`, `-c key=value`, `--enable/--disable FEATURE`, `--strict-config`, `-p PROFILE`, `-C DIR`, `--add-dir`, `--skip-git-repo-check`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--dangerously-bypass-hook-trust`, `--trust`, `--worktree`, `--output-schema`. Note: `codex exec --help` lists no `-a`/`--ask-for-approval`; use `-c approval_policy="on-request"` or the config.
- JSON events: `thread.started`, `turn.started`, `item.started`, `item.completed` (`command_execution` with `status` incl. `declined`; `file_change`; `agent_message`; `error`), `turn.completed` with usage. noninteractive.md:82-93; `exec/src/event_processor_with_jsonl_output.rs:167-210`.
- Hook blocks in `--json`: NO event. `HookStarted`/`HookCompleted` are dropped (`event_processor_with_jsonl_output.rs:477-479`). A blocked PreToolUse means the tool never starts, so there is no `command_execution` item. The block text appears only if the model repeats it in its next `agent_message`. To test a gate:
  1. Run without `--json` and read stderr for `hook: PreToolUse Blocked` (`event_processor_with_human_output.rs:281-290`), or
  2. Read the session rollout `~/.codex/sessions/.../rollout-*.jsonl`, or
  3. Make the hook script write its own log file. This is the most reliable check.
- Rules blocks: a forbidden command gives a `command_execution` item with status `declined` or an error item (inferred from the status mapping above; not tested live).

---

## 8. Gate mapping (11 owner gates)

Legend: H = hook (PreToolUse unless named), R = execpolicy rule, S = sandbox, A = approval policy + PermissionRequest hook, G = git hook, SV = server side (GitHub branch protection / rulesets).

| # | Gate | Best Codex mechanism | Minimal example | What still gets past on Codex |
|---|---|---|---|---|
| 1 | Secret scan before commit or push | G (pre-commit, pre-push) as the base; H on `Bash` for `git commit|push` as an early message; SV (GitHub push protection) | `.git/hooks/pre-commit` runs gitleaks; hook script parses `tool_input.command` | `--no-verify`, `-c core.hooksPath=`, any hook failure (fails open), commit via `write_stdin`; only SV is a real wall |
| 2 | No push to main or master; no merge without the owner's OK | S (workspace-write, no network: push needs escalation) + A (`on-request`; PermissionRequest hook denies `git push` to main/master and `gh pr merge` unless an owner-OK marker exists) + R (`git push` prompt, `git -C` prompt, `gh pr merge` prompt) + SV (branch protection: no direct push to main, required review) | `prefix_rule(pattern=["gh","pr","merge"], decision="prompt")`; PermissionRequest hook returns `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"deny","message":"Owner OK needed"}}}` | Owner presses "approve" by mistake; network turned on in config; `danger-full-access`; a GitHub MCP tool if one is configured (needs an MCP matcher); only SV stops it fully |
| 3 | No `--no-verify` | H (regex on the whole command string for `--no-verify`, `-n` after `commit`, `core.hooksPath`) + R (`git commit --no-verify/-n` forbidden) | rule from section 4.1 | flag after other args (rule misses it, hook catches it); `git -c core.hooksPath=/dev/null`; env `GIT_CONFIG_*`; scripts; hook failure |
| 4 | PR body template check before `gh pr create/edit/ready` | H on `Bash` (parse `--body`/`--body-file`, check Mermaid, Evidence, Door, Blast Radius, sessions block); R `prompt` as a backstop; S (network off means `gh` needs escalation, so PermissionRequest sees it too) | PreToolUse deny with reason listing missing sections | `gh api` calls, `curl` to the API, a GitHub MCP tool, body from a file the hook cannot read; hook failure |
| 5 | Other `gh` writes ask first | A + R `prompt` on `gh` write verbs; S (no network) | `prefix_rule(pattern=["gh", ["issue","release","repo","api","secret","label"]], decision="prompt")` | `gh api` with GET-looking args that write; `curl`; with network on and `on-request`, a sandboxed `gh` call runs without a prompt unless a rule matches |
| 6 | No sudo | S (Linux `no_new_privs`; macOS needs a password TTY) + R `forbidden` + requirements `allowed_sandbox_modes` without `danger-full-access` | `prefix_rule(pattern=["sudo"], decision="forbidden")` | an escalated command (outside the sandbox) on <server>, where sudo needs no password, if the rule is bypassed (`env sudo`, script, nested shell) |
| 7 | No destructive commands (`rm -rf` of data, `git reset --hard` with changes, `docker volume rm`) | S (writes only in the workspace; `.git` read-only) + R `prompt`/`forbidden` for `rm -rf`, `git reset --hard`, `git clean -fdx`, `docker volume rm`, `docker system prune` + H for context checks ("has uncommitted changes") | `prefix_rule(pattern=["docker","volume","rm"], decision="forbidden")` | destruction inside the workspace (the sandbox allows it), `find -delete`, Python scripts, flags in another order (`rm -fr`), docker socket access when network/escalation is on |
| 8 | Audit before a package install | R `prompt` on `npm|pnpm|yarn|pip|uv add|brew install`; S (no network: install fails or needs escalation, so PermissionRequest hook sees it) + H for the audit message | `prefix_rule(pattern=[["npm","pnpm","yarn"], ["install","add","i"]], decision="prompt")` | `uv run --with x`, `npx pkg`, `pipx run`, installs inside scripts; with `network_access = true` nothing triggers escalation |
| 9 | Load a skill before an edit of AGENTS.md or SKILL.md | H on `apply_patch` (parse `*** Update File:` paths; deny unless a session marker shows the skill was loaded, for example from PostToolUse on a `cat .../SKILL.md` read) + S (`.agents/` is protected, so SKILL.md under `.agents/skills` needs escalation) | PreToolUse deny: "Load writing-for-agents first" | edits by shell (`cat >`, `sed -i`, `python`) of AGENTS.md (not a protected path); Codex has no "skill was loaded" event, so the marker is a heuristic |
| 10 | No edit on main or master (worktree first) | H on `apply_patch` and `Bash` (run `git -C <cwd> branch --show-current`; deny on main/master) + `codex exec --worktree` / `codex --worktree` for automation | hook denies with "Create a branch or worktree first" | shell writes not detected by the hook parser; hook failure; `write_stdin` |
| 11 | "ship" skill before `gh pr ready` | H on `Bash` (`gh pr ready`: deny unless a ship-evidence file exists for the branch) + R `prompt` + A | `prefix_rule(pattern=["gh","pr","ready"], decision="prompt")` | `gh api` GraphQL `markPullRequestReadyForReview`; hook failure; fake evidence file (the agent can write it) |

Cross-cutting rules for all gates:
- Hooks fail open. Every gate hook must exit 0 with valid JSON, a non-empty reason, and no extra fields. For the high-risk gates (2, 3, 6, 7), wrap the whole script in a catch-all. On an internal error, the catch-all returns a deny.
- Put the gate hooks in a managed layer (`/etc/codex/hooks.json` or `requirements.toml`) so trust does not drift and a plugin update does not silently disable them.
- Pin `[features] hooks = true` and the sandbox and approval allowlists in `/etc/codex/requirements.toml`.
- Keep the sandbox at `workspace-write` with network off. Most gates then reduce to "escalation needed", and escalation goes to the human or to the PermissionRequest hook.

---

## 9. Differences from Claude Code that matter for one shared rule set

Claude Code has, Codex lacks (Claude side from `plan-research/docs/hooks.md`, the Claude Code hooks page):

| Claude feature | Codex 0.170.0 |
|---|---|
| `onFailure: "block"` (block the action when the hook fails) | None. All errors fail open (section 2.6). |
| `permissionDecision: "ask"` in PreToolUse | Parsed but unsupported: the hook run is marked failed AND THE TOOL RUNS. A shared router that returns `ask` makes a gate a no-op on Codex. |
| `permissionDecision: "allow"` without `updatedInput` | Marked failed (tool runs anyway). |
| `if` field (permission-rule filter such as `Bash(git push*)`) | None. Only regex `matcher` on the tool name; filter inside the script. |
| `prompt`, `agent`, `http` handler types | `prompt`/`agent` parsed and skipped; `http` not supported. Only `command` and `mcp_tool`. hooks.md:198-199 |
| Events: PostToolUseFailure, PermissionDenied, Notification, InstructionsLoaded, ConfigChange, CwdChanged, FileChanged, WorktreeCreate/Remove, TaskCreated/Completed, TeammateIdle, Elicitation, UserPromptExpansion, PostToolBatch | None of these. |
| Tool names `Edit`, `Write`, `Read`, `Grep`, `Glob` | Edits are one tool, `apply_patch` (`Edit`/`Write` are matcher aliases only; input is patch text, not `file_path`). Reads are shell commands (`Bash`). |
| `tool_input.file_path`, `old_string`, `new_string` | Not present. Parse the patch text. |
| Unknown output fields tolerated | Codex rejects unknown fields (`deny_unknown_fields`), so the hook run fails and the tool runs. |
| `settings.json` `permissions.deny` with path rules (`Edit(path)`, `Read(path)`) | No per-path edit rules. Rules are command prefixes only. Use the sandbox, protected paths, permission profiles (`deny_read`), or a hook. |
| `@path` imports in CLAUDE.md | Not supported in AGENTS.md. |
| Hooks run without a trust step (settings are trusted by file location) | Every non-managed hook needs `/hooks` trust; changed declarations are skipped. |

Codex has, Claude Code lacks or does differently:

| Codex feature | Note |
|---|---|
| OS sandbox on by default (`workspace-write`, network off, `.git`/`.codex`/`.agents` read-only) | The strongest Codex control. Claude Code sandboxing is opt-in. |
| execpolicy rules with shell splitting and host-executable resolution, inline `match`/`not_match` tests, `codex execpolicy check` | Testable offline. |
| `requirements.toml` as a plain local file (`/etc/codex/requirements.toml`) with `[hooks]`, `[rules]`, `[features]`, `allow_managed_hooks_only`, `additional_developer_instructions` | Claude has `managed-settings.json` as the equivalent. |
| PermissionRequest hook that can allow or deny the escalation itself | Claude also has PermissionRequest; the trigger set differs (Codex: sandbox escalation, network approval). |
| `updatedInput` rewrite in PreToolUse | Both have it. |
| PreModelRequest, PostModelRequest, Interrupt events; `async` background hooks; `additionalContextLimit` | |
| Hook trust by hash; plugin content hash | Change detection, but fail-open on change. |
| `approvals_reviewer = "auto_review"` (reviewer agent, fails closed) | Similar to Claude auto mode, different contract. |

Practical rule for a shared router: with `--agent codex`, emit only the Codex-supported subset. That is a deny with a non-empty reason, or exit 2 with stderr. Never emit `ask` or extra keys. On Codex, turn each "ask" decision into a deny with "ask the owner" text.

---

## 10. Not documented or could not confirm

1. Unknown JSON field behavior was not run live. The conclusion (fail open) comes from `deny_unknown_fields` on structs that also use `#[serde(flatten)]`; serde documents that combination as not fully supported. A one-line test in a live session would settle it.
2. Whether spawned subagents load the same global and project AGENTS.md: inferred from `thread_manager.rs:2236`, not documented.
3. Whether `/etc/codex/rules/*.rules` loads when `/etc/codex/config.toml` does not exist (the System layer may need the file to exist). Not documented; code reads `layer.config_folder()` for active layers only.
4. Whether `allowed_approval_policies` / `allowed_sandbox_modes` in a local `/etc/codex/requirements.toml` make `codex exec --dangerously-bypass-approvals-and-sandbox` fail at start or only clamp it. The doc says `--yolo` is blocked; no exec-specific statement.
5. The exact `codex exec --json` output for an execpolicy `forbidden` command (status `declined` vs an `error` item). Not tested live.
6. Whether hook commands run outside the sandbox: inferred from the plain process spawn in `command_runner.rs`; not documented.
7. Which built-in tools other than `write_stdin` and code-mode `wait` opt out of hooks in practice (any tool with a `Custom` payload, for example a freeform tool). Only the default code path was read, not every handler.
8. `trust_level = "untrusted"` turns off project AGENTS.md (source), but the docs say only "This also disables project-local configuration".
9. `codex execpolicy check` prints an error for a bad rules file; its process exit code was not captured.
