# ai/adapters/claude.sh: Claude Code wiring through its own CLI (SPEC 20).
# Our own merge code only touches: the CLAUDE.md managed block (base.sh), env keys, and hook
# entries in settings.json that the ai-core plugin now owns (adopt, recorded for uninstall).

CLAUDE_PLUGINS_DIR="$CLAUDE_DIR/plugins"
CLAUDE_JSON() { if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then echo "$CLAUDE_CONFIG_DIR/.claude.json"; else echo "$HOME/.claude.json"; fi; }

claude_has_marketplace() {
    [ -n "$(aiconf json-get "$CLAUDE_PLUGINS_DIR/known_marketplaces.json" "$1" 2>/dev/null)" ] && return 0
    claude plugin marketplace list 2>/dev/null | grep -Eq "(^|[^[:alnum:]_-])$1([^[:alnum:]_-]|$)"
}

claude_has_plugin() {
    [ -n "$(aiconf json-get "$CLAUDE_PLUGINS_DIR/installed_plugins.json" "plugins/$1" 2>/dev/null)" ] && return 0
    claude plugin list 2>/dev/null | grep -qF "$1"
}

# claude_plugin <marketplace-name> <marketplace-source> <plugin@marketplace> [audited sha]
claude_plugin() {
    local mname=$1 msrc=$2 plugin=$3 sha=${4:-} head
    if ! claude_has_marketplace "$mname"; then
        run claude plugin marketplace add "$msrc"
        aiconf record-cmd "claude-marketplace:$mname" -- claude plugin marketplace remove "$mname"
    fi
    if [ -n "$sha" ] && [ "$AI_DRY_RUN" != 1 ]; then
        head=$(git -C "$CLAUDE_PLUGINS_DIR/marketplaces/$mname" rev-parse HEAD 2>/dev/null || echo unknown)
        if [ "$head" != "$sha" ]; then
            warn "$mname marketplace is at $head, audited pin is $sha: plugin not installed (check /plugin)"
            return 1
        fi
    fi
    if claude_has_plugin "$plugin"; then
        info "$plugin already installed: kept as is"
        return 0
    fi
    run claude plugin install "$plugin" --scope user
    aiconf record-cmd "claude-plugin:$plugin" -- claude plugin uninstall "$plugin"
    ok "Claude plugin $plugin (user scope)"
}

# ---------------------------------------------------------------- step 7: MCP

claude_mcp() {
    has claude || { skip "Claude MCP: claude not found"; return 0; }
    # Plugin .mcp.json serves Serena, context7, GitHub, Grounded Docs. Remove user-scope copies
    # (the hand-made server config registered Serena there) so no server runs twice.
    aiconf claude-take-mcp "$(CLAUDE_JSON)" "$(PLUGIN_DIR)/.mcp.json"
    ok "Claude MCP: served by the ai-core plugin (no user-scope duplicates)"
}

# ---------------------------------------------------------------- step 8: plugins

claude_plugins() {
    has claude || { skip "Claude plugins: claude not found"; return 0; }
    local p hash_file hash old=""
    p=$(PLUGIN_DIR)

    # ai-core from this repo (directory marketplace). Reinstall when the tree changed.
    hash_file="$AI_STATE_DIR/ai-core.claude.hash"
    hash=$(aiconf tree-hash "$p")
    [ -f "$hash_file" ] && old=$(cat "$hash_file")
    if claude_has_plugin ai-core@ai && [ "$hash" != "$old" ]; then
        run claude plugin marketplace update ai
        run claude plugin uninstall ai-core@ai
        run claude plugin install ai-core@ai --scope user
        ok "Claude plugin ai-core@ai reinstalled (plugin files changed)"
    else
        claude_plugin ai "$AI_HOME/ai/marketplace" ai-core@ai
    fi
    [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$hash" > "$hash_file"; }

    # Ponytail and i-have-adhd from the audited local copies (no auto-update for local paths).
    if claude_has_plugin ponytail@ponytail; then info "ponytail@ponytail installed: kept as is"
    elif [ -d "$(plugin_src_dir ponytail)" ] || [ "$AI_DRY_RUN" = 1 ]; then
        claude_plugin ponytail "$(plugin_src_dir ponytail)" ponytail@ponytail
    else skip "Ponytail: audited source missing"; fi

    if claude_has_plugin i-have-adhd@i-have-adhd; then info "i-have-adhd installed: kept as is"
    elif [ -d "$(plugin_src_dir i-have-adhd)" ] || [ "$AI_DRY_RUN" = 1 ]; then
        claude_plugin i-have-adhd "$(plugin_src_dir i-have-adhd)" i-have-adhd@i-have-adhd
    else skip "i-have-adhd: audited source missing"; fi
    # Always-on flag (empty file; the hook tests existence). Codex reads the same path.
    local empty; empty=$(mktemp "${TMPDIR:-/tmp}/ai-empty.XXXXXX")
    aiconf file-put "$CLAUDE_DIR/.i-have-adhd-always" "$empty" --mode 644
    rm -f "$empty"

    # claude-seo, claude-blog: tag pin in the add command, sha checked after the clone.
    claude_plugin agricidaniel-claude-seo "AgriciDaniel/claude-seo#$CLAUDE_SEO_REF" claude-seo@agricidaniel-claude-seo "$CLAUDE_SEO_SHA" || true
    claude_plugin agricidaniel-blog "AgriciDaniel/claude-blog#$CLAUDE_BLOG_REF" claude-blog@agricidaniel-blog "$CLAUDE_BLOG_SHA" || true
    manual "Claude, once per machine: /seo setup, then /seo doctor (claude-seo venv + Chromium)"

    # Plugins the design dropped: report, never remove.
    local f="$CLAUDE_PLUGINS_DIR/installed_plugins.json" name
    if [ -f "$f" ]; then
        for name in $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1])).get("plugins",{}).keys()))' "$f" 2>/dev/null); do
            case "$name" in
                caveman@*|context7@*) manual "dropped by design, remove if you agree: claude plugin uninstall $name" ;;
            esac
        done
    fi
}

