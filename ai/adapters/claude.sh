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

# Marketplace source as Claude stored it in known_marketplaces.json, in one comparable form:
# github:<Owner/repo>#<ref>, git:<url>#<ref>, directory:<real path>; empty when the marketplace is not known.
claude_marketplace_src() {
    python3 - "$CLAUDE_PLUGINS_DIR/known_marketplaces.json" "$1" <<'EOS'
import json, os, sys
try:
    src = (json.load(open(sys.argv[1])).get(sys.argv[2]) or {}).get("source") or {}
except (OSError, ValueError):
    src = {}
kind = src.get("source", "")
if kind == "github":
    print("github:%s#%s" % (src.get("repo", ""), src.get("ref") or ""))
elif kind == "git":
    print("git:%s#%s" % (src.get("url", ""), src.get("ref") or ""))
elif kind == "directory":
    print("directory:%s" % os.path.realpath(src.get("path", "")))
elif kind:
    print("%s:%s" % (kind, json.dumps(src, sort_keys=True)))
EOS
}

# The same form for a source as we pass it to `claude plugin marketplace add`: a path, or Owner/repo[#ref].
claude_src_norm() {
    case "$1" in
        /*) printf 'directory:%s\n' "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1")" ;;
        *'#'*) printf 'github:%s#%s\n' "${1%%#*}" "${1#*#}" ;;
        *) printf 'github:%s#\n' "$1" ;;
    esac
}

# same_src <a> <b>: two sources in that form are the same (GitHub owner/repo names ignore case).
same_src() {
    case "$1" in
        github:*) [ "$(printf '%s' "${1%%#*}" | tr 'A-Z' 'a-z')#${1#*#}" = "$(printf '%s' "${2%%#*}" | tr 'A-Z' 'a-z')#${2#*#}" ] ;;
        *) [ "$1" = "$2" ] ;;
    esac
}

# The add form of a stored source (for a restore record): the reverse of claude_marketplace_src.
claude_src_add_form() {
    case "$1" in
        directory:*) printf '%s\n' "${1#directory:}" ;;
        github:*'#') printf '%s\n' "${1#github:}" | sed 's/#$//' ;;
        github:*|git:*) printf '%s\n' "${1#*:}" | sed 's/#$//' ;;
        *) printf '%s\n' "${1#*:}" ;;
    esac
}

# state_has <key>: true when this setup recorded <key> in its state file (we added that thing).
state_has() {
    python3 - "$AI_STATE_FILE" "$1" <<'EOS'
import json, sys
try:
    entries = json.load(open(sys.argv[1])).get("entries") or []
except (OSError, ValueError):
    entries = []
sys.exit(0 if any(e.get("key") == sys.argv[2] for e in entries) else 1)
EOS
}

# claude_plugin_info <plugin@marketplace>: "<version> <gitCommitSha>" of the installed plugin (installed_plugins.json).
claude_plugin_info() {
    python3 - "$CLAUDE_PLUGINS_DIR/installed_plugins.json" "$1" <<'EOS'
import json, sys
try:
    rows = (json.load(open(sys.argv[1])).get("plugins") or {}).get(sys.argv[2]) or []
except (OSError, ValueError):
    rows = []
row = rows[0] if rows else {}
print("%s %s" % (row.get("version") or "-", row.get("gitCommitSha") or "-"))
EOS
}

# claude_enabled_get <plugin@marketplace>: the user's enabledPlugins value in settings.json (true, false, or
# nothing). claude_enabled_set <plugin> <value>: put it back after an uninstall + install (not recorded: it is
# the user's own value, not ours).
claude_enabled_get() {
    python3 - "$CLAUDE_DIR/settings.json" "$1" <<'EOS'
import json, sys
try:
    v = (json.load(open(sys.argv[1])).get("enabledPlugins") or {}).get(sys.argv[2])
except (OSError, ValueError):
    v = None
print("" if v is None else json.dumps(v))
EOS
}
claude_enabled_set() {
    [ -n "$2" ] && [ "$AI_DRY_RUN" != 1 ] || return 0
    [ "$(claude_enabled_get "$1")" = "$2" ] && return 0
    python3 - "$CLAUDE_DIR/settings.json" "$1" "$2" <<'EOS'
import json, os, sys
path, key, value = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
try:
    data = json.load(open(path))
except (OSError, ValueError):
    data = {}
data.setdefault("enabledPlugins", {})[key] = value
tmp = path + ".ai-tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
os.replace(tmp, path)
EOS
    info "$1: enabledPlugins kept at $2 (the value before the reinstall)"
}

# claude_plugin_current <plugin> <sha> <version> <stamp file>: true when the installed plugin is the wanted one.
# With a commit: Claude's gitCommitSha when it records one (github marketplaces), else the stamp this setup
# wrote after the last verified install (local folder marketplaces: a new tag with the same plugin.json version
# still counts as new), else unknown (false: refresh once). Without a commit: the version.
claude_plugin_current() {
    local plugin=$1 sha=$2 want=$3 stamp=$4 info iver isha
    info=$(claude_plugin_info "$plugin"); iver=${info%% *}; isha=${info##* }
    if [ -n "$sha" ]; then
        [ "$isha" != - ] && { [ "$isha" = "$sha" ]; return; }
        [ -f "$stamp" ] || return 1
        [ "$(cat "$stamp")" = "$sha" ] || return 1
        [ -z "$want" ] || [ "$iver" = "$want" ]
        return
    fi
    [ -z "$want" ] || [ "$iver" = "$want" ]
}

# claude_plugin_verified <plugin> <sha> <version>: after an install or update, what Claude reports: its
# gitCommitSha when it records one, else the version (a local folder marketplace has no commit in Claude).
claude_plugin_verified() {
    local plugin=$1 sha=$2 want=$3 info iver isha
    claude_has_plugin "$plugin" || return 1
    info=$(claude_plugin_info "$plugin"); iver=${info%% *}; isha=${info##* }
    if [ -n "$sha" ] && [ "$isha" != - ]; then [ "$isha" = "$sha" ]; return; fi
    [ -z "$want" ] || [ "$iver" = "$want" ]
}

# Replace a marketplace that points to another source (a foreign one, or ours at an older tag: the claude CLI
# stores the ref and `marketplace update` never changes it, so a new tag needs remove + add). The plugin is
# uninstalled first with --keep-data (its data folder stays; removing the marketplace alone would uninstall it
# without that flag). A marketplace this setup did not add gets a restore record: uninstall.sh first removes
# ours, then adds the old source back (and its plugin). If the add fails, the old source and the plugin come back
# at once (claude_replace_rollback). Sets CLAUDE_REPLACED_FROM to the old source.
CLAUDE_REPLACED_FROM=""
claude_marketplace_replace() {
    local mname=$1 msrc=$2 plugin=$3 cur=$4 enabled=$5 old had=0
    old=$(claude_src_add_form "$cur")
    claude_has_plugin "$plugin" && had=1
    if ! state_has "cmd:claude-marketplace:$mname"; then
        if [ $had = 1 ]; then
            aiconf record-cmd "claude-marketplace-restore:$mname" -- sh -c \
                'claude plugin marketplace add "$1" && claude plugin install "$2" --scope user' _ "$old" "$plugin"
        else
            aiconf record-cmd "claude-marketplace-restore:$mname" -- claude plugin marketplace add "$old"
        fi
    fi
    info "marketplace $mname points to $old, ours is $msrc: replaced (plugin data kept)"
    [ $had = 0 ] || run claude plugin uninstall "$plugin" --keep-data || true
    if ! run claude plugin marketplace remove "$mname"; then
        warn "claude plugin marketplace remove $mname failed: left as it is"
        [ $had = 0 ] || { run claude plugin install "$plugin" --scope user || true; claude_enabled_set "$plugin" "$enabled"; }
        return 1
    fi
    CLAUDE_REPLACED_FROM=$old
    if ! run claude plugin marketplace add "$msrc"; then
        warn "claude plugin marketplace add $msrc failed: the old source $old is put back"
        claude_replace_rollback "$mname" "$plugin" "$enabled" "$had"
        return 1
    fi
    aiconf record-cmd "claude-marketplace:$mname" -- claude plugin marketplace remove "$mname"
}

# claude_replace_rollback <mname> <plugin> <enabled value> <had plugin 0|1>: after a failed replace, the old
# marketplace source and the plugin (with its enabledPlugins value) come back.
claude_replace_rollback() {
    local mname=$1 plugin=$2 enabled=$3 had=${4:-1} old=$CLAUDE_REPLACED_FROM
    [ -n "$old" ] || return 0
    CLAUDE_REPLACED_FROM=""
    claude_marketplace_src "$mname" | grep -q . && run claude plugin marketplace remove "$mname" || true
    if run claude plugin marketplace add "$old"; then
        if [ "$had" = 1 ]; then
            run claude plugin install "$plugin" --scope user || { warn "rollback: $plugin not reinstalled from $old: check /plugin"; return 1; }
            claude_enabled_set "$plugin" "$enabled"
        fi
        info "rollback: marketplace $mname is $old again$([ "$had" = 1 ] && printf ', %s reinstalled' "$plugin")"
    else
        warn "rollback: claude plugin marketplace add $old failed: $plugin is not installed now (check /plugin)"
    fi
}

# git_source_audited <tool name> <repo URL> <ref> <sha>: agent-audit of a git source at <sha> before a plugin
# moves to it. Skipped when the audited plugin source clone (plugin_clone) is already at that commit.
git_source_audited() {
    local name=$1 repo=$2 ref=$3 sha=$4 tmp
    [ -n "$sha" ] || return 0
    [ "$(src_head "$(plugin_src_dir "$name")")" = "$sha" ] && return 0
    if grep -qs "^$sha $name\$" "$AI_STATE_DIR/rejected-shas"; then
        warn "$name ${ref:-${sha:0:12}}: skill-scanner rejected this commit before: not installed (no new scan)"; return 1
    fi
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] git clone $repo at ${ref:-${sha:0:12}}; agent-audit dir"; return 0; fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-$name.XXXXXX")
    git clone -q "$repo" "$tmp/$name" && git -C "$tmp/$name" -c advice.detachedHead=false checkout -q "$sha" \
        || { warn "$name: clone of $repo at $sha failed"; rm -rf "$tmp"; return 1; }
    audit_ok dir "$tmp/$name" "$sha" "$name" || { rm -rf "$tmp"; return 1; }
    local missing
    missing=$(plugin_files_missing "$tmp/$name")
    if [ -n "$missing" ]; then
        warn "$name ${ref:-${sha:0:12}}: files its plugin config starts are not in the git tree ($missing): not installable"
        rm -rf "$tmp"; return 1
    fi
    rm -rf "$tmp"
}

# plugin_files_missing <dir>: the ${CLAUDE_PLUGIN_ROOT}/<path> files that .mcp.json and the hooks JSON of a
# plugin tree name but the tree does not have (OMC v5.8.6: bridge/mcp-server.cjs is a build output, not in git,
# so its MCP server failed with CONNECTION_CLOSED; owner QA 2026-11-15).
plugin_files_missing() {
    python3 - "$1" <<'EOS'
import json, os, re, sys
root = sys.argv[1]
missing = []
for rel in (".mcp.json", ".claude-plugin/plugin.json", "hooks/hooks.json"):
    try:
        text = json.dumps(json.load(open(os.path.join(root, rel))))
    except (OSError, ValueError):
        continue
    for m in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"'\\]+)", text):
        if not os.path.exists(os.path.join(root, m.group(1))) and m.group(1) not in missing:
            missing.append(m.group(1))
print(", ".join(missing[:5]))
EOS
}

# claude_plugin <marketplace-name> <marketplace-source> <plugin@marketplace> [sha] [version]
# Marketplace: added when missing; replaced when it points to another source. Plugin: installed when missing;
# moved when it is not at <sha> / <version> (marketplace update + plugin update, else uninstall --keep-data +
# install), then checked; the user's enabledPlugins value survives every reinstall. A github marketplace clone
# must be at <sha> (the commit the resolver saw for the tag). A failure after a replace puts the old source back.
claude_plugin() {
    local mname=$1 msrc=$2 plugin=$3 sha=${4:-} want=${5:-} cur head stamp enabled before
    stamp="$AI_STATE_DIR/claude-plugin.${plugin%@*}.src"
    enabled=$(claude_enabled_get "$plugin")
    CLAUDE_REPLACED_FROM=""
    cur=$(claude_marketplace_src "$mname")
    if [ -z "$cur" ] && ! claude_has_marketplace "$mname"; then
        run claude plugin marketplace add "$msrc" || { warn "claude plugin marketplace add $msrc failed"; return 1; }
        aiconf record-cmd "claude-marketplace:$mname" -- claude plugin marketplace remove "$mname"
    elif [ -n "$cur" ] && [ "$mname" != ai ] && ! same_src "$cur" "$(claude_src_norm "$msrc")"; then
        # (ai = this repo's own marketplace: never removed here, B2; ai-core is refreshed in place below.)
        claude_marketplace_replace "$mname" "$msrc" "$plugin" "$cur" "$enabled" || return 1
    fi
    case "$msrc" in
        /*) ;;
        *)
            if [ -n "$sha" ] && [ "$AI_DRY_RUN" != 1 ]; then
                head=$(git -C "$CLAUDE_PLUGINS_DIR/marketplaces/$mname" rev-parse HEAD 2>/dev/null || echo unknown)
                if [ "$head" != "$sha" ]; then
                    run claude plugin marketplace update "$mname" || true
                    head=$(git -C "$CLAUDE_PLUGINS_DIR/marketplaces/$mname" rev-parse HEAD 2>/dev/null || echo unknown)
                fi
                if [ "$head" != "$sha" ]; then
                    warn "$mname marketplace is at $head, the resolved source is $sha: plugin not installed or moved (check /plugin)"
                    claude_replace_rollback "$mname" "$plugin" "$enabled"
                    return 1
                fi
            fi
            ;;
    esac
    if claude_has_plugin "$plugin"; then
        if claude_plugin_current "$plugin" "$sha" "$want" "$stamp"; then
            info "$plugin installed${want:+ $want}${sha:+ at ${sha:0:7}}"
            return 0
        fi
        before=$(claude_plugin_info "$plugin")
        run claude plugin marketplace update "$mname" || true
        run claude plugin update "$plugin" || true
        # A local folder marketplace: Claude records no commit, and `plugin update` keeps a cache whose version
        # did not change. Same version, new commit: reinstall so the new files are really copied.
        if [ "$AI_DRY_RUN" != 1 ] && [ -n "$sha" ] && [ "${before##* }" = - ] && [ "$(claude_plugin_info "$plugin")" = "$before" ]; then
            run claude plugin uninstall "$plugin" --keep-data || true
            run claude plugin install "$plugin" --scope user || true
        fi
        if [ "$AI_DRY_RUN" != 1 ] && ! claude_plugin_verified "$plugin" "$sha" "$want"; then
            run claude plugin uninstall "$plugin" --keep-data || true
            run claude plugin install "$plugin" --scope user || true
        fi
        claude_enabled_set "$plugin" "$enabled"
        if [ "$AI_DRY_RUN" = 1 ] || claude_plugin_verified "$plugin" "$sha" "$want"; then
            [ -z "$sha" ] || [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$sha" > "$stamp"; }
            ok "Claude plugin $plugin moved to ${want:-${sha:0:7}} (newest stable)"
            return 0
        fi
        warn "Claude plugin $plugin is $(claude_plugin_info "$plugin") after update, wanted ${want:-$sha}: check /plugin"
        return 1
    fi
    # A marketplace can be declared but not loaded, or loaded from an older tree ("plugin not found"):
    # refresh it once and retry before giving up (old Mac, 2026-11-12).
    if ! run claude plugin install "$plugin" --scope user; then
        run claude plugin marketplace update "$mname" || run claude plugin marketplace add "$msrc" || true
        if ! run claude plugin install "$plugin" --scope user; then
            warn "claude plugin install $plugin failed"
            claude_replace_rollback "$mname" "$plugin" "$enabled"
            return 1
        fi
    fi
    aiconf record-cmd "claude-plugin:$plugin" -- claude plugin uninstall "$plugin"
    claude_enabled_set "$plugin" "$enabled"
    if [ "$AI_DRY_RUN" != 1 ] && ! claude_plugin_verified "$plugin" "$sha" "$want"; then
        warn "Claude plugin $plugin installed but Claude reports $(claude_plugin_info "$plugin"), wanted ${want:-$sha}: check /plugin"
        return 1
    fi
    [ -z "$sha" ] || [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$sha" > "$stamp"; }
    ok "Claude plugin $plugin (user scope)"
}

# claude_git_plugin <tool id> <marketplace-name> <Owner/repo> <plugin@marketplace>: a plugin from a github
# marketplace at the resolved tag (Owner/repo#<tag>; no tag: the default branch), audited before it moves.
claude_git_plugin() {
    local tool=$1 mname=$2 repo=$3 plugin=$4 src I_VERSION="" I_SHA="" I_SCANNED=0 X_VERSION=""
    resolve_tool "$tool" || return 1
    eval "$(resolver installed-info "$tool" 2>/dev/null)"
    src="$repo${R_REF:+#$R_REF}"
    # A copy installed before this setup audited it (I_SCANNED 0, e.g. OMC 5.8.6 before the skill-scanner rule)
    # is audited again, even when it is the newest.
    if claude_has_plugin "$plugin" && claude_plugin_current "$plugin" "$R_SHA" "" "$AI_STATE_DIR/claude-plugin.${plugin%@*}.src" \
        && same_src "$(claude_marketplace_src "$mname")" "$(claude_src_norm "$src")" \
        && { [ "$I_SCANNED" = 1 ] || [ "$I_SHA" != "$R_SHA" ]; }; then
        info "$plugin at ${R_REF:-${R_SHA:0:7}} (newest stable)"; return 0
    fi
    if [ "$R_STATUS" = cached ] && claude_has_plugin "$plugin"; then info "$plugin kept (offline)"; return 0; fi
    if [ -n "$R_VERSION" ] && [ "$X_VERSION" = "$R_VERSION" ]; then
        warn "$plugin ${R_REF:-$R_VERSION} was rejected by skill-scanner before: not installed"
    elif git_source_audited "$tool" "${R_SOURCE#git }" "$R_REF" "$R_SHA"; then
        claude_plugin "$mname" "$src" "$plugin" "$R_SHA" || return 1
        r_record
        return 0
    fi
    claude_git_plugin_fallback "$tool" "$mname" "$repo" "$plugin"
}

# The newest version failed (skill-scanner reject or files missing): the newest older stable tag that passes
# (at most 5 tried, newest first). The installed copy counts when this setup audited it. None passes: the
# installed copy stays, with a loud warning when it is that failing version itself (ai-doctor FAILs it).
claude_git_plugin_fallback() {
    local tool=$1 mname=$2 repo=$3 plugin=$4 newest=$R_VERSION line v ref sha
    for line in $(resolver candidates "$tool" --max 5 --below "${R_REF:-$R_VERSION}" 2>/dev/null | tr ' ' '|'); do
        v=${line%%|*}; ref=${line#*|}; sha=${ref#*|}; ref=${ref%%|*}
        if [ "$v" = "$I_VERSION" ] && [ "$I_SCANNED" = 1 ] && claude_has_plugin "$plugin"; then
            warn "$plugin: newest $newest failed the audit; the installed $v (audited) stays"; return 0
        fi
        R_VERSION=$v; R_REF=$ref; R_SHA=$sha
        if git_source_audited "$tool" "${R_SOURCE#git }" "$ref" "$sha"; then
            claude_plugin "$mname" "$repo#$ref" "$plugin" "$sha" || return 1
            r_record
            warn "$plugin moved to $ref, the newest version that passes the audit ($newest failed it)"
            return 0
        fi
    done
    if claude_has_plugin "$plugin" && [ "$I_VERSION" = "$newest" ]; then
        warn "LOUD: $plugin $I_VERSION is installed and fails the audit itself (skill-scanner reject or files missing), and none of the 5 older versions passes: it stays installed; remove it by hand if you agree (claude plugin uninstall $plugin)"
    else
        warn "$plugin not moved to $newest: audit (no older version of the last 5 passes either)"
    fi
    return 1
}

# plugin_json_version <dir>: "version" of <dir>/.claude-plugin/plugin.json, or nothing.
plugin_json_version() {
    python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("version") or "")
except Exception: pass' "$1/.claude-plugin/plugin.json"
}

# B2: ai-core must be installed AND enabled before we remove anything it replaces.
claude_ai_core_ok() {
    [ "$AI_DRY_RUN" = 1 ] && return 0   # plan only: the moves below print, they do not run
    local listing
    listing=$(claude plugin list 2>/dev/null || true)
    printf '%s\n' "$listing" | grep -qF 'ai-core@ai' || return 1
    printf '%s\n' "$listing" | claude_listed_disabled ai-core@ai && return 1
    [ "$(aiconf json-get "$CLAUDE_DIR/settings.json" 'enabledPlugins/ai-core@ai' 2>/dev/null)" = true ]
}

# claude_listed_disabled <plugin@marketplace>: true when `claude plugin list` (on stdin) shows that plugin
# disabled. The CLI prints a block per plugin with "Status: ... disabled" on its own line (2.1.x); a status on
# the name line counts too.
claude_listed_disabled() {
    awk -v p="$1" 'index($0, p) { f = 1; if (tolower($0) ~ /disabled/) d = 1; next }
        f && /^[[:space:]]*$/ { f = 0 }
        f && /❯/ { f = 0 }
        f && tolower($0) ~ /status:.*disabled/ { d = 1 }
        END { exit d ? 0 : 1 }'
}

# ---------------------------------------------------------------- step 7: MCP

claude_mcp() {
    has claude || { skip "Claude MCP: claude not found"; return 0; }
    # The ai-core plugin serves Serena, context7, GitHub, Grounded Docs. Any user-scope copy (the
    # hand-made config registered Serena there) is moved in step 8, after ai-core is verified.
    info "Claude MCP: served by the ai-core plugin (user-scope duplicates are moved after the plugin check)"
    # Dropped servers (AI_DROP_MCP in ai/pins.env): removed from user scope, each entry saved for uninstall.
    [ -z "${AI_DROP_MCP:-}" ] || aiconf claude-drop-mcp "$(CLAUDE_JSON)" $AI_DROP_MCP
}

# Remove user-scope MCP copies and settings.json hook copies, only when ai-core is live.
claude_take_over() {
    if ! claude_ai_core_ok; then
        warn "ai-core@ai is not installed and enabled: user-scope MCP and settings.json hooks left untouched"
        return 0
    fi
    aiconf claude-take-mcp "$(CLAUDE_JSON)" "$(PLUGIN_DIR)/.mcp.json"
    local hooks; hooks="$(PLUGIN_DIR)/hooks/hooks.json"
    if [ -f "$hooks" ]; then
        aiconf claude-adopt-hooks "$CLAUDE_DIR/settings.json" "$hooks"
        ok "Claude: ai-core verified; it now owns the MCP servers and hooks it ships (no duplicates)"
    else
        warn "plugin hooks/hooks.json missing: settings.json hooks left as they are"
    fi
}

# Newest cached copy of ai-core, or empty.
claude_ai_core_cache() {
    ls -td "$CLAUDE_PLUGINS_DIR"/cache/ai/ai-core/* 2>/dev/null | head -n1 || true
}

# ---------------------------------------------------------------- step 8: plugins

claude_plugins() {
    has claude || { skip "Claude plugins: claude not found"; return 0; }
    local p hash_file hash old="" cache
    p=$(PLUGIN_DIR)

    # ai-core from this repo (directory marketplace).
    hash_file="$AI_STATE_DIR/ai-core.claude.hash"
    hash=$(aiconf tree-hash "$p")
    [ -f "$hash_file" ] && old=$(cat "$hash_file")
    if claude_has_plugin ai-core@ai && [ "$hash" != "$old" ]; then
        # B2: refresh in place; never uninstall first. Check the cache against the source after.
        run claude plugin marketplace update ai || warn "claude plugin marketplace update ai failed"
        run claude plugin update ai-core@ai || warn "claude plugin update ai-core@ai failed"
        cache=$(claude_ai_core_cache)
        # `claude plugin update` keeps a cache whose version number did not change: copy the repo over it.
        if [ "$AI_DRY_RUN" != 1 ] && [ -n "$cache" ] && [ "$(aiconf tree-hash "$cache")" != "$hash" ]; then
            aiconf tree-sync "$p" "$cache" >/dev/null
        fi
        if [ "$AI_DRY_RUN" = 1 ] || { [ -n "$cache" ] && [ "$(aiconf tree-hash "$cache")" = "$hash" ]; }; then
            ok "Claude plugin ai-core@ai updated (cache matches the repo)"
        else
            warn "ai-core cache does not match the repo after update and copy: ${cache:-no cache folder}"
            manual "refresh ai-core by hand when no session runs: claude plugin uninstall ai-core@ai && claude plugin install ai-core@ai --scope user"
            hash=$old
        fi
    else
        claude_plugin ai "$AI_HOME/ai/marketplace" ai-core@ai || true
    fi
    [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$hash" > "$hash_file"; }

    claude_take_over

    # Ponytail and i-have-adhd from the audited local copies (plugin_clone moves them to the newest stable tag):
    # the plugin follows its source (marketplace update + plugin update, checked against the source commit).
    local pn d
    for pn in ponytail i-have-adhd; do
        d=$(plugin_src_dir "$pn")
        if [ -d "$d" ] || [ "$AI_DRY_RUN" = 1 ]; then
            claude_plugin "$pn" "$d" "$pn@$pn" "$(src_sha_for "$pn")" "$(plugin_json_version "$d")" || true
        else
            skip "$pn: audited source missing"
        fi
    done
    # Always-on flag (empty file; the hook tests existence). Codex reads the same path.
    local empty; empty=$(mktemp "${TMPDIR:-/tmp}/ai-empty.XXXXXX")
    aiconf file-put "$CLAUDE_DIR/.i-have-adhd-always" "$empty" --mode 644
    rm -f "$empty"

    # claude-seo, claude-blog: the resolved tag in the add command, its commit checked after the clone.
    claude_git_plugin claude-seo agricidaniel-claude-seo AgriciDaniel/claude-seo claude-seo@agricidaniel-claude-seo || true
    claude_git_plugin claude-blog agricidaniel-blog AgriciDaniel/claude-blog claude-blog@agricidaniel-blog || true
    # Owner decision 2026-11-12: opt-in per project (about 12k tokens per session each). Installed, but OFF
    # at user scope (claude_plugins_off, AI_OFF_CLAUDE_PLUGINS); a project turns one on with ai-adopt --tools
    # seo|blog, which writes enabledPlugins true in its .claude/settings.json (project settings win over user).
    claude_omc_wiring
    # Serena: opt-in per project (owner decision 2026-11-12). Installed, OFF at user scope; a project turns it
    # on with ai-adopt --tools serena (project enabledPlugins ai-serena@ai = true).
    # Playwright the same way (project .mcp.json no longer loads under the managed mcp lock).
    # Serena: ON at user scope (owner decision 2026-11-12, evening: Serena and graphify on by default in every
    # project; `no-serena` in a project's .ai/enabled turns it off there). Playwright stays opt-in per project.
    local op
    for op in ai-serena@ai ai-playwright@ai; do
        claude_plugin ai "$AI_HOME/ai/marketplace" "$op" || true
    done
    aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/ai-serena@ai" true
    aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/ai-playwright@ai" false
    claude_box_plugin
    claude_take_serena
    manual "Claude, once per machine, in a project with claude-seo on: /seo setup, then /seo doctor (venv + Chromium)"

    claude_last30days
    claude_plugins_off
    claude_drop_plugins
}

# The box MCP server is its own plugin, ai-box@ai (owner decision 2026-11-14): profile server installs it (its
# tools list nothing where no proj-agent runs); profile dev-mac never installs it, and removes an earlier one.
# Refreshed like ai-core: a changed tree (tree-hash) is updated in place and copied over a stale cache.
claude_box_plugin() {
    local p="$AI_HOME/ai/marketplace/plugins/ai-box" hf="$AI_STATE_DIR/ai-box.claude.hash" hash old="" cache
    if [ "${PROFILE_BOX:-1}" = 1 ]; then
        hash=$(aiconf tree-hash "$p")
        [ -f "$hf" ] && old=$(cat "$hf")
        if claude_has_plugin ai-box@ai && [ "$hash" != "$old" ]; then
            run claude plugin marketplace update ai || warn "claude plugin marketplace update ai failed"
            run claude plugin update ai-box@ai || warn "claude plugin update ai-box@ai failed"
            cache=$(ls -td "$CLAUDE_PLUGINS_DIR"/cache/ai/ai-box/* 2>/dev/null | head -n1 || true)
            if [ "$AI_DRY_RUN" != 1 ] && [ -n "$cache" ] && [ "$(aiconf tree-hash "$cache")" != "$hash" ]; then
                aiconf tree-sync "$p" "$cache" >/dev/null
            fi
            if [ "$AI_DRY_RUN" = 1 ] || { [ -n "$cache" ] && [ "$(aiconf tree-hash "$cache")" = "$hash" ]; }; then
                ok "Claude plugin ai-box@ai updated (cache matches the repo)"
            else
                warn "ai-box cache does not match the repo after update and copy: ${cache:-no cache folder}"
                hash=$old
            fi
        else
            claude_plugin ai "$AI_HOME/ai/marketplace" ai-box@ai || true
        fi
        [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; printf '%s\n' "$hash" > "$hf"; }
    elif claude_has_plugin ai-box@ai; then
        run claude plugin uninstall ai-box@ai || { warn "claude plugin uninstall ai-box@ai failed"; return 0; }
        ok "Claude plugin ai-box@ai removed (profile $AI_PROFILE has no box)"
    else
        info "box MCP: not installed (profile $AI_PROFILE)"
    fi
    return 0
}

# last30days (owner decision 2026-11-14): ON by default for Claude on every machine. Same path as claude-seo:
# newest stable tag, audited, a foreign marketplace replaced by the tag source (plugin data kept).
# Turned on only when the plugin step succeeded. The first run of this setup turns it on (stamp
# last30days.on-once in the state folder); on later runs a value the user set to false is kept.
claude_last30days() {
    local pk=last30days@last30days-skill stamp="$AI_STATE_DIR/last30days.on-once"
    # Profile dev-mac (owner decision 2026-11-14): no last30days on the Macs; an installed copy is removed.
    if [ "${PROFILE_LAST30DAYS:-1}" = 0 ]; then
        if claude_has_plugin "$pk"; then
            run claude plugin uninstall "$pk" || { warn "claude plugin uninstall $pk failed"; return 0; }
            ok "Claude plugin $pk removed (profile $AI_PROFILE has no last30days)"
        else
            info "last30days: not installed (profile $AI_PROFILE)"
        fi
        return 0
    fi
    claude_git_plugin last30days last30days-skill mvanhorn/last30days-skill "$pk" || return 0
    if [ -f "$stamp" ] && [ "$(claude_enabled_get "$pk")" = false ]; then
        info "$pk is off by your choice (enabledPlugins false): kept"
        return 0
    fi
    aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/$pk" true
    [ "$AI_DRY_RUN" = 1 ] || { mkdir -p "$AI_STATE_DIR"; : > "$stamp"; }
}

# Off by default (AI_OFF_CLAUDE_PLUGINS in ai/pins.env, owner decisions 2026-11-12 and 2026-11-14): installed
# plugins on that list get enabledPlugins false at user scope (recorded; uninstall puts the old value back).
# A project turns one on with ai-adopt where a tool id exists (seo, blog, ui); typesafe has none: just off.
claude_plugins_off() {
    local pk off=""
    for pk in ${AI_OFF_CLAUDE_PLUGINS:-}; do
        claude_has_plugin "$pk" || continue
        aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/$pk" false
        off="$off ${pk%@*}"
    done
    [ -z "$off" ] || ok "Claude: off at user scope:$off (per project: ai-adopt --tools seo,blog,ui)"
}

# Dropped plugins (AI_DROP_CLAUDE_PLUGINS in ai/pins.env): uninstalled with --keep-data, and their marketplace
# removed when no other installed plugin comes from it. One restore record: uninstall.sh adds the old
# marketplace source back and installs the plugin again. The context7 plugin is only reported (owner's call).
claude_drop_plugins() {
    local p m src others en
    for p in ${AI_DROP_CLAUDE_PLUGINS:-}; do
        claude_has_plugin "$p" || continue
        m=${p#*@}
        en=$(claude_enabled_get "$p")
        src=$(claude_src_add_form "$(claude_marketplace_src "$m")")
        others=$(claude_marketplace_users "$m" "$p")
        [ -z "$others" ] && [ "$m" != ai ] || src=""
        run claude plugin uninstall "$p" --keep-data || { warn "claude plugin uninstall $p failed: left as it is"; continue; }
        # Restore: marketplace (when it went), plugin, then its old enabledPlugins value.
        aiconf record-cmd "claude-plugin-restore:$p" -- sh -c \
            '[ -z "$1" ] || claude plugin marketplace add "$1" >/dev/null 2>&1; claude plugin install "$2" --scope user || exit 1; [ -z "$3" ] || python3 -c "import json,sys; f,k,v=sys.argv[1:4]; d=json.load(open(f)); d.setdefault(\"enabledPlugins\",{})[k]=json.loads(v); json.dump(d,open(f,\"w\"),indent=2)" "$4" "$2" "$3"' \
            _ "$src" "$p" "$en" "$CLAUDE_DIR/settings.json"
        if [ -n "$src" ]; then
            run claude plugin marketplace remove "$m" || warn "claude plugin marketplace remove $m failed: left as it is"
        fi
        ok "Claude plugin $p removed (dropped; data kept${src:+; marketplace $m removed}; uninstall.sh restores it)"
    done
    local f="$CLAUDE_PLUGINS_DIR/installed_plugins.json" name
    if [ -f "$f" ]; then
        for name in $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1])).get("plugins",{}).keys()))' "$f" 2>/dev/null); do
            case "$name" in
                context7@*) manual "dropped by design, remove if you agree: claude plugin uninstall $name" ;;
            esac
        done
    fi
    return 0
}

# claude_marketplace_users <marketplace> <plugin>: other installed plugins from that marketplace, one per line.
claude_marketplace_users() {
    python3 - "$CLAUDE_PLUGINS_DIR/installed_plugins.json" "$1" "$2" <<'EOS'
import json, sys
try:
    names = (json.load(open(sys.argv[1])).get("plugins") or {}).keys()
except (OSError, ValueError):
    names = []
for n in names:
    if n.endswith("@" + sys.argv[2]) and n != sys.argv[3]:
        print(n)
EOS
}

# Owner decision 2026-11-14: once ai-serena@ai is installed and enabled, it serves Serena; a user-scope copy
# named serena in ~/.claude.json is moved out (saved, restore recorded), like context7 after ai-core.
# The plugin runs a bare `serena`: without it on PATH the user-scope copy stays (it is the only working one).
claude_take_serena() {
    if [ "$AI_DRY_RUN" != 1 ]; then
        claude_has_plugin ai-serena@ai || return 0
        [ "$(aiconf json-get "$CLAUDE_DIR/settings.json" 'enabledPlugins/ai-serena@ai' 2>/dev/null)" = true ] || return 0
        claude plugin list 2>/dev/null | claude_listed_disabled ai-serena@ai && return 0
        has serena || { info "serena not on PATH: the user-scope serena in $(CLAUDE_JSON) is kept (ai-serena@ai runs a bare serena)"; return 0; }
    fi
    aiconf claude-take-mcp "$(CLAUDE_JSON)" "$AI_HOME/ai/marketplace/plugins/ai-serena/.mcp.json"
}

# Dropped hook entries (AI_DROP_CLAUDE_HOOKS in ai/pins.env): settings.json handlers whose command has one of
# the words are removed (saved, recorded; undo restores). Their script files are not ours: reported, kept.
claude_drop_hooks() {
    [ -n "${AI_DROP_CLAUDE_HOOKS:-}" ] || return 0
    local rx w files="" p
    if [ "$AI_DRY_RUN" != 1 ]; then
        for p in ${AI_DROP_CLAUDE_PLUGINS:-}; do
            if claude_has_plugin "$p"; then
                warn "$p is still installed (its uninstall failed): its settings.json hooks are left as they are"
                return 0
            fi
        done
    fi
    rx=$(python3 -c 'import re,sys; print("|".join(re.escape(w) for w in sys.argv[1:]))' $AI_DROP_CLAUDE_HOOKS)
    aiconf hooks-remove "$CLAUDE_DIR/settings.json" "$rx"
    for w in $AI_DROP_CLAUDE_HOOKS; do
        [ -e "$CLAUDE_DIR/hooks/$w" ] && files="$files $CLAUDE_DIR/hooks/$w"
    done
    [ -z "$files" ] || manual "hook scripts left on disk (no hook runs them now; not ours):$files. Delete them if you agree"
    return 0
}

# ---------------------------------------------------------------- step 9: skills

link_skills() {
    # link_skills <target dir> [<plugin skills dir>]: every ai/skills/<name>/SKILL.md becomes <target>/<name> (a
    # link), except a name the plugin skills dir also ships: the plugin serves it, so our earlier link goes (one
    # copy per session; owner QA 2026-11-15: prompting-claude-and-codex loaded twice in Claude).
    local dir=$1 served=${2:-} s n
    [ -d "$AI_HOME/ai/skills" ] || return 0
    for s in "$AI_HOME"/ai/skills/*/; do
        [ -f "$s/SKILL.md" ] || continue
        n=$(basename "$s")
        if [ -n "$served" ] && [ -f "$served/$n/SKILL.md" ]; then
            if [ -L "$dir/$n" ] && [ "$(readlink "$dir/$n")" = "${s%/}" ]; then
                run rm -f "$dir/$n" && ok "skill $n: the plugin copy serves it, link $dir/$n removed"
            fi
            continue
        fi
        if [ -d "$dir/$n" ] && [ ! -L "$dir/$n" ]; then
            warn "$dir/$n is a real folder (not ours): skill $n not linked"; continue
        fi
        aiconf link "$dir/$n" "${s%/}"
    done
}

