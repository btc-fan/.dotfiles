
Audit and gates
- Before you install a package, MCP server, skill or plugin: agent-audit npm|pypi|dir|skill <target> (also pypi httpx==0.28.1). Exit 3 = a scanner could not run: no PASS, not a finding. A finding means stop and show it to me. Exact versions only, no @latest, no curl piped to a shell.
- Never git add -A or git add . blindly: git status first, then add your changed files by name. Sandbox placeholder files in project roots are ignored globally; a real new .mcp.json or .claude/commands needs git add -f.
- Never commit a key, token or password. The secret-scan gate blocks commit and push on a hit.
- Commands run in a sandbox. A network or permission error is final too: do not try to get around it (no other path, no SSH instead of HTTPS); tell me the command and the error.
- A blocked gate is final for you. Only I can let it through (sudo ai-gate-skip). Never try to get around it; tell me the command and why.
