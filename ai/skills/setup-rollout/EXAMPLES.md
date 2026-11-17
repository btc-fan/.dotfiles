# Setup rollout: real examples

Proven on 2026-11-16 and 2026-11-17: three machines, four projects. Names are generic.

- **Main Mac, docs-only repo.** Adopted from main. `ai-adopt` made branch `ai-adopt`. The Makefile got Markdown
  checks only (`ai-docs-check`). Merged locally: the repo had no remote.
- **Home server, crawler project (Python, code).** Machine update by `git pull` (the hook ran `ai-sync`).
  `ai-doctor` 0 fail. Re-adopt said "nothing to change". `make check-fast` was red on one date-dependent test.
  A separate project PR fixed it, with a regression line. The Stop hook stayed off until it was green.
- **Second Mac, web app project with owner rules.** `claude` and `codex` under nvm: the install needed
  `--agents claude,codex,herdr`. RTK by hand: switch file. Re-adopt kept 11 owner rules, 30 own skills, one
  project hook and `.claude/CLAUDE.md`. Stop hook off: an owner rule forbids full-suite runs while working.
- **After each merge to `ai`.** Main Mac: `checkout --detach origin/ai`, then `ai-sync`. Home server: `git pull`.
  Second Mac: `git pull`, plus `install.sh --yes --agents claude,codex,herdr` when the installer changed.
- **State after PR #4 (ddabcc1, 2026-11-17).** All three machines at ddabcc1, `ai-doctor` 0 fail,
  `grep -c "^Standing permission" ~/.config/ai/AGENTS.md` = 1.
