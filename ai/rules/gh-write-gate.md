# gh-write gate (gh writes ask the owner)

Our own gate (`routing.yaml` rule `gh-write`; code `hooklib.py`). Added 2026-11-16. Rule: `gh` is read-only unless the
owner asks (root rules, "Code navigation").

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
- Reads pass: `pr view|list|diff|checks|status|checkout`, `issue view|list|status`, `repo view|list`,
  `run view|list|watch`, `workflow view|list`, `auth status`, `search`, `status`, `gh api` as a GET.
- `gh pr create|edit|ready|merge` go to their own gates (pr-rules, ship, merge-approval).
- Every other write asks the owner: `issue create|comment`, `repo edit`, `release`, `label`, an unknown subcommand,
  `gh api` with `-X POST|PUT|PATCH|DELETE` or with fields (`-f`, `-F`, `--input`).

## Enforcement
- L4 gate: Claude asks the owner (permission prompt). Codex has no ask: deny with the message.
- Owner skip: `sudo ai-gate-skip gh-write <min> <why>`.

## Proof
- Should fire (EN): "Create a GitHub issue for this bug." Asks first. RO: "creeaza un issue pe GitHub". RU: "создай issue на GitHub".
- Should not fire: `gh pr view 3`, `gh issue list`, `gh api repos/x/y` (GET).
- Signal: an ask or `DENY gh-write` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/gh-write.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k gh-write`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
