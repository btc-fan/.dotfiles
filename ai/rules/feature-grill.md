# feature-grill (questions first before feature code)

Home since rules-that-hold 12 (2026-11-20): the model-invocable skill `ai/skills/feature-kickoff/SKILL.md` (its
description holds the trigger words in EN, RO and RU) and 1 index line in `ai/agents-md/80-tool-catalog.md`. The
router row `feature-grill` and its `{feature_flow}` text are gone. The grill skill is mattpocock `grill-with-docs`
or `grilling`, see `mattpocock-skills.md`. The text below is the old row.

## Vendor rules (verbatim)
NOT FOUND for the row; the grilling skill text is in `mattpocock-skills.md`.

## When / when not
- A feature prompt: a verb (add, implement, build, create, introduce; RO adauga, implementeaza, construieste,
  creeaza; RU добавь, реализуй, сделай, создай, внедри) plus a feature noun (feature, endpoint, page, screen,
  command, option, flag, setting, integration, flow, button, form, report, export, webhook, notification, mode),
  or "add support for", "change how", "new feature".
- Then, where the project links grill-with-docs (`skills:` line, tier mvp and long by default): grill-with-docs
  (questions, then GLOSSARY.md and docs/adr), for a feature touching 3+ files to-spec, then to-tickets (slices
  with acceptance criteria and the verify-<app> feature each slice must pass; tickets in docs/tickets/, never
  GitHub issues without the owner), then build slice by slice in the Done order (check-fast, verify-<app>
  evidence, then e2e). Elsewhere (tier try, not adopted): the grilling skill, one round of questions.
- grill-with-docs, to-spec and to-tickets are typed-only (`disable-model-invocation: true`): the Skill tool cannot
  run them. The hint gives the SKILL.md path that exists for the agent (project link `.claude/skills/<name>/` for
  Claude, `.agents/skills/<name>/` for Codex, else the machine copy). The agent reads that file, follows it, and
  tells the owner the typed form (`/grill-with-docs`). Proof: a Skill call or a Read of that SKILL.md.
- Not: trivial changes (typo, rename, one-line fix, a config value): the agent answers "none needed".
- Not: "new app" or "kickoff" (the existing tie-break already routes it to grilling).

## Enforcement
- L2: the router adds the forced-eval line (YES or NO, "none needed" allowed); the text comes from the
  `{feature_flow}` placeholder (router.py), so it follows the project's links. No gate.
- L7: `proof: skill:...grill`; a fired row without a grilling call goes to `misses.jsonl`.

## Proof
- Should fire (EN): "add a CSV export endpoint to the API".
- Should fire (RO): "adaugă o funcționalitate de export în CSV".
- Should fire (RU): "добавь функцию экспорта в CSV".
- Should not fire: "fix the typo in the README"; "исправь опечатку в README"; "build the project and run the tests".
- Signal: `- feature-grill:` in the L2 context; Skill `grilling` call. Tests: `ai/tests/cases/feature-grill.json`.

## Setup checklist
- Install: nothing extra (routing row; the grilling skill is installed with the mattpocock skills).
- Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k feature-grill`; after a week, `misses.jsonl` rows for `feature-grill`.
- Cleanup: remove the row from `ai/routing.yaml`, run `ai-render`.
