# Standardized AGENTS.md

What "standardized" means here, how every agent gets the same rules, and how to change a rule.

## 1. What AGENTS.md is

`AGENTS.md` is a plain text file of instructions for a coding agent. The agent reads it at the start of a session. It is the agent's house rules: how to reply, which tools to use, what never to do.

The problem: every agent wants its rules in a different place and a different way.
- Claude Code reads `CLAUDE.md` (and supports `@import` lines).
- Codex reads `AGENTS.md`.
- Hermes reads `SOUL.md`.
- opencode reads `AGENTS.md` and an `instructions` list.

Without a standard, you keep four copies, and they drift apart. Standardized means: **one source, one built file, and each agent receives it in the way it supports.**

## 2. The one source

```
ai/agents-md/            the parts (you edit these)
  00-owner.md              owner text, copied byte for byte, never reworded
  10-output-shape.md       reply shape (i-have-adhd)
  20-rtk.md                RTK in four lines
  30-code-navigation.md    repo AGENTS.md Map first, narrow search, context7 docs, gh
  40-audit-before-use.md   agent-audit and the gates
  45-no-root.md            never sudo; give the owner the command
  50-pull-requests.md      PR rules and the author-sessions block
  60-characters.md         no em dash
  70-prompting-others.md   how to brief another agent (one line)
  80-tool-catalog.md       non-interactive commands of the other agents (one line)
  85-l0.md                 one line: where the L0 table goes
  90-toolbox-and-vendor-rules.md   opt-in tools, OMC, Ponytail, toolbox pointer
ai/routing.yaml          the routing table (the L0 table is built from it)
        |
        v   ai-render
ai/AGENTS.md             the built root file (built on each machine, not committed; target under 12 KB, hard cap 30 KB)
```

`ai-render` does three things:
1. Joins the parts in file-name order. The number prefix sets the order. Owner text first.
2. Builds the L0 table (one row per routing rule) from `ai/routing.yaml` and puts it where `<!-- AI:L0 -->` is.
3. Fails if the result is over **30 KB** or contains an em dash (U+2014).

Why small: the root file is loaded into every session. A big file costs tokens on every prompt and hides the important lines (research on context files: keep them short, only non-standard facts). Owner target since 2026-11-12: well under 12 KB (about 10 KB today); the 30 KB cap in `ai-render` is only the hard stop. The root file holds only non-standard house rules: where projects live, boxes, no sudo, gates, the PR flow, docs lookup. No tool marketing, no repo overviews. Long text belongs in `ai/rules/<tool>.md`.

### What each part is for

| Part | Why it exists | Example line |
|---|---|---|
| 00 owner | your own style rules, never changed by us | "Lead with the answer. Hard limit: 60 words unless I ask for detail." |
| 10 output shape | makes i-have-adhd work in agents that have no hook | "Follow i-have-adhd in every reply. It is always on." |
| 20 RTK | the command proxy, in four lines | "Full output (security tools, debugging): rtk bypass <cmd>." |
| 30 code navigation | read the repo Map first, search narrowly, docs before code | "In a repo, read the Map and Libraries sections of its AGENTS.md first." |
| 40 audit | the audit rule and gate summary | "A finding means stop. Show it to me. Do not install." |
| 45 no root | agents never escalate; the owner runs root commands | "When something needs root, stop and give me the exact command to run." |
| 50 pull requests | PR shape and the author-sessions block | "Mermaid diagram of the change, one-way or two-way door?, blast radius." |
| 60 characters | one character rule | "Never the em dash." |
| 70 prompting others | the brief in one line | "Goal and what is ruled out, absolute file paths, one narrow task." |
| 80 other agents | the non-interactive commands | `opencode run "<task>" --format json` |
| 90 tools | opt-in tools, OMC, Ponytail, toolbox pointer | "Off in a project: suggest the command, never install it yourself." |

## 3. How each agent receives it

