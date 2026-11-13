#!/usr/bin/env bash
# SSH key-only and tight, firewall, fail2ban, security updates, sysctl, hostname, timezone, Tailscale.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

SSHD_FILE=/etc/ssh/sshd_config.d/10-server.conf
TS_NET=100.64.0.0/10
ADMIN_USER=${ADMIN_USER:-admin}
ADMIN_SUDOERS=/etc/sudoers.d/10-server-admin
MAIN_PASSWD_SUDOERS=/etc/sudoers.d/zz-server-main-password
ADMIN_MARKER_NAME=.admin-login-ok
DROP_MAIN_SUDO=${DROP_MAIN_SUDO:-0}

main() {
    apt_install ufw fail2ban unattended-upgrades needrestart curl jq gnupg ca-certificates python3
    # The rollback below posts through discord-notify, so it lands here already (step 50 keeps it).
    put_file sbin/discord-notify /usr/local/sbin/discord-notify 755
    set_identity
    setup_admin_user
    harden_ssh
    drop_main_sudo
    remove_stale_main_nopasswd
    setup_firewall
    setup_fail2ban
    setup_updates
    harden_sysctl
    install_tailscale
    if systemctl is-active -q server-rollback.timer; then
        log "SSH safety timer is armed. Test a NEW SSH login, then: sudo systemctl stop server-rollback.timer"
    fi
}

set_identity() {
    log "hostname and timezone"
    if [ -n "${SERVER_NAME:-}" ] && [ "$(hostnamectl --static 2>/dev/null || hostname)" != "$SERVER_NAME" ]; then
        run hostnamectl set-hostname "$SERVER_NAME"
        if grep -q '^127\.0\.1\.1' /etc/hosts; then
            run sed -i "s/^127\.0\.1\.1.*/127.0.1.1 $SERVER_NAME/" /etc/hosts
        else
            run sh -c "echo '127.0.1.1 $SERVER_NAME' >> /etc/hosts"
        fi
    fi
    if [ "$(timedatectl show -p Timezone --value)" != "$TIMEZONE" ]; then
        run timedatectl set-timezone "$TIMEZONE"
    fi
    info "$(hostname), $(timedatectl show -p Timezone --value)"
}

# The safety net: if SSH or the firewall changes, undo both in 10 minutes unless stopped.
# When it fires it is never silent: journal (logger), wall, and the alerts webhook (if set).
# setup.sh stops after step 10 while this timer is armed.
arm_rollback() {
    rollback_armed && return 0
    info "arming 10 min SSH safety timer (server-rollback.timer)"
    local msg="server-rollback fired: no new SSH login was confirmed within 10 min. ufw is OFF and $SSHD_FILE was removed. Log in, check SSH and ufw, then run setup again."
    run systemctl reset-failed server-rollback.service 2>/dev/null || true
    run systemd-run --unit=server-rollback --on-active=10min \
        /bin/sh -c "ufw --force disable; rm -f $SSHD_FILE; systemctl try-reload-or-restart ssh; \
logger -t server-rollback '$msg'; wall '$msg' 2>/dev/null; \
/usr/local/sbin/discord-notify alerts 'SSH safety rollback fired' '$msg' || true"
}

# A separate admin user: SSH key only, passwordless sudo. The main user stays your daily login.
# First run: the admin gets a copy of the main user's authorized_keys.
setup_admin_user() {
    log "admin user $ADMIN_USER: SSH key only, passwordless sudo"
    if ! id "$ADMIN_USER" >/dev/null 2>&1; then
        run useradd -m -s /bin/bash -c "server admin" "$ADMIN_USER"
        # '*' = no password can ever match (key login only). Not '!', which some tools read as locked.
        run usermod -p '*' "$ADMIN_USER"
    fi
    local home keys main_keys
    home=$(getent passwd "$ADMIN_USER" | cut -d: -f6 || true)
    home=${home:-/home/$ADMIN_USER}
    keys=$home/.ssh/authorized_keys
    main_keys="$(getent passwd "$MAIN_USER" | cut -d: -f6)/.ssh/authorized_keys"
    if [ ! -s "$keys" ]; then
        [ -s "$main_keys" ] || die "$MAIN_USER has no authorized_keys to copy for $ADMIN_USER"
        info "copy $main_keys to $keys (first run only; later edit $keys yourself)"
        run install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$home/.ssh"
        run install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" "$main_keys" "$keys"
    fi
    put_sudoers "$ADMIN_SUDOERS" <<EOF
# Managed by ~/.dotfiles setup.sh (step 10-security): the admin user has passwordless sudo.
$ADMIN_USER ALL=(ALL:ALL) NOPASSWD: ALL
EOF
}

