# Skill card

At session start the router adds the skill card: the must-use skills with their trigger lines, and the typed-only skills with the SKILL.md path to read. A repo without the AI base also gets `no-ai-base`.

## Sub-features

- `card-start`: the card on `startup`, `resume` and `clear`.
- `card-no-base`: `no-ai-base` in a repo without `.ai/base-version`.
- `card-adopted`: `project-knowledge`, `serena` and `graph` in an adopted repo.

## How to get to it (user POV)

- Start, resume or clear a Claude or Codex session in a repo.

## Driving it with verify

Preconditions: `empty` and an adopted fixture (see ai-adopt.md), `doctor: PASS`.

- **Start, no base.** `$H drive hook --fixture empty SessionStart '{"source":"startup"}'`. Expect `rules fired: no-ai-base`; `NN-hook.txt` has `[ai router: skill-card] Must-use skills (the router checks them):`.
- **Resume.** The same with `{"source":"resume"}`: the card text again.
- **Adopted.** `$H drive hook --fixture python-with-tests SessionStart '{"source":"startup"}'` after ai-adopt: `rules fired: graph, project-knowledge, serena` and the card.
- **Real session.** A `$H drive session claude --fixture empty ...` run: the stream has a `hook_response` for `SessionStart:startup` with `[ai router: no-ai-base]` and `[ai router: skill-card]`.

## Gotchas

- `skill-card` is context text, not a rule row: it is not in `rules fired`. Read the output.

## Proof paths

- success: the card on startup.
- cancel: n/a.
- error: n/a (no input to get wrong; a broken routing.json is a doctor FAIL first).
- empty: the `empty` kind: `no-ai-base` plus the card.
- persistence: `resume` and `clear` bring the card back.
- Unreachable: `compact` in a real session. Blocked by: a headless `claude -p` run is too short to compact. Route tried: the payload `{"source":"compact"}` works.
