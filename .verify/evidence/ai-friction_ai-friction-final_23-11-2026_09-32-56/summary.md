# verify-ai-setup: ai-friction, after the review fixes (2026-11-23)

Doctor: PASS (--no-agents). Real files changed: none.

| Drive | Result |
|---|---|
| `ai-friction --projects ~/.claude/projects --days 14` | rc 0 |
| same with `--max-turns-per-day 5` | rc 1, "over the limit: 11.1 owner turns a day with a stop" |
| `ai-friction --days 0` | rc 2, "--days must be more than 0" |

Raw drive files are left out: they hold real transcript lines, and the repo is public.
