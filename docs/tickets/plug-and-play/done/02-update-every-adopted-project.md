# 02: One command updates every adopted project

**What to build:** `ai-adopt` records each project it adopts in a list under `~/.local/state/ai/`. `ai-update --projects` then re-runs `ai-adopt` in each listed project. A project with nothing to change prints "current". A project with changes gets them on the `ai-adopt` branch, with a push and a PR, as a single adopt does today. The owner merges each PR. No project file is ever edited by hand.

**Blocked by:** 01

**Status:** done (2026-11-19)

The goal (owner 2026-11-19): the setup does not care which project it is in. In a new project the owner runs 2 commands (`ai-adopt --dir . --yes`, then merge its PR). After a change to the setup, `ai-update --projects` carries it to every project.

- [x] The list holds the path of every project adopted on this machine; a folder that is gone is dropped with one line.
- [x] A project not on its default branch, or with uncommitted changes on it, is skipped with the reason; the others go on.
- [x] The run ends with one line per project: current, PR link, or skipped (reason).
- [x] Tested on fixture repos in a temp folder (no real project).
