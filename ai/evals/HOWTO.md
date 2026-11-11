## Appendix 5. How to run the evals and what to log (all packs)

1. Fresh session per case: `claude -p "<prompt>" --output-format stream-json --verbose` in the target project, NOT `--bare`; Spence used `--max-turns 1 --allowedTools Skill` so the run stops at the first Skill call (ai-research-5.md); that measures "did it call Skill", not task success. Parse `Skill` tool_use `input.skill`.
2. For typed commands, log with a UserPromptExpansion hook (`command_name`); for model calls, a PostToolUse hook with matcher `Skill`. Append one line per event: timestamp, session id, prompt hash, skill, source (model or human). This one log is the "we can prove it fired" artifact, and the same log feeds the gates.
3. Official alternative for plugin packs: `claude plugin eval` (three runs, with and without the plugin, grader `tool_used: Skill`). Run on every model change and every pin bump.
4. Pass bars: should-fire 3/3 per skill; should-not 0/2 false fires; hard-case misses expected 10 to 25% without L2 (ai-research-5.md estimate, unmeasured for this stack).
5. Before any eval, run `/context` or `/doctor` once: if the skill shows name-only in the listing (finding 2), expect misses unless L0/L2 is on.
