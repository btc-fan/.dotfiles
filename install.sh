#!/usr/bin/env bash
# install.sh: the AI setup of the `ai` branch for macOS and Ubuntu (SPEC.md, sections 1 and 20).
#
#   Ubuntu server (admin, always from the root-owned clone /opt/ai-setup, never from a user's home):
#     sudo git clone --branch ai <repo URL> /opt/ai-setup                         (once)
#     sudo /opt/ai-setup/install.sh --update --for-user <user> [options]    (fetch + fast-forward, then run)
#   User part alone (testing; never calls sudo):   ~/.dotfiles-ai/install.sh --user [options]
#   macOS, or a Linux user with sudo (one process): ~/.dotfiles-ai/install.sh [options]
#
#   options: [--dry-run] [--agents claude,codex,hermes,opencode,herdr] [--skip-packages]
#            [--allow-dirty] [--yes] [--keep-claudeai-connectors]   env: AI_OMC_WIRING=plugin|cli|remove
#
# Distribution = each agent's own extension points (plugins, `mcp add`, `config set`). Our own merge
# code only writes managed blocks, single keys and links, and records every change for uninstall.sh
# (user: ~/.local/state/ai/managed-keys.json, system: /var/lib/ai/managed-keys.json).
# Root runs only a root-owned copy of the pushed branch (--allow-dirty: development only).
# Idempotent: a second run changes nothing.
set -euo pipefail

AI_HOME=$(cd "$(dirname "$0")" && pwd -P)
AI_SRC_HOME=${AI_SRC_HOME:-$AI_HOME}   # the user's work tree (set by the system part)
export AI_HOME AI_SRC_HOME

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

AI_DRY_RUN=0 AI_YES=0 AI_SKIP_PACKAGES=0 AI_DOCS_SERVER=0 AI_ALLOW_DIRTY=0 AGENTS=""
AI_MODE=all AI_FOR_USER="" AI_UPDATE=0
AI_ARGS=("$@")
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) AI_DRY_RUN=1 ;;
        --yes|-y) AI_YES=1 ;;
        --skip-packages) AI_SKIP_PACKAGES=1 ;;
        --docs-server) printf 'note: --docs-server is gone (Grounded Docs was dropped; install removes it)\n' >&2 ;;
        --allow-dirty) AI_ALLOW_DIRTY=1 ;;
        --update) AI_UPDATE=1 ;;
        --keep-claudeai-connectors) AI_CLAUDEAI_CONNECTORS=keep ;;
        --user) AI_MODE=user ;;
        --for-user) [ $# -ge 2 ] || usage 1; AI_MODE=system; AI_FOR_USER=$2; shift ;;
        --for-user=*) AI_MODE=system; AI_FOR_USER=${1#--for-user=} ;;
        --agents) [ $# -ge 2 ] || usage 1; AGENTS=$2; shift ;;
        --agents=*) AGENTS=${1#--agents=} ;;
        -h|--help) usage 0 ;;
        *) printf 'unknown option: %s\n' "$1" >&2; usage 1 ;;
    esac
    shift
done
AI_CLAUDEAI_CONNECTORS=${AI_CLAUDEAI_CONNECTORS:-}
export AI_DRY_RUN AI_YES AI_SKIP_PACKAGES AI_ALLOW_DIRTY AI_MODE AI_FOR_USER AI_CLAUDEAI_CONNECTORS

# Root never runs code from a tree another user can change. This first check uses no file of the tree;
# ai/lib/root-guard.sh (sourced only after it passed) adds the file, clean-tree and pushed-commit checks.
if [ "$(id -u)" -eq 0 ]; then
    _owner=$(stat -c %U "$AI_HOME" 2>/dev/null || stat -f %Su "$AI_HOME" 2>/dev/null || echo unknown)
    if { [ "$_owner" != root ] && [ "$_owner" != "${SUDO_USER:-}" ]; } || [ "$_owner" = "${AI_FOR_USER:-}" ]; then
        printf 'ERROR: refusing to run as root from %s (owned by %s). Root runs only the root-owned clone:\n' "$AI_HOME" "$_owner" >&2
        printf '  sudo git clone --branch ai <repo URL> /opt/ai-setup    (once)\n' >&2
        printf '  sudo /opt/ai-setup/install.sh --update --for-user <user>\n' >&2
        exit 1
    fi
    . "$AI_HOME/ai/lib/root-guard.sh"
    if [ "$AI_UPDATE" = 1 ]; then
        # Fetch + fast-forward the root-owned clone, then run the updated install.sh (without --update).
        ai_update_clone "$AI_HOME" "${AI_ALLOW_DIRTY:-0}"
        _args=()
        for _a in ${AI_ARGS[@]+"${AI_ARGS[@]}"}; do [ "$_a" = --update ] || _args+=("$_a"); done
        exec bash "$AI_HOME/install.sh" ${_args[@]+"${_args[@]}"}
    fi
    ai_root_guard "$AI_HOME" "${AI_FOR_USER:-}" "${AI_ALLOW_DIRTY:-0}" "$(basename "$0")"
