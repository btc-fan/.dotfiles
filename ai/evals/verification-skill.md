# Eval cases: verification skills and the Done order

Run method: `HOWTO.md`. Format: tool | FIRE (EN ; RO ; RU) | NOT (a ; b) | signal. Pass bar: fire 3 of 3, NOT 0 of 2.
Copied from the proof section of `ai/rules/verification-skill.md`. Typed skills (`/create-verification-skill`,
`/maintain-verification-skill`) are proven by the UserPromptExpansion log, not by model choice.

- create-verification-skill (typed) | `/create-verification-skill` in a repo with a web UI ; "/create-verification-skill pentru aplicatia asta" ; "/create-verification-skill для этого репо" | NOT "explain how the tests are organised" ; a plain mention "we should make a verification skill some day" | signal: `.agents/skills/verify-<app>/SKILL.md` and `features/README.md` written, one feature driven, evidence kept after cleanup
- maintain-verification-skill (typed) | `/maintain-verification-skill` after the status says stale ; "/maintain-verification-skill, harta e veche" ; "/maintain-verification-skill, карта устарела" | NOT "add a feature" ; "fix the failing test" | signal: outcome clean, changed (one PR, only the skill folder) or blocked
- verify-<app> Done order (project with verify-shop, tier mvp) | "add a discount field to checkout, then finish" ; "adauga un camp de reducere la checkout si termina" ; "добавь поле скидки в оформление заказа и закончи" | NOT "fix the typo in the README" ; the same prompt in tier try (verify optional) | signal: `[ai router: verify-before-done]`; order check-fast, verify-shop run with evidence, then e2e test; PR Verify cites evidence and test
- pr-rules verify evidence (project with a verify skill, app code in the diff) | `gh pr create` with `Verify: make check passed` only ; "deschide PR-ul" (body without the verify run) ; "создай PR" (body without the evidence path) | NOT a docs-only PR ; a body that names verify-shop, artifacts/... and tests/e2e/... | signal: `DENY pr-rules` with "Verify: the verify-shop run"
