# pstack skills: repo copy only

Commit: ace4e93. Fixture: dotfiles-worktrees. doctor: PASS.

## Setup

The fixture HOME `home-sync` got the state of ubuntu01 on 2026-11-25: an old automatic download in `.local/share/ai/plugins/pstack-verification` (`.commit` 41e4009...), and the 4 skill links in `.claude/skills` and `.agents/skills` pointed at it.

## Drives

1. `drive merge installed` (01-merge.txt): a real `git merge` in the installed copy. The post-merge hook runs `ai-sync`. Result: `rc: 0`, `HOME changed: yes`. The 4 links now point to `home-sync/.dotfiles-ai/ai/skills/<skill>`, the repo copy.
2. `drive install dev-mac` and `drive install server` (02, 03): `install.sh --dry-run --user`. `real files changed: none`. The plan table lists `pstack 41e400932eca new` (resolver status, the same column for every tool). The `--user` dry run does not reach the plugin step, so the `pstack_check` warning is proven by `ai/tests/test_resolve.py::t_bash_pstack`.

## Cleanup

`real files changed: none`.
