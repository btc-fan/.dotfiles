---
name: upgrade-review
description: 'Use when the session start says tools were upgraded (upgrade-review rule), or the owner asks what changed in Claude Code, Codex, graphify, Serena, the Matt Pocock skills, OMC, ui-ux-pro-max, claude-seo or claude-blog. Reads the release notes between the old and new version and proposes how the AI setup should use the new features, as a dotfiles PR for the owner. Not for installing or upgrading (install.sh and ai-sync do that).'
---

# Upgrade review: what is new, and what we should use

Input: `~/.local/state/ai/upgrades.json` (written by install.sh after a version change):
`{"pending": [{"tool": "graphify", "old": "0.9.111", "new": "0.9.120", "ts": "..."}]}`.

## Steps

1. **Read the notes.** For each pending tool, read the release notes or the changelog from `old` to `new`.
   Primary sources only: the GitHub releases (`gh release list -R <owner/repo>`, `gh release view`), the
   CHANGELOG file, the official docs (context7 first). Quote the version for each claim.
2. **Sort each change** into one of: breaks our setup (a flag, a file path, a hook format we use), a new feature
   worth using, or not relevant.
3. **Check our use.** For each "breaks" or "worth using" item, find where the setup touches it
   (`rg -n <flag or path> ~/work/dotfiles-ai/ai`) and run the smallest test that proves it.
4. **Report.** Write the findings into the PR body: per tool, old -> new, "breaks", "use it" (what to change and
   where), "skip". No Markdown file outside the allowed places.
5. **Change.** On a branch `upgrade-<date>` in `~/work/dotfiles-ai`: fix what breaks, add what is worth using,
   update `docs/GUIDE.md` and the skills-guide. `bash ai/tests/run.sh` green. Open the PR; the owner approves.
6. **Clear.** Remove the reviewed tools from `pending` in `upgrades.json` (keep the file).
