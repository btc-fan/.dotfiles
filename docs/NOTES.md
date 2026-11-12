# Notes: decisions and why

These scripts come from the first build of the owner's home server (November 2026).
That build ran phase by phase. Each phase was checked on the machine and over reboots.
This branch turns it into one generic setup. Real values (IPs, serials, names) are not here.

## Reference machine

- Old desktop: Intel Ivy Bridge quad core (AVX yes, AVX2 no), 14 GB RAM, legacy BIOS boot
  (GPT, sda1 = bios_grub). BIOS and UEFI both work with this setup.
- 250 GB SSD: Ubuntu, Docker images, the shared projects folder.
- 500 GB HDD: main data disk (Postgres, Docker volumes, backups).
- 500 GB HDD: backup disk (nightly mirror of the backups).
- 320 GB HDD: spare.
- Ubuntu Server 26.04, no desktop. dracut initrd. Rust coreutils.

## Decisions

| Decision | Why |
|---|---|
| Plain bash scripts, one per step, run with sudo | Easy to read on the server, no extra tools to install first. Every step can run alone. |
| Idempotent: write a file only when its content changes | Run the setup again at any time. A second run changes nothing, so you can use it to check drift too. |
| One `host.env` per server, gitignored | The repo is public. Real IPs, serials and user names never go in git. |
| SSH keys only, no root, AllowUsers, MaxAuthTries 3 | The box is reachable from the LAN and Tailscale. Passwords are the usual way in for attackers. |
| ufw: SSH only from LAN and Tailscale | Nothing on this server needs to be on the internet. Tailscale gives remote access without open ports. |
| fail2ban with growing bans + recidive | One wrong-password burst gets 10 min. Repeat offenders get up to a week. LAN and Tailscale are never banned, so the owner is never locked out by it. |
| 10 min rollback timer when SSH or ufw changes | The first build used it. A wrong firewall rule over SSH is the classic lockout. |
| Security updates only, no automatic reboot | Updates without surprises. A reboot is the owner's choice. |
| Tailscale installed, login by hand | The login needs a browser. Plain Tailscale network; SSH keeps using keys (no Tailscale SSH). |
| Sleep targets masked, logind ignores keys and idle | A server must never sleep. Masking works even if a desktop gets installed later. |
| Power key = clean poweroff | A short press is the safe way to stop the box without SSH. |
| HDD spin-down off, by a systemd unit | Spin cycles wear disks and add latency. A udev rule failed: dracut copied it into the initrd. |
| Hardware watchdog (iTCO), softdog fallback | A hung kernel or systemd resets itself in 30 s. Nobody needs to press the button. |
| kernel.panic=10, panic_on_oops, softlockup_panic | A broken kernel reboots instead of hanging. |
| kdump | After a crash, a dump says why. The boot message uses it to report "crash". |
| fsck.repair=yes, GRUB recordfail timeout 5 s | After a power cut the boot never waits for a key press. |
| Wake-on-LAN | Manual fallback when the BIOS does not power on after a cut. |
| Persistent journal | Needed to tell power cut, crash and clean shutdown apart. |
| Disks by serial, mount by UUID, nofail + 90 s timeout, label must match | `/dev/sdX` names change. A dead disk must not stop the boot; a slow HDD after a power cut still mounts. A wrong disk never gets the mount point. |
| Format only empty disks, only with `--format` | The setup must never destroy data by mistake. |
| Postgres data on the data disk, localhost only, checksums on | Data off the small SSD. No network exposure (use an SSH tunnel). Checksums catch silent disk corruption. |
| Postgres and Docker require their mounts | They must never start on the SSD with an empty data folder. |
| Docker default bind 127.0.0.1 | Docker skips ufw. A published port must be exposed to the LAN on purpose. |
| Docker images on SSD, named volumes on the data disk | Images are big and easy to download again; volumes hold data. |
| Backups after 07:30 | The night hours belong to other heavy jobs on the reference machine. |
| pg-backup keeps 3 days, can skip big DBs | A big database can have its own backup job; the general dump stays small and fast. |
| Mirror to a second disk (`rsync -aH --delete`) | One disk can die. `-H` keeps the hard links of the work snapshots, so the mirror is not much bigger than the source. |
| Discord webhooks, two channels | alerts (notifications on) for problems, info (muted) for normal events. Webhook URLs are root-only files, never in git, never on a command line. |
| Every alert script is a no-op without its URL | The setup works on a server with no Discord at all. |
| Failure alerts for every service (top-level drop-in) | No list to keep up to date. The handler cancels the drop-in for itself, so it can never loop. |
| Alerts grouped per key | A flapping service or a script with many SSH logins does not flood the channel. |

