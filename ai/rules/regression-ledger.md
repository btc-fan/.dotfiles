# regression ledger (`docs/REGRESSIONS.md`, `ai-ledger`, edit nudge)

Our own tool (Tier 1 T3). Ideas: the Rust tidy check (`src/tools/tidy`, MIT/Apache-2.0, read 2026-11-12: the list
is machine-checked and exceptions only shrink) and pytest issue markers. No ready tool exists.

## Vendor rules (verbatim)
NOT FOUND (our own tool).

## When / when not
- Long tier only (`tier: long` in `.ai/enabled`). `ai-adopt --tier long` writes the template.
- One row per bug that reached the main branch, added in the fix PR with a test that failed before the fix:
  `R-012 | 2026-11-12 | area: src/billing/ | symptom: ... | cause: ... | test: tests/regressions/test_r012_x.py | reopened: 0`
- `area:` is a folder or a file path (more than one with commas); `src/bill` does not cover `src/billing/`. `reopened` goes up when the same symptom comes back.
- Flaky tests go under `## Quarantine` with a date: `- <test id> | since: YYYY-MM-DD | why`.
- Not for bugs found before merge, and not a task list.

## Enforcement
- L3 nudge (router PreToolUse, Edit/Write/MultiEdit/NotebookEdit): one line with the R-IDs and their tests,
  once per area per session (`ledger-nudge`).
- Stop: `stop-check` adds one note for areas that Bash changed (no Edit hook saw it).
- `ai-ledger --check` (in `make check`, long tier; `ai-doctor --project`): fields complete, test files exist and
  carry the id, no regression test without a row, rows never removed, `reopened` never down, quarantine only
  shrinks (no back-dated or re-dated line); stale areas and quarantine lines older than 14 days warn.
- PR gate (long tier): a `fix:` PR needs `Ledger: R-NNN` and a test file in its diff.

## Proof
- Should fire (EN): an Edit of `src/billing/refund.py` where R-012 has `area: src/billing/`.
- Should fire (RO): "modifica functia de refund din src/billing" (the edit gets the R-012 line).
- Should fire (RU): "поправь расчёт возврата в src/billing" (the edit gets the R-012 line).
- Should not fire: a second file in the same area in the same session; an edit outside every area; tier `mvp`.
- Signal: `[ai router: ledger-nudge]` in the context; `fired.jsonl`. Tests: `ai/tests/cases/ledger-nudge.json`,
  `ai/tests/test_tier1.py` (`t_ledger_*`).

## Setup checklist
- Install: nothing extra (`ai/bin/ai-ledger`, parser in `hooklib.py`).
- Per project: `ai-adopt --tier long` (template), first rows by hand from the fix history.
- Keys, telemetry: none.
- Verify: `ai-ledger --check --dir <repo>` exits 0; `ai-ledger --hits <file>` prints the reminder.
- Cleanup: delete `docs/REGRESSIONS.md` and `tests/regressions/`, or set the tier to `mvp`.
