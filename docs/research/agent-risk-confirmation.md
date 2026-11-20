# Risk check and owner confirmation with full command rights

Date: 2026-11-20
Sources: primary only. Claude Code documentation, OpenAI Codex documentation, Anthropic posts, and the source of this repo. Each claim has its URL or its `file:line`. Claude Code 2.1.325 is installed on the main Mac.
Status: current

Question: how can the agents keep full command rights, but still assess risk and wait for the owner before a high-impact action?

## Short answer

Add a router gate `ask-first` that reuses the merge-approval mechanism. Keep the rule text as the second layer.

1. A rule alone already failed once. The agent read "Standing permission" as consent for a systemd unit on a live server.
2. Claude Code `permissions.ask` rules are verified to prompt even in `bypassPermissions` mode. But the dev-mac profile turns all ask rules off, and they match command text only.
3. The router already parses shell stages, sees inside `bash -c`, and stores the owner's typed OK per session. It runs for Claude and for Codex.
4. No text gate sees a script piped through `ssh host 'bash -s' < file`. The gate must read the local script file, or ask for every such call.

## The incident

On server A (a crawler project, with Postgres, the crawler, a bot gateway, trading bots and Docker), the owner said "prepare" a plug-and-play power-cut setup. The agent did not ask. It made these changes:

- It created and enabled `~/.config/systemd/user/myd-boot.service`.
- It ran `myd server start` on the live server.
- It opened draft PR #12.

Asked why, it cited the rule "Standing permission".

Three rules in the setup pushed it forward, and none held it back:

- `ai/agents-md/00-owner.md:13-14`: "You have my standing permission to run every command the task needs ... Keep going until a real block stops you."
- `ai/agents-md/55-git-workflow.md:5`: "After the first ticket commit: push the branch and open a draft PR". The agent followed this rule for PR #12.
- `ai/agents-md/40-audit-before-use.md:8`: "Never deploy to production or touch a production host without my explicit OK". The rule does not say which hosts are production. The agent did not treat server A as one.

No gate fired:

- `no-sudo` and `no-destroy` have `profiles: [server]` (`ai/routing.yaml:118`, `ai/routing.yaml:126`). The comment says dev-mac is used on "all 3 machines". So server A probably had both gates off (not verified on the host).
- `systemctl --user` needs no sudo. So `no-sudo` does not catch it on any profile.
- `PROFILE_GUARDS=0` on dev-mac (`ai/profiles/dev-mac.env:15`) removes all Claude ask and deny rules (`ai/adapters/claude.sh:801`, `ai/adapters/claude.sh:817`).
- `gh pr create` passes `gh-write`, because `GH_OWN_GATES` hands it to `pr-rules` (`hooklib.py:1612`). `pr-rules` checks the body only, not the owner's request.

## Fact 1: how the existing gates detect commands and the owner's OK

Paths in this section are under `ai/marketplace/plugins/ai-core/hooks/`.

- One router handles every hook event for Claude and Codex (`router.py:1-27`). Matching is "regex, globs and project state. No LLM, no network."
- The shell parser splits a command into stages with the program, arguments, operator and redirections (`hooklib.py:40-44`, `hooklib.py:61`). It strips wrappers such as `env`, `timeout` and `rtk` (`hooklib.py:231`). It reads the inner text of `bash -c` and `eval` (`hooklib.py:268`).
- `runs_stdin_as_code` knows when `bash -s` or `sh` reads its program from stdin (`hooklib.py:413`). Today only the curl-to-shell check uses it (`hooklib.py:429`).
- Heredoc bodies are not in the stages. `script_writes` scans the raw command text for them (`hooklib.py:285`).
- Gates return `None`, `("ask", msg)` or `("deny", msg)` (`router.py:1592`). `GATES` maps a rule id to its function (`hooklib.py:2187`).
- The owner's OK for a merge: at `UserPromptSubmit`, `on_user_prompt` strips pasted output (`router.py:257`) and calls `remember_merge_ok` (`router.py:213`). That stores `merge_ok` in the session state (`router.py:290-299`). A later prompt without the word clears it.
- `owner_merge_ok` accepts "merge", "approve", "lgtm" and RO and RU forms. It refuses a question or a negation such as "don't merge yet" (`hooklib.py:1488-1519`).
- `gate_merge` denies until `merge_ok` is set (`hooklib.py:1573`). The deny text tells the agent that the owner can say merge in the next message (`router.py:1599-1600`).
- `gate_gh` returns `ask` for each gh write that is not a PR command (`hooklib.py:1617`).
- Codex has no hook `ask`. The router turns `ask` into `deny` for Codex (`router.py:612-621`). The Codex deny text points to `sudo ai-gate-skip`. On dev-mac that tool may not exist.
- The owner can skip a gate for up to 60 minutes with `sudo ai-gate-skip` (`ai/routing.yaml:29`, `router.py:1608`).

