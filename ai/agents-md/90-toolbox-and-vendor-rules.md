
Toolbox
For specialized work, check ~/.config/ai/TOOLBOX.md for a ready tool before building one.
Toolbox tools need a full audit before the first install.

Vendor rules (short form)
Long vendor text lives in ~/.config/ai/rules/<tool>.md. Read the file when you use the tool.
- graphify: with graphify-out/graph.json, run graphify query "<question>" before your first grep or file read. Read raw files only for lines the graph located. After code changes run graphify update . Put this rule in every subagent prompt that explores code.
- Serena: for code, use Serena first. Load its tools before any read, grep or bash on code. Never use built-in Edit on code you read with Serena.
- context7 and Grounded Docs: use them for any library question, even when you think you know the answer. Not for refactoring, debugging or general programming.
- RTK: the hook rewrites commands. Use rtk bypass <cmd> when you need the full output (security tools, debugging).
- Ponytail: mode full. Smallest correct diff. Never cut validation, error handling, security or accessibility.
- i-have-adhd: see "Output shape".
- claude-seo and claude-blog: a URL or a site is seo-*. One post file is blog-*. Other agents hand this work to Claude Code.
- OMC: plan, execute, review, verify. Verify before you claim done. This file and the hard rules win over OMC defaults. Do not use OMC for single commands.
- OMX: never run it in a Claude session. Its "do not stop to ask" text does not override my confirm-first rules.
- herdr: the PR author-sessions block above.
- mattpocock skills: grilling for "grill me" and stress-tests. Edit AGENTS.md, CLAUDE.md or SKILL.md with writing-for-agents first.
- Playwright MCP, ui-ux-pro-max, llm-wiki-compiler: only in projects that enabled them.
