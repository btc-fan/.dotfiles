
No root
Never run sudo or try to get root (su, pkexec, setuid tricks, editing sudoers). When something needs root (apt, systemctl, files in /etc), stop and give me the exact command to run.
The only exception, on a server where the hosting rules allow it: box commands, written ai-box <subcommand> (Codex and Hermes may also write sudo proj-agent <subcommand>). The no-sudo gate blocks everything else.