claude_skills() {
    link_skills "$CLAUDE_DIR/skills" "$(PLUGIN_DIR)/skills"
    mattpocock_link "$CLAUDE_DIR/skills"
    pstack_link "$CLAUDE_DIR/skills"
    claude_skill_dups_off
    ok "Claude: shared skills and the 5 mattpocock skills linked into $CLAUDE_DIR/skills"
}

# A vendor plugin that ships a skill under one of our names (OMC: create-verification-skill,
# maintain-verification-skill) loads it twice. Ours win: skillOverrides "<plugin>:<name>" = "off" (recorded).
claude_skill_dups_off() {
    local key
    for key in $(aiconf claude-skill-dups "$CLAUDE_DIR" --offs 2>/dev/null); do
        aiconf json-set "$CLAUDE_DIR/settings.json" "skillOverrides/$key" '"off"'
    done
}

# ---------------------------------------------------------------- step 10: hooks

claude_hooks() {
    has claude || { skip "Claude hooks: claude not found"; return 0; }
    local hooks; hooks="$(PLUGIN_DIR)/hooks/hooks.json"

    # graphify is opt-in per project now (`graph` in .ai/enabled): no global graphify hooks; earlier ones go.
    aiconf hooks-remove "$CLAUDE_DIR/settings.json" 'graphify (hook-guard|hook-check)'
    claude_drop_hooks

    claude_rtk
    # graphify or RTK may have added copies of plugin hooks just now: adopt again (gated by B2).
    claude_ai_core_ok && [ -f "$hooks" ] && aiconf claude-adopt-hooks "$CLAUDE_DIR/settings.json" "$hooks"
    return 0
}

