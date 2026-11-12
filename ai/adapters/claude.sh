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
        run claude plugin marketplace add "$msrc" || { warn "claude plugin marketplace add $msrc failed"; return 1; }
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
    run claude plugin install "$plugin" --scope user || { warn "claude plugin install $plugin failed"; return 1; }
    aiconf record-cmd "claude-plugin:$plugin" -- claude plugin uninstall "$plugin"
    ok "Claude plugin $plugin (user scope)"
}

# B2: ai-core must be installed AND enabled before we remove anything it replaces.
claude_ai_core_ok() {
    [ "$AI_DRY_RUN" = 1 ] && return 0   # plan only: the moves below print, they do not run
    local listing
    listing=$(claude plugin list 2>/dev/null || true)
    printf '%s\n' "$listing" | grep -qF 'ai-core@ai' || return 1
    printf '%s\n' "$listing" | grep -F 'ai-core@ai' | grep -qi 'disabled' && return 1
    [ "$(aiconf json-get "$CLAUDE_DIR/settings.json" 'enabledPlugins/ai-core@ai' 2>/dev/null)" = true ]
}

# ---------------------------------------------------------------- step 7: MCP

claude_mcp() {
    has claude || { skip "Claude MCP: claude not found"; return 0; }
    # The ai-core plugin serves Serena, context7, GitHub, Grounded Docs. Any user-scope copy (the
    # hand-made config registered Serena there) is moved in step 8, after ai-core is verified.
    info "Claude MCP: served by the ai-core plugin (user-scope duplicates are moved after the plugin check)"
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

    # Ponytail and i-have-adhd from the audited local copies (no auto-update for local paths).
    if claude_has_plugin ponytail@ponytail; then info "ponytail@ponytail installed: kept as is"
    elif [ -d "$(plugin_src_dir ponytail)" ] || [ "$AI_DRY_RUN" = 1 ]; then
        claude_plugin ponytail "$(plugin_src_dir ponytail)" ponytail@ponytail || true
    else skip "Ponytail: audited source missing"; fi

    if claude_has_plugin i-have-adhd@i-have-adhd; then info "i-have-adhd installed: kept as is"
    elif [ -d "$(plugin_src_dir i-have-adhd)" ] || [ "$AI_DRY_RUN" = 1 ]; then
        claude_plugin i-have-adhd "$(plugin_src_dir i-have-adhd)" i-have-adhd@i-have-adhd || true
    else skip "i-have-adhd: audited source missing"; fi
    # Always-on flag (empty file; the hook tests existence). Codex reads the same path.
    local empty; empty=$(mktemp "${TMPDIR:-/tmp}/ai-empty.XXXXXX")
    aiconf file-put "$CLAUDE_DIR/.i-have-adhd-always" "$empty" --mode 644
    rm -f "$empty"

    # claude-seo, claude-blog: tag pin in the add command, sha checked after the clone.
    claude_plugin agricidaniel-claude-seo "AgriciDaniel/claude-seo#$CLAUDE_SEO_REF" claude-seo@agricidaniel-claude-seo "$CLAUDE_SEO_SHA" || true
    claude_plugin agricidaniel-blog "AgriciDaniel/claude-blog#$CLAUDE_BLOG_REF" claude-blog@agricidaniel-blog "$CLAUDE_BLOG_SHA" || true
    # Owner decision 2026-11-12: opt-in per project (about 12k tokens per session each). Installed, but OFF
    # at user scope; a project turns one on with ai-adopt --tools seo|blog, which writes enabledPlugins true in
    # its .claude/settings.json (project and local settings win over user settings).
    local pk
    for pk in claude-seo@agricidaniel-claude-seo claude-blog@agricidaniel-blog; do
        aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/$pk" false
    done
    ok "Claude: claude-seo and claude-blog off by default (per project: ai-adopt --tools seo,blog)"
    claude_omc_wiring
    # Serena: opt-in per project (owner decision 2026-11-12). Installed, OFF at user scope; a project turns it
    # on with ai-adopt --tools serena (project enabledPlugins ai-serena@ai = true).
    # Playwright the same way (project .mcp.json no longer loads under the managed mcp lock).
    local op
    for op in ai-serena@ai ai-playwright@ai; do
        claude_plugin ai "$AI_HOME/ai/marketplace" "$op" || true
        aiconf json-set "$CLAUDE_DIR/settings.json" "enabledPlugins/$op" false
    done
    manual "Claude, once per machine, in a project with claude-seo on: /seo setup, then /seo doctor (venv + Chromium)"

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
    mattpocock_link "$CLAUDE_DIR/skills"
    ok "Claude: shared skills and the 5 mattpocock skills linked into $CLAUDE_DIR/skills"
}

