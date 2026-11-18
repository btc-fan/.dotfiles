# Git hooks as the seam for the git rules

Date: 2026-11-18
Sources: primary only. Git documentation, husky, lefthook and pre-commit documentation and source, Claude Code documentation, OpenAI Codex documentation. Each claim has its URL. Local tests ran on git 2.50.1 (macOS) in throwaway repos.
Status: current

Question: can one global git hook folder (`core.hooksPath`) enforce one owner's git rules for each agent and each repo, and still run the hooks that a repo already has?

## Short answer

No, not with a global `core.hooksPath` alone. Three facts stop it:

1. A repo-local `core.hooksPath` wins over the global value. husky sets one. In such a repo the global folder is silently off.
2. With a global `core.hooksPath`, git ignores `.git/hooks`. The pre-commit tool and lefthook also refuse to install.
3. Each client-side hook can be skipped with one flag, one `-c` option or one environment variable.

Git 2.54 and later has a better seam: hooks defined in the global config (`hook.<name>.event`, `hook.<name>.command`). Git runs them first and runs the hook from the hook folder last. This leaves the repo's own hooks in place. The local git is 2.50.1, so this was not tested.

## Table: rule by rule

"All git users" means each process that runs git with the owner's global config: the owner's shell, Claude, Codex, subagents, scripts, GUI tools. The column "How it can be skipped" always includes the general skips in the section "Fact 4".

| Rule | Hook point | Holds for whom | How it can be skipped |
|---|---|---|---|
| No commit on a protected branch | `pre-commit` (read the branch with `git symbolic-ref --short HEAD`). Add `pre-merge-commit` for merge commits. | All git users, for `git commit` and `git merge` with a merge commit. | `git commit --no-verify`. Also not triggered at all by a fast-forward merge, `git cherry-pick`, or `git commit-tree` with `git update-ref` (tested locally). |
| No push to a protected branch | `pre-push`. The hook reads the remote ref from standard input, not the current branch. | All git users. | `git push --no-verify`. Then only a server-side branch rule holds. |
| No secret in the staged diff | `pre-commit` (scan `git diff --cached`). | All git users, for `git commit`. | `git commit --no-verify`. A cherry-pick and a fast-forward merge do not run `pre-commit`. The push-range scan is the second net. |
| No secret in the pushed range | `pre-push`. Standard input gives the local and the remote object name for each ref. | All git users. | `git push --no-verify`. Then only a server-side scan holds. |
| No `git add -A` or `git add .` | None. Git has no hook for `git add`. | Nobody through git. An agent hook on the command text holds for that agent only. | Not applicable. A `pre-commit` check of the staged file list can replace the rule: it checks the result, not the command. |
| Commit message rules | `commit-msg` (parameter 1 is the message file). | All git users, for `git commit` and `git merge`. | `git commit --no-verify`. A cherry-pick did not run `commit-msg` (tested locally). |
| No `--no-verify` | None. Git does not report the flag to a hook. | Only the agents that have an agent hook on the command text. | The owner's shell and each agent without that hook can use the flag. |

Sources for the hook points: <https://git-scm.com/docs/githooks> (`pre-commit`, `pre-merge-commit`, `commit-msg`, `pre-push`, and the full list of 28 hooks, which has no hook for `git add`).

Local tests for the table (each in a new `mktemp -d` folder, with `GIT_CONFIG_GLOBAL=<temp file>` and `git config --global core.hooksPath <temp folder>`):

- Tested locally: `git commit -m x` on `main` with a `pre-commit` hook that exits 1 on `main`: exit 1. `git commit --no-verify -m x`: exit 0.
- Tested locally: `git merge --ff-only work` on `main` ran `post-merge` and `reference-transaction` only. `git merge side` (merge commit) ran `pre-merge-commit`, `prepare-commit-msg`, `commit-msg`, `post-merge`. `git cherry-pick side` ran `prepare-commit-msg` and `post-commit` only. `git commit-tree` plus `git update-ref refs/heads/main` ran `reference-transaction` only.
- Tested locally: `git push origin work:main` gave the hook the line `refs/heads/work -> refs/heads/main`. The hook exited 1 and the push failed. `git push --no-verify origin work:main`: exit 0.
- Tested locally: `git add -A` ran `post-index-change` only. The hook got the parameters `0 0`. With `exit 1` in the hook, `git add -A` still returned 0 and the files were staged.
- Tested locally: `git commit -a -m x` staged two changed files without `git add`. The `pre-commit` hook saw them in `git diff --cached --name-only`.

