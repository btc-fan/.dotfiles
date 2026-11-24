# verify-ai-setup: ask-first OK with plan step picks (merged branch)

Commit dd3b8db (after the merge of origin/ai with #33). Doctor: PASS. Real files changed: none.

Each row: a UserPromptSubmit payload with the prompt, then a PreToolUse payload with `systemctl restart web-api` in the same session.

| Prompt | Decision |
|---|---|
| `go 1 2 3` | allow |
| `OK 1-5` | allow |
| `go all` | allow |
| `go but not 2` | deny |
| `1 2 3` | deny |
| `goall` | deny |
| `go 1-11-1...1-1x` (13 ranges, the slow input before the fix) | deny |

Also: `ai-doctor --works graphify` from #33 on this branch: `PASS graphify works`, rc 0.
