# Memory Maintenance

## Discovery Model

- Core principle: progressive discovery through references, building a graph of memories.
- Initially, agents are provided with the list of all memories (names only).
- Agents should read `mem:core` as the top-level entry point (graph root).
  This memory should contain references to other memories covering major project domains.
  The referenced memories shall, in turn, shall contain references to even more specific memories, and so on.
  The depth of the graph shall depend on the project complexity.
- Use topics/folders to group related memories in order to make the content structure explicit.
  Folders can mirror project structure (e.g. modules like frontend/backend) or topics like debugging, architecture, etc.
- Memory references must use a mem: prefix inside backticks, e.g. `mem:frontend/core`.
  The surrounding text should clearly indicate when to read the memory/which content to expect.
  The text should provide more precise guidance than the memory name alone, 
  i.e. avoid a reference like "frontend debugging: `mem:frontend/debugging` and instead make clear which aspects of frontend debugging are covered.
- Memories themselves should not contain information about when to read them; this is the responsibility of the referring memory.

## Style

Dense agent notes, not prose docs. Prefer invariants, terse bullets. 
Avoid obvious context, rationale, and examples unless they prevent likely mistakes. 
Keep guidance durable and generalizable, not task-local.

## Add/update threshold

Add or update memories only with stable, non-obvious project conventions that avoid complex rediscovery in the future.
Do not add: quick-read facts; generic language/framework knowledge; one-off task notes; volatile line-level details; behavior likely to change soon.

## Maintenance Actions

- Renaming memories: References are updated automatically if handled via Serena's memory rename tool.
- Checking for stale memories (e.g. after deletion): Call `serena memories check` for a report.

## Our rules (dotfiles ai branch, added to the Serena 2.1.0 template above)

- Sizes: core <= 60 lines, other memories <= 40 lines, all memories together <= 16 KB. Split by topic, do not grow one file.
- core holds: what the project is (1 line), a source map (folder or module -> one line), the main commands, and `mem:` links to the other memories.
- Do not repeat AGENTS.md or CLAUDE.md (loaded every session). Point to files by path.
- No secrets, keys, tokens, passwords, hostnames with credentials, phone numbers, emails or other personal data. Memories are committed and pushed.
- Library docs IDs live in .ai/libs.md, not in memories.
- Update the source map in core when you add, delete or rename a module. Memories are hints: the code wins.
- Plain short sentences. No long dash (U+2014).
