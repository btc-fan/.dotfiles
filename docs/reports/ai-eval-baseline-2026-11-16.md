# ai-eval baseline, 2026-11-16 (ticket 02)

Setup under test: the installed `ai` branch at b57ad9d (before any enforcement change). Harness: `ai-eval` from commit 2a59837. Raw reports are kept outside the repo.

## Install level

| Fixture | Adopt rc | Second run | Result |
|---|---|---|---|
| empty-git | 0 | no change | pass |
| docs-only | 0 | no change | pass |
| no-git | 1 ("not a git repo") | none | refuses (wanted; `--init` is ticket 09) |
| app | 0 | only gitignored graph cache files | harness noise (ticket 09 fixes the snapshot) |
| project-copy | 0 | `.ai/enabled` rewritten and a new commit | bug: ai-adopt is not idempotent (ticket 09) |

Also seen: the adopt commit lands on the current branch, also main (ticket 09).

## Behaviour level (hits in 3 runs, max 4 turns)

| Case | Claude | Codex |
|---|---|---|
| writing-for-agents | 3/3 | 3/3 |
| docs-lookup | 3/3 | 3/3 |
| graphify-first | 3/3 | 3/3 |
| diagnosing-bugs | 2/3 | 3/3 |
| ship | 1/3 | 3/3 |
| winner-tdd | 0/3 | 3/3 |

Checked against the transcripts: Codex reads the SKILL.md files itself; Claude went to edits without `tdd` in all 3 winner-tdd runs.

## Limits of this baseline

1. The cases name the action plainly. The misses in real sessions came from vague prompts ("write this down", "investigate how it performs"). Hard cases with that wording are added next; the 90% bar applies to them too.
2. 4 turns can end a run before a Stop hook fires (ticket 06 raises the cap).
