# claude-blog

Pin: v2.3.2 = 4f9c2cb8fd17f594e868d6c2ce0e8fb2c971f987. Installed on every machine, enabled per project only (32 skills; blog-chart is internal). Source: https://github.com/AgriciDaniel/claude-blog/blob/4f9c2cb8fd17f594e868d6c2ce0e8fb2c971f987/skills/

## Vendor rules (verbatim)
No user-facing CLAUDE.md block. The router skill (`skills/blog/SKILL.md`) is the vendor routing text:
- "Use when the user asks to create, revise, analyze, plan, translate, localize, audit, or repurpose blog content, or invokes a /blog subcommand. Do not activate merely because the word "blog" appears in an unrelated coding, theme-debugging, database, log-analysis, or definition request."
- Scope fences: blog-write "Not for editing an existing post (blog-rewrite), and not for a standalone outline, brief or research request." blog-analyze "For a site-wide health check ... use blog-audit instead." blog-chart "Internal capability, not user-invocable ... Agents cannot call it." blog-image, blog-audio, blog-google, blog-notebooklm: "Runs only on an explicit request".
Claude-only is an inference from its CLAUDE.md wording, not a vendor statement.

## When / when not
- Use for any task on blog posts as authored content: write (blog-write), rewrite (blog-rewrite), score or check one post (blog-analyze, blog-seo-check, blog-factcheck), plan (blog-brief, blog-outline, blog-strategy, blog-calendar, blog-cluster), translate (blog-translate, blog-localize, blog-multilingual), repurpose, taxonomy.
- One post file or a post to be written: blog-*. Site, URL, domain: seo-*. Whole-blog health: blog-audit.
- Not for technical docs, runbooks, AGENTS.md, code comments. Not for "blog" in log analysis, theme debugging, database work.
- Ask the owner first: paid image or audio, Indexing API, NotebookLM, any upload of text to a third party.
- Opt-in per project (owner decision 2026-11-12). Turn it on for one project: `ai-adopt --tools blog`. It adds `blog` to `.ai/enabled` and sets `"enabledPlugins": {"claude-blog@agricidaniel-blog": true}` in the project `.claude/settings.json` (either one alone also counts as on). Claude only: Codex, opencode and Hermes read the skill files and count it as on everywhere. Claude in a project without it: the router row `blog-not-enabled` says so in one line; suggest the command, do not enable it yourself.
- Other harnesses: same cases as in `claude-seo.md`. Hermes never hands off. Codex hands off only when `claude` is usable (logged in and network allowed). Else follow the skill files, starting at `skills/blog/SKILL.md` in the claude-blog copy. On a hand-off, ask for the post path and the preflight report path back.
- The skill does not follow STE or the short-reply style. Tell it "reply short, report to a file".

## Enforcement
- L0 (mandatory). Rows: `write a post | scrie un articol, напиши статью | blog-write`; `fix or refresh a post file | rescrie, actualizeaza postarea, перепиши, обнови пост | blog-rewrite`; `score or check a post | verifica postarea, проверь статью | blog-analyze / blog-seo-check`; `translate a post | tradu articolul, переведи статью | blog-translate`; `brief or outline for one post | brief pentru articol, бриф для статьи | blog-brief / blog-outline`; `fact check | verifica sursele, проверь факты | blog-factcheck`. Start with the router `claude-blog:blog`.
- L1: the routing table comes back after compaction or /clear.
- L2 (tight): fire only on (post|article|blog|articol|postare|статья|пост) AND (write|rewrite|draft|translate|brief|outline|scrie|rescrie|tradu|напиши|перепиши|переведи|проверь), or a path ending .md or .mdx under blog, posts, content, articles. Include "none". The word "blog" alone is a bad trigger.
- L3: Edit or Write of `**/{blog,posts,articles,content}/**/*.{md,mdx}` gives context "post file: use claude-blog, run blog_preflight before delivery".
- L4 (fits here): PostToolUse matcher `Skill` and UserPromptExpansion each write a per-session marker. PreToolUse on Write or Edit of post paths denies unless the marker has a `claude-blog:` entry. Do not read the transcript for this (it lags). Escape: owner only, `sudo ai-gate-skip <gate> <minutes> <why>`.
- L5: own subagents that write posts get the table through SubagentStart.
- Vendor gates (preflight, blog-reviewer, review nonces) prove a real run. Skill fired but no gates means a fake run.

## Proof
Eval cases: `ai/evals/claude-blog.md`. Hard cases: "blog" in a log-analysis prompt must NOT fire. A post file against a URL (blog-* against seo-*).
- Signal 1: Skill tool_use `claude-blog:blog`, then `claude-blog:blog-<x>`. Signal 2: Bash `blog_preflight.py`, a delivery folder, a nonce file in `~/.cache/claude-blog/review-nonces`.

## Setup checklist
1. Prerequisites: Claude Code, Python 3.11 or newer.
2. Install (pinned tag): `claude plugin marketplace add AgriciDaniel/claude-blog#v2.3.2`, `claude plugin install claude-blog@agricidaniel-blog`, disable it at user scope (`enabledPlugins` false), restart. Audited copy for other agents: `/opt/agent-plugins/claude-blog` (Linux) or `~/.local/share/ai/plugins/claude-blog` (macOS). Record the sha in `ai/pins.env`. Never install or uninstall from v2.2.0 (its uninstall deletes your own blog-* folders). Do not install `blog-studio` or `brain/`. Do not run `setup_image_mcp.py` (writes settings.json with a key).
3. Python packages: the plugin route installs none. Build a venv from the hash-locked `requirements.lock`, plus the `presentation` extra for rendering (Patchright, WeasyPrint, Markdown, Pillow, requests, google-genai). Without a renderer, gate 3 blocks delivery. How the plugin finds the venv: UNVERIFIED, smoke-test. WeasyPrint system libraries on Ubuntu: UNVERIFIED, read its install page.
4. Keys, all optional, in `~/.config/ai/secrets.env`: GOOGLE_AI_API_KEY or GEMINI_API_KEY (paid hero, audio), UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, PIXABAY_API_KEY, Google credentials (blog-google), GITHUB_TOKEN (blog-flow).
5. blog-google shares `~/.config/claude-seo/google-api.json` and `oauth-token.json` with claude-seo. Never commit them.
6. Per project: `ai-adopt --tools blog`. The draft folder is created per run (default path UNVERIFIED: check and gitignore it). Optional BRAND.md and VOICE.md at the project root.
7. Verify: `claude plugin list` shows claude-blog 2.3.2, disabled at user scope; enabled inside an enabled project. A throwaway `/blog write` on a dummy topic gives Skill `claude-blog:blog-write`, `blog_preflight.py --gate 1` runs, a nonce appears, no import errors.
8. Cleanup: `claude plugin uninstall claude-blog@agricidaniel-blog`, `claude plugin marketplace remove AgriciDaniel/claude-blog`, delete `~/.cache/claude-blog`.