elif [ "$AI_UPDATE" = 1 ]; then
    printf 'ERROR: --update is for the root-owned clone: sudo /opt/ai-setup/install.sh --update ...\n' >&2
    exit 1
fi

. "$AI_HOME/ai/lib/common.sh"

want() { case ",$AGENTS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

main() {
    detect_os
    check_mode
    [ "$AI_MODE" = system ] && setup_system_target
    for f in base tools claude codex hermes opencode herdr; do . "$AI_HOME/ai/adapters/$f.sh"; done
    load_pins
    [ "$AI_MODE" = user ] || first_question
    pick_agents

    say "AI setup ($AI_MODE mode${AI_FOR_USER:+ for $AI_FOR_USER}) from $AI_HOME on $AI_OS ($AI_ARCH). Agents: ${AGENTS:-none}."
    [ "$AI_DRY_RUN" = 1 ] && say "DRY RUN: commands are printed, nothing is changed."

    case "$AI_MODE" in
        system) run_system ;;
        user)   run_user ;;
        all)    sudo_ready || exit 1; run_all ;;
    esac
    [ "$AI_MODE" = system ] || logins_left
    summary
}

check_mode() {
    case "$AI_MODE" in
        system)
            [ "$AI_OS" = linux ] || die "--for-user is for Ubuntu servers (admin installs for a user)"
            is_root || die "--for-user runs as root: sudo $0 --for-user $AI_FOR_USER"
            getent passwd "$AI_FOR_USER" >/dev/null || die "no such user: $AI_FOR_USER"
            [ "$AI_FOR_USER" != root ] || die "--for-user root is not supported"
            ;;
        user) is_root && die "--user runs as the target user, never as root" ;;
        all)
            if is_root; then
                die "as root use: $0 --for-user <user> (root steps here, user part as that user)"
            fi
            ;;
    esac
    return 0
}

# Admin mode: the target user's paths, then a root-owned copy of the user's work tree (S7).
setup_system_target() {
    AI_TARGET_HOME=$(getent passwd "$AI_FOR_USER" | cut -d: -f6)
    export AI_TARGET_HOME
    AI_STATE_DIR=/var/lib/ai
    AI_STATE_FILE=$AI_SYSTEM_STATE_FILE
    root_prepare "$AI_HOME" || exit 1     # the admin clone this script runs from (root-guard checked it)
}

# ---------------------------------------------------------------- the three modes

# Root steps only (admin, for one user). Ends by running the user part as that user.
run_system() {
    STEP_TOTAL=9
    step "prerequisites (apt)";                                  base_prereqs
    step "pins (ai/pins.env is the only source of versions)";    base_pins
    step "render AGENTS.md and routing data in the root-owned copy"; base_render
    step "agents: pinned harness installs (system-wide)";        tools_harnesses
    step "system tools: RTK (built as $AI_FOR_USER), GitHub MCP, plugin sources"; tools_system
    step "system layer: /etc env, managed settings, admin rules, webhook helper"; do_system_layer
    step "Hermes (user $HERMES_USER)";                           do_hermes
    step "dropped tools: Grounded Docs server, GitHub MCP binary"; tools_drop_system
    step "user part as $AI_FOR_USER";                            run_user_part
}

