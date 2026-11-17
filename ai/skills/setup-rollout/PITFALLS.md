# Setup rollout: pitfalls

Each item happened on a real machine. Machine names are generic.

## Machine

- **Agent detection (second Mac).** `claude` and `codex` live under `~/.nvm/versions/node/<v>/bin`. The installer
  printed "Agents: herdr." and skipped every Claude step (rules block, OMC note). Run it from a login shell and
  add `--agents claude,codex,herdr`. Check line 2 of the install output.
- **Remote PATH.** A non-login ssh shell has no `~/.local/bin`, Homebrew or nvm. macOS:
  `ssh <host> "zsh -lc 'bash -s'" < script.sh`. Linux: `ssh <host> 'bash -s' < script.sh`.
- **RTK by hand (owner choice).** Put `off` in `~/.config/ai/rtk-hook` (or `AI_RTK_HOOK=off` for `install.sh`).
  The installer then writes no RTK hook. `ai-doctor` reports PASS "RTK hook off by owner choice". Keep an owner
  line in `~/.claude/CLAUDE.md`, for example "never run rtk init -g". Before ddabcc1, `ai-doctor` failed here (R-003).
- **Old OMC block.** An old `<!-- OMC:START -->` block in `~/.claude/CLAUDE.md` becomes the 3-line note when
  `install.sh` runs with Claude detected. Owner text stays.
- **Live sync from the dev checkout.** The dev checkout has post-merge and post-rewrite hooks. They run `ai-sync`
  into the live `~/.codex`. When you merge unreviewed branches there, use `git -c core.hooksPath=/dev/null merge ...`.
  Never run `git commit --amend` there. A sync that went live by accident:
  `AI_HOME=~/.dotfiles-ai ~/.dotfiles-ai/ai/bin/ai-sync`.
- **Dry run from a worktree.** The plan is safe. A real install from a worktree links everything to it.
- **Audit guard.** A newest-stable tool that fails `agent-audit` stays at the audited version (seen: OMC 5.8.6 held
  at 5.8.5). This is not an error.

## Project

- **Uncommitted leftovers (history).** Before ddabcc1, `ai-adopt` left `.ai/enabled`, the Map timing and a
  Libraries row uncommitted (R-001). Now it commits every file it writes. A dirty tree after a run is a bug: report it.
- **Owner Makefile flag lost (history).** A rerun once dropped an owner flag in the managed Makefile block (R-002).
  Now a rerun keeps owner flags. Still check them (step 5).
- **Pasted output fired stop rules (history).** Pasted session output fired the `diagnosing-bugs` and `tdd` stop
  rules (R-004). The router now ignores code fences and lines that start with `⏺`, `❯`, `>` or `│`, and product
  names. An `<agent-message>` hand-back counts as a notification, not a prompt.
- **Merge OK.** The merge OK comes only from the owner's own typed lines. A pasted "merge" never sets it (R-005).
- **Add-only guard.** An update must not change owner text. If `ai-adopt` would, it writes nothing, prints the diff
  and exits non-zero. Do not edit the owner text to make it pass. Do not move project rules into or out of an
  AI block. Show the diff to the owner.
- **Rule inside an AI block.** The owner asks for a new project rule: write it under `## Project rules`, never
  inside an AI block. A later update can replace a block.
- **Stop hook against an owner rule.** See step 5.5 in `SKILL.md`.
- **Rendered L0 warning.** `ai-doctor` in a dev checkout can say "out of date: ai/build/...". Run `ai-render`
  there. Do not treat it as a machine fault.
