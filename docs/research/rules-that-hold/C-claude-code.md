# Claude Code enforcement capability map (v2.1.325)

Scope: what makes a rule hold in every session, subagent, headless run and project. Sources: official docs at code.claude.com, fetched 2026-11-20 as raw `.md` pages. Each claim carries its URL. "Not documented" means the fetched pages do not say it. Installed version checked: `claude --version` prints `2.1.325 (Claude Code)`.

Short URL keys used below (all under `https://code.claude.com/docs/en/`):
MEM=memory, CTX=context-window, HK=hooks, HG=hooks-guide, PRM=permissions, PMD=permission-modes, SBX=sandboxing, MGD=managed-settings, SET=settings, SREF=settings-reference, SUB=sub-agents, SKL=skills, PLD=plugins/loading, PCO=plugins/components, PIN=plugins/install, PCLI=plugins/cli-reference, PMK=plugins/create-marketplace, HL=headless, CLI=cli-reference, EVAL=plugin-evals, DBG=debug-your-config, WT=worktrees, OS=output-styles, MODS=plugins/mods/admin, FO=features-overview, CMD=commands, ENV=env-vars, MC=model-config.

Key finding up front: the docs say CLAUDE.md is "context, not enforced configuration" (MEM#write-effective-instructions), and "Settings rules are enforced by the client regardless of what Claude decides to do" (MEM#deploy-organization-wide-claude-md). Enforcement comes from permissions, hooks, sandbox and managed settings. Instructions only shape behavior.

---

## 1. Instruction files

### 1.1 Locations and load order (broad to specific; later = read last)
Source: https://code.claude.com/docs/en/memory#choose-where-to-put-claude-md-files

| Scope | Location | Notes |
|---|---|---|
| Managed policy | macOS `/Library/Application Support/ClaudeCode/CLAUDE.md`; Linux/WSL `/etc/claude-code/CLAUDE.md` | Cannot be excluded by `claudeMdExcludes` (MEM#exclude-specific-claude-md-files). Also `claudeMd` key inside managed settings, honored only in managed/policy settings (MEM#deploy-organization-wide-claude-md) |
| User | `~/.claude/CLAUDE.md` | All projects |
| User rules | `~/.claude/rules/*.md` | Loaded before project rules (MEM#user-level-rules) |
| Project | `./CLAUDE.md` or `./.claude/CLAUDE.md` | |
| Project rules | `./.claude/rules/**/*.md` (recursive) | Without `paths`: loaded at launch, same priority as `.claude/CLAUDE.md` (MEM#set-up-rules) |
| Local | `./CLAUDE.local.md` | Appended after CLAUDE.md in the same directory |
| AGENTS.md | `AGENTS.md`, `.claude/AGENTS.md` | Read only when no CLAUDE.md/CLAUDE.local.md exists in cwd or above, by default. Requires v2.1.277+ (MEM#agents-md) |

- Ancestors: CLAUDE.md and CLAUDE.local.md in cwd and every directory above load at launch, root first (MEM#how-claude-md-files-load).
- Nested (subdirectories): load on demand when Claude reads, writes or edits a file in that subdirectory, including a Bash `cat`/`head` on one file (MEM#how-claude-md-files-load).
- Path-scoped rules: frontmatter `paths:` (YAML list or comma string). Loaded when Read/Write/Edit (or a Bash read such as `cat`) touches a matching file. `paths` is the only field read (MEM#rule-frontmatter-reference).
  ```markdown
  ---
  paths:
    - "src/api/**/*.ts"
  ---
  # API rules
  - Validate all input
  ```
- `@imports`: relative to the importing file, absolute allowed, max depth four hops. External imports (outside cwd) in project files trigger a one-time approval dialog; user-scope files import without the dialog. Imports inside code spans/fences are skipped (MEM#import-additional-files).
- Symlinked rules: a symlink in `.claude/rules/` whose target is outside cwd counts as an external import; after approval only rules without `paths` load. Put shared rules in `~/.claude/rules/` to avoid approval (MEM#share-rules-across-projects-with-symlinks).
- AGENTS.md mode setting: `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles` = `claude-md-or-agents-md` (default) / `claude-md-and-agents-md` / `claude-md` / `managed-only`. Read only from `~/.claude/settings.json`, `--settings`, or managed settings (MEM#choose-which-instruction-files-load).
  ```json
  {"pluginConfigs":{"cc-plugin-agents-md@builtin":{"options":{"instructionFiles":"claude-md-and-agents-md"}}}}
  ```
- HTML block comments are stripped before injection (MEM#how-claude-md-files-load).
- `--add-dir` directories: CLAUDE.md not loaded unless `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` (MEM#load-from-additional-directories).
- `--setting-sources` without `project` skips project rules; before v2.1.211 on-demand rules still loaded (MEM#set-up-rules).

### 1.2 Delivery and strength
- CLAUDE.md is delivered as a user message after the system prompt; no guarantee of strict compliance (MEM#claude-isnt-following-my-claude-md).
- For system-prompt level: `--append-system-prompt` / `--append-system-prompt-file` (MEM#claude-isnt-following-my-claude-md, CLI).
- Must-run-at-a-point rules: docs say write them as a hook (MEM#claude-isnt-following-my-claude-md).
- Built-in git instructions can compete with your commit/PR rules: turn off with `includeGitInstructions: false` (MEM#claude-isnt-following-my-claude-md; SREF#includegitinstructions).

### 1.3 Size guidance
- Target under 200 lines per CLAUDE.md; longer reduces adherence. Imports do not reduce context cost (MEM#write-effective-instructions).
- Files over 4 MiB are skipped. Warning at startup and in `/status` when a file is over the recommended length or the sum passes a combined limit (MEM#my-claude-md-is-too-large).
- On-demand files (nested CLAUDE.md, subdirectory rules, path-scoped rules) are truncated over a per-file limit: 40,000 characters on 200K context; 200,000 (Opus/Sonnet 4.6) or 150,000 (later models) on 1M. Limit applies since v2.1.309 (MEM#claude-ignores-the-end-of-my-subdirectory-claude-md).

### 1.4 After compaction (CTX#what-survives-compaction)
| Content | After compaction |
|---|---|
| Project-root CLAUDE.md and unscoped rules | Re-injected from disk |
| Rules with `paths:` | Reload on demand only (summarized away until a matching file is touched) |
| Nested CLAUDE.md | Reload on demand only |
| Invoked skill bodies | Re-injected, cap 5,000 tokens per skill, 25,000 total, oldest dropped |
| Skill descriptions | Rebuilt (v2.1.304+) |
| Context added by hooks earlier | Summarized |
| SessionStart hooks matching `compact` | Run again; output added |
- Docs: "If a rule must persist across compaction, drop the `paths:` frontmatter or move it to the project-root CLAUDE.md" (CTX#what-survives-compaction).

### 1.5 Subagents and instructions (SUB#what-loads-at-startup)
- A non-fork subagent loads every CLAUDE.md level the main conversation loads (user, project, rules, local, managed, AGENTS.md).
- Exceptions: built-in `Explore` and `Plan` skip CLAUDE.md and git status. A subagent with `omitClaudeMd: true` loads only managed policy files (none if the definition comes from managed settings). v2.1.271+.
- Output style and auto memory do not reach a non-fork subagent (SUB#what-loads-at-startup; OS#how-output-styles-work).
- Consequence for "every session": a rule that must reach Explore/Plan needs a `SubagentStart` hook `additionalContext`, a managed CLAUDE.md does not help there (Explore/Plan skip all CLAUDE.md). This is an inference from SUB#what-loads-at-startup + HK#subagentstart.

### 1.6 How to see what loaded
- `/context all` lists "Memory files" loaded at launch; nested files do not appear there, a `Loaded` line appears in the terminal when they load (MEM#claude-isnt-following-my-claude-md).
- `/memory` lists and opens files (MEM#view-and-edit-with-memory).
- `InstructionsLoaded` hook: fires per file with `file_path`, `memory_type` (User/Project/Local/Managed), `load_reason` (`session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact`), `globs`, `trigger_file_path`, `parent_file_path`. Matcher filters `load_reason`. Cannot block; output discarded. Does not fire for AGENTS.md read directly via the setting (HK#instructionsloaded; MEM#where-agents-md-differs-from-claude-md).
- `/doctor prompt-audit` checks instruction files for conflicts (v2.1.283+) (MEM#audit-your-instruction-files).

---

## 2. Hooks (complete)

### 2.1 Events (HK#hook-lifecycle, HK#exit-code-2-behavior-per-event)
| Event | Fires | Exit 2 blocks? | Matcher field |
|---|---|---|---|
| SessionStart | Session begins/resumes | No (stderr to user) | `startup`,`resume`,`clear`,`compact`,`fork` |
| Setup | `--init-only`, or `--init`/`--maintenance` with `-p` | No | `init`,`maintenance` |
| UserPromptSubmit | Prompt submitted; also scheduled tasks, background subagent reports, cross-session messages | Yes, blocks prompt | none |
| UserPromptExpansion | Typed command expands | Yes | command name |
| PreToolUse | Before tool call (all tools except EndConversation) | Yes | tool name |
| PermissionRequest | Permission decision needed | No (use JSON `decision`) | tool name |
| PermissionDenied | Auto mode denial | No (`retry` only) | tool name |
| PostToolUse | Tool succeeded | No (stderr to Claude) | tool name |
| PostToolUseFailure | Tool failed | No | tool name |
| PostToolBatch | After a parallel batch, before next model call | Yes, stops loop | none |
| Notification | Notification | No | notification type |
| MessageDisplay | Text displayed | No (display only) | none |
| SubagentStart | Subagent spawned/resumed | No (stderr to user) | agent type |
| SubagentStop | Subagent finished | Yes, keeps it running | agent type |
| TaskCreated | TaskCreate | Yes, rolls back | none |
| TaskCompleted | Task completed | Yes | none |
| Stop | Main agent finishes responding (not on user interrupt) | Yes, continues | none |
| StopFailure | Turn ends on API error | No, output ignored | error type |
| TeammateIdle | Agent team teammate idle | Yes | none |
| InstructionsLoaded | CLAUDE.md/rules loaded | No | load reason |
| ConfigChange | Settings/skill file changes mid-session | Yes (not `policy_settings`) | `user_settings`,`project_settings`,`local_settings`,`policy_settings`,`skills` |
| CwdChanged | cwd changes | No | none |
| DirectoryAdded | `/add-dir` | No | `slash_command`,`register_repo_root` |
| FileChanged | Watched file changes | No | literal filenames |
| WorktreeCreate | Worktree creation | Any non-zero fails creation | none |
| WorktreeRemove | Worktree removal | Non-zero fails removal | none |
| PreCompact | Before compaction | Yes | `manual`,`auto` |
| PostCompact | After compaction | No | `manual`,`auto` |
| PreModelSwitch | Before requested model switch | Yes | model name |
| PostModelSwitch | After model changes | No | model name |
| Elicitation | MCP asks user input | Yes (decline) | server name |
| ElicitationResult | After user answers elicitation | Yes | server name |
| SessionEnd | Session ends | No | `clear`,`resume`,`logout`,`prompt_input_exit`,`other` |

### 2.2 Matcher syntax (HK#matcher-patterns)
- `"*"`, `""`, omitted: match all.
- Only letters, digits, `_`, `-`, space, `,`, `|`: exact string or list (`Edit|Write`, `Edit, Write`).
- Any other character: unanchored JavaScript regex (`Edit.*` also matches `NotebookEdit`; use `^Edit$`).
- `FileChanged`, `StopFailure`: narrower exact set (letters, digits, `_`, `|`).
- MCP: `mcp__<server>__.*` (the `.*` is required). Plugin MCP tools: `mcp__plugin_<plugin>_<server>__<tool>`.
- A `Bash` matcher on PreToolUse/PermissionRequest also runs on Monitor commands, but `allow`/`updatedInput` have no effect on them (v2.1.314+) (HK#match-monitor-commands).
- A `matcher` on an event without matcher support is silently ignored. A matcher written as a JSON array makes the hook never fire (DBG#check-common-causes).

### 2.3 Handler types and fields (HK#hook-handler-fields)
Common: `type` (`command`|`http`|`mcp_tool`|`prompt`|`agent`), `if`, `timeout` (s), `statusMessage`, `once` (honored only in skill frontmatter).
- command: `command`, `args` (exec form, no shell), `async`, `asyncRewake`, `shell` (`bash`|`powershell`), `onFailure` (`continue`|`block`, v2.1.295+).
- http: `url`, `headers`, `allowedEnvVars`, `onFailure`.
- mcp_tool: `server` (plugin servers: `plugin:<plugin>:<server>`), `tool`, `input` (`${tool_input.file_path}` substitution), `onFailure` (v2.1.328+ for mcp_tool, so not in 2.1.325). Not available at launch SessionStart or Setup.
- prompt: `prompt` (`$ARGUMENTS`), `model`, `timeout`, `continueOnBlock`.
- agent (experimental): `prompt`, `model`, `timeout`; up to 50 turns.
- Default timeouts: 600 s command/http/mcp_tool; 30 s prompt; 60 s agent; 30 s for command/http/mcp_tool on UserPromptSubmit, PreModelSwitch, PostModelSwitch; 10 s on MessageDisplay; SessionEnd shares a 1.5 s budget (raised to max 60 s by a longer per-hook timeout) (HK#common-fields).
- Event support: all five types on PermissionDenied, PostToolBatch, PostToolUse, PostToolUseFailure, PreToolUse, Stop, SubagentStop, TaskCompleted, TaskCreated, TeammateIdle, UserPromptExpansion, UserPromptSubmit. PermissionRequest: no `agent`. SessionStart: only `command`, `mcp_tool`. Setup: only `command`. Others: command/http/mcp_tool only (HK#prompt-based-hooks).

Exec form example (preferred with path placeholders):
```json
{"type":"command","command":"node","args":["${CLAUDE_PLUGIN_ROOT}/scripts/check.js"],"onFailure":"block"}
```
Placeholders: `${CLAUDE_PROJECT_DIR}` (stays at the session start root, even inside a worktree; read `cwd` from input instead), `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}` (HK#reference-scripts-by-path).

### 2.4 Exit codes and JSON (HK#exit-code-output)
| Stdout | Exit 0 | Exit 2 | Other |
|---|---|---|---|
| Valid JSON | fields apply | blocks; PreToolUse stays blocked even with `allow` | fields alone decide (unless `onFailure: block`, then failure) |
| Bad JSON | non-blocking error | blocks, stderr = reason | non-blocking error |
| Text/none | success | blocks, stderr = reason | non-blocking error |
- Exit 1 is NOT a block. Docs: "If your hook is meant to enforce a policy, use `exit 2`" (HK#other-exit-codes).
- Stdout must be one JSON object only; shell-profile echo breaks it silently (HG#shell-profile-output-before-the-json).
- Fields at wrong level are ignored silently; debug log shows `Hook JSON output had unrecognized keys` (HG#fields-at-the-wrong-level).
- Universal fields: `continue`, `stopReason`, `suppressOutput` (no effect), `systemMessage`, `terminalSequence` (HK#json-output).
- PreToolUse (`hookSpecificOutput`): `permissionDecision` `allow`|`deny`|`ask`|`defer`; `permissionDecisionReason`; `updatedInput` (replaces whole input; permission rules are evaluated against the new input); `additionalContext`. `defer` only in `-p` with a single tool call. Deny and ask rules are still evaluated whatever the hook returns (HK#pretooluse-decision-control).
  ```json
  {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"git push is gated"}}
  ```
- `updatedInput` without decision in auto mode: can be denied with `a hook changed this call's input after auto mode reviewed it` (HK#pretooluse-updatedinput-in-auto-mode).
- Several hooks return `updatedInput` for the same tool: no merge, no guarantee which one wins (HG#limitations).
- UserPromptSubmit: `decision: "block"`, `reason` (shown to user only), `additionalContext`, `sessionTitle`, `suppressOriginalPrompt`. Plain stdout on exit 0 becomes context. Timeout: hook canceled, prompt goes through without context unless `onFailure: block` (HK#userpromptsubmit).
- Stop/SubagentStop: `decision: "block"` + `reason` (required) continues the turn; `hookSpecificOutput.additionalContext` continues as non-error feedback. Input has `stop_hook_active`, `last_assistant_message`, `background_tasks`, `session_crons`. Cap: 8 consecutive continuations without a tool call, then the block is overridden; `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` changes it, `0` disables (HK#stop; ENV).
- SubagentStart: `additionalContext` injected into the subagent; cannot block (HK#subagentstart).
- PostToolUse: `decision: "block"`, `updatedToolOutput`, `additionalContext`; cannot undo (HK#decision-control).
- PermissionRequest: `decision.behavior` allow/deny, `updatedInput`, permission updates. In `-p` they run outside `dontAsk` (HG#limitations).
- ConfigChange: block keeps new settings out of the running session; no message is shown (HK#configchange-decision-control).
- `additionalContext`, `systemMessage`, plain stdout: capped at 10,000 characters each; over the cap a file path plus 2,000-char preview replaces it; no setting raises it (HK#json-output).
- Text framed as system commands in `additionalContext` can trigger prompt-injection defenses; write factual statements (HK#add-context-for-claude).

### 2.5 Failure, timeouts, parallelism
- Failed/timed-out hook: action goes ahead (fail-open), unless `onFailure: "block"` on command/http (v2.1.295+) (HK#block-the-action-when-a-hook-fails). No effect on Stop/SubagentStop/TaskCompleted/TeammateIdle or async hooks.
- On PreToolUse a timed-out hook does not block; "don't count on a stalled hook to act as a gate" (HK#timeouts).
- All matching hooks run in parallel and to completion; a `deny` does not stop sibling hooks (HG#combine-results-from-multiple-hooks). Max 12 prompt/agent hooks at once (HK#hook-handler-fields).
- Disagreement: PreToolUse precedence `deny` > `defer` > `ask` > `allow`; all `additionalContext` values are delivered (HK#pretooluse-decision-control).
- Same handler in several settings files runs once; plugin/skill copies stay separate (HK#hook-handler-fields).
- Background process in a hook: print the decision first and redirect the child's stdio, or the call is blocked with `stdio went quiet` (HK#hooks-that-start-a-background-process).
- `async: true`: cannot block; output delivered next turn; killed at `-p` teardown. `asyncRewake: true`: exit 2 wakes Claude (HK#run-hooks-in-the-background).

### 2.6 Where hooks can live and where they apply (HK#hook-locations)
| Location | Scope | Inside subagents | In `claude -p` |
|---|---|---|---|
| `~/.claude/settings.json` | all projects | yes (HK#hook-locations) | yes; skipped with `--bare` (HL#start-faster-with-bare-mode) |
| `.claude/settings.json` | project | yes | yes, even untrusted folder (HK#workspace-trust) |
| `.claude/settings.local.json` | project, personal | yes | yes |
| Managed settings | machine | yes | yes, also with `--safe-mode` (CLI) |
| Plugin `hooks/hooks.json` (or `hooks` manifest key) | where plugin enabled | yes | yes if installed; `--bare` skips installed plugins (CLI `--bare`) |
| Skill frontmatter `hooks:` | rest of session after invoke | not documented beyond "rest of the session" | yes; project skill hooks register even in untrusted `-p` (HK#hooks-in-skills-and-agents) |
| Subagent frontmatter `hooks:` | while that subagent runs | n/a | project agents: NOT in `-p` (needs folder trust); user agents and `--agents` run (SUB#hooks-in-subagent-frontmatter) |
- Hooks merge across levels; user/project cannot remove managed hooks (HK#hook-locations).
- Plugin agents ignore `hooks`, `mcpServers`, `permissionMode`, `initialPrompt` (PCO#frontmatter-fields-in-plugin-agents).
- Interactive: hooks from every settings file, including user settings, wait for workspace trust acceptance (HK#workspace-trust).
- Hooks are read from cwd `.claude/` only, no parent fallback (PRM#where-output-styles-hooks-and-local-settings-load-from).
- Skill hook limits: per source 1,024 hooks and 16,384 matcher characters (v2.1.304+) (HK#limits-on-skill-hooks).
- Two plugins with the same manifest name: only one registers its hooks (PLD#hooks-when-two-enabled-plugins-share-a-name).

### 2.7 Hooks vs permission modes (HG#hooks-and-permission-modes)
- A hook `deny` holds in every mode, including `bypassPermissions` and `dontAsk`; PreToolUse fires before any mode check.
- A hook `allow` does not bypass deny/ask rules, and in plan mode has no effect on edits.
- Exit 2 blocks before allow rules are evaluated (PRM#precedence-among-rules-hooks-and-mods).
- Mods caveat: without managed settings, `managed-mcp.json`, or a Team/Enterprise `/login`, an installed mod can approve a call a PreToolUse hook blocked and some calls a deny rule refuses. With managed settings present, the built-in guard `sec-default@builtin` loads and keeps hook blocks and deny rules (PRM#precedence-among-rules-hooks-and-mods; MODS#know-what-happens-by-default). A mod's own `$.fs`/`$.process` calls skip rules and hooks even with the guard (MODS).

---

## 3. The `if` field
Source: HK#common-fields, HK#how-if-patterns-match-bash-commands, HG#filter-by-tool-name-and-arguments-with-the-if-field.
- Syntax: one permission rule, `Tool(specifier)`. No `&&`, `||` or lists; use one handler per condition.
- Events: only PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest, PermissionDenied. On any other event a hook with `if` never runs.
- Effect: the handler process spawns only when the tool call matches, so no process start for other calls.
- Bash matching: leading `VAR=value` stripped; each subcommand of `&&`, `;`, `|` checked; commands inside `$()` and backticks checked; a pattern longer than the command name (e.g. `Bash(git push *)`) runs on any `$()`, backtick or `$VAR`; unsplittable input runs the hook anyway. Docs: best-effort, "use the permission system rather than a hook to enforce a hard allow or deny".
- File tools: `Edit(src/**)` matches only `<cwd>/src`; use `Edit(**/src/**)` for any depth.
- Monitor: name `Monitor(tail *)` in `if` when the matcher includes Monitor.

Examples:
```json
{"hooks":{"PreToolUse":[
  {"matcher":"Bash","hooks":[{"type":"command","if":"Bash(git push *)","command":"node","args":["${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-push.js"],"onFailure":"block"}]},
  {"matcher":"Edit|Write","hooks":[{"type":"command","if":"Edit(**/AGENTS.md)","command":"node","args":["${CLAUDE_PROJECT_DIR}/.claude/hooks/need-skill.js"]}]}
]}}
```
Note: `Edit(...)` rules apply to all built-in file-editing tools (PRM#what-read-and-edit-rules-cover); whether an `if: "Edit(...)"` matches a `Write` call is not documented explicitly. Safer: one handler with `Edit(**/AGENTS.md)` and one with `Write(**/AGENTS.md)`. Note `Write(path)` permission rules do not match (PRM#write-path-glob-path-and-grep-path-rules-dont-match), and whether that also holds for `if` is not documented, so test both.

---

## 4. Prompt hooks and agent hooks
Source: HK#prompt-based-hooks, HK#agent-based-hooks, HG#prompt-based-hooks.
- Input: your `prompt` text with `$ARGUMENTS` replaced by the hook input JSON (appended if absent). For Stop that JSON includes `last_assistant_message`, `stop_hook_active`; for PreToolUse `tool_name`, `tool_input` (HK#stop-input, HK#common-input-fields). Whether a prompt hook sees the whole transcript is not documented; it sees `transcript_path` as a string only.
- Model: default is the "background functionality" model (`ANTHROPIC_DEFAULT_HAIKU_MODEL` controls it per MC); override with `model`.
- Output schema: `{"ok": true|false, "reason": "...", "impossible": true|false}`.
- Verdict effect on `ok:false`: Stop/SubagentStop continue with `reason` as next instruction (unless `impossible:true`); PreToolUse denies the call and by default ends the turn, `continueOnBlock: true` returns the reason as a tool error instead; PostToolUse ends turn by default; UserPromptSubmit/UserPromptExpansion/PostToolBatch end the turn; PermissionRequest: no effect; PermissionDenied: discarded.
- Agent hooks: experimental, spawn a subagent with Read/Grep/Glob etc., up to 50 turns, default timeout 60 s, act like `continueOnBlock: true`, no `impossible`.
- Cost/latency: every prompt/agent hook is a model call; default timeouts 30 s / 60 s; max 12 run at once. Exact cost per call: not documented.
- Limits: not supported on SessionStart, Setup, SubagentStart, ConfigChange, InstructionsLoaded and other observational events. Stop hook loop cap of 8 applies.
- `/goal` is a built-in session-scoped prompt Stop hook; it cannot run under `allowManagedHooksOnly` (HK#stop; SREF#allowmanagedhooksonly).
Example (reply-style judge at Stop):
```json
{"hooks":{"Stop":[{"hooks":[{"type":"prompt","timeout":30,
 "prompt":"Judge the reply in $ARGUMENTS (field last_assistant_message). Rules: lead with the answer, at most 60 words outside code blocks, no U+2014. If stop_hook_active is true, return {\"ok\": true}. Else return {\"ok\": false, \"reason\": \"<rule broken>\"} on a breach, or {\"ok\": true}."}]}]}}
```

---

## 5. Permissions
Source: PRM, PMD, SREF.
- Keys: `permissions.allow`, `permissions.ask`, `permissions.deny`, `permissions.defaultMode`, `permissions.additionalDirectories`, `permissions.disableBypassPermissionsMode: "disable"`, `permissions.disableAutoMode: "disable"`, `permissions.denyInsteadOfPrompting`, `permissions.blockReadsOutsideWorkingDirectories`, `permissions.blockWritesOutsideWorkingDirectories` (v2.1.314+) (PRM#permission-modes, PRM#block-file-tool-reads-and-writes-outside-the-working-directories).
- Order: deny, then ask, then allow; first match wins; specificity does not matter (PRM#manage-permissions). Deny at any level cannot be allowed by another level, including `--allowedTools` (PRM#settings-precedence).
- Bare tool deny (`"Bash"`, `"mcp__*"`, `"*"`) removes the tool from context (PRM#manage-permissions, PRM#tool-name-wildcards).
- Bash: `Bash(npm run *)`; `*` matches spaces; trailing ` *` also matches bare command; `:*` suffix equivalent. Compound commands split on `&&`,`||`,`;`,`|`,`|&`,`&`, newline; deny/ask match any subcommand incl. subshells and `$()`. Wrappers stripped: `timeout`,`time`,`nice`,`nohup`,`stdbuf`,`command`,`builtin`,`noglob`, bare `xargs` (PRM#bash).
- Documented Bash limits (PRM#what-a-bash-rule-doesnt-match): `Bash(git push *)` does not stop `git -C . push ...` or `git -c push.default=current push`; `Bash(rm *)` does not stop `/bin/rm` or `bash -c 'rm ...'`. Docs: "isn't a security boundary around the program"; use sandbox or a PreToolUse hook.
- Parameter rules (deny/ask only): `Agent(isolation:worktree)`, `Bash(run_in_background:true)`, `Bash(dangerouslyDisableSandbox:true)`. Not on primary fields (`command`, `file_path`, `url`) (PRM#match-by-input-parameter).
- Read/Edit: gitignore syntax; `//abs`, `~/home`, `/settings-relative`, `./cwd-relative`. `/path` in user settings anchors at `~/.claude/`, so use `//` or `~/` in user settings (PRM#where-a-pattern-anchors). `Edit` rules cover all edit tools; `Write(path)`, `Glob(path)`, `Grep(path)` rules don't match (use `Edit`/`Read`). A `Read` deny also blocks Edit/Write on the path (v2.1.228+ for Write). Read/Edit rules apply to Bash only for recognized file commands and redirects, not to scripts that open files (PRM#read-and-edit).
- WebFetch: `WebFetch(domain:example.com)`, `*.example.com`; wildcards v2.1.172+ (PRM#webfetch).
- MCP: `mcp__server`, `mcp__server__*`, `mcp__server__tool`; plugin servers `mcp__plugin_<plugin>_<server>__*`. `mcp__` rules with parentheses in settings files are skipped (PRM#mcp, PRM#match-by-input-parameter).
- Agent: `Agent(Explore)` deny disables a subagent (PRM#agent-subagents).
- Modes (PMD#available-modes): `default` (Manual), `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`.
- Still enforced in `bypassPermissions` (PMD#actions-no-mode-auto-approves, PMD#available-modes): deny rules; explicit ask rules; `AskUserQuestion` and `requiresUserInteraction` MCP tools; critical-path `rm`/`rmdir`; cross-session safeguards; `blockReadsOutsideWorkingDirectories`/`blockWritesOutsideWorkingDirectories`; PreToolUse hook deny (HG#hooks-and-permission-modes). Allow rules have no effect; protected-path checks are skipped.
- Protected paths (PMD#protected-paths): `.git`, `.claude` (with exceptions), `.husky`, `.vscode`, shell rc files, `.pre-commit-config.yaml`, `lefthook.yml`, `.mcp.json`, `.claude.json`, `--settings` file, symlink targets of settings files. Prompted in default/acceptEdits, classifier in auto, denied in dontAsk, allowed in bypass. Allow rules do not pre-approve them.
- `disableBypassPermissionsMode`: works from any scope (user can lock self out); also makes subagent `permissionMode: bypassPermissions` ignored (PRM#managed-settings; SREF#permissions-disablebypasspermissionsmode).
- `-p` default mode: Manual since v2.1.302; calls needing approval are denied unless allowed (PMD#tool-calls-denied-in-claude-p-and-agent-sdk-runs).
- Project `allow` rules need workspace trust; deny/ask do not (PRM#project-allow-rules-and-workspace-trust).

---

## 6. Sandbox
Source: SBX, SREF#sandbox-settings.
- Platforms: macOS (Seatbelt, built in); Linux and WSL2 (`bubblewrap` + `socat`); native Windows unsandboxed (SBX).
- Scope: Bash, PowerShell, Monitor commands and their children. NOT the Read/Edit/Write/WebFetch tools, hooks, MCP servers, status line, mods (SBX#what-runs-outside-the-sandbox).
- Keys: `sandbox.enabled`, `sandbox.failIfUnavailable`, `sandbox.allowUnsandboxedCommands` (false = strict mode, ignores `dangerouslyDisableSandbox`), `sandbox.autoAllowBashIfSandboxed`, `sandbox.excludedCommands`, `sandbox.filesystem.allowWrite`, `.denyWrite`, `.denyRead`, `.allowRead`, `.disabled`, `sandbox.network.allowedDomains`, `.deniedDomains`, `.strictAllowlist` (v2.1.219+), `sandbox.credentials` (SBX#configure-sandboxing, SBX#network-isolation).
  ```json
  {"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,
   "filesystem":{"denyWrite":["~/.config/ai"],"denyRead":["~/.ssh"]},
   "network":{"allowedDomains":["github.com","*.npmjs.org"],"strictAllowlist":true}}}
  ```
- Default: writes to cwd, per-user temp, added dirs; reads most of the machine incl. `~/.ssh`; network via proxy, allowlist starts empty (SBX#what-the-sandbox-restricts).
- Fallback: by default, if unavailable, commands run unsandboxed; `failIfUnavailable: true` exits instead (SBX#get-started).
- `excludedCommands`: whole command text must match; runs with full access (SBX#run-commands-outside-the-sandbox-with-excludedcommands).
- `allowUnsandboxedCommands: false` from user settings holds against a project `true` (v2.1.285+); from managed or `--settings` it makes the sandbox "admin-required", which ignores loosening keys in repo files (SBX#turn-off-the-retry-with-strict-sandbox-mode).
- What it protects that hooks cannot (SBX#protected-paths): writes by any sandboxed process (including scripts that open files themselves) to `.claude` settings, `.claude/skills|agents|commands|hooks`, `.mcp.json`, `.git/hooks` and `.git/config` in cwd, shell rc files, most of `~/.claude` and `~/.claude.json`. `allowWrite` or `Edit` allow cannot reopen them. In linked worktrees, `hooks/` and `config` in the shared `.git` stay denied (SBX#filesystem-isolation). Hooks only see tool-call text; the sandbox enforces at OS level on what the process does.
- A state folder of your own (e.g. `~/.config/ai/state`): add it to `filesystem.denyWrite`; not in the default protected list. (Inference from SBX#configure-sandboxing.)
- Limits: no TLS inspection, domain fronting possible; `!` shell-mode commands typed by the user run unsandboxed; `allowNestedUserNamespaces` on Linux breaks protected paths (SBX#limitations).
- Subagents use the same sandbox config (SBX#scope).

---

## 7. Managed settings
Source: MGD, SET#settings-precedence, SREF.
- File paths: macOS `/Library/Application Support/ClaudeCode/managed-settings.json` plus `managed-settings.d/*.json` and `managed-mcp.json`; Linux/WSL `/etc/claude-code/...` (MGD#where-each-mechanism-stores-the-policy). Also macOS plist domain `com.anthropic.claudecode` (MDM), and server-managed settings.
- Reload: file read at startup and reloaded when the file changes (MGD#choose-a-delivery-mechanism).
- Source ranking (default `first-wins`): server-managed > MDM/plist > file > HKCU; `managedSourcesBehavior: "merge"` composes them (v2.1.242+) (MGD#how-claude-code-combines-managed-sources).
- Precedence: managed > `--settings` > local > project > user; lists merge across levels (SET#settings-precedence). Managed `model` is only a default (MGD#what-a-developer-can-change).
- Managed-only keys (MGD#keys-only-a-managed-source-can-set): `allowManagedHooksOnly`, `allowManagedPermissionRulesOnly`, `allowManagedMcpServersOnly`, `strictPluginOnlyCustomization` (true or array of `skills`,`agents`,`hooks`,`mcp`), `strictKnownMarketplaces`, `blockedMarketplaces`, `disableSideloadFlags` (v2.1.193+), `disableCommandPluginSources`, `sandbox.network.allowManagedDomainsOnly`, `sandbox.filesystem.allowManagedReadPathsOnly`, `forceRemoteSettingsRefresh`, `policyHelper`, `managedSourcesBehavior`, `managedMcpServers`. Plus `claudeMd` (MEM#deploy-organization-wide-claude-md).
- `allowManagedHooksOnly: true`: runs managed hooks, SDK hooks, and hooks of plugins force-enabled in managed `enabledPlugins` (full `plugin@marketplace` id); blocks user, project, local, other plugin and agent-frontmatter hooks; `/goal` cannot run (SREF#allowmanagedhooksonly).
- `allowManagedPermissionRulesOnly: true`: ignores allow/ask/deny in user, project, local, `--settings`, and `--allowedTools`; ignores `allowed-tools` in non-managed skills (v2.1.282+). `--disallowedTools` still applies (SREF#allowmanagedpermissionrulesonly).
- `disableAllHooks` outside managed cannot disable managed hooks (HK#disable-or-remove-hooks).
- `--safe-mode` still applies managed hooks and policy, but not managed plugins, skills, CLAUDE.md or MCP (CLI `--safe-mode`).
- Agent SDK sessions load managed settings even when `settingSources` excludes others (MGD#where-and-when-a-policy-applies).
- ConfigChange cannot block `policy_settings` changes (HK#configchange-decision-control).
- Check: `/status` shows `Enterprise managed settings (file)`; `claude doctor` lists dropped entries (MGD#deploy-a-managed-settings-file, MGD#check-that-a-policy-is-in-force).
- Single user on own Mac: the docs do not address this case directly. They say "a developer who is an administrator on the machine can edit the managed source itself" (MGD#what-a-developer-can-change). Inference: a root-owned file in `/Library/Application Support/ClaudeCode/` cannot be changed by the agent process running as the normal user without `sudo`; Claude Code refuses `bypassPermissions` under root/sudo (PMD#skip-all-checks-with-bypasspermissions-mode). The agent could still run `sudo` through Bash if sudo is passwordless or cached, so pair with a `Bash(sudo *)` deny rule in the same managed file (that rule has the documented Bash-pattern limits). Protected-path lists do not include `/Library/Application Support/ClaudeCode/` (PMD#protected-paths); the sandbox denies writes there by default because it is outside the writable set (SBX#what-the-sandbox-restricts). Side benefit: any managed settings file loads the built-in mod guard (MODS#know-what-happens-by-default).

---

## 8. Subagents
Source: SUB.
- Locations and priority: managed (1) > `--agents` JSON (2) > `.claude/agents/` (3, walks up to repo root) > `~/.claude/agents/` (4) > plugin `agents/` (5) (SUB#choose-the-subagent-scope).
- Frontmatter (SUB#frontmatter-reference): `name` (required), `description` (required), `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `autoCompactWindow`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `omitClaudeMd` (v2.1.271+), `effort`, `isolation: worktree`, `color`, `initialPrompt`, `experimental.cacheTtl`. Unknown fields ignored silently; `claude --debug` logs `does not recognize or apply` (v2.1.296+).
  ```markdown
  ---
  name: reviewer
  description: Read-only code reviewer
  tools: Read, Grep, Glob
  disallowedTools: Write, Edit, Bash
  permissionMode: plan
  hooks:
    PreToolUse:
      - matcher: "Bash"
        hooks:
          - type: command
            command: "./scripts/validate.sh"
  ---
  ```
- Inherits: CLAUDE.md (not Explore/Plan, not `omitClaudeMd`); all settings/managed/plugin hooks fire for its tool calls with `agent_id`/`agent_type` (HK#hook-locations; SUB#define-hooks-for-subagents); permission rules apply ("The rule applies to the main conversation and to subagents", SUB#restrict-which-tools-a-subagent-can-use); MCP tools of the main conversation (SUB#available-tools); same sandbox (SBX#scope).
- Permission mode: if main is `bypassPermissions`, `acceptEdits` or `auto`, the subagent uses that mode and ignores its own `permissionMode`; plan main keeps subagent in plan; from `default`/`dontAsk` main the subagent uses its own value, except `bypassPermissions` (v2.1.267+) (SUB#permission-modes). Ignored for plugin subagents.
- Tool restriction by construction: `tools` allowlist and/or `disallowedTools`; `disallowedTools: Bash(git push *)` removes the whole Bash tool (SUB#restrict-which-tools-a-subagent-can-use). Background subagents keep only a fixed tool set (SUB#available-tools). `Agent(worker, researcher)` in `tools` limits spawnable subagents for a `--agent` main thread (SUB#restrict-which-subagents-can-be-spawned).
- Skills: `skills:` preloads full content (first 32 names); without `Skill` in tools, it cannot invoke skills (SUB#preload-skills-into-subagents).
- SubagentStart: inject context (cannot block). SubagentStop: block to keep it working; `agent_transcript_path`, `last_assistant_message` (HK#subagentstart, HK#subagentstop). To feed the parent, use PostToolUse on `Agent` (HK#subagentstop).
- Frontmatter `Stop` hook becomes `SubagentStop` (HK#hooks-in-skills-and-agents).
- `isolation: worktree`: temp worktree from default branch, auto-cleaned if no changes (SUB#frontmatter-reference).

---

## 9. Skills
Source: SKL.
- Frontmatter (SKL#frontmatter-reference): `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context: fork`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`. Unknown fields ignored; bad YAML loads with no fields.
- Trigger: description + when_to_use go into a listing; combined text truncated at 1,536 chars (`skillListingMaxDescChars`). Listing budget 1% of context window (`skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`); overflow drops least-used descriptions (SKL#skill-descriptions-are-cut-short). `skillOverrides` per skill: `on`, `name-only`, `user-invocable-only`, `off`; not for plugin skills (SKL#override-skill-visibility-from-settings).
- `disable-model-invocation: true`: Claude cannot invoke; description not in context; cannot be preloaded. `user-invocable: false`: hidden from `/` (SKL#control-who-invokes-a-skill).
- `allowed-tools`: pre-approves for the invoking turn only; does not restrict. Applied even in untrusted `-p` (SKL#pre-approve-tools-for-a-skill). `disallowed-tools`: removes tools until next user message.
- `hooks`: registered on invocation, run for the rest of the session; `once: true` removes after first success (HK#hooks-in-skills-and-agents).
- `paths`: activate skill for matching files (SKL#frontmatter-reference).
- `context: fork`: runs in a subagent of type `agent`; with `agent: Explore` no CLAUDE.md (SKL#run-skills-in-a-subagent).
- Lifecycle: content stays in conversation; not re-read; after compaction first 5,000 tokens kept (SKL#skill-content-lifecycle). Put key rules at top.
- Built-in commit hook into skills: a project/personal skill named `verify` or `simplify` makes Claude run it before each commit (v2.1.286+, needs `includeGitInstructions` on, model-invocable) (SKL#run-your-checks-before-each-commit).
- When to move text from CLAUDE.md: multi-step procedures or rules for one part of the codebase go to a skill or path-scoped rule (MEM#when-to-add-to-claude-md; FO#build-your-setup-over-time). A rule that "must hold every time" goes to a hook, optionally in the skill's `hooks` (SKL#claude-stops-following-a-skill).
- `/skill-doctor` (v2.1.252+) reports cost/use; not available without feature-flag fetching (SKL#find-unused-skills).

---

## 10. Plugins
Source: PCO, PLD, PIN, PCLI, PMK.
- Structure: `.claude-plugin/plugin.json` (only `name` required; optional `version`), `skills/<name>/SKILL.md`, `commands/`, `agents/`, `hooks/hooks.json` (top-level `"hooks"` key, same shape as settings), `.mcp.json`/MCP config, LSP, monitors, output styles, `bin/` executables (PCO#explore-the-plugin-directory).
- Plugin hooks register when the session loads the plugin and fire on every event, not only when a plugin skill runs (PCO#when-plugin-hooks-fire). Env: `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PLUGIN_OPTION_<KEY>`.
- Plugin skills are namespaced `/plugin:skill`; plugin agents `plugin:agent`; plugin MCP tools `mcp__plugin_<plugin>_<server>__<tool>`.
- Cache: `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` (`CLAUDE_CODE_PLUGIN_CACHE_DIR`); `installed_plugins.json`, `known_marketplaces.json`; old versions removed 14 days after orphaning (PLD#find-plugins-on-disk).
- Version: manifest `version` first, then marketplace entry `version`, then commit SHA (git sources) or `unknown` (local non-git). A pinned `version` keeps users on the cached copy until the string changes (PLD#how-claude-code-computes-the-version).
- In-place loading: `--plugin-dir` plugins, skills-directory plugins, and relative-path plugins in a marketplace added from a local path load from source every session start / `/reload-plugins`; no version bump needed (PLD#in-place-and-copied-plugins; PMK).
- Local directory marketplace: `my-marketplace/.claude-plugin/marketplace.json` with `name`, `owner`, `plugins[{name, source:"./plugins/x"}]`; `claude plugin marketplace add ./my-marketplace`; `claude plugin install x@my-marketplace` (PMK).
- Update: `claude plugin update <plugin>@<marketplace>` (no "update all"); auto-update default off for non-official marketplaces; `/reload-plugins` switches hooks/MCP/LSP to new path (PIN#keep-plugins-updated; PLD#when-auto-update-runs).
- `enabledPlugins` sources: `--add-dir` < user < project < local < `--settings` < managed; managed `true` force-enables, `false` blocks (PLD#find-where-a-plugin-is-enabled).
- `--plugin-dir` overrides a same-named installed plugin silently (PLD#name-conflicts); disable with `"enabledPlugins": {"name@inline": false}`.
- `-p`: installed plugins load; `/plugin` unavailable (PIN#jetbrains-non-interactive-runs-and-the-agent-sdk).
- See/disable hooks: `/hooks` labels source `[plugin:<name>]`; `/plugin` Errors tab; `claude plugin disable`; `disableAllHooks` stops plugin hooks unless the plugin is force-enabled by managed settings (SREF#disableallhooks).
- `claude plugin validate <dir>` checks syntax (PCLI#plugin-validate).

---

## 11. Headless and evaluation
Source: HL, CLI, EVAL.
- Flags: `-p`; `--output-format text|json|stream-json`; `--verbose` (needed with stream-json in examples); `--include-hook-events` (requires stream-json; SessionStart/Setup hook events always included); `--max-turns`; `--max-budget-usd`; `--permission-mode`; `--allowedTools`/`--disallowedTools`; `--settings <file-or-json>`; `--setting-sources user,project,local`; `--plugin-dir` (repeatable); `--agents` (file path in `-p`, v2.1.281+); `--safe-mode`; `--bare`; `--restricted` (v2.1.248+); `--debug-file <path>`; `--no-session-persistence`; `--permission-prompts none` (v2.1.259+) (CLI#cli-flags).
- `--bare` skips your hooks, skills, plugins, CLAUDE.md, MCP; even `--settings` hooks and flag-loaded plugin hooks do not run in bare mode (HL#start-faster-with-bare-mode). So a setup test must not use `--bare` (consistent with the owner's rule).
- Stream events: `hook_started`, `hook_progress`, `hook_response` (with `--include-hook-events`); `permission_denied` system messages; final `result` has `permission_denials`; `system/init` lists `plugins`, `plugin_errors`, `mcp_servers`, `mcp_server_errors` (HL#read-session-metadata; HL line on denials; CLI `--include-hook-events`).
- Minimal setup probe:
  ```bash
  claude -p "Run: git push origin main" --output-format stream-json --verbose \
    --include-hook-events --max-turns 3 --permission-mode default \
    --debug-file /tmp/probe.log | jq -c 'select(.type=="system" or .type=="result")'
  ```
- Trust in `-p`: settings hooks and project skill hooks run; project subagent frontmatter hooks do not; project allow rules are not applied (PRM#what-runs-before-you-trust-a-folder).
- `claude plugin eval` (v2.1.269+ per EVAL#requirements): runs each case in a fresh isolated `claude -p` with only the plugin loaded; user settings, hooks, CLAUDE.md, other plugins are absent; managed policy still applies (EVAL#how-runs-are-isolated). Graders include `tool_used` (e.g. `tool: Skill`), regex, llm judge; baseline arm without the plugin; exit non-zero below threshold for CI (EVAL; SKL#evaluate-and-iterate-on-a-skill). Bash grants require the OS sandbox (EVAL#shell-grants-need-a-sandbox). `claude plugin eval init` writes a suite. Consequence: to eval the owner's rules, package them as a plugin.
- skill-creator plugin: separate `evals/evals.json` loop for one skill (SKL#run-evals-with-skill-creator).

---

## 12. Debugging
- `/hooks`: read-only browser, source label per hook, full command (HK#the-hooks-menu). Skill hooks appear only after invocation.
- Debug log: `claude --debug` writes `~/.claude/debug/<session-id>.txt`; `--debug-file <path>`; `/debug` mid-session. v2.1.296+ writes `Hooks: <Event>:<match> [cmd] finished with status N (31ms)` lines with timing; `CLAUDE_CODE_DEBUG_LOG_LEVEL=verbose` adds matcher counts (HK#debug-hooks).
- Transcript view `Ctrl+O`: hook block messages and `hook error` notices (HG#check-what-a-hook-did).
- Async hook completion notices: `--verbose` or `Ctrl+O` (HK#how-async-hooks-execute).
- Manual test: pipe sample JSON to the script and check `$?` (HG#hook-error-in-output).
- `/doctor` (bundled skill): installation, settings, extensions, CLAUDE.md; `claude doctor` in shell for invalid settings and dropped managed entries (CMD; MGD#check-that-a-policy-is-in-force; DBG).
- `/context all`, `/memory`, `/status` (setting sources), `/permissions` (rules with source file) (DBG; PRM#manage-permissions).
- `disableAllHooks: true` (any file; cannot disable managed hooks outside managed); `--settings '{"disableAllHooks": true}'` for one run. No per-hook disable (HK#disable-or-remove-hooks).
- `--safe-mode`: all customizations off except managed policy (CLI).

---

## 13. Rule type -> strongest documented mechanism

| Rule | Mechanism | Example | What still gets past |
|---|---|---|---|
| (a) never run a command form | `permissions.deny` (managed for tamper-proof) + PreToolUse command hook with `onFailure:"block"` that normalizes the command + sandbox for the side effect | `{"permissions":{"deny":["Bash(git push *)"]}}` plus hook `if:"Bash(git *)"` that rejects any `push` token | Other spellings (`git -C . push`, `/usr/bin/git`, `sh -c`) pass the rule (PRM#what-a-bash-rule-doesnt-match); `if` is best-effort (HK#how-if-patterns-match-bash-commands); scripts the agent writes and runs; mods' own calls (MODS); user `!` commands |
| (b) never edit a path | `Edit(...)` deny (covers all edit tools) + `Read` deny if needed + `sandbox.filesystem.denyWrite` + `blockWritesOutsideWorkingDirectories` | `{"permissions":{"deny":["Edit(//Users/me/.config/ai/**)"]},"sandbox":{"enabled":true,"allowUnsandboxedCommands":false,"filesystem":{"denyWrite":["~/.config/ai"]}}}` | Without sandbox: Bash scripts that open files (PRM#read-and-edit); `excludedCommands`; hooks, MCP servers, mods run unsandboxed (SBX#what-runs-outside-the-sandbox) |
| (c) always run a check before commit/PR | PreToolUse hook `if:"Bash(git commit *)"` / `Bash(gh pr create *)` that runs the check and exits 2 on failure, `onFailure:"block"`; plus git pre-commit hook outside Claude; Stop prompt hook as backstop | `{"matcher":"Bash","hooks":[{"type":"command","if":"Bash(git commit *)","command":"/abs/path/precommit-gate.sh","onFailure":"block","timeout":300}]}` | Commit forms the `if` does not see (e.g. via script, `git -c ... commit`); `--no-verify` unless denied; hooks off via `disableAllHooks` in a project file overriding user (HK#disable-or-remove-hooks) unless managed |
| (d) load a procedure before a kind of edit | PreToolUse hook `if:"Edit(**/SKILL.md)"` that checks the transcript for a prior Skill call and denies with a reason naming the skill; or path-scoped rule (`paths:`) for passive text; or skill `paths:` | hook returning `permissionDecision:"deny"` + reason "Load writing-for-agents first" | Transcript lag: `transcript_path` may not include the latest turn (HK#common-input-fields); edits via Bash (`sed -i`, `cat >`) unless also matched; path rules are only context |
| (e) reply style | Output style (system prompt, main + forks only) or `--append-system-prompt`; Stop `type:"prompt"` hook judging `last_assistant_message` | see section 4 example | Not deterministic; 8-continuation cap; subagents do not get output style (OS#how-output-styles-work); cost per turn |
| (f) use tool X before tool Y | PreToolUse hook on Y that reads state written by a PostToolUse hook on X (e.g. a file in `scratchpad_dir` keyed by `session_id`) and denies otherwise | PostToolUse `matcher:"mcp__serena__find_symbol"` writes marker; PreToolUse `matcher:"Grep"` checks it | State file writable by the agent unless sandbox `denyWrite` covers it; subagents have own `agent_id` (decide per session vs agent); parallel hooks; transcript lag |
| (g) keep session in one worktree | Start with `--worktree` or `isolation: worktree`: built-in checks block edits, cwd and git redirects into the main checkout (WT#how-claude-code-enforces-isolation); `Cd(...)` rules limit `/cd`; `blockWritesOutsideWorkingDirectories` | `claude --worktree <name>`; `{"permissions":{"deny":["Cd"]}}` | `cp` or shell redirects into the main checkout are not tracked by the checks (WT); `blockWritesOutsideWorkingDirectories` does not limit shell or MCP (PRM); sandbox write scope is the fix |
| (h) no secrets in a commit | git pre-commit hook (outside Claude, e.g. gitleaks) + PreToolUse hook on `Bash(git commit *)` running the scanner + deny `Bash(git commit --no-verify *)`/`-n` + `Read` deny on secret files + sandbox `credentials`/`denyRead` | `{"permissions":{"deny":["Read(**/.env)","Bash(git commit --no-verify *)","Bash(git commit -n *)"]}}` | Scanner false negatives; other no-verify spellings (`git -c core.hooksPath=/dev/null commit`); `.git/hooks` edits blocked only by sandbox protected paths or protected-path prompts (SBX#protected-paths, PMD#protected-paths) |

Cross-cutting for "every session":
- Put hooks in `~/.claude/settings.json` or a user-scope plugin: they reach every project, subagents, and `-p` (not `--bare`) (HK#hook-locations). A project `.claude/settings.json` with `"disableAllHooks": false/true` wins over user settings (HK#disable-or-remove-hooks); only managed settings are immune.
- Use `onFailure: "block"` on every policy hook; default is fail-open (HK#block-the-action-when-a-hook-fails).
- Explore/Plan subagents skip CLAUDE.md; use `SubagentStart` additionalContext for rules they need (SUB#what-loads-at-startup).
- Managed settings file on the owner's Mac gives: unoverridable deny rules and hooks, `disableAllHooks` immunity, and the mod guard (MGD; MODS).

---

## 14. Not documented / could not confirm
1. Whether a hook `if: "Edit(...)"` matches `Write` and `NotebookEdit` calls (permission `Edit` rules do; `if` matching for Write is not stated). Test it.
2. Exact cost and latency of a prompt/agent hook call; which concrete model "background functionality" resolves to by default.
3. Whether skill-frontmatter hooks registered in the main session also fire inside subagents spawned later.
4. Whether a prompt hook can read the transcript content (only `transcript_path` string in input is documented).
5. Explicit guidance for a single-user Mac that owns its own managed settings file; the docs cover only "local admin rights" generally.
6. Whether `allowManagedHooksOnly` hooks run in `--bare` mode (bare skips "your hooks"; managed behavior under bare is not stated).
7. Precise rule for how `once: true` interacts with subagents.
8. Default model for agent hooks beyond "same as prompt hooks".
9. The minimum versions of most hook events and of the `if` field itself.
10. Embedded guide reference said `plugin eval` exists from v2.1.198; the public EVAL page says v2.1.269 or later. The public page is cited above.
11. Official Anthropic engineering blog posts were not fetched; the docs link "Steering Claude Code" (https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) from FO#compare-similar-features, not read here.