# RTK rewrite hook: dry-run first, decline the proxy, no CLAUDE.md edit (contracts-mcp-a finding 3).
claude_rtk() {
    has rtk || { warn "RTK hook: rtk not installed (or not built): Claude runs without it"; return 0; }
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

# ---------------------------------------------------------------- permissions (allow safe reads, deny config edits)

# MCP tools of a plugin server are named mcp__plugin_<plugin>_<server>__<tool> (Claude Code docs, plugins).
CLAUDE_MCP_PREFIX="mcp__plugin_ai-core_"
CLAUDE_BOX_PREFIX="mcp__plugin_ai-box_"     # the box server lives in plugin ai-box (profile server)

# Read-only or knowledge tools only. Writes, git push and installs still prompt or meet the gates.
claude_allow_rules() {
    local t
    # context7 (resolve + query): every tool.
    printf '%s\n' "${CLAUDE_MCP_PREFIX}context7__*"
    # Serena (plugin ai-serena, on by default): the read-only symbol tools of the claude-code context (its file
    # and shell tools are excluded there; memories and onboarding are off: mode no-memories). Edits still prompt.
    for t in initial_instructions get_current_config search_for_pattern get_symbols_overview find_symbol \
        find_referencing_symbols find_declaration find_implementations get_diagnostics_for_file; do
        printf 'mcp__plugin_ai-serena_serena__%s\n' "$t"
    done
    # GitHub through the gh CLI (the GitHub MCP was dropped): read-only forms only; everything else asks.
    # The bare forms run inside the sandbox; the absolute forms are what the router writes for the commands
    # that leave the sandbox (excludedCommands, root-owned program only).
    local gh; gh=$(sandbox_prog gh)
    for t in 'pr view *' 'pr list*' 'pr diff *' 'pr checks *' 'issue view *' 'issue list*' 'repo view*' \
        'run view *' 'run list*'; do
        printf 'Bash(gh %s)\n' "$t"
        [ -z "$gh" ] || printf 'Bash(%s %s)\n' "$gh" "$t"
    done
    # Shell: our own read-only tools. graphify: the read and local-build subcommands (install/hook ask).
    # rtk: the RTK hook rewrites the read-only commands Claude allows by itself (cat/head/tail, grep, rg, ls,
    # find, tree, diff, wc, git status/log/diff/show) into `rtk <cmd>` (rtk v1.2.0 src/discover/rules.rs),
    # so those forms are allowed here. rtk passes the arguments to the real tool, so the forms that run a
    # program or write a file are DENIED below (find -exec/-delete, rg --pre/--hostname-bin, tree -o,
    # git --output/--ext-diff); a deny always wins over these allows.
    printf '%s\n' 'Bash(graphify query *)' 'Bash(graphify path *)' 'Bash(graphify explain *)' \
        'Bash(graphify extract *)' 'Bash(graphify update *)' 'Bash(graphify --version)' \
        'Bash(agent-audit *)' 'Bash(ai-doctor*)' 'Bash(ai-libs)' 'Bash(ai-libs --check*)' \
        'Bash(rtk gain*)' 'Bash(rtk discover*)' 'Bash(rtk --version)' 'Bash(rtk read *)' 'Bash(rtk ls*)' \
        'Bash(rtk wc*)' 'Bash(rtk grep *)' 'Bash(rtk rg *)' 'Bash(rtk find *)' 'Bash(rtk tree*)' 'Bash(rtk diff *)' \
        'Bash(rtk git status*)' 'Bash(rtk git diff*)' 'Bash(rtk git log*)' 'Bash(rtk git show*)'
    printf '%s\n' WebFetch WebSearch 'Read(~/.claude/plugins/**)' 'Read(~/.config/ai/**)'
    # Installs run unattended (headless too): the audit-before-install gate is the decider (it denies a
    # package without an agent-audit PASS in 24 h and asks for what it cannot parse); the sandbox still holds.
    # Plain and RTK forms (RTK rewrites uv, pip, npm, pnpm, bun; Fable readiness B4).
    for t in 'uv add *' 'uv pip install *' 'uv sync*' 'pip install *' 'pip3 install *' 'python3 -m pip install *' \
        'npm install*' 'npm i *' 'npm ci*' 'pnpm add *' 'pnpm install*' 'yarn add *' 'yarn install*' 'bun add *' \
        'bun install*'; do
        printf 'Bash(%s)\nBash(rtk %s)\n' "$t" "$t"
    done
    # Box work runs unattended through the box MCP tools (server installs): proj-agent behind them refuses
    # everything outside its own menu, and exec runs inside the box, never on the host.
    if box_present; then
        printf '%s\n' "${CLAUDE_BOX_PREFIX}box__*"
    fi
    return 0
}

# graphify subcommands that write agent config or git hooks: always ask, even under Bash(graphify *).
claude_ask_rules() {
    # git push always asks, also when the sandbox would auto-allow a command (it runs outside the sandbox).
    printf '%s\n' 'Bash(git push*)' 'Bash(rtk git push*)'
    local git; git=$(sandbox_prog git)
    [ -z "$git" ] || printf 'Bash(%s push*)\n' "$git"
    printf '%s\n' 'Bash(graphify install*)' 'Bash(graphify uninstall*)' 'Bash(graphify hook*)' \
        'Bash(graphify * install*)' 'Bash(graphify * uninstall*)' 'Bash(graphify * hook*)'
}

# User-writable folders on PATH (ours: ~/.local/bin; the usual language tool folders). Claude's Write and
# Edit tools run outside the Bash sandbox, so a program planted there would shadow a system one by name.
CLAUDE_PATH_DIRS="~/.local/bin/** ~/bin/** ~/.npm-global/bin/** ~/.cargo/bin/** ~/go/bin/** ~/.bun/bin/** ~/.deno/bin/** ~/.local/share/pnpm/** ~/.volta/bin/** ~/.yarn/bin/**"

# Agents never edit the files that carry the house rules and their own permissions.
claude_deny_rules() {
    local f
    set -f   # $CLAUDE_PATH_DIRS below is split on spaces, never globbed
    # Files that carry house rules, permissions, hooks, plugin code, shell start-up, Serena config and the
    # global Serena memories. Edit(path) rules cover every built-in file-writing tool (Write and NotebookEdit
    # too); Claude ignores Write(path) rules and warns about them, so none are listed (an earlier install's
    # Write rules are dropped by the list sync). Project .claude/settings*.json are written by ai-adopt.
    for f in '~/.claude/settings.json' '~/.claude/settings.local.json' '~/.claude.json' '~/.claude/CLAUDE.md' \
        '~/.claude/plugins/**' '//etc/claude-code/**' '//etc/codex/**' '~/.codex/config.toml' '~/.codex/hooks.json' \
        '~/.codex/AGENTS.md' '~/.hermes/config.yaml' '~/.hermes/SOUL.md' '~/.config/ai/**' \
        '~/.serena/serena_config.yml' '~/.serena/memories/global/**' '~/.bashrc' '~/.zshenv' '~/.profile' \
        '**/.claude/settings.json' '**/.claude/settings.local.json' \
        '~/.zshrc' '~/.zprofile' '~/.bash_profile' '~/.bash_login' '~/.bash_aliases' '~/.config/environment.d/**' \
        '~/.config/rtk/**' '~/Library/Application Support/rtk/**' '~/.gitconfig' '~/.config/git/**' \
        $CLAUDE_PATH_DIRS; do
        printf 'Edit(%s)\n' "$f"
    done
    set +f
    printf '%s\n' 'Read(~/.config/ai/secrets.env)'
    # The exec and write forms of the commands RTK rewrites (checked against rtk v1.2.0: find, tree, grep/rg
    # and git pass their arguments to the real program): a deny wins over the rtk allows above.
    local x
    for x in -exec -execdir -ok -okdir -delete -fprint -fprint0 -fprintf -fls; do
        printf 'Bash(rtk find *%s*)\nBash(find *%s*)\n' "$x" "$x"
    done
    printf '%s\n' 'Bash(rtk grep *--pre*)' 'Bash(rtk rg *--pre*)' 'Bash(rtk grep *--hostname-bin*)' \
        'Bash(rtk rg *--hostname-bin*)' 'Bash(*RIPGREP_CONFIG_PATH*)' 'Bash(rtk tree* -o*)' \
        'Bash(git * --output*)' 'Bash(rtk git * --output*)' 'Bash(git * --ext-diff*)' 'Bash(rtk git * --ext-diff*)'
    # sudo: not a deny list here (sudo python3 -c, sudo env bash... would pass). The router gate no-sudo
    # blocks every sudo (box work: the box MCP tools); containment stays in sudoers.
    return 0
}

# Merge (never replace) into permissions.allow / ask / deny. Each item is recorded for uninstall.
claude_permissions() {
    has claude || { skip "Claude permissions: claude not found"; return 0; }
    local f="$CLAUDE_DIR/settings.json" kind tmp
    # Sync, not just add: a rule an earlier install added and the current lists no longer hold (GitHub MCP
    # tools, old rtk/graphify forms) is removed; rules the user added by hand are never touched.
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-perm.XXXXXX")
    for kind in allow ask deny; do
        "claude_${kind}_rules" | while IFS= read -r r; do [ -n "$r" ] && json_str "$r"; done > "$tmp"
        aiconf json-list-sync "$f" "permissions/$kind" "$tmp" >/dev/null
    done
    rm -f "$tmp"
    ok "Claude permissions merged into $f: allow read-only tools, ask graphify install/hook, deny rule/config edits and secrets.env"
}

json_str() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

# ---------------------------------------------------------------- managed policy (Linux, root): sandbox and
# planted-config defence. Facts: code.claude.com/docs/en/sandboxing, settings-reference, managed-mcp.

# Files no sandboxed command may read, and secrets removed from its environment.
SANDBOX_DENY_READ="~/.ssh ~/.config/gh ~/.claude/.credentials.json ~/.codex/auth.json ~/.config/ai/secrets.env ~/.hermes/.env"
SANDBOX_DENY_ENV="GITHUB_PERSONAL_ACCESS_TOKEN GITHUB_TOKEN GH_TOKEN CONTEXT7_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY OPENROUTER_API_KEY"
# Writes besides the working directory and the sandbox temp dir: /tmp and the caches the tools really use.
# uv: its own cache folder for sandboxed commands (UV_CACHE_DIR in the Claude env, claude_env_sandbox). The
# default ~/.cache/uv is what installs use: if the sandbox could write it, a file hard-linked from it into an
# installed tool (graphify, serena) could be changed in place and then run outside the sandbox.
SANDBOX_ALLOW_WRITE="/tmp ~/.cache/ai-sandbox ~/.cache/pre-commit ~/.cache/pip ~/.npm ~/.cache/node-gyp ~/.cargo/registry ~/go/pkg/mod ~/.cache/go-build ~/.cache/graphify ~/.local/state/ai"
# Never writable by a sandboxed command, also when the session runs in a folder above them (cwd ~ is refused
# by the router too): PATH folders (a planted program there shadows a system one for unsandboxed hooks and
# excluded commands), uv's installed tools, shell start-up files, git's user config, every agent's config.
# Claude adds its own built-in protections on top (.git/hooks, .git/config, rc files in the project; seen in
# the 2.1.322 binary), so they are not repeated as globs here (denyWrite globs are not expanded on Linux).
# Nothing under ~/.config is needed by sandboxed dev work (tool caches live in ~/.cache).
SANDBOX_DENY_WRITE="~/.local/bin ~/bin ~/.npm-global/bin ~/.cargo/bin ~/go/bin ~/.bun/bin ~/.deno/bin ~/.local/share/uv/tools ~/.local/share/pnpm ~/.volta/bin ~/.yarn/bin ~/.bashrc ~/.profile ~/.bash_profile ~/.bash_login ~/.bash_aliases ~/.zshenv ~/.zshrc ~/.zprofile ~/.gitconfig ~/.config ~/.codex ~/.claude ~/.claude.json ~/.hermes ~/.serena ~/.ssh ~/.local/share/ai"
# Hosts sandboxed commands reach without a prompt (git over HTTPS, npm, PyPI/uv, crates, Go, context7).
# Other hosts prompt in an interactive session and are refused in a headless one (no strict allowlist:
# a fixed list would break new package hosts; see docs).
SANDBOX_DOMAINS="github.com *.github.com *.githubusercontent.com codeload.github.com registry.npmjs.org *.npmjs.org nodejs.org pypi.org files.pythonhosted.org *.pythonhosted.org astral.sh crates.io *.crates.io proxy.golang.org sum.golang.org context7.com *.context7.com"
# Run outside the sandbox (they need the gh token or the git credential helper): still need permission.
# Written with the ABSOLUTE path of a root-owned program (sandbox_prog): a bare name would be found on PATH,
# and ~/.local/bin (first on PATH) is writable by Claude's Write tool, so a planted `git` or `gh` there
# would run outside the sandbox with the user's full rights. The router writes the absolute path for a
# plain single call; anything else (a bare name in a chain, a planted copy) stays sandboxed.
SANDBOX_EXCLUDED_GIT="push *"
SANDBOX_EXCLUDED_GH="pr view *|pr list *|pr diff *|pr checks *|pr create *|pr edit *|issue view *|issue list *|repo view *|run view *|run list *"

# sandbox_prog NAME: absolute path of NAME in /usr/local/bin, /usr/bin or /bin when the file and every folder
# up to / are root-owned and not writable by group or others (symlinks followed and checked too); else empty.
sandbox_prog() {
    python3 - "$1" "${AI_SANDBOX_PROG_DIRS:-/usr/local/bin /usr/bin /bin}" "${AI_SANDBOX_PROG_INSECURE_TEST:-0}" <<'EOS'
import os, stat, sys
name, dirs, insecure = sys.argv[1], sys.argv[2].split(), sys.argv[3] == "1"
def safe(p):
    try:
        st = os.stat(p)
    except OSError:
        return False
    return (insecure or st.st_uid == 0) and not st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
def chain(p):
    p = os.path.abspath(p)
    if insecure:          # tests only: the file itself, no owner or parent check (test folders sit in /tmp)
        return safe(p)
    while True:
        if not safe(p):
            return False
        if p == "/":
            return True
        p = os.path.dirname(p)
for d in dirs:
    p = os.path.join(d, name)
    if os.path.isfile(p) and os.access(p, os.X_OK) and chain(p) and chain(os.path.realpath(p)):
        print(p)
        break
EOS
}

sandbox_excluded() {
    local git gh t
    git=$(sandbox_prog git); gh=$(sandbox_prog gh)
    local IFS='|'
    if [ -n "$git" ]; then for t in $SANDBOX_EXCLUDED_GIT; do printf '%s %s|' "$git" "$t"; done; fi
    if [ -n "$gh" ]; then for t in $SANDBOX_EXCLUDED_GH; do printf '%s %s|' "$gh" "$t"; done; fi
}

claude_sandbox_json() {
    python3 - "$SANDBOX_DENY_READ" "$SANDBOX_DENY_ENV" "$SANDBOX_ALLOW_WRITE" "$SANDBOX_DOMAINS" "$(sandbox_excluded)" \
        "$SANDBOX_DENY_WRITE" <<'EOS'
import json, sys
deny_read, deny_env, allow_write, domains, excluded, deny_write = sys.argv[1:7]
print(json.dumps({
    "enabled": True,
    "failIfUnavailable": True,
    "allowUnsandboxedCommands": False,
    "excludedCommands": [e for e in excluded.split("|") if e],
    "filesystem": {"denyRead": deny_read.split(), "allowWrite": allow_write.split(), "denyWrite": deny_write.split()},
    "credentials": {"files": [{"path": p, "mode": "deny"} for p in deny_read.split()],
                    "envVars": [{"name": n, "mode": "deny"} for n in deny_env.split()]},
    "network": {"allowedDomains": domains.split(), "allowAllUnixSockets": False, "allowLocalBinding": False},
    "enableWeakerNestedSandbox": False,
    "enableWeakerNetworkIsolation": False,
}, sort_keys=True))
EOS
}

# The box tool: unix sockets stay blocked in the sandbox (allowAllUnixSockets false: on Linux there is no
# per-socket list, and a host has sockets that are a full escape: Postgres, tmux, the user's systemd). Box
# work goes through the box MCP server in ai-core (mcp/box.py), which runs outside the sandbox and talks to
# the root socket service of the ubuntu-server branch (box_present in base.sh).

# Add bwrapPath when the AppArmor-profiled copy exists (Ubuntu with the userns restriction): managed-only key.
claude_sandbox_json_final() {
    local j; j=$(claude_sandbox_json)
    if [ -e "${AI_BWRAP:-/usr/local/lib/ai/bwrap}" ] || [ "${AI_SANDBOX_BWRAP_FORCE:-0}" = 1 ]; then
        python3 -c 'import json,sys; d=json.loads(sys.argv[1]); d["bwrapPath"]=sys.argv[2]; print(json.dumps(d, sort_keys=True))' \
            "$j" "${AI_BWRAP:-/usr/local/lib/ai/bwrap}"
    else
        printf '%s\n' "$j"
    fi
}

# The sandbox's own uv cache (allowWrite has ~/.cache/ai-sandbox, not ~/.cache/uv): Claude's env, this user.
claude_env_sandbox() {
    has claude || return 0
    aiconf json-set "$CLAUDE_DIR/settings.json" env/UV_CACHE_DIR "\"$HOME/.cache/ai-sandbox/uv\""
}

# The managed "hooks" value: every router.py hook of ai-core's hooks.json, pointed at the root-owned copy
# ($AI_ROOT_REPO, root guard) with --managed, plus RTK's PreToolUse hook when rtk is root-owned.
claude_managed_hooks() {
    python3 - "$(PLUGIN_DIR)/hooks/hooks.json" "${AI_ROOT_REPO}/ai/marketplace/plugins/ai-core" "${1:-}" <<'EOS'
import json, sys
src, root, rtk = sys.argv[1:4]
data = json.load(open(src))["hooks"]
out = {}
for event, groups in data.items():
    for g in groups:
        hooks = [dict(h, command=h["command"].replace("${CLAUDE_PLUGIN_ROOT}", root) + " --managed")
                 for h in g.get("hooks", []) if "/hooks/router.py" in h.get("command", "")]
        if event == "PreToolUse":
            # Gates fail closed: a crash, bad output or timeout of the router blocks the call (Claude 2.1.295+;
            # hooks fail open by default). Managed only: the server's Claude version is known.
            hooks = [dict(h, onFailure="block") for h in hooks]
        if hooks:
            out.setdefault(event, []).append(dict(g, hooks=hooks))
if rtk:
    out.setdefault("PreToolUse", []).append({"matcher": "Bash", "hooks": [{"type": "command", "command": rtk + " hook claude"}]})
print(json.dumps(out, sort_keys=True))
EOS
}

# managed-settings.json keys (merge; only these keys): the Bash sandbox, the planted-config lock, the RTK
# hook as a managed hook, and a git setting that a planted .git/config cannot turn into code execution.
claude_managed_policy() {
    [ "$AI_OS" = linux ] || return 0
    local ms=/etc/claude-code/managed-settings.json rtk_bin
    aiconf_root json-set "$ms" sandbox "$(claude_sandbox_json_final)" --mode 644
    # Planted project config: project/user/local settings hooks and project .mcp.json / ~/.claude.json MCP
    # servers stop loading; plugin hooks, plugin MCP servers (ai-core, OMC, Ponytail, i-have-adhd, opt-in
    # ai-serena / claude-seo / claude-blog) and managed hooks keep working.
    aiconf_root json-set "$ms" strictPluginOnlyCustomization '["hooks","mcp"]' --mode 644
    # Several managed sources (claude.ai server-managed, MDM, this file): the default "first-wins" silently
    # ignores this file when a higher source sends any key. "merge" unions lists and keeps the strictest locks.
    aiconf_root json-set "$ms" managedSourcesBehavior '"merge"' --mode 644
    # ai-core (router, gates) force-enabled from managed settings: no user or agent can switch it off.
    # OMC, Ponytail and i-have-adhd stay as the owner set them (owner decision 2026-11-12).
    aiconf_root json-set "$ms" "enabledPlugins/ai-core@ai" true --mode 644
    # Managed hooks: the ai-core router (gates) from the root-owned copy, and RTK's hook (it lived in
    # ~/.claude/settings.json, which the lock above stops). The plugin copy of the router in
    # ~/.claude/plugins/cache is user-writable: with these in place it steps aside (router.py plugin_copy).
    rtk_bin=$(command -v rtk 2>/dev/null || true)
    case "$rtk_bin" in
        /usr/local/bin/rtk|/usr/bin/rtk) ;;
        *) warn "rtk not in /usr/local/bin: its Claude hook is not managed (it stops under the hooks lock)"; rtk_bin="" ;;
    esac
    aiconf_root json-set "$ms" hooks "$(claude_managed_hooks "$rtk_bin")" --mode 644
    # The server's git guard (ubuntu-server branch, /usr/local/bin/git) hardens EVERY repo for agents when it
    # sees GIT_GUARD_AGENT=1: hooks off, config allow-list. Every process Claude starts gets it (Bash, the
    # commands outside the sandbox such as git push, hooks, MCP servers).
    aiconf_root json-set "$ms" env/GIT_GUARD_AGENT '"1"' --mode 644
    # core.fsmonitor from a planted .git/config would run a program on every git status.
    aiconf_root json-set "$ms" env/GIT_CONFIG_COUNT '"1"' --mode 644
    aiconf_root json-set "$ms" env/GIT_CONFIG_KEY_0 '"core.fsmonitor"' --mode 644
    aiconf_root json-set "$ms" env/GIT_CONFIG_VALUE_0 '"false"' --mode 644
    ok "Claude managed policy: Bash sandbox (deny secrets, limited writes, proxy domains), hooks+mcp only from plugins/managed, RTK managed hook, git fsmonitor off"
}

