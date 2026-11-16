---
name: skills-guide
description: 'Use when the owner asks which skill, flow or command fits a task ("which skill for X", "how do I use wayfinder", "what does implement do", "list our skills", "what skills do we have", "cum folosesc", "какой скилл"), or before you pick between Matt Pocock skills, OMC skills and our own. Explains how each of the 27 Matt Pocock skills works, when to use it, an example, what it writes, and how the AI setup enables it per project. Not for writing a new skill (use writing-for-agents).'
---

# Skills guide (AI setup)

Snapshot: 2026-11-15, mattpocock/skills at the newest stable tag. The full owner guide with long scenarios is
`~/.dotfiles-ai/docs/GUIDE.md`. Read it for "adopt a messy repo", "start a mobile app", "build V2".

Before you say what a skill does, read its own SKILL.md. The summaries here are for orientation only.
- Matt Pocock originals: `~/.local/share/ai/plugins/mattpocock-skills/<name>/SKILL.md` (Linux server profile:
  `/opt/agent-plugins/mattpocock-skills/<name>/SKILL.md`). They are unchanged copies of upstream.
- Upstream: https://github.com/mattpocock/skills (router: `ask-matt`, phase rules: `ask-matt/PHASE-BOUNDARIES.md`).

## 1. Where each skill is on

| Scope | Skills | How to change |
|---|---|---|
| Global, every repo, Claude and Codex | grilling, grill-me, wait-what, writing-for-agents, retro, ask-matt (Matt); skills-guide, ship, release, promote-skill, upgrade-review, prompting-claude-and-codex, create-verification-skill, maintain-verification-skill (ours) | install.sh |
| Per project, default in every project | grill-with-docs, domain-modeling, to-spec, to-tickets, tdd, pr, diagnosing-bugs, improve-codebase-architecture, implement, research, handoff, wayfinder, prototype (+ callees codebase-design, code-review) | `skills:` line in `.ai/enabled` |
| Per project, opt-in | implement-spec, triage, wizard, to-questionnaire, teach, setup-matt-pocock-skills | `ai-adopt --skills <list>` |
| Per project, default tool | ui-ux-pro-max (every project has a UI; `no-ui` in `.ai/enabled` turns it off) | `ai-adopt` |

- No tiers: every project gets the full setup (`tier: long`: Done block, docs/REGRESSIONS.md, ratchet).
- A rerun of `ai-adopt` adds new defaults and keeps extra opt-ins already on the `skills:` line.
- A skill that is not linked in this project is still readable at the path above. If the owner wants it here:
  `ai-adopt --skills <current list>,<name>` (--skills replaces the list; read the `skills:` line first).
- Do not run `setup-matt-pocock-skills` in a repo that `ai-adopt` set up. ai-adopt already wrote
  `docs/agents/issue-tracker.md` and `docs/agents/domain.md` in the format the skills read.

Typed = the owner must type `/<name>` (the model cannot start it). Auto = the model starts it when the task fits.

## 2. The main flow (idea to ship)

```
idea -> /grill-with-docs -> needs a runnable answer? -> prototype (throwaway, branch prototype/<name>)
          |
          +-- fits one session  -> /implement here
          +-- several sessions  -> /to-spec -> /to-tickets -> /implement <ticket> (/clear between tickets)
                                                         \-> or /implement-spec (parallel subagents, one integration branch)
   /implement = tdd red-green slices + code-review (Standards + Spec) + commit
   -> ship (checks, verify, review, security, UI checklist, Evidence, gh pr ready) -> the owner says merge
   -> after the merge: /improve-codebase-architecture + /retro (the session start asks; findings = a PR)
   -> several features merged, the owner says release -> release (full audit, fix PRs, tag)
On-ramps: a hard bug -> diagnosing-bugs     raw incoming issues -> /triage
          a huge, unclear effort -> /wayfinder -> /to-spec
UI:       kickoff -> ui-ux-pro-max --design-system, 3 to 5 variants (prototype ?variant=), the owner picks, --persist
          (design-system/<app>/MASTER.md); every UI change reads it; code-review checks it (CODING_STANDARDS.md)
Setup:    a good approach in one repo -> promote-skill (dotfiles PR); tools upgraded -> upgrade-review
```

Git (global rule "Git workflow"): a branch named after the feature slug before the first edit; /implement commits
each ticket there; push and a draft PR after the first ticket; the ship skill, then gh pr ready; every PR goes
through the owner: merge only after the owner says merge (the merge-approval gate), never push to main.
prototype/ and research/ branches are never merged. Agents never skip git hooks (the no-verify gate).

Navigation: wide question -> graphify query / graphify affected; exact symbol -> Serena; text -> rg.

Context hygiene: keep grill-with-docs, to-spec and to-tickets in one unbroken session (no /compact before
to-tickets). Each /implement starts fresh from its ticket.

## 3. Phase boundaries (between two chunks of work)

Ask in this order. The first yes wins.
1. Continue? Yes when the next phase needs this one verbatim (grill -> implement) or there is room left
   (about 150k tokens of sharp reasoning).