## What changed compared with the scripts that ran on the server

- Steps renumbered: disks (30) now run before tools (40), because Postgres and Docker need the
  data disk mounted. Alerts moved to 50.
- All values come from `host.env` (the first build had them in each script).
- SSH settings, sysctl and fail2ban each live in one file now. Old file names from the first
  build are removed when found: `sshd_config.d/10-hardening.conf` and `60-hardening.conf`,
  `sysctl.d/60-hardening.conf` and `60-net-hardening.conf`, `fail2ban/jail.d/60-hardening.local`,
  `itco-watchdog.service`, and the `*.timer.d/10-schedule.conf` overrides of the backup timers.
- ufw: no `ufw --force reset` any more, so rules added by hand stay.
- Watchdog unit renamed `load-watchdog.service`, with a softdog fallback.
- Journal: `Storage=persistent` and `SystemMaxUse=1G` set explicitly.
- Postgres: no automatic restart of a running cluster; `random_page_cost` added; tuning from RAM.
- Backups: dumps are written to a temp folder and renamed when complete; retention keeps the
  newest N dated folders; the mirror uses `-H` and refuses an empty source.
- Alerts (step 50) are new. The server did not have them yet.
- The agents part of the first build (users, Claude Code, Codex, Hermes, house rules) is not
  here. Only the optional second user and shared folder (step 55) stayed.

## Tested here, and not tested

Written on a macOS machine without access to the server (that Mac is frozen for changes).

Tested:
- `bash -n` on every script (macOS bash 3.2). shellcheck was not installed, so it did not run.
- `discord-notify`: `--test` output, the silent no-op without a URL file, and the grouping
  (3 sends in a window: 1 posted, 2 held back; the next post says "+2 more").
- The fstab rewrite in 30-disks: an old `/data` line is commented and replaced; a second run
  changes nothing; a new disk is appended.
- The DISK-ROLES.md merge keeps notes outside the markers.
- The GRUB edit: adds `fsck.repair=yes` once, works with an empty value, does not add it twice.
  (These ran with macOS sed and awk; the server has GNU sed and mawk.)

Not tested (needs the Ubuntu server):
- Any full run of `setup.sh`, the `--dry-run` output, and the idempotency of a second full run.
- Every systemd, apt, ufw, fail2ban, smartd, PAM and Postgres command.
- The OnFailure drop-in for all services: `%n` (full unit name, for example
  `postgresql@16-main.service`) as the handler instance, used as is for `systemctl` and `journalctl -u`.
- `boot-notify` cause detection (needs real clean, crash and power-cut boots).
- A non-22 `SSH_PORT` with socket-activated SSH.

First run on the real server: use `--dry-run` and read the diff for each file.

## Added 2026-11-11: admin user and project hosting (owner decisions)

