#!/usr/bin/env bash
# Postgres dumps with history (normal + big databases), monthly restore drill, WORK_DIR snapshots, mirror.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

PG_VERSION=${PG_VERSION:-16}
BACKUP_DIR=${BACKUP_DIR:-}
UNITS=0
unit_changed() { if changed; then UNITS=1; fi; }

main() {
    [ -n "$BACKUP_DIR" ] || { log "BACKUP_DIR is empty: step skipped"; return 0; }
    apt_install rsync acl
    run install -d -m 700 "$BACKUP_DIR"
    # Old schedule overrides from the first build. They would hide the times below.
    remove_legacy /etc/systemd/system/pg-backup.timer.d/10-schedule.conf \
        /etc/systemd/system/work-snapshot.timer.d/10-schedule.conf \
        /etc/systemd/system/backup-mirror.timer.d/10-schedule.conf
    unit_changed
    if is_yes "${INSTALL_POSTGRES:-yes}"; then pg_backup; pg_pitr; fi
    if [ -n "${WORK_DIR:-}" ]; then work_snapshot; fi
    if [ -n "${BACKUP_MOUNT:-}" ]; then backup_mirror; fi
    if [ "$UNITS" = 1 ]; then
        run systemctl daemon-reload
        # Pick up new times in timers that are already running.
        local t
        for t in pg-backup pg-backup-big pg-base-backup pg-restore-drill work-snapshot backup-mirror; do
            if systemctl is-active -q "$t.timer"; then run systemctl restart "$t.timer"; fi
        done
    fi
    if is_yes "${INSTALL_POSTGRES:-yes}"; then
        enable_unit pg-backup.timer --now
        if [ "${PG_PITR:-no}" = base ] || is_yes "${PG_PITR:-no}"; then
            # The base backups (and with "yes" the WAL archive) cover the big databases: no daily dump.
            if systemctl is-enabled -q pg-backup-big.timer 2>/dev/null; then run systemctl disable --now pg-backup-big.timer; fi
            enable_unit pg-base-backup.timer --now
        else
            enable_unit pg-backup-big.timer --now
        fi
        enable_unit pg-restore-drill.timer --now
    fi
    [ -z "${WORK_DIR:-}" ] || enable_unit work-snapshot.timer --now
    [ -z "${BACKUP_MOUNT:-}" ] || enable_unit backup-mirror.timer --now
    dry || systemctl list-timers --all --no-pager 'pg-backup*.timer' 'pg-base-backup.timer' 'pg-restore-drill.timer' 'work-snapshot.timer' 'backup-mirror.timer' | sed 's/^/   /'
}

# PG_PITR: how the big databases are backed up.
#   no    daily pg_dump of PG_BACKUP_SKIP_DBS (pg-backup-big)
#   base  base backups of the whole cluster on PG_BASE_BACKUP_DAY (self-contained, no WAL archive)
#   yes   base backups plus every finished WAL file copied to the backup disk: restore to any
#         moment since the oldest base backup. Size it first: archived WAL is about 0.6 x the WAL
#         written (zstd), and the backup disk must hold the WAL of PG_BASE_KEEP base intervals.
# archive_mode needs one PostgreSQL restart: this step never restarts PostgreSQL itself.
pg_pitr() {
    local conf="/etc/postgresql/$PG_VERSION/main/conf.d/30-wal-archive.conf"
    case "${PG_PITR:-no}" in no|base|yes) ;; *) die "PG_PITR: no, base or yes, not '${PG_PITR}'" ;; esac
    if [ "${PG_PITR:-no}" != yes ] && [ -f "$conf" ]; then
        run rm -f "$conf"
        dry || runuser -u postgres -- psql -XAtqc "SELECT pg_reload_conf()" >/dev/null
        warn "WAL archive off: $conf removed (a pending archive_mode no longer waits for a restart)"
    fi
    [ "${PG_PITR:-no}" != no ] || return 0
    [ -n "${BACKUP_MOUNT:-}" ] || die "PG_PITR=yes needs BACKUP_MOUNT (the WAL archive and the base backups go there)"
    local wal=${PG_WAL_DIR:-$BACKUP_MOUNT/postgres-wal} base=${PG_BASE_DIR:-$BACKUP_MOUNT/postgres-base}
    local day=${PG_BASE_BACKUP_DAY:-Sun} at=${PG_BASE_BACKUP_TIME:-05:30}
    # PG_BASE_BACKUP_DAY: daily, or days like Sun or Wed,Sun
    [[ "$day" =~ ^(daily|(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(,(Mon|Tue|Wed|Thu|Fri|Sat|Sun))*)$ ]] \
        || die "PG_BASE_BACKUP_DAY: daily or Mon..Sun (comma list), not '$day'"
    [[ "$wal" =~ ^/[A-Za-z0-9/._-]+$ ]] || die "PG_WAL_DIR: odd path '$wal'"
    local cal="$day *-*-*"; [ "$day" != daily ] || cal="*-*-*"
    log "base backup ($day at $at) -> $base, keep ${PG_BASE_KEEP:-2}; WAL archive: $([ "$PG_PITR" = yes ] && echo "$wal (zstd)" || echo off)"
    apt_install zstd
    run install -d -o postgres -g postgres -m 700 "$base"
    put_file sbin/pg-base-backup /usr/local/sbin/pg-base-backup 750
    pg_unit pg-base-backup "Base backup of the PostgreSQL cluster" "/usr/local/sbin/pg-base-backup" "$base"
    timer pg-base-backup "PostgreSQL base backup" "$at" "$cal"
    [ "$PG_PITR" = yes ] || return 0
    run install -d -o postgres -g postgres -m 700 "$wal"
    put_file sbin/pg-wal-archive /usr/local/sbin/pg-wal-archive 755
    put "$conf" 644 postgres:postgres <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups, PG_PITR=yes). archive_mode needs a restart.
