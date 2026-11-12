
Audit and gates
- Before you install a package, MCP server, skill or plugin: agent-audit npm|pypi|dir|skill <target>. A finding means stop and show it to me. Exact versions only, no @latest, no curl piped to a shell.
- Never commit a key, token or password. The secret-scan gate blocks commit and push on a hit.
- Commands run in a sandbox. A network or permission error is final too: do not try to get around it (no other path, no SSH instead of HTTPS); tell me the command and the error.
- A blocked gate is final for you. Only I can let it through (sudo ai-gate-skip). Never try to get around it; tell me the command and why.
