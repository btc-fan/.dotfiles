---
name: prompting-claude-and-codex
description: 'Use when you write a brief for another agent: a subagent, codex exec, claude -p, opencode run, omc ask, herdr agent prompt. Also for "ask codex", "da-i lui codex", "спроси codex". Gives the brief shape, the non-interactive commands, and how to check the result. Not for editing AGENTS.md or SKILL.md (use writing-for-agents).'
---

# Prompting Claude Code and Codex

Snapshot date: 2026-11-11. Condensed from the official docs. Re-read the links when you update this file.
Sources: https://code.claude.com/docs/en/headless.md, https://code.claude.com/docs/en/skills.md, https://code.claude.com/docs/en/hooks.md, https://developers.openai.com/codex/

## The brief (every agent)
1. Goal in one sentence. Then what is already ruled out or already done.
2. Name the files. Use absolute paths.
3. Narrow scope: one task. Say what the agent must not touch.
4. Expected output and its format. For a long result: "write it to <path> and return the path".
5. Read-only unless the owner said otherwise.
6. If the agent explores code, add: "graphify query first, then Serena, then read only located lines".
7. Say how to prove success: a command to run, a test, a file to check.

## Commands
- Claude: `claude -p "<task>" --output-format stream-json --verbose`. Run it from the project directory. Do NOT add `--bare`: it skips hooks, skills, plugins, subagents. A `-p` run shows no trust dialog and runs project hooks: use trusted directories only.
- Claude from another harness: `omc ask claude --prompt "<task>"` (markdown file in `.omc/artifacts/ask/`).
- Codex: `codex exec "<prompt>"`. JSON events: `--json`. With OMX: `omx exec "<prompt>"`.
- opencode: `opencode run "<prompt>" --format json`.
- herdr: `herdr agent prompt <target> <text> [--wait] [--until STATUS] [--timeout MS]`.

## Check the result
- The agent report is a claim. Check the file, run the test, read the diff.
- For a skill-based task, ask for the Skill names used. A skill that "ran" without its own gates is a fake run.
- Plugin skills of Claude are not visible to Codex or opencode. Hand that work to Claude.

## Wording tips
- Front-load the leading word of each instruction. Wording decides how reliably it fires.
- Name the tool or skill you want. A name in the text fires more often than a general hint.
- Keep rules short and positive: say what to do.
- Skill descriptions: triggers first, under 1,536 characters. The listing drops descriptions of unused skills when over budget.
