
Audit before use
Before you install a package, MCP server, skill or plugin, run agent-audit on it.
- Commands: agent-audit npm|pypi|dir|skill <target>.
- A finding means stop. Show it to me. Do not install.
- Install exact versions only. No @latest. No curl piped to a shell.
- The gate blocks npm, pip, uv, npx and curl-to-shell without a PASS in the last 24 hours. It asks me for brew, cargo, go, gem and pipx.
- Use no tool that uploads code, prompts or telemetry.
- Secrets: never put a key, token or password in a file that is committed. The secret-scan gate blocks git commit and git push on a hit.
- Escape hatch for a gate: AI_GATE_SKIP=<rule-id> with a reason. It is logged. Use it only when I say so.
