#!/usr/bin/env bash
# Discord alerts: failed services, SMART, disk full, boot reason, SSH logins. No webhook = no-op.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

HOOK_DIR=$SERVER_ETC/webhooks
SBIN=/usr/local/sbin
UNITS=0
unit_changed() { if changed; then UNITS=1; fi; }

main() {
    apt_install curl jq smartmontools util-linux
    run install -d -m 700 "$HOOK_DIR" /var/lib/server-alerts
    install_scripts
    failure_alerts
    smart_alerts
    disk_full_timer
    boot_message
    ssh_login_message
    if [ "$UNITS" = 1 ]; then run systemctl daemon-reload; fi
    enable_unit disk-usage-check.timer --now
    enable_unit boot-notify.service
    status
}

install_scripts() {
    log "alert scripts in $SBIN"
    local s
    for s in discord-notify notify-failure smartd-notify disk-usage-check boot-notify ssh-login-notify; do
        put_file "sbin/$s" "$SBIN/$s" 755
    done
}

# Every service gets OnFailure=notify-failure@<name>.service through one top-level drop-in.
# The handler itself must not get it (a failing handler would start itself again):
# a drop-in with the same name, linked to /dev/null, cancels it for the handler.
failure_alerts() {
    log "failed service -> #alerts (last 20 log lines, grouped per unit)"
    put /etc/systemd/system/notify-failure@.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts).
[Unit]
Description=Discord alert for failed unit %i

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/notify-failure %i
EOF
    unit_changed
    put /etc/systemd/system/service.d/10-notify-failure.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts): any failed service sends a Discord alert.
# %n = full unit name with instance and suffix (postgresql@16-main.service), passed as is.
[Unit]
OnFailure=notify-failure@%n.service
EOF
    unit_changed
    local mask=/etc/systemd/system/notify-failure@.service.d/10-notify-failure.conf
    if [ "$(readlink "$mask" 2>/dev/null)" != /dev/null ]; then
        run install -d /etc/systemd/system/notify-failure@.service.d
        run ln -sfn /dev/null "$mask"
        UNITS=1
    fi
}

smart_alerts() {
    log "SMART problems on any disk -> #alerts (smartd)"
    put /etc/smartd.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts).
# Every disk: all health checks and attribute autosave. Watch only: smartd never starts a
# self-test or offline scan (owner rule: SMART tests only by hand, a test stresses a weak disk).
# Temperature: logged from 50 C, alert from 60 C.
# Problems go to smartd-notify (Discord #<host>-alerts), repeated after 1, 2, 4... days while they last.
DEVICESCAN -a -S on -W 0,50,60 -m <nomailer> -M diminishing -M exec /usr/local/sbin/smartd-notify
EOF
    if changed && ! dry; then
        systemctl enable smartmontools >/dev/null 2>&1 || true
        systemctl reload-or-restart smartmontools
    fi
}

disk_full_timer() {
    log "disk fuller than ${DISK_ALERT_PCT:-85}% -> #alerts (every 30 min, once a day per disk)"
    put /etc/systemd/system/disk-usage-check.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts).
[Unit]
Description=Alert when a disk is almost full

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/disk-usage-check
EOF
    unit_changed
    put /etc/systemd/system/disk-usage-check.timer 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts).
[Unit]
Description=Check disk usage every 30 minutes

[Timer]
OnCalendar=*:0/30
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
EOF
    unit_changed
}

# Type=exec: boot does not wait for it. Enabled only, never started by setup:
# starting it now would post "server is up" for a boot that happened long ago.
boot_message() {
    log "boot -> #info with the cause of the last stop"
    put /etc/systemd/system/boot-notify.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 50-alerts).
[Unit]
Description=Discord message: server is up, and why it stopped
Wants=network-online.target
After=network-online.target

[Service]
Type=exec
ExecStart=/usr/local/sbin/boot-notify

[Install]
WantedBy=multi-user.target
EOF
    unit_changed
}

ssh_login_message() {
    log "SSH login -> #info (user and address, via PAM)"
    local line="session optional pam_exec.so quiet $SBIN/ssh-login-notify"
    if ! grep -qF "$line" /etc/pam.d/sshd; then
        { cat /etc/pam.d/sshd; echo "# ~/.dotfiles setup.sh (step 50-alerts): SSH login message, never blocks a login."; echo "$line"; } \
            | put /etc/pam.d/sshd 644
    fi
}

status() {
    log "webhooks"
    local c
    for c in alerts info; do
        if [ -s "$HOOK_DIR/$c.url" ]; then
            info "$c: set"
        else
            info "$c: not set (alerts for it do nothing). Set it: sudo discord-notify --set $c"
        fi
    done
    info "try without posting: sudo boot-notify --test ; sudo disk-usage-check --test"
}

main "$@"
