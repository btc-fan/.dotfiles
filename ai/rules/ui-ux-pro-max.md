# ui-ux-pro-max

Pin: v2.15.0 = a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5 (the manifests inside still say 2.13.0: do not use them as a version check). OPT-IN per project (7 skills). Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5/

## Vendor rules (verbatim)
No CLAUDE.md block for users. Activation text:
- README "Skill Mode (Auto-activate)": "The skill activates automatically when you request UI/UX work. Just chat naturally: Build a landing page for my SaaS product".
- `skills/ui-ux-pro-max/SKILL.md` "When to Apply": "Use this Skill when the task involves UI structure, visual design decisions, interaction patterns, or user experience quality control ..." and "Skip it for pure backend logic, API/database design, non-visual performance work, infrastructure/DevOps, or non-visual scripts, unless the task changes how something looks, feels, moves, or is interacted with." (The vendor text has an em dash here. It is replaced, because U+2014 is not allowed in this repo.)
- Persistence: save a design system only with `--persist` and `--output-dir <project root>`. It writes `design-system/<project-slug>/MASTER.md`. "Never use `--force` without explicit user authorization."
Its skill files hold 34 U+2014 characters in total. Lint every output.

## When / when not
- Only in a project that builds or reviews a visual interface with a supported stack (React, Next, Vue, Svelte, Tailwind, shadcn, SwiftUI, Flutter and others). Streamlit is not on the list.
- Core skill: ui-ux-pro-max. Asset skills: design (logo, icons, social images), design-system (tokens), ui-styling, brand, banner-design, slides.
- Not for backend, SQL, infra, scripts. Not for the md999 Streamlit dashboard unless the owner says so.
- Paid: logo, icon and image generation call Gemini. Ask first.
- Never copy its `stack/` folder.
- Figma URL: use the Figma skills. Any chart or dashboard styling: dataviz. A .pptx file: the pptx skill. OG or hero image for SEO or a post: seo-image-gen or blog-image.

## Enforcement
- Opt-in means project scope. Enable it in `.claude/settings.local.json` or the project `.claude/settings.json`. It must be OFF in `~/.claude/settings.json`. Plugin skills ignore `skillOverrides`, so the switch is the whole plugin.
- L0: one line in the project AGENTS.md only: `UI work (pages, components, layout, color, type, a11y) -> use ui-ux-pro-max first; assets: design / banner-design / slides / brand`. RO and RU: "interfata, design, pagina, componente", "интерфейс, дизайн, страница, компонент".
- L1: only through a project SessionStart hook when the project opted in (marker: `design-system/` or `.claude/skills/ui-ux-pro-max`).
- L2 and L3 (routing row `ui`): only in opt-in projects. Edit or Write of tsx, jsx, vue, svelte, css, html files gives a nudge to run its `search.py`.
- L5: the OMC designer agent needs the L0 line from SubagentStart.
- L6: the six asset skills have marketing-style descriptions and `design` overlaps the rest. Add RO and RU triggers in the hook.
- The no-em-dash lint covers its output.

## Proof
Eval cases: `ai/evals/ui-ux-pro-max.md`. Run them only in a project that enabled the plugin. In a project that did not, ALL of them must NOT fire and the skill must be absent from the listing.
- Signal: Skill tool_use `ui-ux-pro-max:ui-ux-pro-max`. Or Bash `search.py`. A persisted `design-system/<slug>/MASTER.md`.

## Setup checklist
1. Prerequisite: Python 3, stdlib only.
2. Plugin route: `claude plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill#v2.15.0`, `claude plugin install ui-ux-pro-max@ui-ux-pro-max-skill`. Choose project or local scope, not user. CLI route for other harnesses: `uipro init --ai claude|codex|opencode|universal` (project scope; never `--global`). npm package `ui-ux-pro-max-cli`: pin the exact version after reading it (UNVERIFIED). Do not use the stale `uipro-cli`.
3. Auto-update: off by default for this third-party marketplace.
4. Keys: none for search. Optional GEMINI_API_KEY (image, logo, icon), GOOGLE_FONTS_API_KEY.
5. Per project: enable as above. Add the L0 line to the project AGENTS.md. Decide whether `design-system/` is committed.
6. Verify: `claude plugin list` shows scope Project or Local. `python3 <plugin path>/.claude/skills/ui-ux-pro-max/scripts/search.py "saas dashboard" --design-system` returns a design system.
7. Cleanup: `claude plugin uninstall ui-ux-pro-max@ui-ux-pro-max-skill`. CLI route: `uipro uninstall`. Delete `design-system/` if unwanted.
