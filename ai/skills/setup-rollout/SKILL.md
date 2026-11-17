---
name: setup-rollout
description: 'Use when the owner wants the AI setup installed or updated on a machine, a project folder adopted or re-adopted ("apply the dotfiles ai setup to folder X", "adopt this repo", "update the AI setup on the server"), or a merged change rolled out to every machine. Runbook with a check after each step. Not for changing the setup itself (use promote-skill).'
---

# Roll out the AI setup

The setup source is the branch `ai` of the dotfiles repo. The owner may say "main" or "master" of the setup.
They mean `ai`. The installed copy is `~/.dotfiles-ai`. Run every real install from that copy. A dev checkout
or a worktree can run `--dry-run` only: a real install from it points every link at that folder.

Two levels. Machine level is the user part: `~/.dotfiles-ai`, `~/.config/ai`, `~/.local/bin`, `~/.claude`,
`~/.codex`. It covers every project of that user. Project level is `ai-adopt` in one repo.

Pitfalls, each one seen on a real machine: `PITFALLS.md` (same folder). Read it before step 2 on a new
machine or when a step fails. Real examples: `EXAMPLES.md` (same folder).

Updates are add-only. Owner text is everything outside the managed `<!-- AI:... -->` blocks (project rules,
Done, Lessons) and every line the owner added inside a block. An update adds or refreshes setup lines. It never
rewrites or removes owner text. The `<!-- AI:... -->` blocks belong to the setup only. Write a project rule outside them, under
`## Project rules` or in the project own sections. Never move or "clean up" project rules.
`ai-doctor` may warn "custom line inside an AI block". Move that line under `## Project rules` only with the
owner's OK.

Work from files. Write a script on the main machine, then run it on the target. Never paste multi-line commands.

## 1. Choose the path

- `~/.dotfiles-ai` missing: fresh install. Follow `docs/INSTALL.md`: clone branch `ai` to `~/.dotfiles-ai`, then run
  `~/.dotfiles-ai/install.sh` (macOS, or a Linux user with sudo) or `install.sh --user`. Then go to step 3.
- `~/.dotfiles-ai` exists: update. Go to step 2.
- Task names a project folder only: go to step 4.

Done when: you can say "fresh" or "update", and the target is a machine or a folder.

## 2. Update a machine

1. Get the change. A clone on branch `ai`: `git -C ~/.dotfiles-ai pull --ff-only`. A detached copy:
   `git -C ~/.dotfiles-ai fetch` then `git -C ~/.dotfiles-ai checkout --detach origin/ai`, then run
   `~/.dotfiles-ai/ai/bin/ai-sync` yourself (a checkout runs no post-merge hook).
2. `ai-sync` (the hook runs it after a pull) renders the rules and routing and refreshes the Codex block.
   It takes about 10 s. Claude reads the plugin from the folder: router changes are live at the next session start.
3. Run `install.sh` again only when the change touched the installer (new hooks, binaries, switches, tool
   versions) or `ai-doctor` says so. First `~/.dotfiles-ai/install.sh --dry-run --yes`. Show the plan to the owner.
   Then `~/.dotfiles-ai/install.sh --yes`. Check line 2 of the output: `Agents:` must list claude and codex.
   If not, read `PITFALLS.md` (agent detection).

Done when: `git -C ~/.dotfiles-ai log --oneline -1` shows the commit that was merged to `ai`.

## 3. Verify the machine

1. `~/.dotfiles-ai/ai/bin/ai-doctor --quick | tail -1` ends with 0 fail.
2. `grep -c "^Standing permission" ~/.config/ai/AGENTS.md` prints 1. This proves the rendered owner rules are live.
   For a newer rule, grep a line that only the new rule has.
3. Tell the owner: restart every running Claude and Codex session.

Done when: both outputs are shown in your report, with the commit hash.

## 4. Adopt a project folder

1. Read the project `AGENTS.md` and `CLAUDE.md`. List the owner items that must survive: owner rule sections,
   own skills (real folders in `.claude/skills`), hooks in `.claude/settings.json`, `.claude/CLAUDE.md`, Makefile edits.
2. `git status --short --branch` is clean, on the default branch, and pulled. No git: `ai-adopt` refuses.
   `--init` runs `git init` (never in `$HOME` or `/`).
3. `~/.dotfiles-ai/ai/bin/ai-adopt --dir X --dry-run`. Read every "would write" line.
   "nothing to change (base vN)" means the project is current: stop.
4. `~/.dotfiles-ai/ai/bin/ai-adopt --dir X --yes`. When it exits non-zero with "owner text would change: nothing
   written", it is the add-only guard. Stop. Show the owner the printed diff. The owner decides. On main or master it commits on branch `ai-adopt` and
   prints "merge the ai-adopt branch". No remote: it warns that push and PR are not possible.
5. Prove the owner items survived (next step). Then `git status --short` must be empty: `ai-adopt` commits
   every file it writes.

Done when: the dry run was read, the real run exited 0 (or you showed the guard diff to the owner), and the git tree is clean.

## 5. Check the owner items

1. `git diff <base>..ai-adopt --name-only -- .claude/skills .claude/hooks .claude/CLAUDE.md .claude/settings.json`
   lists only the linked skills.
2. Diff the text of each owner section of `AGENTS.md`: byte-identical.
3. The owner Makefile flags are still in the file.
4. `make check-fast`. A red result belongs to the project: report the failing tests. Do not edit project code
   in a setup task.
5. A project rule can conflict with the Stop hook (example: "run the full suite only before a merge").
   Then, with the owner's OK, add `no-stop-check  # <owner rule>` to `.ai/enabled` in the same branch.

Done when: steps 1 to 3 show no loss and the `make check-fast` result is in your report.

## 6. Hand over

1. Push the branch. Open a PR with the `pr` skill template. Evidence: the diff stat and the step 5 result.
2. The owner merges. After the merge: pull the default branch, delete the merged local branch.
3. Verify a session in the project. Ask in a fresh session: "Quote the SessionStart context: the skill card and
   the main: line." Expect the 4 must-use skills (writing-for-agents, diagnosing-bugs, ship, tdd), the typed-only
   paths and the session id. `/memory` lists `~/.claude/CLAUDE.md` and the project `AGENTS.md`. `/hooks` lists
   the ai-core router on SessionStart, UserPromptSubmit, PreToolUse, PostToolUse and Stop.

Done when: the owner confirms the PR is merged and the session quote matches.

## Roll out to every machine

After a merge to `ai`, do steps 2 and 3 on each machine, one machine at a time. Report one line per machine:
name, commit, `ai-doctor` result.
