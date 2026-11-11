#!/usr/bin/env bash
# install.sh: the AI setup of the `ai` branch for macOS and Ubuntu (SPEC.md, sections 1 and 20).
#
#   ./install.sh [--dry-run] [--agents claude,codex,hermes,opencode,herdr] [--skip-packages]
#                [--rtk-hook] [--docs-server] [--yes]
#
# Distribution = each agent's own extension points (plugins, `mcp add`, `config set`). Our own
# merge code only writes managed blocks, single keys and links, and records every change in
# ~/.local/state/ai/managed-keys.json (system files: /var/lib/ai/managed-keys.json) for uninstall.sh.
# Idempotent: a second run changes nothing. Run as your normal user (sudo is used where needed).
set -euo pipefail

AI_HOME=$(cd "$(dirname "$0")" && pwd -P)
export AI_HOME

usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

AI_DRY_RUN=0 AI_YES=0 AI_SKIP_PACKAGES=0 AI_RTK_HOOK=0 AI_DOCS_SERVER=0 AGENTS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) AI_DRY_RUN=1 ;;
        --yes|-y) AI_YES=1 ;;
        --skip-packages) AI_SKIP_PACKAGES=1 ;;
        --rtk-hook) AI_RTK_HOOK=1 ;;
        --docs-server) AI_DOCS_SERVER=1 ;;
        --agents) [ $# -ge 2 ] || usage 1; AGENTS=$2; shift ;;
        --agents=*) AGENTS=${1#--agents=} ;;
        -h|--help) usage 0 ;;
        *) printf 'unknown option: %s\n' "$1" >&2; usage 1 ;;
    esac
    shift
done
export AI_DRY_RUN AI_YES AI_SKIP_PACKAGES AI_RTK_HOOK

. "$AI_HOME/ai/lib/common.sh"
for f in base tools claude codex hermes opencode herdr; do . "$AI_HOME/ai/adapters/$f.sh"; done

want() { case ",$AGENTS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

main() {
    detect_os
    is_root && die "run as your normal user, not root (sudo is used where needed)"
    load_pins
    first_question
    pick_agents

    say "AI setup from $AI_HOME on $AI_OS ($AI_ARCH). Agents: ${AGENTS:-none}."
    [ "$AI_DRY_RUN" = 1 ] && say "DRY RUN: commands are printed, nothing is changed."
    [ "$AI_OS" = linux ] && [ "$AI_DRY_RUN" != 1 ] && sudo -v

    STEP_TOTAL=13
    [ "$AI_DOCS_SERVER" = 1 ] && STEP_TOTAL=14

    step "prerequisites (git, jq, python3, node, npm, uv, curl)";  base_prereqs
    step "pins (ai/pins.env is the only source of versions)";    base_pins
    step "links (~/.dotfiles-ai, ~/.config/ai, ~/.local/bin, claude-notify)"; base_links
    step "render AGENTS.md and routing data (ai-render)";        base_render
    step "agents: pinned harness installs";                     tools_harnesses
    step "tools: Serena, graphify, RTK, GitHub MCP, plugin sources"; tools_cli
    step "MCP servers";                                         do_mcp
    step "plugins (marketplace ai, ai-core, Ponytail, i-have-adhd, claude-seo, claude-blog)"; do_plugins
    step "skills";                                              do_skills
    step "hooks (plugin owns them; vendor hooks: RTK, herdr, graphify)"; do_hooks
    step "root rules (managed blocks; other blocks kept)";      base_rules
    step "environment: telemetry and auto-update off";          base_env
    [ "$AI_DOCS_SERVER" = 1 ] && { step "Grounded Docs server role"; tools_docs_server; }
    step "verify";                                              do_verify

    logins_left
    summary
}

first_question() {
    [ "$AI_OS" = linux ] || return 0
    if confirm_default_no "Is this a new Ubuntu server that needs the base server setup first?"; then
        cat <<'EOF'

Do the base server setup first, from the `ubuntu-server` branch of this repo:
  git clone --branch ubuntu-server <this repo URL> ~/.dotfiles
  then follow ~/.dotfiles/README.md (its last section points back here).
Then add this branch and run this script again:
  git -C ~/.dotfiles worktree add ~/.dotfiles-ai ai && ~/.dotfiles-ai/install.sh
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
    if [ -n "$AGENTS" ]; then return 0; fi
    local list=""
    has claude && list="$list,claude"
    has codex && list="$list,codex"
    hermes_exists && list="$list,hermes"
    # opencode is always installed (SPEC 3); herdr where it exists or on Linux servers.
    list="$list,opencode"
    { has herdr || [ "$AI_OS" = linux ]; } && list="$list,herdr"
    AGENTS=${list#,}
}

do_mcp() {
    base_serena_config
    want claude && claude_mcp
    want codex && codex_mcp
    want hermes && hermes_exists && hermes_mcp
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
    want hermes && hermes_exists && hermes_skills
    return 0
}

do_hooks() {
    want claude && claude_hooks
    want codex && codex_hooks
    want hermes && hermes_exists && hermes_hooks
    want opencode && opencode_hooks
    want herdr && herdr_hooks
    base_webhook_helper
    if [ "$AI_OS" = linux ] && ! has caffeinate; then
        # SessionStart keeps `caffeinate -s -w $PPID`: on Linux a systemd-inhibit wrapper.
        aiconf_root file-put /usr/local/bin/caffeinate "$AI_HOME/ai/adapters/linux/caffeinate" --mode 755
        ok "caffeinate wrapper (systemd-inhibit) in /usr/local/bin"
    fi
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
    for t in claude codex opencode omc serena graphify rtk herdr github-mcp-server; do
        if has "$t"; then info "$t: $("$t" --version 2>/dev/null | head -n1)"; fi
    done
    return 0
}

logins_left() {
    want claude && manual "log in once: claude (then /login)"
    want codex && manual "log in once: codex login --device-auth"
    want hermes && hermes_exists && manual "Hermes: Codex login by device code as $HERMES_USER; Discord token and allowed users in its secrets"
    has gh && ! gh auth status >/dev/null 2>&1 && manual "log in once: gh auth login"
    return 0
}

main "$@"
