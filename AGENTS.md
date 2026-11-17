# dotfiles (branch ai): the AI setup

## Map
- Owner guide: `docs/GUIDE.md` (how it works, scenarios, troubleshooting). Decisions and history: `docs/agents/notes.md`, `ai/SPEC-LOG.md`.
- Global rules: `ai/agents-md/*.md` (joined by `ai/bin/ai-render` into `~/.config/ai/AGENTS.md` and the Codex block). Routing rows: `ai/routing.yaml`.
- Router hooks: `ai/marketplace/plugins/ai-core/hooks/` (`router.py`, `hooklib.py`). The Hermes copies are generated.
- Installer: `install.sh` and `ai/adapters/*.sh`. Project layer: `ai/bin/ai-start` (`ai-adopt` is a link to it).
- Our skills: `ai/skills/<name>/SKILL.md`, linked into `~/.claude/skills` and `~/.agents/skills`.
- Check: `bash ai/tests/run.sh` (everything; about 10 min).
- Evals: `ai/bin/ai-eval` (fixture repos, install level, headless behaviour level); cases in `ai/evals/cases/*.json`.

## Project rules
<!-- Rules for this repo only, one line each. They may add or tighten the global rules, never loosen them. -->
- A gap in the setup is fixed in install.sh or an adapter, with a test, never as a manual step on one machine. Manual steps only for what a script cannot do (logins, trust dialogs).
- The owner gave full rights for this repo and its rollout: commit, push to origin/ai, install on the 3 machines, verify, without a stop for an OK.
- Never put the scanners, the install gate or root-layer steps back on a machine unless the owner asks (profile dev-mac everywhere).