## Fact 1: global `core.hooksPath` and the repo's own hooks

- Default hook folder: `$GIT_DIR/hooks`. `core.hooksPath` replaces it. Git reads one hook folder, not two. <https://git-scm.com/docs/githooks>, <https://git-scm.com/docs/git-config>
- Git reads the config files in the order system, global, repo, worktree. The last value wins. A repo-local `core.hooksPath` wins over the global value. <https://git-scm.com/docs/git-config> (section FILES)
- Tested locally: global `core.hooksPath` plus `.git/hooks/pre-commit` in the repo: only the global hook ran. `git rev-parse --git-path hooks` printed the global folder.
- Tested locally: global `core.hooksPath` plus `git config core.hooksPath .husky/_` in the repo: only the repo hook ran. No global hook ran, not even `reference-transaction`.
- husky sets the repo-local value: its installer runs `git config core.hooksPath .husky/_`. <https://github.com/typicode/husky/blob/main/index.js>, <https://typicode.github.io/husky/>
- The pre-commit tool writes its script to `.git/hooks`. It stops when `core.hooksPath` is set: "Cowardly refusing to install hooks with `core.hooksPath` set." <https://github.com/pre-commit/pre-commit/blob/main/pre_commit/commands/install_uninstall.py>. Tested locally with pre-commit 4.7.0: `pre-commit install` with a global `core.hooksPath` printed that message and returned 1.
- lefthook stops in the same way. A plain `lefthook install` stops when `core.hooksPath` is set, locally or globally. `--force` or `--reset-hooks-path` resolves it. <https://lefthook.dev/usage/commands/install/>, <https://github.com/evilmartians/lefthook/blob/master/internal/command/install.go>
- A global hook can call the repo's hook. Tested locally: a global `pre-commit` that ends with `exec "$(git rev-parse --git-common-dir)/hooks/pre-commit" "$@"` ran the global check and then the repo hook, also in a linked worktree. This chain covers `.git/hooks` only. It does not help in a repo with a local `core.hooksPath`, because git does not start the global hook there.
- Git 2.54 added hooks in the config: "Hook commands are now allowed to be defined (possibly centrally) in the configuration files, and run multiple of them for the same hook event." <https://github.com/git/git/blob/master/Documentation/RelNotes/2.54.0.adoc>
- Order with config hooks: git runs the configured hooks in the order of the config parse. "The default `<hook-name>` from the hookdir is run last." <https://git-scm.com/docs/git-hook>
- The pre-commit documentation shows this as its "global" installation for git 2.54 and later, with `hook.<name>.event` and `hook.<name>.command` in the global config. It says the setup is not recommended for its own tool, because hooks can run in an untrusted repo. <https://pre-commit.com/> (section "usage with git 2.54+ hook configuration")

## Fact 2: linked worktrees

- A linked worktree has its own `$GIT_DIR` (`.git/worktrees/<id>`). `$GIT_COMMON_DIR` points to the main `.git`. <https://git-scm.com/docs/git-worktree> (section DETAILS)
- The `hooks` folder is shared: "This directory is ignored if `$GIT_COMMON_DIR` is set and `$GIT_COMMON_DIR/hooks` will be used instead." <https://git-scm.com/docs/gitrepository-layout>
- The repo config file is shared by all worktrees, unless `extensions.worktreeConfig` is on. <https://git-scm.com/docs/git-worktree> (section CONFIGURATION FILE)
- Tested locally: in a linked worktree, `git rev-parse --git-path hooks` printed the main repo's `.git/hooks` without a global value, and the global folder with a global `core.hooksPath`. A commit in the worktree ran the global hooks.
- A relative `core.hooksPath` is relative to the folder where the hook runs, which is the root of that working tree. <https://git-scm.com/docs/git-config>, <https://git-scm.com/docs/githooks>
- Tested locally: a repo with `core.hooksPath .husky/_` and an untracked `.husky/_` folder (husky writes a `.gitignore` with `*` into it). In a new linked worktree the folder was missing and a commit ran no hook at all. No error was shown.