| Agent | How | Refreshed by |
|---|---|---|
| Claude Code | `~/.config/ai/AGENTS.md` is a link to the built file. `~/.claude/CLAUDE.md` has a managed block with one line: `@~/.config/ai/AGENTS.md` | `ai-render` alone (the link points to the built file; `ai-sync` runs it) |
| opencode | `~/.config/opencode/opencode.json` has `instructions` pointing to `~/.config/ai/AGENTS.md` | `ai-render` alone |
| Codex | `~/.codex/AGENTS.md` has a managed block `AI:core` with a **copy** of the root text (Codex cannot import) | `ai-sync` after `git pull` |
| Hermes | `SOUL.md` of the `hermes` user has a managed block `AI:core` with a **copy** of the root text plus the i-have-adhd rules | `ai-sync` after `git pull` (needs sudo for that user) |
| Project boxes (server) | `proj` copies the hosting rules into each box as `/etc/proj-rules/AGENTS.md` | `sudo proj sync-rules --all` (admin) |
| Servers, system copy | root-owned copies under `/etc` so an agent running as the user cannot change them | **coming** (not confirmed in the code of this branch yet) |

Two details:
- On a server, the hosting rules (from the `ubuntu-server` branch, `docs/AGENTS-hosting.md`) are added after the root rules. Claude gets an extra `@` line for that file. Codex and Hermes get the text appended to their copy. Those rules say where project code may live (in a box, never on the host) and which one root command agents may run.
- A copy can go stale. `ai-sync --check` exits 1 when a copy differs from the source. `ai-doctor` runs it.

### A real managed block

This is what the install writes into `~/.claude/CLAUDE.md` (the text around it is yours and stays):

```
# My own notes
Prefer tabs in Makefiles.

<!-- AI:core v1 START -->
@~/.config/ai/AGENTS.md
@~/.dotfiles/docs/AGENTS-hosting.md
<!-- AI:core v1 END -->

<!-- OMC:START -->
... oh-my-claudecode block, owned by OMC, never edited by us ...
<!-- OMC:END -->
```

Rules for managed blocks:
- The markers are `<!-- AI:<name> v<N> START -->` and `<!-- AI:<name> v<N> END -->`. `<name>` is `core` for the global block, or a tool id for a project block. `<N>` is the block version.
- The installer replaces a block **by marker**. Text outside the markers is never touched. Other tools' blocks (OMC, OMX, graphify) are never touched.
- Do not edit inside a block by hand. The next install or `ai-sync` overwrites it.
- Every block we write is recorded in `managed-keys.json`, so `uninstall.sh` removes exactly that block and leaves the rest.

## 4. What projects add

The global rules are the floor. A project adds its own text on top.

```
my-project/
  AGENTS.md      project rules (stack, commands, conventions)
  CLAUDE.md      one line: @AGENTS.md
  .ai/
    base-version   which routing version the project was set up with
    enabled        opt-in rule ids, one per line
  .serena/project.yml, graphify-out/   only when the project turned Serena or graphify on
```

- **Project knowledge lives in the project AGENTS.md** (owner decision 2026-11-12). Every agent reads it with no tool call, which beats on-demand tools. `ai-adopt` writes two managed sections between markers and never touches text outside them:
  - `## Map` between `<!-- AI:map START -->` and `<!-- AI:map END -->`: entry points, where things live, how to run and test, non-obvious conventions. At most 60 lines. Written from repo facts plus one read-only claude pass for the conventions; edit it freely inside the markers; `ai-adopt --refresh-map` writes it again.
  - `## Libraries` between `<!-- AI:libraries START lock: ... -->` and `<!-- AI:libraries END -->`: library, locked version, context7 ID. `ai-libs --sync` updates it; the START line holds the lockfile hashes for the stale check.
  - The routing rows `project-knowledge` (session start) and `knowledge-check` (after a commit) keep them used and fresh. Never secrets or personal data in them: they are pushed. Worked example: [README.md](../README.md), section 3, example D.

- **Project AGENTS.md.** Write what is true only for this project: how to run tests, folder layout, naming. Short, plain sentences.
- **One-line CLAUDE.md.** Claude Code skips `AGENTS.md` when a `CLAUDE.md` exists. So `CLAUDE.md` holds `@AGENTS.md` and nothing else. Both agents then read the same file.
- **Opt-in tool blocks.** `ai-start` (new project) and `ai-adopt` (existing repo) add one short managed block per enabled opt-in tool: the routing action plus a pointer to the contract. Example for a project that enabled ui-ux-pro-max:

