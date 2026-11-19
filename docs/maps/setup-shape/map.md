# Map: the shape of the AI setup

## Destination

One spec, approved by the owner, for a smaller setup with 3 layers (short rule text, git hooks for git rules,
narrow agent hooks for the rest). The spec states how each of the 5 owner goals is measured: the agent answers
short, follows the global rules, uses the defined skills, checks its own work, and follows the owner's git rules.
The map ends when nothing is left to decide before `to-tickets` can slice the spec.

## Notes

- Domain: the dotfiles `ai` branch. Evidence for each ticket: `docs/reports/setup-deep-audit-2026-11-18.md`.
- Build tickets that need no decision are in `docs/tickets/setup-audit/`. This map holds only decisions.
- The destination text comes from the owner's message of 2026-11-18. It was not grilled yet; the first ticket
  does that.
- Each session reads the report sections that its ticket names, not the whole report.
- Skills for each session: grilling and domain-modeling for a grilling ticket, research for a research ticket,
  prototype for a prototype ticket.
- Standing preference: measure before a rule is added or removed. A wall with more than 1 false block in 3
  becomes a hint (owner decision 2026-11-18).

## Decisions so far

<!-- one line per resolved ticket: gist, then the link -->

- [Can git hooks carry the git rules for each agent and each repo](issues/03-git-hooks-as-the-seam.md): some
  rules yes (commit and push on a protected branch, secrets, commit message); a global `core.hooksPath` alone
  does not work with husky and the pre-commit tool; `git add -A` and `--no-verify` have no hook point.

## Not yet specified

- The outcome eval: which tasks and which numbers prove that the smaller setup is not worse. It waits for the
  measures of the first ticket. A first build ticket exists (`docs/tickets/setup-audit/06-outcome-eval.md`).
- Codex: which of the new hook fields (`if`, `onFailure`) Codex has, and what replaces them there.
- The order of the change on the 3 machines, and how a machine goes back when the new shape fails.
- How "uses the defined skills" is counted when a skill is read as a file and not called.
- Which rules move to a git hook, after a test of git config hooks (git 2.54 or later) on a real machine. The
  research found no hook point for `git add -A`; that rule needs an agent hook.
- A home for the setup: own repo, CI. It waits for the profile decision.

## Out of scope

- The host layer of the server (`ubuntu-server` branch).
- New skills, and the UI and SEO tools.
- The verify tool of each project (tickets 08 to 10 of `verify-enforcement` hold that rollout).
