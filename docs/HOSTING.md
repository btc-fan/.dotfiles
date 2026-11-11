# Rules for projects on this server

## The idea

Every project lives in its own box. A box is a small Linux machine (an Incus container).
What a project owns lives inside its box: code, database, files, secrets.
Delete the box and the project is gone. Nothing is left behind.

- Code: `/srv/app` (a git checkout). It can always come back from git.
- Data: `/srv/data` (its own volume). This is the part to keep.
- System: everything else. It can be rebuilt at any time (`proj recreate`).
- Inside every box: user `dev`, with sudo inside that box only.

Root in a box is a normal user on the host. A box cannot see other boxes, the host files,
or the home network.

## Tiers

| | try | mvp | long |
|---|---|---|---|
| For | a quick test, an agent playground, a fork | a real attempt, may be shown to friends | keeps running, must not be lost |
| Life | dies by itself after 7 days (warning 2 days before, stopped at the end, deleted 3 days later). `proj extend` adds time | no end | no end |
| CPU / RAM / disk | 1 CPU, 1 GiB, 10 GiB | 2 CPU, 2 GiB, 20 GiB + data volume | 4 CPU, 4 GiB, 40 GiB + data volume |
| Snapshots | by hand | every night, 3 kept | every night, 7 kept |
| Backup to /data and /backup | no | no | every night (`proj-backup.timer`), 7 kept |
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
sudo proj recreate radar                       # rebuild the system, keep /srv/data
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

Box names: lower case letters, digits and `-`, 2 to 31 characters. Forks: `<box>--<word>`.

## Rules

- Use `proj` for everything. Never use `incus delete`, `zfs destroy`, `docker system prune` or
  `dropdb` by hand.
- Before something risky: `sudo proj snapshot <box>`.
- To try something wild: `sudo proj fork <box> <box>--try1`. Throw it away after.
- A project's data lives inside its box. No project keeps data on the host.
- Secrets live in `/srv/app/.env` (mode 600) inside the box. Never in git.
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

- **Wipe** = gone. The box, its data volume and its snapshots are deleted. Use it for try and
  mvp boxes you do not need. The code stays in git.
- **Recreate** = clean system, same data. The box is deleted and launched again from the image;
  `/srv/data` is kept and attached again; the repo is cloned again and `box/setup.sh` runs.
  Use it when a box is in a bad state. Box snapshots are lost; long boxes get a backup first.
- **Restore a backup** of a long box (for example on a new server):
  ```bash
  sudo incus import /data/backups/boxes/<box>/<date>-instance.tar.zst
  sudo incus storage volume import boxes /data/backups/boxes/<box>/<date>-data.tar.zst <box>-data
  ```

## Agents

- Agents work inside the box of their project. Never on the host.
- Inside its box an agent may do anything. Outside it, nothing.
- Agents never get general sudo on the host, the Docker group, the incus-admin group or `proj`
  itself (owner decision 2026-11-11, `AGENT_SUDO="none"`).
- One exception (owner decision 2026-11-11, `AGENT_SUDO_ALLOW="proj-agent"`): the main user and
  `AGENT_USER` may run `sudo proj-agent` without a password. It is a strict allow-list: new box
  (try or mvp only), list, snapshot, doctor, logs, status, restart a service inside a box.
  It refuses host projects, tier long, every other proj command and any odd character, and logs
  every call to `/var/log/proj-agent.log`. Everything else the agent gives you as a command.
  ```bash
  sudo proj-agent help
  sudo proj-agent new test1 --tier try          # long: the owner runs sudo proj new
  sudo proj-agent logs box test1 -n 100
  sudo proj-agent restart test1 nginx
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

If the disk is not PASSED, do not use it. Leave `BOX_DISK_SERIAL` empty (hosting off).
