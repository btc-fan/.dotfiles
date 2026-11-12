# Hermes Agent (skills and rules side)

Pin: NOT FOUND for the installer. Record `hermes --version` after install in `ai/pins.env`. Docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills, .../hooks, .../context-files

## Vendor rules
No rules text to import. Facts, verbatim:
- "Level 0: skills_list() -> [{name, description, category}, ...] (~3k tokens); Level 1: skill_view(name) -> Full content + metadata; Level 2: skill_view(name, path) -> Specific reference file. The agent only loads the full skill content when it actually needs it."
- "The list of skills the agent picks from is part of the conversation's system prompt, which stays fixed so the provider's prompt cache keeps working."
- `pre_llm_call` runs "once per turn before the loop; all valid string/{"context": ...} returns are joined and injected into the user message; the first valid {"action": "block", ...} ends the turn".

## When / when not
- Chat gateway (Discord DMs and a private channel) and a daily 09:00 summary. Runs as the user `hermes`, with no sudo (owner decision 2026-11-11: no agent has sudo; the server has no sudoers entry for hermes). The no-root rule applies: never sudo or try to get root. Only box commands on a server, where the hosting rules allow it: `ai-box <subcommand>` or `sudo proj-agent <subcommand>` (Hermes has no Claude sandbox, so both work). For anything else that needs root, give the owner the exact command.
- Plain SKILL.md skills only. No hand-off to Claude Code (owner decision 2026-11-12). For SEO and blog work, follow the claude-seo or claude-blog skill files directly (paths in `claude-seo.md`): read `skills/seo/SKILL.md` or `skills/blog/SKILL.md`, then the sub-skill it names. ui-ux-pro-max: tell the owner it needs a Claude session.
- Skills from `official/` only. Never `--force`. Hermes has no manual-only flag, so every installed skill is model-reachable.

## Enforcement
- L0: AGENTS.md is read into the system prompt at session start. Whether it survives compaction: UNVERIFIED, test it.
- L1: a plugin system-prompt section. L2 and L3: a small `pre_llm_call` plugin with a regex gate and a "none" option.
- L4: none known. A `pre_tool_call` hook exists: blocking semantics not read.
- L6: the model reads the whole index, so descriptions matter.
- Rules for Hermes: managed block in SOUL.md (i-have-adhd rules and the root text).
- L7: no miss log. Proof is a `skill_view` call with the skill name.

## Proof
- Should fire: the same prompt set as Claude. Count `skill_view` names. No measured activation rate exists for Hermes.
- Should not fire: a prompt with no matching skill gets no `skill_view`.

## Setup checklist
1. Installed already on the home server by its vendor installer (review before running).
2. As user `hermes` (`sudo -u hermes -H`): `hermes mcp add` for the MCP servers, `hermes config set` for settings, plugin dir `~/.hermes/plugins/<name>/` enabled in `plugins.enabled`.
3. Env in secrets: `DISCORD_ALLOWED_USERS` = owner only. Bot permissions 117760 and Message Content Intent. Unauthorized DMs ignored. Approvals manual. Telemetry off. Gateway as a user service.
4. `hermes skills trust` once in a repo that ships `.agents/skills/`.
5. Serena for Hermes: `--context ide`, by hand.
6. Verify: `hermes doctor`. `hermes skills list` shows exactly the intended skills.
7. Cleanup: delete copied skill folders, `hermes skills untrust` for a repo, remove SOUL.md block and MCP entries.
