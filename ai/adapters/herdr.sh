# ai/adapters/herdr.sh: herdr has no agent-config surface of its own; it installs status hooks
# into Claude and Codex with its own command, and has update checks on by default.

herdr_hooks() {
    has herdr || { skip "herdr integrations: herdr not found"; return 0; }
    local a
    for a in claude codex; do
        want "$a" && has "$a" || continue
        if herdr integration status "$a" 2>/dev/null | grep -qiE 'installed|enabled|ok' \
            && ! herdr integration status "$a" 2>/dev/null | grep -qiE 'not installed|missing'; then
            info "herdr integration for $a present"
            continue
        fi
        run herdr integration install "$a" </dev/null || { warn "herdr integration install $a failed"; continue; }
        aiconf record-cmd "herdr-integration:$a" -- herdr integration uninstall "$a"
        ok "herdr integration for $a"
    done
}

herdr_env() {
    local f="${HERDR_CONFIG_PATH:-$HOME/.config/herdr/config.toml}"
    aiconf toml-set "$f" update version_check false
    aiconf toml-set "$f" update manifest_check false
    ok "herdr: version and manifest checks off (never run 'herdr update')"
}