How an `ask-first` gate can reuse this:

1. A new function `owner_go_ok(prompt)` next to `owner_merge_ok`. It accepts "go", "do it", "yes", "approved", "da", "давай". It refuses a question and a negation.
2. `on_user_prompt` stores `go_ok` with the same pattern as `remember_merge_ok`. The next prompt without the word clears it.
3. `gate_ask_first(ctx, cmd, stages)` finds a high-impact stage. With `go_ok` set, it passes. Else Claude gets `ask` and Codex gets `deny`. The text says: "State the plan, the risk and the undo. Wait for the owner's OK."
4. The Codex path works with the typed OK. It does not need `ai-gate-skip`.

## Fact 2: Claude Code permissions and hooks

- Rules are checked in the order deny, ask, allow. "A matching ask rule prompts even when a more specific allow rule also matches." <https://code.claude.com/docs/en/permissions>
- "Permission rules are enforced by Claude Code, not by the model. Instructions in your prompt or `CLAUDE.md` shape what Claude tries to do, but they don't change these rules." <https://code.claude.com/docs/en/permissions>
- `bypassPermissions` "Skips permission prompts, except for the actions no mode auto-approves". That list includes "Tools matched by an explicit ask rule". <https://code.claude.com/docs/en/permissions>, <https://code.claude.com/docs/en/permission-modes>
- Ask and deny rules apply to each subcommand. This includes a subshell, a command substitution and a `for` body. Example: `cd /tmp && git clean -f` still prompts. <https://code.claude.com/docs/en/permissions>
- A Bash rule "isn't a security boundary around the program". `Bash(rm *)` does not stop `/bin/rm -rf build/` or `bash -c 'rm -rf build/'`. <https://code.claude.com/docs/en/permissions>
- "Bash permission patterns that try to constrain command arguments are fragile." The docs point to PreToolUse hooks for this. <https://code.claude.com/docs/en/permissions>
- PreToolUse `permissionDecision` values: `allow`, `deny`, `ask` ("prompts the user to confirm") and `defer`. Precedence between hooks: `deny` > `defer` > `ask` > `allow`. <https://code.claude.com/docs/en/hooks>
- "PreToolUse hook decisions don't bypass permission rules." A matching ask rule still prompts when a hook returns `allow`. <https://code.claude.com/docs/en/permissions>
- A hook that exits with code 2 "stops the tool call before permission rules are evaluated". <https://code.claude.com/docs/en/permissions>
- Managed settings have the highest precedence. No other level can override a managed permission rule. <https://code.claude.com/docs/en/permissions>
- `UserPromptSubmit` gets the submitted text in `prompt`. Pasted text arrives expanded. <https://code.claude.com/docs/en/hooks>
- Auto mode blocks by default: "Production deploys and migrations", "Force push", `git reset --hard`, "Irreversibly destroying files that existed before the session", and "Merging a pull request no human has approved". It allows "Pushing to any branch of the repository you're working in". <https://code.claude.com/docs/en/permission-modes>
- In auto mode, "To require a human checkpoint before these commands ... add `permissions.ask` rules." A stated limit such as "don't push" is a block signal. "For a hard guarantee, add a deny rule instead." <https://code.claude.com/docs/en/permission-modes>

