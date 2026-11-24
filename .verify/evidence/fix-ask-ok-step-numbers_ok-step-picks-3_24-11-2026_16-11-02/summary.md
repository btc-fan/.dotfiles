# verify-ai-setup: ask-first OK with plan step picks (after review fixes, at the PR code head)

Commit 6468f78. Doctor: PASS. Real files changed: none.

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
