#!/usr/bin/env bash
# Nightly Postgres dumps, WORK_DIR snapshots, and a mirror of both to the backup disk. Times from host.env.
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
        for t in pg-backup work-snapshot backup-mirror; do
            if systemctl is-active -q "$t.timer"; then run systemctl restart "$t.timer"; fi
        done
    fi
    is_yes "${INSTALL_POSTGRES:-yes}" && enable_unit pg-backup.timer --now
    [ -z "${WORK_DIR:-}" ] || enable_unit work-snapshot.timer --now
    [ -z "${BACKUP_MOUNT:-}" ] || enable_unit backup-mirror.timer --now
    dry || systemctl list-timers --all --no-pager 'pg-backup.timer' 'work-snapshot.timer' 'backup-mirror.timer' | sed 's/^/   /'
}

# timer NAME DESCRIPTION HH:MM
timer() {
    put "/etc/systemd/system/$1.timer" 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups). Change the time in host.env.
[Unit]
Description=$2 at $3

[Timer]
OnCalendar=*-*-* $3
RandomizedDelaySec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
    unit_changed
}

pg_backup() {
    local at=${PG_BACKUP_TIME:-07:30}
    log "pg-backup at $at: $BACKUP_DIR/postgres, keep ${PG_BACKUP_KEEP_DAYS:-3} days, skip: ${PG_BACKUP_SKIP_DBS:-none}"
    put_file sbin/pg-backup /usr/local/sbin/pg-backup 750
    put /etc/systemd/system/pg-backup.service 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 60-backups).
[Unit]
Description=Dump all PostgreSQL databases
Requires=postgresql@$PG_VERSION-main.service
After=postgresql@$PG_VERSION-main.service
RequiresMountsFor=$BACKUP_DIR

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/pg-backup
Nice=10
IOSchedulingClass=idle
EOF
    unit_changed
    timer pg-backup "Nightly PostgreSQL dump" "$at"
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
