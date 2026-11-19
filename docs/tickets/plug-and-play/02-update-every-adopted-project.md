# 02: One command updates every adopted project

**What to build:** `ai-adopt` records each project it adopts in a list under `~/.local/state/ai/`. `ai-update --projects` then re-runs `ai-adopt` in each listed project. A project with nothing to change prints "current". A project with changes gets them on the `ai-adopt` branch, with a push and a PR, as a single adopt does today. The owner merges each PR. No project file is ever edited by hand.

**Blocked by:** 01

**Status:** ready-for-agent

The goal (owner 2026-11-19): the setup does not care which project it is in. In a new project the owner runs 2 commands (`ai-adopt --dir . --yes`, then merge its PR). After a change to the setup, `ai-update --projects` carries it to every project.

- [ ] The list holds the path of every project adopted on this machine; a folder that is gone is dropped with one line.
- [ ] A project not on its default branch, or with uncommitted changes on it, is skipped with the reason; the others go on.
- [ ] The run ends with one line per project: current, PR link, or skipped (reason).
- [ ] Tested on fixture repos in a temp folder (no real project).
