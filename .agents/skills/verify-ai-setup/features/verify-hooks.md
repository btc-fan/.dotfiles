# Verify hooks

Planned: tickets 02 to 05 of `docs/tickets/verify-enforcement/`. The 4 hooks read `.verify/evidence/<run>/run.log` of the checkout: the tool must exist, the tool must be used, a commit that adds tests needs fresh proof, a PR needs proof of its final tree.

## Sub-features

- `vh-exists` (ticket 02): Stop and SubagentStop block a turn that edited app code in a project without a verify skill.
- `vh-used` (ticket 03): Stop and SubagentStop block a turn with an app-code change and no newer valid run.log.
- `vh-commit` (ticket 04): ai-precommit refuses a commit that adds a test without a valid run.log newer than HEAD.
- `vh-pr` (ticket 05): `gh pr create`, `gh pr edit`, `gh pr ready` need a valid run.log at the PR head.

## How to get to it (user POV)

- An agent ends a turn, commits, or opens a PR in a project.

## Driving it with verify

Preconditions: the hooks exist (they do not yet). Fixtures: `python-with-tests` (no verify skill) and a copy with a `.agents/skills/verify-app/` skill.

- **Exists.** Edit `app/calc.py` in `python-with-tests`, then `$H drive hook Stop '{"session_id":"v1"}'`: expect `decision: block` (ticket 02).
- **Commit.** Stage a new `tests/test_more.py` and run `$H drive cli --fixture python-with-tests ai-precommit`: expect a non-zero `rc` (ticket 04).
- Write the rest when the tickets land, with their own payloads.

## Gotchas

- Until tickets 02 to 05 merge, every drive above passes. That is the expected state, not a proof.

## Proof paths

- success, cancel, error, empty, persistence: n/a until tickets 02 to 05 land.
- Unreachable: all paths. Blocked by: the hooks do not exist on this branch. Route tried: none.
