# Rules for projects on this server

## The idea

Every project lives in its own box. A box is a small Linux machine (an Incus container).
The project runs inside its box: services, database, files. Its code sits in a workspace
folder on the host that the box sees as `/srv/app`.

- Code: `/srv/app` in the box = `/srv/proj/work/<box>` on the host (the workspace, a git
  checkout). Agents on the host edit it there. It survives `proj recreate`.
- Data: `/srv/data` (its own volume, inside the box). This is the part to keep.
- System: everything else. It can be rebuilt at any time (`proj recreate`).
- Inside every box: user `dev`, with sudo inside that box only.

Root in a box is a normal user on the host. A box cannot see other boxes, the home network,
or any host file except its own workspace.

## Tiers

| | try | mvp | long |
|---|---|---|---|
| For | a quick test, an agent playground, a fork | a real attempt, may be shown to friends | keeps running, must not be lost |
| Life | dies by itself after 7 days (warning 2 days before, stopped at the end, deleted 3 days later). `proj extend` adds time | no end | no end |
| CPU / RAM / disk | 1 CPU, 1 GiB, 10 GiB | 2 CPU, 2 GiB, 20 GiB + data volume | 4 CPU, 4 GiB, 40 GiB + data volume |
| Snapshots | by hand | every night, 3 kept | every night, 7 kept |
| Backup to /data and /backup | no | no | every night (`proj-backup.timer`): box, data and workspace, 7 kept |
| Delete protection | no | no | **yes** |

All box memory caps together may not pass `BOX_MEMORY_BUDGET` (default 4 GiB).
A new box that does not fit is refused. Caps are limits, not use: idle boxes use much less.

## RAM budget (reference machine, 14 GB)

Everything that holds RAM on purpose, so the boxes never squeeze the database:

| Who | How much | Set by |
|---|---|---|
| PostgreSQL `shared_buffers` | about 1/7 of RAM (step 40 rounds down to 256 MB steps) | step 40 `pg_tuning`, or the md999 move for its own cluster |
| ZFS cache (ARC) | 1.5 GB cap | `ZFS_ARC_MAX_MB=1536` (step 70) |
| All boxes together | 4 GiB cap | `BOX_MEMORY_BUDGET` (step 70) |
| kdump crash kernel | reserved at boot, gone for everything else | Ubuntu's `crashkernel=` default (step 20). Real value: `cat /sys/kernel/kexec_crash_size` |
| Host system, Docker, page cache | the rest | |

Huge pages (`vm.nr_hugepages`) are NOT set by this base setup. The md999 move sets them for its
own Postgres; count them in this table when they are on (`grep Huge /proc/meminfo`).
Raise `BOX_MEMORY_BUDGET` only when `free -h` shows the room.

## Commands

All commands need sudo. `proj --help` lists them.

```bash
sudo proj new radar --tier mvp --repo https://github.com/you/radar.git --pg   # new box
sudo proj new test1 --tier try                 # quick test box, 7 days
sudo proj list                                 # all boxes and host projects
sudo proj shell radar                          # log in (tmux session "main")
sudo proj snapshot radar before-upgrade        # snapshot box + data
sudo proj snapshots radar                      # list snapshots
sudo proj restore radar before-upgrade         # go back (makes a pre-restore snapshot first)
sudo proj fork radar radar--try1               # instant copy for a wild idea (try, 3 days)
sudo proj wipe radar--try1                     # throw the copy away
sudo proj recreate radar                       # rebuild the system, keep /srv/data and the workspace
sudo proj workspace radar                      # older box: give it a workspace (copies /srv/app out)
sudo proj promote radar --to long              # move up a tier
sudo proj extend test1 7d                      # more time for a try box
sudo proj backup radar                         # export now
sudo proj sync-rules radar                     # push the current agent rules into the box (--all: every box)
sudo proj doctor                               # health checks (--net: also the network selftest)
sudo proj selftest                             # throwaway box: address, DNS, internet, LAN blocked
```

Options of `proj new`: `--docker` (Docker inside the box), `--pg` (PostgreSQL inside the box,
data on `/srv/data/pg`, database named after the box), `--repo URL` (cloned to `/srv/app`; if the
repo has `box/setup.sh`, it runs), `--ttl 7d` (try only), `--owner NAME`.

## Workspace (the code)

Owner decision 2026-11-11: agents (Claude Code and Codex as the main user, Hermes as
`AGENT_USER`) run on the HOST and work on a project that lives in a box.

- `proj new` makes `/srv/proj/work/<box>` (host.env `WORK_ROOT`) and mounts it in the box at
  `/srv/app`. Owner: the main user. Group: `SHARED_GROUP` (devs). Mode 2775 and a default ACL
  `g:devs:rwx`: files made by the main user, by Hermes or by `dev` in the box stay writable for
  all three.
