# pr-rules gate (PR body parts and fields)

Our own gate in `hooklib.py` (`gate_pr`). Tier fields added 2026-11-14 (Tier 1 T4). Template since
2026-11-15 (owner): the `pr` skill of Matt Pocock (Summary, Evidence, Merge Danger) plus a required Mermaid diagram. Rules copied as ideas from
tests-checker-action (MIT), the SwiftLint Dangerfile (MIT) and the Zed dangerfile (GPL, idea only: reject
placeholder text), read 2026-11-12.

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
- Every `gh pr create` and `gh pr edit` with a body (also behind `rtk` and `rtk proxy`).
- Always: a ```mermaid block and the `<!-- author-sessions` block.
- Fields that block (no tiers since 2026-11-15, every project is long): `Evidence` (check command and the tail of
  its output; a `## Evidence` heading or an `Evidence:` label), `Door:` (must say one-way or two-way),
  `Blast Radius:`. With a verify-<app> skill and app code changed, Evidence also names the skill run, an evidence
  path and the e2e test.
- Fields that only warn (ticket 13, 2026-11-18): `Docs:` (files, or "none, because ..."), `Changed guards:` (each
  edited or removed test and why, or "none"), and on a fix PR `Ledger: R-NNN`.
- Body file: `$VAR`, `"$VAR"`, `${VAR}` come from a simple `VAR=value` earlier in the same command; a `cd`
  earlier in the command sets the folder. An unreadable body file gives "could not read the body file <path>".
- Placeholder text (`TODO`, `TBD`, `<...>`, `...`, `n/a`) counts as missing.
- A `fix:` PR (title `fix`, `bugfix`, `hotfix`) needs a test file in its diff against the base .
- Over 400 changed lines (lockfiles and generated files left out): a warning, never a block.
- `--fill`, `--fill-first`, `--fill-verbose`, `--web`: refused (the gate cannot see the body).

## Enforcement
- L4 gate, deny (Codex: deny with `decision: block`). Owner skip: `sudo ai-gate-skip pr-rules <min> <why>`.
- L0: `ai/agents-md/50-pull-requests.md` lists the parts.
- No diff (no base branch found): the test-file and size checks are skipped with a note in the context. A named
  base (`--base ai`) is `origin/ai`, else `ai`, else fetched (`git fetch origin ai`, 5 s); never main in its place.
- Only `fix:`, `fix(scope):`, `bugfix:`, `hotfix:` titles are fix PRs. A test file is a test name or a code file
  under tests/ (tests/README.md is not).
- Limit: `gh api repos/.../pulls -f body=...` and the GitHub web page are not checked (no `gh pr` command).

## Proof
- Should fire (EN): `gh pr create --title x --body "fix"` (BLOCK).
- Should fire (RO): "deschide un PR cu titlul fix: rotunjire" with no test in the diff (BLOCK).
- Should fire (RU): "создай PR" with `Evidence: TODO` in the body (BLOCK).
- Should not fire: a body with mermaid, Evidence, Door, Blast Radius and the author-sessions block ; `gh pr edit 12
  --add-label bug`.
- Signal: `DENY pr-rules` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/pr-rules.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k pr-rules`; `ai-doctor --live` canary (a PR without the blocks is denied).
- Cleanup: none (the rule is part of the router).
