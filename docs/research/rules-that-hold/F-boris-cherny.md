# F: Boris Cherny and the Claude Code team: setup, rules, enforcement

Research date: 2026-11-20. Read-only. Raw downloads are in `plan-research/raw/` (tweets.txt, cc-files.txt, bcherny-tips-draft.md, docs-best-practices.md, docs-memory.md).

Source quality key:
- **Primary**: his own post (tweet text fetched through the fxtwitter API), his own repo, an official Anthropic doc or post.
- **Secondary**: a third party reports or transcribes his words. Marked as such.
- **Not verified**: I could not open the source.

---

## 1. Boris Cherny's own setup (dated practices with quotes)

### 1.1 Thread "my setup", 2026-01-02 (primary, https://x.com/bcherny/status/2007179832300581177)

| # | Practice | Quote | URL |
|---|---|---|---|
| 0 | Mostly vanilla | "My setup might be surprisingly vanilla! Claude Code works great out of the box, so I personally don't customize it much." | https://x.com/bcherny/status/2007179832300581177 |
| 1-2 | Parallel sessions | 5 local sessions in numbered terminal tabs, plus 5-10 on claude.ai/code, some started from the iOS app (summary of tweets 1-2 via threadreader). | https://threadreaderapp.com/thread/2007179832300581177.html |
| 3 | Model | "I use Opus 4.5 with thinking for everything ... since you have to steer it less and it's better at tool use, it is almost always faster than using a smaller model in the end." | https://x.com/bcherny/status/2007179838864666847 |
| 4 | Shared CLAUDE.md in git | "Our team shares a single CLAUDE.md for the Claude Code repo. We check it into git, and the whole team contributes multiple times a week. Anytime we see Claude do something incorrectly we add it to the CLAUDE.md, so Claude knows not to do it next time." | https://x.com/bcherny/status/2007179840848597422 |
| 5 | Update CLAUDE.md in code review | "During code review, I will often tag @.claude on my coworkers' PRs to add something to the CLAUDE.md as part of the PR. We use the Claude Code Github action" ("our version of ... Compounding Engineering"). | https://x.com/bcherny/status/2007179842928947333 |
| 6 | Plan mode first | "Most sessions start in Plan mode (shift+tab twice) ... go back and forth with Claude until I like its plan. From there, I switch into auto-accept edits mode and Claude can usually 1-shot it." | https://x.com/bcherny/status/2007179845336527000 |
| 7 | Slash commands with pre-computed context | "I use slash commands for every 'inner loop' workflow that I end up doing many times a day ... Commands are checked into git and live in .claude/commands/." /commit-push-pr "uses inline bash to pre-compute git status ... to avoid back-and-forth with the model". | https://x.com/bcherny/status/2007179847949500714 |
| 8 | Subagents | "code-simplifier simplifies the code after Claude is done working, verify-app has detailed instructions for testing Claude Code end to end". | https://x.com/bcherny/status/2007179850139000872 |
| 9 | PostToolUse formatter hook | "We use a PostToolUse hook to format Claude's code ... the hook handles the last 10% to avoid formatting errors in CI later." | https://x.com/bcherny/status/2007179852047335529 |
| 10 | Allow list, not skip | "I don't use --dangerously-skip-permissions. Instead, I use /permissions to pre-allow common bash commands that I know are safe ... Most of these are checked into .claude/settings.json and shared with the team." | https://x.com/bcherny/status/2007179854077407667 |
| 11 | Tools via CLI and MCP | Slack via MCP (shared in .mcp.json), BigQuery via the bq CLI, Sentry logs (threadreader summary). | https://threadreaderapp.com/thread/2007179832300581177.html |
| 12 | Long-running tasks | "(a) prompt Claude to verify its work with a background agent when it's done, (b) use an agent Stop hook to do that more deterministically, or (c) use the ralph-wiggum plugin ... --permission-mode=dontAsk or --dangerously-skip-permissions in a sandbox". | https://x.com/bcherny/status/2007179858435281082 |
| 13 | Verification (his top tip) | "probably the most important thing to get great results out of Claude Code -- give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality of the final result." "Make sure to invest in making this rock-solid." | https://x.com/bcherny/status/2007179861115511237 |

