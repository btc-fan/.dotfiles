# ai/adapters/base.sh: prerequisites, sources (newest stable per tool), links, render, root rules, environment.
# Sourced by install.sh. Uses ai/lib/common.sh. bash 3.2.

PLUGIN_DIR() { printf '%s' "$AI_HOME/ai/marketplace/plugins/ai-core"; }
CLAUDE_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
CODEX_DIR=${CODEX_HOME:-$HOME/.codex}
OPENCODE_JSON="$HOME/.config/opencode/opencode.json"
# The user the setup is for: yourself, or --for-user <user> when admin runs the system part as root.
AI_TARGET_HOME=${AI_TARGET_HOME:-$HOME}
HOSTING_DOC="$AI_TARGET_HOME/.dotfiles/docs/AGENTS-hosting.md"

# ---------------------------------------------------------------- 1 prerequisites

# base_nvm_path: node from nvm is on PATH only in an interactive shell (.zshrc). In a login or ssh shell the
# install did not find it and ran `brew install node`, which builds llvm from source on macOS 12 (old Mac,
# 2026-11-15). Put nvm's node on PATH first: the `current` link, else the default alias, else the newest one.
base_nvm_path() {
    has node && return 0
    local d="${NVM_DIR:-$HOME/.nvm}" bin="" v
    [ -d "$d/versions/node" ] || return 0
    if [ -x "$d/current/bin/node" ]; then bin="$d/current/bin"
    else
        # The default alias is a version ("24", "v24.18.0") or a name ("lts/*", "node"): a name means the newest.
        v=$(cat "$d/alias/default" 2>/dev/null || true)
        case "$v" in [0-9]*|v[0-9]*) bin=$(ls -d "$d/versions/node/v${v#v}"*/bin 2>/dev/null | base_newest_version || true) ;; esac
        [ -n "$bin" ] || bin=$(ls -d "$d"/versions/node/v*/bin 2>/dev/null | base_newest_version || true)
    fi
    [ -n "$bin" ] && [ -x "$bin/node" ] || return 0
    PATH="$bin:$PATH"; export PATH
    info "node from nvm: $bin"
}

# base_newest_version: the line with the highest .../vX.Y.Z/... (no `sort -V`: macOS 12 sort does not have it).
base_newest_version() {
    awk '{ if (match($0, /\/v[0-9]+\.[0-9]+\.[0-9]+/)) { split(substr($0, RSTART + 2, RLENGTH - 2), a, ".")
           printf "%06d%06d%06d %s\n", a[1], a[2], a[3], $0 } }' | sort | tail -n 1 | cut -d' ' -f2-
}

base_prereqs() {
    local missing="" c
    base_nvm_path
    for c in git jq python3 node npm uv curl; do has "$c" || missing="$missing $c"; done
    if has python3 && ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
        die "python3 3.9 or newer is needed"
    fi
    if has node; then
        local nv; nv=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
        [ "$nv" -ge "$NODE_MAJOR_MIN" ] 2>/dev/null || warn "node $nv is older than $NODE_MAJOR_MIN (Ponytail, i-have-adhd and context7 need a current LTS)"
    fi
    if [ -z "$missing" ]; then ok "prerequisites present"; return 0; fi
    info "missing:$missing"
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "prerequisites:$missing (--skip-packages)"; return 0; fi
    if [ "$AI_MODE" = user ]; then
        manual "missing:$missing. Ask admin to run: $(admin_cmd)"
        return 0
    fi
    case "$AI_OS" in
        macos)
            # brew only for missing CLIs; never `brew upgrade`.
            has brew || { manual "install Homebrew, then re-run (missing:$missing)"; return 0; }
            local pkgs=""
            for c in $missing; do case "$c" in npm) ;; node) pkgs="$pkgs node" ;; *) pkgs="$pkgs $c" ;; esac; done
            if confirm "brew install$pkgs ?" n; then run brew install $pkgs && ok "brew install$pkgs"
            else manual "brew install$pkgs"; fi
            ;;
        linux)
            local apt="" rest=""
            for c in $missing; do
                case "$c" in git|jq|python3|curl) apt="$apt $c" ;; *) rest="$rest $c" ;; esac
            done
            if [ -n "$apt" ] && ! root_layer; then manual "ask the admin: sudo apt-get install -y$apt"
            elif [ -n "$apt" ]; then run_root apt-get install -y -q $apt && ok "apt-get install$apt"; fi
            # node (NodeSource) and uv (sha256-checked release) come from the ubuntu-server base branch
            if [ -n "$rest" ]; then
                manual "install$rest with the ubuntu-server base setup (signed repo / checksummed release), then re-run"
            fi
            ;;
    esac
    return 0
}

