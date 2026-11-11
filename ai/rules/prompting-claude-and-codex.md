# prompting-claude-and-codex (our own skill)

Pin: dated snapshot, in the skill file header. Source: our own text in `ai/skills/prompting-claude-and-codex/SKILL.md`, condensed from the official docs linked inside it.

## Vendor rules
Not a vendor tool. The skill holds our condensed rules and links to the official sources: https://code.claude.com/docs/en/ (skills, hooks, headless, sub-agents) and https://developers.openai.com/codex/. Update the snapshot date when you re-read the docs.

## When / when not
- Use when you write a brief for another agent: subagent, `codex exec`, `claude -p`, `opencode run`, `omc ask`, `herdr agent prompt`.
- Not for writing AGENTS.md or SKILL.md (that is writing-for-agents).

## Enforcement
- L0: AGENTS.md "Prompting other agents". L3: routing row `prompting-others` on the commands above (nudge). L6: description starts with the trigger words.

## Proof
- Should fire (EN): "ask codex to review this diff" gives a brief with goal, files, scope, output format, read-only.
- Should fire (RO): "da-i lui codex sarcina asta".
- Should not fire: "explain this function".
- Signal: Skill tool_use `prompting-claude-and-codex`, or the nudge text before a `codex exec` call.

## Setup checklist
1. The installer copies the skill folder to `~/.agents/skills/` (shared) and links it for Claude. It is also in the ai-core plugin.
2. No keys. No network. No telemetry.
3. Verify: `/skills` lists it. A `codex exec` call in a test session shows the nudge.
4. Cleanup: delete the folder.