Reply on the same day, 2026-01-02 (primary, Threads): "Our checked in CLAUDE.md is 2.5k tokens. It covers: common bash commands - code style conventions - ui and content design guidelines - how to do state management, logging, error handling, gating, and debugging - pull request template". https://www.threads.com/@boris_cherny/post/DTCSBrFjvgk/our-checked-in-claude-md-is-k-tokens-it-covers-common-bash-commands-code-style (X version: https://x.com/bcherny/status/2007212366094811401, via https://zenn.dev/beagle/articles/_0019_keypoints_from_responses_of_boris, not opened on X.)

Other replies of 2026-01-02 to 2026-01-03 (secondary, Zenn summary, 2026-01-08): one git clone per parallel task, not worktrees; skills and slash commands are "interchangeable" for him; he leaves compaction timing to Claude; for verification "give Claude tools to verify its output and make sure it knows when ... to use them". https://zenn.dev/beagle/articles/_0019_keypoints_from_responses_of_boris

### 1.2 Thread "tips from the team", 2026-01-31 (primary, https://x.com/bcherny/status/2017742741636321619)

- Plan mode, 2026-01-31: "Start every complex task in plan mode. Pour your energy into the plan so Claude can 1-shot the implementation. One person has one Claude write the plan, then they spin up a second Claude to review it as a staff engineer. ... the moment something goes sideways, they switch back to plan mode and re-plan. Don't keep pushing." https://x.com/bcherny/status/2017742745365057733
- CLAUDE.md, 2026-01-31: "After every correction, end with: 'Update your CLAUDE.md so you don't make that mistake again.' Claude is eerily good at writing rules for itself. Ruthlessly edit your CLAUDE.md over time. Keep iterating until Claude's mistake rate measurably drops." https://x.com/bcherny/status/2017742747067945390
- Skills, 2026-01-31: "Create your own skills and commit them to git. Reuse across every project. ... If you do something more than once a day, turn it into a skill or command." Also a /techdebt command at session end. https://x.com/bcherny/status/2017742748984742078
- Subagents, 2026-01-31: "Offload individual tasks to subagents to keep your main agent's context window clean and focused." "Route permission requests to Opus 4.5 via a hook". https://x.com/bcherny/status/2017742755737555434
- Worktrees: "Spin up 3-5 git worktrees at once ... the single biggest productivity unlock". https://x.com/bcherny/status/2017742743125299476

### 1.3 Thread "customize", 2026-02-11 (primary, https://x.com/bcherny/status/2021699851499798911)

- Effort: "Personally, I use High for everything." https://x.com/bcherny/status/2021699860869902424
- Permissions: "Out of the box, we pre-approve a small set of safe commands. To pre-approve more, run /permissions and add to the allow and block lists. Check these into your team's settings.json." https://x.com/bcherny/status/2021700332292911228
- Sandbox: "Opt into Claude Code's open source sandbox runtime ... to improve safety while reducing permission prompts." https://x.com/bcherny/status/2021700506465579443
- Hooks: "Hooks are a way to deterministically hook into Claude's lifecycle. Use them to: Automatically route permission requests to Slack or Opus; Nudge Claude to keep going when it reaches the end of a turn ...; Pre-process or post-process tool calls, eg. to add your own logging". https://x.com/bcherny/status/2021701059253874861

Note: none of his hook examples injects reminder text to make Claude obey a rule. His hooks format, log, route permissions or keep Claude going.

### 1.4 Later 2026 posts (primary)

- 2026-03-24, auto mode: "no more permission prompts". https://x.com/bcherny/status/2036555259997462541
- 2026-03-30, hooks: SessionStart to "dynamically load in context", PreToolUse to "log every bash command", PermissionRequest to route prompts to WhatsApp, Stop to "poke Claude to keep going". https://x.com/bcherny/status/2038454343519932844
- 2026-04-16, auto mode for parallel work: "it means you can run more Claudes in parallel. Once a Claude is cooking, you can switch focus to the next Claude." https://x.com/bcherny/status/2044847849662505288
- 2026-04-16, /fewer-permission-prompts skill: scans history and "recommends a list of commands to add to your permissions allowlist". https://x.com/bcherny/status/2044847851591856461
- 2026-04-16, effort: "I use xhigh effort for most tasks, and max effort for the hardest tasks." https://x.com/bcherny/status/2044847856872546639
- 2026-04-16, verification and /go: "This has always been a way to 2-3x what you get out of Claude, and with 4.7 it's more important than ever." /go makes Claude "1. Test itself end to end using bash, browser, or computer use 2. Run the /simplify skill 3. Put up a PR". https://x.com/bcherny/status/2044847858634064115
- 2026-05-28, Opus 4.8: high effort by default, "For hard problems and long-running async work, switch to xhigh." Dynamic workflows "token-intensive, so save it for your biggest jobs". https://x.com/bcherny/status/2060048875918930045 , https://x.com/bcherny/status/2060048877944778995

