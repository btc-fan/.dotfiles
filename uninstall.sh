#!/usr/bin/env bash
# uninstall.sh: remove what install.sh added, from its records:
#   ~/.local/state/ai/managed-keys.json        (user: files, plugins, MCP registrations, links)
#   /var/lib/ai/managed-keys.json              (Ubuntu system files)
#   ~hermes/.local/state/ai/managed-keys.json  (Hermes user, if present)
# Default: a key that changed after install is left alone; installed tools (binaries, npm/uv
# packages, plugin sources, the docs service) are KEPT; logins, secrets and data stay.
#
#   Ubuntu (admin):  sudo ~<user>/.dotfiles-ai/uninstall.sh --for-user <user> [level] [--dry-run] [--yes]
#   user part alone: ~/.dotfiles-ai/uninstall.sh --user [level] [--dry-run] [--yes]   (never calls sudo)
#   macOS, or a Linux user with sudo: ~/.dotfiles-ai/uninstall.sh [level] [--dry-run] [--yes]
#
#   level: (none)          undo the recorded changes, keep tools
#          --purge-config  + delete the agents' whole config/state folders (user, and Hermes as admin)
#          --purge-all     + --purge-config + remove every tool the installer recorded
#   Purge: backup tarball first (~/ai-backup-<UTC>.tar.gz, mode 600), then the exact list, then you
#   must type `purge` in a terminal. --yes does not skip that. Never touched: projects, boxes,
#   databases, /data, /backup, the base setup, ~/.dotfiles, ~/.dotfiles-ai.
set -euo pipefail

AI_HOME=$(cd "$(dirname "$0")" && pwd -P)
export AI_HOME
AI_DRY_RUN=0 AI_YES=0 AI_MODE=all AI_FOR_USER="" PURGE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) AI_DRY_RUN=1 ;;
        --yes|-y) AI_YES=1 ;;
        --user) AI_MODE=user ;;
        --for-user) [ $# -ge 2 ] || exit 1; AI_MODE=system; AI_FOR_USER=$2; shift ;;
        --purge-config) PURGE=config ;;
        --purge-all) PURGE=all ;;
        -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown option: %s\n' "$1" >&2; exit 1 ;;
    esac
    shift
done
export AI_DRY_RUN AI_YES AI_MODE AI_FOR_USER
. "$AI_HOME/ai/lib/common.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)

main() {
    detect_os
    if [ -n "$PURGE" ] && [ "$AI_DRY_RUN" != 1 ] && [ ! -t 0 ]; then
        die "purge needs a terminal: it asks you to type 'purge' (no flag skips that). Use --dry-run to see the plan."
    fi
    case "$AI_MODE" in
        system) is_root || die "--for-user runs as root: sudo $0 --for-user $AI_FOR_USER"
                getent passwd "$AI_FOR_USER" >/dev/null || die "no such user: $AI_FOR_USER"
                undo_system_mode ;;
        user)   is_root && die "--user runs as the target user, never as root"
                undo_user_mode ;;
        all)    is_root && die "as root use: $0 --for-user <user>"
                undo_all_mode ;;
    esac
    [ -n "$PURGE" ] && say "
The repo work tree is kept. To remove it too:  git -C ~/.dotfiles worktree remove ~/.dotfiles-ai"
    summary
}

# ---------------------------------------------------------------- record undo (default level)

undo_user_state() {
    if [ -f "$AI_STATE_FILE" ]; then aiconf status || true; aiconf undo --skip-tools; ok "user changes undone (tools kept)"
    else skip "no user state in $AI_STATE_FILE"; fi
    [ "$AI_DRY_RUN" = 1 ] || rm -f "$AI_STATE_DIR"/ai-core.*.hash
}

hermes_state_exists() {
    hermes_exists && sudo -n -u "$HERMES_USER" test -f "$(hermes_home)/.local/state/ai/managed-keys.json" 2>/dev/null
}

undo_hermes_state() {
    # undo_hermes_state [--only-tools]
    local pass=${1:---skip-tools}
    if hermes_state_exists; then aiconf_hermes undo "$pass" && ok "hermes: undo $pass"
    else skip "no Hermes state"; fi
}

