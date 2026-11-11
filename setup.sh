#!/usr/bin/env bash
# setup.sh: build this Ubuntu server from host.env. Safe to run again: a second run changes nothing.
#
# Usage: sudo ./setup.sh [--only STEP]... [--dry-run] [--format] [--drop-main-sudo] [--list]
#   --only STEP       run one step (number or name: 10, security, 10-security). Repeat for more.
#   --dry-run         show what would change. Writes nothing.
#   --format          allow 30-disks and 70-hosting to format disks that are completely empty.
#   --drop-main-sudo  main user: sudo with password, out of docker. Only after the admin login is proven.
#   --list            list the steps and exit.
set -euo pipefail

REPO_DIR=$(cd "$(dirname "$0")" && pwd)
export REPO_DIR
# Root runs these scripts, so root runs them from a root-owned copy. A clone in a user's home
# can be edited by that user (or by an agent running as that user): that would be root for them.
INSTALL_DIR=/opt/server-setup
ARGS=("$@")

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

only=()
DRY_RUN=0
FORMAT=0
DROP_MAIN_SUDO=0
list=0
while [ $# -gt 0 ]; do
    case "$1" in
        --only) [ $# -ge 2 ] || usage 2; only+=("$2"); shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --format) FORMAT=1; shift ;;
        --drop-main-sudo) DROP_MAIN_SUDO=1; shift ;;
        --list) list=1; shift ;;
        -h|--help) usage 0 ;;
        *) echo "unknown option: $1"; usage 2 ;;
    esac
done
export DRY_RUN FORMAT DROP_MAIN_SUDO

all=("$REPO_DIR"/steps/[0-9][0-9]-*.sh)
if [ "$list" = 1 ]; then
    for s in "${all[@]}"; do
        printf '%-18s %s\n' "$(basename "$s" .sh)" "$(sed -n '2s/^# *//p' "$s")"
    done
    exit 0
fi

# shellcheck source=lib/common.sh
. "$REPO_DIR/lib/common.sh"
need_root
load_env

# install_copy: copy this repo (with host.env, without .git) to INSTALL_DIR, root:root,
# folders 755, files 644. Built next to it and swapped in, so a failed copy never leaves half a tree.
install_copy() {
    local new=$INSTALL_DIR.new bad
    [ "$(stat -c %U:%G /opt 2>/dev/null)" = root:root ] || die "/opt is not owned by root:root. Refused."
    case "$(stat -c %A /opt)" in ?????w????|????????w?) die "/opt is writable by group or others. Refused." ;; esac
    rm -rf "$new"
    install -d -m 755 -o root -g root "$new"
    tar -C "$REPO_DIR" --exclude=./.git -cf - . | tar -C "$new" --no-same-owner --no-same-permissions -xf -
    chown -R root:root "$new"
    find "$new" -type d -exec chmod 755 {} +
    find "$new" -type f -exec chmod 644 {} +
    bad=$(find "$new" \( ! -user root -o ! -group root -o -perm /022 \) -print -quit)
    [ -z "$bad" ] || { rm -rf "$new"; die "the copy in $new cannot be made root-owned ($bad). Refused."; }
    rm -rf "$INSTALL_DIR"
    mv "$new" "$INSTALL_DIR"
}

if [ "$REPO_DIR" != "$INSTALL_DIR" ]; then
    if dry; then
        echo "   would copy $REPO_DIR to $INSTALL_DIR (root:root, folders 755, files 644) and run from there"
        echo "   (dry run: runs from $REPO_DIR, nothing is copied)"
    else
        install_copy
        echo "   copied $REPO_DIR to $INSTALL_DIR (root-owned). Running from there."
        exec bash "$INSTALL_DIR/setup.sh" ${ARGS[@]+"${ARGS[@]}"}
    fi
fi

# Pick the steps to run. 00-preflight (read only) always runs first, also with --only.
steps=()
matched=0
for s in "${all[@]}"; do
    name=$(basename "$s" .sh)
    if [ "${#only[@]}" -eq 0 ] || [ "$name" = 00-preflight ]; then
        steps+=("$s")
    fi
    for o in ${only[@]+"${only[@]}"}; do
        if [ "$o" = "$name" ] || [ "$o" = "${name%%-*}" ] || [ "$o" = "${name#*-}" ]; then
            matched=1
            [ "$name" = 00-preflight ] || steps+=("$s")
        fi
    done
done
[ "${#only[@]}" -eq 0 ] || [ "$matched" = 1 ] || die "no step matches: ${only[*]}. See ./setup.sh --list"

LOG=/var/log/server-setup.log
exec > >(tee -a "$LOG") 2>&1
printf '\n##### setup.sh %s  dry-run=%s  format=%s  from=%s\n' "$(date -Is)" "$DRY_RUN" "$FORMAT" "$REPO_DIR"

# rollback_stop: the SSH safety timer is armed. The run stops here: nothing after step 10 may
# change the server before a NEW login has proven that SSH and the firewall still let you in.
rollback_stop() {
    local port_opt=""
    [ "$SSH_PORT" = 22 ] || port_opt="-p $SSH_PORT "
    cat <<EOF

!!! SSH safety timer is ARMED. In 10 minutes it turns the firewall off, removes the new SSH
!!! settings and posts to the alerts channel, in case you are locked out.
!!! The setup STOPS here. Open a NEW terminal on your computer and test a new login:
!!!     ssh ${port_opt}-o IdentitiesOnly=yes $MAIN_USER@${SERVER_NAME:-<server>} 'echo LOGIN-OK'
!!!     ssh ${port_opt}-o IdentitiesOnly=yes ${ADMIN_USER:-admin}@${SERVER_NAME:-<server>} 'sudo -n true && echo ADMIN-OK'
!!! When both print OK:   sudo systemctl stop server-rollback.timer
!!! Then run setup again (same options) for the remaining steps.
EOF
}

n=${#steps[@]}
i=0
env_done=0
for s in "${steps[@]}"; do
    i=$((i + 1))
    name=$(basename "$s" .sh)
    if [ "$env_done" = 0 ] && [ "$name" != 00-preflight ]; then
        # Runtime scripts (alerts, backups) read the same values from /etc/server/host.env.
        # Root-owned and 644: no secrets in it, and nobody else can change what root sources.
        run install -d -m 755 -o root -g root "$SERVER_ETC"
        put "$SERVER_ETC/host.env" 644 root:root < "$REPO_DIR/host.env"
        env_done=1
    fi
    # Steps after 10 wait until the SSH safety timer is stopped (armed by step 10, now or earlier).
    case "$name" in 00-*|10-*) ;; *)
        if rollback_armed; then
            if dry; then
                warn "SSH safety timer is armed: a real run stops before $name (dry run goes on)"
            else
                rollback_stop
                exit 3
            fi
        fi ;;
    esac
    printf '\n[%d/%d] %s\n' "$i" "$n" "$name"
    if ! bash "$s"; then
        printf '\nFAILED at %s. Fix the cause, then run: sudo ./setup.sh --only %s\n' "$name" "${name%%-*}"
        exit 1
    fi
done

printf '\n##### done. Log: %s\n' "$LOG"
if rollback_armed; then
    rollback_stop
fi
if [ -f /var/run/reboot-required ]; then
    echo "Reboot needed (kernel, kdump or GRUB change): sudo reboot"
fi