archive_mode = on
archive_command = '/usr/local/sbin/pg-wal-archive %p %f $wal'
archive_timeout = 900      # a quiet hour still sends its WAL every 15 min
EOF
    dry || runuser -u postgres -- psql -XAtqc "SELECT pg_reload_conf()" >/dev/null
    if ! dry && [ "$(runuser -u postgres -- psql -XAtc "SHOW archive_mode")" != on ]; then
        warn "archive_mode needs one PostgreSQL restart (seconds; clients reconnect): sudo systemctl restart postgresql@$PG_VERSION-main"
    fi
}

# timer NAME DESCRIPTION HH:MM [DAYS]: DAYS is the OnCalendar date part (default every day).
timer() {
    put "/etc/systemd/system/$1.timer" 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups). Change the time in host.env.
[Unit]
Description=$2 at $3

[Timer]
OnCalendar=${4:-*-*-*} $3
RandomizedDelaySec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
    unit_changed
}

pg_backup() {
    local at=${PG_BACKUP_TIME:-07:30} big_at=${PG_BIG_BACKUP_TIME:-04:30} drill_at=${PG_DRILL_TIME:-05:30}
    local dest=${PG_BACKUP_DIR:-${BACKUP_MOUNT:+$BACKUP_MOUNT/postgres}}
    dest=${dest:-$BACKUP_DIR/postgres}
    local big_dest=${PG_BIG_BACKUP_DIR:-${dest}-big} mounts
    mounts="$dest $big_dest"
    [ -z "${PG_BACKUP_KEEP_DAYS:-}" ] || [ -n "${PG_BACKUP_KEEP_DAILY:-}" ] \
        || warn "PG_BACKUP_KEEP_DAYS is replaced by PG_BACKUP_KEEP_DAILY (default 7) and PG_BACKUP_KEEP_WEEKLY (default 4)"
    log "pg-backup at $at: $dest, keep ${PG_BACKUP_KEEP_DAILY:-7} daily + ${PG_BACKUP_KEEP_WEEKLY:-4} weekly, skip: ${PG_BACKUP_SKIP_DBS:-none}"
    log "pg-backup-big at $big_at: ${PG_BACKUP_SKIP_DBS:-none} -> $big_dest, keep ${PG_BIG_KEEP_DAILY:-7} daily + ${PG_BIG_KEEP_WEEKLY:-4} weekly"
    log "pg-restore-drill monthly (day 1) at $drill_at: newest dumps into a throwaway database, result to Discord"
    put_file sbin/pg-backup /usr/local/sbin/pg-backup 750
    put_file sbin/pg-restore-drill /usr/local/sbin/pg-restore-drill 750
    pg_unit pg-backup "Dump the PostgreSQL databases (with history)" "/usr/local/sbin/pg-backup" "$mounts"
    timer pg-backup "PostgreSQL dumps" "$at"
    pg_unit pg-backup-big "Dump the big PostgreSQL databases (PG_BACKUP_SKIP_DBS)" "/usr/local/sbin/pg-backup --big" "$mounts"
    timer pg-backup-big "Big PostgreSQL dumps" "$big_at"
    pg_unit pg-restore-drill "Restore the newest dumps into a throwaway database" "/usr/local/sbin/pg-restore-drill" "$mounts"
    timer pg-restore-drill "Monthly PostgreSQL restore drill" "$drill_at" "*-*-01"
}

# pg_unit NAME DESCRIPTION EXEC MOUNTS
pg_unit() {
    put "/etc/systemd/system/$1.service" 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups).
[Unit]
Description=$2
Requires=postgresql@$PG_VERSION-main.service
After=postgresql@$PG_VERSION-main.service
RequiresMountsFor=$4

[Service]
Type=oneshot
ExecStart=$3
Nice=10
IOSchedulingClass=idle
EOF
    unit_changed
}

work_snapshot() {
    local at=${WORK_SNAPSHOT_TIME:-07:45}
    log "work-snapshot at $at: $WORK_DIR -> $BACKUP_DIR/work, keep ${WORK_SNAPSHOT_KEEP_DAYS:-14} days"
    put_file sbin/work-snapshot /usr/local/sbin/work-snapshot 750
    put /etc/systemd/system/work-snapshot.service 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups).
[Unit]
Description=Daily snapshot of $WORK_DIR
RequiresMountsFor=$BACKUP_DIR

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/work-snapshot
Nice=10
IOSchedulingClass=idle
EOF
    unit_changed
    timer work-snapshot "Daily snapshot of $WORK_DIR" "$at"
}

backup_mirror() {
    local at=${BACKUP_MIRROR_TIME:-08:30}
    log "backup-mirror at $at: $BACKUP_DIR -> $BACKUP_MOUNT/data-backups, not mirrored: ${BACKUP_MIRROR_EXCLUDE-md999-move}"
    put_file sbin/backup-mirror /usr/local/sbin/backup-mirror 750
    put /etc/systemd/system/backup-mirror.service 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups).
[Unit]
Description=Mirror $BACKUP_DIR to the backup disk
RequiresMountsFor=$BACKUP_DIR $BACKUP_MOUNT
After=pg-backup.service work-snapshot.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/backup-mirror
Nice=10
IOSchedulingClass=idle
EOF
    unit_changed
    timer backup-mirror "Mirror of $BACKUP_DIR to $BACKUP_MOUNT" "$at"
}

main "$@"