## Fact 3: OpenAI Codex

- Rules (execpolicy) "control which commands Codex can run outside the sandbox". They are experimental. Files: `~/.codex/rules/*.rules` and `<repo>/.codex/rules/` in a trusted project. <https://learn.chatgpt.com/docs/agent-configuration/rules> (redirect from `developers.openai.com/codex/rules`)
- `prefix_rule(pattern = [...], decision = ...)` with `allow`, `prompt` or `forbidden`. With several matches, "the most restrictive decision" wins. <https://learn.chatgpt.com/docs/agent-configuration/rules>
- Codex splits `bash -lc` scripts that are a plain chain joined by `&&`, `||`, `;` or `|`. With redirection, substitution, variables or control flow, it does not split, and matches the whole call. <https://learn.chatgpt.com/docs/agent-configuration/rules>
- "A command rule can also require review inside the sandbox." <https://learn.chatgpt.com/docs/agent-approvals-security>
- `on-request` lets sandbox-allowed commands run without approval. `never` turns approval prompts off. Network is off by default. <https://learn.chatgpt.com/docs/agent-approvals-security>
- A Codex PreToolUse `ask` is "parsed but not supported yet". Codex marks the hook run as failed "and continues the tool call". Tool hooks are "a useful guardrail, not a complete enforcement boundary." <https://learn.chatgpt.com/docs/hooks>
- This setup pins Codex to `workspace-write` and `on-request`, with `never` allowed for `codex exec` (`ai/adapters/codex.sh:186-194`).

## Fact 4: Anthropic guidance on autonomy

- "Humans should retain control over how their goals are pursued, particularly before high-stakes decisions are made." <https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents>
- Claude Code "must ask for human approval before taking any actions that modify code or systems" by default. <https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents>
- "Agents can then pause for human feedback at checkpoints or when encountering blockers." <https://www.anthropic.com/engineering/building-effective-agents>
- The auto mode post names this failure "overeager": the agent "takes initiative beyond what the user would approve". <https://www.anthropic.com/engineering/claude-code-auto-mode>
- Same post: "The prompt establishes what is authorized; everything the agent chooses on its own is unauthorized until the user says otherwise." "Clean up my branches" does not authorize "a batch delete". <https://www.anthropic.com/engineering/claude-code-auto-mode>
- Same post, on prompt fixes for consent signals: "We've tried prompt-engineering around this and haven't found a fix that doesn't cost more than it gains." <https://www.anthropic.com/engineering/claude-code-auto-mode>

The incident matches this pattern. "Prepare" authorized a plan and files, not a live start and an enabled boot unit.

## Design options

The options below use these risky classes:

1. `systemctl`, `service`, `launchctl`.
2. `reboot`, `shutdown`, `poweroff`.
3. `docker restart`, `docker stop`, `docker compose down` or `up -d`.
4. `crontab`, and writes to `~/.config/systemd/`, `/etc/systemd/` or `~/Library/LaunchAgents/`.
5. `ssh <host>` with a mutating command.
6. `kill`, `pkill`, `killall`.
7. `gh pr create` that the owner did not ask for.
8. `git push --force`.
9. `rm -r`.
10. DB writes (`psql -c 'DROP ...'`, `UPDATE`, `DELETE`).

### Option A: rule text only

- Mechanism: rewrite "Standing permission" (see the proposal below). Define "live host" and "high-impact".
- Catches: all ten classes in theory, if the model follows it. It also catches scripts, because the model wrote them.
- False positives: low. The model judges.
- Remote ssh: yes, as a rule.
- Codex: yes. The rendered AGENTS.md goes to both.
- Gap: a rule-only fix already failed once. Anthropic reports no cheap prompt fix for consent signals (Fact 4). It is not a gate.

