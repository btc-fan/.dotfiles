# Ponytail

Pin: commit 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846 (version 5.3.3). Source: https://github.com/DietrichGebert/ponytail

## Vendor rules
The verbatim main skill is the file `ai/rules/vendor/ponytail-96608e0-SKILL.md` (copy of the main `SKILL.md` at the audited pin 96608e0, version 5.3.3). Deviation: U+2014 characters replaced by "-" (repo rule: no em dash), as for OMC and OMX. No other change.
Key lines of that file, verbatim:
- "You are a lazy senior developer. The best code is the code never written. You solve the whole problem with the least new code. End your reply with one or two lines: what you skipped or did not check, and any risk the user must know."
- "Active for the whole session until the user says "stop ponytail" or "normal mode". Switch level: `/ponytail lite|full|ultra`."
- "Never cut: validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs, anything the user asked for."
- Levels: lite (build what was asked, name the smaller option), full (default), ultra (also question the request).
Other vendor skills (ponytail-gain, -help, -review, -debt, -audit) and the README are in the intake copy only. They are not imported. Config modes include `off`: owner config stays `full`.
Collision with owner rules: Ponytail ends each reply with a "what I skipped" line. That line is short and fits the 60-word limit exception for the state line.

## When / when not
- Use on every code-writing task. Mode `full` (config file, owner block A.3).
- Not for prose, docs or config text. Not a replacement for review.
- Never run `/ponytail band import`. It starts a hidden detached process. Skip the whole band UI.

## Enforcement
- L0: one line in AGENTS.md vendor short form.
- L1 and L5: vendor hooks (SessionStart, subagent hook). Exact events UNVERIFIED.
- Per prompt: a UserPromptSubmit mode tracker adds context. Count it in the injection budget.
- L7: `~/.claude/.ponytail-active` holds the mode. ai-doctor reads it.
- Do not set `PONYTAIL_DEFAULT_MODE` (it overrides the config file).

## Proof
- Should fire (EN): "add a retry wrapper around the fetch in gql.py". Small diff. No new layer. Error handling kept.
- Should fire (RO): "adauga un camp nou in tabelul sellers si arata-mi codul".
- Should not fire: "explain what the crawler daemon does".
- Signal: `~/.claude/.ponytail-active` contains `full`. Eval: diff size on a fixed task against mode off.

## Setup checklist
1. Prerequisite: node.
2. Clone `https://github.com/DietrichGebert/ponytail` to `/opt/agent-plugins/ponytail` (macOS: `~/.local/share/ai/plugins/ponytail`). `git checkout 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846`. Check `git rev-parse HEAD`. Make it read-only. Run `agent-audit dir`.
3. Claude: `claude plugin marketplace add <path>`, `claude plugin install ponytail@ponytail --scope user`.
4. Codex: `codex plugin marketplace add <path>`, `codex plugin add ponytail@ponytail`. Then trust its hooks once in `/hooks` (owner, interactive).
5. Config `~/.config/ponytail/config.json` equals `{"defaultMode": "full"}`.
6. Never install by `/plugin marketplace add DietrichGebert/ponytail` (unpinned).
7. Telemetry: none documented. Auto-update: none.
8. Verify: `claude plugin list` shows ponytail 5.3.3. Config file equals the block. `git -C <path> rev-parse HEAD` equals the pin.
9. Cleanup: `claude plugin uninstall ponytail@ponytail`, `claude plugin marketplace remove ponytail`, Codex remove (subcommand UNVERIFIED), delete `~/.config/ponytail/` and `~/.claude/.ponytail-active`.
Collision: OMC `minimal-code-discipline` does the same job. Ponytail owns the global rule.