## Fact 3: which hooks exist for the rules

See the table. More detail:

- `pre-push` gets `<local-ref> SP <local-object-name> SP <remote-ref> SP <remote-object-name>` for each ref. A new remote branch has the all-zero remote object name. This gives the pushed range for a secret scan. <https://git-scm.com/docs/githooks>
- `prepare-commit-msg` "is not suppressed by the `--no-verify` option", and a non-zero exit aborts the commit. The same page says it "should not be used as a replacement for the pre-commit hook". <https://git-scm.com/docs/githooks>. Tested locally: a `prepare-commit-msg` hook that exits 1 on `main` stopped `git commit --no-verify` (exit 1).
- `reference-transaction` runs for each ref update. A non-zero exit in the "prepared" state aborts the update. <https://git-scm.com/docs/githooks>. Tested locally: a hook that exits 1 for `refs/heads/main` stopped `git commit --no-verify` and `git update-ref` (exit 128, "ref updates aborted by hook"). It also stopped a fast-forward merge into `main`, which is what a normal pull does. The stopped merge left a staged file behind.
- `post-index-change` runs after an index write. It gets two flags only. It cannot block and it does not see the command. <https://git-scm.com/docs/githooks>

## Fact 4: what skips the hooks, and what holds then

General skips. Each one works for each actor, on each hook in the table:

