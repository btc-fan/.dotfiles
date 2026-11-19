# 14: The router starts only where a rule can fire, and a gate blocks on a timeout

**What to build:** a tool call that no rule covers starts no router process, and a gate that passes its timeout
blocks the call. Measured on 2026-11-18: the plugin hook file names 11 tools in one matcher, so the router starts
before and after each Read, Glob, Agent and Task call, and no routing rule names these tools. The Claude Code
hooks reference says that a timed-out PreToolUse hook does not block the call unless the entry sets
`"onFailure": "block"` (version 2.1.295 or later). No entry sets it. An entry can also carry an `if` filter such
as `"Bash(git *)"`.

**Blocked by:** None (can start immediately). The map ticket "Narrow hook wiring" measures the full version; this
ticket is the part that needs no decision.

**Status:** ready-for-agent

- [ ] The matchers hold only tools that a rendered rule names. Read, Glob, Agent and Task go.
- [ ] Each entry that can deny has `onFailure: "block"`. A test makes a gate sleep past its timeout and sees a
  block.
- [ ] The Stop check entries are written only for a profile that turns the Stop check on. On dev-mac no
  `stop-check.py` process starts.
- [ ] The prompt hook has enough time to store the owner's merge OK on a slow machine, or the OK is stored in a
  way that a timeout cannot lose. Today the timeout is 5 s, and 2 timeouts were seen in one session.
- [ ] The hooks may use a bytecode cache in the state folder.
- [ ] `ai-doctor` prints the count of hook processes for one Bash call, one Read and one Stop.
- [ ] The notifier that hits its 12 s timeout on Stop is fixed or removed (6 lines in the router error log).