# ---------------------------------------------------------------- step 9: skills

link_skills() {
    # link_skills <target dir>: every ai/skills/<name>/SKILL.md becomes <target>/<name> (a link)
    local dir=$1 s n
    [ -d "$AI_HOME/ai/skills" ] || return 0
    for s in "$AI_HOME"/ai/skills/*/; do
        [ -f "$s/SKILL.md" ] || continue
        n=$(basename "$s")
        if [ -d "$dir/$n" ] && [ ! -L "$dir/$n" ]; then
            warn "$dir/$n is a real folder (not ours): skill $n not linked"; continue
        fi
        aiconf link "$dir/$n" "${s%/}"
    done
}

claude_skills() {
    link_skills "$CLAUDE_DIR/skills"
    ok "Claude: shared skills linked into $CLAUDE_DIR/skills"
}

# ---------------------------------------------------------------- step 10: hooks

claude_hooks() {
    has claude || { skip "Claude hooks: claude not found"; return 0; }
    local hooks; hooks="$(PLUGIN_DIR)/hooks/hooks.json"

    # graphify global skill per agent (its writes are reported; duplicates are adopted below).
    if has graphify; then
        local before; before=$(snap_files "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/CLAUDE.md")
        run graphify install --platform claude </dev/null || warn "graphify install --platform claude failed"
        report_changes "$before" "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/CLAUDE.md"
    fi

    claude_rtk

    if [ -f "$hooks" ]; then
        aiconf claude-adopt-hooks "$CLAUDE_DIR/settings.json" "$hooks"
        ok "Claude hooks: ai-core plugin owns router, gates, notify, caffeinate (no duplicates in settings.json)"
    else
        warn "plugin hooks/hooks.json missing (agent B): settings.json hooks left as they are"
    fi
}

# RTK rewrite hook: dry-run first, decline the proxy, no CLAUDE.md edit (contracts-mcp-a finding 3).
claude_rtk() {
    has rtk || { skip "RTK hook: rtk not installed"; return 0; }
    if [ "$AI_OS" = macos ] && [ "$AI_RTK_HOOK" != 1 ]; then
        skip "RTK hook on macOS: only with --rtk-hook (never re-enabled silently)"; return 0
    fi
    if grep -qs 'rtk' "$CLAUDE_DIR/settings.json" && aiconf hooks-diff "$CLAUDE_DIR/settings.json" | grep -q 'rtk'; then
        info "RTK hook already in $CLAUDE_DIR/settings.json"; return 0
    fi
    local help flags="-g"
    help=$(rtk init --help 2>&1 || true)
    case "$help" in *--hook-only*) flags="$flags --hook-only" ;; esac
    case "$help" in *--auto-patch*) flags="$flags --auto-patch" ;; esac
    if printf '%s' "$help" | grep -q -- '--dry-run'; then
        info "rtk init $flags --dry-run:"
        rtk init $flags --dry-run </dev/null 2>&1 | sed 's/^/    /' | head -30 || true
    fi
    local before; before=$(snap_files "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/CLAUDE.md")
    run rtk init $flags </dev/null
    report_changes "$before" "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/CLAUDE.md"
    # AGENTS.md carries the RTK block A.4: drop the vendor import if it was added.
    aiconf line-remove "$CLAUDE_DIR/CLAUDE.md" "@RTK.md"
    aiconf record-cmd rtk:claude -- rtk init -g --uninstall
    ok "RTK hook for Claude (proxy declined, no CLAUDE.md import)"
}

# ---------------------------------------------------------------- step 12: env

claude_env() {
    # OMC: no self-update (SPEC 19). JSONC file: comments are dropped on write, reported.
    if [ -d "$CLAUDE_DIR/claude-omc" ] || has omc; then
        aiconf json-set "$CLAUDE_DIR/claude-omc/config.jsonc" security/disableAutoUpdate true --jsonc
    fi
    # Ponytail mode (A.3); never PONYTAIL_DEFAULT_MODE (it overrides the file).
    aiconf json-set "$HOME/.config/ponytail/config.json" defaultMode '"full"'
    ok "Claude add-ons: OMC auto-update off, Ponytail defaultMode full"
}
