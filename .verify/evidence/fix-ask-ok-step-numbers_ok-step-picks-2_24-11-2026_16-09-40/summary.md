# verify-ai-setup: ask-first OK with plan step picks (after review fixes)

Commit a886339. Doctor: PASS. Real files changed: none.

Each row: a UserPromptSubmit payload with the prompt, then a PreToolUse payload with `systemctl restart web-api` in the same session.

| Prompt | Prompt hook time | Decision |
|---|---|---|
| `go 1 2 3` | 0 s | allow |
| `OK 1-5` | 0 s | allow |
| `go all` | 1 s | allow |
| `go but not 2` | 0 s | deny |
| `1 2 3` | 0 s | deny |
| `goall` | 0 s | deny |
| `go 1-11-1...1-1x` (13 ranges, the slow input before the fix) | 0 s | deny |