### 1.5 Talks and interviews

- YC Lightcone "Inside Claude Code With Its Creator Boris Cherny" (date not shown on the transcript page; about February 2026, not verified). Secondary transcript: personal CLAUDE.md "is just two lines" (auto-merge each PR; post each PR to the team stamps channel). On a big file: "my recommendation would be to delete your [CLAUDE.md] and just start fresh"; "do the minimal possible thing in order to get the model on track"; "with every model you have to add less and less." https://podcasttranscript.ai/library/inside-claude-code-with-its-creator-boris-cherny , https://engineeredintelligence.substack.com/p/how-the-claude-code-team-works
- YC Startup School 2026 with Diana Hu, 2026-07-28 (secondary). Quoted by Rohan Paul on 2026-07-30: "every 6 months, delete your claude.md file, delete your skills, and delete your hooks. Then see what the model does. It might surprise you. For Opus 5, we strongly recommend trying to delete all of these things because the model may no longer need the extensive instructions that were necessary for previous models." https://x.com/rohanpaul_ai/status/2082695402953031825 . Transcript excerpt: "we deleted 80% of the system prompt"; "something that you did for one model maybe three months ago, it just might not translate". https://spoken.md/episode/boris-cherny-building-claude-code-1000778651350 . A summary (barath.ai, 2026-08-02) describes the method as ablation: remove, use, restore a line only when the model keeps failing; names "overspecifying" as the most common failure; mentions `CLAUDE_CODE_SIMPLE=1`. These are the author's paraphrases. https://www.barath.ai/learnings/boris-cherny-yc-startup-school-2026
- Lenny's Podcast 2026-02-19 and Sequoia AI Ascent 2026: found only in search snippets; not opened (not verified).

### 1.6 How his advice changed (primary)

- 2025-04-13 draft post in his own repo: "tune instructions (eg. to clarify cases, or add 'IMPORTANT', 'YOU MUST', etc.) to improve adherence." https://github.com/bcherny/bcherny.github.io/blob/master/_drafts/Tips-for-Using-Claude-Code.md
- 2026 official docs: "If Claude keeps ignoring a line that is in CLAUDE.md, adding IMPORTANT probably won't fix it. Either the file has grown long enough that the line gets lost, or the line is a rule that can't have exceptions, in which case it belongs in a hook." https://code.claude.com/docs/en/best-practices
- 2026-07: delete CLAUDE.md, skills and hooks every 6 months and re-add only what the model still needs (secondary, above).

---

## 2. bcherny GitHub repos with agent setup files

Method: `gh api users/bcherny/repos` (50 most recent), then the tree of each own (non-fork) repo active since 2024, filtered for CLAUDE, AGENTS.md, skill, .cursor, copilot. Code search for `filename:CLAUDE.md user:bcherny` returned nothing.

| Repo | File | Size | Content kind | History |
|---|---|---|---|---|
| bcherny/bcherny.github.io | `_drafts/Tips-for-Using-Claude-Code.md` | 18,046 B | Unpublished blog draft, 2025-04-13. It is the early form of the "Claude Code best practices" post. | 4 commits, 2025-04-13 to 2025-04-14 |
| bcherny/json-schema-to-typescript | `.github/workflows/claude.yml` | 1,055 B | Stock `@claude` mention workflow (anthropics/claude-code-action@v1), `contents: read`. | 3 commits: added 2025-05-19, edited 2026-08-01 and 2026-08-28 (tooling upgrades) |
| bcherny/sandbox-runtime | fork of anthropics/sandbox-runtime | n/a | The sandbox he recommends | fork |