2. Context no longer relevant? `/clear`.
3. Work must travel (Claude -> Codex, M3 -> ubuntu01, another repo, a colleague, a side task found mid-phase)?
   `/handoff`. The file goes to $TMPDIR. It is portable, not stored knowledge.
4. Can it run alone (a review, a research question)? A subagent.
5. Otherwise `/compact <what the next phase needs>`.
Decide only at a boundary. Mid-phase: continue, or split the rest into subagents.

## 4. Each skill

### Planning and alignment
- **grilling** (auto, global). The interview primitive. Rounds of questions, a recommended answer for each, facts
  are the agent's job, decisions are the owner's. No action until confirmed. Example: "grill me on the pricing
  plan". Writes nothing.
- **grill-me** (typed, global). grilling with no repo under it: plans, writing, life decisions. Writes nothing.
- **grill-with-docs** (typed, project). grilling plus domain-modeling in a repo. Use it before every change.
  Example: `/grill-with-docs add team billing`. Writes `GLOSSARY.md` terms and `docs/adr/NNNN-<title>.md` for
  hard-to-reverse decisions.
- **domain-modeling** (auto, project). Sharpens terms: challenges a fuzzy word, splits an overloaded word
  ("account" doing three jobs), records an ADR. Writes `GLOSSARY.md`, `docs/adr/`.
- **codebase-design** (auto, project). The deep-module words: module, interface, depth, seam, adapter. Use it to
  decide where a seam goes or to make code testable. Writes nothing by itself.
- **wayfinder** (typed, project). For work too big and too unclear for one session. Session 1 charts
  a map: destination, decision tickets (research = agent alone, prototype / grilling = with the owner, task =
  manual work that unblocks a decision), and a "Not yet specified" list. Next sessions: `/wayfinder <map>`
  resolves ONE ticket each (research tickets can run in parallel). It produces decisions, not code. When the
  map is clear, go to `/to-spec`. Files: `docs/maps/<effort>/map.md`, `docs/maps/<effort>/issues/NN-<slug>.md`.
  Example: `/wayfinder a mobile app for iOS and Android that syncs offline`.
- **prototype** (auto, project). Throwaway code that answers one design question. Logic question: one
  HTML file with buttons that drives the state model. UI question: several very different layouts on one route,
  switched with `?variant=`. No tests, no persistence. Kept on branch `prototype/<name>`; only the decision goes
  to main.
- **research** (auto, project). A background agent reads primary sources (official docs, source code) and writes
  one Markdown file with a source for each claim. Use context7 first for library docs. File:
  `docs/research/<topic>.md`. Example: "research how Expo EAS handles iOS push certificates". Feed the file into
  grill-with-docs.
- **to-questionnaire** (typed, opt-in). The blocker is in someone else's head. It asks the owner who the reader
  is and what is needed back, then writes a Markdown questionnaire to send.
- **ask-matt** (typed, global). Router: "which flow fits?". Reads the skill files before it answers.

### Spec, tickets, build
- **to-spec** (typed, project). Turns the current conversation into a spec. No new interview. File:
  `docs/specs/<feature>.md`.
- **to-tickets** (typed, project). Splits a spec into tracer-bullet tickets (thin vertical slices), each with
  "Blocked by" edges. Files: `docs/tickets/<feature>/NN-<slice>.md`. Done tickets move to `done/`.
- **implement** (typed, project). Builds one ticket or a small piece of work: tdd at agreed seams, typecheck and
  single test files often, full suite at the end, then code-review, then a commit on the current branch.
  Example: `/implement docs/tickets/billing/02-refunds.md`. Our Done order still applies after it: check-fast,
  verify-<app> evidence, e2e test.
- **implement-spec** (typed, opt-in). The whole spec in one run: one implementer subagent per ready ticket, each
  in its own worktree, merged into one integration branch, one code-review at the end. Overlaps OMC team: use
  this for a to-tickets graph, OMC team for ad-hoc parallel work.
- **tdd** (auto, project). Red-green-refactor, one vertical slice at a time. Tests go through public
  interfaces; mock only at system edges.