# Everything that lives in the user's home. Never calls sudo.
run_user() {
    STEP_TOTAL=13
    step "prerequisites (check only)";                           base_prereqs
    step "pins (ai/pins.env is the only source of versions)";    base_pins
    step "links (~/.dotfiles-ai, ~/.config/ai, ~/.local/bin, claude-notify)"; base_links
    step "render AGENTS.md and routing data (ai-render)";        base_render
    step "user tools: Serena, graphify, context7";               tools_user
    step "MCP servers";                                         do_mcp
    step "plugins (marketplace ai, ai-core, Ponytail, i-have-adhd, claude-seo, claude-blog)"; do_plugins
    step "skills";                                              do_skills
    step "hooks (plugin owns them; vendor hooks: RTK, herdr, graphify)"; do_hooks
    step "root rules (managed blocks; other blocks kept)";      base_rules_user
    step "environment: telemetry and auto-update off";          base_env_user
    step "git hooks: ai-sync after each pull";                  base_sync_hook
    step "verify";                                              do_verify
}

# macOS, or a Linux user with sudo: one process, today's behaviour.
run_all() {
    STEP_TOTAL=14
    [ "$AI_OS" = linux ] && STEP_TOTAL=16
    if pgrep -x claude >/dev/null 2>&1; then
        warn "a Claude session is running: settings are written atomically, restart the session after install"
    fi
    step "prerequisites (git, jq, python3, node, npm, uv, curl)";  base_prereqs
    step "pins (ai/pins.env is the only source of versions)";    base_pins
    step "links (~/.dotfiles-ai, ~/.config/ai, ~/.local/bin, claude-notify)"; base_links
    step "render AGENTS.md and routing data (ai-render)";        base_render
    step "agents: pinned harness installs";                     tools_harnesses
    step "tools: RTK, GitHub MCP, plugin sources, Serena, graphify, context7"; tools_system; tools_user
    step "MCP servers";                                         do_mcp
    step "plugins (marketplace ai, ai-core, Ponytail, i-have-adhd, claude-seo, claude-blog)"; do_plugins
    step "skills";                                              do_skills
    step "hooks (plugin owns them; vendor hooks: RTK, herdr, graphify)"; do_hooks
    step "root rules (managed blocks; other blocks kept)";      base_rules_user
    step "environment: telemetry and auto-update off";          base_env_user
    if [ "$AI_OS" = linux ]; then
        step "system layer: /etc env, managed settings, admin rules, webhook helper"; do_system_layer
        step "Hermes (user $HERMES_USER)";                       do_hermes
    fi
    step "git hooks: ai-sync after each pull";                  base_sync_hook
    [ "$AI_OS" = linux ] && tools_drop_system
    step "verify";                                              do_verify
}

# Admin mode: run the root-owned copy's user part as the target user (it never calls sudo).
run_user_part() {
    local args="--user --yes"
    [ "$AI_DRY_RUN" = 1 ] && args="$args --dry-run"
    [ "$AI_SKIP_PACKAGES" = 1 ] && args="$args --skip-packages"
    [ "$AI_CLAUDEAI_CONNECTORS" = keep ] && args="$args --keep-claudeai-connectors"
    [ -n "$AGENTS" ] && args="$args --agents $(printf '%s' "$AGENTS" | sed 's/,*hermes//; s/^,//')"
    info "running as $AI_FOR_USER: $AI_HOME/install.sh $args"
    # shellcheck disable=SC2086
    # AI_SRC_HOME for the user part = that user's own work tree (links, pull hook), never the admin clone.
    if sudo -u "$AI_FOR_USER" -H env AI_SRC_HOME="$AI_TARGET_HOME/.dotfiles-ai" AI_OMC_WIRING="${AI_OMC_WIRING:-plugin}" \
        AI_CLAUDEAI_CONNECTORS="${AI_CLAUDEAI_CONNECTORS:-}" "$AI_HOME/install.sh" $args; then
        ok "user part for $AI_FOR_USER"
    else
        warn "user part for $AI_FOR_USER failed: see its output above"
    fi
}

# ---------------------------------------------------------------- step groups

first_question() {
    [ "$AI_OS" = linux ] || return 0
    if confirm_default_no "Is this a new Ubuntu server that needs the base server setup first?"; then
        cat <<'EOF'

Do the base server setup first, from the `ubuntu-server` branch of this repo:
  git clone --branch ubuntu-server <this repo URL> ~/.dotfiles
  then follow ~/.dotfiles/README.md (its last section points back here).
Then add this branch as the user, and let admin run this script for that user:
  git -C ~/.dotfiles worktree add ~/.dotfiles-ai ai
  sudo /opt/ai-setup/install.sh --update --for-user <user>     (as admin, root-owned clone)
EOF
        exit 0
    fi
}

