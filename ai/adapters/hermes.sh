# ai/adapters/hermes.sh: Hermes runs as user `hermes` (Linux only). Every change runs as that
# user (`sudo -u hermes -H`) and is recorded in ITS state file (~hermes/.local/state/ai/), so its
# own uninstall can undo it. The owner's home may be closed to hermes: files are staged first.

hermes_stage_dir() {
    # hermes_stage_dir <local dir> <name> -> prints the staged path (a copy in hermes' home)
    local src=$1 name=$2 hh
    hh=$(hermes_home)
    if [ "$AI_DRY_RUN" != 1 ]; then
        tar -C "$(dirname "$src")" -cf - "$(basename "$src")" \
            | sudo -u "$HERMES_USER" -H sh -c "mkdir -p '$hh/.local/share/ai/stage/$name' && tar -C '$hh/.local/share/ai/stage/$name' --strip-components=1 -xf -"
    fi
    printf '%s/.local/share/ai/stage/%s' "$hh" "$name"
}

# ---------------------------------------------------------------- step 7: MCP

hermes_mcp() {
    as_hermes_ro 'command -v hermes' >/dev/null || { skip "Hermes MCP: hermes binary not found for user $HERMES_USER"; return 0; }
    local root c7 hh
    hh=$(hermes_home)
    # Serena and context7 for this user too (its own PATH and HOME; no runtime npx).
    if ! as_hermes_ro 'command -v serena' >/dev/null && [ "$AI_SKIP_PACKAGES" != 1 ]; then
        audit_ok pypi serena-agent "$SERENA_VERSION" \
            && as_hermes "uv tool install --no-build -p $SERENA_PYTHON serena-agent==$SERENA_VERSION" \
            && aiconf_hermes record-cmd uv:serena -- uv tool uninstall serena-agent
    fi
    c7="$hh/.local/share/ai/npm/context7-mcp-$CONTEXT7_MCP_VERSION"
    if ! sudo -n -u "$HERMES_USER" test -x "$c7/node_modules/.bin/context7-mcp" 2>/dev/null && [ "$AI_SKIP_PACKAGES" != 1 ]; then
        npm_local @upstash/context7-mcp "$CONTEXT7_MCP_VERSION" "$CONTEXT7_MCP_INTEGRITY" "$c7" hermes \
            && aiconf_hermes record-cmd npm-local:context7 -- rm -rf "$c7"
    fi
    root=$(hermes_stage_dir "$(PLUGIN_DIR)" plugin-ai-core)
    aiconf_hermes mcp-register hermes --mcp-json "$root/.mcp.json" --plugin-root "$root"
    hermes_serena_config
    manual "Hermes: put GITHUB_PERSONAL_ACCESS_TOKEN and CONTEXT7_API_KEY in ~$HERMES_USER/.config/ai/secrets.env (600)"
    ok "Hermes MCP: serena (ide context), context7, github, grounded-docs"
}

hermes_serena_config() {
    local cfg; cfg="$(hermes_home)/.serena/serena_config.yml"
    if ! sudo -n -u "$HERMES_USER" test -f "$cfg" 2>/dev/null; then
        as_hermes 'serena init' >/dev/null || { warn "serena init as $HERMES_USER failed"; return 0; }
    fi
    aiconf_hermes yaml-top-set "$cfg" agent_interface tools
    aiconf_hermes yaml-top-set "$cfg" excluded_tools "[execute_shell_command, serena_repl]"
    aiconf_hermes yaml-top-set "$cfg" web_dashboard false
    aiconf_hermes yaml-top-set "$cfg" web_dashboard_open_on_launch false
}

# ---------------------------------------------------------------- step 9: skills

