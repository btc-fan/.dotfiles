# dotfiles (branch ai): the AI setup

## Map
- Owner guide: `docs/GUIDE.md` (how it works, scenarios, troubleshooting). Decisions and history: `docs/agents/notes.md`, `ai/SPEC-LOG.md`.
- Global rules: `ai/agents-md/*.md` (joined by `ai/bin/ai-render` into `~/.config/ai/AGENTS.md` and the Codex block). Routing rows: `ai/routing.yaml`.
- Router hooks: `ai/marketplace/plugins/ai-core/hooks/` (`router.py`, `hooklib.py`; `rtk-hook` is the Claude RTK wrapper, silent in auto mode; `README.md` lists every gate and stop rule). The Hermes copies are generated.
- Gates, stop rules, skill card, winner table: rows and the `skills:` and `winners:` blocks of `ai/routing.yaml`; one contract per rule in `ai/rules/` (for example `winner-gate.md`, `skill-card.md`).
- Installer: `install.sh` and `ai/adapters/*.sh`. Project layer: `ai/bin/ai-start` (`ai-adopt` is a link to it); add-only updates and the owner-text guard: `ai/lib/ownertext.py`. One-command update of a machine and its adopted projects: `ai/bin/ai-update` (project list: `~/.local/state/ai/projects`).
- Our skills: `ai/skills/<name>/SKILL.md`, linked into `~/.claude/skills` and `~/.agents/skills`.
- Check: `bash ai/tests/run.sh` (everything; about 10 min).
- Evals: `ai/bin/ai-eval` (fixture repos, install level, headless behaviour level); cases in `ai/evals/cases/*.json`.
- Verify tool of this repo: `.agents/skills/verify-ai-setup/` (helper `verify`: launch, doctor, drive, cleanup on temp fixtures; evidence in `.verify/evidence/<run>/`). Run it before a PR that changes a gate, a stop rule, a CLI or the installer.
- Work files: specs `docs/specs/`, tickets `docs/tickets/<slug>/` (finished ones in `done/`), reports `docs/reports/`, research `docs/research/`, the setup-shape map and its issues `docs/maps/setup-shape/`.

## Project rules
<!-- Rules for this repo only, one line each. They may add or tighten the global rules, never loosen them. -->
- Mandatory (owner 2026-11-19): this repo, branch `ai`, is the one source of truth of the AI setup. Every setup change, refactor included, is made here, and machines and projects get it only by a command (`install.sh`, `ai-sync`, `ai-adopt`): plug and play. A step that needs a hand edit of a generated file in a project or on a machine is a setup bug: fix it here with a test, then rerun the command. Hand steps only for what a script cannot do (logins, trust dialogs). The OS bases (`main` macOS, `windows`, `ubuntu-server`) are separate branches by design.
- Rights in this repo (owner 2026-11-20): commit and push a feature branch without a question. A merge to `ai` and an install on a machine wait for the owner's OK (Standing permission).
- Never put the scanners, the install gate or root-layer steps back on a machine unless the owner asks (profile dev-mac everywhere).
- This repo is generic: it is installed into any project. New code, tests and docs name no local project, machine or user. A test against a local project runs from a scratch folder and is deleted after (owner 2026-11-18).