# ---------------------------------------------------------------- OMC wiring (owner decision pending)

# Owner decision 2026-11-12: OMC is a Claude plugin, as on the Mac (oh-my-claudecode@omc at the newest stable
# tag since 2026-11-14, OMC_PLUGIN_SOURCE in pins.env), exa MCP off (claude_env). AI_OMC_WIRING=cli keeps the old npm-CLI
# route (`omc setup --no-plugin`), keep leaves the installed OMC alone (owner 2026-11-15), remove uninstalls the npm CLI. Set it in the environment of install.sh.
AI_OMC_WIRING=${AI_OMC_WIRING:-plugin}

claude_omc_wiring() {
    case "$AI_OMC_WIRING" in
        cli) return 0 ;;
        keep) info "OMC: installed copy kept as it is, no update and no scan (AI_OMC_WIRING=keep)" ;;
        plugin)
            claude_git_plugin omc-plugin omc Yeachan-Heo/oh-my-claudecode oh-my-claudecode@omc || true
            if [ "$AI_OS" = linux ]; then
                # Owner decision 2026-11-12 (servers only; the Mac keeps it on): installed, OFF at user scope
                # (6.7k tokens per session, .omc/ in every repo). A project turns it on: ai-adopt --tools omc.
                aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/oh-my-claudecode@omc" false
                ok "Claude: oh-my-claudecode off by default here (per project: ai-adopt --tools omc)"
            else
                manual "OMC plugin route: run /oh-my-claudecode:omc-setup once in Claude (CLAUDE.md block, HUD)"
            fi
            ;;
        remove)
            if has omc; then manual "AI_OMC_WIRING=remove: admin runs: sudo npm uninstall -g oh-my-claude-sisyphus"; fi
            ;;
        *) warn "AI_OMC_WIRING=$AI_OMC_WIRING is not cli, plugin, keep or remove: nothing changed" ;;
    esac
    return 0
}

