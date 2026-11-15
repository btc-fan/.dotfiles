# ai/skills

Our own skills live here. The installer copies them to `~/.agents/skills/` (shared by Codex, opencode, Hermes) and links them for Claude.

| Skill | Source |
|---|---|
| create-verification-skill, maintain-verification-skill | pstack (MIT, Lauren Tan), adapted by `ai/lib/pstack_adapt.py` from `ai/rules/vendor/pstack-verification/` (never edit by hand: change the script or the vendor copy). Contract: `ai/rules/verification-skill.md`. |
| skills-guide | `ai/skills/skills-guide/SKILL.md`: how each of the 27 Matt Pocock skills works, when to use it, flows, phase boundaries, overlaps with OMC. Owner guide: `docs/GUIDE.md`. |
| prompting-claude-and-codex | `ai/skills/prompting-claude-and-codex/SKILL.md`. A copy sits in `ai/marketplace/plugins/ai-core/skills/`. Keep both equal: edit here, then `cp -R`. ai-doctor should diff them. |

## Pinned copies fetched by the installer (not stored in this repo)
All 27 skills of the official mattpocock/skills plugin set are fetched at the newest stable tag. Six are global: grilling, grill-me, wait-what, retro, writing-for-agents, ask-matt. The other 21 are linked per project only (`skills:` line in `.ai/enabled`; 12 by default). Copy whole folders and keep `agents/openai.yaml`. No plugin. No `npx skills@latest`. Details: `ai/rules/mattpocock-skills.md`.

Third-party plugin packs (claude-seo, claude-blog, ui-ux-pro-max) are not skills in this folder. They install as plugins. See `ai/rules/`.
