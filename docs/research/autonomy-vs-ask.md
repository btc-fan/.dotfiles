# Autonomy with a stop only before high-impact actions

Date: 2026-11-20
Installed: Claude Code 2.1.325, codex-cli 0.170.0 (main Mac).
Status: current
Related: `docs/specs/ask-first.md`, and `docs/research/agent-risk-confirmation.md` on branch `research/risk-gate`.

Question: how do Claude Code (first) and Codex (second) stay fully autonomous for normal work, but stop and ask the owner before a high-impact action?

Labels: VERIFIED means a primary doc, the source code or an experiment in this file. UNVERIFIED means an estimate or an inference.

## Short answer

1. A rule in CLAUDE.md or AGENTS.md is always loaded, but it is guidance only. Anthropic says to use a hook when an action must always stop.
2. Experiment: a PreToolUse hook `ask` shows a real Yes/No prompt in `bypassPermissions` mode. In `-p` mode it becomes a deny. A hook `deny` blocks in both.
3. So the owner can keep `bypassPermissions` and add one narrow gate. Normal work gets zero prompts. Auto mode is not needed for this.
4. Codex has no hook `ask`. A deny plus a typed "go" (the merge-approval pattern) is the Codex path.

## Q1: rules in CLAUDE.md and AGENTS.md

| Claim | Status | Source |
|---|---|---|
| CLAUDE.md files are "loaded at the start of every conversation". Claude treats them "as context, not enforced configuration". | VERIFIED | <https://code.claude.com/docs/en/memory> |
| "To block an action regardless of what Claude decides, use a PreToolUse hook instead." | VERIFIED | <https://code.claude.com/docs/en/memory> |
| CLAUDE.md "is delivered as a user message after the system prompt". There is "no guarantee of strict compliance, especially for vague or conflicting instructions." | VERIFIED | <https://code.claude.com/docs/en/memory> |
| Target "under 200 lines per CLAUDE.md file". Longer files "reduce adherence". Conflicting rules: "Claude may pick one arbitrarily." | VERIFIED | <https://code.claude.com/docs/en/memory> |
| After `/compact`, the project-root CLAUDE.md is re-read from disk and re-injected. Rules given only in chat can be lost. | VERIFIED | <https://code.claude.com/docs/en/memory> (section "Instructions seem lost after /compact") |
| Subagents load every CLAUDE.md level, also `~/.claude/CLAUDE.md`. The built-in Explore and Plan agents skip them. `omitClaudeMd: true` also skips them. | VERIFIED | <https://code.claude.com/docs/en/sub-agents> |
| A subagent of a `bypassPermissions` parent runs in `bypassPermissions` too. | VERIFIED | <https://code.claude.com/docs/en/sub-agents> |
| Hooks from settings and plugins fire for subagent tool calls. | VERIFIED | <https://code.claude.com/docs/en/hooks>, <https://code.claude.com/docs/en/sub-agents> |
| Anthropic splits instructions into "non-deterministic" (prompt, CLAUDE.md, skill) and "deterministic" (hook, deny rule, managed setting). The second kind applies "every time, no matter what the model decided". | VERIFIED | <https://code.claude.com/docs/en/best-practices> |
| Hooks give "deterministic control: certain actions always happen rather than relying on the LLM". | VERIFIED | <https://code.claude.com/docs/en/hooks-guide> |
| On consent signals in prompts: "We've tried prompt-engineering around this and haven't found a fix that doesn't cost more than it gains." | VERIFIED | <https://www.anthropic.com/engineering/claude-code-auto-mode> (quoted in the earlier research) |

Result: the rule text is needed, because it gives the agent the plan-then-ask habit and covers cases no gate sees. It is not a guarantee. The incident showed this: the agent read "Standing permission" as consent.

## Q2: hooks in bypassPermissions mode (experiment)

Setup (VERIFIED, files in the scratch folder `hooktest/`):

- `.claude/settings.json` with a PreToolUse hook on `Bash`. The hook returns `ask` for `echo RISKY` and `deny` for `echo BLOCKED`.
- The user settings and plugins stayed on, so the test matches the real setup. `HC_TERMINAL_ID` was unset, so the herdr card hook did not wait.
- The hook log shows `mode=bypassPermissions` for each call.

Results:

