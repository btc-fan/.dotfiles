# ai/skills

Our own skills live here. The installer copies them to `~/.agents/skills/` (shared by Codex, opencode, Hermes) and links them for Claude.

| Skill | Source |
|---|---|
| prompting-claude-and-codex | `ai/skills/prompting-claude-and-codex/SKILL.md`. A copy sits in `ai/marketplace/plugins/ai-core/skills/`. Keep both equal: edit here, then `cp -R`. ai-doctor should diff them. |

## Pinned copies fetched by the installer (not stored in this repo)
The five global skills of mattpocock/skills are fetched at the pinned commit `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`: grilling, grill-me, wait-what, retro, writing-for-agents. Copy whole folders and keep `agents/openai.yaml`. No plugin. No `npx skills@latest`. Details: `ai/rules/mattpocock-skills.md`.

Third-party plugin packs (claude-seo, claude-blog, ui-ux-pro-max) are not skills in this folder. They install as plugins. See `ai/rules/`.
