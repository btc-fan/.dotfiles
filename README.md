# ubuntu-server: default setup for a home Ubuntu server

This branch builds a new Ubuntu server with a few commands.
You put the values of your machine in one file (`host.env`).
Then `setup.sh` does the rest: security, 24/7 power settings, disks, tools, alerts, backups,
and (optional) project hosting: one isolated box per project.

You can run it again at any time. A second run changes nothing.
To change the server, change `/etc/server/host.env` (or push new scripts) and run it again.

AI agents are not on this branch. They are on the `ai` branch (see the end).

## Contents

- [What you need](#what-you-need)
- [New server: the commands](#new-server-the-commands)
- [What each step does, and why](#what-each-step-does-and-why)
- [Admin user and main user](#admin-user-and-main-user)
- [BIOS checklist](#bios-checklist)
- [Your manual steps](#your-manual-steps)
- [Power cut: what happens](#power-cut-what-happens)
- [Check the server](#check-the-server)
- [Update](#update)
- [Troubleshooting](#troubleshooting)
- [Quirks we learned](#quirks-we-learned)
- [Files](#files)
- [AI setup](#ai-setup)

Other docs: [docs/HOSTING.md](docs/HOSTING.md) (rules for project boxes),
[docs/AGENTS-hosting.md](docs/AGENTS-hosting.md) (rules for agents, imported by the `ai` branch),
[docs/NOTES.md](docs/NOTES.md) (decisions and why).

## What you need

- A x86_64 PC with wired Ethernet. An old desktop is fine.
- Ubuntu Server 26.04 (24.04 should work, but only 26.04 is tested).
- One SSD for the system. One or more HDDs for data and backups.
- UEFI or legacy BIOS boot: both work (the reference server boots legacy BIOS, with a
  `bios_grub` partition on the system disk).
- Your SSH public key on the server, for your user (`ssh-copy-id`).
  The setup turns password login off. Without a key you are locked out.
  The preflight step checks this and stops if there is no key.

The reference machine: Intel Ivy Bridge (AVX, no AVX2), 14 GB RAM, 250 GB SSD,
two 500 GB HDDs (data + backup), one spare HDD. See [docs/NOTES.md](docs/NOTES.md).

## New server: the commands

Log in over SSH as the admin user (or, on a brand new server, as the user the installer made),
then:

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone -b ubuntu-server https://github.com/btc-fan/.dotfiles.git /opt/server-setup
sudo install -D -m 644 /opt/server-setup/host.env.example /etc/server/host.env
sudo nano /etc/server/host.env                    # put the values of THIS server
sudo /opt/server-setup/setup.sh --dry-run         # look first: shows what would change, writes nothing
sudo /opt/server-setup/setup.sh                   # do it
```

To find the values for `host.env`:

| Value | Command |
|---|---|
| `NIC` (network interface) | `ip -br link` |
| `LAN_CIDR` (home network) | `ip -br addr` (for `192.168.1.23/24` write `192.168.1.0/24`) |
| Disk serials for `DISKS` | `lsblk -d -o NAME,SIZE,MODEL,SERIAL` |
| `TIMEZONE` | `timedatectl list-timezones` |

**Where root runs from (security).** Root runs setup only from `/opt/server-setup`: a git clone
that root owns, made by the admin with `sudo git clone`. `host.env` lives in
`/etc/server/host.env` (root:root 644), never in a clone. Never run `sudo` on a script in the main
user's home (`~<main user>/.dotfiles`): that user, or an agent running as that user, can change
it, and then it would run as root. `setup.sh` refuses to start (and prints the right commands)
when its folder, or any folder above it, or any file in it belongs to another user than root or
the admin, when there is a symlink in it, or when `git status` is not clean. The main user's
clone is for reading and for pushing changes to GitHub; the server takes them only through
`sudo /opt/server-setup/setup.sh --update` (fetch, fast-forward only, then run).

**The first run stops after step 10.** When SSH or the firewall changed, step 10 arms a 10 minute
safety timer, and `setup.sh` stops there and prints two `ssh` test commands (main user and admin).

1. Open a NEW terminal on your computer and run both. Both must print OK.
2. Then: `sudo systemctl stop server-rollback.timer`.
3. Run `sudo /opt/server-setup/setup.sh` again: it does the remaining steps.

If you do nothing, after 10 minutes the firewall turns off, the new SSH settings go away, and an
alert goes to the alerts channel (and the journal: `journalctl -t server-rollback`).
This saves you when a mistake locks you out. No step after 10 runs while the timer is armed.

When `setup.sh` ends:

1. Test the admin login (see [Admin user and main user](#admin-user-and-main-user)).
2. Log out and in again (new groups: docker).
3. Reboot once: `sudo reboot`. Kernel options (fsck repair, crash kernel) need it.
4. Run the check: `sudo /opt/server-setup/setup.sh --only verify`.
5. Do [your manual steps](#your-manual-steps).

Options (`S=/opt/server-setup/setup.sh`):

```bash
sudo $S --update                       # fetch the pushed branch (fast-forward only), then run it
sudo $S --update --only hosting        # same, one step
sudo $S --list                         # list the steps
sudo $S --only security                # one step (number or name: 10, security, 10-security)
sudo $S --only 50 --only 60            # some steps
sudo $S --dry-run                      # show changes, write nothing
sudo $S --only disks --format          # also format disks that are completely EMPTY
sudo $S --only security --drop-main-sudo   # main user: out of sudo (after the admin test)
```

`--update` with `--dry-run` still moves the clone to the pushed commit, then shows what that
commit would change. It refuses when the clone has local commits or the remote history was
rewritten (a force push): look at the new commits first.
`00-preflight` (read only) always runs first, also with `--only`.
Each step is also a normal script, run from the root-owned copy: `sudo bash /opt/server-setup/steps/20-always-on.sh`.
The log of every run is in `/var/log/server-setup.log`.

## What each step does, and why

### 00-preflight (read only, always runs first)

Checks the machine before anything changes. It stops (and changes nothing) when:

- it is not Ubuntu 24.04 or newer, or not x86_64;
- `NIC` does not exist, or its address is not in `LAN_CIDR`;
- there is no default route or no DNS;
- an open SSH connection comes from outside the LAN and Tailscale (the firewall would cut it).
  It reads every connection with `ss`, not only logins listed by `who`;
- `MAIN_USER` has no SSH key;
- a disk in `DISKS` is the system disk;
- Ubuntu's `docker.io` package is installed (it conflicts with Docker CE);
- a value in `host.env` is wrong (time zone, times, port, a KEEP value below 1, `AGENT_SUDO`, `AGENT_SUDO_ALLOW`).

It also prints the CPU, RAM and disks, and warns when the CPU has no AVX2 (see [Quirks](#quirks-we-learned)).

### 10-security

- **Admin user** `ADMIN_USER` (default `admin`): SSH key only, passwordless sudo. On the first
  run it gets a copy of `MAIN_USER`'s `authorized_keys`. See [Admin user and main user](#admin-user-and-main-user).
- **SSH**: keys only, no root login, only `MAIN_USER`, `ADMIN_USER` (and `SSH_EXTRA_USERS`) may log in,
  3 tries per connection, no X11 or agent forwarding, idle connections closed after 10 min.
  Port forwarding stays on: you use it for SSH tunnels (for example to Postgres).
  One file: `/etc/ssh/sshd_config.d/10-server.conf`.
  Why `10-`: sshd keeps the first value it reads, and `10-` comes before `50-cloud-init.conf`.
- **Firewall (ufw)**: deny all incoming. Allow SSH from `LAN_CIDR` and from Tailscale only.
  `LAN_PORTS` opens more ports to the LAN only. Rules you add by hand stay.
- **fail2ban**: bans an address after 5 failed logins in 10 min. The ban starts at 10 min and
  doubles each time, up to 1 week. `recidive`: banned 3 times in 1 day means 1 week on all ports.
  Your LAN and Tailscale are never banned. It also reads `sshd-session` (OpenSSH 10 logs failed
  logins under that name).
- **Updates**: unattended-upgrades installs security updates every day. It never reboots.
  needrestart restarts services after a library update, except PostgreSQL, Incus, Docker and
  containerd: those you restart yourself, when it suits.
- **Apt keys**: every repo signing key (Docker, PGDG, NodeSource, GitHub CLI, Tailscale, Zabbly)
  is checked against a fixed fingerprint in `lib/common.sh`. A different key is refused.
- **sysctl**: standard network hardening (no redirects, no source routing, SYN cookies, rp_filter).
  IP forwarding stays on, because Docker needs it.
- **Hostname and time zone** from `host.env`.
- **Tailscale**: installed only. You log in by hand (see manual steps).

Safety: when SSH or the firewall changes, a 10 min timer is armed first (`server-rollback.timer`).
If you are locked out, wait 10 min and it undoes both, and says so in the alerts channel.
`setup.sh` stops after this step while the timer is armed. Stop it after a good new login.
Old SSH files from the first build are removed only after `sshd -t` accepts the new file.

### 20-always-on

The server must run 24/7 and come back by itself.

- **No sleep**: sleep, suspend and hibernate targets are masked. logind ignores the lid, the
  suspend key and idle. The power key does a clean poweroff.
- **Persistent journal** (max 1 GB): needed to tell later why the server stopped.
- **HDD spin-down off** on every rotating disk (`hdd-no-spindown.service`, runs `hdparm -S 0`).
  Spin-up and spin-down cycles wear the disks, and a sleeping disk makes Postgres slow.
- **caffeinate**: `/usr/local/bin/caffeinate` works like on macOS (`caffeinate -i cmd`).
- **Watchdog**: loads the Intel `iTCO_wdt` hardware watchdog (or `softdog` when there is none).
  systemd pings it every few seconds. No ping for 30 s (kernel or systemd hung) = hard reset.
- **Reboot on panic**: 10 s after a kernel panic, oops or soft lockup.
- **kdump**: after a kernel crash, a small second kernel saves a dump to `/var/crash`, then reboots.
- **GRUB**: `fsck.repair=yes` (after a power cut, fsck repairs the disk and does not wait for a
  key press) and `GRUB_RECORDFAIL_TIMEOUT=5` (after a failed boot, the menu waits 5 s, not forever).
- **Wake-on-LAN** on `NIC`: a way to start the box from another computer.

### 30-disks

Disks are found by **serial number**, not by `/dev/sdX` (those names change).
For each line in `DISKS` (`SERIAL|LABEL|MOUNT|ROLE`):

- disk not connected: warning, skip. The server boots without it.
- disk with one partition (or one with the right label): mounted at `MOUNT` by UUID.
- disk completely empty (no partitions, no signatures): formatted (GPT, ext4, the label) ONLY when
  you pass `--format`. Without it you get a warning.
- disk with data but no partition table, or more than one partition and none with the label:
  the step stops. Fix it by hand. It never wipes data.
- before fstab is touched: the filesystem label must be `LABEL`, and if something is already
  mounted on `MOUNT` it must be this filesystem. Otherwise the step stops (a swapped disk never
  gets the mount point). It prints the rename command when the disk is the right one.

fstab lines use `nofail` and `x-systemd.device-timeout=90s`: a dead disk never stops the boot,
and a slow HDD after a power cut still gets 90 s to spin up.
Old lines for the same mount point are kept as comments. A copy of fstab is saved first.

It writes `DISK-ROLES.md` on the data disk: which disk is which (model, size, serial, role,
SMART health). Only the part between the `setup:begin` and `setup:end` markers is generated.
Your own notes in that file stay.

### 40-tools

- Base: git, curl, jq, tmux, htop, btop, build-essential, ripgrep, fd, bat, fzf, lazygit, ncdu,
  iotop, glances (TUI only, its web daemon is off), rsync, unzip, gh (GitHub CLI).
- `fd` and `bat` get their usual names (Ubuntu calls them `fdfind` and `batcat`).
- Fix for macOS terminals: they send `LC_CTYPE=UTF-8`, which Linux does not know.
- **Docker CE + Compose** from Docker's own repo (refused while Ubuntu's `docker.io` is installed).
  `/etc/docker/daemon.json` is compared by meaning (`jq -S`), our keys are merged into it and
  other keys stay. Refused: a `data-root`, or a merged file `dockerd --validate` rejects. A change
  is applied with `systemctl reload docker`, never a restart; `ip` and log settings then apply at
  the next Docker restart (it tells you). Our keys:
  - `"ip": "127.0.0.1"`: a published port listens on localhost only, unless you write an
    address on purpose (`0.0.0.0:8080:8080`). Why: Docker writes its own firewall rules and
    skips ufw. Without this, every `ports:` line is open to the LAN.
  - log limit 10 MB x 3 files per container (`local` driver).
  - `live-restore`: containers keep running when Docker restarts.
  - Images stay on the SSD. Named volumes live on the data disk (bind mount
    `DATA_MOUNT/docker-volumes` on `/var/lib/docker/volumes`).
  - `MAIN_USER` joins the `docker` group.
- **uv** and **lazydocker** from GitHub releases, pinned (`UV_VERSION`, `LAZYDOCKER_VERSION`),
  checked against their sha256.
- **Node.js LTS** from NodeSource.
- **PostgreSQL** (`PG_VERSION`) from the PGDG repo:
  - data in `DATA_MOUNT/postgresql`, data checksums on;
  - listens on localhost only (use an SSH tunnel from another machine);
  - never starts without its disk (`RequiresMountsFor`);
  - memory tuned from RAM size, disk settings from `PG_DISK` (hdd or ssd);
  - `MAIN_USER` is a Postgres superuser (peer login: `psql postgres`).
  - A running database is never restarted by setup. If memory settings change, it tells you.
  - Setup starts (and enables) the cluster only when this run created it. A cluster that already
    exists and is stopped stays stopped (a move or restore may be going on): it only warns.

### 50-alerts

Messages go to two Discord channels through webhooks (channel names: `#<host>-alerts`,
`#<host>-info`; the agent on the `ai` branch uses `#<host>-hermes`):

| Channel | File | What |
|---|---|---|
| `#<host>-alerts` (notifications on) | `/etc/server/webhooks/alerts.url` | a service failed, a disk has SMART problems, a disk is more than 85 % full, the SSH safety rollback fired |
| `#<host>-info` (muted) | `/etc/server/webhooks/info.url` | server started (with the cause of the last stop), every SSH login |

No URL file = no message. Everything works without Discord.

| Piece | How |
|---|---|
| Failed service | Every service gets `OnFailure=notify-failure@...`. The message has the last 20 log lines. The same service alerts at most once every `ALERT_REPEAT_MIN` minutes; the next message says how many were held back. |
| SMART | smartd watches every disk and calls `smartd-notify`. It never starts a self-test: SMART tests run only by hand (a test stresses a weak disk). |
| Disk full | `disk-usage-check.timer` every 30 min. One message per disk per day. |
| Boot | `boot-notify.service` once per boot: "clean reboot", "clean shutdown", "crash" (kdump dump or panic in the log) or "power cut". Also how long it was down. |
| SSH login | PAM (`pam_exec`, optional): user and address. It never blocks or slows a login. |

Test each piece without posting anything:

```bash
sudo boot-notify --test
sudo disk-usage-check --test
sudo smartd-notify --test
sudo notify-failure --test ssh
sudo ssh-login-notify --test
sudo discord-notify --test alerts "title" "text"
```

Send one real message (after you set a webhook): `sudo discord-notify info "hello" "it works"`.

### 55-shared-users (optional)

Skipped unless `AGENT_USER` is set. It makes a second user with no docker (for an AI agent, for
example), a shared group, and a shared folder `WORK_DIR` (setgid + ACL: every new file stays
group-writable). The agents themselves are installed from the `ai` branch.

`AGENT_SUDO` (default `none`, owner decision 2026-11-11: agents get no sudo). `none` removes the
`/etc/sudoers.d/90-<agent>` file this setup wrote (a hand-written one is left, with a warning).
`full` writes that file (passwordless sudo, checked with `visudo -c`).
**Risk of `full`:** the agent is root on the host: anything it runs, or anything that tricks it
(a web page, a file, a prompt), can read, change or delete everything on the server.

### 60-backups

All times come from `host.env`. Defaults are after 07:30, when nothing heavy runs.

| Job | Default | What | Keeps |
|---|---|---|---|
| `pg-backup` | 07:30 | `pg_dump` of every database except `PG_BACKUP_SKIP_DBS`, plus roles, to `BACKUP_DIR/postgres/<date>` | 3 days |
| `work-snapshot` | 07:45 | copy of `WORK_DIR` to `BACKUP_DIR/work/<date>`. Unchanged files are hard links, so a day costs only what changed | 14 days |
| `backup-mirror` | 08:30 | copy of `BACKUP_DIR` to the backup disk `BACKUP_MOUNT/data-backups`, except `BACKUP_MIRROR_EXCLUDE` (default `md999-move`) | same as source |

A dump or snapshot is made in a `.partial-*` folder and gets its date name only when complete;
half-done `.partial-*` folders from a killed run are deleted on the next run and never mirrored.
`pg-backup` refuses to start when the free space is less than 2x the largest database it would
dump. KEEP values below 1 are refused (0 would delete every backup). The mirror refuses to run
when the source is empty or a disk is not mounted (so it never wipes the copy). A failed job
sends an alert.

Restore one database: `pg_restore -d NAME --clean BACKUP_DIR/postgres/<date>/NAME.dump`.

### 70-hosting (optional)

Skipped unless `BOX_DISK_SERIAL` is set. Every project gets its own **box**: an unprivileged
Incus system container. Wipe = one command, nothing left behind. Snapshot and fork are instant.
Agents can be root inside their box without any power over the host or the other boxes.
Rules for people: [docs/HOSTING.md](docs/HOSTING.md). Rules for agents: [docs/AGENTS-hosting.md](docs/AGENTS-hosting.md).

- **Incus 6.0 LTS from the Ubuntu archive** (6.0.5 on 26.04, Ubuntu-signed, no extra repo),
  pinned to the 6.0 series. `INCUS_SOURCE=zabbly` switches to Incus 7.0 LTS from the Zabbly repo
  (made by the Incus maintainers, LTS to 2031): its key fingerprint is checked and apt is pinned
  to it. There is no way back from 7.0 to 6.0; the step refuses that.
- **ZFS pool `boxes` on its own whole disk.** Made once, and only when: the disk is not the
  system disk, not in `DISKS`, not mounted, completely empty, `smartctl -H` says PASSED (no test
  is started by the setup), and you pass `--format`. With `--format`, a box disk that is still
  mounted with an empty filesystem (only `lost+found`) is released first: unmounted, its fstab line
  commented out, signatures wiped. A non-empty one is refused. ZFS cache capped (`ZFS_ARC_MAX_MB`)
  to leave RAM for Postgres.
- **Profiles**: `box-base` (isolated ID range per box, port isolation, process limit),
  `tier-try` / `tier-mvp` / `tier-long` (CPU, RAM, disk, nightly snapshots), `docker`
  (Docker inside a box: nesting, never privileged). Files in `files/incus/`.
- **Network**: bridge `incusbr0` (`BOX_SUBNET`, NAT, no IPv6). ACL `box-egress`: boxes reach the
  internet but not `BOX_EGRESS_REJECT` (home network, tailnet, Docker networks). The ACL and its
  default actions are set on the bridge AND on every box NIC (the defaults differ, so they are
  never left to chance). ufw lets boxes use only DHCP and DNS on the host (narrower than the
  Incus how-to, which opens every host port to the bridge), and routes new box connections only
  out through `NIC` (the internet). Nothing new is routed into a box; replies come back through
  ufw's RELATED,ESTABLISHED rule.
- **Selftest**: `sudo proj selftest` (also run by 90-verify) launches a throwaway box and proves
  it gets an address, resolves DNS, reaches the internet and cannot reach your home gateway.
- **Host Docker fix**: Docker sets the FORWARD policy to DROP and puts `DOCKER-USER` first.
  `incus-docker-fix.service` (after every Docker start) accepts only replies to boxes there and
  hands all other box traffic on (`RETURN`) to the ufw route rules above. No blanket ACCEPT.
- **Memory budget**: all box caps together may not pass `BOX_MEMORY_BUDGET` (default 4 GiB,
  Incus enforces it). The full RAM budget is in [docs/HOSTING.md](docs/HOSTING.md).
- **`proj`**: the one tool for boxes: `new`, `list`, `shell`, `snapshot`, `restore`, `fork`,
  `wipe`, `recreate`, `workspace`, `protect` / `unprotect`, `promote`, `extend`, `backup`,
  `expire`, `registry`, `sync-rules`, `doctor`, `selftest`. Long boxes are delete-protected. Host
  projects (`HOST_PROJECTS`, for example the md999 crawler) are listed and checked and never touched.
- **Workspaces** (owner decision 2026-11-11): the code of each box lives on the host in
  `WORK_ROOT/<box>` (default `/srv/proj/work/<box>`) and is mounted in the box at `/srv/app`
  (Incus disk device `app`, `shift=true`: an idmapped mount, so `MAIN_USER` (uid 1000) is `dev` in
  the box). Agents on the host edit the code there with their normal tools and run it in the box
  with `sudo proj-agent exec <box> -- <cmd>`. Folder `MAIN_USER:SHARED_GROUP`, mode 2775, default
  ACL `g:SHARED_GROUP:rwx`, so the main user, `AGENT_USER` and `dev` can all write. `recreate`
  keeps it, `fork` copies it, `wipe` moves it to `WORK_ROOT/.trash` unless you type `delete`,
  long boxes get it in the nightly backup. Data stays on the box volume (`/srv/data`).
  Step 70 makes the root (`root:SHARED_GROUP 750`), `.trash` (root 700) and the git
  `safe.directory` entry. Needs `MAIN_USER` = uid 1000 (proj refuses otherwise).
- **Where am I, and the rules, for agents**: `/etc/proj-host` on the host (step 70) and
  `/etc/proj-box` in every box (name, tier, owner, created; written by `proj new`, `recreate`,
  `fork`, `promote`). `proj new` and `recreate` also copy the house rules
  (`~MAIN_USER/.dotfiles-ai/ai/AGENTS.md`, read as that user) plus `docs/AGENTS-hosting.md` into
  the box as `/etc/proj-rules/AGENTS.md`, linked from dev's `~/.config/ai/AGENTS.md`.
  `sudo proj sync-rules <box>|--all` refreshes them. No host credentials (`~/.claude`,
  `~/.codex`) ever go into a box.
- **Timers**: `proj-backup` exports long boxes to `BACKUP_DIR/boxes` (then the mirror copies
  them to the backup disk); `proj-expire` warns, stops and deletes expired try boxes.
- Group `incus-admin` (full control of Incus, so root on the host) holds only `ADMIN_USER`.
  Anybody else in it gets a warning. Group `incus` (per-user socket) is not used.
- **`proj-agent`** (`AGENT_SUDO_ALLOW`, default `proj-agent`, owner decision 2026-11-11): the one
  root command agents may run, without a password. `MAIN_USER` and `AGENT_USER` (those that
  exist) get `/etc/sudoers.d/zzz-agents-proj`: `NOPASSWD: /usr/local/sbin/proj-agent`, nothing
  else. proj-agent allows only: `new <name> --tier try|mvp [--docker] [--pg]`, `list`,
  `snapshot <box>`, `doctor`, `logs <unit>|box <box> [-n N]`, `status <unit>`,
  `restart <box> <service>` (inside the box), `exec <box> [--cwd DIR] [--timeout S] -- <cmd>`
  (any command INSIDE the box as `dev`, never as root, default 600 s, at most 3600 s),
  `ports <box>` and `url <box> [port]` (how to reach a box service from the host; nothing is
  opened to the LAN). Every argument before `--` is checked with a strict pattern,
  host projects are refused, children run with a clean environment and no pager, every call is
  logged to `/var/log/proj-agent.log`. The file name sorts after `zz-server-main-password`
  because sudo uses the last matching rule: that keeps the main user's password for everything
  else. `AGENT_SUDO_ALLOW=""` removes the file.

### 90-verify

Prints PASS / FAIL / INFO for every item above. Exit code 1 when something FAILs.
It only reads, with one exception: with hosting on, `proj selftest` makes and deletes one
throwaway box (about a minute). For `proj-agent` it checks: root:root 755, the sudoers file is
valid and sorts last, and `sudo -n -l -U <user>` leaves proj-agent as the only passwordless
command for the agents (the main user only after `--drop-main-sudo`; before that: INFO).

## Admin user and main user

Two logins, two jobs:

| User | For | sudo | docker group |
|---|---|---|---|
| `ADMIN_USER` (default `admin`) | server admin: setup, `proj`, updates | yes, no password | no (it has sudo) |
| `MAIN_USER` (your daily login) | daily work, SSH tunnels, attended agent sessions | after `--drop-main-sudo`: with password (only `proj-agent` stays passwordless) | after `--drop-main-sudo`: no (also out of `incus-admin`, `lxd`, `adm`) |

Why: an agent or a script running as your daily user has root today (passwordless sudo, and the
docker, incus-admin and lxd groups are all root). After the change, root needs your password or
the admin login. `adm` (read every system log) goes too: least privilege.

Step 10 makes the admin user on every run (key only, passwordless sudo, in `AllowUsers`).
Your main user is NOT changed until you ask, and only after the admin login is proven:

1. From your computer, in a NEW terminal:
   ```bash
   ssh -o IdentitiesOnly=yes admin@<server> 'sudo -n true && touch ~/.admin-login-ok && echo ADMIN-OK'
   ```
   It must print `ADMIN-OK`. This proves SSH login and passwordless sudo for the admin.
2. Make sure your main user has a password you know: `sudo passwd <MAIN_USER>`.
3. Then: `sudo /opt/server-setup/setup.sh --only security --drop-main-sudo`.
   It refuses (and changes nothing) if the marker file is missing, the admin is not in
   `AllowUsers`, the admin sudoers file is broken, or the main user has no password.

Undo: `sudo rm /etc/sudoers.d/zz-server-main-password` (and `sudo usermod -aG docker,adm <MAIN_USER>`).

## BIOS checklist

Do this once, with a screen and keyboard. Names differ per board.

| Setting | Value | Why |
|---|---|---|
| Restore on AC Power Loss | **Power On** | After a power cut the PC starts by itself. Nothing else can do this. (Some boards: Advanced > Super IO Configuration.) |
| SATA mode | **AHCI** | Normal mode for Linux. SMART and hdparm work. |
| Boot order | **SSD first** | No waiting for USB or network boot. |
| ErP / EuP / Deep sleep | **Off** | With ErP on, the board cuts standby power: no power-on after a cut, no Wake-on-LAN. |
| Wake on LAN / PME | **On** | Start the box with a magic packet. |

## Your manual steps

These need you. The setup cannot do them.

1. **DHCP reservation** on your router: give the server's MAC address a fixed IP.
   Without it the address can change after a power cut, and SSH goes to the wrong place.
   MAC: `ip -br link show <NIC>`.
2. **Tailscale login**: `sudo tailscale up --hostname=<SERVER_NAME>`. Open the URL it prints.
   Then you can reach the server from anywhere, and SSH works over Tailscale too.
3. **Discord webhooks**: in Discord, make two channels: `#<host>-alerts` (notifications on) and
   `#<host>-info` (muted). (`#<host>-hermes` is for the agent, see the `ai` branch.)
   For each: Edit Channel > Integrations > Webhooks > New Webhook > Copy URL. Then:
   ```bash
   sudo discord-notify --set alerts   # paste the URL (hidden)
   sudo discord-notify --set info
   sudo discord-notify info "hello" "first message"
   ```
   The URLs are secrets: root only, mode 600, never in git.
4. **Logins** for your tools when you need them: `gh auth login`, and the AI tools (ai branch).
5. **Power-cut test** once: pull the plug, wait 10 s, plug it back. The box must start by
   itself, and the info channel must say "power cut".

## Power cut: what happens

1. Power comes back. The BIOS starts the PC (Restore on AC Power Loss = Power On).
2. GRUB boots. If the last boot failed, the menu waits 5 s only.
3. fsck repairs the disks by itself (`fsck.repair=yes`).
4. A missing or dead data disk does not stop the boot (`nofail`, 90 s timeout for a slow HDD).
   Postgres and Docker wait for their disk and do not start on the SSD by mistake.
5. Services start. Containers with `restart: unless-stopped` start too.
6. Backup timers that were missed run now (`Persistent=true`).
7. The info channel gets "server is up, last stop: power cut, about N min down".

If the kernel or systemd hangs: the watchdog resets the board after 30 s.
If the kernel panics: kdump saves a dump, then the box reboots after 10 s.
If the PC does not start after a cut: check the BIOS setting and ErP. Wake-on-LAN from another
machine on the LAN: `wakeonlan <MAC>` (or `etherwake`).

There is no UPS yet. See "Later" in [docs/NOTES.md](docs/NOTES.md).

## Check the server

```bash
sudo /opt/server-setup/setup.sh --only verify     # full PASS / FAIL report
systemctl --failed                # failed services
systemctl list-timers             # when the backups run next
journalctl -b -1 -n 50            # the end of the previous boot
cat /data/DISK-ROLES.md           # which disk is which
sudo smartctl -H /dev/sda         # disk health
```

## Update

As the admin user:

```bash
sudo /opt/server-setup/setup.sh --update --dry-run   # fetch what was pushed, see what changes
sudo /opt/server-setup/setup.sh                      # do it
```

To change a value: `sudo nano /etc/server/host.env`, then run setup (or the one step) again.

New settings in `host.env.example` that `/etc/server/host.env` does not have: the preflight step lists
them. Their defaults apply until you add them.

## Troubleshooting

**SSH does not connect (timeout).**
- The IP changed (no DHCP reservation, or the router gave it to another device). Find the server:
  router page (list of clients), or `arp -a` on your computer, or use Tailscale:
  `ssh <user>@<SERVER_NAME>` (Tailscale name). Then make the DHCP reservation.
- You are outside the LAN and not on Tailscale: the firewall drops you. That is by design.

**SSH says "Too many authentication failures".**
MaxAuthTries is 3. Your SSH agent offers too many keys. Use one key:
`ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 <user>@<server>`.

**Banned by fail2ban** (from an address that is not LAN or Tailscale):
```bash
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip 203.0.113.5
sudo fail2ban-client set recidive unbanip 203.0.113.5
```

**Locked out after a setup run.** Wait 10 min: `server-rollback.timer` turns the firewall off and
removes the new SSH file. If the timer was already stopped: screen and keyboard, log in, run
`sudo ufw disable` and fix `/etc/ssh/sshd_config.d/10-server.conf`.

**sudo asks for a password I do not know** (after `--drop-main-sudo`). Log in as the admin user
(`ssh admin@<server>`) and use sudo there. To undo: `sudo rm /etc/sudoers.d/zz-server-main-password`.

**Boxes have no network.** `sudo proj doctor`. After a Docker restart: `sudo systemctl restart
incus-docker-fix`. Check `sudo iptables -L DOCKER-USER -n` shows two `incusbr0` lines (ACCEPT
RELATED,ESTABLISHED and RETURN), and `sudo ufw show added` has `route allow in on incusbr0 out on <NIC>`.

**setup.sh stopped after step 10.** The SSH safety timer is armed. Test a new login, stop the
timer (`sudo systemctl stop server-rollback.timer`), run setup again. Exit code 3 means this stop.

**setup.sh says "Root runs setup only from a clean git clone".** You started it from a folder
another user owns (for example the main user's `~/.dotfiles`), or the clone has local edits. Use
the commands it prints: `sudo /opt/server-setup/setup.sh --update`. Edits belong in a clone of
your own, pushed to GitHub, never in `/opt/server-setup`.

**A step failed.** Read the last lines. Fix the cause. Run only that step again:
`sudo /opt/server-setup/setup.sh --only <step>`. Every step is safe to repeat.

**A disk is missing after a reboot.** `lsblk -o NAME,SIZE,SERIAL,MOUNTPOINT`. If the serial is
there but not mounted: `sudo mount <MOUNT>` and look at `journalctl -b | grep -i <MOUNT>`.

**No Discord messages.** `sudo ls -l /etc/server/webhooks/` (files must exist, mode 600).
`journalctl -t discord-notify` shows sent and failed messages.

## Quirks we learned

- **Ubuntu 26.04 uses Rust coreutils (uutils).** `chown -h` on a symlink changed the target
  folder, not the link. `stat -c` quoting (`%N`) differs from GNU. The scripts avoid both.
- **No AVX2 on older CPUs** (Ivy Bridge and older). Prebuilt binaries made for x86-64-v3 crash
  with "illegal instruction". Build such tools from source (`cargo build --release`).
  The preflight step warns you.
- **dracut builds the initrd** on 26.04, not initramfs-tools. dracut copies udev rules into the
  initrd, where tools like hdparm do not exist. So spin-down is a systemd unit, not a udev rule.
  Files in `/etc/initramfs-tools/` do nothing.
- **Ubuntu blacklists watchdog modules.** `systemd-modules-load` refuses them ("deny-listed").
  `modprobe iTCO_wdt` by name works, so an early unit loads it.
- **Docker publishes ports past ufw.** A `ports: "8080:8080"` line is open to the whole LAN even
  when ufw denies it. Fixed here with `"ip": "127.0.0.1"` in daemon.json.
- **HDD for Postgres** is fine for a home server, but tune for it (`PG_DISK=hdd`: low
  `effective_io_concurrency`, `random_page_cost = 4`) and turn spin-down off.
- **macOS sends `LC_CTYPE=UTF-8`** over SSH. Linux has no such locale. Mapped to `C.UTF-8`.
- **Docker and Incus on one host**: Docker's FORWARD drop cuts the boxes off. Fixed by the
  `DOCKER-USER` rules (step 70). Docker's nftables backend has no `DOCKER-USER`: keep iptables.
- **Ubuntu 26.04 uses sudo-rs.** The sudoers files here are checked with `visudo -c` before they
  are installed, so a broken file never lands.

## Files

```
setup.sh              runs the steps in order: [n/N], --only, --dry-run, --format, --drop-main-sudo
host.env.example      every host value, as examples. Copy to /etc/server/host.env
lib/common.sh         shared helpers (write only when changed, dry-run)
steps/NN-*.sh         one script per step
files/sbin/*          scripts copied to /usr/local/sbin (alerts, backups, watchdog, docker fix)
files/bin/caffeinate  copied to /usr/local/bin
files/proj/proj       the proj CLI (to /usr/local/sbin/proj)
files/sbin/proj-agent the only root command agents may run (sudo, no password, allow-list)
tests/proj-agent.test.sh   offline tests for proj-agent (fake tools, run as a normal user)
tests/proj-workspace.test.sh   offline tests for proj workspaces (new, fork, wipe, recreate)
tests/git-guard.test.sh   offline tests for the workspace git guard (every known bypass + normal use)
files/proj/box-bootstrap.sh   runs inside every new box (user dev, tools, docker, postgres)
files/incus/*.yaml    Incus profiles: box-base, tier-try, tier-mvp, tier-long, docker
docs/HOSTING.md       rules for project boxes (for people)
docs/AGENTS-hosting.md   rules for agents in boxes (the ai branch imports it into AGENTS.md)
docs/NOTES.md         decisions and why, later items, what was tested
```

On the server: `/opt/server-setup/` (root-owned git clone of this branch, the only place setup
runs from), `/etc/server/host.env` (the host values, root:root 644, read by setup and by the alert
and backup scripts), `/etc/server/webhooks/` (Discord URLs, root only), `/etc/proj/` (profiles, host
projects), `/etc/proj-host` (marker: this is the host), `/srv/proj/REGISTRY.md` and
`REGISTRY.json` (list of boxes), `/srv/proj/work/<box>` (the code of each box = `/srv/app` in
the box; `.trash` holds workspaces of wiped boxes), `/var/log/proj.log` (every proj action),
`/var/log/proj-agent.log` (every proj-agent call: who, what, result).

## AI setup

AI agents and their rules are on the `ai` branch of this repo. Same rule as here: root runs its
installer only from a root-owned clone, never from the main user's home. As the admin user:

```bash
sudo git clone --branch ai https://github.com/btc-fan/.dotfiles.git /opt/ai-setup   # once
sudo /opt/ai-setup/install.sh --update --for-user <main user> --dry-run             # look first
sudo /opt/ai-setup/install.sh --update --for-user <main user>                       # do it (and every update)
```

Then read the `ai` branch README for logins and options.

Where agents run: project agents work **inside the box of their project** (step 70, `proj`),
never on the host. On the host, agent sessions are for server admin only, with you watching.
No agent has general sudo on the host (owner decision 2026-11-11, `AGENT_SUDO="none"`). The one
exception is `sudo proj-agent` (step 70, `AGENT_SUDO_ALLOW`): agents make try and mvp boxes, list,
snapshot, read logs and status, and restart services inside boxes. For anything else (tier long,
wipe, restore, host changes) they give you the exact command and you run it.
The `ai` branch imports [docs/AGENTS-hosting.md](docs/AGENTS-hosting.md) into AGENTS.md.
(Step 55, a host user for an agent, is the older way. Keep `AGENT_USER` empty for new servers.)