# ---------------------------------------------------------------- 2 sources (ai/pins.env)

# ai/pins.env names where each tool comes from; the steps below install the newest stable release (owner
# decision 2026-11-14). This step resolves every tool once (one network round, kept for this run in
# AI_RESOLVE_MEMO) and prints what each one resolves to.
base_pins() {
    local bad=0 p nw=""
    p=$(PLUGIN_DIR)
    # context7.sh finds the installed version folder itself: a fixed version line there goes stale on the next update.
    if grep -qE '^[[:space:]]*v=[0-9]' "$p/mcp/context7.sh"; then
        warn "$p/mcp/context7.sh has a fixed version line: it must find the installed version"; bad=1
    fi
    # No runtime downloads: no npx, @latest or curl|sh in the plugin or the project MCP template.
    if grep -rnE '@latest|(^|[^[:alnum:]_-])npx([^[:alnum:]_-]|$)|curl[^|]*\|[[:space:]]*(ba)?sh' \
        "$p/.mcp.json" "$p/mcp" "$AI_HOME/ai/mcp/project" 2>/dev/null \
        | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' | grep -q .; then
        warn "runtime npx, @latest or curl|sh in ai-core or ai/mcp/project"; bad=1
    fi
    [ "$AI_DRY_RUN" = 1 ] && nw=--no-write
    info "newest stable per tool (ai/lib/resolve.py; a <TOOL>_HOLD line in ai/pins.env wins):"
    AI_STATE_DIR="$AI_STATE_DIR" python3 "$AI_HOME/ai/lib/resolve.py" list $nw 2>&1 | sed 's/^/    /' \
        || { warn "resolver failed: each tool keeps what is installed"; bad=1; }
    [ $bad = 0 ] && ok "sources resolved (ai/pins.env)"
    return 0
}

# ---------------------------------------------------------------- 3 links

