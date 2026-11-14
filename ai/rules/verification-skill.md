# verification skill (pstack create-verification-skill, maintain-verification-skill; project verify-<app>)

Version: newest commit of github.com/cursor/plugins (folder `pstack/`; no vX.Y.Z tags for pstack, so the default
branch HEAD, SPEC 23). Read and audited at intake: commit 3dbd22ff12742fb28c9700b9760baa29ed41dc13, pstack plugin
version 0.15.36. License MIT, Copyright (c) 2026 Lauren Tan (kept in every copy). Ideas also read (not copied):
poteto/verification-skill-example (verify-atlas, a feature map per area) and kody-hq/kody `control-kody` (one CLI:
doctor, dev, request, browse, verify <feature>, health; "CI green is not enough", local verification first).

## Vendor rules (verbatim)
The verbatim text is in `ai/rules/vendor/pstack-verification/` (both SKILL.md files, the feature-map example,
LICENSE, SOURCE.md). Deviation: U+2014 became " - " (repo rule). Key lines: "Every serious project needs a scripted
way to drive the real app and prove behavior: launch it, exercise a feature the way a user would, and capture
evidence." "A generated skill that was never executed is a draft, not a deliverable." "A feature map rots the moment
the app changes."

## When / when not
- `/create-verification-skill` (typed; `disable-model-invocation: true`): once per project, when it has no scripted
  way to prove UI, CLI or service behavior. It writes `.agents/skills/verify-<app>/` (SKILL.md: Launch, Doctor,
  Drive, Evidence, Cleanup, Helpers; `features/README.md` plus one file per feature) and proves it once end to end.
  Then `ai-adopt` adds the committed link `.claude/skills/verify-<app>` -> `../../.agents/skills/verify-<app>`.
- `/maintain-verification-skill` (typed): when the session status says the map is stale (25 code commits, or 30
  days with code commits, since the feature map last changed), and at least monthly in an active project.
- `verify-<app>` (the project's own skill): in tier mvp and long, before "done" on every user-visible change, in
  this order: (a) `check-fast` green; (b) `verify-<app>` on the changed feature(s): launch, doctor, drive every
  reachable entry point the feature file lists, capture evidence (screenshots and DOM or ARIA for UI, response
  bodies, DB rows, logs for backends), clean up but keep the evidence; (c) only after (b) passes, add or extend e2e
  tests that encode the proven journey (Playwright with screenshot comparison for UI, HTTP or pytest level for
  APIs, as the stack allows); (d) the PR Verify field cites the evidence path and the e2e test.
- Tier try: optional. Not for library-only repos with no user surface (then the tests are the proof).
- Never generate a verify skill for a project without the owner asking (it runs the app).

## Enforcement
- L1: the session-start status says "Verify skill: verify-<app> (N features)", "... stale ...: run
  /maintain-verification-skill" or "missing, run /create-verification-skill".
- L3: row `verify-before-done` after the first code edit of a session (tier mvp, long; only with a verify skill).
- L2: the feature flow (`feature-grill`) names the verify feature per slice and the Done order.
- L4: pr-rules: with a verify skill and app code in the diff, Verify must name the verify run, an evidence path
  and an e2e test path.
- L7: `ai-doctor --project`: WARN when missing (mvp, long), stale, or without the Claude link.
- Text: Done item 1 in the repo AGENTS.md. The root AGENTS.md carries nothing extra (hooks over text).

## Proof
- Should fire (EN): `/create-verification-skill` in a repo with a web UI: `.agents/skills/verify-<app>/` with a
  feature map; "verify the checkout change before you say done" in a project that has one: the agent runs
  `verify-<app>` on the checkout feature and saves evidence.
- Should fire (RO): "verifica schimbarea de la cos cu skill-ul de verificare inainte sa termini".
- Should fire (RU): "проверь изменение корзины навыком проверки, прежде чем закончить".
- Should not fire: "fix the typo in the README" (no code edit, no hint); a project in tier try (hint quiet).
- Signal: Skill or Read of `verify-<app>`, evidence files under the path the skill names, `[ai router:
  verify-before-done]`. Tests: `ai/tests/test_tier1.py` (`t_verify_*`, `t_adopt_verify_link`),
  `ai/tests/cases/verify-before-done.json`, `pr-rules.json`, `test_resolve.py` (`t_bash_pstack`).

## Setup checklist
- Install: `install.sh` links `ai/skills/create-verification-skill` and `ai/skills/maintain-verification-skill`
  into `~/.claude/skills` and `~/.agents/skills` (like every own skill). `PSTACK_SOURCE` in `ai/pins.env`: when
  upstream moves, `pstack_src` clones, checks for symlinks, adapts (`ai/lib/pstack_adapt.py`), runs `agent-audit
  dir`, installs into the plugin source dir and `pstack_link` points the links there; the run warns that the
  vendor copy is behind (review the diff, refresh `ai/rules/vendor/pstack-verification` and `ai/skills`).
  Hermes: not wired (typed skills only; UNVERIFIED for Hermes).
- Keys, telemetry, network: none (the generated project skill may start the app locally).
- Per project: `/create-verification-skill`, review the generated skill, commit `.agents/skills/verify-<app>/`,
  run `ai-adopt` (the `.claude` link). The `.gitignore` block shares `.claude/skills/verify-*`.
- Verify: `ls ~/.claude/skills/create-verification-skill/SKILL.md ~/.agents/skills/maintain-verification-skill/SKILL.md`;
  `ai-doctor --project <repo>` shows the verify skill line.
- Cleanup: remove the two links; delete `<plugin src>/pstack-verification`; per project delete
  `.agents/skills/verify-<app>/` and the `.claude` link.
