# 04: Narrow hook wiring: does it hold, and what does it save

Type: prototype
Status: open
Blocked by: none

## Question

When each hook entry gets an `if` filter and each gate gets `onFailure: "block"`, do all router case files still
pass, and how many processes does a session start?

Build a throwaway copy of the plugin hook file on a `prototype/` branch. Run a fixed list of 20 tool calls (Bash
that is not git, `git commit`, `gh pr create`, Read, Edit of a code file, Edit of `.env`, Edit of `AGENTS.md`,
a Skill call, a Stop) in a headless session with the copy. Count the hook processes and the wall time, with
today's wiring and with the copy. Then make one gate sleep past its timeout and show that the call is blocked.

The owner reacts to 2 things: the table of counts, and the list of rules that cannot be written as one `if`
filter (a filter holds one rule and has no "or").

Read first: report section 3.
