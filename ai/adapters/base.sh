# ai/adapters/base.sh: prerequisites, pin checks, links, render, root rules, environment.
# Sourced by install.sh. Uses ai/lib/common.sh. bash 3.2.

PLUGIN_DIR() { printf '%s' "$AI_HOME/ai/marketplace/plugins/ai-core"; }
CLAUDE_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
CODEX_DIR=${CODEX_HOME:-$HOME/.codex}
OPENCODE_JSON="$HOME/.config/opencode/opencode.json"
HOSTING_DOC="$HOME/.dotfiles/docs/AGENTS-hosting.md"

# ---------------------------------------------------------------- 1 prerequisites

base_prereqs() {
    local missing="" c
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
            [ -n "$apt" ] && run_root apt-get install -y -q $apt && ok "apt-get install$apt"
            # node (NodeSource) and uv (sha256-checked release) come from the ubuntu-server base branch
            if [ -n "$rest" ]; then
                manual "install$rest with the ubuntu-server base setup (signed repo / checksummed release), then re-run"
            fi
            ;;
    esac
    return 0
}

# ---------------------------------------------------------------- 2 pins

base_pins() {
    local bad=0 p
    p=$(PLUGIN_DIR)
    grep -q "@upstash/context7-mcp@$CONTEXT7_MCP_VERSION" "$p/mcp/context7.sh" \
        || { warn "context7 version in $p/mcp/context7.sh differs from pins.env ($CONTEXT7_MCP_VERSION)"; bad=1; }
    if [ -f "$AI_HOME/ai/mcp/project/playwright.mcp.json" ]; then
        grep -q "@playwright/mcp@$PLAYWRIGHT_MCP_VERSION" "$AI_HOME/ai/mcp/project/playwright.mcp.json" \
            || { warn "Playwright version in ai/mcp/project/playwright.mcp.json differs from pins.env"; bad=1; }
    fi
    if grep -rqE '@latest|curl[^|]*\|[[:space:]]*(ba)?sh' "$p/.mcp.json" "$p/mcp" 2>/dev/null; then
        warn "unpinned @latest or curl|sh in the ai-core plugin"; bad=1
    fi
    if [ "$(today)" \< "$OMX_NOT_BEFORE" ]; then
        info "oh-my-codex $OMX_VERSION: install waits until $OMX_NOT_BEFORE (release under 1 week old at audit)"
    fi
    [ $bad = 0 ] && ok "pins consistent (ai/pins.env)"
    return 0
}

# ---------------------------------------------------------------- 3 links

base_links() {
    local f name exclude

    # Hooks and docs use $HOME/.dotfiles-ai; a work tree elsewhere gets a link there.
    if [ "$AI_HOME" != "$HOME/.dotfiles-ai" ]; then
        if [ ! -e "$HOME/.dotfiles-ai" ] || [ -L "$HOME/.dotfiles-ai" ]; then
            aiconf link "$HOME/.dotfiles-ai" "$AI_HOME"
        else
            warn "$HOME/.dotfiles-ai exists and is not $AI_HOME: hooks will use that copy"
        fi
    fi

    aiconf link "$HOME/.config/ai/AGENTS.md" "$AI_HOME/ai/AGENTS.md"
    aiconf link "$HOME/.config/ai/TOOLBOX.md" "$AI_HOME/ai/TOOLBOX.md"

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
    # tools interface (REPL runs any Python), no second shell, no dashboard (SPEC 4)
    aiconf yaml-top-set "$cfg" agent_interface tools
    aiconf yaml-top-set "$cfg" excluded_tools "[execute_shell_command, serena_repl]"
    aiconf yaml-top-set "$cfg" web_dashboard false
    aiconf yaml-top-set "$cfg" web_dashboard_open_on_launch false
    ok "Serena: tools interface, shell + REPL excluded, dashboard off ($cfg)"
}

# ---------------------------------------------------------------- 10 webhook root helper (Linux)