undo_system_state() {
    # undo_system_state [--only-tools]
    local pass=${1:---skip-tools}
    if [ "$AI_OS" = linux ] && sudo -n test -f "$AI_SYSTEM_STATE_FILE" 2>/dev/null; then
        if [ ! -f "$AI_ROOT_HELPER" ]; then
            warn "root helper $AI_ROOT_HELPER missing: system state kept (re-run install once, then uninstall)"
            return 0
        fi
        aiconf_root undo "$pass" && ok "system: undo $pass"
    else
        skip "no system state"
    fi
}

# ---------------------------------------------------------------- purge helpers

# Folders the purge deletes, relative to a home. Fixed list: nothing outside it is ever removed.
purge_rel_user() {
    printf '%s\n' .claude .claude.json .codex .config/opencode .serena .cache/graphify .cache/graphify-queries.log \
        .local/state/ai .config/ai .local/share/ai
}
purge_rel_hermes() {
    printf '%s\n' .hermes .serena .local/state/ai .local/share/ai .config/ai
}

# Existing paths for one home, as that user. purge_existing <home> <as-user-or-empty> <rel list fn>
purge_existing() {
    local home=$1 who=$2 fn=$3 rel p
    case "$home" in /|"") return 0 ;; esac
    for rel in $($fn); do
        p="$home/$rel"
        case "$p" in "$home/.dotfiles"|"$home/.dotfiles/"*|"$home/.dotfiles-ai"|"$home/.dotfiles-ai/"*) continue ;; esac
        if [ -n "$who" ]; then sudo -n -u "$who" test -e "$p" -o -L "$p" 2>/dev/null && printf '%s\n' "$rel"
        elif [ -e "$p" ] || [ -L "$p" ]; then printf '%s\n' "$rel"; fi
    done
    return 0
}

# Backup tarball first (mode 600, owned by that user). purge_backup <home> <as-user-or-empty> <rels...>
purge_backup() {
    local home=$1 who=$2; shift 2
    local out="$home/ai-backup-$STAMP.tar.gz"
    [ $# -gt 0 ] || { info "nothing to back up in $home"; return 0; }
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] backup $out (mode 600) with: $*"; return 0; fi
    local cmd="umask 077 && tar -czf $(quote "$out") -C $(quote "$home") $(quote "$@") && chmod 600 $(quote "$out")"
    if [ -n "$who" ]; then sudo -u "$who" -H sh -c "$cmd"; else sh -c "$cmd"; fi \
        || die "backup $out failed: nothing deleted"
    ok "backup $out ($(du -h "$out" 2>/dev/null | cut -f1 || echo '?'), mode 600)"
}

purge_delete() {
    # purge_delete <home> <as-user-or-empty> <rels...>
    local home=$1 who=$2 rel; shift 2
    for rel in "$@"; do
        if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] rm -rf $home/$rel"; continue; fi
        if [ -n "$who" ]; then sudo -u "$who" -H rm -rf -- "$home/$rel"; else rm -rf -- "$home/$rel"; fi
    done
    [ $# -eq 0 ] || ok "deleted ${#} config/state paths in $home"
}

confirm_purge() {
    [ "$AI_DRY_RUN" = 1 ] && { info "(dry run: no prompt, nothing deleted)"; return 0; }
    local ans
    printf "\nType 'purge' to back up (done above) and delete everything listed: "
    read -r ans || ans=""
    [ "$ans" = purge ] || { say "not confirmed: nothing deleted (the backup tarball stays)"; exit 1; }
}

