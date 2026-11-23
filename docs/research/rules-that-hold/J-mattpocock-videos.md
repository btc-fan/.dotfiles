# J. Matt Pocock's videos: what he says and does about agent setups

Date: 2026-11-23. Research files A to I read his repositories. This file reads his videos.

## Method

- Source: the 321 videos of the channel `@mattpocockuk`, as plain-text transcripts (536,189 words).
- In scope: the 89 videos from 2025-09 to 2026-11 about AI coding (187,080 words). The 232 older videos are about TypeScript.
- The planner read 51 videos in full: the 49 short ones and 2 long ones.
- Five reader agents read the other 38 long videos in full and wrote notes with verbatim quotes.
- Check of the notes: a script searched each quote in the transcript of its video. It found 472 of 506. The other 34 were split wrongly by the script.
- The transcripts are auto captions. A quote can hold a caption error. The raw text is not in this repository.
- A link has the form `https://www.youtube.com/watch?v=<id>`. Each finding gives the id and the date.

## Findings

### 1. The always-loaded file is almost empty

- His own file is one line of 6 words: "You are on WSL on Windows" (`9tmsq-Gvx6g`, 2026-02-24).
- "I've advocated almost always deleting your Claude.md" (`3CSi8QAoN-s`, 2026-02-25).
- The reason is an instruction budget: "LLMs really only have a realistic instruction budget of around 300 to 400 instructions." (`9tmsq-Gvx6g`).
- A line in that file is global: "anything you put into this global scope here will affect everything you do and cost you tokens every time" (`9tmsq-Gvx6g`).
- What stays out: commands, architecture, file paths and each fact that the agent can find in the code.
- What stays out too: a rule that a hook enforces. "The hook already enforces it deterministically." (`llwTBpPqo9A`, 2026-03-23).
- History: in 2025-10 his file had "only about 43 lines". In 2026-02 it had 1 line.

### 2. A rule is a deterministic check, not a sentence

- A sentence lowers the chance, and does not prevent: "we're reducing our chances of running get push or reducing our chances of running npm, but we're not preventing it." (`3CSi8QAoN-s`).
- His fix is one small script for each rule on the PreToolUse event. The script prints the right command and ends with exit code 2.
- "You get to take instructions out of your instruction budget and enforce them deterministically." (`3CSi8QAoN-s`).
- Style rules become lint rules: "turning them into ESLint rules so that I can lint Claude into the right thing without needing to warn it or instruct it." (`3CSi8QAoN-s`).
- A review finding becomes a lint rule that gets stricter with time (`jVBlkOF8sHk`, 2026-11-18).

### 3. Checks run at the commit, not in the agent hooks

- Video: "STOP running your checks in harness hooks" (`zgy8_ApYNDk`, 2026-10-13).
- A check on each file edit is slow and noisy: "what you're doing there is you're just telling the agent something it already knows."
- "if you put these checks in a pre-commit hook instead, you're going to end up with a better result."
- Time limit for the pre-commit hook: "You ideally want them shorter than 3 seconds."
- Slow checks go to CI, "which will run before the PR merges".
- Agent hooks are for one job only: to block or redirect a command (finding 2).

### 4. Skills are short, and the user starts them

- "I think of my skills as empowering the user, not empowering the agent." (`32LyZyFQhCQ`, 2026-07-17).
- Most of his skills are user-invoked, so their cost is small: "the skills only take up 660 tokens here." (`M6mYodf0dJM`, 2026-07-16).
- No hook or router selects a skill. The user types the skill name.
- A few skills are model-invoked with a clear description: `pr`, `writing-for-agents`, and narrow knowledge skills.
- "Before you use any skill, you should read the entire skill." (`BsJGo1wFTvQ`, 2026-10-05).
- Video: "Your skills are WAY TOO LONG" (`y81cjELJMI0`, 2026-10-13): "Ruthlessly edit them. Keep them short."
- "Skill hell" is many frameworks in one context window: "it overloads the model" (`32LyZyFQhCQ`).
- Rare knowledge goes into a narrow skill, not into the always-loaded file (`llwTBpPqo9A`).

### 5. One home for the setup, not a copy in each repository

- Video: "The Home Repo" (`hWe-j78vNpc`, 2026-11-12).
- The problem: "you then need to keep all of those skills, all of that tooling in sync across different repos".
- His answer: one repository holds the skills, the steering file, the versioned settings and the tools. The agent always starts there.
- A link to another repository is "Literally just a path inside the agents.md."
- He rejects the user directory for a team, because it is not visible and it falls behind.
- For one developer he accepts a global install: "global is fine if you're just a solo developer" (`M6mYodf0dJM`).

### 6. Less text in the context gives better work

- Video: "Claude Code's system tools are SO BLOATED" (`oLx4yCbeklQ`, 2026-07-16). He switched off unused built-in tools, bundled skills and connectors in `settings.json`.
- Result: "from 25K down to around 8K" tokens at the start of a session.
- "The less you send over the wire, the better your outputs are going to be".
- The smart zone ends near 150,000 tokens (`sOd7svdu_1I`, 2026-07-20). One ticket fits one context window.
- Effort level: "I use Opus 5.5 on medium, and I'm debating even moving to low." (`JgEsphDAXnY`, 2026-10-13).
- More tools make the model worse: "the more tools that you give the LLM, the worse it performs." (`_1KrC_5Xv4s`, 2025-09-25).