# claude-notify runs as the user; the webhook URL stays root-only in /etc/server/webhooks/.
# A root helper (COPY, never a link) posts for it through one sudoers rule. The URL is never
# copied into the user's home.
base_webhook_helper() {
    [ "$AI_OS" = linux ] || return 0
    local src="$AI_HOME/ai/hooks/root/ai-webhook-post"
    [ -f "$src" ] || { skip "webhook helper: ai/hooks/root/ai-webhook-post not built (agent B)"; return 0; }
    if ! sudo -n test -f /etc/server/webhooks/info.url 2>/dev/null; then
        skip "webhook helper: no /etc/server/webhooks/info.url yet (claude-notify stays a silent no-op)"
        return 0
    fi
    aiconf_root file-put /usr/local/sbin/ai-webhook-post "$src" --mode 755
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/ai-sudoers.XXXXXX")
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/ai-webhook-post\n' "$(id -un)" > "$tmp"
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

base_rules() {
    local tmp
    if [ ! -f "$AI_HOME/ai/AGENTS.md" ]; then
        warn "ai/AGENTS.md not built yet: rules blocks skipped (run ai-render, then re-run install)"
        return 0
    fi

    if want claude; then
        tmp=$(mktemp "${TMPDIR:-/tmp}/ai-claude.XXXXXX")
        printf '@~/.config/ai/AGENTS.md\n' > "$tmp"
        [ -f "$HOSTING_DOC" ] && printf '@~/.dotfiles/docs/AGENTS-hosting.md\n' >> "$tmp"
        aiconf block-upsert "$CLAUDE_DIR/CLAUDE.md" core 1 "$tmp"
        rm -f "$tmp"
        ok "Claude: managed block in $CLAUDE_DIR/CLAUDE.md (other blocks kept)"
    fi

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

    if want hermes && hermes_exists; then
        hermes_rules
    fi
}

# ---------------------------------------------------------------- 12 environment

env_pairs() { grep -E '^[A-Z0-9_]+=' "$AI_HOME/ai/adapters/env.list"; }

base_env() {
    local tmp line k v
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-env.XXXXXX")
    {
        printf '# Generated by %s/install.sh from ai/adapters/env.list. Do not edit: re-run install.\n' "$AI_HOME"
        env_pairs | while IFS= read -r line; do printf 'export %s\n' "$line"; done
    } > "$tmp"
    aiconf file-put "$HOME/.config/ai/env.sh" "$tmp" --mode 644
    if ! grep -qs 'config/ai/env.sh' "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zprofile" \
        && [ ! -f /etc/profile.d/ai-env.sh ]; then
        manual "add to your shell rc: [ -f ~/.config/ai/env.sh ] && . ~/.config/ai/env.sh"
    fi

    if want claude; then
        env_pairs | while IFS='=' read -r k v; do
            aiconf json-set "$CLAUDE_DIR/settings.json" "env/$k" "\"$v\""
        done
        ok "Claude: telemetry/update env keys in $CLAUDE_DIR/settings.json (merge)"
    fi

    if [ "$AI_OS" = linux ]; then
        aiconf_root file-put /etc/profile.d/ai-env.sh "$tmp" --mode 644
        env_pairs > "$tmp"
        aiconf_root file-put /etc/environment.d/91-ai.conf "$tmp" --mode 644
        # Claude managed settings: merge our keys only (SPEC 3, 7).
        local ms=/etc/claude-code/managed-settings.json
        for k in DISABLE_TELEMETRY DISABLE_ERROR_REPORTING DISABLE_AUTOUPDATER; do
            aiconf_root json-set "$ms" "env/$k" '"1"' --mode 644
        done
        aiconf_root json-set "$ms" skillListingBudgetFraction 0.02 --mode 644
        ok "Ubuntu: /etc/profile.d/ai-env.sh, /etc/environment.d/91-ai.conf, $ms"
    fi
    rm -f "$tmp"

    want codex && codex_env
    want opencode && opencode_env
    want herdr && herdr_env
    want claude && claude_env
    want hermes && hermes_exists && hermes_env
    return 0
}