| Decision | Why |
|---|---|
| Separate `ADMIN_USER` (key only, passwordless sudo) | Admin work gets its own login. The daily user can lose root without the owner losing root. |
| Main user loses passwordless sudo and docker only with `--drop-main-sudo`, after a proven admin login | Never lock the owner out. The proof is a marker file the admin creates over SSH with `sudo -n`, so SSH and sudo both work before anything changes. The main user must also have a password. |
| Main user gets a `zz-` sudoers rule with `PASSWD:` instead of editing the cloud-init file | The last matching rule wins, `zz-` sorts last, and undo is one `rm`. |
| Every sudoers file is checked with `visudo -c` before it lands | A broken sudoers file takes sudo away from everybody. |
| One unprivileged Incus box per project, ZFS pool on its own disk | One-command wipe and recreate, instant snapshot and fork, hard limits, delete protection, agents root only inside their box. Design: hosting research, section 10. |
| Incus 6.0 LTS from the Ubuntu archive by default; Zabbly 7.0 LTS behind `INCUS_SOURCE=zabbly` | Owner decision: Ubuntu-signed, no extra repo. Pinned to `6.0.*`. Zabbly path: key fingerprint 4EFC5906...C838DCFD checked, apt pinned to that origin, no pipe to shell. 7.0 back to 6.0 is refused (the Incus database only moves forward). |
| `incus-admin` holds only the admin user | Full control of Incus is root on the host. Everybody else uses `sudo proj`. |
| ACL and both default actions set on the bridge AND on the box NIC | The docs give different defaults (network: reject, bridged NIC: drop) and the NIC wins. Explicit is safe. |
| Port isolation in box-base | It only works when every box NIC has it. |
| `proj selftest` in 90-verify | DHCP and DNS to the bridge are "baseline" rules before any ACL (implied by the docs, not stated). A throwaway box proves it on every verify. |
| Pool only on a disk where `smartctl -H` says PASSED, only with `--format`, never a disk in DISKS | The old 1 TB disk failed. The setup must never format a disk with data on it. Owner decision 2026-11-11: scripts never start a SMART test. |
| Data volumes deleted only by proj, with their box | Incus has no delete protection for custom volumes (checked in the docs). |
| ufw on incusbr0: only DHCP and DNS in; routing only new box connections out via `NIC` | The Incus how-to says `ufw allow in on incusbr0` (every host port). Narrower is enough. (Narrowed again in the 2026-11-11 fix round.) |
| Egress ACL rejects LAN, tailnet, Docker and link-local ranges, not 10.0.0.0/8 | The box bridge itself is 10.99.0.0/24. If your LAN is 10.x, add its range to `BOX_EGRESS_REJECT`. |
| Host projects (the crawler) are registered, protected, never boxed | The big database on /data gains nothing from a box. proj only lists and checks it. |
| No `proj expose`, `agent`, `grant`, `archive` yet | Kept the first version small. Exposure (Tailscale in the box) and a read-only DB grant come later. |

### Incus names checked against the current docs (2026-11-11)

Verified in linuxcontainers.org/incus/docs/main: `security.protection.delete` (instance),
`security.idmap.isolated`, `security.port_isolation` (bridged NIC), `snapshots.schedule` and
`snapshots.expiry` (instances AND custom ZFS volumes, `@daily`, `3d`), `limits.cpu`,
`limits.memory`, `limits.processes`, `security.nesting`, `security.syscalls.intercept.mknod`,
`security.syscalls.intercept.setxattr`, project `limits.memory` (needs `limits.memory` on every
instance; the tier profiles set it), the two `DOCKER-USER` iptables rules, the three ufw
commands, `incus network acl create` / `rule add` and `security.acls`,
`security.acls.default.egress.action` / `ingress.action` (default becomes reject once an ACL is
set, so both are set to allow), `incus export --instance-only --compression`,
`incus storage volume export --volume-only`, `incus storage create <pool> zfs source=<dev>`,
`incus storage volume attach <pool> <vol> <instance> <device> <path>`, the Zabbly key URL and
fingerprint, channels and 26.04 support, Ubuntu 26.04 = incus 6.0.5-8.

Not verified (test on the server): `security.port_isolation` together with `network=incusbr0`
(the docs list it for bridged NICs, and a `network=` bridge is bridged, but they do not say it
outright); that DHCP and DNS to the bridge stay allowed with the egress ACL (the docs only say
"baseline network service rules" come first; `proj selftest` checks it); root disk `size`
key (standard, not re-read); `incus copy <box>/<snapshot>` and
`incus storage volume copy <pool>/<vol>/<snapshot>` for forks; `incus export` of a running box;
the exact `zstd` compression name; that `images:ubuntu/26.04` exists on the image server.

### Tested here for these additions

- `bash -n` on `proj`, `box-bootstrap.sh`, `incus-docker-fix`, `70-hosting.sh` and the changed
  steps. Nothing that calls incus, zfs, visudo or sudo could run on this Mac.

