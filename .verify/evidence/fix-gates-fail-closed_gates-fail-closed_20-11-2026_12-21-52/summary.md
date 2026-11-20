# verify-ai-setup run: gates-fail-closed

Feature: router gates (R-017). Code commit: `38eac49`. Fixtures: `empty`, `docs-only`.

| Step | Result | File |
|---|---|---|
| Doctor (with agents) | PASS | `run.log` |
| `git push origin main`, Claude payload | deny, `merge-approval` | `01-hook.txt` |
| `git push origin main`, Codex payload | deny, `merge-approval` | `02-hook.txt` |
| `git push origin feature-x` | allow | `03-hook.txt` |
| Denied command of 16 KB (`git commit --no-verify -m` and 8000 times `a-`) | deny in 0.63 s (before the fix: 14.5 s) | `04-hook.txt` |
| Bash `tool_input` is a string | deny, `[ai router: payload]` | `05-hook.txt` |
| `exec_command` `tool_input` is a list, Codex payload | deny (block) | `06-hook.txt` |
| Bash payload without `tool_input` | allow, as before | `07-hook.txt` |
| Corrupt `routing.json`, Bash, Claude payload | deny, `[ai router: routing]` | `08-hook.txt` |
| Corrupt `routing.json`, Bash, Codex payload | deny (block) | `09-hook.txt` |
| Corrupt `routing.json`, Read | allow | `10-hook.txt` |
| Real Claude session, corrupt `routing.json`, `echo hello` | denied, the agent stopped | `11-session.txt` |
| Real Claude session, `git push origin main` | denied, remote heads did not change | `12-session.txt` |
| Real Codex session | NOT RUN: Codex usage limit on 2026-11-20 | none |

Notes:

- The times include the start of the helper. The router alone answers a denied command of 200 KB in 0.55 s.
- Drive 11, tool result: `PreToolUse:Bash hook error: [ai router: routing] <tmp>/build/routing.json does not load, so no gate can check this tool call. Stop and tell the owner: run ai-sync, then try again.`
- The stream files and the session-state folders of drives 11 and 12 are not in git, because this repo is public. A session stream lists the skills and connectors of the account. A state folder holds the host name.
- A payload that is not a JSON object has no drive: the helper accepts only an object. `ai/tests/test_router.py::check_fail_closed_inputs` covers it.
- Cleanup: `real files changed: none`.
