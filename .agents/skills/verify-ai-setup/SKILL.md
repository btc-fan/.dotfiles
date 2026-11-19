---
name: verify-ai-setup
description: "Verify the AI setup of this dotfiles checkout the way agents and the owner use it: router hooks (JSON payloads and real headless claude -p and codex exec sessions), the project CLIs (ai-adopt, ai-doctor, ai-check-detect, agent-audit, ai-precommit) and install.sh --dry-run per profile, all on throwaway fixtures. Use before a PR that changes a gate, a stop rule, a CLI or the installer, and to prove a fix in this repo."
---

# verify-ai-setup

The "app" is this checkout's AI setup. It has 3 surfaces: the ai-core router hooks, the CLIs in `ai/bin`, and `install.sh`. One helper drives all 3 on fixtures in a temp folder and keeps evidence in this checkout.

Helper (run from any folder of the checkout):

```
H=$(git rev-parse --show-toplevel)/.agents/skills/verify-ai-setup/verify
$H --help
```

## Launch

```
$H launch --label <what> empty docs-only python-with-tests web-app existing-project-with-own-Done
```

- Name only the kinds you drive. Each kind is a git repo on `main`, with one commit pushed to a local bare remote `remotes/fixture-owner/<kind>.git`.
- `empty`: no files. `docs-only`: Markdown. `python-with-tests`: the ai-eval app (pyproject, pytest test, Makefile), no verify skill. `web-app`: Node, 3 pages, `node --test`. `existing-project-with-own-Done`: the Python app plus an AGENTS.md with the owner's own `## Done`.
- `dotfiles-worktrees`: a dotfiles dev worktree on `main` and its installed copy `<tmp>/home-sync/.dotfiles-ai`. They share the git hooks from this checkout's `ai-sync --install-hook`.
- A fake `gh` is first on the drive PATH. It logs to `<tmp>/gh.log` and never reaches GitHub.
- Ready means: launch printed `run:`, `evidence:` and one path per kind.
- Each launch is a new run. After a failed doctor, or after a change to this checkout's code, launch again.

## Doctor

```
$H doctor              # before any session drive
$H doctor --no-agents  # hooks, CLIs and installer only
```

It runs once per run and writes the `doctor:` line of `run.log`. It checks:

- `checkout`: the run was launched from this checkout (`git rev-parse --show-toplevel`). Another worktree has its own `.verify/` and its own runs.
- `commit`: HEAD is still the commit of the run.
- `plugin`: a session loads `--plugin-dir <checkout>/ai/marketplace/plugins/ai-core`, and its router resolves `ai_home` to this checkout.
- `routing`: `ai-render --profile dev-mac` wrote `routing.json` into the run's temp folder (sessions get it as `AI_ROUTING_JSON`).
- `fixture`, `fake-gh`: each fixture is on `main` with a temp origin; the drive PATH finds the fake gh.
- `isolation`: the temp folder is outside `~/.claude`, `~/.codex`, `~/.dotfiles-ai` and the checkout. Launch recorded hashes of `~/.claude/settings.json`, `~/.claude/plugins/installed_plugins.json`, `~/.codex/config.toml`, `~/.codex/hooks.json`, the git state of `~/.dotfiles-ai` and the link targets in `~/.claude/skills` and `~/.agents/skills`; cleanup compares them.
- `claude`, `codex`: installed and logged in (`claude auth status`, `codex login status`).

## Drive

The feature map in [features/README.md](features/README.md) gives the recipe per feature, in sweep order. Cross-surface flows are in [multi-surface-journeys.md](multi-surface-journeys.md). The drivers:

- **Hook payload:** `$H drive hook [--fixture K] [--agent claude|codex] EVENT 'JSON'`. It pipes the payload into this checkout's `router.py` with a temp HOME and state folder. It prints `decision: allow|deny|ask|block`, the rules fired and the router errors. Drives with the same `session_id` share state (a prompt, then a Stop).
- **Headless session:** `$H drive session claude|codex [--fixture K] [--max-turns N] [--plugin-dir P] [--allow RULE] 'PROMPT'`. The command comes from `ai-eval` (`agent_cmd`, `child_env`, the stream scorer).
  - Claude: `claude -p PROMPT --output-format stream-json --verbose --max-turns 40 --permission-mode acceptEdits --allowedTools 'Bash(gh *)' ... --plugin-dir <checkout>/ai/marketplace/plugins/ai-core --settings '{"enabledPlugins": {"ai-core@ai": false}, "env": {<env.list>}}' --strict-mcp-config`. The installed ai-core stays off; the stream's `init` event names the plugin path. The `env` is this checkout's `ai/adapters/env.list`, as install.sh writes it into the Claude settings env.
  - Claude options: `--max-turns N` for a long session (the timeout grows to 20 s per turn); `--plugin-dir P` loads a stand-in plugin, for example a skill under test that is not installed; `--allow RULE` adds one allowed tool, for example `--allow Bash` for a command with a variable.
  - Codex: `codex exec --json -s workspace-write PROMPT` with `CODEX_HOME=<tmp>/codex-home`: a link to `~/.codex/auth.json`, this checkout's `codex-hooks.json` as user hooks, and trust from `aiconf.py codex-trust-hooks`. The env.list values are in its process env.
  - It prints the ai-core path, the rules fired, the `[ai gate <id>]` lines seen, the tool calls, and whether a branch moved on the remotes of its own fixture.
  - Parallel drives are safe: each drive gets its own `NN`, and sessions in different fixtures do not see each other's pushes. Two sessions in one fixture share the work tree and the remote.
- **CLI:** `$H drive cli [--fixture K] [--timeout S] [KEY=VALUE ...] NAME [ARG ...]`. It runs `<checkout>/ai/bin/NAME` in the fixture, in its own PTY, with the ai-eval throwaway HOME (`<tmp>/home`) and `AI_GITHUB_OWNERS=fixture-owner`. `KEY=VALUE` sets env, for example `AI_PROFILE=server`. It saves the transcript, the exit code and `git status --short` after.
- **Installer:** `$H drive install dev-mac|server`. It runs `install.sh --dry-run --yes --profile P --user` with HOME, `CLAUDE_CONFIG_DIR` and `CODEX_HOME` in a temp folder. It prints the real files that changed (must be `none`) and the files the dry run left in the temp HOME.
- **Merge:** `$H drive merge dev|installed`. It runs a real `git merge` in a worktree of the `dotfiles-worktrees` fixture with HOME=`<tmp>/home-sync`. It prints the hook version and whether HOME changed.

## Evidence

- Folder: `<checkout>/.verify/evidence/<run>/`, committed with the PR (`summary.md` first). `<run>` is
  `<branch>_<label>_<DD-MM-YYYY>_<HH-MM-SS>` (UTC), for example
  `verify-evidence-in-git_evidence-in-git_19-11-2026_17-30-01`.
- `run.log`: the helper writes `commit:` at launch, `doctor:` at doctor, `db_writes: no` and `finished:` at cleanup. Never edit it by hand. This tool has no database: `db_writes` is always `no`.
- One file per drive: `NN-hook.txt`, `NN-cli.txt`, `NN-install-<profile>.txt`, `NN-merge.txt`, `NN-session.txt` with `NN-session-stream.jsonl` and `NN-session-state/fired.jsonl`. `state.json` has the fixture paths and the guard hashes. `guard.txt` has the guard result.
- `$H evidence` lists the folder of the current run (after cleanup: the newest run) and says whether `run.log` is proof. It reads `run.log` with the hooks' parser (`hooklib.verify_runs`): `commit`, `doctor: PASS`, `db_writes: no`, `finished`.
- Proof standard: drive the real entry point (a hook payload or a real session, the real CLI, the real installer). Show the action and the end state: the decision and the remote refs for a gate, `git status` and the fixture files for a CLI, the planned lines and the untouched real files for the installer.

## Cleanup

```
$H cleanup
```

It stops the processes whose command line names the run's temp folder (OMC session-end workers, the graphify rebuild), removes the temp folder, compares the guards, and finishes `run.log`. Exit 1 when a guarded real file changed. The evidence folder stays. Confirm with `ls <evidence folder>`.

## Stand-in limits

- A Claude session uses the real `~/.claude` for the login (a temp `CLAUDE_CONFIG_DIR` is "Not logged in"). Claude writes its session transcript under `~/.claude/projects/`. The guards prove that settings and plugins stay the same.
- The other installed plugins (OMC, Ponytail, i-have-adhd, ai-serena from `~/.dotfiles-ai`) load in a Claude session, as on the owner's Mac. A Codex session loads only this checkout's hooks and no global AGENTS.md.
- The installer runs as `--user --dry-run` on this Mac. A real install, the system mode and the other 2 machines stay unverified.

## Maintenance

A PR that adds or changes a gate, a stop rule, a CLI or an installer step updates its feature file in the same PR. Run `maintain-verification-skill` when a recipe no longer matches.
