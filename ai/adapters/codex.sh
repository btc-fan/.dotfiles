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
    local skip=()
    box_present || skip=(--skip box)
    aiconf mcp-register codex --mcp-json "$(PLUGIN_DIR)/.mcp.json" --plugin-root "$(PLUGIN_DIR)" ${skip[@]+"${skip[@]}"}
    if box_present; then
        # The box server runs outside Codex's sandbox (MCP servers are not sandboxed): the only way a sandboxed
        # Codex reaches the root socket. exec may run 3600 s; box work runs without an approval prompt (the box
        # is the boundary; proj-agent refuses anything off its menu).
        aiconf toml-set "$CODEX_DIR/config.toml" mcp_servers.box tool_timeout_sec 3720
        aiconf toml-set "$CODEX_DIR/config.toml" mcp_servers.box default_tools_approval_mode '"approve"'
    fi
    ok "Codex MCP: context7$(box_present && echo ', box') (github, grounded-docs and the global serena were dropped)"
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
    if [ "$AI_OS" != linux ] || ! grep -qs 'agent-plugins/ponytail' /etc/codex/hooks.json; then
        manual "Codex: open /hooks once and trust the hooks of ponytail and i-have-adhd (ai-core, rtk, graphify are trusted by install)"
    fi

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
    mattpocock_link "$HOME/.agents/skills"
    ok "Codex/opencode: shared skills and the 5 mattpocock skills linked into ~/.agents/skills"
}

# ---------------------------------------------------------------- step 10: hooks

codex_hooks() {
    has codex || return 0
    # graphify is opt-in per project now: no global graphify hook (its Codex hook was a no-op anyway).
    aiconf hooks-remove "$CODEX_DIR/hooks.json" 'graphify"? hook-check'
    if has rtk && grep -qs 'rtk' /etc/codex/hooks.json; then
        # The admin layer carries the RTK hook: a user copy would only be an untrusted duplicate.
        if grep -qs rtk "$CODEX_DIR/hooks.json"; then
            run rtk init -g --codex --uninstall </dev/null || warn "rtk init -g --codex --uninstall failed"
            aiconf record-cmd rtk:codex-user-removed -- rtk init -g --codex
            info "RTK for Codex comes from /etc/codex/hooks.json: user copy removed"
        else
            info "RTK for Codex comes from /etc/codex/hooks.json"
        fi
    elif has rtk; then
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
    codex_trust
}

# Linux admin installs: Codex sandbox and approvals pinned through the documented managed layer
# (codex-rs config_requirements.rs at 0.167.0: allowed_sandbox_modes, allowed_approval_policies in
# /etc/codex/requirements.toml) and system defaults in /etc/codex/config.toml (users may tighten, not loosen).
# workspace-write keeps the network off by default. Codex cannot deny reads of home files (no read deny list
# in its sandbox): a documented gap, covered by no network in workspace-write.
codex_system_policy() {
    [ "$AI_OS" = linux ] && [ "$AI_MODE" != user ] || return 0
    want codex || return 0
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/ai-codex-req.XXXXXX")
    cat > "$tmp" <<'EOR'
# Managed by install.sh (ai branch). Codex reads this as the system requirements layer.
# Codex workspace-write on Linux blocks every socket connect (seccomp), so `proj-agent` (the socket client)
# fails inside it. Box work goes through the box MCP server (codex_mcp), which runs outside the sandbox.
allowed_sandbox_modes = ["read-only", "workspace-write"]
# "never" is allowed for `codex exec` (headless: no one to approve; without it exec falls back to untrusted and
# runs nothing). The sandbox stays: never only means "do not ask", the command still runs in workspace-write.
allowed_approval_policies = ["untrusted", "on-request", "never"]
EOR
    aiconf_root file-put /etc/codex/requirements.toml "$tmp" --mode 644
    rm -f "$tmp"
    aiconf_root toml-set /etc/codex/config.toml "" sandbox_mode '"workspace-write"'
    aiconf_root toml-set /etc/codex/config.toml "" approval_policy '"on-request"'
    aiconf_root toml-set /etc/codex/config.toml sandbox_workspace_write network_access false
    ok "Codex: sandbox read-only/workspace-write only, approvals untrusted/on-request/never (default workspace-write, on-request, no network)"
}