# "Yes" must be typed; --yes and non-interactive runs answer No here.
confirm_default_no() {
    local ans
    [ "$AI_YES" = 1 ] && return 1
    [ -t 0 ] || return 1
    printf '%s [y/N] ' "$1"
    read -r ans || ans=""
    case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

pick_agents() {
    if [ -n "$AGENTS" ]; then
        [ "$AI_MODE" = user ] && AGENTS=$(printf '%s' "$AGENTS" | sed 's/,*hermes//; s/^,//')
        return 0
    fi
    local list=""
    has claude && list="$list,claude"
    has codex && list="$list,codex"
    [ "$AI_MODE" != user ] && hermes_exists && list="$list,hermes"
    # opencode is always installed (SPEC 3); herdr where it exists or on Linux servers.
    list="$list,opencode"
    { has herdr || [ "$AI_OS" = linux ]; } && list="$list,herdr"
    AGENTS=${list#,}
}

do_system_layer() {
    base_env_system
    base_admin_layer
    base_webhook_helper
    # ai-info for every user (also hermes, whose PATH has no ~/.local/bin of ours): a link to the root-owned
    # copy. Only in system mode, where AI_HOME is that root-owned copy.
    if [ "$AI_MODE" = system ] && [ -f "$AI_HOME/ai/bin/ai-info" ]; then
        aiconf_root link /usr/local/bin/ai-info "$AI_HOME/ai/bin/ai-info"
    fi
    # Owner-only gate skip: a root-owned copy (sudo must never run a user-writable script).
    aiconf_root file-put /usr/local/sbin/ai-gate-skip "$AI_HOME/ai/hooks/root/ai-gate-skip" --mode 755
    codex_system_hooks
    codex_system_policy
    # The ai-core SessionStart caffeinate hook runs on macOS only now: no Linux wrapper is installed.
    # One that an earlier install put in /usr/local/bin is removed by uninstall.sh (recorded file).
    return 0
}

do_hermes() {
    if ! want hermes || ! hermes_exists; then skip "Hermes: user $HERMES_USER not present or not selected"; return 0; fi
    hermes_mcp
    hermes_skills
    hermes_hooks
    if [ -f "$AI_HOME/ai/AGENTS.md" ]; then hermes_rules; else warn "Hermes rules: ai/AGENTS.md not built"; fi
    hermes_env
    return 0
}

do_mcp() {
    base_serena_config
    tools_drop_user
    want claude && claude_mcp
    want codex && codex_mcp
    want opencode && opencode_mcp
    return 0
}

do_plugins() {
    want claude && claude_plugins
    want codex && codex_plugins
    return 0
}

do_skills() {
    want claude && claude_skills
    { want codex || want opencode; } && codex_skills
    return 0
}

do_hooks() {
    want claude && claude_hooks
    want codex && codex_hooks
    want opencode && opencode_hooks
    want herdr && herdr_hooks
    return 0
}

do_verify() {
    local doctor="$AI_HOME/ai/bin/ai-doctor"
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] $doctor --quick"; return 0; fi
    if [ -x "$doctor" ]; then
        if "$doctor" --quick; then ok "ai-doctor --quick passed"; else warn "ai-doctor --quick reported problems (see above)"; fi
    else
        warn "ai/bin/ai-doctor missing (agent B): no verify run"
    fi
    local t
    for t in claude codex opencode omc serena graphify rtk herdr gh; do
        if has "$t"; then info "$t: $("$t" --version 2>/dev/null | head -n1)"; fi
    done
    return 0
}

logins_left() {
    want claude && manual "log in once: claude (then /login)"
    want codex && manual "log in once: codex login --device-auth"
    if [ "$AI_MODE" = all ] && want hermes && hermes_exists; then
        manual "Hermes: Codex login by device code as $HERMES_USER; Discord token and allowed users in its secrets"
    fi
    has gh && ! gh auth status >/dev/null 2>&1 && manual "log in once: gh auth login"
    return 0
}

main "$@"
