# Decisions (owner), newest first

Moved here from Claude auto memory on 2026-11-16 (auto memory is off: the repo is the one knowledge store).

## 2026-11-16: ship, merge, release
- Every PR goes through the owner. The agent merges only after the owner's latest message says merge or approve
  (merge-approval gate). No push to main or master. Agents never skip git hooks (no-verify gate).
- Feature done: the ship skill. After a merge: /improve-codebase-architecture and /retro (session start asks).
  The owner says release: the release skill (full audit, fix PRs, tag).
- Every project has a UI: ui-ux-pro-max on by default; kickoff makes 3 to 5 design variants; MASTER.md.
- Markdown only in its places (ai-docs-check in make check; adopt writes a baseline of today's files).
- Navigation: graphify for wide questions, Serena for exact symbols, rg for text.
- Tool upgrades: install.sh records versions (ai-versions); the session start asks for upgrade-review.
- No scheduler: every review runs on an event (a merge, a release, an upgrade, a session start).

## 2026-11-15
- One light profile, `dev-mac`, on all 3 machines (M3, old Intel Mac, ubuntu01). No scanners, no package audit,
  no install gate, no opencode, no box, no sandbox, no root layer. The `server` profile stays in the code, unused.
- skill-scanner is off in every profile (add `skill-scanner` to PROFILE_SCANNERS to turn it on).
- Full agent autonomy on dev-mac: the gates are secret-scan, pr-rules, merge-approval and no-verify.
- Newest stable version of every tool, no holds.
- No project tiers: every project is `tier: long`.
- All 27 Matt Pocock skills (6 global, 21 per project); skills-guide explains them.
- PR body: the Matt pr template plus a required Mermaid diagram.
- Git workflow close to Matt; local tracker in docs/ (no GitHub issues).
- scriptube: the owner finishes the open work first, then runs ai-adopt there.
- Per-machine projects folder: ~/work (old Mac: ~/openclaw/projects and ~/work).
