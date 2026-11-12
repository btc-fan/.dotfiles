
Tool catalog (harnesses)
Use this to hand work to another agent. Details: ~/.config/ai/rules/<tool>.md.

| Harness | Use it for | Non-interactive command | JSON output | Limits |
|---|---|---|---|---|
| Claude Code + OMC | main coding, SEO and blog skills, team runs | claude -p "<task>" --output-format stream-json --verbose | stream-json | no --bare. A -p run skips the trust dialog: point it at trusted dirs only. Hermes never hands off to it. Others hand off only when claude is usable (logged in for this user; from Codex also network, which the sandbox lacks unless I approve an escalated run), else follow the skill files |
| OMC ask | call another provider from Claude | omc ask <claude\|codex\|gemini\|antigravity\|grok\|cursor\|muse> --prompt "..." | none (markdown file in .omc/artifacts/ask/) | needs the omc command line (not on the plugin route: then use claude -p or codex exec). Never omc intake schedule (writes crontab) |
| Codex + OMX | second main harness, Codex-side team runs | omx exec "<prompt>" (wraps codex exec) | codex exec --json (JSONL events) | OMX 0.22.6 not before 2026-11-17. Native binaries off |
| opencode | other model front-ends (Grok, Kimi, DeepSeek), scripted runs | opencode run "<prompt>" --format json | --format json | no SEO or blog work. Never opencode upgrade. No gates or hooks inside it |
| Hermes | chat gateway, daily summary | hermes (see ~/.config/ai/rules/hermes.md) | not verified | runs as user hermes. Plain SKILL.md skills only |
| herdr | run agents in panes, read session ids | herdr agent prompt <target> <text> [--wait] | herdr agent get returns JSON | not a harness. No model call. Never herdr update |
| omo (optional) | only when I ask | none known | none known | never /bug on a private project |

Docs: https://code.claude.com/docs/en/headless.md, https://opencode.ai/docs/, https://herdr.dev/tui/docs.
