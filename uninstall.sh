#!/usr/bin/env bash
# uninstall.sh: remove only what install.sh added, from its records:
#   ~/.local/state/ai/managed-keys.json        (your files, plugins, MCP registrations, links)
#   /var/lib/ai/managed-keys.json              (Ubuntu system files, services, firewall rules)
#   ~hermes/.local/state/ai/managed-keys.json  (Hermes user, if present)
# A key that changed after install is left alone and reported. Logins, secrets.env, tool data
# and project files are never touched.
#
#   ./uninstall.sh [--dry-run] [--yes]
set -euo pipefail

AI_HOME=$(cd "$(dirname "$0")" && pwd -P)
export AI_HOME
AI_DRY_RUN=0 AI_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) AI_DRY_RUN=1 ;;
        --yes|-y) AI_YES=1 ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown option: %s\n' "$1" >&2; exit 1 ;;
    esac
    shift
done
export AI_DRY_RUN AI_YES
. "$AI_HOME/ai/lib/common.sh"

main() {
    detect_os
    is_root && die "run as your normal user, not root"
    say "This removes what install.sh recorded. Other content in the same files stays."
    if [ ! -f "$AI_STATE_FILE" ] && [ ! -f "$AI_SYSTEM_STATE_FILE" ]; then
        say "nothing recorded: no install state found"; exit 0
    fi
    aiconf status || true
    [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes?" n || { say "cancelled"; exit 0; }

    STEP_TOTAL=3
    step "your files and registrations"
    if [ -f "$AI_STATE_FILE" ]; then aiconf undo; ok "user changes undone"; else skip "no user state"; fi

    step "Hermes user"
    if hermes_exists && sudo -n -u "$HERMES_USER" test -f "$(hermes_home)/.local/state/ai/managed-keys.json" 2>/dev/null; then
        aiconf_hermes undo && ok "hermes changes undone"
    else
        skip "no Hermes state"
    fi

    step "system files (Ubuntu)"
    if [ "$AI_OS" = linux ] && sudo -n test -f "$AI_SYSTEM_STATE_FILE" 2>/dev/null; then
        aiconf_root undo && ok "system changes undone"
    else
        skip "no system state"
    fi

    [ "$AI_DRY_RUN" = 1 ] || rm -f "$AI_STATE_DIR"/ai-core.*.hash
    manual "kept on purpose: ~/.config/ai/secrets.env, logins, ~/.serena, plugin data dirs, backups in $AI_STATE_DIR/backup"
    summary
}

main "$@"