Result: **no CLAUDE.md, AGENTS.md, .claude/ folder or skills in any public bcherny repo.** So there is no git history of a Boris CLAUDE.md to measure. His own words describe the file: the team file is 2.5k tokens (2026-01-02), his personal file is two lines (YC Lightcone, secondary).

---

## 3. Official guidance from the Claude Code team

### 3.1 Best practices page (https://code.claude.com/docs/en/best-practices, fetched 2026-11-20, no date on the page)

(a) Size and content of instruction files
- "Only write down what Claude can't find by reading the repo, or what it would otherwise spend time rediscovering every session."
- Test: "1. Could it find this by reading the code? 2. Would it actually go and look? If both are yes, leave it out."
- "every line in it takes a little of Claude's attention on every task, whether it's relevant or not."
- Keep: exact test, typecheck and lint commands; places where the code misleads; decisions not in the repo; "Anything you've had to correct twice already". Sample file: 9 lines.
- `/init` then "the work is mostly removing lines"; the memory guide "recommends staying under 200". `/doctor prompt-audit` flags instructions "written for older models", dead paths and contradictions.

(b) Hook, permission rule, skill, subagent
- Two kinds: non-deterministic (prompt, CLAUDE.md, skill: "there's no guarantee that it'll follow your instructions") and deterministic (hook, deny rule, managed setting: "Claude Code applies this every time").
- "If you keep adding emphasis to a CLAUDE.md line and Claude still misses it, that's a sign the line belongs in a hook. The reverse holds too: if you have hooks for things that are only preferences, delete them and let Claude decide."
- "A prompt or agent hook asks another model to decide, so it isn't deterministic either. For real enforcement, use a command, http, or mcp_tool hook, and add onFailure: 'block'".
- "a hook is for a rule with zero exceptions".
- `deny` rules "hold in every permission mode, including auto and bypassPermissions". "Rules match tool calls, not intent".
- "keep the enforced set small. Every hook and deny rule will occasionally fire when it shouldn't, and someone has to maintain each one. If you ever find yourself at forty of them, most are probably preferences that Claude could have weighed on its own."
- Auto mode "is a classifier model ... your 'never' rules belong in deny rules or hooks." A rule said in chat "can get lost when the conversation compacts".
- Skills for team procedures; side-effect skills get `disable-model-invocation: true`. "The CLAUDE.md rule applies to skills too".
- MCP: connected servers "add their tool names and instructions to the context even when you're not using them", so turn off unused ones. Prefer a CLI when one exists.

(c) Verification
- "Give Claude something it can run that comes back pass or fail."
- "the single most useful line in your CLAUDE.md is the command that runs it."
- Ladder: prompt, `/goal`, Stop hook (exit 2; `pnpm tsc --noEmit 1>&2 || exit 2`), `/code-review` in a fresh subagent. Ask for evidence: "'All tests pass' on its own tells you very little".
- Reviewer prompt must say "skip style": "A reviewer that's asked to find problems will always find something."

(d) Measured: nothing numeric on adherence on this page.

### 3.2 Memory page (https://code.claude.com/docs/en/memory)