- Edit the code there with your normal tools. Build, test and run it in the box:
  `sudo proj-agent exec <box> -- <command>` (as `dev`, in `/srv/app`). Services run in the box
  (a systemd unit or `docker compose`, started with exec). Never run the project on the host.
- Reach a service from the host: `sudo proj-agent url <box> [port]` prints `http://<box IP>:<port>`.
  That address works on this host only. Nothing is opened to the LAN.
- Secrets: `/srv/app/.env` (in the workspace), mode 600, listed in the repo's `.gitignore`.
  Mode 600 means only the main user (= `dev` in the box) can read it; Hermes cannot.
- `recreate` keeps the workspace and mounts it again: the code survives a rebuild. `fork`
  copies it (as it is now). `wipe` asks: Enter keeps it (moved to `/srv/proj/work/.trash/<box>-<date>`),
  typing `delete` deletes it. `--yes` and expired try boxes always keep it. Empty `.trash` by hand.
- Every `proj snapshot` also archives the workspace to `/srv/proj/work/.snapshots/<box>/<label>.tar.zst`
  (root only, newest 10 kept, `PROJ_WS_SNAP_KEEP` in host.env changes that). Dependency and cache
  folders (`node_modules`, `.venv`, `__pycache__`, `.cache`, `.next`, ...) are left out: reinstall
  them after a restore. `restore` puts the workspace back too; the current one goes to `.trash`
  first. Still commit and push often. Long boxes: the nightly backup includes it (`<date>-work.tar.zst`).
- The workspace root is `root:devs 750`: the group can look, only proj adds folders.
- How the ids line up: the disk device has `shift=true`, an idmapped mount. The box sees host
  uid N as its own uid N, so the main user must be uid 1000 (= `dev` in every box); proj refuses
  otherwise. The box processes keep their own isolated ID range on the host
  (`security.idmap.isolated`). We do not use `raw.idmap`: it would run `dev` as the real main
  user on the host, so a box escape would get that user. `dev` joins a group with the devs gid
  inside the box, so it may write Hermes' files too.
- Boxes made before workspaces: `sudo proj workspace <box>` copies their `/srv/app` out (no
  owners or setuid bits from the box, links not followed) and mounts the workspace over it.
  Restart the box services after. `proj recreate` does the same copy first.

Box names: lower case letters, digits and `-`, 2 to 31 characters. Forks: `<box>--<word>`.

## Rules

- Use `proj` for everything. Never use `incus delete`, `zfs destroy`, `docker system prune` or
  `dropdb` by hand.
- Before something risky: `sudo proj snapshot <box>`.
- To try something wild: `sudo proj fork <box> <box>--try1`. Throw it away after.
- A project's data lives inside its box (`/srv/data`). Only the code is on the host (the workspace).
- Secrets live in `/srv/app/.env` (mode 600, in `.gitignore`). Never in git.
- Every project repo should have `box/setup.sh` (installs what the project needs, safe to run
  again). Then `proj recreate` rebuilds the box in one command.

## What is protected

| What | Protection |
|---|---|
| long boxes | Incus refuses to delete them (`security.protection.delete=true`). `proj wipe` refuses tier long always. |
| any box you `proj protect` | Incus refuses to delete it. `proj wipe` refuses it. |
| data volumes | Incus has no delete protection for volumes. `proj` only deletes a volume together with its box, and never for a protected or long box. |
| host projects | Listed in host.env `HOST_PROJECTS` (md999, the crawler). `proj` shows and checks them, refuses every command that would change them, and never lets a box take their name. |
| Incus itself | Only the admin user is in `incus-admin`. Everybody else goes through `sudo proj`. |

`--yes` skips the "type the box name" question for try and mvp boxes. Never for long boxes.

## How to remove a long box

1. `sudo proj unprotect <box>`. You type the name. A fresh backup is made first.
   Protection comes back by itself after 2 hours.
2. Within those 2 hours, delete it by hand, on purpose (`proj wipe` always refuses long boxes):
   `sudo incus delete --force <box>`, then `sudo incus storage volume delete boxes <box>-data`.
   The backups stay in `/data/backups/boxes/<box>/`.

## How to wipe and recreate

- **Wipe** = gone. The box, its data volume and its snapshots are deleted. Workspace snapshots follow the workspace (`.trash`, or deleted with it). Use it for try and
  mvp boxes you do not need. The workspace is moved to `/srv/proj/work/.trash` unless you type
  `delete`. The code also stays in git.
- **Recreate** = clean system, same data, same code. The box is deleted and launched again from
  the image; `/srv/data` and the workspace are attached again; the repo is cloned only if the
  workspace has no checkout, then `box/setup.sh` runs. Use it when a box is in a bad state. Box
  snapshots are lost; long boxes get a backup first.
