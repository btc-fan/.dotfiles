# ai/adapters/codex.sh: Codex CLI wiring through its own CLI (SPEC 20).
# Own merge code only for: the AGENTS.md managed block (base.sh) and single keys in config.toml.

# Installed plugins only: `codex plugin list` also prints the remote catalog ("not installed" lines).
codex_installed_plugins() {
    codex plugin list 2>/dev/null | grep -viE 'not[ _-]?installed|uninstalled|available' | grep -E '[[:alnum:]]' || true
}
codex_has_plugin() { codex_installed_plugins | grep -qF "$1"; }

codex_marketplace_plugin() {
    # codex_marketplace_plugin <marketplace dir> <marketplace name> <plugin@marketplace>
    local dir=$1 mname=$2 plugin=$3
    if codex_has_plugin "${plugin%@*}"; then info "Codex plugin $plugin installed: kept as is"; return 0; fi
    if ! codex plugin marketplace list 2>/dev/null | grep -Eq "(^|[^[:alnum:]_-])$mname([^[:alnum:]_-]|$)"; then
        run codex plugin marketplace add "$dir" || { warn "codex plugin marketplace add $dir failed"; return 1; }
        aiconf record-cmd "codex-marketplace:$mname" -- codex plugin marketplace remove "$mname"
    fi
    run codex plugin add "$plugin" || { warn "codex plugin add $plugin failed"; return 1; }
    aiconf record-cmd "codex-plugin:$plugin" -- codex plugin remove "$plugin"
    ok "Codex plugin $plugin"
}

# ---------------------------------------------------------------- step 7: MCP

codex_mcp() {
    has codex || { skip "Codex MCP: codex not found"; return 0; }
    aiconf mcp-register codex --mcp-json "$(PLUGIN_DIR)/.mcp.json" --plugin-root "$(PLUGIN_DIR)"
    ok "Codex MCP: serena (codex context), context7, github, grounded-docs"
}

# ---------------------------------------------------------------- step 8: plugins

codex_plugins() {
    has codex || { skip "Codex plugins: codex not found"; return 0; }
    local p hash_file hash old=""
    p=$(PLUGIN_DIR)
    hash_file="$AI_STATE_DIR/ai-core.codex.hash"
    hash=$(aiconf tree-hash "$p")
    [ -f "$hash_file" ] && old=$(cat "$hash_file")
    if codex_has_plugin ai-core && [ "$hash" != "$old" ]; then
        # Refresh in place; never remove first (a failed add would leave no plugin).
        if run codex plugin add ai-core@ai; then ok "Codex plugin ai-core@ai refreshed (plugin files changed)"
        else warn "codex plugin add ai-core@ai failed: old copy kept"; hash=$old; fi
    else
        codex_marketplace_plugin "$AI_HOME/ai/marketplace" ai ai-core@ai || true
    fi
    [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$hash" > "$hash_file"; }

    if [ -d "$(plugin_src_dir ponytail)" ] || [ "$AI_DRY_RUN" = 1 ]; then
        codex_marketplace_plugin "$(plugin_src_dir ponytail)" ponytail ponytail@ponytail || true
    fi
    if [ -d "$(plugin_src_dir i-have-adhd)/.codex-plugin" ] || [ "$AI_DRY_RUN" = 1 ]; then
        codex_marketplace_plugin "$(plugin_src_dir i-have-adhd)" i-have-adhd i-have-adhd@i-have-adhd || true
    fi
    manual "Codex: open /hooks once and trust the hooks of ai-core, ponytail and i-have-adhd"

    # Remote curated plugins installed without our audit (SPEC 20): show, owner decides.
    local others
    others=$(codex_installed_plugins | grep -vE 'ai-core|ponytail|i-have-adhd' || true)
    if [ -n "$others" ]; then
        info "other installed Codex plugins (not audited by us):"
        printf '%s\n' "$others" | sed 's/^/    /'
        manual "decide keep or remove for the Codex plugins listed above (codex plugin remove <name>)"
    fi
}

# ---------------------------------------------------------------- step 9: skills

codex_skills() {
    link_skills "$HOME/.agents/skills"
    ok "Codex/opencode: shared skills linked into ~/.agents/skills"
}

# ---------------------------------------------------------------- step 10: hooks

codex_hooks() {
    has codex || return 0
    if has graphify; then
        local before; before=$(snap_files "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json" "$CODEX_DIR/AGENTS.md")
        run graphify install --platform codex </dev/null || warn "graphify install --platform codex failed"
        report_changes "$before" "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json" "$CODEX_DIR/AGENTS.md"
    fi
    if has rtk; then
        if grep -qs rtk "$CODEX_DIR/hooks.json" "$CODEX_DIR/config.toml"; then
            info "RTK already wired for Codex"
        else
            local before; before=$(snap_files "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json" "$CODEX_DIR/AGENTS.md")
            run rtk init -g --codex </dev/null
            report_changes "$before" "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json" "$CODEX_DIR/AGENTS.md"
            aiconf record-cmd rtk:codex -- rtk init -g --codex --uninstall
            ok "RTK for Codex"
        fi
    fi
}

# ---------------------------------------------------------------- step 12: env

codex_env() {
    local f="$CODEX_DIR/config.toml"
    aiconf toml-set "$f" "" check_for_update_on_startup false
    aiconf toml-set "$f" "" project_doc_max_bytes 65536
    aiconf toml-set "$f" analytics enabled false
    aiconf toml-set "$f" feedback enabled false
    ok "Codex: update check, analytics, feedback off; project_doc_max_bytes 65536"
}