| Run | What happened | Status |
|---|---|---|
| `claude -p "run the bash command: echo RISKY" --permission-mode bypassPermissions --output-format stream-json --verbose --max-turns 3` | The command did not run. A `permission_denied` event, then a tool result with `is_error: true` and the text "TESTHOOK: RISKY needs owner OK". Claude stopped and told the user. 2 turns, USD 0.89. | VERIFIED (experiment) |
| Same with `echo BLOCKED` | The command did not run. Tool result: "PreToolUse:Bash hook error: TESTHOOK: BLOCKED is denied". Claude did not try another way. 2 turns, USD 0.56. | VERIFIED (experiment) |
| Interactive `claude --permission-mode bypassPermissions "run the bash command: echo RISKY"` under `expect` | A prompt appeared: "Hook PreToolUse:Bash requires confirmation for this command: TESTHOOK: RISKY needs owner OK [settings]", with "1. Yes / 2. No". After Esc the command did not run. | VERIFIED (experiment) |
| Same, with a logging PermissionRequest hook added | The PermissionRequest hook fired for the hook `ask`. So the owner's herdr card hook (`~/.config/herdr-app/mods/chat/ask-hook.sh`) also gets these prompts. | VERIFIED (experiment) |

Docs that match the experiment:

- `permissionDecisionReason`: "For `ask`, shown to the user in the permission prompt." In a `-p` run, Claude Code denies the call. Then "Claude reads the reason in the tool result instead." VERIFIED, <https://code.claude.com/docs/en/hooks>
- Hook precedence: `deny` > `defer` > `ask` > `allow`. VERIFIED, <https://code.claude.com/docs/en/hooks>
- "Deny rules block in every mode, including `bypassPermissions`." Explicit ask rules still prompt there. VERIFIED, <https://code.claude.com/docs/en/permission-modes>
- In headless runs: "Claude is told that nobody can approve the request and not to retry it, and the run continues." VERIFIED, <https://code.claude.com/docs/en/headless>

This closes the open point "hook ask in bypassPermissions" from the earlier research.

## Q3: Claude Code auto mode

How it works:

- "A separate classifier model reviews actions before they run, blocking anything that escalates beyond your request, targets unrecognized infrastructure, or appears driven by hostile content." VERIFIED, <https://code.claude.com/docs/en/permission-modes>
- Two stages: a fast single-token filter, then reasoning only for flagged actions. VERIFIED, <https://www.anthropic.com/engineering/claude-code-auto-mode>
- The classifier reads the user's messages and the commands, not the command output. VERIFIED, <https://code.claude.com/docs/en/auto-mode-config>
- The default classifier model is Claude Sonnet 5. VERIFIED, <https://code.claude.com/docs/en/permission-modes>

Default rules on this install (`claude auto-mode defaults`, VERIFIED): 16 allow, 72 soft_deny, 1 hard_deny, 21 environment entries. Rules that touch the incident:

- "Unauthorized Persistence": "creating cron jobs, systemd services ... or other mechanisms that persist access or execute code beyond the current session."
- "Remote Shell Writes": writes "to running production or shared hosts via remote shell access (e.g. ... `ssh`)".
- "Interfere With Workloads": killing a job "the agent did not create this session".
- "Production Deploy", "Git Destructive" (force push), "Irreversible Local Destruction", "Merge Without Review".
- A host is a sensitive remote target only when `prod` or `production` is a whole word in its name. The name of server A does not match. It must go into `autoMode.environment`. VERIFIED, <https://code.claude.com/docs/en/auto-mode-config>
- A starting `myd server start` on the local host has no clear default rule. Whether the classifier blocks it is UNVERIFIED.
- An unrequested `gh pr create` in the own repo: auto mode "can also open pull requests there when your task asks for one". Whether "prepare" counts as a request is UNVERIFIED.