### 7. No memory, few documents

- Video: "Kill your MEMORY.md" (`A0scuiiGBC4`, 2026-07-17): "I much prefer my agent to be completely stateless".
- Video: "Delete (most of) your docs" (`Fj8DKMbdIzU`, 2026-07-16). A document that repeats the code drifts from the code.
- Three kinds of document stay: decision records, a glossary, and "a thin layer of docs just to navigate".
- A spec is deleted when the code holds it (`F3lL98Pj90o`, 2026-07-30). Research files rot (`Ah9p7v7nJWg`, 2026-03-03).

### 8. Quality comes from feedback loops and from the codebase

- "Your code base, way more than the prompts that you use, way more than your agents.md file, is the biggest influence on AI's output." (`uC44zFz7JSM`, 2026-02-26).
- Loops that he uses: tests first with one test at a time, strong types, lint, mutation testing, a browser for UI work.
- Review runs in fresh subagents on 2 axes, the standards and the spec (`M6mYodf0dJM`).
- A PR carries evidence: "Without asking for hard evidence it's very easy for agents to say yeah that probably works cuz I've read the code" (`BsJGo1wFTvQ`).
- A guest, the author of pstack, ranks verification first: "the single most important skill that should be in your toolkit is verification" (`MN9dGgmLyso`, 2026-10-03).
- The same guest moves the deterministic part of a skill into a script: "I try to extract out the deterministic parts and turn that into code and just leave only the parts that actually require judgment".

### 9. A mistake changes the environment, with a human in the loop

- His `retro` skill reads past sessions and proposes a check, a lint rule or a line in the coding standards (`Q8XzzKUbp0Y`, 2026-10-13).
- "No, you don't want to automate this." (`BsJGo1wFTvQ`). An automated loop finds false positives without end.
- The guest says the same: "how do I turn this into a lint rule? How do I make it so that the code base makes this impossible?" (`MN9dGgmLyso`).
- The guest reviews by sample and then corrects the environment, "Not not that single agent."

### 10. The human decides where the review is

- Big work: agree first (grilling), review last. Small work: no grilling, review last only (`Yn8h5Ip-L9c`, 2026-07-20).
- "if that diff is really small, then you can probably just oneshot the thing." (`jVBlkOF8sHk`).
- Merge danger has 2 parts: a one-way or two-way door, and the blast radius (`BsJGo1wFTvQ`).

### 11. Reply style is one line or one skill

- His line in 2025-10: "be extremely concise and sacrifice grammar for the sake of concision" (`I12Mf8KBT1I`, 2025-10-08).
- In 2026-02 he said that this line is "better placed inside a skill" (`9tmsq-Gvx6g`).
- In 2026-08 he said that output styles and lines in the steering file did not fix long replies. A skill did (`gaDdrDdczO4`).

## Where he changed his mind

| Topic | Before | Now |
|---|---|---|
| Always-loaded file | 43 lines (2025-10) | 1 line (2026-02) |
| Dumb zone | 100,000 tokens (2026-01) | about 150,000 tokens (2026-11) |
| Compaction | avoid it | he uses it when the plan is in a document |
| Ticket loop | a shell loop (2026-01) | a deterministic script, or one skill with subagents (2026-10) |
| Domain file | `CONTEXT.md` | `GLOSSARY.md`, because the old name did not trigger the agent |
| Worktrees | "every single time" (2026-02) | setup cost is high for small work (2026-07) |

## Compared with this setup

Numbers of this setup are from `docs/reports/baseline-2026-11-20.md` and from the branch at commit `6fc9ba3`.

| Topic | His setup | This setup |
|---|---|---|
| Always-loaded rules | 1 line | 2,847 words in 13 parts |
| Text added by hooks at session start | none | the rule table again, plus style text of 2 plugins |
| Text added for each prompt | none | a list of yes or no questions about tools |
| Skill choice | the user types it | hooks select skills by prompt words |
| Agent hook code | 1 script of a few lines for each block rule | 5,991 lines, 12 hook entries, 8 events |
| Checks | pre-commit under 3 s, then CI | pre-commit, CI, and 2 Stop checks at each end of turn |
| Setup location | 1 home | 1 home plus a generic layer copied into each project |
| Update of a project | none | 1 PR for each project and each setup version |
| Verification skill | the guest's top skill | present, and it has a helper script |
| Review on 2 axes, PR evidence, door and blast radius | present | present |
| Glossary, decision records, thin map | present | present |

The last 3 rows agree. The first 8 rows are the cause of the owner's two complaints: the setup is hard to follow, and the agents skip rules.

## Limits

- He works alone on TypeScript projects. He gives no advice for servers, deploys or data that must not be deleted.
- He gives no measured numbers for rule adherence. Our own number is 241 of 321 reminder fires not followed.
- His hook scripts check the start of a command only. A compound command passes them. A hard wall must be at the remote.
- The 232 TypeScript videos were not read.