show_list() {
    local title=$1; shift
    printf '\n%s\n' "$title"
    [ $# -gt 0 ] || { printf '  (none)\n'; return 0; }
    local x; for x in "$@"; do printf '  %s\n' "$x"; done
}

# Tools --purge-all removes, from the records (only what this installer installed).
purge_tool_list() {
    local f
    for f in "$@"; do
        [ -n "$f" ] || continue
        python3 -I "${AI_ROOT_HELPER_RO:-$AI_HOME/ai/lib/aiconf.py}" --state "$f" tools 2>/dev/null | cut -f2 | sed 's/^/  /'
    done
    return 0
}

# ---------------------------------------------------------------- modes

# The user's part never calls sudo.
undo_user_mode() {
    local home=$HOME rels=""
    if [ -n "$PURGE" ]; then
        rels=$(purge_existing "$home" "" purge_rel_user)
        STEP_TOTAL=4
        step "backup"; purge_backup "$home" "" $rels
        show_list "Will delete (in $home):" $rels
        if [ "$PURGE" = all ]; then
            printf '\nWill uninstall (recorded tools in your state):\n'; purge_tool_list "$AI_STATE_FILE"
            info "system tools (npm -g, /usr/local/bin, /opt, docs service) need admin: $(admin_cmd | sed 's/install.sh/uninstall.sh/') --purge-all"
        fi
        confirm_purge
    else
        STEP_TOTAL=1
        say "This removes what install.sh recorded for $(id -un). Other content in the same files stays."
        [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes for $(id -un)?" n || { say "cancelled"; exit 0; }
    fi
    step "your files and registrations"; undo_user_state
    if [ -n "$PURGE" ]; then
        if [ "$PURGE" = all ] && [ -f "$AI_STATE_FILE" ]; then aiconf undo --only-tools; ok "your recorded tools removed"; fi
        step "delete config/state"; purge_delete "$home" "" $rels
    else
        manual "kept on purpose: ~/.config/ai/secrets.env, logins, ~/.serena, plugin data dirs, installed tools"
    fi
}

# Admin: the user part as that user first (from the root-owned copy), then Hermes, then system.
undo_system_mode() {
    local uhome hhome="" urels="" hrels="" copy="$AI_ROOT_REPO/uninstall.sh" args="--user --yes"
    uhome=$(getent passwd "$AI_FOR_USER" | cut -d: -f6)
    hermes_exists && hhome=$(hermes_home)
    [ -x "$copy" ] || copy="$AI_HOME/uninstall.sh"
    [ "$AI_DRY_RUN" = 1 ] && args="$args --dry-run"
    STEP_TOTAL=4

    if [ -n "$PURGE" ]; then
        STEP_TOTAL=7
        urels=$(purge_existing "$uhome" "$AI_FOR_USER" purge_rel_user)
        [ -n "$hhome" ] && hrels=$(purge_existing "$hhome" "$HERMES_USER" purge_rel_hermes)
        step "backups (one per user, owned by that user)"
        purge_backup "$uhome" "$AI_FOR_USER" $urels
        [ -n "$hhome" ] && purge_backup "$hhome" "$HERMES_USER" $hrels
        show_list "Will delete (in $uhome):" $urels
        [ -n "$hhome" ] && show_list "Will delete (in $hhome):" $hrels
        if [ "$PURGE" = all ]; then
            printf '\nWill uninstall (recorded by this installer):\n'
            AI_ROOT_HELPER_RO=$AI_ROOT_HELPER purge_tool_list "$AI_SYSTEM_STATE_FILE" \
                "$uhome/.local/state/ai/managed-keys.json" ${hhome:+"$hhome/.local/state/ai/managed-keys.json"}
            printf '  docs service data: /var/lib/private/ai-docs-mcp /var/lib/ai-docs-mcp (if present)\n'
            dpkg -s claude-code >/dev/null 2>&1 && printf '\nKept: claude-code (apt): not installed by this installer.\n'
        fi
        confirm_purge
    else
        say "Removing what install.sh recorded for $AI_FOR_USER, Hermes and the system layer (tools kept)."
        [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes?" n || { say "cancelled"; exit 0; }
    fi

    step "user part as $AI_FOR_USER"
    # shellcheck disable=SC2086
    sudo -u "$AI_FOR_USER" -H "$copy" $args || warn "user part for $AI_FOR_USER failed: see above"
    step "Hermes user"; undo_hermes_state
    step "system files"; undo_system_state

    if [ "$PURGE" = all ]; then
        step "recorded tools"
        if [ "$AI_DRY_RUN" != 1 ] && [ -f "$uhome/.local/state/ai/managed-keys.json" ]; then
            sudo -u "$AI_FOR_USER" -H python3 -I "$AI_ROOT_HELPER" --state "$uhome/.local/state/ai/managed-keys.json" undo --only-tools || true
        fi
        undo_hermes_state --only-tools
        undo_system_state --only-tools
        run rm -rf /var/lib/private/ai-docs-mcp /var/lib/ai-docs-mcp
    fi
    if [ -n "$PURGE" ]; then
        step "delete config/state"
        purge_delete "$uhome" "$AI_FOR_USER" $urels
        [ -n "$hhome" ] && purge_delete "$hhome" "$HERMES_USER" $hrels
    fi
    step "root-owned copy"
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] rm -rf /usr/local/lib/ai"
    else rm -rf /usr/local/lib/ai && ok "removed /usr/local/lib/ai"; fi
}

# macOS, or a Linux user with sudo: everything from one process.
undo_all_mode() {
    local home=$HOME rels="" hhome="" hrels=""
    if [ ! -f "$AI_STATE_FILE" ] && [ ! -f "$AI_SYSTEM_STATE_FILE" ] && [ -z "$PURGE" ]; then
        say "nothing recorded: no install state found"; exit 0
    fi
    STEP_TOTAL=3
    if [ -n "$PURGE" ]; then
        STEP_TOTAL=6
        rels=$(purge_existing "$home" "" purge_rel_user)
        if hermes_exists && sudo -n true 2>/dev/null; then
            hhome=$(hermes_home); hrels=$(purge_existing "$hhome" "$HERMES_USER" purge_rel_hermes)
        fi
        step "backups"
        purge_backup "$home" "" $rels
        [ -n "$hhome" ] && purge_backup "$hhome" "$HERMES_USER" $hrels
        show_list "Will delete (in $home):" $rels
        [ -n "$hhome" ] && show_list "Will delete (in $hhome):" $hrels
        if [ "$PURGE" = all ]; then
            printf '\nWill uninstall (recorded by this installer):\n'
            purge_tool_list "$AI_STATE_FILE"
            [ -f "$AI_SYSTEM_STATE_FILE" ] && AI_ROOT_HELPER_RO=$AI_ROOT_HELPER purge_tool_list "$AI_SYSTEM_STATE_FILE"
        fi
        confirm_purge
    else
        say "This removes what install.sh recorded (tools kept). Other content in the same files stays."
        aiconf status || true
        [ "$AI_DRY_RUN" = 1 ] || confirm "Undo all recorded changes?" n || { say "cancelled"; exit 0; }
    fi
    # Ask for the sudo password once, up front, when any recorded undo needs root.
    if [ "$AI_DRY_RUN" != 1 ] && [ "$AI_OS" = linux ] \
        && { [ -e "$AI_SYSTEM_STATE_FILE" ] || grep -q '"sudo"' "$AI_STATE_FILE" 2>/dev/null || hermes_exists; }; then
        sudo -v
    fi
    step "your files and registrations"; undo_user_state
    step "Hermes user"; undo_hermes_state
    step "system files (Ubuntu)"; undo_system_state
    if [ "$PURGE" = all ]; then
        step "recorded tools"
        [ -f "$AI_STATE_FILE" ] && aiconf undo --only-tools
        undo_hermes_state --only-tools
        undo_system_state --only-tools
    fi
    if [ -n "$PURGE" ]; then
        step "delete config/state"
        purge_delete "$home" "" $rels
        [ -n "$hhome" ] && purge_delete "$hhome" "$HERMES_USER" $hrels
    else
        manual "kept on purpose: ~/.config/ai/secrets.env, logins, ~/.serena, plugin data dirs, installed tools"
    fi
    if [ "$AI_OS" = linux ] && [ "$AI_DRY_RUN" != 1 ] && [ -d /usr/local/lib/ai ]; then sudo rm -rf /usr/local/lib/ai; fi
    return 0
}

main "$@"
