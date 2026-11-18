# Evolution scenario: first run (2026-11-18)

Command: `ai-eval scenario --agent both --runs 3` (scenario `ai/evals/scenarios/evolution.json`).

| Step | Claude | Codex |
|---|---|---|
| 2 session: first code on a feature branch, commit (rule knowledge-check) | 3/3 | 0/3 |
| 3 check: branch, Map names calc, graph fresh | 1/3 (Map 3/3, graph 1/3) | 0/3 |
| 5 session after the merge: Serena or graphify, rule merge-review | 0/3 (Serena 3/3, merge-review 0/3) | not reached |
| 6 check: Map, graph fresh | 2/3 | not reached |
| Run passes | 0/3 | 0/3 |

The first run (before 1e3d69d) scored 0 for both agents because the headless sessions had no write access. That is a harness fault, not a setup fault.

Findings (ticket 13):
1. merge-review never fires after the first merge in a new repo. The first session sees no code, so `.ai/last-review` is never set. The next session sets it quietly instead of giving the nudge.
2. The graph is fresh right after the commit in 1 of 3 runs. The refresh after a commit is not finished when the session ends.
3. Codex built nothing in 3 of 3 runs. The writing-for-agents gate fired on the AGENTS.md Map edit, and the session stopped.
4. Claude ran `rg` after Serena in 3 of 3 runs (nav-first fired). Serena answered the question first.
