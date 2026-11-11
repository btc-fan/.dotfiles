#!/usr/bin/env bash
# uninstall.sh: remove only what install.sh added, from its records:
#   ~/.local/state/ai/managed-keys.json        (user: files, plugins, MCP registrations, links)
#   /var/lib/ai/managed-keys.json              (Ubuntu system files, services, firewall rules)
#   ~hermes/.local/state/ai/managed-keys.json  (Hermes user, if present)
# A key that changed after install is left alone and reported. Logins, secrets.env, tool data
# and project files are never touched.
#
#   Ubuntu (admin):  sudo ~<user>/.dotfiles-ai/uninstall.sh --for-user <user> [--dry-run] [--yes]
#   user part alone: ~/.dotfiles-ai/uninstall.sh --user [--dry-run] [--yes]   (never calls sudo)
#   macOS, or a Linux user with sudo: ~/.dotfiles-ai/uninstall.sh [--dry-run] [--yes]
set -euo pipefail

AI_HOME=$(cd "$(dirname "$0")" && pwd -P)
export AI_HOME
AI_DRY_RUN=0 AI_YES=0 AI_MODE=all AI_FOR_USER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) AI_DRY_RUN=1 ;;
        --yes|-y) AI_YES=1 ;;
        --user) AI_MODE=user ;;
        --for-user) [ $# -ge 2 ] || exit 1; AI_MODE=system; AI_FOR_USER=$2; shift ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown option: %s\n' "$1" >&2; exit 1 ;;
    esac
    shift
done
export AI_DRY_RUN AI_YES AI_MODE AI_FOR_USER
. "$AI_HOME/ai/lib/common.sh"

main() {
    detect_os
    case "$AI_MODE" in
        system) is_root || die "--for-user runs as root: sudo $0 --for-user $AI_FOR_USER"
                getent passwd "$AI_FOR_USER" >/dev/null || die "no such user: $AI_FOR_USER"
                undo_system_mode ;;
        user)   is_root && die "--user runs as the target user, never as root"
                undo_user_mode ;;
        all)    is_root && die "as root use: $0 --for-user <user>"
                undo_all_mode ;;
    esac
    summary
}

undo_user_state() {
    if [ -f "$AI_STATE_FILE" ]; then aiconf status || true; aiconf undo; ok "user changes undone"
    else skip "no user state in $AI_STATE_FILE"; fi
    [ "$AI_DRY_RUN" = 1 ] || rm -f "$AI_STATE_DIR"/ai-core.*.hash
}

undo_hermes_state() {
    if hermes_exists && sudo -n -u "$HERMES_USER" test -f "$(hermes_home)/.local/state/ai/managed-keys.json" 2>/dev/null; then
        aiconf_hermes undo && ok "hermes changes undone"
    else
        skip "no Hermes state"
    fi
}

undo_system_state() {
    if [ "$AI_OS" = linux ] && sudo -n test -f "$AI_SYSTEM_STATE_FILE" 2>/dev/null; then
        if [ ! -f "$AI_ROOT_HELPER" ]; then
            warn "root helper $AI_ROOT_HELPER missing: system state kept (re-run install once, then uninstall)"
            return 0
        fi
        aiconf_root undo && ok "system changes undone"
    else
        skip "no system state"
    fi
}

# The user's part never calls sudo.
undo_user_mode() {
    STEP_TOTAL=1
    say "This removes what install.sh recorded for $(id -un). Other content in the same files stays."
    [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes for $(id -un)?" n || { say "cancelled"; exit 0; }
    step "your files and registrations"; undo_user_state
    manual "kept on purpose: ~/.config/ai/secrets.env, logins, ~/.serena, plugin data dirs, backups in $AI_STATE_DIR/backup"
}

# Admin: the user part as that user first (it runs from the root-owned copy), then Hermes, then
# the system records, then the root-owned copy itself.
undo_system_mode() {
    STEP_TOTAL=4
    say "Removing what install.sh recorded for $AI_FOR_USER, Hermes and the system layer."
    [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes?" n || { say "cancelled"; exit 0; }
    local copy="$AI_ROOT_REPO/uninstall.sh" args="--user --yes"
    [ -x "$copy" ] || copy="$AI_HOME/uninstall.sh"
    [ "$AI_DRY_RUN" = 1 ] && args="$args --dry-run"
    step "user part as $AI_FOR_USER"
    # shellcheck disable=SC2086
    sudo -u "$AI_FOR_USER" -H "$copy" $args || warn "user part for $AI_FOR_USER failed: see above"
    step "Hermes user"; undo_hermes_state
    step "system files"; undo_system_state
    step "root-owned copy"
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] rm -rf /usr/local/lib/ai"
    else rm -rf /usr/local/lib/ai && ok "removed /usr/local/lib/ai"; fi
}

# macOS, or a Linux user with sudo: everything from one process.
undo_all_mode() {
    STEP_TOTAL=3
    say "This removes what install.sh recorded. Other content in the same files stays."
    if [ ! -f "$AI_STATE_FILE" ] && [ ! -f "$AI_SYSTEM_STATE_FILE" ]; then
        say "nothing recorded: no install state found"; exit 0
    fi
    aiconf status || true
    [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes?" n || { say "cancelled"; exit 0; }
    # Ask for the sudo password once, up front, when any recorded undo needs root.
    if [ "$AI_DRY_RUN" != 1 ] && [ "$AI_OS" = linux ] \
        && { [ -e "$AI_SYSTEM_STATE_FILE" ] || grep -q '"sudo"' "$AI_STATE_FILE" 2>/dev/null || hermes_exists; }; then
        sudo -v
    fi
    step "your files and registrations"; undo_user_state
    step "Hermes user"; undo_hermes_state
    step "system files (Ubuntu)"; undo_system_state
    if [ "$AI_OS" = linux ] && [ "$AI_DRY_RUN" != 1 ] && [ -d /usr/local/lib/ai ]; then sudo rm -rf /usr/local/lib/ai; fi
    manual "kept on purpose: ~/.config/ai/secrets.env, logins, ~/.serena, plugin data dirs, backups in $AI_STATE_DIR/backup"
}

main "$@"
