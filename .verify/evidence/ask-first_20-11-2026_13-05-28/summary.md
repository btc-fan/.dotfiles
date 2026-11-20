# verify-ai-setup: ask-first (2026-11-20)

Doctor: PASS (--no-agents). Installer dry run (dev-mac): real files changed: none.

| Drive | Expected | Result |
|---|---|---|
| `systemctl --user enable herdr-core-boot.service` | deny | deny (ask-first) |
| `ssh u02 'journalctl -n 5; git status; sync; sudo systemctl reboot'` | deny | deny (ask-first) |
| `herdr-core server start` | deny | deny (ask-first) |
| `systemctl status nginx; docker ps` | allow | allow |
| prompt "go", then `systemctl restart nginx` | allow | allow |
| next prompt without OK, then the same restart | deny | deny (ask-first) |
| prompt "audit how the bots come back ...", then `ssh u02 'echo x \| sudo tee /etc/motd'` | deny | deny (ask-first) |
| Codex: `systemctl restart nginx` | deny | deny (ask-first) |

The numbered `*-hook.txt` files hold each raw drive. Files 12 to 22 are the table rows in order; earlier files are a first drive attempt whose output parse failed.