## Fix round 2026-11-11 (security review + real dry run + owner decisions)

Done by the lead before this round: `getent passwd ... | cut -d: -f6 || true` in steps 10 and 55
(pipefail ended the dry run when the admin user did not exist yet).

- SSH safety timer: `setup.sh` stops before any step after 10 while `server-rollback.timer` is
  armed, prints the two `ssh` test commands, exit code 3. Legacy sshd files are removed only after
  `sshd -t` passes. When the rollback fires it writes to the journal, `wall` and the alerts webhook
  (`discord-notify` is now installed by step 10 too).
- Docker: refused while Ubuntu's `docker.io` is installed (preflight and step 40). `daemon.json`
  compared with `jq -S`, our keys merged in, other keys kept with a warning. Refused: `data-root`,
  or a merged file `dockerd --validate` rejects. Applied with `systemctl reload docker`; the file is
  written before the first install, so a fresh Docker starts with it.
- needrestart: `override_rc` 0 for postgresql, incus, docker (and containerd, added: restarting it
  under running containers is the same risk).
- 30-disks: mount source and label checked before fstab changes; label mismatch now refuses (was a
  warning). Device timeout 90 s, nofail kept.
- pg-backup: refuses when free space < 2x the largest database it dumps. Example
  `PG_BACKUP_SKIP_DBS="md999"`.
- Postgres: started and enabled only when this run created the cluster; an existing stopped
  cluster only gets a warning.
- setup.sh copies the repo (no `.git`) to `/opt/server-setup` (root:root, 755/644), refuses when
  that fails or `/opt` is not root-only, and re-runs from there. `/etc/server/host.env` root:root 644.
- 00-preflight always runs first, also with `--only`. SSH check reads `ss -tn state established
  '( sport = :SSH_PORT )'` (uses `SSH_PORT`, not a fixed 22); loopback is allowed.
- `BOX_MEMORY_BUDGET` default 4GiB; RAM budget table in HOSTING.md; no `nr_hugepages` in the base.
- KEEP values: preflight refuses < 1, scripts fall back to 1. Stale `.partial-*` removed by
  pg-backup and work-snapshot (work-snapshot now also uses a `.partial-` folder). backup-mirror
  skips `BACKUP_MIRROR_EXCLUDE` (default `md999-move`) and every `.partial-*`. proj backup exports
  to `.partial-*` files and renames only after `zstd -t` passes.
- fail2ban: `journalmatch` covers ssh.service, sshd.service, `sshd` and `sshd-session`; step 10
  warns and verify FAILs when the installed filter does not know `sshd-session`.
- Pins: `UV_VERSION="0.13.7"`, `LAZYDOCKER_VERSION="0.25.2"` (`latest` follows the newest). Apt keys
  checked against fixed primary fingerprints in `lib/common.sh` (exactly one primary key, else
  refused). The Tailscale source line is now written by setup, not downloaded.
- incus-docker-fix: no blanket `-i incusbr0 -j ACCEPT` (removed if found). DOCKER-USER accepts
  replies to boxes and RETURNs other box traffic to the ufw route rules. ufw: one rule
  `route allow in on incusbr0 out on NIC`; the old wide route rules are deleted when found.
- Owner decisions: smartd watches only (no `-s` schedule, no `-o on`); the 70 gate is
  `smartctl -H` PASSED. `AGENT_SUDO=none|full` (step 55, `90-<agent>` via `put_sudoers`, never
  removed by setup, accepted by verify). BIOS and UEFI both documented. `HOST_PROJECTS` example
  with `md999-crawler.service`. Channel names `#<host>-alerts`, `#<host>-info`, `#<host>-hermes`.
- Later the same day (owner): agents get NO sudo. `AGENT_SUDO="none"` now removes our managed
  `90-<agent>` file (this replaces "never removed" above); agents give the owner the
  `sudo proj new` command. `--drop-main-sudo` also takes the main user out of `lxd` and `adm`
  (least privilege), next to docker and incus-admin.