- `git commit --no-verify` skips `pre-commit` and `commit-msg`. <https://git-scm.com/docs/git-commit>. `git merge --no-verify` skips `pre-merge-commit` and `commit-msg`. <https://git-scm.com/docs/git-merge>. `git push --no-verify` skips `pre-push`. <https://git-scm.com/docs/git-push>
- Tested locally: `git commit --no-verify` still ran `prepare-commit-msg`, `post-commit` and `reference-transaction`.
- `git -c core.hooksPath=/dev/null <command>` turns off all hooks for that command. The git documentation names this use. <https://git-scm.com/docs/git-config>. Tested locally: no hook ran.
- `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` do the same from the environment, without a flag in the command text. <https://git-scm.com/docs/git-config>. Tested locally: `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null git commit -m x` ran no hook.
- `git config core.hooksPath <other>` in the repo does the same for all later commands. Tested locally.
- On git 2.54 and later: `hook.<name>.enabled=false` turns off one configured hook, also from the repo config. `hook.<event>.enabled=false` turns off all hooks for the event, the hook folder included. <https://github.com/git/git/blob/master/Documentation/config/hook.adoc>
- Tool switches: `HUSKY=0` (<https://typicode.github.io/husky/how-to.html>), `LEFTHOOK=0` (<https://lefthook.dev/usage/envs/LEFTHOOK/>), `SKIP=<hook id>` for the pre-commit tool (<https://pre-commit.com/>).

What still holds then:

- A server-side rule. The `pre-receive` and `update` hooks run in the remote repo, and their exit status decides the ref update. A client flag cannot skip them. <https://git-scm.com/docs/githooks>. A branch protection rule on the hosting service has the same position. It was not researched here.
- The existing no-verify gate. It is an agent hook on the command text. Claude Code runs `PreToolUse` hooks before a tool call, also for subagents, and exit code 2 blocks the call. <https://code.claude.com/docs/en/hooks>. It holds for agents with that hook only, not for the owner's shell. A gate that reads the command text can miss a config override that comes from the environment (`GIT_CONFIG_COUNT`). This was not tested.
- The Claude Code documentation calls the hook `if` filter best-effort and says to use the permission system for a hard allow or deny. <https://code.claude.com/docs/en/hooks>

## Fact 5: hooks inside the agent sandboxes

Hook environment in general:

- Git sets the working directory of a hook to the root of the working tree and exports variables such as `GIT_DIR`. <https://git-scm.com/docs/githooks>
- Tested locally: the hook `PATH` was the caller's `PATH` with the `git --exec-path` folder in front. With `PATH=/usr/bin:/bin git commit`, the hook saw only those folders plus the exec path. So a hook has the `PATH` of the process that started git, not the `PATH` of the owner's interactive shell.
- husky documents the same problem for GUI clients and sources `~/.config/husky/init.sh` before each hook to repair `PATH`. <https://typicode.github.io/husky/how-to.html>

Claude Code (<https://code.claude.com/docs/en/sandboxing>):

- The sandbox is off by default. When it is on, it covers the shell commands and "the processes they start". A git hook is such a process, so it runs inside the sandbox.
- Environment variables are inherited from Claude Code. The page does not describe a change of `PATH`.
- Writes: the working directory, added directories and `$TMPDIR`. Network: only allowed domains, through a proxy. A hook that writes a cache in the home folder, or that downloads data, fails inside the sandbox.
- `hooks` and `config` inside `.git` are write-protected in the working directory. In a linked worktree the shared `.git` is writable, but `hooks/` and `config` in it stay denied. So a sandboxed command cannot edit the repo hooks or set a repo-local `core.hooksPath`. It follows that `husky`, `pre-commit install` and `lefthook install` cannot install from a sandboxed command. This was not tested.
- A global hook folder outside the working directory is readable (default read access to the whole computer) and not writable from a sandboxed command.
- Outside the sandbox: Claude's file tools, agent hooks, commands that match `excludedCommands`, and unsandboxed retries. The sandbox does not stop `git -c core.hooksPath=/dev/null`, because that is not a file write.
- Subagents use the same sandbox configuration as the parent session.

Codex (<https://developers.openai.com/codex/sandboxing>, which redirected to <https://learn.chatgpt.com/docs/sandboxing> on 2026-11-18):

- "The sandbox applies to spawned commands, not just to built-in file operations." Tools such as `git` "inherit the same sandbox boundaries". A git hook is a child of git, so it runs inside the sandbox.
- In `workspace-write` mode, `<writable_root>/.git` is read-only, also when `.git` is a pointer file of a worktree. <https://learn.chatgpt.com/docs/agent-approvals-security>
- "This is why commands like `git commit` may still require approval to run outside the sandbox." <https://learn.chatgpt.com/docs/config-file/config-advanced>. So a commit, and its hooks, usually run outside the Codex sandbox after an approval.
- Network access is off by default in `workspace-write`. <https://learn.chatgpt.com/docs/agent-approvals-security>
- `shell_environment_policy` controls the environment of spawned commands (`inherit`, `set`, filters). <https://learn.chatgpt.com/docs/config-file/config-reference>. The pages read do not state the default for `PATH`.

## Fact 6: what the known tools do

The pre-commit tool (<https://pre-commit.com/>, source links above):

1. `pre-commit install` writes one script per hook type to the hooks folder of the common git dir. The script starts `pre-commit hook-impl`.
2. It needs a `.pre-commit-config.yaml` in each repo. There is no global config file.
3. An existing hook is moved to `<hook>.legacy` and runs first ("migration mode"). Tested locally with 4.7.0.
4. `pre-commit init-templatedir <dir>` plus `git config --global init.templateDir <dir>` copies the hook into each new clone or new repo. It does not change existing repos. Repos without a config are skipped. Tested locally: `git init` with that template folder created `.git/hooks/pre-commit`.
5. It refuses to install when `core.hooksPath` is set. For git 2.54 and later it documents a global setup with config hooks and warns about untrusted repos.

husky (<https://typicode.github.io/husky/>, <https://github.com/typicode/husky/blob/main/index.js>, <https://github.com/typicode/husky/blob/main/husky>):

1. `husky` sets the repo-local `core.hooksPath` to `.husky/_` and writes 14 small hook files there.
2. Each file starts a helper that runs `.husky/<hook>` with `sh -e` and puts `node_modules/.bin` on `PATH`.
3. The install runs from the `prepare` script of npm. `.husky/_` is ignored by git, so each clone and each working tree needs its own install.
4. `HUSKY=0` skips the install and each hook. `~/.config/husky/init.sh` is sourced before each hook.
5. Result for this question: the repo-local value wins, so a global `core.hooksPath` is off in each husky repo.

lefthook (<https://lefthook.dev/usage/commands/install/>, <https://lefthook.dev/usage/envs/LEFTHOOK_CONFIG/>, <https://lefthook.dev/examples/lefthook-local/>):

1. `lefthook install` writes hook files into the git hooks folder. They read `lefthook.yml` on each run.
2. It stops when `core.hooksPath` is set, locally or globally. The source comment says: "In general using lefthook doesn't make sense with global hooks."
3. It has no global config file. The nearest option is `LEFTHOOK_CONFIG=~/global_lefthook.yml`, which replaces the main config for that process. Local config, `extends` and `remotes` still load.
4. `lefthook-local.yml` holds personal overrides for one repo. `remotes` shares one config between repos.
5. `LEFTHOOK=0` skips the hooks. The documentation has an example that blocks a push from `main` in `pre-push`, with an environment variable as the override. <https://lefthook.dev/examples/protect-branch/>

## Recommendation

Git hooks for some rules, not for all. Do not stay with agent hooks only.

1. Move the commit and push rules to git hooks: protected branch at commit and at push, secret scan of the staged diff and of the pushed range, commit message rules. These hooks hold for the owner's shell, Claude, Codex, subagents and scripts with one implementation. They need no parser of command text.
2. Do not use a global `core.hooksPath` as the seam. It is silently off in each husky repo. It hides `.git/hooks`. It makes `pre-commit install` and `lefthook install` fail. Use the config hooks of git 2.54 and later in the global config: git runs them first and then runs the repo's own hook folder. This needs a git upgrade from 2.50.1 and a test first.
3. Keep agent hooks for what git cannot see: `--no-verify`, a `core.hooksPath` or `hook.*.enabled` override in the command, and `git add -A` (or replace that rule with a check of the staged file list in `pre-commit`). Keep the PR and merge gates as agent hooks. They are not git events.
4. Treat each client-side hook as a net, not as a wall. One flag skips it for each actor. Only a server-side branch rule holds against a skip.

Until the git upgrade: a global `core.hooksPath` with a chain to `$(git rev-parse --git-common-dir)/hooks/<hook>` works for repos with plain `.git/hooks`. It needs a check at session start that reports a repo with a local `core.hooksPath`, because the global hooks are off there.

Design notes that follow from the tests:

- Check the protected branch in `pre-push` from the remote ref on standard input. The current branch is the wrong input.
- A `pre-commit` check alone does not stop a cherry-pick or a fast-forward merge onto `main`. The `pre-push` check is the one that covers them.
- Give each hook its own `PATH` or absolute tool paths. The hook gets the `PATH` of the caller.
- A hook must work with writes limited to the working directory and `$TMPDIR`, and with no network. Then it also works inside the Claude Code sandbox.
- `reference-transaction` is the only client-side point that also stops `--no-verify` and plumbing commands. It also stops a normal pull on `main`. Do not use it for the protected-branch rule without a design for that case.

## Not verified

- Config hooks of git 2.54 and later were not run. The local git is 2.50.1. Open points: a configured hook that fails stops the commit and the later hooks; `--no-verify` skips configured hooks; configured global hooks run together with a husky repo-local `core.hooksPath`; `git -c core.hooksPath=/dev/null` leaves configured hooks on.
- No hook was run inside a real Claude Code sandbox or a real Codex sandbox. The statements in "Fact 5" come from the documentation. The same `PATH` inside both sandboxes is not proven.
- The Codex default for `shell_environment_policy.inherit`, and whether it keeps `PATH`, was not found on the pages read.
- The Codex pages were read at the redirect target `learn.chatgpt.com`. The redirect came from `developers.openai.com`.
- husky and lefthook were not installed. Their behaviour comes from their documentation and source. The husky worktree test used a hand-made `.husky/_` layout.
- `git rebase`, `git commit --amend`, `git revert` and `git am` were not tested against the hooks.
- `git pull` on `main` with a blocking `reference-transaction` hook was not tested directly. The fast-forward merge was tested.
- Server-side rules on a hosting service were not researched (out of scope).
- Windows was not checked.
