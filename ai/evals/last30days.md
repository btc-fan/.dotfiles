## last30days eval prompts (Claude, any project: on by default; expected Skill = `last30days:last30days`)

Format: tool | FIRE (EN ; RO ; RU) | NOT (a ; b) | signal. Pass bar: fire cases 3 of 3, NOT cases 0 of 2 false fires.
Copied from the proof section of `ai/rules/last30days.md`. Change both places together.

- last30days | "What are people saying about Claude Code in the last 30 days?" ; "Ce spun oamenii pe Reddit și X despre Cursor luna asta?" ; "Что люди пишут про Polymarket за последний месяц?" | NOT "Show me the FastAPI docs for dependencies" [context7] ; "Find where the price parser is defined in this repo" [Map, graph, Serena] | signal: Skill tool_use `last30days:last30days`; Bash `python3 <SKILL_DIR>/scripts/last30days.py`; a saved brief in `~/Documents/Last30Days`