- **code-review** (auto, project). Reviews the diff since a fixed point on two axes, in two parallel subagents:
  Standards (the repo's coding rules plus a Fowler smell list) and Spec (does it do what the ticket asked).
  Name clash: Claude Code also has a built-in `/code-review`. Say "Matt code-review skill" to get this one.
- **pr** (auto, project). The PR body shape. Our gate requires it plus a Mermaid diagram:
  `## Summary` (smallest visual, a ```mermaid diagram is required), `## Evidence` (Before / After: test run,
  output or screenshot), `## Merge Danger` (`**Door:** one-way or two-way`, `**Blast Radius:**`), then
  Docs, Changed guards, Ledger (fix PRs), then the author-sessions block.
- **wizard** (auto, opt-in). For steps only a human can do (provision infra, create API keys, CI secrets, a
  dashboard click-through, a one-off cutover). It writes an interactive bash script that the owner runs; the
  script opens each URL and saves each value. The agent does not edit `.env` itself.

### Bugs and quality
- **diagnosing-bugs** (auto, project). For hard bugs and slow paths. Phase 1 is the skill: build ONE fast,
  repeatable command that goes red on this exact bug before any theory. Then shrink the case, rank 3 to 5
  testable guesses (show them to the owner), probe one variable at a time with `[DEBUG-xxxx]` tagged logs,
  write the regression test before the fix, remove the debug logs. Commit message states the cause that was
  right.
- **triage** (typed, opt-in). Moves raw incoming issues (bug reports, requests you did not write) through
  triage states and writes agent-ready briefs. Not for tickets that to-tickets made. Our tracker is local:
  no GitHub issues or labels without the owner.
- **improve-codebase-architecture** (typed, project default). A survey: finds "deepening" chances (shallow
  modules, bad seams), shows an HTML report, then grills through the one the owner picks. Runs after each merge
  to main (the merge-review rule at session start), focused on the area that changed. Record it with
  `git rev-parse main > .ai/last-review`.

### Our own flow skills
- **ship** (auto, global). The pre-merge pipeline on a feature branch: make check, verify-<app>, Matt
  code-review, /security-review, the UI checklist, PR Evidence, gh pr ready, then ask the owner.
- **release** (auto, global). The owner says release: a full audit (security, architecture, web performance,
  SEO, blog, UI and accessibility, mobile, API, migrations), fix PRs, `docs/releases/<version>.md`, then the tag.
- **promote-skill** (auto, global). Turns a good approach from one repo into a shared skill in the dotfiles,
  through a PR for the owner.
- **upgrade-review** (auto, global). After a tool upgrade (session start says so): release notes, what breaks,
  what to use, a dotfiles PR.
- **retro** (typed, global). After a session (best: one that went wrong). Suggests changes to the environment,
  most severe first: Map pointers, automated checks, coding standards, AGENTS.md rules, tooling. Mechanical
  mistakes become checks; judgement calls become standards.

### Communication and learning
- **handoff** (typed, project). Writes a short summary of this session to $TMPDIR with "suggested skills" for the
  next agent. It points to specs, tickets and commits instead of copying them, and removes secrets. Use it only
  when work travels (see section 3). Example: `/handoff continue the refund slice in Codex on ubuntu01`.
- **wait-what** (typed, global). "That did not land." The agent re-explains its last message in plain words with
  the GLOSSARY.md terms.
- **teach** (typed, opt-in). Teaches a concept over several sessions; the folder keeps the learning record.
- **writing-for-agents** (auto, global). Rules for skills, AGENTS.md, CLAUDE.md. Use it before you edit one.
- **setup-matt-pocock-skills** (typed, opt-in). Upstream setup of tracker, labels, doc layout. Not needed in an
  ai-adopt repo (see section 1).

## 5. Overlaps (use the first)

| Need | Use | Not |
|---|---|---|
| New feature or kickoff interview | grill-with-docs | OMC deep-interview (only for "ambiguity score") |
| Plan a well-scoped feature | to-spec, to-tickets | `oh-my-claudecode:plan`, `oh-my-claudecode:omc-plan`, `oh-my-claudecode:ralplan`, `oh-my-codex:plan`, `oh-my-codex:ralplan` |
| Plan a huge unclear effort | wayfinder | OMC ultragoal (orchestration: it still runs) |
| Build tickets | implement / implement-spec | `oh-my-claudecode:execute`, OMC team for ad-hoc work |
| Build test-first | tdd | `oh-my-claudecode:tdd` |
| Research a library or API | research (context7 first) | `oh-my-claudecode:research`, `oh-my-codex:best-practice-research`, web search |
| Review a diff | Matt code-review | built-in /code-review, `oh-my-claudecode:review`, `oh-my-claudecode:omc-review`, `oh-my-codex:code-review` |
| Write a PR body | pr | `oh-my-claudecode:pr` |
| Prove a feature works | verify-<app> (create-verification-skill) | "tests pass" alone |
| Knowledge | AGENTS.md Map, GLOSSARY.md, docs/adr, docs/specs, docs/tickets, docs/research | Serena memories, `oh-my-claudecode:wiki`, `oh-my-codex:wiki`, Claude auto memory (off) |
| Pre-merge checks | ship (ours) | OMC verify alone |
| Cut a version | release (ours) | `oh-my-claudecode:release` |

The winner gate enforces this table (`winners` in `ai/routing.yaml`; a test keeps both the same). An agent's
Skill tool call of a name in backticks is denied, and the message names the skill to use (a typed-only winner:
read its SKILL.md and follow it). A typed /name of the owner always runs. Codex runs a skill by reading its
file: a shell read of a losing OMX skill (`~/.codex/skills/<name>/SKILL.md`) or OMC skill file is denied the
same way. OMC and OMX orchestration (autopilot, ralph, team, ultragoal) always runs, and so do the skills it
calls. ask, babysit, fix-ci and cancel run too, but they do not unlock the skills in backticks.

## 6. Answering "which skill?"
1. Name the situation in one line.
2. Give the skill, typed or auto, the exact command, and the file it writes.
3. If it is not linked in this project, give the `ai-adopt --skills` command.
4. Read that skill's SKILL.md before you add detail.