# Linux admin installs (system mode): the ai-core and RTK Codex hooks go to /etc/codex/hooks.json. Codex
# loads it as the system config layer, which is managed: no per-user trust hash, always on, for every
# user (codex-rs discovery.rs: System layer is_managed; loader puts /etc/codex in the layer stack even
# without a config.toml). Commands point at the root-owned copy ($AI_HOME = /usr/local/lib/ai/repo), so
# no user can change what runs for another. The plugin manifest of that copy then points at an empty
# hooks file, so Codex does not also load an untrusted plugin copy ("Hooks need review" every start).
# Not used in "all" mode (AI_HOME is a user-writable work tree) or on macOS: there, trust hashes.
codex_system_hooks() {
    [ "$AI_OS" = linux ] && [ "$AI_MODE" = system ] || return 0
    want codex || return 0
    local p tmp th extra=""
    p=$(PLUGIN_DIR)
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-codex-hooks.XXXXXX")
    # Owner decision 2026-11-12: the audited Ponytail and i-have-adhd hooks go here too (root-owned sources).
    local vendor="" v
    for v in ponytail i-have-adhd; do
        [ -d "$(plugin_src_dir "$v")/.codex-plugin" ] && vendor="$vendor --plugin $(plugin_src_dir "$v")"
    done
    if has rtk && [ "$AI_DRY_RUN" != 1 ]; then
        # What this rtk version writes for Codex, captured in a throwaway HOME (only its rtk handlers are kept).
        th=$(mktemp -d "${TMPDIR:-/tmp}/ai-rtk.XXXXXX")
        mkdir -p "$th/.codex"
        HOME="$th" CODEX_HOME="$th/.codex" rtk init -g --codex </dev/null >/dev/null 2>&1 || true
        [ -f "$th/.codex/hooks.json" ] && extra="--extra $th/.codex/hooks.json"
    fi
    # shellcheck disable=SC2086
    if ! python3 "$AI_HOME/ai/lib/aiconf.py" --state /dev/null codex-managed-hooks --plugin-root "$p" \
        --hooks "$p/hooks/codex-hooks.json" $extra $vendor > "$tmp"; then
        warn "Codex managed hooks not built: users fall back to trust hashes"; rm -rf "$tmp" ${th:+"$th"}; return 0
    fi
    rm -rf ${th:+"$th"}
    aiconf_root file-put /etc/codex/hooks.json "$tmp" --mode 644
    rm -f "$tmp"
    # The root-owned copy only (rebuilt by every admin run): plugin hooks -> the empty managed file.
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] $p/.codex-plugin/plugin.json hooks -> ./hooks/codex-hooks.managed.json (root-owned copy)"
    else
        python3 - "$p/.codex-plugin/plugin.json" <<'EOS'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["hooks"] = "./hooks/codex-hooks.managed.json"
open(path, "w").write(json.dumps(data, indent=2) + "\n")
EOS
    fi
    ok "Codex: ai-core$( [ -n "$extra" ] && printf ', RTK')$( [ -n "$vendor" ] && printf ', Ponytail, i-have-adhd') hooks in /etc/codex/hooks.json (managed layer, no trust step)"
}

# Codex skips every non-managed hook it has no matching trust hash for (0 Codex sessions in fired.jsonl).
# Write the hashes for exactly our hooks: the installed ai-core plugin, and the rtk/graphify entries of
# ~/.codex/hooks.json. Recomputed on every install and ai-sync (a changed hook or plugin file = new hash).
codex_trust() {
    has codex || return 0
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] aiconf codex-trust-hooks $CODEX_DIR/config.toml --auto"; return 0; fi
    # Plugins whose hooks run from /etc/codex/hooks.json: their plugin copies are switched off (and marked
    # reviewed, so Codex does not ask about them at every start).
    local args="--verify-source ai-core@ai=$(PLUGIN_DIR)" pid rc=0
    for pid in ponytail@ponytail i-have-adhd@i-have-adhd; do
        if grep -qs "agent-plugins/${pid%@*}" /etc/codex/hooks.json; then
            args="$args --disable $pid --verify-source $pid=$(plugin_src_dir "${pid%@*}")"
        fi
    done
    # The plugin cache is user-writable: a content hash is approved only when the cache equals its source.
    # `codex plugin add` keeps a cache whose version did not change, so a cache that differs is replaced by
    # a copy of its source (--refresh-stale) before the hashes are computed. Exit 4 = still differs.
    # shellcheck disable=SC2086
    aiconf codex-trust-hooks "$CODEX_DIR/config.toml" --auto --refresh-stale $args || rc=$?
    case "$rc" in
        0) ok "Codex: hook entries for ai-core, rtk, graphify (and switched-off plugin copies) in $CODEX_DIR/config.toml" ;;
        4) warn "Codex plugin copy still differs from its source after a reinstall: its hooks are not trusted" ;;
        *) warn "Codex hook trust not written: open /hooks in Codex once and trust the ai-core hooks" ;;
    esac
}

# ---------------------------------------------------------------- step 12: env

codex_env() {
    local f="$CODEX_DIR/config.toml"
    aiconf toml-set "$f" "" check_for_update_on_startup false
    aiconf toml-set "$f" "" project_doc_max_bytes 65536
    aiconf toml-set "$f" analytics enabled false
    aiconf toml-set "$f" feedback enabled false
    # The env switches for every command Codex runs (Codex starts no login shell, /etc/profile.d is not read).
    local k v
    while IFS='=' read -r k v; do
        [ -n "$k" ] && aiconf toml-set "$f" shell_environment_policy.set "$k" "\"$v\""
    done <<EOT
$(env_pairs)
EOT
    # Agent mode of the server's git guard (every repo hardened). Codex builds the command env from this policy
    # once per request, before it picks the sandbox, so an approved command outside the sandbox gets it too
    # (codex-rs 0.167 core/src/unified_exec/process_manager.rs open_session_with_sandbox: create_env first).
    aiconf toml-set "$f" shell_environment_policy.set GIT_GUARD_AGENT '"1"'
    ok "Codex: update check, analytics, feedback off; project_doc_max_bytes 65536; env switches and GIT_GUARD_AGENT in shell_environment_policy.set"
}