- **Restore a backup** of a long box (for example on a new server). The workspace first, because
  the box expects it at `/srv/proj/work/<box>`:
  ```bash
  sudo tar -C /srv/proj/work --zstd -xpf /data/backups/boxes/<box>/<date>-work.tar.zst
  sudo incus import /data/backups/boxes/<box>/<date>-instance.tar.zst
  sudo incus storage volume import boxes /data/backups/boxes/<box>/<date>-data.tar.zst <box>-data
  ```

## Agents

- Agents run on the host (owner decision 2026-11-11) but the project runs in its box: they edit
  the workspace and run everything with `sudo proj-agent exec <box> -- <cmd>`. Never on the host.
- Inside its box an agent may do anything. Outside it, nothing but its workspace.
- Agents never get general sudo on the host, the Docker group, the incus-admin group or `proj`
  itself (owner decision 2026-11-11, `AGENT_SUDO="none"`).
- One exception (owner decision 2026-11-11, `AGENT_SUDO_ALLOW="proj-agent"`): the main user and
  `AGENT_USER` may run `sudo proj-agent` without a password. It is a strict allow-list: new box
  (try or mvp only), list, snapshot, doctor, logs, status, restart a service inside a box, and
  exec / ports / url inside a box (exec runs any command there as `dev`, never as root, at most
  3600 s; the box is the boundary).
  It refuses host projects, tier long, every other proj command and any odd character, and logs
  every call to `/var/log/proj-agent.log`. Everything else the agent gives you as a command.
  ```bash
  sudo proj-agent help
  sudo proj-agent new test1 --tier try          # long: the owner runs sudo proj new
  sudo proj-agent logs box test1 -n 100
  sudo proj-agent restart test1 nginx
  sudo proj-agent exec test1 -- npm test        # in /srv/app, as dev
  sudo proj-agent exec test1 --timeout 1800 -- docker compose up -d --build
  sudo proj-agent url test1 3000                # http://<box IP>:3000, from this host only
  ```
  Turn it off: `AGENT_SUDO_ALLOW=""` in host.env, then `sudo ./setup.sh --only hosting`.
- Host agent sessions are for server admin only, with the owner watching.
- Rules for the agents themselves: [AGENTS-hosting.md](AGENTS-hosting.md).

## Network

- A box is private. It can reach the internet, but not the home network, the tailnet, Docker
  networks or other boxes (network ACL `box-egress` and port isolation).
- Sharing a box with friends (Tailscale inside the box) is a later step, not built yet.

## Host projects

- Some projects run on the host, not in a box (for example the crawler, with its big database
  on /data). They are registered in host.env `HOST_PROJECTS`.
- They are long-term and protected. `proj list` and `proj doctor` show them. `proj` never wipes,
  recreates, backs up or changes them. Their own jobs back them up (pg-backup, the mirror).
- A box may never have the same name as a host project.

## The list

`/srv/proj/REGISTRY.md` shows every box and host project: tier, owner, created, expiry,
protection, data volume, repo, last backup. `proj` rewrites it after every change. Do not edit it.

## Setup notes (owner)

The box disk is a whole disk, used only for the ZFS pool `boxes`. Before step 70 can make it:

1. Remove the disk from `DISKS` in host.env (if it was a data disk). If it is mounted and EMPTY
   (only `lost+found`), step 70 with `--format` unmounts it, comments out its fstab line and
   wipes it. With anything on it, step 70 refuses: clear it or unmount it by hand.
2. Check its health: `sudo smartctl -H /dev/sdX` must say PASSED (step 70 checks the same and
   refuses otherwise). The scripts never start a SMART test. A long test, if you want one, is
   your call, by hand (`sudo smartctl -t long /dev/sdX`): it stresses a weak disk.
3. A disk that is not mounted but holds data: only if nothing on it is needed,
   `sudo wipefs -a /dev/sdX1; sudo wipefs -a /dev/sdX`.
4. Put its serial in `BOX_DISK_SERIAL` and run `sudo ./setup.sh --only hosting --format`.
5. Network test: `sudo proj selftest` (address, DNS, internet, home gateway blocked).
6. Test once: `sudo proj new test1 --tier try`, `sudo proj snapshot test1`, `sudo proj fork test1
   test1--a`, `sudo proj wipe test1--a`, `sudo proj wipe test1`, `sudo proj doctor`.
   The selftest also proves the workspace round trip (host file writable as dev in a box, box
   file owned by the main user on the host, Hermes and dev write each other's files).

If the disk is not PASSED, do not use it. Leave `BOX_DISK_SERIAL` empty (hosting off).
