# verify-ai-setup run: hook-copy-and-block

Features: `ai-sync` (R-018) and the router hook wiring (ticket setup-audit 14). Code commit: `8309fd3`.
Fixtures: `empty`, `docs-only`, `python-with-tests`, `dotfiles-worktrees`.

| Step | Result | File |
|---|---|---|
| Doctor (with agents) | PASS | `run.log` |
| Real Claude session with a stand-in gate that sleeps 8 s, timeout 2 s, no `onFailure` | The command ran: `probe-file.txt` exists. This is the old behaviour | `01-session.txt` |
| The same session with `"onFailure": "block"` on the stand-in gate | Blocked: `probe-file.txt` does not exist | `02-session.txt` |
| Real Claude session with the plugin of this checkout, `git push origin main` | Denied by `merge-approval`, remote heads did not change | `03-session.txt` |
| Real `git merge` in the installed copy of the `dotfiles-worktrees` fixture, with an old Claude hook copy | The post-merge hook ran `ai-sync`; the copy is equal to the merged `router.py` | `04-merge.txt` |

Notes:

- Drive 02, tool result: `PreToolUse:Bash hook error: [sleep 8; exit 0]: timed out; blocking because onFailure is "block"`.
- Drive 04, before the merge: `<tmp>/home-sync/.claude/plugins/cache/ai/ai-core/1.0.0/hooks/router.py` held the one line `# an old copy`.
  After the merge: `cmp` of that file and `<tmp>/home-sync/.dotfiles-ai/ai/marketplace/plugins/ai-core/hooks/router.py` gave no difference.
  `04-merge.txt` lists the new `.local/state/ai/ai-core.claude.hash` and the files of the copy.
- The 2 stand-in plugins are throwaway folders with one `hooks.json` each. They are not in the repo.
- The stream files and the session-state folders are not in git, because this repo is public.
- Not run: a real Codex session. Codex has no `onFailure` field, and this change does not touch its hooks.
- Cleanup: `real files changed: none`.