Choices made where the brief was open (safer option taken):
- "unknown keys" in daemon.json read as keys dockerd rejects; valid keys we do not manage are kept
  with a warning (the merge would mean nothing otherwise).
- `reload docker` does not apply `ip` or log settings; setup warns and leaves the restart to the
  owner instead of restarting a Docker with containers.
- smartd `-o on` (automatic offline scans) dropped together with `-s`: also a drive-side test.
- Box traffic in DOCKER-USER is RETURNed to ufw instead of a narrower ACCEPT, so ufw stays the one
  place that decides; ufw's own before.rules accept RELATED,ESTABLISHED.

Not tested (needs the server): the `/opt/server-setup` copy and re-exec; the stop after step 10;
`ss -H` output parsing; the jq merge on the real `daemon.json`; `systemctl reload docker`; the
fingerprint check on each real key file (it requires exactly one primary key per file); the exact
`ufw show added` text that the old-rule delete greps for; box network after the DOCKER-USER and
ufw change (`proj selftest` in verify covers it); fail2ban with `sshd-session` lines.
Tested here: `bash -n` on every script.

## Added 2026-11-11: proj-agent, the agents' one root command (owner decision)

Agents (MAIN_USER sessions, AGENT_USER) have no general sudo, but may create, list and snapshot
boxes, read logs and status, and restart services inside boxes, without a password.

| Decision | Why |
|---|---|
| One wrapper, `/usr/local/sbin/proj-agent`, is the only command in the sudoers line | sudoers argument matching is fragile; a script with strict regexes per argument is easier to read and test. |
| Every argument must match `[A-Za-z0-9@._-]`, then a per-field pattern (box names as proj) | No shell meta characters, spaces, slashes or newlines ever reach a command. Units start with a letter or digit, so no option injection. |
| Tier long, `--repo`, `--ttl`, `--owner`, labels, `doctor --net` refused | Long boxes are the owner's; a repo URL runs code; doctor `--net` makes a box. |
| `restart` only through `incus exec <box> -- systemctl restart`; host projects refused | Never a host unit. |
| PATH fixed in the script, `#!/bin/bash -p`, children via `env -i` with `SYSTEMD_PAGER=` and `PAGER=cat` | Does not depend on sudo's env handling (sudo-rs or not); a pager never opens. |
| File name `zzz-agents-proj` | The last matching rule wins; `zz-server-main-password` matches ALL, so ours must sort after it. |
| Installed and granted by step 70, not 55 | The binary and the rule land together, only when hosting is on; step 55 skips when `AGENT_USER` is empty but the main user needs the rule too. |
| `Defaults!/usr/local/sbin/proj-agent env_reset, secure_path=...`, dropped with a warning if visudo rejects it | macOS sudo 1.9 visudo parses it; sudo-rs support not checked. The wrapper is safe without it. |

Tested here: `tests/proj-agent.test.sh` (95 checks: every allowed form, refusals for long tier,
bad names, `;` `$()` backticks spaces newlines, host projects, unknown commands, `-n 99999`,
slashes; child environment; log lines; the `sudo -l` parser; sudoers.d order). `bash -n` on the
changed scripts. Not tested (needs the server): sudo-rs `visudo` and `sudo -l -U` output format,
the real proj/incus/journalctl calls.

## Later

- **UPS + NUT**: a small UPS and `nut` so the server shuts down cleanly before the battery is
  empty, and the boot message can say "power cut" for sure (today a hard hang looks the same).
- **Outside down-check**: a free external check (for example healthchecks.io with a cron ping)
  that alerts when the whole server or the home internet is down. Today all alerts come from the
  server itself, so a dead server says nothing.
- Alert when a service restarts in a loop but never ends "failed" (today only failed units alert).
- Off-site copy of the backups.
- proj: `expose` (Tailscale inside a box, per-box name), `grant pg-readonly` (a box reads a host
  database), `agent` (install and start an agent in a box), `archive`, and a bats test file run
  on the server.

## Added 2026-11-11: shared workspace for box projects (owner decision)

Agents run on the HOST (Claude Code and Codex as `MAIN_USER`, Hermes as `AGENT_USER`) and must
work on a project that lives in a box.