```
<!-- AI:ui v4 START -->
UI work: use ui-ux-pro-max. Ask before paid image generation or any npx ...@latest. Details: ~/.config/ai/rules/ui-ux-pro-max.md
<!-- AI:ui v4 END -->
```

- **Never the same rule twice.** If the project already has text for a tool, or a vendor tool wrote its own block (OMX), `ai-adopt` skips and reports. A rule lives either globally or in the project, never both.
- **Employer rules stay out of this repo.** Put them in the project or in a private file.

## 5. Precedence

When two rules clash, this order decides:

1. The owner's hard rules in the global file (part 00, the gates, "confirm before outward actions").
2. The rest of the global file.
3. The project `AGENTS.md`. It may add rules. It may override **only style or tooling details** (for example "use `pnpm`, not `npm`", or "tabs, not spaces"). It may not remove a gate, drop the audit rule or relax the secret rule.
4. Vendor templates (OMC, OMX). On a clash the owner text and the hard rules win. Example: OMX says "do not stop to ask". The owner rule says to confirm hard-to-reverse actions. The owner rule wins.

Example of a legal project override: the global rule says "tests run through RTK". A project that needs `uv run` writes "run tests with `uv run rtk pytest`". That is a tooling detail, and it keeps RTK.
Example of an illegal override: a project says "skip agent-audit, it is slow". Not allowed. The gate blocks the install anyway.

## 6. How to change a rule, end to end

Example: you want agents to "always write commit messages in English".

1. **Pick the right place.**
   - Applies to every project and every agent: a part in `ai/agents-md/`.
   - Applies to one tool: its contract `ai/rules/<tool>.md` (and a short form in part 90 if needed).
   - Applies to one project: that project's `AGENTS.md`. Not this repo.
   - Is a tool-choice rule ("use X when Y"): a row in `ai/routing.yaml`, not prose.
2. **Edit the part.** Short, plain sentences (Simplified Technical English). No em dash. Example in `ai/agents-md/50-pull-requests.md`:
```
Write commit messages in English.
```
3. **Render.** `ai/bin/ai-render`. It rebuilds `ai/AGENTS.md` and fails if the file is over 30 KB. Read the new file. It is built on each machine and is not committed, so the check on your side is the size and the content.
4. **Test the rule.** If it is a routing rule, add one should-fire and one should-not-fire eval (see [EXTENDING.md](EXTENDING.md)). Run `ai-doctor`.
5. **Commit.** The changed part (and `ai/routing.yaml` if you changed it). The rendered file is not committed.
6. **Push.** `git push origin ai`.
7. **Pull on each machine.** `git -C ~/.dotfiles-ai pull`. The git hook runs `ai-sync`. Claude and opencode see the change at once (they read the link). Codex and Hermes get their copies refreshed by `ai-sync`.
8. **Check.** `ai-sync --check` and `ai-doctor` on each machine. On a server with boxes, an admin also runs `sudo proj sync-rules --all`.

If the hook is not installed on a machine, run `ai-sync` by hand after the pull. Install the hook with `ai-sync --install-hook`.

### Example 2: add a tool to the routing table

1. Add a row to `ai/routing.yaml` (`id`, `scope`, `trigger`, `action`, `strength`).
2. `ai-render`: the L0 table in `ai/AGENTS.md` gets the new row, and `routing.json` is rebuilt for the hooks.
3. Steps 4 to 8 above.

### Example 3: the file gets too big

`ai-render` fails: `AGENTS.md is over 30 KB`. Do not raise the cap. Move long text out: put it in `ai/rules/<tool>.md`, and leave 2 to 4 lines in part 90 with the pointer "Details: ~/.config/ai/rules/<tool>.md". Render again.

## 7. Why this design

- **One source** means a rule is written once and cannot disagree with itself.
- **Link or import where possible, copy only where needed.** Copies are the weak point, so `ai-sync --check` guards them.
- **Managed blocks** let us live in files that other tools also write, without owning them. And they make removal exact.
- **A size cap** keeps the always-loaded text small.
- **Global must, project may adjust style** keeps safety rules from being dropped by one careless project file.