Custom rules (VERIFIED, <https://code.claude.com/docs/en/auto-mode-config>):

- `autoMode.environment`, `allow`, `soft_deny`, `hard_deny` are prose rules. Put `"$defaults"` in each list to keep the built-in rules.
- The classifier reads `autoMode` only from `~/.claude/settings.json`, managed settings or `--settings`. It ignores project `.claude/settings.json`.
- The owner already has an `autoMode` block in `~/.claude/settings.json` (entries for a crawler project). VERIFIED (file read).
- A boundary said in chat ("don't push") blocks matching actions, but "can be lost if context compaction removes the message".

What happens on a block (VERIFIED, <https://code.claude.com/docs/en/permission-modes>):

- Claude gets the reason and should "try a safer approach where one exists". It does not stop and ask. VERIFIED, <https://www.anthropic.com/engineering/claude-code-auto-mode>
- After 3 blocks in a row or 20 in total, auto mode pauses and normal prompts come back. These limits "are not configurable".
- The owner can approve a blocked action in `/permissions` (tab "Recently blocked") or by naming the action and its target in chat.
- In `-p` runs a block does not stop the run. The blog post says headless "terminates" instead. The two sources differ. The docs page is newer.

Numbers from Anthropic (VERIFIED, <https://www.anthropic.com/engineering/claude-code-auto-mode>):

- Users accept 93% of manual permission prompts.
- False positive rate 0.4% of real actions after both stages.
- False negative rate 17% on real overeager actions. The post calls auto mode "not a drop-in replacement for careful human review on high-stakes infrastructure."

Cost and latency (VERIFIED, <https://code.claude.com/docs/en/permission-modes>): each check adds a round-trip before the action. Classifier calls count toward usage on Enterprise and API accounts. When the server reviews the actions inside the model request, no extra calls are counted.

With hooks (VERIFIED, <https://code.claude.com/docs/en/hooks>, <https://code.claude.com/docs/en/auto-mode-config>): deny and explicit ask rules run before the classifier. A PreToolUse hook `ask` goes to the prompt, and the classifier does not decide it. So auto mode and a gate can run together.

Availability (VERIFIED): `claude --help` lists `--permission-mode` with `"auto"` and the `auto-mode` subcommand. From v2.1.283, auto mode is the default start mode for interactive sessions. `~/.claude/settings.json` has no `defaultMode` key, so the owner's bypass mode comes from a launch flag or a launcher (UNVERIFIED which one).

Comparison:

| Topic | bypassPermissions + narrow gate | Auto mode |
|---|---|---|
| Normal work | Zero prompts, no extra latency | Zero prompts, one classifier round-trip per action |
| Incident steps | Stops all four (when the gate lists them) | Persistence and remote writes likely; local service start and the PR UNVERIFIED |
| On a hit | Asks the owner (interactive) or denies with a reason | Denies; agent looks for another way; asks only after 3 or 20 blocks |
| Misses | Commands not in the list, scripts on the remote host | 17% of overeager actions (Anthropic number) |
| Codex | Same router, deny + typed OK | Not available |
| Tunable | Exact, per command | Prose rules, not exact |

## Q4: Codex

- `on-request`: "commands allowed by the sandbox can run without approval." `never`: "disable approval prompts". `granular` keeps some prompt types and rejects others. `untrusted` is retired. VERIFIED, <https://learn.chatgpt.com/docs/agent-approvals-security>
- `approvals_reviewer = "auto_review"` routes approval requests to a reviewer agent. It works only with interactive approvals and uses extra model calls. VERIFIED, same page.
- Execpolicy `prompt`: "Prompt before each matching invocation." `forbidden`: "Block the request without prompting." Rules live in `~/.codex/rules/*.rules`. VERIFIED, <https://learn.chatgpt.com/docs/agent-configuration/rules>
- `prompt` under `approval_policy = never`: the docs do not say. The source does. `prompt_is_rejected_by_policy` returns "approval required by policy, but AskForApproval is set to Never", and the call becomes `Forbidden`. VERIFIED, `codex-rs/core/src/exec_policy.rs` on `openai/codex` main (read 2026-11-20; not checked against the 0.170.0 tag).
- Codex PreToolUse `ask` is "parsed but not supported yet", and the tool call continues. VERIFIED, <https://learn.chatgpt.com/docs/hooks> (earlier research). The router already turns `ask` into `deny` for Codex (`router.py:613`).

Experiment with `codex execpolicy check` (VERIFIED, command output):

| Rule: `prefix_rule(pattern=["systemctl", ["start","stop","restart","enable","disable"]], decision="prompt")` | Result |
|---|---|
| `systemctl enable x.service` | `"decision":"prompt"` |
| `systemctl status x` (allow rule) | `"decision":"allow"` |
| `systemctl --user enable x.service` | `{"matchedRules":[]}`: no match |
| `bash -lc 'systemctl restart x'` | no match in the check tool |

The exact incident form `systemctl --user enable` passes a plain prefix rule. Execpolicy is a weak gate for this list.

Local config (VERIFIED, file read, no secrets printed): `~/.codex/config.toml` has no `approval_policy` and no `sandbox_mode` key, so Codex uses its defaults. `~/.codex/rules/default.rules` has 40 lines of `allow` rules saved from the TUI, among them `prefix_rule(pattern=["docker", "compose"], decision="allow")`.

## Q5: design

### Layers

1. **Conduct rule (always on).** The "Standing permission" text from `docs/specs/ask-first.md` Part 1, in the global AGENTS.md. It reaches Claude, Codex and most subagents, and it comes back after compaction (Q1). It covers what no gate can see, for example a script that already lives on the remote host.
2. **Gate `ask-first` (deterministic).** A PreToolUse rule in the router, on every profile, for the spec's 11 command classes. Reads pass (`systemctl status`, `docker ps`, `crontab -l`, `ssh host 'uptime'`). It fires inside subagents too (Q1).
3. **Plan, then OK.** On a hit the gate denies with this text: "State the plan, the risk and the undo, then wait for the owner's go." The owner's next typed "go" sets `go_ok`, as `merge_ok` does (`router.py:290`). One "go" covers the plan until the next owner prompt without an OK.
4. **Stay in `bypassPermissions`.** No classifier cost and no latency. Auto mode stays an option for a live server session (see below).

Why deny + typed OK, not a native `ask`, for Claude too (UNVERIFIED design judgement):

- A native `ask` shows only the command. The owner wants the plan, the risk and the undo first.
- A native `ask` becomes a deny in `-p` runs anyway (Q2).
- One "go" covers a multi-step plan. A native `ask` prompts once per command.
- Claude and Codex then behave the same.
- Cost: the agent's turn ends at the gate. The owner types "go" instead of one key.
- A native `ask` with the herdr card stays possible for a single command, for example `reboot`.

Not recommended as the main layer:

- `permissions.ask` lists: `ssh` alone ran about 132 times a day in the owner's sessions (scan below). Every-ssh prompts break the zero-prompt goal.
- Codex execpolicy `prompt`: positional prefixes miss `--user` (Q4).
- A SessionStart conduct reminder: CLAUDE.md already reloads after compaction (Q1). The router already re-sends its table after `compact` (`router.py:48`). A just-in-time text in the gate message is more useful.
- Auto mode as the only layer: it blocks instead of asking, and it misses 17% of overeager actions (Q3).

Option for live servers (UNVERIFIED benefit): run Claude on server A in auto mode, with the gate still on. Add `"Sensitive remote targets: server A, server B, old Mac"` to `autoMode.environment`. The classifier then also catches actions the gate list misses, and the gate still forces the plan.

### Prompt frequency

Data (VERIFIED, scan of `~/.claude/projects/*/*.jsonl`, files changed in the last 14 days, main Mac only, script `scan.py` in the scratch folder):

- 204 session files, 17 calendar days, 8424 Bash calls, about 495 per day.
- A rough regex for the high-impact list matched 374 calls (about 22 per day).
- Top classes: `rm -r` 141 (34 of them in tmp, scratch or build paths), `gh pr create` 81, service verbs 75.
- Other classes: `kill` 29, force push 26, `reboot`/`shutdown` 24.
- Samples show real hits, for example `ssh host-b 'sudo systemctl reboot'` and `launchctl kickstart -k gui/$(id -u)/com.example.crawler`.
- Samples also show false matches, for example `grep ... shutdown` in a log search. The real rate is lower than 22 per day.

Estimates (UNVERIFIED, from the scan and the gate's pass list):

| Design | Normal dev day | Server-admin day | Reliable stop |
|---|---|---|---|
| Rule text only | 0 | 0 to 2 | No (incident) |
| Rule + gate, deny + typed "go" per plan | 0 to 1 | 2 to 5 | Yes, for listed commands |
| Rule + gate, native `ask` per command | 0 to 2 | 5 to 15 | Yes, for listed commands |
| `permissions.ask` on `ssh`, `systemctl` and others | more than 100 | more than 100 | Yes, but too noisy |
| Auto mode alone | about 2 false blocks (0.4% of 495) | 2 to 5 blocks | Partly (17% miss) |
| Codex with deny + typed "go" | same as the Claude gate row | same | Yes, for listed commands |

On a normal dev day most gate hits are `gh pr create` without an ask and `rm -r` outside the worktree. Both drop to near zero when the gate passes a PR the owner asked for and paths in the worktree, scratchpad and `/tmp`.

## Not verified

- How the owner's sessions start in `bypassPermissions` (no `defaultMode` in settings).
- Whether auto mode blocks `myd server start` or an unrequested draft PR.
- The Codex `prompt` + `never` behaviour in the 0.170.0 binary (source read on main only; no live `codex exec` run).
- The prompt estimates. They come from one machine and a rough regex.
- Whether the typed "go" scope (until the next owner prompt) is too wide for a long autonomous turn.