| What | Why |
|---|---|
| Code on the host in `WORK_ROOT/<box>` (default `/srv/proj/work`), disk device `app` at `/srv/app` | Host agents use their normal tools on the code; it runs only in the box. `recreate` re-attaches it, so code survives a rebuild. Data stays on the box volume. |
| `shift=true` (idmapped mount), not `raw.idmap` | Idmapped mounts work with `security.idmap.isolated`: the mount shows host uid N as box uid N, the box processes keep their own isolated range. `raw.idmap "both <uid> 1000"` would make `dev` the real main user on the host (a box escape gets that user) and needs extra `/etc/subuid` entries. Cost: `MAIN_USER` must be uid 1000; proj refuses otherwise. |
| Folder `MAIN_USER:SHARED_GROUP` 2775 + default ACL `g:SHARED_GROUP:rwx`; `dev` joins a group with the same gid in the box | All three (main user, Hermes, dev) can write each other's files. A default ACL also overrides every umask. |
| Root `root:SHARED_GROUP 750`, `.trash` root 700 | Only proj adds workspaces; agents can look but not make project folders on the host. |
| `wipe` keeps the workspace in `.trash` unless the owner types `delete`; `--yes` and `expire` always keep it | Code is never deleted silently. `.trash` is emptied by hand. |
| Workspace in the nightly backup of long boxes (`<date>-work.tar.zst`, tar exit 1 accepted) | `incus export` does not hold a host-path device. A changing file in a live box is not a failure. |
| `proj-agent exec` runs `incus exec ... -- setpriv --reuid=1000 --regid=1000 --init-groups -- timeout N bash -lc "<cmd>"` | `incus exec --user 1000 --group 1000` sets no supplementary groups (as far as we know from LXC attach), so `docker` and the shared group would be missing. setpriv drops to dev with dev's groups before bash starts: the command never runs as root. timeout runs as dev in the box; an outer timeout (N + 30 s) only catches a stuck incus. |
| exec allows any command after `--`; the words before `--` get strict patterns; log cut to 300 chars | The box is the isolation boundary (owner decision). The command never touches a host shell. |
| `url` prints box IP:port, `ports` runs `ss` in the box | Read only; nothing is exposed to the LAN. |
| `proj workspace <box>` for boxes made earlier | Copies the old `/srv/app` out as root: `--no-same-owner`, setuid bits removed, links not followed, then mounted over. |

Tested here: `tests/proj-agent.test.sh` (142 checks, new: exec, ports, url forms and refusals,
log cut and newline escape) and `tests/proj-workspace.test.sh` (34 checks: device add order in
`new`, folder mode and ACL calls, fork copy and device move, wipe keep/delete/default, recreate
re-attach, adopting an older box with a setuid file and a link). `bash -n` on every changed script.

Not verified (test on the server): `shift=true` on the host filesystem of `/srv/proj/work`
(`incus info | grep idmapped_mounts` must say true); POSIX ACLs through the idmapped mount;
setgid inheritance seen from the box; `setpriv --init-groups` in the 26.04 image; whether
`incus exec --user` really drops supplementary groups; that `incus copy` keeps the `app` device
for a fork; `tar --zstd` on 26.04; the host reaching a box IP through ufw.

## Fix round 2026-11-12 (second audit)

### Root runs only from a root-owned clone
- Before: admin ran `sudo ~MAIN_USER/.dotfiles/setup.sh`. `setup.sh` and `lib/common.sh` ran as
  root from that user-owned clone before the root-owned copy was made, and the copy took the
  working tree (uncommitted edits by an agent included).
- Now: `/opt/server-setup` is a git clone made by the admin (`sudo git clone`), root-owned.
  `host.env` lives in `/etc/server/host.env` (root:root 644), not in any clone. `--update` fetches
  the branch and fast-forwards only (refused on local commits or a rewritten history), prints the
  new commits, then runs the new code.
- `source_guard` (lib/common.sh) refuses as root when: `/etc/server/host.env` or a folder above it
  is not root-only; the clone, or any folder above it, belongs to someone other than root or
  `ADMIN_USER` or is writable by others; any file in it (`.git` too) belongs to another user, is a
  symlink, or is writable by others; `git status` is not clean. The message prints the right
  commands. Steps run alone (`sudo bash /opt/server-setup/steps/NN-x.sh`) run the same check.
