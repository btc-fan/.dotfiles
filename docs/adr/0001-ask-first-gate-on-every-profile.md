# The ask-first gate runs on every profile, with a typed OK per plan

All machines run the `dev-mac` profile, which turns off the Claude ask and deny guards. A rule text alone already failed once: on 2026-11-20 an agent on a server enabled a systemd unit and started a service without an OK. So we added a router gate `ask-first` with no profile limit. It asks before a high-impact step, and the owner's typed OK covers one plan only.

We rejected three other options. A server profile for the servers: the owner keeps one profile. Claude `permissions.ask` lists: they ask for `systemctl status` too, and they miss `bash -s` scripts. Claude auto mode: it works only for Claude, and it denies instead of asking. Research: `docs/research/agent-risk-confirmation.md`.
