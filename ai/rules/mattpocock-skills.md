# mattpocock/skills (pinned copies)

Pin: commit 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d (dated 2026-10-31). Source: https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/
GLOBAL (5): grilling, grill-me, wait-what, retro, writing-for-agents. Everything else is opt-in per project.

## Vendor rules (verbatim)
No routing text for AGENTS.md. The only block the vendor writes is from `setup-matt-pocock-skills` (opt-in projects only): "## Agent skills / ### Issue tracker / [one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`. / ### Triage labels ... / ### Domain docs / [one-line summary of layout: "single-context" or "multi-context"]. See `docs/agents/domain.md`."
`.agents/invocation.md`: "User-invoked: reachable only by the human typing its name. Set `disable-model-invocation: true` in the frontmatter (Claude Code) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (Codex)." and "Naming the tool is what gets it fired: ... spelling that out gets a higher hit rate than dropping a `/name` into prose."
writing-for-agents: "The pointer's wording, not its target, decides when the agent reaches the material, and how reliably." and "Front-load the leading word".

## When / when not
- grilling (model-invoked): the owner wants a plan stress-tested ("grill me"). Numbered question rounds, a recommended answer each, no action until confirmed. Not for "explain this code", not for "deep interview with ambiguity score" (OMC deep-interview).
- grill-me (typed only): runs grilling. wait-what (typed only): "that did not land, re-pitch" in STE with GLOSSARY.md terms. retro (typed only): after a coding session, environment fixes.
- writing-for-agents (model-invoked): any edit of a skill, AGENTS.md or CLAUDE.md. Not for README, app docs, settings.json (that is update-config).
- Opt-in group: to-spec, to-tickets, triage, wayfinder, implement (auto-commits: conflicts with commit-only-when-asked), implement-spec, grill-with-docs, domain-modeling, prototype, handoff, teach, and more (SPEC section 5). A pick pulls in its callees. Do not enable the ones that duplicate OMC or built-ins without an owner decision: research, code-review, tdd, diagnosing-bugs, pr. misc/* is frozen and in-progress/* is beta.

## Enforcement
- grill-me, wait-what and retro CANNOT be fired by the model, a hook or another skill. "Used every time" means the model suggests the command and the owner types it. Only grilling and writing-for-agents can be forced.
- L0 rows: `grill, stress-test a plan | grill, verifica planul, прогони план | grilling`; `owner says "did not land", nu am inteles, не понял | suggest the human type /wait-what; answer in short plain words`; `after a long session | suggest /retro`; `editing AGENTS.md, CLAUDE.md, SKILL.md | writing-for-agents first`.
- L3: PreToolUse on Edit or Write of `**/{AGENTS.md,CLAUDE.md,SKILL.md}` or under `.claude/skills/` gives "call Skill writing-for-agents before editing" (nudge, not deny). UserPromptSubmit regex "nu am inteles|не понял|wait what|re-pitch" gives "suggest /wait-what".
- L4: none (a gate would block the owner's own edits). L1 and L2: skip.
- Hermes does not honor user-only flags: all five are model-reachable there. Codex honors `allow_implicit_invocation: false`.

## Proof
Eval cases: `ai/evals/mattpocock-and-llmwiki.md`. Typed commands: the pass condition is the UserPromptExpansion log entry plus the response shape. A plain-text mention must not expand anything.
- Signals: Skill tool_use `grilling` or `writing-for-agents`. UserPromptExpansion `command_name` in {grill-me, wait-what, retro}. Names are bare (copies, no plugin prefix): match `(^|:)grilling$`.

## Setup checklist
1. Do NOT use `claude plugin install mattpocock-skills@claude-plugins-official` (all 27 skills, auto-update on) or `npx skills@latest add` (unpinned). Never run its `scripts/link-skills.sh` (it runs `rm -rf`).
2. Pinned copies, done by the installer: clone, `git checkout 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`, read the five folders, copy whole folders (keep `agents/openai.yaml`): productivity/{grilling,grill-me,wait-what,writing-for-agents} and engineering/retro into `~/.agents/skills/` (shared: Codex, opencode, Hermes project convention) and a link for Claude (`~/.claude/skills/`). One route per agent: two routes give every skill twice. Hermes also `~/.hermes/skills/`.
3. Keys: none. Settings: none. Updating means a new reviewed checkout, never an auto-update.
4. Per project (opt-in only): `/setup-matt-pocock-skills` once. It writes `docs/agents/*.md`, an `## Agent skills` block, and may run `git init`, `git remote add origin` and `gh label create`. Trap: "If CLAUDE.md exists, edit it" lands the block in CLAUDE.md. Tell it to edit AGENTS.md.
5. Verify: `ls ~/.agents/skills/{grilling,grill-me,wait-what,retro,writing-for-agents}/SKILL.md`. `/skills` lists them. Typed `/wait-what` expands. "grill me on X" calls Skill `grilling`.
6. Cleanup: delete exactly those five folders under `~/.claude/skills`, `~/.agents/skills`, `~/.hermes/skills`. Per project: `docs/agents/`, the block, labels.
See also `ai/skills/README.md`.