- Limit: bash has read `setup.sh` before the check runs, so a hostile copy can drop the check.
  The guard stops mistakes; the protection is that the docs give the admin only commands that
  start from `/opt/server-setup`.
- The `ai` branch installer follows the same rule (`/opt/ai-setup`, `--update --for-user`).

### git guard: allow-list instead of deny-list
- The audit proved three bypasses of the old deny-list guard: `extensions.worktreeConfig` with a
  filter in `config.worktree` (ran a planted command on `git status`); `core.worktree` pointing
  outside (`git checkout -- .` overwrote a file outside); `--git-dir` from outside skipped the
  check. Four more keys passed the regex (`submodule.<n>.update`, `pager.<cmd>`,
  `interactive.diffFilter`, `trailer.<t>.command`).
- Now: the guard finds the real repository (`rev-parse` with the caller's `-C`, `--git-dir`,
  `--work-tree`, `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`; symlinks resolved) and checks
  every config file (`config`, `config.worktree`, `worktrees/*`, `modules/*`) against an
  allow-list. Plus `safe.bareRepository=explicit`, `protocol.ext.allow=never`, no submodule
  recursion, URL checks, `.git` file and alternates must stay in the workspace. Outside the
  workspaces with no folder named: plain git, no extra process (fast path).
- `tests/git-guard.test.sh`: 65 checks. Against the old guard 26 fail (3 payloads ran).
- Left open, said in HOSTING.md: a race between the check and git reading the config, and
  local-path remotes (needed for a local bare remote) can copy a host repository in on fetch.
  The full fix for the race is to freeze the config files for the git run (a private mount
  namespace, bubblewrap) or to run git for box projects only inside the box.

### Workspace mount is a hard dependency of Incus
- `incus.service` and `incus.socket` get a drop-in with `Requires=` and `After=` the
  `nosuid,nodev` bind mount of `WORK_ROOT`. When the mount fails, Incus does not start.
- Step 70 never restarts that mount (a restart would restart Incus and stop every box): wrong
  flags are fixed with `mount -o remount`. Setuid files there are only reported now: a root
  `chmod` could be sent through a symlink an agent swaps in, and on `nosuid` the bit does nothing.

### proj restore and workspace copy: no root chown in agent-writable folders
- Before: `ws_unsnap` and `ws_copy_out` extracted as root, then root ran `find ... -exec chown`
  and `chmod` over the workspace. Agents and box code can write there, so a link swapped in
  between find and chown could send a root chown or chmod to any file on the host.
- Now: root only opens the archive (or the box tar stream); MAIN_USER extracts it (`runuser`,
  `as_main`), so the files are MAIN_USER's from the start and the setgid folder gives the group.
  The mode fixes (`ws_fix_modes`: no setuid bits, group write, setgid folders) also run as
  MAIN_USER with `find -P`. A test refuses any root `find -exec chown/chmod` left in proj.

### Backups with history, md999 included, monthly restore drill
- Before: one dump folder a day on `/data` (same disk as Postgres), 3 days kept, mirrored with
  `rsync --delete` (so the backup disk had no history), and md999 (in `PG_BACKUP_SKIP_DBS`) had
  no backup at all.
- Now: `pg-backup` writes straight to the backup disk (`BACKUP_MOUNT/postgres`), 7 daily + 4
  weekly (weekly = hard links of the first good dump of the ISO week). `pg-backup --big`
  (own timer, 04:30) dumps each `PG_BACKUP_SKIP_DBS` database on its own, same history; a
  database that does not exist yet is noted (`.not-there-yet`), not an error. Every dump is a
  `.partial-*` until `pg_restore -l` reads it back. zstd compression (Postgres 16+).
- Choice: `pg_dump -Fc`, not `pg_basebackup`. A dump restores one database into a throwaway
  database (the drill), crosses Postgres versions and leaves indexes out. A base backup is the
  whole cluster and needs WAL archiving to give more than a nightly copy. If md999 later needs
  point-in-time recovery, add WAL archiving plus a weekly base backup then.
