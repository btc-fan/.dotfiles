# verify-ai-setup: ask-first OK with plan step picks

Commit c5945ed. Doctor: PASS. Real files changed: none.

Each row: a UserPromptSubmit payload with the prompt, then a PreToolUse payload with `systemctl restart web-api` in the same session.

| Prompt | Decision |
|---|---|
| `go 1 2 3` | allow |
| `OK 1-5` | allow |
| `go all` | allow |
| `go but not 2` | deny |
| `1 2 3` | deny |
