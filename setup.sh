#!/usr/bin/env bash
# setup.sh: build this Ubuntu server from /etc/server/host.env. Safe to run again: a second run changes nothing.
#
# Usage: sudo /opt/server-setup/setup.sh [--update] [--only STEP]... [--dry-run] [--format] [--drop-main-sudo] [--list]
#   --update          first fetch the pushed branch from GitHub (fast-forward only), then run it.
#   --only STEP       run one step (number or name: 10, security, 10-security). Repeat for more.
#   --dry-run         show what would change. Writes nothing.
#   --format          allow 30-disks and 70-hosting to format disks that are completely empty.
#   --drop-main-sudo  main user: out of sudo, docker, lxd, adm. Only after the admin login is proven.
#   --list            list the steps and exit.
set -euo pipefail

REPO_DIR=$(cd "$(dirname "$0")" && pwd -P)
export REPO_DIR
# SECURITY: root runs only from a clone that root (or the admin user) owns, with a clean git tree.
# Never from the main user's home: that user, or an agent running as that user, could change
# what root runs. The checks are in lib/common.sh (source_guard). The right place: /opt/server-setup.
ARGS=()
usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

only=()
UPDATE=0
DRY_RUN=0
FORMAT=0
DROP_MAIN_SUDO=0
list=0
while [ $# -gt 0 ]; do
    case "$1" in
        --update) UPDATE=1; shift ;;
        --only) [ $# -ge 2 ] || usage 2; only+=("$2"); ARGS+=("$1" "$2"); shift 2 ;;
        --dry-run) DRY_RUN=1; ARGS+=("$1"); shift ;;
        --format) FORMAT=1; ARGS+=("$1"); shift ;;
        --drop-main-sudo) DROP_MAIN_SUDO=1; ARGS+=("$1"); shift ;;
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
source_guard
load_env

# --update: fetch the pushed branch and fast-forward to it (refused when the tree is dirty, when
# local commits exist, or when the remote history was rewritten), then run the new setup.sh.
if [ "$UPDATE" = 1 ]; then
    update_clone
    exec bash "$REPO_DIR/setup.sh" ${ARGS[@]+"${ARGS[@]}"}
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
[ "${#only[@]}" -eq 0 ] || [ "$matched" = 1 ] || die "no step matches: ${only[*]}. See setup.sh --list"

LOG=/var/log/server-setup.log
exec > >(tee -a "$LOG") 2>&1
printf '\n##### setup.sh %s  dry-run=%s  format=%s  from=%s at %s\n' "$(date -Is)" "$DRY_RUN" "$FORMAT" "$REPO_DIR" \
    "$(git_root -C "$REPO_DIR" log -1 --format='%h %s' 2>/dev/null || echo '?')"

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
for s in "${steps[@]}"; do
    i=$((i + 1))
    name=$(basename "$s" .sh)
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
        printf '\nFAILED at %s. Fix the cause, then run: sudo %s/setup.sh --only %s\n' "$name" "$REPO_DIR" "${name%%-*}"
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
