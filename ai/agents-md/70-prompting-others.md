
Prompting other agents
This applies to subagents, codex exec, claude -p, opencode run, omc ask and herdr agent prompt.
1. Give the goal and what is already ruled out.
2. Name the files. Use absolute paths.
3. Keep the scope narrow. One task per agent.
4. Say the expected output and its format. Ask for a file path when the result is long.
5. Read-only unless I said otherwise.
6. Put the code navigation rules in the brief when the agent explores code (graphify query first, then Serena).
7. Do not add --bare to claude -p. It turns off hooks, skills and plugins.
8. Check the result yourself. The agent report is a claim, not proof.
Skill: prompting-claude-and-codex.
