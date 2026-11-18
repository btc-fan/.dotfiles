# dotfiles (branch ai): the AI setup

## Map
- Owner guide: `docs/GUIDE.md` (how it works, scenarios, troubleshooting). Decisions and history: `docs/agents/notes.md`, `ai/SPEC-LOG.md`.
- Global rules: `ai/agents-md/*.md` (joined by `ai/bin/ai-render` into `~/.config/ai/AGENTS.md` and the Codex block). Routing rows: `ai/routing.yaml`.
- Router hooks: `ai/marketplace/plugins/ai-core/hooks/` (`router.py`, `hooklib.py`; `rtk-hook` is the Claude RTK wrapper, silent in auto mode; `README.md` lists every gate and stop rule). The Hermes copies are generated.
- Gates, stop rules, skill card, winner table: rows and the `skills:` and `winners:` blocks of `ai/routing.yaml`; one contract per rule in `ai/rules/` (for example `winner-gate.md`, `skill-card.md`).
- Installer: `install.sh` and `ai/adapters/*.sh`. Project layer: `ai/bin/ai-start` (`ai-adopt` is a link to it); add-only updates and the owner-text guard: `ai/lib/ownertext.py`.
- Our skills: `ai/skills/<name>/SKILL.md`, linked into `~/.claude/skills` and `~/.agents/skills`.
- Check: `bash ai/tests/run.sh` (everything; about 10 min).
- Evals: `ai/bin/ai-eval` (fixture repos, install level, headless behaviour level); cases in `ai/evals/cases/*.json`.
- Verify tool of this repo: `.agents/skills/verify-ai-setup/` (helper `verify`: launch, doctor, drive, cleanup on temp fixtures; evidence in `.verify/evidence/<run>/`). Run it before a PR that changes a gate, a stop rule, a CLI or the installer.
- Work files: specs `docs/specs/`, tickets `docs/tickets/<slug>/` (finished ones in `done/`), eval reports `docs/reports/`.

## Project rules
<!-- Rules for this repo only, one line each. They may add or tighten the global rules, never loosen them. -->
- A gap in the setup is fixed in install.sh or an adapter, with a test, never as a manual step on one machine. Manual steps only for what a script cannot do (logins, trust dialogs).
- The owner gave full rights for this repo and its rollout: commit, push to origin/ai, install on the 3 machines, verify, without a stop for an OK.
- Never put the scanners, the install gate or root-layer steps back on a machine unless the owner asks (profile dev-mac everywhere).
