# 02: ask-first gate for local commands

**What to build:** a new router gate `ask-first` on every profile. It denies the local high-impact command classes of spec Part 2 (services, power, containers, cron and unit files, kill and tmux kill, users and access, git force and hard reset, unasked PR and release commands, deploys, `rm -r` outside safe folders, SQL writes, unknown programs with a start or stop verb). The deny message tells the agent to show the plan, the risk and the undo, and to wait for a typed OK. Read forms pass.

**Blocked by:** None (can start immediately)

**Status:** done (2026-11-20)

- [x] Incident replay cases deny: `systemctl --user enable herdr-core-boot.service`, `herdr-core server start`, `tmux kill-session -t x`, `docker compose down`, `npx wrangler deploy`, `git push -f origin main`
- [x] Pass cases: `systemctl status x`, `systemctl --user list-units`, `docker ps`, `crontab -l`, `npx wrangler deploy --dry-run`, `kill $!`, `rm -rf node_modules`, `rm -rf "$TMPDIR/x"`
- [x] Same verdicts for Claude and Codex payloads
- [x] Real-command replay (14 days on this Mac, 10,274 commands): 5.4 stops a day (0.74%). Each stop is a real class (SQL write, unit file write, launchctl, kill, reset --hard). The 5 a day target is near; the owner decides if `kill <pid>` should pass
- [x] `bash ai/tests/run.sh` 0 failed (801 router cases)

Note: `gh pr create` without an owner ask moves to ticket 04, which holds the owner-prompt state.
