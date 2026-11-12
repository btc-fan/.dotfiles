
No root
Never run sudo or try to get root (su, pkexec, setuid tricks, editing sudoers). When something needs root (apt, systemctl, files in /etc), stop and give me the exact command to run.
Box work on a server: the box tool (MCP server box: list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help); outside a sandbox also plain proj-agent <subcommand>; never sudo (the no-sudo gate blocks sudo proj-agent like every other sudo).