hermes_skills() {
    # Only plain-SKILL.md skills (no plugin form); Claude-only packs go through `claude -p`.
    # Our copies carry a .ai-managed marker. A same-name skill without it is moved to a backup
    # first and comes back on uninstall (S5).
    local s n dest hh bk
    [ -d "$AI_HOME/ai/skills" ] || return 0
    hh=$(hermes_home)
    for s in "$AI_HOME"/ai/skills/*/; do
        [ -f "$s/SKILL.md" ] || continue
        n=$(basename "$s")
        dest="$hh/.hermes/skills/$n"
        if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] copy skill $n to $dest (a foreign one is backed up)"; continue; fi
        if sudo -n -u "$HERMES_USER" test -d "$dest" && ! sudo -n -u "$HERMES_USER" test -f "$dest/.ai-managed"; then
            bk="$hh/.local/state/ai/backup/skills/$n.$(date +%Y%m%d-%H%M%S)"
            sudo -u "$HERMES_USER" -H sh -c "mkdir -p \"\$(dirname '$bk')\" && mv '$dest' '$bk'"
            aiconf_hermes record-cmd "skill-backup:$n" -- sh -c 'rm -rf "$1" && mv "$2" "$1"' sh "$dest" "$bk"
            info "Hermes skill $n was not ours: moved to $bk"
        fi
        tar -C "$AI_HOME/ai/skills" -cf - "$n" | sudo -u "$HERMES_USER" -H sh -c "mkdir -p '$hh/.hermes/skills' && rm -rf '$dest' && tar -C '$hh/.hermes/skills' -xf - && touch '$dest/.ai-managed'"
        aiconf_hermes record-cmd "skill:$n" -- rm -rf "$dest"
    done
    ok "Hermes: plain skills copied to ~$HERMES_USER/.hermes/skills"
}

# ---------------------------------------------------------------- step 10: hooks

hermes_hooks() {
    # Hermes plugin (pre_llm_call router, system-prompt section) is built by agent B.
    local src="$AI_HOME/ai/hooks/hermes"
    if [ -d "$src" ]; then
        local staged; staged=$(hermes_stage_dir "$src" hermes-plugin)
        as_hermes "mkdir -p ~/.hermes/plugins && rm -rf ~/.hermes/plugins/ai-core && cp -R '$staged' ~/.hermes/plugins/ai-core"
        aiconf_hermes record-cmd hermes-plugin:ai-core -- rm -rf "$(hermes_home)/.hermes/plugins/ai-core"
        manual "Hermes: enable the ai-core plugin (plugins.enabled) and restart the gateway"
        ok "Hermes plugin files in ~$HERMES_USER/.hermes/plugins/ai-core"
    else
        skip "Hermes plugin: ai/hooks/hermes not built (agent B)"
    fi
}

# ---------------------------------------------------------------- step 11: rules

hermes_rules() {
    local tmp adhd staged
    tmp=$(rules_text_file)
    # i-have-adhd rules appended (Hermes has no plugin form for it, SPEC 5).
    adhd="$(plugin_src_dir i-have-adhd)/skills/i-have-adhd/SKILL.md"
    [ -f "$adhd" ] || adhd="$AI_HOME/ai/rules/vendor/i-have-adhd-1ecea19-SKILL.md"
    if [ -f "$adhd" ]; then printf '\n' >> "$tmp"; awk 'NR==1 && /^---$/ {f=1; next} f && /^---$/ {f=0; next} !f' "$adhd" >> "$tmp"; fi
    staged=$(hermes_stage "$tmp" soul-block.md)
    aiconf_hermes block-upsert "$(hermes_home)/.hermes/SOUL.md" core 1 "$staged"
    rm -f "$tmp"
    ok "Hermes: managed block in ~$HERMES_USER/.hermes/SOUL.md (root rules + i-have-adhd)"
}

# ---------------------------------------------------------------- step 12: env

hermes_env() {
    as_hermes_ro 'command -v hermes' >/dev/null || return 0
    local key want cur
    for kv in "approvals.mode=manual" "unauthorized_dm_behavior=ignore"; do
        key=${kv%%=*}; want=${kv#*=}
        cur=$(as_hermes_ro "hermes config get $key" | tail -n1 | tr -d '[:space:]' || true)
        if [ "$cur" = "$want" ]; then info "Hermes $key = $want"; continue; fi
        if [ -n "$cur" ]; then
            aiconf_hermes record-cmd "hermes-config:$key" -- hermes config set "$key" "$cur"
        else
            manual "Hermes $key had no value before install: uninstall cannot unset it (hermes config has no unset we verified)"
        fi
        as_hermes "hermes config set $key $want"
        ok "Hermes $key = $want (was ${cur:-unset})"
    done
}