# Once the main user is on "sudo with password" (zz-server-main-password exists), an older file
# that still says "$MAIN_USER ... NOPASSWD: ALL" (cloud-init, or one made by hand before this repo)
# is only beaten by file order. It goes: moved to /root/sudoers-removed/ (undo: move it back).
remove_stale_main_nopasswd() {
    local f
    [ -f "$MAIN_PASSWD_SUDOERS" ] || return 0
    for f in /etc/sudoers.d/*; do
        [ -f "$f" ] && [ "$f" != "$MAIN_PASSWD_SUDOERS" ] || continue
        grep -qE "^[[:space:]]*$MAIN_USER[[:space:]].*NOPASSWD:[[:space:]]*ALL[[:space:]]*$" "$f" 2>/dev/null || continue
        log "remove stale passwordless sudo for $MAIN_USER: $f (kept in /root/sudoers-removed/)"
        if dry; then info "[dry-run] mv $f /root/sudoers-removed/"; continue; fi
        install -d -m 700 /root/sudoers-removed
        mv -- "$f" "/root/sudoers-removed/$(basename "$f").$(date +%Y%m%d-%H%M%S)"
    done
    dry || visudo -c >/dev/null || die "sudoers invalid after removing a stale file: restore it from /root/sudoers-removed/"
}

# main_sudo_rule: host.env MAIN_SUDO decides what the main user keeps after --drop-main-sudo.
#   password (default): sudo with the password.
#   none (owner decision 2026-11-12): no sudo at all, out of the sudo/admin groups. Agents run as the
#        main user and could fake a "sudo" prompt in its shell to catch the password; admin work is
#        done as ADMIN_USER. The allow-listed `sudo proj-agent` (step 70) stays.
# The last matching sudoers rule wins, and zz- sorts last: this beats any older rule.
main_sudo_rule() {
    local g
    case "${MAIN_SUDO:-password}" in
        none)
            put_sudoers "$MAIN_PASSWD_SUDOERS" <<EOF
# Managed by ~/.dotfiles setup.sh (step 10-security, host.env MAIN_SUDO=none).
# $MAIN_USER has NO sudo (only the allow-listed proj-agent of step 70). Admin work: log in as $ADMIN_USER.
# Undo: MAIN_SUDO=password in host.env, run setup.sh --only 10, then: sudo usermod -aG sudo $MAIN_USER
EOF
            for g in sudo admin wheel; do
                if getent group "$g" >/dev/null && id -nG "$MAIN_USER" | tr ' ' '\n' | grep -qx "$g"; then
                    run gpasswd -d "$MAIN_USER" "$g"
                    info "$MAIN_USER left the $g group: no sudo (takes effect at the next login)"
                fi
            done ;;
        password)
            put_sudoers "$MAIN_PASSWD_SUDOERS" <<EOF
# Managed by ~/.dotfiles setup.sh (step 10-security, --drop-main-sudo).
# $MAIN_USER keeps sudo, but must type the password. Admin work: log in as $ADMIN_USER.
# Undo: sudo rm $MAIN_PASSWD_SUDOERS
$MAIN_USER ALL=(ALL:ALL) PASSWD: ALL
EOF
            ;;
        *) die "host.env MAIN_SUDO must be password or none (got '${MAIN_SUDO}')" ;;
    esac
}

# --drop-main-sudo: the main user keeps sudo, but WITH a password, and leaves the docker group.
# Done only after the admin login is proven (the owner creates the marker file through it).
drop_main_sudo() {
    local home marker
    home=$(getent passwd "$ADMIN_USER" | cut -d: -f6 || true)
    marker=$home/$ADMIN_MARKER_NAME
    if [ "$DROP_MAIN_SUDO" != 1 ]; then
        if [ ! -f "$MAIN_PASSWD_SUDOERS" ]; then
            info "main user $MAIN_USER keeps passwordless sudo (pass --drop-main-sudo to change it)"
        else
            # Already dropped once: apply host.env MAIN_SUDO (password | none) on every run.
            main_sudo_rule
        fi
        return 0
    fi
    log "main user $MAIN_USER: sudo with password, out of the docker, incus-admin, lxd and adm groups"
    local fail=0
    # 1. The admin user really logged in over SSH and ran sudo without a password.
    if [ ! -f "$marker" ] || [ "$(stat -c %U "$marker")" != "$ADMIN_USER" ]; then
        warn "admin login not proven yet. From your computer, in a NEW terminal, run:"
        warn "  ssh -o IdentitiesOnly=yes $ADMIN_USER@${SERVER_NAME:-<server>} 'sudo -n true && touch ~/$ADMIN_MARKER_NAME && echo ADMIN-OK'"
        warn "It must print ADMIN-OK. Then run setup again with --drop-main-sudo."
        fail=1
    fi
    # 2. The admin sudoers file is in place and valid.
    if [ ! -f "$ADMIN_SUDOERS" ] || ! visudo -c -f "$ADMIN_SUDOERS" >/dev/null 2>&1; then
        warn "$ADMIN_SUDOERS is missing or invalid"
        fail=1
    fi
    # 3. sshd lets the admin in.
    if ! sshd -T 2>/dev/null | grep -i '^allowusers' | grep -qw "$ADMIN_USER"; then
        warn "sshd AllowUsers does not contain $ADMIN_USER"
        fail=1
    fi
    # 4. The main user has a usable password, or "sudo with password" would mean no sudo at all.
    if [ "$(passwd -S "$MAIN_USER" 2>/dev/null | awk '{print $2}')" != P ]; then
        warn "$MAIN_USER has no usable password. Set one first: sudo passwd $MAIN_USER"
        fail=1
    fi
    [ "$fail" = 0 ] || die "--drop-main-sudo refused. Nothing changed for $MAIN_USER."

    main_sudo_rule
    if id -nG "$MAIN_USER" | tr ' ' '\n' | grep -qx docker; then
        run gpasswd -d "$MAIN_USER" docker
        info "$MAIN_USER left the docker group (takes effect at the next login)"
    fi
    if getent group incus-admin >/dev/null && id -nG "$MAIN_USER" | tr ' ' '\n' | grep -qx incus-admin; then
        run gpasswd -d "$MAIN_USER" incus-admin
    fi
    # Least privilege: lxd is root on the host (like docker), adm reads every system log.
    # The admin user keeps both jobs through sudo.
    local g
    for g in lxd adm; do
        if getent group "$g" >/dev/null && id -nG "$MAIN_USER" | tr ' ' '\n' | grep -qx "$g"; then
            run gpasswd -d "$MAIN_USER" "$g"
            info "$MAIN_USER left the $g group (takes effect at the next login)"
        fi
    done
}

sshd_conf() {
    local users="$MAIN_USER $ADMIN_USER ${SSH_EXTRA_USERS:-}"
    echo "# Managed by ~/.dotfiles setup.sh (step 10-security). Edit host.env, not this file."
    echo "# 10- sorts before 50-cloud-init.conf, and sshd keeps the first value it reads."
    [ "$SSH_PORT" = 22 ] || echo "Port $SSH_PORT"
    cat <<EOF
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers ${users% }
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
PermitTunnel no
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
}

harden_ssh() {
    log "sshd: keys only, no root, only $MAIN_USER"
    local new old_copy legacy=(/etc/ssh/sshd_config.d/10-hardening.conf /etc/ssh/sshd_config.d/60-hardening.conf)
    new=$(sshd_conf)
    if [ -f "$SSHD_FILE" ] && [ "$(cat "$SSHD_FILE")" = "$new" ] \
        && [ ! -e "${legacy[0]}" ] && [ ! -e "${legacy[1]}" ]; then
        info "unchanged"
        return 0
    fi
    arm_rollback
    old_copy=$(mktemp)
    [ -f "$SSHD_FILE" ] && cp "$SSHD_FILE" "$old_copy"
    put "$SSHD_FILE" 644 <<< "$new"
    if dry; then
        remove_legacy "${legacy[@]}"
        rm -f "$old_copy"
        return 0
    fi
    if ! sshd -t; then
        warn "sshd -t failed, restoring the old file"
        if [ -s "$old_copy" ]; then cp "$old_copy" "$SSHD_FILE"; else rm -f "$SSHD_FILE"; fi
        rm -f "$old_copy"
        die "sshd config invalid"
    fi
    rm -f "$old_copy"
    # Files from the first server build, now merged into 10-server.conf.
    # Removed only after sshd -t passed, so a failed test leaves the old working set in place.
    remove_legacy "${legacy[@]}"
    if [ "$SSH_PORT" != 22 ] && systemctl is-enabled -q ssh.socket 2>/dev/null; then
        # Ubuntu 24.04+ uses socket activation; the port comes from a generator.
        systemctl daemon-reload
        systemctl restart ssh.socket
    fi
    systemctl try-reload-or-restart ssh
    sshd -T | grep -E '^(port|passwordauthentication|permitrootlogin|allowusers|maxauthtries) ' | sed 's/^/   /'
}

ufw_allow() {
    local out
    if dry; then info "would run: ufw allow $*"; return 0; fi
    out=$(ufw allow "$@")
    case "$out" in *Skipping*) ;; *) info "$out" ;; esac
}

setup_firewall() {
    log "ufw: deny incoming, SSH from LAN and Tailscale only"
    local p
    if ! ufw status | grep -q 'Status: active'; then
        arm_rollback
    fi
    if ! grep -q '^DEFAULT_INPUT_POLICY="DROP"' /etc/default/ufw; then
        run ufw default deny incoming
    fi
    if ! grep -q '^DEFAULT_OUTPUT_POLICY="ACCEPT"' /etc/default/ufw; then
        run ufw default allow outgoing
    fi
    # ufw skips rules that already exist, so these lines are safe to repeat.
    # No "ufw reset": rules you added by hand stay.
    ufw_allow from "$LAN_CIDR" to any port "$SSH_PORT" proto tcp comment 'SSH LAN'
    ufw_allow in on tailscale0 to any port "$SSH_PORT" proto tcp comment 'SSH Tailscale'
    for p in ${LAN_PORTS:-}; do
        ufw_allow from "$LAN_CIDR" to any port "$p" proto tcp comment 'LAN port (host.env)'
    done
    for p in ${TAILNET_PORTS:-}; do
        ufw_allow in on tailscale0 to any port "$p" proto tcp comment 'Tailscale port (host.env)'
    done
    if ! ufw status | grep -q 'Status: active'; then
        run ufw --force enable
    fi
    ufw status | sed 's/^/   /'
}

setup_fail2ban() {
    log "fail2ban: sshd (aggressive) + growing bans + recidive"
    put /etc/fail2ban/jail.local 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 10-security).
# LAN and Tailscale are never banned. Bans start at 10 min and double each time, up to 1 week.
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 $LAN_CIDR $TS_NET
bantime  = 10m
findtime = 10m
maxretry = 5
backend  = systemd
banaction = ufw
bantime.increment = true
bantime.factor = 2
bantime.maxtime = 1w

[sshd]
enabled = true
mode = aggressive
port = $SSH_PORT
# OpenSSH 10 logs failed logins from sshd-session, not sshd. Ubuntu's unit is ssh.service.
journalmatch = _SYSTEMD_UNIT=ssh.service + _SYSTEMD_UNIT=sshd.service + _COMM=sshd + _COMM=sshd-session

# Banned 3 times in 1 day: banned 1 week on all ports.
[recidive]
enabled = true
backend = auto
logpath = /var/log/fail2ban.log
banaction = %(banaction_allports)s
bantime = 1w
findtime = 1d
maxretry = 3
EOF
    local any=$CHANGED
    remove_legacy /etc/fail2ban/jail.d/60-hardening.local
    if changed; then any=1; fi
    if [ "$any" = 1 ] && ! dry; then
        fail2ban-client -t >/dev/null
        systemctl enable --now fail2ban
        systemctl restart fail2ban
        sleep 2
    fi
    enable_unit fail2ban --now
    # The filter must also know the sshd-session prefix (fail2ban 1.1+ does), or OpenSSH 10
    # failures match nothing even with the journalmatch above.
    if [ -f /etc/fail2ban/filter.d/sshd.conf ] && ! grep -q 'sshd-session' /etc/fail2ban/filter.d/sshd.conf; then
        warn "fail2ban sshd filter does not know sshd-session (OpenSSH 10): failed logins may not be banned. Update fail2ban."
    fi
    dry || fail2ban-client status | sed 's/^/   /'
}

# Security updates only (the Ubuntu default origins), never an automatic reboot.
setup_updates() {
    log "unattended-upgrades: security only, no auto-reboot; needrestart restarts services"
    put /etc/apt/apt.conf.d/20auto-upgrades 644 <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
    put /etc/apt/apt.conf.d/52unattended-local 644 <<'EOF'
// Managed by ~/.dotfiles setup.sh (step 10-security).
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
    put /etc/needrestart/conf.d/50-auto.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh: restart services after library updates without asking.
$nrconf{restart} = 'a';
# Never restart these by surprise: databases, boxes and containers. needrestart lists them;
# the owner restarts them when it suits.
$nrconf{override_rc}{qr(^postgresql)} = 0;
$nrconf{override_rc}{qr(^incus)} = 0;
$nrconf{override_rc}{qr(^docker)} = 0;
$nrconf{override_rc}{qr(^containerd)} = 0;
EOF
    enable_unit unattended-upgrades --now
}

harden_sysctl() {
    log "sysctl network hardening"
    put /etc/sysctl.d/60-server-hardening.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 10-security).
# IP forwarding is left alone: Docker needs it.
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.log_martians = 1
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
fs.protected_symlinks = 1
fs.protected_hardlinks = 1
EOF
    local any=$CHANGED
    remove_legacy /etc/sysctl.d/60-hardening.conf /etc/sysctl.d/60-net-hardening.conf
    if changed; then any=1; fi
    if [ "$any" = 1 ]; then run sysctl --system >/dev/null; fi
}

# Install only. Login is a manual step: sudo tailscale up --hostname=NAME
install_tailscale() {
    log "Tailscale (official repo, install only)"
    if ! command -v tailscale >/dev/null; then
        . /etc/os-release
        local key=/usr/share/keyrings/tailscale-archive-keyring.gpg tmp
        tmp=$(mktemp)
        curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.noarmor.gpg" -o "$tmp"
        check_key_fpr "$tmp" "$FPR_TAILSCALE" Tailscale
        put "$key" 644 < "$tmp"
        rm -f "$tmp"
        # The source line is written here, not downloaded: only the key comes from the network.
        put /etc/apt/sources.list.d/tailscale.list 644 <<< \
            "deb [signed-by=$key] https://pkgs.tailscale.com/stable/ubuntu $VERSION_CODENAME main"
        run apt-get update -q
        run apt-get install -y -q tailscale
    fi
    enable_unit tailscaled --now
    if command -v tailscale >/dev/null; then
        tailscale status >/dev/null 2>&1 && info "Tailscale logged in" \
            || info "Tailscale not logged in yet: sudo tailscale up --hostname=${SERVER_NAME:-$(hostname)}"
    fi
}

main "$@"