base_links() {
    local f name exclude

    # Hooks and docs use $HOME/.dotfiles-ai; a work tree elsewhere gets a link there.
    if [ "$AI_HOME" != "$HOME/.dotfiles-ai" ] && [ "${AI_SRC_HOME:-}" != "$HOME/.dotfiles-ai" ]; then
        if [ ! -e "$HOME/.dotfiles-ai" ] || [ -L "$HOME/.dotfiles-ai" ]; then
            aiconf link "$HOME/.dotfiles-ai" "$AI_HOME"
        else
            warn "$HOME/.dotfiles-ai exists and is not $AI_HOME: hooks will use that copy"
        fi
    fi

    # Rules, toolbox and contracts every agent reads by these paths (CLAUDE.md, Codex, Hermes, opencode).
    aiconf link "$HOME/.config/ai/AGENTS.md" "$AI_HOME/ai/AGENTS.md"
    aiconf link "$HOME/.config/ai/TOOLBOX.md" "$AI_HOME/ai/TOOLBOX.md"
    aiconf link "$HOME/.config/ai/rules" "$AI_HOME/ai/rules"
    [ -e "$HOME/.config/ai/rules/serena.md" ] || [ "$AI_DRY_RUN" = 1 ] \
        || warn "$HOME/.config/ai/rules is not our link (a real folder?): agents miss the tool contracts"

    if [ -d "$AI_HOME/ai/bin" ]; then
        for f in "$AI_HOME"/ai/bin/*; do
            [ -f "$f" ] && [ -x "$f" ] || continue
            aiconf link "$HOME/.local/bin/$(basename "$f")" "$f"
        done
    else
        warn "ai/bin is missing (agent B builds it): no commands linked"
    fi

    # Owner's hooks.json path: ~/.dotfiles/bin/claude-notify -> ai/bin/claude-notify
    if [ -d "$HOME/.dotfiles/.git" ] || [ -f "$HOME/.dotfiles/.git" ]; then
        if git -C "$HOME/.dotfiles" ls-files --error-unmatch bin/claude-notify >/dev/null 2>&1; then
            skip "~/.dotfiles/bin/claude-notify is tracked by the base branch: left alone"
        elif [ -x "$AI_HOME/ai/bin/claude-notify" ]; then
            aiconf link "$HOME/.dotfiles/bin/claude-notify" "$AI_HOME/ai/bin/claude-notify"
            exclude=$(git -C "$HOME/.dotfiles" rev-parse --git-path info/exclude 2>/dev/null || echo .git/info/exclude)
            case "$exclude" in /*) ;; *) exclude="$HOME/.dotfiles/$exclude" ;; esac
            aiconf line-add "$exclude" "bin/claude-notify"
        else
            warn "ai/bin/claude-notify missing: ~/.dotfiles/bin/claude-notify not linked"
        fi
    else
        info "no ~/.dotfiles base checkout: claude-notify link skipped (plugin hooks still work)"
    fi

    # Secrets file: names only in the repo.
    local sec="$HOME/.config/ai/secrets.env"
    if [ ! -f "$sec" ]; then
        manual "create $sec: install -m 600 $AI_HOME/secrets.env.example $sec, then fill GITHUB_PERSONAL_ACCESS_TOKEN and CONTEXT7_API_KEY"
    else
        local mode; mode=$(ls -l "$sec" | cut -c1-10)
        [ "$mode" = "-rw-------" ] || warn "$sec mode is $mode: run chmod 600 $sec"
    fi
    ok "links"
}

# ---------------------------------------------------------------- 4 render

base_render() {
    local r="$AI_HOME/ai/bin/ai-render"
    if [ ! -x "$r" ]; then warn "ai/bin/ai-render missing (agent B): AGENTS.md and routing.json not rebuilt"; return 0; fi
    if [ ! -w "$AI_HOME/ai" ] && [ "$AI_DRY_RUN" != 1 ]; then
        info "render: $AI_HOME is read-only here (root-owned copy, rendered by the system part)"
        return 0
    fi
    run "$r" && ok "ai-render: ai/AGENTS.md, ai/build/routing.json, ai/build/L0.md"
    if [ -f "$AI_HOME/ai/AGENTS.md" ]; then
        local size; size=$(wc -c < "$AI_HOME/ai/AGENTS.md" | tr -d ' ')
        [ "$size" -le 30720 ] || warn "ai/AGENTS.md is $size bytes: over the 30 KB cap (SPEC 17)"
    fi
}

# ---------------------------------------------------------------- 7 Serena global config (owner)

base_serena_config() {
    has serena || { skip "Serena config: serena not installed"; return 0; }
    local cfg="${SERENA_HOME:-$HOME/.serena}/serena_config.yml"
    [ -f "$cfg" ] || run serena init </dev/null >/dev/null || { warn "serena init failed"; return 0; }
    # Serena 2.1.0 serena_config.template.yml keys. tools interface (the v2 default REPL runs any Python, and
    # excluded_tools only applies to the tools interface), no second shell, no dashboard or GUI log window.
    aiconf yaml-top-set "$cfg" agent_interface tools
    aiconf yaml-top-set "$cfg" excluded_tools "[execute_shell_command, serena_repl]"
    aiconf yaml-top-set "$cfg" web_dashboard false
    aiconf yaml-top-set "$cfg" web_dashboard_open_on_launch false
    aiconf yaml-top-set "$cfg" gui_log_window false
    aiconf yaml-top-set "$cfg" log_level 30
    aiconf yaml-top-set "$cfg" tool_timeout 240
    # Token use: a tool answer is cut at 40k characters (default 150k), so one broad call cannot fill the context.
    aiconf yaml-top-set "$cfg" default_max_tool_answer_chars 40000
    # No Serena memories and no onboarding (mode no-memories): the repo AGENTS.md Map is the one place for
    # project knowledge; onboarding is a long first-run exploration that writes a second, drifting copy.
    aiconf yaml-top-set "$cfg" default_modes "[no-memories]"
    aiconf yaml-top-set "$cfg" read_only_memory_patterns '["global/.*"]'
    ok "Serena: tools interface, shell + REPL excluded, dashboard/GUI off, log warnings only, answers cut at 40k, no memories/onboarding ($cfg)"
}

# ---------------------------------------------------------------- admin layer (Linux, root-owned)

# House rules in the admin layer that agents cannot edit or exclude (shared-server research, gap 2).
# Root-owned 644 copies, recorded in /var/lib/ai for uninstall. The per-user layer stays (macOS
# source; also kept on Linux). ai-sync calls this too: without passwordless sudo it skips.
# Never set allowManagedHooksOnly (it would block the oh-my-claudecode hooks).
base_admin_layer() {
    root_layer || return 0
    if [ ! -f "$AI_HOME/ai/AGENTS.md" ]; then warn "admin layer: ai/AGENTS.md not built, skipped"; return 0; fi
    if [ "$AI_DRY_RUN" != 1 ] && ! sudo -n true 2>/dev/null; then
        warn "admin layer: no passwordless sudo, /etc copies not refreshed"; return 0
    fi
    local tmp; tmp=$(rules_text_file)
    # Claude: /etc/claude-code/CLAUDE.md (cannot be excluded). managed-settings.json is merged in
    # the environment step (telemetry keys kept, skill budget); nothing else is set there.
    aiconf_root file-put /etc/claude-code/CLAUDE.md "$tmp" --mode 644
    # opencode: managed config dir /etc/opencode/ (file name to confirm with `opencode debug config`).
    if want opencode && has opencode; then
        aiconf_root json-add /etc/opencode/opencode.json instructions '"/etc/claude-code/CLAUDE.md"'
        manual "check that opencode reads /etc/opencode/opencode.json: opencode debug config (file name UNVERIFIED for $(opencode --version 2>/dev/null || echo 'this version'))"
    fi
    rm -f "$tmp"
    # Codex: requirements.toml constrains settings (sandbox, approvals); it has no instructions key,
    # and support at the pinned version is not verified here.
    skip "Codex /etc/codex/requirements.toml: not written here (codex_system_policy writes it in system mode)"
    ok "admin layer: /etc/claude-code/CLAUDE.md (root 644)$(want opencode && has opencode && printf ', /etc/opencode/opencode.json')"
}

# B's git hooks (post-merge, post-rewrite) run ai-sync after a pull in this work tree.
base_sync_hook() {
    # The hook belongs to the user's own work tree (not a root-owned copy).
    local tree="${AI_SRC_HOME:-$AI_HOME}"
    local s="$tree/ai/bin/ai-sync"
    [ -x "$s" ] || { skip "ai-sync hook: $s missing"; return 0; }
    # Note: the hooks dir is the repo's COMMON dir, shared by every worktree of this repo.
    run "$s" --install-hook "$tree" || { warn "ai-sync --install-hook failed: no pull hook"; return 0; }
    aiconf record-cmd ai-sync-hook -- "$s" --uninstall-hook "$tree"
    ok "git hooks post-merge + post-rewrite run ai-sync after a pull"
}

# ---------------------------------------------------------------- 10 webhook root helper (Linux)

# claude-notify runs as the user; the webhook URL stays root-only in /etc/server/webhooks/.
# A root helper (COPY, never a link) posts for it through one sudoers rule. The URL is never
# copied into the user's home.
base_webhook_helper() {
    root_layer || return 0
    local src="$AI_HOME/ai/hooks/root/ai-webhook-post"
    [ -f "$src" ] || { skip "webhook helper: ai/hooks/root/ai-webhook-post not built (agent B)"; return 0; }
    if ! sudo -n test -f /etc/server/webhooks/info.url 2>/dev/null; then
        skip "webhook helper: no /etc/server/webhooks/info.url yet (claude-notify stays a silent no-op)"
        return 0
    fi
    aiconf_root file-put /usr/local/sbin/ai-webhook-post "$src" --mode 755
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/ai-sudoers.XXXXXX")
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/ai-webhook-post\n' "${AI_FOR_USER:-$(id -un)}" > "$tmp"
    if [ "$AI_DRY_RUN" != 1 ] && ! sudo visudo -cf "$tmp" >/dev/null; then
        warn "sudoers rule for ai-webhook-post failed visudo -c: not installed"; rm -f "$tmp"; return 0
    fi
    aiconf_root file-put /etc/sudoers.d/ai-webhook-post "$tmp" --mode 440
    rm -f "$tmp"
    ok "webhook helper /usr/local/sbin/ai-webhook-post (root:root 755) + sudoers rule (0440, visudo checked)"
}

# ---------------------------------------------------------------- 11 rules (managed blocks)

# Full text for agents without @import (Codex, Hermes): root AGENTS.md + server hosting doc.
rules_text_file() {
    local out; out=$(mktemp "${TMPDIR:-/tmp}/ai-rules.XXXXXX")
    cat "$AI_HOME/ai/AGENTS.md" > "$out"
    if [ -f "$HOSTING_DOC" ]; then printf '\n' >> "$out"; cat "$HOSTING_DOC" >> "$out"; fi
    printf '%s' "$out"
}

base_rules() { base_rules_user; }   # old name, used by ai-sync

# The body of the Claude AI:core block: the import of the root rules (and the server hosting doc).
claude_core_block_file() {
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/ai-claude.XXXXXX")
    printf '@~/.config/ai/AGENTS.md\n' > "$tmp"
    [ -f "$HOSTING_DOC" ] && printf '@~/.dotfiles/docs/AGENTS-hosting.md\n' >> "$tmp"
    printf '%s' "$tmp"
}

# OMC companion file (owner decision 2026-11-14). `omc launch` (oh-my-claude-sisyphus 5.8.x, dist/cli/launch.js
# prepareOmcLaunchConfigDir) builds <claude dir>/.omc-launch/ when <claude dir>/CLAUDE-omc.md has the OMC
# markers; its CLAUDE.md is a COPY of CLAUDE-omc.md only, so ~/.claude/CLAUDE.md and our AI:core import are not
# loaded in omc-launched sessions. When that file exists, the same AI:core block goes into it too, appended
# after <!-- OMC:END --> (never inside OMC's markers; recorded, uninstall removes it). macOS only: on Linux the
# house rules come from /etc/claude-code/CLAUDE.md, which every Claude session loads. ai-sync runs this too.
claude_omc_companion_block() {
    local f="$CLAUDE_DIR/CLAUDE-omc.md" tmp
    [ "$AI_OS" != linux ] && [ -f "$f" ] || return 0
    if grep -qF '<!-- OMC:START -->' "$f" && ! grep -qF '<!-- OMC:END -->' "$f"; then
        warn "$f has <!-- OMC:START --> without <!-- OMC:END -->: AI:core block not added (fix the file, re-run)"
        return 0
    fi
    tmp=$(claude_core_block_file)
    aiconf block-upsert "$f" core 1 "$tmp"
    rm -f "$tmp"
    ok "Claude: managed block also in $f (omc launch reads only that file)"
}

# ~/.claude/CLAUDE.md holds only the root rules import, the machine line and this 3-line OMC note (owner
# 2026-11-16): the long block that OMC setup writes competes with the root rules, so it goes (recorded, undo puts
# it back). ai-doctor (check_claude_cleanup) FAILs when an OMC update writes it back.
claude_omc_note() {
    local f="$CLAUDE_DIR/CLAUDE.md" tmp
    aiconf block-remove "$f" omc-vendor --markers '<!-- OMC:START -->' '<!-- OMC:END -->'
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-omc.XXXXXX")
    printf 'OMC and OMX are toolboxes.\nAGENTS.md and the gates win.\nCatalog: the omc-reference skill.\n' > "$tmp"
    aiconf block-upsert "$f" omc 1 "$tmp"
    rm -f "$tmp"
}

# base_host_block: one line per machine in the Claude and Codex rules: where the projects live (owner
# 2026-11-15). Folder: AI_PROJECTS_DIR (saved in ~/.config/ai/projects-dir) > that file > ~/work if it exists.
# No folder: the block is removed.
base_host_block() {
    local f="${AI_TARGET_HOME:-$HOME}/.config/ai/projects-dir" dir="${AI_PROJECTS_DIR:-}" tmp
    if [ -n "$dir" ]; then
        tmp=$(mktemp "${TMPDIR:-/tmp}/ai-pdir.XXXXXX"); printf '%s\n' "$dir" > "$tmp"
        aiconf file-put "$f" "$tmp" --mode 644; rm -f "$tmp"
    elif [ -r "$f" ]; then dir=$(sed -n '1{s/[[:space:]]*$//;p;}' "$f")
    elif [ -d "${AI_TARGET_HOME:-$HOME}/work" ]; then dir="~/work"
    fi
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-host.XXXXXX")
    printf 'This machine: projects live in %s (one folder per project, each a git repo). Look there first for a project the owner names.\n' "$dir" > "$tmp"
    local file
    for file in $(want claude && echo "$CLAUDE_DIR/CLAUDE.md") $(want codex && echo "$CODEX_DIR/AGENTS.md"); do
        if [ -n "$dir" ]; then aiconf block-upsert "$file" host 1 "$tmp"; else aiconf block-remove "$file" host; fi
    done
    rm -f "$tmp"
    [ -z "$dir" ] || ok "rules: projects live in $dir (host block)"
}

base_rules_user() {
    local tmp
    if [ ! -f "$AI_HOME/ai/AGENTS.md" ]; then
        warn "ai/AGENTS.md not built yet: rules blocks skipped (run ai-render, then re-run install)"
        return 0
    fi

    if want claude && root_layer; then
        # Linux: house rules come from /etc/claude-code/CLAUDE.md (admin layer, cannot be excluded).
        # A per-user import would load them twice: none, and ours is removed if an older install added it.
        aiconf block-remove "$CLAUDE_DIR/CLAUDE.md" core
        ok "Claude: house rules from /etc/claude-code/CLAUDE.md (no per-user import on Linux)"
    elif want claude; then
        tmp=$(claude_core_block_file)
        aiconf block-upsert "$CLAUDE_DIR/CLAUDE.md" core 1 "$tmp"
        rm -f "$tmp"
        ok "Claude: managed block in $CLAUDE_DIR/CLAUDE.md (other blocks kept)"
        claude_omc_companion_block
    fi
    want claude && claude_omc_note

    if want codex; then
        tmp=$(rules_text_file)
        aiconf block-upsert "$CODEX_DIR/AGENTS.md" core 1 "$tmp"
        rm -f "$tmp"
        ok "Codex: managed block in $CODEX_DIR/AGENTS.md (OMX blocks kept)"
    fi

    if want opencode; then
        aiconf json-add "$OPENCODE_JSON" instructions "\"$HOME/.config/ai/AGENTS.md\""
        ok "opencode: instructions -> ~/.config/ai/AGENTS.md"
    fi
    base_host_block
    return 0
}

# ---------------------------------------------------------------- 12 environment

env_pairs() { grep -E '^[A-Z0-9_]+=' "$AI_HOME/ai/adapters/env.list"; }

base_env_user() {
    local tmp line k v
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-env.XXXXXX")
    env_sh_file > "$tmp"
    aiconf file-put "$HOME/.config/ai/env.sh" "$tmp" --mode 644
    rm -f "$tmp"
    if ! grep -qs 'config/ai/env.sh' "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zprofile" \
        && [ ! -f /etc/profile.d/ai-env.sh ]; then
        manual "add to your shell rc: [ -f ~/.config/ai/env.sh ] && . ~/.config/ai/env.sh"
    fi

    base_path_block
    base_git_excludes

    if want claude; then
        env_pairs | while IFS='=' read -r k v; do
            aiconf json-set "$CLAUDE_DIR/settings.json" "env/$k" "\"$v\""
        done
        claude_connectors_env "$CLAUDE_DIR/settings.json" aiconf
        ok "Claude: env switches in $CLAUDE_DIR/settings.json (merge): hooks, MCP servers and -p runs see them"
        claude_permissions
        claude_env_sandbox
    fi

    want codex && codex_env
    want opencode && opencode_env
    want herdr && herdr_env
    want claude && claude_env
    return 0
}

# claude.ai account connectors (Gmail, Calendar, Drive...) in Claude Code: off on Linux servers, where
# unattended agents run (an agent must not reach the owner's mail). Keep them: install with
# AI_CLAUDEAI_CONNECTORS=keep. macOS: left as Claude's default unless AI_CLAUDEAI_CONNECTORS=off or the
# profile has the context diet (PROFILE_CONTEXT_DIET=1: the connectors cost about 6,300 start tokens).
claudeai_connectors_off() {
    case "${AI_CLAUDEAI_CONNECTORS:-}" in
        keep) return 1 ;;
        off) return 0 ;;
    esac
    [ "${PROFILE_CONTEXT_DIET:-0}" = 1 ] || [ "$AI_OS" = linux ]
}

# claude_connectors_env <settings file> <aiconf|aiconf_root>
claude_connectors_env() {
    # The keep decision is remembered for ai-doctor (it fails on Linux when connectors load by accident).
    if [ "$2" = aiconf ] && [ "$AI_DRY_RUN" != 1 ]; then
        mkdir -p "$AI_STATE_DIR"
        if [ "${AI_CLAUDEAI_CONNECTORS:-}" = keep ]; then : > "$AI_STATE_DIR/claudeai-connectors.keep"
        else rm -f "$AI_STATE_DIR/claudeai-connectors.keep"; fi
    fi
    # Settings key disableClaudeAiConnectors: a true in any settings file wins (settings-reference). The env
    # var ENABLE_CLAUDEAI_MCP_SERVERS is documented for the shell only, so it is not used here.
    if claudeai_connectors_off; then
        if [ "$2" = aiconf_root ]; then aiconf_root json-set "$1" disableClaudeAiConnectors true --mode 644
        else aiconf json-set "$1" disableClaudeAiConnectors true; fi
    elif [ "${AI_CLAUDEAI_CONNECTORS:-}" = keep ]; then
        # Keep = also undo an earlier off (a true in any settings file would still win). Recorded.
        if [ "$2" = aiconf_root ]; then aiconf_root json-del "$1" disableClaudeAiConnectors --mode 644
        else aiconf json-del "$1" disableClaudeAiConnectors; fi
    fi
    return 0
}

# ~/.local/bin and the env switches for shells that read no profile (ssh host cmd, scripts, cron via bash).
# Linux only (the Mac shell files are the owner's). bash: at the TOP of ~/.bashrc, before Ubuntu's
# "not interactive: return" line; zsh: ~/.zshenv (read by every zsh).
base_path_block() {
    [ "$AI_OS" = linux ] || return 0
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/ai-path.XXXXXX")
    printf '%s\n' 'case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$HOME/.local/bin:$PATH"; export PATH ;; esac' \
        '[ -f "$HOME/.config/ai/env.sh" ] && . "$HOME/.config/ai/env.sh"' > "$tmp"
    aiconf block-upsert "$HOME/.bashrc" path 1 "$tmp" --comment --top
    if [ -f "$HOME/.zshenv" ] || [ "$(basename "${SHELL:-}")" = zsh ]; then
        aiconf block-upsert "$HOME/.zshenv" path 1 "$tmp" --comment --top
    fi
    rm -f "$tmp"
    ok "~/.local/bin and ~/.config/ai/env.sh for non-login shells (top of ~/.bashrc, ~/.zshenv for zsh)"
}

# Claude's sandbox keeps placeholder entries for the protected names it finds missing in the project root (Claude
# 2.1.322 binary: files .gitconfig .gitmodules .bashrc .bash_profile .zshrc .zprofile .profile .ripgreprc
# .mcp.json, folders .vscode .idea .claude/commands .claude/agents). git status then lists them and
# `git add -A` dies ("can only add regular files"). The user's global git excludes ignore exactly these names,
# at the repo root only (a leading /). Tracked files stay tracked; a real new one needs `git add -f`.
GIT_SANDBOX_EXCLUDES="/.gitconfig /.gitmodules /.bashrc /.bash_profile /.zshrc /.zprofile /.profile /.ripgreprc /.mcp.json /.vscode /.idea /.claude/commands /.claude/agents"
git_excludes_file() {
    local f; f=$(git config --global --get core.excludesFile 2>/dev/null || true)
    case "$f" in
        "") echo "${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore" ;;
        "~/"*) echo "$HOME/${f#\~/}" ;;
        *) echo "$f" ;;
    esac
}
base_git_excludes() {
    has git || return 0
    local f tmp
    f=$(git_excludes_file)
    mkdir -p "$(dirname "$f")"
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-gitx.XXXXXX")
    printf '%s\n' $GIT_SANDBOX_EXCLUDES > "$tmp"
    aiconf block-upsert "$f" git-sandbox-placeholders 1 "$tmp" --comment
    rm -f "$tmp"
    ok "git: global excludes ignore the sandbox placeholders in project roots ($f)"
}

env_sh_file() {
    printf '# Generated by install.sh from ai/adapters/env.list. Do not edit: re-run install.\n'
    env_pairs | while IFS= read -r line; do printf 'export %s\n' "$line"; done
}

# Ubuntu, root: every user and user services get the switches; Claude managed settings merged.
base_env_system() {
    root_layer || return 0
    local tmp k
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-env.XXXXXX")
    env_sh_file > "$tmp"
    aiconf_root file-put /etc/profile.d/ai-env.sh "$tmp" --mode 644
    env_pairs > "$tmp"
    aiconf_root file-put /etc/environment.d/91-ai.conf "$tmp" --mode 644
    rm -f "$tmp"
    # /etc/environment (pam_env): ssh commands, cron and sudo -i see the plain switches without a profile.
    # A key that is already set there (by anyone) is left as it is.
    local line v
    while IFS= read -r line; do
        grep -qs "^${line%%=*}=" /etc/environment || aiconf_root line-add /etc/environment "$line"
    done <<EOT
$(env_pairs)
EOT
    # Claude managed settings: every user (also hermes) and every Claude process, -p runs included.
    local ms=/etc/claude-code/managed-settings.json
    while IFS='=' read -r k v; do
        [ -n "$k" ] && aiconf_root json-set "$ms" "env/$k" "\"$v\"" --mode 644
    done <<EOT
$(env_pairs)
EOT
    claude_connectors_env "$ms" aiconf_root
    aiconf_root json-set "$ms" skillListingBudgetFraction 0.02 --mode 644
    # Managed deny rules cannot be removed by user or project settings (agents cannot edit /etc). Synced:
    # deny rules of an earlier install that the current list dropped (the old sudo forms) go away.
    local denyf; denyf=$(mktemp "${TMPDIR:-/tmp}/ai-deny.XXXXXX")
    claude_deny_rules | while IFS= read -r line; do [ -n "$line" ] && json_str "$line"; done > "$denyf"
    chmod 644 "$denyf"
    aiconf_root json-list-sync "$ms" permissions/deny "$denyf" --mode 644
    rm -f "$denyf"
    claude_managed_policy
    ok "Ubuntu: /etc/profile.d/ai-env.sh, /etc/environment.d/91-ai.conf, /etc/environment, $ms (env, deny rules)"
}
