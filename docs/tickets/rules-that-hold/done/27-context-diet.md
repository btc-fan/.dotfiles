# 27: A smaller start context for each Claude session

**What to build:** The installer writes a "context diet" block into the user settings of Claude Code on the `dev-mac` profile. A new session then starts with about 14,700 fewer tokens. One profile key turns the whole block off.

**Why:** A new Claude Code session in an adopted project started with about 56,900 tokens before the first prompt. Three parts of that text have no use for the owner: the claude.ai connectors, the long skill descriptions and the built-in tools that no session calls.

**Solution:**
1. Profile key `PROFILE_CONTEXT_DIET` in `ai/profiles/*.env`: 1 on `dev-mac`, 0 on `server`. The value 0 turns the whole block off.
2. `"disableClaudeAiConnectors": true`, through the present connectors switch (`claudeai_connectors_off` in `ai/adapters/base.sh`). The owner flag `--keep-claudeai-connectors` still wins.
3. `"skillListingMaxDescChars": 80` (`claude_context_diet` in `ai/adapters/claude.sh`), written with `aiconf json-set` and recorded.
4. A bare tool name in `permissions.deny` for each built-in tool of the deny list (`CLAUDE_DIET_DENY`). The names go through `claude_deny_rules`, so the present permissions sync adds them, keeps owner entries and removes only our entries.
5. `ai-doctor --numbers --live` runs one real `claude -p` session in the project and prints its start tokens and its cost. Without `--live`, no model call occurs.

**Tool counts:** Calls of each built-in tool in the session list, 60 days of session logs. The second machine counts came with the brief. The brief gave counts for 6 tools only, so this ticket takes the count of each other candidate on that machine as 0.

| Tool | This machine | Second machine | Result |
|---|---|---|---|
| Bash, Edit, Read, Write, WebFetch, WebSearch, Skill, ToolSearch, Agent (Task) | 549 to 29,189 each | not given | stays |
| SendMessage | 987 | 174 | stays |
| Monitor | 121 | 5 | stays |
| TaskStop | 102 | 23 | stays |
| ListAgents | 35 | 10 | stays |
| CronCreate | 2 | 0 | stays |
| CronList | 1 | 0 | stays |
| ScheduleWakeup | 0 | 14 | stays |
| EnterWorktree | 0 | 2 | stays |
| CronDelete | 0 | 0 | stays: it removes a job that CronCreate made |
| ExitWorktree | 0 | 0 | stays: it closes a worktree that EnterWorktree opened |
| DesignSync, NotebookEdit, RemoteTrigger, ReportFindings, Workflow | 0 | 0 | denied |
| ListMcpResourcesTool, ReadMcpResourceTool, ReadMcpResourceDirTool | 0 | 0 | denied |

**Measurements:** 7 real sessions with `claude -p "Reply with the word OK only." --model claude-haiku-5-5 --settings <file> --output-format stream-json --verbose`, in one adopted project. Start tokens are `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` of the result. The listing columns come from the `skill_listing` attachment of each session transcript (134 entries in each run).

| Settings | Start tokens | Listing characters | Entries with no description | Cost (USD) |
|---|---|---|---|---|
| as installed | 57,110 | 29,945 | 25 | 0.0058 |
| connectors off, 80 characters | 45,243 | 14,277 | 0 | 0.0034 |
| connectors off, 120 characters | 46,664 | 18,595 | 0 | 0.0036 |
| connectors off, 160 characters | 47,935 | 22,427 | 0 | 0.0039 |
| connectors off, 240 characters | 49,732 | 27,875 | 0 | 0.0043 |
| connectors off, 80 characters, `skillListingBudgetFraction` 0.002 | 42,409 | 5,979 | 104 | 0.0028 |
| final block: connectors off, 80 characters, 8 deny names | 42,382 | 14,277 | 0 | 0.0085 |

The choice is 80 characters. It is the smallest limit, and each description still shows its first 80 characters. At each limit, the same 17 descriptions are shorter than 80 characters in full. The budget fraction 0.002 drops 104 descriptions, so the block does not set it. As installed, the listing is over its budget, and 25 descriptions are dropped. The final block keeps 19 built-in tools of 27.

**Limits of the measurement:**
1. Each row is one session, so the numbers have no variance. Two runs of one setting can differ by some hundred tokens.
2. All runs used one machine, one project and the plugins that were on at that time. Another project has other rules files and skills.
3. The start tokens include the short prompt and the cache split. The total is correct, but the cost changes with the cache state.
4. The second machine counts are from the brief. This ticket did not read its logs.

**Rules kept:** No plugin is turned on or off. Serena, OMC and the style plugins do not change. The `server` profile does not change.

**Edge cases:**
1. An owner entry in `permissions.deny` stays. A name that the owner added first is not recorded, so the undo keeps it.
2. A second install run changes nothing.
3. The key set to 0 after an install: the description limit and the deny names go. The connectors key stays until an install with `--keep-claudeai-connectors`.

**Status:** done

**Size:** S

- [x] The block writes the 3 settings on `dev-mac` and nothing on `server`.
- [x] An owner deny entry survives, a rerun changes nothing, and the undo removes only our entries.
- [x] `ai-doctor --numbers --live` prints the start tokens and the cost.

**Verify:**
- Unit: `t_context_diet` in `ai/tests/test_m3.py`, `t_numbers_live` in `ai/tests/test_info.py`, the profile fixtures in `ai/tests/fixtures/profiles/`.
- Live: `ai-doctor --numbers --live` in an adopted project after an install.

**Rollback:** Set `PROFILE_CONTEXT_DIET=0` in the profile and run the installer, or revert the commit.
