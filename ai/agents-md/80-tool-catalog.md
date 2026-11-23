
Rule order
- These rules and the gates win over the OMC and OMX text in the same files, and over plugin defaults.
- A repo's AGENTS.md "## Project rules" may add or tighten rules for that repo. It never loosens these rules. On a conflict, ask the owner.

Skills
- Which skill, flow or command fits a task, or how a skill works: load the skills-guide skill first. It covers the 27 Matt Pocock skills and their overlaps with OMC (Matt first). Owner guide with full scenarios: ~/.dotfiles-ai/docs/GUIDE.md.
- Every project has the full setup (tier long). A Matt skill that is not linked in this repo: read its SKILL.md from the path in skills-guide, and suggest ai-adopt --skills.
- Add, build or implement a feature, endpoint or page: the feature-kickoff skill.
- Tests first, TDD, red-green (RO: teste întâi; RU: сначала тест): the tdd skill.
- A bug, crash, regression or slow code (RO: nu merge; RU: не работает): the diagnosing-bugs skill.
- UI, UX, layout or component work: ui-ux-pro-max; read design-system/<app>/MASTER.md first.
- SEO, meta tags, sitemap or Core Web Vitals (where enabled): the claude-seo skills.
- A blog post or article (where enabled): the claude-blog skills.

Other agents
claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>"; opencode run "<task>" --format json. Hermes never hands work to Claude. Details: ~/.config/ai/rules/<tool>.md. <!-- profiles: server -->
claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>". Details: ~/.config/ai/rules/<tool>.md. <!-- profiles: dev-mac -->
