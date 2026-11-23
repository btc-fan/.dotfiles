# verify-ai-setup: ai-friction (2026-11-23)

Doctor: PASS (--no-agents). Real files changed: none.

| Drive | Result |
|---|---|
| `ai-friction --projects ~/.claude/projects --days 14` | rc 0, report printed |
| same with `--max-turns-per-day 5` | rc 1, "over the limit: 10.9 owner turns a day with a stop (limit 5.0)" |