# ---------------------------------------------------------------- step 10: hooks

claude_hooks() {
    has claude || { skip "Claude hooks: claude not found"; return 0; }
    local hooks; hooks="$(PLUGIN_DIR)/hooks/hooks.json"

    # graphify is opt-in per project now (`graph` in .ai/enabled): no global graphify hooks; earlier ones go.
    aiconf hooks-remove "$CLAUDE_DIR/settings.json" 'graphify (hook-guard|hook-check)'

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

# Read-only or knowledge tools only. Writes, git push and installs still prompt or meet the gates.
claude_allow_rules() {
    local t
    # context7 (resolve + query): every tool.
    printf '%s\n' "${CLAUDE_MCP_PREFIX}context7__*"
    # Serena (opt-in plugin ai-serena): reads, symbol lookups, project memory. Symbol edits are NOT here.
    for t in initial_instructions get_current_config onboarding check_onboarding_performed list_dir find_file \
        read_file search_for_pattern get_symbols_overview find_symbol find_referencing_symbols find_declaration \
        find_implementations get_diagnostics_for_file list_memories read_memory write_memory edit_memory \
        rename_memory; do
        printf 'mcp__plugin_ai-serena_serena__%s\n' "$t"
    done
    # GitHub through the gh CLI (the GitHub MCP was dropped): read-only forms only; everything else asks.
    printf '%s\n' 'Bash(gh pr view *)' 'Bash(gh pr list*)' 'Bash(gh pr diff *)' 'Bash(gh pr checks *)' \
        'Bash(gh issue view *)' 'Bash(gh issue list*)' 'Bash(gh repo view*)' 'Bash(gh run view *)' 'Bash(gh run list*)'
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
    # Box work runs unattended: proj-agent refuses everything outside its own menu (Linux servers only).
    if proj_agent_present; then printf '%s\n' 'Bash(sudo proj-agent *)' 'Bash(sudo -n proj-agent *)'; fi
    return 0
}

# graphify subcommands that write agent config or git hooks: always ask, even under Bash(graphify *).
claude_ask_rules() {
    # git push always asks, also when the sandbox would auto-allow a command (it runs outside the sandbox).
    printf '%s\n' 'Bash(git push*)' 'Bash(rtk git push*)'
    printf '%s\n' 'Bash(graphify install*)' 'Bash(graphify uninstall*)' 'Bash(graphify hook*)' \
        'Bash(graphify * install*)' 'Bash(graphify * uninstall*)' 'Bash(graphify * hook*)'
}

# Agents never edit the files that carry the house rules and their own permissions.
claude_deny_rules() {
    local f
    # Files that carry house rules, permissions, hooks, plugin code, shell start-up, Serena config and the
    # global Serena memories. Edit covers every built-in editing tool (NotebookEdit too); Write is listed as
    # well. Project .claude/settings*.json are written by ai-adopt (a script), never by an agent.
    for f in '~/.claude/settings.json' '~/.claude/settings.local.json' '~/.claude.json' '~/.claude/CLAUDE.md' \
        '~/.claude/plugins/**' '//etc/claude-code/**' '//etc/codex/**' '~/.codex/config.toml' '~/.codex/hooks.json' \
        '~/.codex/AGENTS.md' '~/.hermes/config.yaml' '~/.hermes/SOUL.md' '~/.config/ai/**' \
        '~/.serena/serena_config.yml' '~/.serena/memories/global/**' '~/.bashrc' '~/.zshenv' '~/.profile' \
        '**/.claude/settings.json' '**/.claude/settings.local.json'; do
        printf 'Edit(%s)\nWrite(%s)\n' "$f" "$f"
    done
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
    # blocks every sudo except `sudo proj-agent ...` on Linux; containment stays in sudoers.
    return 0
}

# Merge (never replace) into permissions.allow / ask / deny. Each item is recorded for uninstall.
claude_permissions() {
    has claude || { skip "Claude permissions: claude not found"; return 0; }
    local f="$CLAUDE_DIR/settings.json" kind r
    for kind in allow ask deny; do
        while IFS= read -r r; do
            [ -n "$r" ] || continue
            aiconf json-add "$f" "permissions/$kind" "$(json_str "$r")" >/dev/null
        done <<EOF
$("claude_${kind}_rules")
EOF
    done
    ok "Claude permissions merged into $f: allow read-only tools, ask graphify install/hook, deny rule/config edits and secrets.env"
}

json_str() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

# ---------------------------------------------------------------- managed policy (Linux, root): sandbox and
# planted-config defence. Facts: code.claude.com/docs/en/sandboxing, settings-reference, managed-mcp.

# Files no sandboxed command may read, and secrets removed from its environment.
SANDBOX_DENY_READ="~/.ssh ~/.config/gh ~/.claude/.credentials.json ~/.codex/auth.json ~/.config/ai/secrets.env ~/.hermes/.env"
SANDBOX_DENY_ENV="GITHUB_PERSONAL_ACCESS_TOKEN GITHUB_TOKEN GH_TOKEN CONTEXT7_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY OPENROUTER_API_KEY"
# Writes besides the working directory and the sandbox temp dir: /tmp and the caches the tools really use.
SANDBOX_ALLOW_WRITE="/tmp ~/.cache/uv ~/.cache/pip ~/.npm ~/.cache/node-gyp ~/.cargo/registry ~/go/pkg/mod ~/.cache/go-build ~/.cache/graphify ~/.local/state/ai"
# Hosts sandboxed commands reach without a prompt (git over HTTPS, npm, PyPI/uv, crates, Go, context7).
# Other hosts prompt in an interactive session and are refused in a headless one (no strict allowlist:
# a fixed list would break new package hosts; see docs).
SANDBOX_DOMAINS="github.com *.github.com *.githubusercontent.com codeload.github.com registry.npmjs.org *.npmjs.org nodejs.org pypi.org files.pythonhosted.org *.pythonhosted.org astral.sh crates.io *.crates.io proxy.golang.org sum.golang.org context7.com *.context7.com"
# Run outside the sandbox (they need the gh token or the git credential helper): still need permission.
SANDBOX_EXCLUDED="git push *|gh pr view *|gh pr list *|gh pr diff *|gh pr checks *|gh pr create *|gh pr edit *|gh issue view *|gh issue list *|gh repo view *|gh run view *|gh run list *"

claude_sandbox_json() {
    python3 - "$SANDBOX_DENY_READ" "$SANDBOX_DENY_ENV" "$SANDBOX_ALLOW_WRITE" "$SANDBOX_DOMAINS" "$SANDBOX_EXCLUDED" <<'EOS'
import json, sys
deny_read, deny_env, allow_write, domains, excluded = sys.argv[1:6]
print(json.dumps({
    "enabled": True,
    "failIfUnavailable": True,
    "allowUnsandboxedCommands": False,
    "excludedCommands": excluded.split("|"),
    "filesystem": {"denyRead": deny_read.split(), "allowWrite": allow_write.split()},
    "credentials": {"files": [{"path": p, "mode": "deny"} for p in deny_read.split()],
                    "envVars": [{"name": n, "mode": "deny"} for n in deny_env.split()]},
    "network": {"allowedDomains": domains.split(), "allowAllUnixSockets": False, "allowLocalBinding": False},
    "enableWeakerNestedSandbox": False,
    "enableWeakerNetworkIsolation": False,
}, sort_keys=True))
EOS
}

# The box tool: sudo cannot run inside the sandbox ("no new privileges"), so `sudo proj-agent ...` runs outside
# it. proj-agent is itself the allow-list (new try/mvp, list, status, snapshot, doctor, logs, restart, exec,
# ports, url; it refuses the rest). Excluded-command entries use Bash-rule syntax and every command of a call
# must match, so only these exact forms leave the sandbox; the no-sudo gate blocks every other sudo.
PROJ_AGENT=/usr/local/sbin/proj-agent
proj_agent_present() { [ "$AI_OS" = linux ] && { [ -x "$PROJ_AGENT" ] || [ "${AI_PROJ_AGENT_FORCE:-0}" = 1 ]; }; }

# Add bwrapPath when the AppArmor-profiled copy exists (Ubuntu with the userns restriction): managed-only key.
claude_sandbox_json_final() {
    local j; j=$(claude_sandbox_json)
    if proj_agent_present; then
        j=$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); d["excludedCommands"] += ["sudo proj-agent *", "sudo -n proj-agent *"]; print(json.dumps(d, sort_keys=True))' "$j")
    fi
    if [ -e "${AI_BWRAP:-/usr/local/lib/ai/bwrap}" ] || [ "${AI_SANDBOX_BWRAP_FORCE:-0}" = 1 ]; then
        python3 -c 'import json,sys; d=json.loads(sys.argv[1]); d["bwrapPath"]=sys.argv[2]; print(json.dumps(d, sort_keys=True))' \
            "$j" "${AI_BWRAP:-/usr/local/lib/ai/bwrap}"
    else
        printf '%s\n' "$j"
    fi
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
    # ai-core (router, gates) force-enabled from managed settings: no user or agent can switch it off.
    # OMC, Ponytail and i-have-adhd stay as the owner set them (owner decision 2026-11-12).
    aiconf_root json-set "$ms" "enabledPlugins/ai-core@ai" true --mode 644
    # RTK's hook lived in ~/.claude/settings.json, which the lock above stops: it moves here, absolute path.
    rtk_bin=$(command -v rtk 2>/dev/null || true)
    case "$rtk_bin" in
        /usr/local/bin/rtk|/usr/bin/rtk)
            aiconf_root json-set "$ms" hooks/PreToolUse \
                "[{\"matcher\": \"Bash\", \"hooks\": [{\"type\": \"command\", \"command\": \"$rtk_bin hook claude\"}]}]" --mode 644 ;;
        *) warn "rtk not in /usr/local/bin: its Claude hook is not managed (it stops under the hooks lock)" ;;
    esac
    # core.fsmonitor from a planted .git/config would run a program on every git status.
    aiconf_root json-set "$ms" env/GIT_CONFIG_COUNT '"1"' --mode 644
    aiconf_root json-set "$ms" env/GIT_CONFIG_KEY_0 '"core.fsmonitor"' --mode 644
    aiconf_root json-set "$ms" env/GIT_CONFIG_VALUE_0 '"false"' --mode 644
    ok "Claude managed policy: Bash sandbox (deny secrets, limited writes, proxy domains), hooks+mcp only from plugins/managed, RTK managed hook, git fsmonitor off"
}

