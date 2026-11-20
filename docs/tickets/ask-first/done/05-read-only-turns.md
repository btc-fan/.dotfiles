# 05: Read-only turns for audit, check and questions

**What to build:** a prompt whose main verb is audit, check, research, look at, review or explain, or a question, makes the turn read-only. In that turn the gate stops every host change, also changes outside the 12 classes (writes over ssh, sudo writes, `tee` to system paths). The router note tells the agent the turn is read-only. A typed OK lifts it for the shown plan.

**Blocked by:** 02

**Status:** done (2026-11-20)

- [x] Replay: prompt "audit how the bots come back after a power outage" plus the reboot chain: deny
- [x] Replay: prompt "how is the migration going?" plus a migration cut-over command: deny
- [x] A normal build prompt ("add a button") is not read-only
- [x] `bash ai/tests/run.sh` 0 failed
