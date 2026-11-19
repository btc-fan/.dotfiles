# 21: The writing style rule gets a check

**What to build:** an Edit or Write of a Markdown file can add a sentence of more than 25 words. Then a nudge names the file, the count and the first words of the longest sentence. The rule is the 25-word limit of ASD-STE100, the writing style of the global rules.

**Blocked by:** None (can start immediately)

**Status:** done (2026-11-19)

Why: the writing style rule (`ai/agents-md/00-owner.md`, since 2026-11-11) had no check. A word limit is the one part of STE that a script can check.

- [x] Red: `ai/tests/cases/ste-sentence.json`: a Write and an Edit with a 32-word sentence fire.
- [x] Quiet: short sentences, front matter, code blocks, table rows, headings, link targets, short list items, a non-Markdown file.
- [x] The L0 row stays short: the SessionStart context grows by 50 characters only.
