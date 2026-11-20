# 02: ask-first gate for local commands

**What to build:** a new router gate `ask-first` on every profile. It denies the local high-impact command classes of spec Part 2 (services, power, containers, cron and unit files, kill and tmux kill, users and access, git force and hard reset, unasked PR and release commands, deploys, `rm -r` outside safe folders, SQL writes, unknown programs with a start or stop verb). The deny message tells the agent to show the plan, the risk and the undo, and to wait for a typed OK. Read forms pass.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Incident replay cases deny: `systemctl --user enable herdr-core-boot.service`, `herdr-core server start`, `tmux kill-session -t x`, `docker compose down`, `npx wrangler deploy`, `git push -f origin main`
- [ ] Pass cases: `systemctl status x`, `systemctl --user list-units`, `docker ps`, `crontab -l`, `npx wrangler deploy --dry-run`, `kill $!`, `rm -rf node_modules`, `rm -rf "$TMPDIR/x"`
- [ ] Same verdicts for Claude and Codex payloads
- [ ] Real-command replay (14 days on this Mac): fewer than 5 stops a day, report in the PR
- [ ] `bash ai/tests/run.sh` 0 failed