- `pg-restore-drill` (day 1 of the month): newest dump of each database into
  `restore_drill_<db>`, table count compared with the dump's table of contents, dropped, one
  Discord message. Needs 1.3x the database size free on the data disk, else it reports a failure.
- Old dumps in `BACKUP_DIR/postgres` (the 3-day layout) are not touched; delete them by hand when
  the new ones are there. `PG_BACKUP_KEEP_DAYS` is replaced by `PG_BACKUP_KEEP_DAILY`.
- Tests: `tests/pg-backup.test.sh` (Linux, fakes): 50 simulated days, failed dump, drill.

### Alerts: digest, ZFS, SMART changes, inodes, reboot needed
- Owner choice: a daily digest (`server-digest`, `DIGEST_TIME`) instead of an outside heartbeat
  service. A missing digest is the alarm. It lists uptime and last stop, failed units, disk and
  inode use, ZFS, backup age per database (and alerts above `BACKUP_MAX_AGE_H`), reboot needed
  (also once per new kernel to #info), boxes with expiry, Postgres, `DIGEST_UNITS`, workspace size.
- zed: `ZED_EMAIL_PROG=zed-discord` (the URL stays in `/etc/server/webhooks`; zed.rc is
  world-readable, so the Slack-style webhook setting was not used).
- `disk-usage-check`: ZFS datasets, inodes (ext4, xfs), pool capacity (80 %) and health,
  workspace size (`WORK_ROOT_ALERT_GB`, du at most once an hour).
- `smart-digest` weekly: `smartctl -n standby -i -H -A` only, attributes 5, 187, 188, 197, 198,
  199 compared with last week by serial. Never a self-test (verify checks the script for `-t`).
- verify and `proj doctor` FAIL on any failed systemd unit.

### Boot network wait
- Measured on the server: after the power-cut test (2026-11-11) the NIC got link at 235 s (the
  router came back after the server). `systemd-networkd-wait-online` (netplan:
  `--any --dns -o routable -i <nic>`) waited its 2 min, failed, and stayed failed.
- Fix: drop-in `50-server.conf`, `-i NIC:routable --timeout=WAIT_ONLINE_TIMEOUT` (30) with a
  `-` prefix, so a slow router never fails the boot. boot-notify now waits up to 15 min for DNS
  and says how late the network came.

### Small
- `BOX_EGRESS_REJECT` default has `10.0.0.0/8`. Incus applies reject before allow, so the box
  network is cut out of any reject range that holds it (computed in step 70); DHCP and DNS to the
  bridge are baseline rules and stay. Existing host.env files keep their own list: add it there.
- ZFS `atime=off` on the boxes pool. logrotate for `/var/log/proj.log` and `proj-agent.log`
  (weekly, 12). Workspace size alert (above).

### server-info and the login message (owner request)
- `/usr/local/bin/server-info`: any user, no sudo, read only, under 2 s (agent CLI versions run in
  parallel, each cut at 1.5 s). host.env is read as text for a few plain values only; nothing
  with an address, URL or secret is printed (the test plants some and checks). Backup ages come
  from small status files pg-backup writes to `/var/lib/server-info/pg-<db>` (644), because the
  dump folders are root-only. Boxes: `sudo -n proj-agent list` when allowed, else REGISTRY.json.
- Login: `/etc/update-motd.d/60-server-info` (short form, 3 s cap). Off: 10-help-text,
  50-motd-news (also `ENABLED=0`), 50-landscape-sysinfo (slow, prints IPs), 91-contract-ua-esm-status.
  A package upgrade may turn one back on; the next step 40 run and verify catch it.
- AGENTS-hosting.md: "Run `server-info` first when unsure what this machine offers."
- `ai-info --short`: update-motd runs as root, so the user's AI facts come from
  `/etc/profile.d/zz-ai-info.sh` (as the user, once per SSH session, not in tmux, 2 s cap; it
  also looks in `~/.local/bin`, which is not on PATH yet when profile.d runs). `server-info
  --short` run by hand adds it too; the full form appends plain `ai-info`.
