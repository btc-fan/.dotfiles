# 18: verify-ai-setup, the verify tool of this repo

**What to build:** the AI builds `verify-ai-setup` for this repo with the generator from ticket 01, and proves it once. The tool drives the AI setup the way an agent and the owner use it: hooks, CLIs and the installer, each on throwaway fixtures.

**Blocked by:** 01

**Status:** done

- [x] The generator makes `.agents/skills/verify-ai-setup/` (SKILL.md with Launch, Doctor, Drive, Evidence, Cleanup, Helpers), plus the committed link `.claude/skills/verify-ai-setup` -> `../../.agents/skills/verify-ai-setup`.
- [x] Each surface has a driver: the router hooks by a JSON payload and by a real headless `claude -p` and `codex exec --json` session that loads this checkout's plugin code; the CLIs (ai-start/ai-adopt, ai-doctor, ai-check-detect, agent-audit, ai-precommit) on throwaway fixture repos; `install.sh --dry-run --yes` per profile (dev-mac, server) with a temp HOME.
- [x] One executable helper with launch (fixture kinds: empty, docs-only, python-with-tests, web-app, existing-project-with-own-Done), doctor, drive per surface, evidence and cleanup. Fixtures live in a temp folder. No run writes to `~/.claude` settings or plugins, `~/.codex` config, or `~/.dotfiles-ai`.
- [x] Evidence goes to `.verify/evidence/<run>/` (gitignored). Each run writes `run.log` with the 4 lines of the ticket 01 contract.
- [x] Feature map: `features/README.md` in full sweep order, one file per feature (router gates, stop rules, skill card, ai-adopt per fixture kind, ai-check-detect, Playwright per profile, verify hooks as planned), and `multi-surface-journeys.md`.
- [x] Proved once: launch, doctor, 2 features end to end (one through a real headless `claude -p` session where a gate denies), cleanup, and the evidence is still there.
- [x] A test runs the helper (launch, doctor, a hook drive, cleanup) and checks the run.log contract and that the evidence survives cleanup.
