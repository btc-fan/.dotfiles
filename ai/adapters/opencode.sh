# ai/adapters/opencode.sh: opencode reads ~/.config/ai/AGENTS.md through its `instructions` key
# (base.sh) and the shared ~/.agents/skills. Here: MCP servers and the no-update/no-share keys.

opencode_mcp() {
    aiconf opencode-mcp "$OPENCODE_JSON" --mcp-json "$(PLUGIN_DIR)/.mcp.json" --plugin-root "$(PLUGIN_DIR)"
    ok "opencode MCP: context7"
}

opencode_hooks() {
    # opencode plugin file (JS) for router/gates, built by agent B if present.
    local f="$AI_HOME/ai/hooks/opencode/ai-core.js"
    if [ -f "$f" ]; then
        aiconf link "$HOME/.config/opencode/plugin/ai-core.js" "$f"
        ok "opencode plugin linked"
    else
        skip "opencode plugin: ai/hooks/opencode/ai-core.js not built (agent B)"
    fi
}

opencode_env() {
    aiconf json-set "$OPENCODE_JSON" '$schema' '"https://opencode.ai/config.json"'
    aiconf json-set "$OPENCODE_JSON" autoupdate false
    aiconf json-set "$OPENCODE_JSON" share '"disabled"'
    ok "opencode: autoupdate false, share disabled (never run 'opencode upgrade')"
}