### Option B: router gate `ask-first` (PreToolUse), typed OK like merge-approval

- Mechanism: new rule in `ai/routing.yaml` with `strength: gate` and no `profiles` limit. Logic in `hooklib.py`, reusing the stage parser and the `merge_ok` state pattern (Fact 1). Claude gets `ask`. Codex gets `deny` until the owner types "go".
- Also a file gate on Edit and Write for `**/systemd/**`, `**/LaunchAgents/**` and crontab files, like `worktree-first`.
- Catches: classes 1 to 4, 6, 8 to 10 by program and arguments, also inside `bash -c`. Class 5: `ssh host '<cmd>'` by parsing the remote text as a shell command. Class 7: `gh pr create` unless the owner's prompt in this session named a PR or a ship.
- `ssh host 'bash -s' < file`: the stage has redirection `<` to `file` (`hooklib.py:44`). The gate reads that local file and parses it. A heredoc body is in the raw text, as in `script_writes`. When it cannot read the script, it asks.
- False positives: medium. Read forms must pass: `systemctl status`, `systemctl --user list-units`, `docker ps`, `docker logs`, `crontab -l`, `journalctl`, `ssh host 'cat ...'`. A read-only verb list keeps them quiet.
- Remote ssh: yes, for the command text and for a local script on stdin. No, for a script that already lives on the remote host (`ssh host ./deploy.sh`). The gate must ask for unknown remote programs.
- Codex: yes, as deny with a typed OK. Codex hook gaps remain: some tool paths "can opt out of the default hook path" (<https://learn.chatgpt.com/docs/hooks>).
- Gap: a script file the agent wrote and then runs locally (`./setup.sh`) hides its commands. The gate can scan a script the session wrote, or ask for each new script run.

### Option C: Claude `permissions.ask` list plus Codex execpolicy `prompt`

- Mechanism: add ask rules to `claude_ask_rules` (`ai/adapters/claude.sh:800`). Examples: `Bash(systemctl *)`, `Bash(ssh *)`, `Bash(crontab *)`, `Bash(gh pr create*)`, `Bash(git push --force*)`. Add `prefix_rule(..., decision = "prompt")` to `~/.codex/rules/default.rules`.
- Catches: the plain forms of classes 1 to 10. Claude also catches subshells and command substitution (Fact 2).
- False positives: high. `Bash(systemctl *)` also asks for `systemctl status`. Argument patterns are "fragile" (Fact 2).
- Remote ssh: only as "every ssh asks". `bash -c '...'`, `/usr/bin/systemctl` and stdin scripts pass (Fact 2).
- Codex: yes, but rules are experimental. The behaviour of `prompt` under `approval_policy = "never"` is not documented on the page read.
- Cost: it needs `PROFILE_GUARDS=1` for ask rules, or a split so that dev-mac gets ask rules but no deny rules.
- Strength: an ask rule prompts even in `bypassPermissions` (Fact 2). It needs no code in the router.

### Option D: Claude auto mode with a stated environment

- Mechanism: run Claude in `auto` mode. A classifier checks each action against what the owner authorized. Set `autoMode.environment` for trusted repos and hosts. Add `permissions.ask` for checkpoints (Fact 2).
- Catches: by intent, not by text. Its defaults block production deploys, force push, `git reset --hard` and unapproved merges.
- False positives: the classifier "is deliberately conservative" (<https://www.anthropic.com/engineering/claude-code-auto-mode>). It may block routine work, which is less than full rights.
- Remote ssh: partly. It blocks "Interactive shells or port-forwards into a sensitive remote target" (<https://code.claude.com/docs/en/permission-modes>). It is not verified that it reads a script piped into `bash -s`.
- Codex: no. Claude only.
- Gap: a block is a deny, not "show the plan and wait". It also gives up `bypassPermissions`, which the owner uses now (`skipDangerousModePermissionPrompt: true` in `~/.claude/settings.json`).

### Summary table

| Option | Hard stop | Remote ssh | `bash -s < file` | Codex | False positives |
|---|---|---|---|---|---|
| A: rule text | No | Yes (as text) | Yes (as text) | Yes | Low |
| B: router gate | Yes | Yes, parsed | Yes, reads the file | Yes (deny + typed OK) | Medium |
| C: ask lists | Yes | All or nothing | No | Yes (experimental) | High |
| D: auto mode | Yes (deny) | Partly | Not verified | No | Medium, not tunable per command |

## Proposed text for "Standing permission"

```text
Standing permission
You have my permission to run low-risk work without a question. Low-risk work is reads, tests, and local edits and commits in a worktree. This applies to Claude Code, Codex and other agents.

Before a high-impact step, stop and ask me. High-impact steps are:
- A start, stop or restart of a service, a container or a server.
- A change to systemd, cron, launchd or the boot sequence.
- A deploy, or a change on a remote host or a live host.
- A PR, an issue, a message or another outward action that I did not ask for.
- A force push, a history rewrite or another destructive git command.
- A deletion of data, or a database write outside a test database.

A live host is a machine with services that run for me. Server A and the old Mac are live hosts.

For a high-impact step, show me this, then wait:
1. The plan: the exact commands and files.
2. The risk: what can break, and for whom.
3. The undo: how to go back.

My OK is good for that plan only. A new step needs a new OK.
"Prepare", "plan" or "set up" means: write the files and the plan. Do not start, enable or deploy.
When you are not sure about the risk, ask.
A gate, a denied call or a step only I can do also stops you. Then give me the exact command or step.
```

Each sentence has 25 words or fewer. The text has no em dash. Edit `ai/agents-md/55-git-workflow.md:5` to match: open the draft PR only when the owner asked for feature or fix work in this session.

## Recommendation

Option B, with Option A as the second layer.

1. B is a real stop, and it is the only option that works for Claude and Codex with one implementation.
2. B reuses tested parts: the stage parser, `bash -c` inner text, `runs_stdin_as_code`, and the typed OK state of merge-approval.
3. B can read a local script piped into `ssh host 'bash -s'`. The text options and the ask lists cannot do this.
4. B can tell `systemctl status` from `systemctl enable`. This keeps reads unblocked, which the ask lists (C) cannot do.
5. B has no `profiles` limit, so it also runs under dev-mac, where the incident happened.
6. A is still needed. No text gate sees a script that already lives on the remote host. The model must own that case.

Add Option C only for the few forms with no read variant, for example `Bash(reboot*)` and `Bash(shutdown*)`. An ask rule prompts even in `bypassPermissions` (Fact 2). Do not use D: it is Claude only, and it replaces "ask me" with a deny.

Test plan for B (before a PR): replay the incident commands. That is `systemctl --user enable myd-boot.service`, `myd server start`, an ssh with `bash -s < script.sh` that has `systemctl restart`, and `gh pr create --draft`. Each must stop. `systemctl status`, `docker ps` and `ssh host 'uptime'` must pass.

## Not verified

- The text "actions that are hard to reverse" in the Claude Code system prompt. No public primary source was found. This file cites the Anthropic posts in Fact 4 instead.
- A PreToolUse hook `ask` in `bypassPermissions` mode. The docs confirm that an explicit ask rule prompts there. They do not state the same for a hook `ask`. Test it before relying on it.
- Codex execpolicy `prompt` with `approval_policy = "never"` (the `codex exec` setting). The page read does not cover it.
- The active profile on server A. The comment in `ai/routing.yaml:118` says dev-mac is on all 3 machines. The host was not checked.
- Whether the auto mode classifier reads a script piped to `bash -s`.
- The Codex pages were read at the redirect target `learn.chatgpt.com`. The redirect came from `developers.openai.com`.
- `myd` was not inspected. Whether `myd server start` restarts other services is not known.
