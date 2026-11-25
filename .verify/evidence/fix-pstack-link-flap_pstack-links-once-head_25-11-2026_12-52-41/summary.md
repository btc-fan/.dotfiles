# pstack skill links are set once (R-022)

Commit: bf74393 (code head after the review fixes). Fixture: dotfiles-worktrees. doctor: PASS.

## Setup

The fixture HOME `home-sync` got a newer pstack copy in `.local/share/ai/plugins/pstack-verification` (`.commit` is not the vendored commit). This is the state of ubuntu01 on 2026-11-25.

## Drive

`drive merge installed`: a real `git merge` in the installed copy. The post-merge hook runs `ai-sync`.

## Result (01-merge.txt)

- `rc: 0`, `HOME changed: yes`.
- Each of `create-verification-skill` and `maintain-verification-skill` gets one `link` line in `.claude/skills` and one in `.agents/skills`.
- 0 lines with "was a link": no switch to the repo copy and back.
- End state: the 4 links point to `home-sync/.local/share/ai/plugins/pstack-verification/<skill>`.

Before the fix, one `ai-update` on ubuntu01 printed 3 link changes for each skill (repo copy, then pstack copy).

## Cleanup

`real files changed: none`.

