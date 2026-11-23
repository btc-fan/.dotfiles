# mattpocock/skills (copies at the newest stable tag)

Version: newest stable release (SPEC 23). First read and audited at intake: commit 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d (dated 2026-10-31); all 27 re-read 2026-11-15 at 5863806. Source: https://github.com/mattpocock/skills
Owner 2026-11-15: the whole official plugin set (27 skills, the list in upstream `.claude-plugin/plugin.json`), unchanged copies. misc/* and in-progress/* stay out (the plugin leaves them out too).
GLOBAL (6): grilling, grill-me, wait-what, retro, writing-for-agents, ask-matt.
PER PROJECT (21), `skills:` line in `.ai/enabled`: default for every project (no tiers since 2026-11-15): grill-with-docs, domain-modeling, to-spec, to-tickets, tdd, pr, diagnosing-bugs, implement, research, handoff, wayfinder, prototype (+ callees codebase-design, code-review). Opt-in (`ai-adopt --skills`): implement-spec, improve-codebase-architecture, triage, wizard, to-questionnaire, teach, setup-matt-pocock-skills.
How each one works, when to use it, examples: the global skill `skills-guide` (ai/skills/skills-guide/SKILL.md) and docs/GUIDE.md.
## Vendor rules (verbatim)
No routing text for AGENTS.md. The only block the vendor writes is from `setup-matt-pocock-skills` (opt-in projects only): "## Agent skills / ### Issue tracker / [one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`. / ### Triage labels ... / ### Domain docs / [one-line summary of layout: "single-context" or "multi-context"]. See `docs/agents/domain.md`."
`.agents/invocation.md`: "User-invoked: reachable only by the human typing its name. Set `disable-model-invocation: true` in the frontmatter (Claude Code) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (Codex)." and "Naming the tool is what gets it fired: ... spelling that out gets a higher hit rate than dropping a `/name` into prose."
writing-for-agents: "The pointer's wording, not its target, decides when the agent reaches the material, and how reliably." and "Front-load the leading word".

## When / when not
- grilling (model-invoked): the owner wants a plan stress-tested ("grill me"). Numbered question rounds, a recommended answer each, no action until confirmed. Not for "explain this code", not for "deep interview with ambiguity score" (OMC deep-interview).
- grill-me (typed only): runs grilling. wait-what (typed only): "that did not land, re-pitch" in STE with GLOSSARY.md terms. retro (typed only): after a coding session, environment fixes.
- writing-for-agents (model-invoked): any edit of a skill, AGENTS.md or CLAUDE.md. Not for README, app docs, settings.json (that is update-config).
- Per project: the `skills:` line in `.ai/enabled` (`ai-adopt --skills a,b|none` replaces it; a rerun without --skills adds new defaults and keeps extras). A pick pulls in its callees (grill-with-docs, to-spec, to-tickets, diagnosing-bugs, triage: domain-modeling; tdd: codebase-design, code-review; implement, implement-spec: tdd, code-review, codebase-design; wayfinder: domain-modeling, research, prototype; improve-codebase-architecture: codebase-design, domain-modeling). Overlaps with OMC and built-ins: the tie-break table in skills-guide (Matt first).
- Feature flow (the `feature-kickoff` skill): grill-with-docs (questions, then GLOSSARY.md and docs/adr), for a feature touching 3+ files to-spec then to-tickets (slices with acceptance criteria and the verify-<app> feature each slice must pass), then slice by slice in the Done order (check-fast, verify evidence, e2e).
- Tracker: local only. `ai-adopt` writes `docs/agents/issue-tracker.md` (specs `docs/specs/`, tickets `docs/tickets/<feature>/`, research `docs/research/`, and a "Wayfinding operations" section: maps `docs/maps/<effort>/`, the upstream local-tracker format with our paths) and `docs/agents/domain.md` when missing; never `gh issue create` or labels without the owner.

## Enforcement
- grill-me, wait-what and retro CANNOT be fired by the model, a hook or another skill. "Used every time" means the model suggests the command and the owner types it. Only grilling and writing-for-agents can be forced.
- L0 rows: `grill, stress-test a plan | grill, verifica planul, прогони план | grilling`; `owner says "did not land", nu am inteles, не понял | suggest the human type /wait-what; answer in short plain words`; `after a long session | suggest /retro`; `editing AGENTS.md, CLAUDE.md, SKILL.md | writing-for-agents first`.
- L3: none since routing v4 (the `agent-docs` and `wait-what` nudges were removed: logs showed them ignored). UserPromptSubmit regex "nu am inteles|не понял|wait what|re-pitch" gives "suggest /wait-what".
- L4: none (a gate would block the owner's own edits). L1 and L2: skip.
- Hermes does not honor user-only flags: all five are model-reachable there. Codex honors `allow_implicit_invocation: false`.

## Proof
Eval cases: `ai/evals/mattpocock-and-llmwiki.md`. Typed commands: the pass condition is the UserPromptExpansion log entry plus the response shape. A plain-text mention must not expand anything.
- Signals: Skill tool_use `grilling` or `writing-for-agents`. UserPromptExpansion `command_name` in {grill-me, wait-what, retro}. Names are bare (copies, no plugin prefix): match `(^|:)grilling$`.

## Setup checklist
1. Do NOT use `claude plugin install mattpocock-skills@claude-plugins-official` (all 27 skills, auto-update on) or `npx skills@latest add` (unpinned). Never run its `scripts/link-skills.sh` (it runs `rm -rf`).
2. Copies at the newest stable tag (SPEC 23), done by the installer on every run: clone, `git checkout <commit of the newest vX.Y.Z tag>`, audit, read the five folders, copy whole folders (keep `agents/openai.yaml`): productivity/{grilling,grill-me,wait-what,writing-for-agents} and engineering/retro into `~/.agents/skills/` (shared: Codex, opencode, Hermes project convention) and a link for Claude (`~/.claude/skills/`). One route per agent: two routes give every skill twice. Hermes also `~/.hermes/skills/`.
3. Keys: none. Settings: none. Updating means a new reviewed checkout, never an auto-update.
4. Per project (opt-in only): `/setup-matt-pocock-skills` once. It writes `docs/agents/*.md`, an `## Agent skills` block, and may run `git init`, `git remote add origin` and `gh label create`. Trap: "If CLAUDE.md exists, edit it" lands the block in CLAUDE.md. Tell it to edit AGENTS.md.
5. Verify: `ls ~/.agents/skills/{grilling,grill-me,wait-what,retro,writing-for-agents}/SKILL.md`. `/skills` lists them. Typed `/wait-what` expands. "grill me on X" calls Skill `grilling`.
6. Per project (opt-in names): the installer copies and audits them with the five (`MATTPOCOCK_OPTIN_PICKS`, found under any category but misc/ and in-progress/; a missing one is skipped with a warning; the pick list is in the `.picks` marker). `ai-adopt` links them into `<repo>/.claude/skills/<name>` (Claude) and `<repo>/.agents/skills/<name>` (Codex) pointing at this machine's copy; the links are gitignored by name and made again on each machine by `ai-adopt`. Verify: `ls -l <repo>/.agents/skills/`.
7. Cleanup: delete exactly those five folders under `~/.claude/skills`, `~/.agents/skills`, `~/.hermes/skills`. Per project: `docs/agents/`, the block, labels.
See also `ai/skills/README.md`.
