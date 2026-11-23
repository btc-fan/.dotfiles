---
name: feature-kickoff
description: 'Use when the owner asks to add, build or implement a feature, endpoint, page or command ("adaugă o pagină", "implementează funcția", "добавь страницу", "сделай функцию"). Starts the feature flow: worktree, grill, spec and tickets, implement, ship. Not for a typo or a one-line fix.'
---

# Feature kickoff

This skill is the order of the feature flow. Each step points to the skill that owns it. Read that skill and follow it; this file does not repeat it.

A typed-only skill (`grill-with-docs`, `to-spec`, `to-tickets`, `implement`) has no Skill tool call. Read `.claude/skills/<name>/SKILL.md` in the project (Codex: `.agents/skills/<name>/SKILL.md`) and follow it.

A trivial change (a typo, a rename, a one-line fix, a config value) skips steps 2 and 3.

## Steps

1. **Worktree.** Make a worktree and a branch named after the feature slug: `git worktree add ../<repo>-<slug> -b <slug> origin/<main>`. Work only there. Done when `git branch --show-current` prints the slug.
2. **Grill.** Run `grill-with-docs` where the project links it, else the `grilling` skill. Done when the owner answered the questions and GLOSSARY.md and docs/adr hold the decisions.
3. **Spec and tickets.** A change that touches 3 or more files: `to-spec`, then `to-tickets`. The tickets go in `docs/tickets/<slug>/`, never in GitHub issues without the owner. Done when each ticket names its acceptance criteria and the verify feature it must pass.
4. **Implement.** For each ticket: `implement`. Each ticket ends with `make check-fast` green, the `verify-<app>` skill on the changed feature (evidence kept), then the tests for the proven journey. Done when every ticket is in `done/`.
5. **Ship.** Run the `ship` skill. It ends when the owner is asked to merge.
