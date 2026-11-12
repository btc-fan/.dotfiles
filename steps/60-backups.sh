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
    if is_yes "${INSTALL_POSTGRES:-yes}"; then pg_backup; fi
    if [ -n "${WORK_DIR:-}" ]; then work_snapshot; fi
    if [ -n "${BACKUP_MOUNT:-}" ]; then backup_mirror; fi
    if [ "$UNITS" = 1 ]; then
        run systemctl daemon-reload
        # Pick up new times in timers that are already running.
        local t
        for t in pg-backup pg-backup-big pg-restore-drill work-snapshot backup-mirror; do
            if systemctl is-active -q "$t.timer"; then run systemctl restart "$t.timer"; fi
        done
    fi
    if is_yes "${INSTALL_POSTGRES:-yes}"; then
        enable_unit pg-backup.timer --now
        enable_unit pg-backup-big.timer --now
        enable_unit pg-restore-drill.timer --now
    fi
    [ -z "${WORK_DIR:-}" ] || enable_unit work-snapshot.timer --now
    [ -z "${BACKUP_MOUNT:-}" ] || enable_unit backup-mirror.timer --now
    dry || systemctl list-timers --all --no-pager 'pg-backup*.timer' 'pg-restore-drill.timer' 'work-snapshot.timer' 'backup-mirror.timer' | sed 's/^/   /'
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