# ---------------------------------------------------------------- OMC wiring (owner decision pending)

# Owner decision 2026-11-12: OMC is a pinned Claude plugin, as on the Mac (oh-my-claudecode@omc at the
# audited tag, OMC_PLUGIN_* in pins.env), exa MCP off (claude_env). AI_OMC_WIRING=cli keeps the old npm-CLI
# route (`omc setup --no-plugin`), remove uninstalls the npm CLI. Set it in the environment of install.sh.
AI_OMC_WIRING=${AI_OMC_WIRING:-plugin}

claude_omc_wiring() {
    case "$AI_OMC_WIRING" in
        cli) return 0 ;;
        plugin)
            claude_plugin omc "Yeachan-Heo/oh-my-claudecode#$OMC_PLUGIN_REF" oh-my-claudecode@omc "$OMC_PLUGIN_SHA" || true
            manual "OMC plugin route: run /oh-my-claudecode:omc-setup once in Claude (CLAUDE.md block, HUD)"
            ;;
        remove)
            if has omc; then manual "AI_OMC_WIRING=remove: admin runs: sudo npm uninstall -g oh-my-claude-sisyphus"; fi
            ;;
        *) warn "AI_OMC_WIRING=$AI_OMC_WIRING is not cli, plugin or remove: nothing changed" ;;
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
