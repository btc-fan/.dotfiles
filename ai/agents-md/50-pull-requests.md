
Pull requests
The PR body follows the `pr` skill (Matt Pocock). Use this template:
```markdown
## Summary
<smallest visual that shows the change; a ```mermaid diagram is required, other visuals are optional>
## Evidence
- **Before:** <failing test run, output or screenshot>
  **After:** <passing run, output or screenshot>
## Merge Danger
**Door:** <one-way or two-way> <reason>
**Blast Radius:** <what can break>
```
Summary must hold a Mermaid diagram of the change.
Evidence is the check-fast command and the tail of its output as After. Add Before when a test went red first. A project with a verify-<app> skill also names the skill run, its evidence path and the e2e test.
Door must say one-way or two-way. Blast Radius must say what can break.
Also required: Docs (files, or "none, because ..."), Changed guards (each edited or removed test and why, or "none"), and on a fix PR Ledger: R-NNN. A fix PR has a test file in its diff.
The author-sessions block goes at the end (next section). The pr-rules gate blocks a PR without the Mermaid diagram, Evidence, Door, Blast Radius or the author-sessions block, and a fix PR without a test file (placeholder text counts as missing). Docs, Changed guards and Ledger get a warning only.

PR author-sessions note
When you create a PR, or push changes to an open PR, keep this hidden block at the end of the PR body, before the generated-with footer:

<!-- author-sessions
updated: <YYYY-MM-DD>
main:   <session-id>  dir: <cwd, with ~ for $HOME>  # <what this session did>
herdr:  <session-id>  dir: <cwd, with ~ for $HOME>  # <what this agent did>
-->
main is your own session. Get the ID with herdr agent get "$HERDR_PANE_ID" | jq -r '.result.agent.agent_session.value'.
Add one herdr line for each Herdr agent that you started or prompted for this PR. Get its ID the same way with its agent name or pane ID, and its dir from .result.agent.cwd.
Do not add subagents. They resume with the main session.
On an update, keep the existing lines, add the new ones, and change updated.
When you edit the PR body for other reasons (for example a recap skill), keep this block.
If an ID is empty, write main: unknown (or herdr: unknown) and tell me. Do not guess an ID.
pr-resume parses this block. Keep the line format exact: one ID, dir:, one path without spaces.
