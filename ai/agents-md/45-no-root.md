
No root
Never run sudo or try to get root (su, pkexec, setuid tricks, editing sudoers). When something needs root (apt, systemctl, files in /etc), stop and give me the exact command to run.
Box work on a server goes through the box tool (MCP server box: list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help) in Claude, Codex and Hermes; plain proj-agent <subcommand> only outside a sandbox. Never sudo proj-agent: the no-sudo gate blocks it like every other sudo.
