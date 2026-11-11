#!/usr/bin/env bash
# Optional: a second user (for example an AI agent) sharing WORK_DIR. No docker; sudo only with AGENT_SUDO=full.
# Skipped when AGENT_USER is empty in host.env. The agents themselves live on the `ai` branch.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

AGENT_USER=${AGENT_USER:-}
AGENT_SUDO=${AGENT_SUDO:-none}
GROUP=${SHARED_GROUP:-devs}
WORK=${WORK_DIR:-/work}

main() {
    if [ -z "$AGENT_USER" ]; then
        log "AGENT_USER is empty: step skipped"
        return 0
    fi
    apt_install acl git
    create_users
    agent_sudo
    create_work_dir
}

# AGENT_SUDO=full: passwordless sudo through its own sudoers file, never through the sudo group.
# AGENT_SUDO=none (default, owner decision 2026-11-11: agents get no sudo): removes OUR managed file
# (recognised by its header). A file someone wrote by hand is left alone with a warning.
agent_sudo() {
    local f=/etc/sudoers.d/90-$AGENT_USER
    case "$AGENT_SUDO" in
        full)
            log "$AGENT_USER: full passwordless sudo (AGENT_SUDO=full)"
            put_sudoers "$f" <<EOF
# Managed by ~/.dotfiles setup.sh (step 55-shared-users): host.env AGENT_SUDO=full.
# $AGENT_USER is root on this host. Undo: set AGENT_SUDO=none and sudo rm $f
$AGENT_USER ALL=(ALL:ALL) NOPASSWD: ALL
EOF
            ;;
        none)
            if [ -e "$f" ]; then
                if grep -q '^# Managed by ~/.dotfiles setup.sh (step 55-shared-users)' "$f" \
                    || grep -q '^# 2026-11-11 owner decision: Hermes' "$f"; then
                    log "$AGENT_USER: no sudo (AGENT_SUDO=none): removing $f"
                    run rm -f "$f"
                    dry || visudo -c >/dev/null || die "visudo check failed after removing $f"
                else
                    warn "AGENT_SUDO=none but $f was written by hand: left as is. To take sudo away: sudo rm $f"
                fi
            fi
            ;;
        *) die "AGENT_SUDO must be none or full, not '$AGENT_SUDO'" ;;
    esac
}

# The agent user: normal account, never in the sudo/docker/adm groups. Shares only GROUP with MAIN_USER.
create_users() {
    log "group $GROUP, user $AGENT_USER (no sudo group, no docker)"
    getent group "$GROUP" >/dev/null || run groupadd "$GROUP"
    id "$AGENT_USER" >/dev/null 2>&1 || run useradd -m -s /bin/bash "$AGENT_USER"
    local u
    for u in "$MAIN_USER" "$AGENT_USER"; do
        id -nG "$u" 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUP" || run usermod -aG "$GROUP" "$u"
    done
    run chmod 750 "/home/$AGENT_USER"
    # User services (an agent gateway, for example) keep running without a login session.
    [ -f "/var/lib/systemd/linger/$AGENT_USER" ] || run loginctl enable-linger "$AGENT_USER"
    if ! dry && id -nG "$AGENT_USER" | tr ' ' '\n' | grep -qx -e sudo -e docker -e adm; then
        die "$AGENT_USER is in a privileged group (sudo, docker or adm). Remove it by hand."
    fi
}

# WORK_DIR: setgid + default ACL, so every new file stays in GROUP and group-writable.
create_work_dir() {
    log "shared folder $WORK"
    run install -d "$WORK"
    run chown "$MAIN_USER:$GROUP" "$WORK"
    run chmod 2775 "$WORK"
    if ! getfacl -p "$WORK" 2>/dev/null | grep -qx "default:group:$GROUP:rwx"; then
        run setfacl -m "g:$GROUP:rwx" "$WORK"
        run setfacl -d -m "g:$GROUP:rwx" "$WORK"
        run setfacl -d -m "u::rwx,o::rx" "$WORK"
    fi
    # The links stay root-owned on purpose: Ubuntu 26.04 Rust coreutils "chown -h"
    # follows the link and changes the target folder instead.
    local u home
    for u in "$MAIN_USER" "$AGENT_USER"; do
        home=$(getent passwd "$u" | cut -d: -f6 || true)
        [ "$(readlink "$home/work" 2>/dev/null)" = "$WORK" ] || run ln -sfn "$WORK" "$home/work"
    done
    # git refuses repositories owned by another user unless they are marked safe.
    git config --system --get-all safe.directory 2>/dev/null | grep -qx "$WORK/\*" \
        || run git config --system --add safe.directory "$WORK/*"
}

main "$@"