# ---------------------------------------------------------------- step 12: env

claude_env() {
    # OMC user config is ${XDG_CONFIG_HOME:-~/.config}/claude-omc/config.jsonc (OMC getConfigPaths).
    # No self-update (SPEC 19), and the exa MCP off: it sends search queries to an outside service.
    # JSONC file: a file with comments is refused and reported as a manual step.
    local omc_cfg="${XDG_CONFIG_HOME:-$HOME/.config}/claude-omc/config.jsonc"
    if [ "$AI_OMC_WIRING" = plugin ] || [ -d "$(dirname "$omc_cfg")" ] || has omc; then
        aiconf json-set "$omc_cfg" security/disableAutoUpdate true --jsonc \
            || manual "set \"security\": {\"disableAutoUpdate\": true} in $omc_cfg by hand (file has comments)"
        aiconf json-set "$omc_cfg" mcpServers/exa/enabled false --jsonc \
            || manual "set \"mcpServers\": {\"exa\": {\"enabled\": false}} in $omc_cfg by hand (file has comments)"
    fi
    # Ponytail mode (A.3); never PONYTAIL_DEFAULT_MODE (it overrides the file).
    aiconf json-set "$HOME/.config/ponytail/config.json" defaultMode '"full"'
    ok "Claude add-ons: OMC auto-update off, Ponytail defaultMode full"
}