- "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence." Imports "don't reduce its context cost".
- "if two instructions contradict each other, Claude may pick one arbitrarily."
- "CLAUDE.md content is delivered as a user message after the system prompt ... there's no guarantee of strict compliance, especially for vague or conflicting instructions."
- If your CLAUDE.md sets commit or PR rules, turn off the built-in ones with `includeGitInstructions` (instructions can compete with Claude Code's own).
- "If the instruction is something that must run at a specific point, such as before every commit or after each file edit, write it as a hook instead."
- User rules (`~/.claude/rules/`) and project rules: "if a user rule and a project rule conflict, Claude may follow either one".
- When to add: "Claude makes the same mistake a second time"; a review catches it; you type the same correction again.
- "By default Claude reads AGENTS.md only when you have no CLAUDE.md or CLAUDE.local.md" in the working directory or above. A SessionStart hook that prints AGENTS.md: "remove it".

### 3.3 Extend Claude Code / features overview (https://code.claude.com/docs/en/features-overview)

- "Build your setup over time": trigger table. "Claude gets a convention or command wrong twice: Add it to CLAUDE.md". "You want something to happen every time without asking: Write a hook". "A second repository needs the same setup: Package it as a plugin".
- Context cost: CLAUDE.md "Every request"; skills "Low (descriptions every request)"; MCP "Low until a tool is used" (tool search on by default); hooks "Zero, unless hook returns additional context".
- "Put guardrails in hooks. An instruction like 'never edit .env' in CLAUDE.md or a skill is a request, not a guarantee."
- Output styles are for "A voice, length, or format you want in every response".
- "If descriptions are vague or overlap, Claude may load the wrong skill or miss one".

### 3.4 "Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents", Michael Segner, 2026-06-18
https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more
- "Keep CLAUDE.md under 200 lines, give it an owner, and review changes to it like code."
- "A real guardrail needs to be deterministic." "The model choosing to run a formatter is different from the formatter running automatically."
- Adherence "can slip in long sessions, ambiguous situations". No measured numbers.

### 3.5 Anthropic engineering posts

- "Effective context engineering for AI agents", 2025-09-29: "the minimal set of information that fully outlines your expected behavior"; context is "a finite resource with diminishing marginal returns"; against "a laundry list of edge cases"; "If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better." https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- "Writing effective tools for agents", Ken Aizawa, 2025-09-11: "More tools don't always lead to better outcomes"; evaluation with "held-out test sets"; Claude Code caps tool responses at 25,000 tokens. https://www.anthropic.com/engineering/writing-tools-for-agents
- "Claude Code sandboxing", 2025-10-20: "sandboxing safely reduces permission prompts by 84%" (internal use); "approval fatigue". https://www.anthropic.com/engineering/claude-code-sandboxing
- "Equipping agents for the real world with Agent Skills", 2025-10-16: progressive disclosure; only name and description load at start. Seen through search snippets only (not opened). https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- "Harness design for long-running application development", Prithvi Rajasekaran, 2026-03-24: agents "reliably skew positive when grading their own work"; "Separating the agent doing the work from the agent judging it proves to be a strong lever"; "every component in a harness encodes an assumption about what the model can't do on its own" and these "can quickly go stale as models improve". Measured: solo run 20 min and $9 versus full harness 6 h and $200. https://www.anthropic.com/engineering/harness-design-long-running-apps
- Auto mode post ("How we built Claude Code auto mode", about March 2026): secondary numbers only: false positives 8.5% to 0.4% on n=10,000 real calls; false negatives 17% on n=52 overeager actions. Not opened (not verified). https://www.digitalapplied.com/blog/claude-code-auto-mode-classifier-numbers-published
- The old post URL https://www.anthropic.com/engineering/claude-code-best-practices now redirects (308) to the docs best-practices page.

---

## 4. anthropics/claude-code repo as an example

Tree of `main` on 2026-11-20 (https://github.com/anthropics/claude-code):

| Item | Size | What it is |
|---|---|---|
| `CLAUDE.md` | 2,218 B (about 330 words, 45 lines) | One topic only: security hardening for GitHub Actions that call Claude (egress-firewall runner, network allow list, `--permission-mode auto`, minimal `permissions:`). |
| `.claude/commands/commit-push-pr.md` | 795 B | `allowed-tools` list in front matter; inline bash pre-computes `git status`, `git diff HEAD`, branch. |
| `.claude/commands/dedupe.md` | 1,676 B | Parallel agents search duplicates; only `./scripts/gh.sh` and a comment script are allowed. |
| `.claude/commands/triage-issue.md` | 5,550 B | Label-only triage; tools limited to wrapper scripts. |
| `.claude/agents/`, `.claude/settings.json`, skills | none | Not present. |
| Workflows that call Claude | `claude.yml` (2,142 B), `claude-issue-triage.yml` (2,568 B), `claude-dedupe-issues.yml` (4,227 B) | `@claude` mentions, triage, dedupe. |
| Enforcement of the CLAUDE.md rule | `workflow-hardening.yml` (648 B) plus `.github/scripts/check_workflow_hardening.py` | CI fails when a Claude job breaks protection 1 or 3. |

CLAUDE.md git history: 2 commits.
- b1922f29, 2026-09-25: file created, 39 lines ("Add the network allow list, a security check and CLAUDE.md guidance").
- 7dbaea23, 2026-09-29: +3/-4 lines (model floor `claude-opus-4-6`; rewrote the claude.yml exception). Net about the same size.

What it shows: the team's public CLAUDE.md is small and holds only facts that Claude cannot infer (why the runner and flags exist). Each rule in it is backed by a CI check: "Do not skip or weaken the check." The rule text explains; the check enforces. Tool limits live in each command's `allowed-tools`, not in prose. The team's real 2.5k-token CLAUDE.md is in Anthropic's private monorepo and is not public.

---

## 5. Direct answers to the five questions

1. "Claude ignores my CLAUDE.md, what do I do?" No Boris quote found. Team docs: check `/context all` that it loaded; make the line specific; remove conflicts; if it must hold, move it to a hook; "adding IMPORTANT probably won't fix it". https://code.claude.com/docs/en/memory , https://code.claude.com/docs/en/best-practices . Boris (YC Lightcone, secondary): delete the file "and just start fresh".
2. "Should I use hooks to enforce rules?" Yes, only for zero-exception rules, and only command, http or mcp_tool hooks; prompt or agent hooks are "not deterministic either". Delete hooks that encode preferences. Boris uses hooks for formatting (2026-01-02), Stop-hook verification (2026-01-02), permission routing and logging (2026-02-11, 2026-03-30).
3. "How long should CLAUDE.md be?" Team file 2.5k tokens (Boris, 2026-01-02). His personal file: two lines (secondary). Docs: under 200 lines. Sample in docs: 9 lines.
4. "How many skills or MCP servers is too many?" No number from Boris or the docs. Closest: "If you ever find yourself at forty of them [hooks and deny rules], most are probably preferences"; turn off unused MCP servers; vague or overlapping skill descriptions cause wrong picks.
5. "How do you test that a setup works?" Docs: for each hook, provoke it ("ask Claude to add a badly indented line"; "ask Claude for a change that breaks a type"); `/context all`; `/doctor prompt-audit`; `InstructionsLoaded` hook to log loads. Boris: "Keep iterating until Claude's mistake rate measurably drops" (2026-01-31); ablation every 6 months (2026-07-28, secondary).

---

## 6. Target: one owner, Claude Code plus Codex, personal setup repo

Current state (from the brief):
- A 3,200-word always-loaded rules file with 83 instructions. That is about 4,200 tokens (my estimate at 1.3 tokens per word). The team file is 2.5k tokens for a whole product team.
- 38 rules in a table. A hook injects 27 of them as reminder text. Measured: 75% are not followed.
- A 5,600-line Python hook router with 11 command gates, installed into every project.

Goal: small, generic, plug-and-play, and rules hold in every session.

### 6.1 What Boris would keep, cut and add (ranked by expected effect)

1. **Cut the 27 hook-injected reminders.** A reminder is text; text is a request. "A prompt or agent hook asks another model to decide, so it isn't deterministic either" (docs). Your 75% miss rate is the measurement that confirms it. Each one becomes either a blocking check (exit 2) or nothing. Hooks cost "Zero, unless hook returns additional context" (features overview), so these 27 are the only hooks that cost context.
2. **Shrink the always-loaded file to what Claude cannot see.** Target under 200 lines and about the team's 2.5k tokens or less; Boris's own personal file is two lines. Apply the docs test "Could it find this by reading the code? Would it actually go and look?" Delete instead of rewording: "do the minimal possible thing in order to get the model on track" (Boris, YC Lightcone).
3. **Make verification the center: one check command plus a Stop hook.** "give Claude a way to verify its work ... 2-3x the quality" (2026-01-02, repeated 2026-04-16). Per project, the "single most useful line" is the check command; enforce it with `make check-fast 1>&2 || exit 2` as a Stop hook. This replaces many "done means" rules.
4. **Keep a small enforced set; express it in native settings, not a router.** Zero-exception rules only (secrets in commits, push to main, merge without approval, `--no-verify`, `.env` reads). Use `permissions.deny` and `ask` (they hold "in every permission mode"), the sandbox, and a few short command hooks with `onFailure: "block"`. "keep the enforced set small ... If you ever find yourself at forty of them, most are probably preferences". Boris pre-allows safe commands in a checked-in settings.json (2026-01-02, 2026-02-11).
5. **Delete gates that encode preferences.** "if you have hooks for things that are only preferences, delete them and let Claude decide." Gates like "graphify before rg" or "load a skill before editing AGENTS.md" are preferences with exceptions. A 5,600-line router is code you must maintain; every hook "will occasionally fire when it shouldn't".
6. **Move procedures out of the always-loaded file into skills.** PR template, git workflow, release, ship: "If an entry is a multi-step procedure ... move it to a skill" (memory docs). Side-effect skills get `disable-model-invocation: true`, so they cost zero context and run only when typed. Boris: "If you do something more than once a day, turn it into a skill or command" (2026-01-31).
7. **Move reply-format rules into an output style.** The 60-word limit, the reply shape and the writing style are about "A voice, length, or format you want in every response" (features overview). An output style is a separate, switchable channel; it stops these rules from competing with project facts in CLAUDE.md.
8. **Pre-compute context in commands instead of rules.** The team's /commit-push-pr "uses inline bash to pre-compute git status" (2026-01-02) and limits tools in `allowed-tools`. A rule such as "git status first, then add files by name" becomes part of the command, not a sentence to remember.
9. **Remove conflicts and layered precedence.** "if two instructions contradict each other, Claude may pick one arbitrarily". Lines such as "AGENTS.md and the gates win over OMC" admit that conflicting sources are loaded. Load fewer sources, run `/doctor prompt-audit`, and set `includeGitInstructions` off if you keep your own commit rules.
10. **Grow the file only from observed mistakes, and prune.** "Anytime we see Claude do something incorrectly we add it" (2026-01-02); "Ruthlessly edit ... until Claude's mistake rate measurably drops" (2026-01-31); docs trigger: "wrong twice". Keep a short log of each mistake and the line it caused, so a line without a log entry can go.
11. **Use a separate reviewer for "done".** Boris's verify-app and code-simplifier subagents (2026-01-02); the harness post: agents "reliably skew positive when grading their own work" (2026-03-24). Use `/code-review` or a verify subagent with "skip style".
12. **Ablate on every model release, or every 6 months.** "delete your claude.md file, delete your skills, and delete your hooks. Then see what the model does" (2026-07-28, secondary). Run a fixed set of 5 to 10 real tasks with the full setup and with none, then restore only the lines that change the result. "every component in a harness encodes an assumption about what the model can't do on its own" (2026-03-24).

### 6.2 What does not transfer

- **Team-maintained CLAUDE.md updated in code review** (`@.claude` on coworkers' PRs, "whole team contributes multiple times a week"). One owner has no reviewers; the substitute is the mistake log in rec. 10.
- **One file per repo, owned by the repo.** Boris's rules live in the product repo, not in a personal setup pushed into every project. A generic file installed everywhere cannot hold the repo facts that the docs say are the valuable part.
- **Managed settings** as the place for policy. They need an organization admin console or MDM; one person can use `~/.claude/settings.json` instead.
- **Parallelism and model budget**: 10-15 sessions, Opus at xhigh or max for most work, dynamic workflows "token-intensive". This needs Anthropic-level token budgets.
- **Internal tools**: the team Slack "stamps" channel, BigQuery skill, the Claude Chrome extension tests of claude.ai/code, routing permissions to Opus or Slack.
- **CI enforcement pattern** of anthropics/claude-code (egress-firewall runner, `workflow-hardening.yml`) needs GitHub Actions on a public product repo; the idea (rule text plus a check that fails) transfers, the infrastructure does not.
- **Codex.** All Boris and team guidance is for Claude Code. Hooks, deny rules, output styles and skills have different forms or do not exist in Codex. A shared AGENTS.md is the only common layer; enforcement must be per tool.

### 6.3 Could not confirm

- A direct Boris answer to "Claude ignores my CLAUDE.md" or "should I use hooks to enforce rules". Only the team docs answer these.
- Any number from Boris or the docs for "too many skills or MCP servers". Only the "forty" hooks and deny rules remark exists.
- The full YC Startup School 2026 transcript (paywalled after an excerpt). The "delete every 6 months" quote comes from Rohan Paul's post; `CLAUDE_CODE_SIMPLE=1` and "overspecifying" come from a summary.
- The exact date of the YC Lightcone episode, and the Lenny's Podcast (2026-02-19) and Sequoia AI Ascent 2026 transcripts.
- The auto mode engineering post and the Agent Skills post (secondary or snippet only).
- Any adherence measurement by Anthropic for CLAUDE.md length or for hook-injected reminders. The docs say "reduce adherence" but give no number.
- Boris's private hooks and settings files. No public repo of his has them.
