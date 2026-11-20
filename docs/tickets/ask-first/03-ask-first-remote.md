# 03: ask-first gate over ssh

**What to build:** the gate reads what an ssh command runs on the other host: every stage of the remote text, a local script piped into `bash -s`, and a heredoc body. A high-impact stage anywhere in the chain stops the whole command. Package changes and writes to system paths stop on a live host (`~/.config/ai/live-hosts`; no file: every host). An unreadable script on a live host stops.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Deny: `ssh h 'journalctl -n 5; git status; sync; sudo systemctl reboot'` (hidden at the end)
- [ ] Deny: `ssh h 'sudo bash -s' < script.sh` with `userdel -r` in the script; the heredoc form too
- [ ] Deny: `ssh h 'sudo apt-get -y full-upgrade'` when h is live
- [ ] Pass: `ssh h 'uptime; systemctl is-active x; journalctl -n 20'`
- [ ] `bash ai/tests/run.sh` 0 failed
