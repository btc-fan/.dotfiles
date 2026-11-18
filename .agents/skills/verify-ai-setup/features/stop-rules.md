# Stop rules

A stop rule blocks the first end of a turn when the prompt matched it and its skill was not used. The example here is `diagnosing-bugs` (a bug or performance prompt). Ticket 14 turns it into a hint; update this file then.

## Sub-features

- `stop-block`: a bug prompt, then Stop: `block`.
- `stop-once`: the second Stop in the same session passes.
- `stop-normal`: a normal prompt, then Stop: passes.

## How to get to it (user POV)

- The owner writes "the build is broken"; the agent tries to end the turn without the diagnosing-bugs skill.

## Driving it with verify

Preconditions: any kind, `doctor: PASS`.

- **Block.** `$H drive hook UserPromptSubmit '{"prompt":"the export crashed again, please debug it","session_id":"s1"}'` (`rules fired: diagnosing-bugs`), then `$H drive hook Stop '{"stop_hook_active":false,"session_id":"s1"}'`: `decision: block`.
- **Once.** Then `$H drive hook Stop '{"session_id":"s1","stop_hook_active":true}'`: `decision: allow`.
- **Normal.** `$H drive hook UserPromptSubmit '{"prompt":"rename the variable total to sum","session_id":"s3"}'`, then Stop with `"session_id":"s3"`: `decision: allow`.

## Gotchas

- Each recipe needs its own `session_id`: the "once" state is per session.
- A real session needs more turns after the block (ai-eval gives `--max-turns 40` to a fixture session).

## Proof paths

- success: the block.
- cancel: n/a (the owner cannot back out of a stop; the agent uses the skill or stops again).
- error: n/a.
- empty: the normal prompt passes.
- persistence: the once state: the second Stop passes.
- Unreachable: none.
