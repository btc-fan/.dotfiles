---
name: promote-skill
description: 'Use when the owner found a good way of doing something in one project and wants it in every project ("make this generic", "add this to our setup", "promote this skill", "fa-l general"). Generalizes a project skill or a session approach into a shared skill in the dotfiles AI setup and opens a PR for the owner. Not for writing a project-only skill.'
---

# Promote a skill into the AI setup

The shared skills live in the dotfiles repo (`~/work/dotfiles-ai`, branch `ai`), folder `ai/skills/<name>/`.
install.sh links every folder there into Claude (`~/.claude/skills`) and Codex (`~/.agents/skills`) on all
machines.

## Steps

1. **Source.** A project skill (`.claude/skills/<name>/` or `.agents/skills/<name>/`), or the approach from this
   session. For a session approach, write the steps down first (what triggered it, the commands, what proved it
   worked).
2. **Generalize.** Remove project names, paths, hosts, accounts, data and secrets. Replace them with
   placeholders (`<app>`, `<repo>`). Keep the commands and the checks. Follow the writing-for-agents skill:
   one job per skill, a description that says when to use it and when not, short steps.
3. **Scope.** Ask the owner once: global (every session sees it, costs context in every session), opt-in per
   project (`ai-adopt --skills`), or on by default in new projects. Default answer: opt-in.
4. **Branch.** In `~/work/dotfiles-ai`: `git switch -c skill-<name>`, write `ai/skills/<name>/SKILL.md`, add a row
   to `ai/skills/skills-guide/SKILL.md` and to `docs/GUIDE.md` section 4.
5. **Test.** `bash ai/tests/run.sh` green. Read the new skill once as a tired reader: each step survives one read.
6. **PR.** Push and open a PR with the full body. The owner approves; after the merge, `ai-sync` on each machine
   installs it.
