# ai/adapters/tools.sh: pinned installs of harnesses and tools (audit first, exact versions).
# Sourced by install.sh. bash 3.2. Each function is skippable when the pinned version is present.

AI_BUILD_DIR="$HOME/.cache/ai/build"

# ---------------------------------------------------------------- helpers

# npm global install of an exact version, integrity checked against the pin, scripts off.
npm_pinned() {
    # npm_pinned <pkg> <version> [integrity]
    local pkg=$1 ver=$2 want=${3:-} got prefix
    if [ -n "$want" ] && [ "$AI_DRY_RUN" != 1 ]; then
        got=$(npm view "$pkg@$ver" dist.integrity 2>/dev/null || true)
        if [ "$got" != "$want" ]; then
            warn "$pkg@$ver integrity mismatch (registry: ${got:-none}): not installed"
            return 1
        fi
    fi
    audit_ok npm "$pkg" "$ver" || return 1
    prefix=$(npm prefix -g 2>/dev/null || echo /usr)
    if [ -w "$prefix/lib" ] || [ -w "$prefix" ]; then
        run npm install -g --ignore-scripts "$pkg@$ver"
    else
        run_root npm install -g --ignore-scripts "$pkg@$ver"
    fi
}

# npm install of an exact version into a private prefix (no global install, no runtime npx):
# integrity checked against the pin, audited, scripts off. Prints nothing on success.
npm_local() {
    # npm_local <pkg> <version> <integrity> <prefix dir> [as-user]
    local pkg=$1 ver=$2 want=$3 dir=$4 user=${5:-} got
    if [ "$AI_DRY_RUN" != 1 ]; then
        got=$(npm view "$pkg@$ver" dist.integrity 2>/dev/null || true)
        if [ -z "$want" ] || [ "$got" != "$want" ]; then
            warn "$pkg@$ver integrity mismatch or not pinned (registry: ${got:-none}): not installed"
            return 1
        fi
    fi
    audit_ok npm "$pkg" "$ver" || return 1
    local cmd="npm install --prefix $(quote "$dir") --ignore-scripts --no-audit --no-fund --save-exact $(quote "$pkg@$ver")"
    if [ -n "$user" ]; then as_hermes "$cmd"; else run sh -c "$cmd"; fi
}

# uv tool install of an exact version, as the user (never root), wheels only (--no-build). Files are copied
# (UV_LINK_MODE=copy), never hard-linked to the uv cache; a tool an older install linked is reinstalled.
uv_pinned() {
    # uv_pinned <pypi-name> <version> [python]
    local name=$1 ver=$2 py=${3:-} re=()
    audit_ok pypi "$name" "$ver" || return 1
    uv_tool_linked "$name" && re=(--reinstall)
    if [ -n "$py" ]; then run env UV_LINK_MODE=copy uv tool install --force --no-build ${re[@]+"${re[@]}"} -p "$py" "$name==$ver"
    else run env UV_LINK_MODE=copy uv tool install --force --no-build ${re[@]+"${re[@]}"} "$name==$ver"; fi
}

# uv_tool_linked <name>: true when a file of that installed uv tool has more than one hard link.
uv_tool_linked() {
    local d; d="$(uv tool dir 2>/dev/null)/$1"
    [ -d "$d" ] || return 1
    [ -n "$(find "$d" -type f -links +1 -print -quit 2>/dev/null)" ]
}

bin_dir() { if [ "$AI_OS" = linux ]; then echo /usr/local/bin; else echo "$HOME/.local/bin"; fi; }

install_bin() {
    # install_bin <file> <name>
    if [ "$AI_OS" = linux ]; then run_root install -m 755 "$1" "/usr/local/bin/$2"
    else run mkdir -p "$HOME/.local/bin" && run install -m 755 "$1" "$HOME/.local/bin/$2"; fi
}

# Audited plugin source at a pinned commit. Linux: /opt/agent-plugins/<name>, root-owned, read-only.
plugin_src_dir() {
    if [ "$AI_OS" = linux ]; then echo "/opt/agent-plugins/$1"; else echo "$HOME/.local/share/ai/plugins/$1"; fi
}

plugin_clone() {
    # plugin_clone <name> <repo> <sha> [ref]   (ref: the tag, for an ai/audit-accepted.txt "dir" line)
    local name=$1 repo=$2 sha=$3 ref=${4:-} dest tmp
    dest=$(plugin_src_dir "$name")
    if [ -d "$dest/.git" ] && [ "$(git -C "$dest" rev-parse HEAD 2>/dev/null)" = "$sha" ]; then
        info "$name source at $dest is at the audited commit ${sha:0:7}"
        return 0
    fi
    if [ -e "$dest" ]; then
        warn "$dest exists but is not at ${sha:0:7}: left alone, fix by hand"
        return 1
    fi
    [ "$AI_SKIP_PACKAGES" = 1 ] && { skip "$name source (--skip-packages)"; return 1; }
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone $repo; checkout $sha; agent-audit dir; move to $dest"
        return 0
    fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-$name.XXXXXX")
    git clone -q "$repo" "$tmp/$name" || { warn "clone of $repo failed"; return 1; }
    git -C "$tmp/$name" -c advice.detachedHead=false checkout -q "$sha" || { warn "$name: commit $sha not found"; return 1; }
    [ "$(git -C "$tmp/$name" rev-parse HEAD)" = "$sha" ] || { warn "$name not at $sha"; return 1; }
    audit_ok dir "$tmp/$name" "$ref" "$name" || { rm -rf "$tmp"; return 1; }
    # S8: a recursive chown/chmod as root must never follow a link out of the tree.
    if [ -n "$(find "$tmp/$name" -type l -print -quit)" ]; then
        warn "$name tree contains symlinks: not installed as root (review: find $tmp/$name -type l)"
        return 1
    fi
    if [ "$AI_OS" = linux ]; then
        run_root mkdir -p /opt/agent-plugins
        run_root mv "$tmp/$name" "$dest"
        run_root chown -R root:root "$dest"
        run_root chmod -R a+rX,go-w "$dest"
        aiconf record-cmd "plugin-src:$name" -- $SUDO_UNDO rm -rf "$dest"
    else
        mkdir -p "$(dirname "$dest")" && mv "$tmp/$name" "$dest"
        aiconf record-cmd "plugin-src:$name" -- rm -rf "$dest"
    fi
    rm -rf "$tmp"
    ok "$name source cloned at ${sha:0:7} to $dest (audited)"
}

# mattpocock/skills (rules/mattpocock-skills.md step 2): the five picked folders only, at the pinned commit,
# audited. The repo has a symlink (AGENTS.md), so the tree is not moved as a whole: only the five folders,
# checked for links, are copied to <plugin src>/mattpocock-skills/<name>.
MATTPOCOCK_REPO=https://github.com/mattpocock/skills
MATTPOCOCK_PICKS="productivity/grilling productivity/grill-me productivity/wait-what productivity/writing-for-agents engineering/retro"

mattpocock_src() {
    local dest tmp p n
    dest=$(plugin_src_dir mattpocock-skills)
    if [ -f "$dest/.commit" ] && [ "$(cat "$dest/.commit")" = "$MATTPOCOCK_SKILLS_SHA" ]; then
        info "mattpocock skills at $dest are at the audited commit ${MATTPOCOCK_SKILLS_SHA:0:7}"; return 0
    fi
    [ "$AI_SKIP_PACKAGES" = 1 ] && { skip "mattpocock skills (--skip-packages)"; return 1; }
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone $MATTPOCOCK_REPO; checkout $MATTPOCOCK_SKILLS_SHA; agent-audit dir; copy $MATTPOCOCK_PICKS to $dest"
        return 0
    fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-mattpocock.XXXXXX")
    git clone -q "$MATTPOCOCK_REPO" "$tmp/src" || { warn "clone of $MATTPOCOCK_REPO failed"; rm -rf "$tmp"; return 1; }
    git -C "$tmp/src" -c advice.detachedHead=false checkout -q "$MATTPOCOCK_SKILLS_SHA" \
        || { warn "mattpocock skills: commit not found"; rm -rf "$tmp"; return 1; }
    mkdir -p "$tmp/out"
    for p in $MATTPOCOCK_PICKS; do
        [ -f "$tmp/src/skills/$p/SKILL.md" ] || { warn "mattpocock skills: skills/$p missing at the pin"; rm -rf "$tmp"; return 1; }
        if [ -n "$(find "$tmp/src/skills/$p" -type l -print -quit)" ]; then
            warn "mattpocock skills: skills/$p contains a symlink: not installed"; rm -rf "$tmp"; return 1
        fi
        cp -R "$tmp/src/skills/$p" "$tmp/out/$(basename "$p")"
    done
    printf '%s\n' "$MATTPOCOCK_SKILLS_SHA" > "$tmp/out/.commit"
    audit_ok dir "$tmp/out" "${MATTPOCOCK_SKILLS_SHA:0:12}" mattpocock-skills || { rm -rf "$tmp"; return 1; }
    if [ "$AI_OS" = linux ]; then
        run_root rm -rf "$dest"
        run_root mkdir -p "$(dirname "$dest")"
        run_root mv "$tmp/out" "$dest"
        run_root chown -R root:root "$dest"
        run_root chmod -R a+rX,go-w "$dest"
        aiconf record-cmd "plugin-src:mattpocock-skills" -- $SUDO_UNDO rm -rf "$dest"
    else
        rm -rf "$dest"; mkdir -p "$(dirname "$dest")" && mv "$tmp/out" "$dest"
        aiconf record-cmd "plugin-src:mattpocock-skills" -- rm -rf "$dest"
    fi
    rm -rf "$tmp"
    ok "mattpocock skills ($MATTPOCOCK_PICKS) at ${MATTPOCOCK_SKILLS_SHA:0:7} in $dest (audited)"
}

# One route per agent: ~/.agents/skills/<name> (Codex, opencode) and ~/.claude/skills/<name> (Claude), links.
mattpocock_link() {
    local dir=$1 src n
    src=$(plugin_src_dir mattpocock-skills)
    [ -d "$src" ] || { [ "$AI_DRY_RUN" = 1 ] || skip "mattpocock skills not installed ($src): not linked into $dir"; return 0; }
    for n in grilling grill-me wait-what writing-for-agents retro; do
        [ -f "$src/$n/SKILL.md" ] || continue
        if [ -d "$dir/$n" ] && [ ! -L "$dir/$n" ]; then warn "$dir/$n is a real folder (not ours): not linked"; continue; fi
        aiconf link "$dir/$n" "$src/$n"
    done
}

# Run a vendor setup command in a throwaway HOME first, show what it would write, then ask.
vendor_preview() {
    # vendor_preview "<label>" <cmd...>
    local label=$1; shift
    local th; th=$(mktemp -d "${TMPDIR:-/tmp}/ai-preview.XXXXXX")
    info "preview of '$label' in a throwaway HOME ($th):"
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] HOME=$th $(quote "$@")"; rm -rf "$th"; return 0; fi
    ( export HOME="$th" CLAUDE_CONFIG_DIR="$th/.claude" CODEX_HOME="$th/.codex"
      while IFS= read -r kv; do export "$kv"; done <<EOF_ENV
$(env_pairs)
EOF_ENV
      "$@" </dev/null >/dev/null 2>&1 ) || true
    # awk reads all input (head would close the pipe early: SIGPIPE 141 under pipefail killed the install).
    ( cd "$th" && find . -type f | sed 's|^\./|    ~/|' | awk 'NR<=40' ) || true
    rm -rf "$th"
}

# ---------------------------------------------------------------- harnesses (step 5)

tools_harnesses() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "harness installs (--skip-packages)"; return 0; fi
    tools_scanners   # first: every install below is audited with them

    if want claude; then
        if ! has claude; then
            if [ "$AI_OS" = linux ]; then manual "install Claude Code from its signed apt repo (ubuntu-server base, phase 5c)"
            else manual "install Claude Code (official installer), then re-run"; fi
        fi
        tools_omc
    fi
    if want codex; then
        if ! has codex; then
            npm_pinned @openai/codex "$CODEX_VERSION" "$CODEX_INTEGRITY" && ok "codex $CODEX_VERSION installed" \
                && aiconf record-cmd npm:codex -- $SUDO_UNDO npm rm -g @openai/codex
        else
            codex --version 2>/dev/null | grep -q "$CODEX_VERSION" || info "codex $(codex --version 2>/dev/null) present (pin $CODEX_VERSION: not changed)"
        fi
        tools_omx
    fi
    want opencode && tools_opencode
    want herdr && tools_herdr
    return 0
}

tools_omc() {
    if [ "$AI_OS" = macos ]; then
        info "oh-my-claudecode: the Mac uses the plugin route; npm route is Ubuntu only (contracts-mcp-c 1.6)"
        return 0
    fi
    case "${AI_OMC_WIRING:-plugin}" in
        plugin) info "oh-my-claudecode: Claude plugin route (installed in the user part); no npm CLI install"; return 0 ;;
        remove)
            if has omc; then
                run_root npm uninstall -g oh-my-claude-sisyphus && ok "oh-my-claudecode npm CLI uninstalled (AI_OMC_WIRING=remove)"
            fi
            return 0 ;;
    esac
    if has omc && omc --version 2>/dev/null | grep -q "$OMC_VERSION"; then
        info "oh-my-claudecode $OMC_VERSION present"
    else
        npm_pinned oh-my-claude-sisyphus "$OMC_VERSION" "$OMC_INTEGRITY" || return 0
        aiconf record-cmd npm:omc -- $SUDO_UNDO npm rm -g oh-my-claude-sisyphus
        ok "oh-my-claudecode $OMC_VERSION installed (scripts off)"
    fi
    if grep -qs '<!-- OMC:START -->' "$CLAUDE_DIR/CLAUDE.md"; then
        info "OMC block already in $CLAUDE_DIR/CLAUDE.md: omc setup not re-run"
        return 0
    fi
    vendor_preview "omc setup --no-plugin" omc setup --no-plugin --quiet
    if confirm "Run 'omc setup --no-plugin' for real (writes OMC hooks, agents, skills, CLAUDE.md block)?" n; then
        local before; before=$(snap_files "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/settings.json")
        run env OMC_UPDATE_REGISTRY_BASE=http://127.0.0.1:9 omc setup --no-plugin </dev/null
        report_changes "$before" "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/settings.json"
        ok "omc setup done"
    else
        manual "review the preview above, then run: omc setup --no-plugin && omc doctor"
    fi
}

tools_omx() {
    if [ "$(today)" \< "$OMX_NOT_BEFORE" ]; then
        skip "oh-my-codex $OMX_VERSION: not before $OMX_NOT_BEFORE (re-run install after that date)"
        return 0
    fi
    if has omx && omx --version 2>/dev/null | grep -q "$OMX_VERSION"; then
        info "oh-my-codex $OMX_VERSION present"
    else
        OMX_AUTO_UPDATE=0 OMX_NATIVE_AUTO_FETCH=0 npm_pinned oh-my-codex "$OMX_VERSION" "$OMX_INTEGRITY" || return 0
        aiconf record-cmd npm:omx -- $SUDO_UNDO npm rm -g oh-my-codex
        ok "oh-my-codex $OMX_VERSION installed (scripts off, native fetch off)"
    fi
    if grep -qs 'OMX:RUNTIME:START' "$CODEX_DIR/AGENTS.md"; then
        info "OMX block already in $CODEX_DIR/AGENTS.md: omx setup not re-run"
        return 0
    fi
    vendor_preview "omx setup" env OMX_AUTO_UPDATE=0 OMX_NATIVE_AUTO_FETCH=0 omx setup
    if confirm "Run 'omx setup' for real (writes Codex config, hooks, AGENTS.md block)?" n; then
        local before; before=$(snap_files "$CODEX_DIR/AGENTS.md" "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json")
        run env OMX_AUTO_UPDATE=0 OMX_NATIVE_AUTO_FETCH=0 omx setup </dev/null
        report_changes "$before" "$CODEX_DIR/AGENTS.md" "$CODEX_DIR/config.toml" "$CODEX_DIR/hooks.json"
        ok "omx setup done"
    else
        manual "review the preview above, then run: omx setup && omx doctor"
    fi
}

tools_opencode() {
    if has opencode && opencode --version 2>/dev/null | grep -q "$OPENCODE_VERSION"; then
        info "opencode $OPENCODE_VERSION present"; return 0
    fi
    npm_pinned opencode-ai "$OPENCODE_VERSION" "$OPENCODE_INTEGRITY" || return 0
    aiconf record-cmd npm:opencode -- $SUDO_UNDO npm rm -g opencode-ai
    # --ignore-scripts skips the postinstall that places the binary: link it by hand (SPEC 19).
    local root os arch pkg bin
    root=$(npm root -g)
    case "$AI_OS" in linux) os=linux ;; macos) os=darwin ;; esac
    case "$AI_ARCH" in x86_64|amd64) arch=x64 ;; arm64|aarch64) arch=arm64 ;; *) arch=$AI_ARCH ;; esac
    pkg="opencode-$os-$arch"
    if [ "$arch" = x64 ] && ! cpu_has_avx2 && [ -d "$root/opencode-ai/node_modules/$pkg-baseline" ]; then
        pkg="$pkg-baseline"
    fi
    bin="$root/opencode-ai/node_modules/$pkg/bin/opencode"
    if [ "$AI_DRY_RUN" = 1 ] || [ -x "$bin" ]; then
        run_root ln -f "$bin" "$root/opencode-ai/bin/opencode.exe"
        ok "opencode $OPENCODE_VERSION installed ($pkg)"
    else
        warn "opencode binary not found at $bin: check the package layout"
    fi
}

tools_herdr() {
    if has herdr; then info "herdr $(herdr --version 2>/dev/null | head -n1) present"; return 0; fi
    local tmp; tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-herdr.XXXXXX")
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] download $HERDR_INSTALLER_URL, check sha256 $HERDR_INSTALLER_SHA256, run with HERDR_INSTALL_DIR=$(bin_dir)"
        rm -rf "$tmp"; return 0
    fi
    curl -fsSL -o "$tmp/install.sh" "$HERDR_INSTALLER_URL" || { warn "herdr installer download failed"; return 0; }
    if ! sha256_is "$tmp/install.sh" "$HERDR_INSTALLER_SHA256"; then
        warn "herdr installer sha256 changed: not run (new audit needed)"; rm -rf "$tmp"; return 0
    fi
    # Ask the installer for the pinned version, then check what it really put there.
    if [ "$AI_OS" = linux ]; then run_root env HERDR_VERSION="$HERDR_VERSION" HERDR_INSTALL_DIR=/usr/local/bin sh "$tmp/install.sh"
    else run env HERDR_VERSION="$HERDR_VERSION" HERDR_INSTALL_DIR="$HOME/.local/bin" sh "$tmp/install.sh"; fi
    rm -rf "$tmp"
    aiconf record-cmd bin:herdr -- $SUDO_UNDO rm -f "$(bin_dir)/herdr"
    local hb="$(bin_dir)/herdr"
    if ! "$hb" --version 2>/dev/null | grep -q "$HERDR_VERSION"; then
        warn "herdr installed is $("$hb" --version 2>/dev/null | head -n1), pin is $HERDR_VERSION: check before use"
    elif [ -n "$HERDR_BIN_SHA256" ] && ! sha256_is "$hb" "$HERDR_BIN_SHA256"; then
        warn "herdr binary sha256 differs from HERDR_BIN_SHA256: check before use"
    else
        ok "herdr $HERDR_VERSION installed (audited installer, sha256 checked, version verified)"
    fi
}

# ---------------------------------------------------------------- tools (step 6)

# User tools: installed as the user, never root (uv tools, per-user npm prefix).
tools_user() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "user tool installs (--skip-packages)"; return 0; fi

    if has serena && serena --version 2>/dev/null | grep -q "$SERENA_VERSION" && ! uv_tool_linked serena-agent; then
        info "serena $SERENA_VERSION present"
    else uv_pinned serena-agent "$SERENA_VERSION" "$SERENA_PYTHON" && ok "serena $SERENA_VERSION" \
        && aiconf record-cmd uv:serena -- uv tool uninstall serena-agent; fi

    if has graphify && graphify --version 2>/dev/null | grep -q "$GRAPHIFY_VERSION" && ! uv_tool_linked graphifyy; then
        info "graphify $GRAPHIFY_VERSION present"
    else uv_pinned graphifyy "$GRAPHIFY_VERSION" && ok "graphify $GRAPHIFY_VERSION (no extras)" \
        && aiconf record-cmd uv:graphify -- uv tool uninstall graphifyy; fi

    tools_context7
    tools_rtk_excludes
    # Root pieces this user needs: report what is missing with the one admin command.
    if [ "$AI_MODE" = user ]; then
        has rtk || manual "rtk missing (system part): $(admin_cmd)"
        [ -d "$(plugin_src_dir ponytail)" ] || manual "Ponytail source missing (system part): $(admin_cmd)"
    fi
    return 0
}

# RTK must leave `git push` and every gh call alone (rtk v1.2.0 [hooks] exclude_commands; an entry also covers
# the path spellings, /usr/bin/git push): Claude runs them OUTSIDE its sandbox only as the exact absolute
# command in sandbox.excludedCommands, which the router writes. Two hooks returning updatedInput for one call
# have no defined winner (hooks run in parallel), so RTK must not rewrite these at all (Fable readiness B2).
RTK_EXCLUDE='["git push", "gh"]'
rtk_config_file() {
    if [ "$AI_OS" = macos ]; then echo "$HOME/Library/Application Support/rtk/config.toml"
    else echo "${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml"; fi
}
tools_rtk_excludes() {
    has rtk || return 0
    local f; f=$(rtk_config_file)
    mkdir -p "$(dirname "$f")"
    aiconf toml-set "$f" hooks exclude_commands "$RTK_EXCLUDE"
}

# System tools: binaries in /usr/local/bin and audited plugin sources in /opt (root on Linux).
tools_system() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "system tool installs (--skip-packages)"; return 0; fi
    tools_rtk
    tools_sandbox_deps
    plugin_clone ponytail "$PONYTAIL_REPO" "$PONYTAIL_SHA" || true
    plugin_clone i-have-adhd "$IHAVEADHD_REPO" "$IHAVEADHD_SHA" || true
    # Readable skill files of the Claude-only packs for agents that cannot hand off to Claude (Codex,
    # Hermes, opencode without a Claude login): the router points them here (claude_handoff).
    plugin_clone claude-seo https://github.com/AgriciDaniel/claude-seo "$CLAUDE_SEO_SHA" "$CLAUDE_SEO_REF" || true
    plugin_clone claude-blog https://github.com/AgriciDaniel/claude-blog "$CLAUDE_BLOG_SHA" "$CLAUDE_BLOG_REF" || true
    mattpocock_src || true
    return 0
}

# Audit scanners for agent-audit (guarddog, skill-scanner, osv-scanner). Every other install is audited with
# them, so they come first. They cannot audit themselves: exact pinned versions, wheels only, sha256 for the
# osv-scanner binary. Linux: system-wide (/opt/uv-tools, links in /usr/local/bin, root-owned). macOS: the
# user's uv tools and ~/.local/bin.
scanner_ok() { has "$1" && "$1" --version 2>/dev/null | grep -q "$2"; }

tools_scanners() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "audit scanners (--skip-packages)"; return 0; fi
    local pair name ver bin
    for pair in "guarddog:$GUARDDOG_VERSION:guarddog" "cisco-ai-skill-scanner:$SKILL_SCANNER_VERSION:skill-scanner"; do
        name=${pair%%:*}; ver=${pair#*:}; ver=${ver%%:*}; bin=${pair##*:}
        if scanner_ok "$bin" "$ver"; then info "$bin $ver present"; continue; fi
        if [ "$AI_OS" = linux ]; then
            run_root env UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin UV_LINK_MODE=copy \
                uv tool install --force --no-build -p "$SCANNER_PYTHON" "$name==$ver" || { warn "$bin $ver install failed"; continue; }
            aiconf record-cmd "uv-root:$bin" -- $SUDO_UNDO env UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin uv tool uninstall "$name"
        else
            run env UV_LINK_MODE=copy uv tool install --force --no-build -p "$SCANNER_PYTHON" "$name==$ver" \
                || { warn "$bin $ver install failed"; continue; }
            aiconf record-cmd "uv:$bin" -- uv tool uninstall "$name"
        fi
        ok "$bin $ver (pinned, wheels only)"
    done
    tools_osv_scanner
}

tools_osv_scanner() {
    local ver=$OSV_SCANNER_VERSION os arch var want got tmp
    if scanner_ok osv-scanner "$ver"; then info "osv-scanner $ver present"; return 0; fi
    case "$AI_OS" in linux) os=linux ;; macos) os=darwin ;; esac
    case "$AI_ARCH" in x86_64|amd64) arch=amd64 ;; arm64|aarch64) arch=arm64 ;; *) warn "osv-scanner: no build for $AI_ARCH"; return 0 ;; esac
    var="OSV_SCANNER_SHA256_${os}_${arch}"; want=$(eval "printf '%s' \"\${$var:-}\"")
    [ -n "$want" ] || { warn "osv-scanner: no pinned sha256 for ${os}_${arch}"; return 0; }
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] download osv-scanner v$ver ${os}_${arch}, check sha256, install"; return 0; fi
    tmp=$(mktemp "${TMPDIR:-/tmp}/osv.XXXXXX")
    curl -fsSL -o "$tmp" "https://github.com/google/osv-scanner/releases/download/v$ver/osv-scanner_${os}_${arch}" \
        || { rm -f "$tmp"; warn "osv-scanner download failed"; return 0; }
    got=$( (sha256sum "$tmp" 2>/dev/null || shasum -a 256 "$tmp") | cut -d' ' -f1)
    if [ "$got" != "$want" ]; then rm -f "$tmp"; warn "osv-scanner sha256 mismatch ($got): not installed"; return 0; fi
    install_bin "$tmp" osv-scanner; rm -f "$tmp"
    aiconf record-cmd bin:osv-scanner -- $SUDO_UNDO rm -f "$(bin_dir)/osv-scanner"
    ok "osv-scanner $ver (sha256 checked)"
}

# context7 MCP: one pinned install per user, run by mcp/context7.sh (no runtime npx, B3).
AI_NPM_DIR="$HOME/.local/share/ai/npm"
tools_context7() {
    local dir="$AI_NPM_DIR/context7-mcp-$CONTEXT7_MCP_VERSION"
    if [ -x "$dir/node_modules/.bin/context7-mcp" ]; then info "context7-mcp $CONTEXT7_MCP_VERSION present"; return 0; fi
    npm_local @upstash/context7-mcp "$CONTEXT7_MCP_VERSION" "$CONTEXT7_MCP_INTEGRITY" "$dir" || return 0
    aiconf record-cmd "npm-local:context7" -- rm -rf "$dir"
    ok "context7-mcp $CONTEXT7_MCP_VERSION in $dir (integrity checked, scripts off)"
}

# RTK: latest stable compatible (owner decision 2026-11-12), not a fixed pin. The tag is the newest stable
# release (no pre-release, no draft, plain vX.Y.Z) that is at least RTK_COOLDOWN_DAYS old; when the audited pin
# RTK_TAG is newer than that, the pin wins (already audited). Offline or API error: the pin. Always built from
# source (prebuilt x86_64 binaries need AVX2, contracts-mcp-a 4.6), so every OS and arch gets the same path,
# and the source tree is audited before the build. The resolved tag and commit go to the audit log.
rtk_resolve_tag() {
    local api="https://api.github.com/repos/${RTK_REPO#https://github.com/}/releases?per_page=100" json
    json=$(curl -fsSL --max-time 20 "$api" 2>/dev/null) || { printf '%s' "$RTK_TAG"; return 0; }
    printf '%s' "$json" | python3 -c '
import json, re, sys, datetime as dt
pin, days = sys.argv[1], int(sys.argv[2])
def key(t): return tuple(int(x) for x in t[1:].split("."))
now = dt.datetime.now(dt.timezone.utc)
best = None
for r in json.load(sys.stdin):
    t = r.get("tag_name", "")
    if r.get("prerelease") or r.get("draft") or not re.fullmatch(r"v\d+\.\d+\.\d+", t):
        continue
    age = now - dt.datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
    if age.days >= days and (best is None or key(t) > key(best)):
        best = t
if best is None or (re.fullmatch(r"v\d+\.\d+\.\d+", pin) and key(pin) > key(best)):
    best = pin
print(best, end="")
' "$RTK_TAG" "${RTK_COOLDOWN_DAYS:-7}" 2>/dev/null || printf '%s' "$RTK_TAG"
}

tools_rtk() {
    local tag ver
    tag=$(rtk_resolve_tag); ver=${tag#v}
    if has rtk && rtk --version 2>/dev/null | grep -q "$ver"; then info "rtk $ver present (latest stable compatible)"; return 0; fi
    if ! has cargo; then
        if [ "$AI_OS" = linux ] && confirm "apt-get install cargo rustc pkg-config libssl-dev (to build RTK)?" y; then
            run_root apt-get install -y -q cargo rustc pkg-config libssl-dev
        elif [ "$AI_OS" = macos ] && has brew && confirm "brew install rust (to build RTK)?" y; then
            run brew install rust
        else
            manual "install a Rust toolchain, then re-run to build rtk $tag from source"; return 0
        fi
    fi
    local src
    if [ "$AI_MODE" = system ]; then src="$AI_TARGET_HOME/.cache/ai/build/rtk"; else src="$AI_BUILD_DIR/rtk"; fi
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone --depth 1 --branch $tag $RTK_REPO $src; agent-audit dir; cargo build --release --locked; install"
        return 0
    fi
    # Build as the user (system mode: the target user), never as root; only the install is root.
    as_target rm -rf "$src"; as_target mkdir -p "$(dirname "$src")"
    as_target git clone -q --depth 1 --branch "$tag" "$RTK_REPO" "$src" || { warn "rtk clone failed"; return 0; }
    local rtkhead
    if [ "$AI_MODE" = system ]; then rtkhead=$(sudo -u "$AI_FOR_USER" git -C "$src" rev-parse HEAD)
    else rtkhead=$(git -C "$src" rev-parse HEAD); fi
    # The pinned tag must still point to the audited commit; a newer tag is audited below like any source.
    if [ "$tag" = "$RTK_TAG" ] && [ "$rtkhead" != "$RTK_COMMIT" ]; then
        warn "rtk tag $RTK_TAG now points to $rtkhead, pin is $RTK_COMMIT: not built (tag moved, new audit needed)"
        return 0
    fi
    audit_ok dir "$src" || return 0
    as_target sh -c "cd '$src' && cargo build --release --locked" || { warn "rtk build failed"; return 0; }
    install_bin "$src/target/release/rtk" rtk
    aiconf record-cmd bin:rtk -- $SUDO_UNDO rm -f "$(bin_dir)/rtk"
    mkdir -p "$AI_STATE_DIR"
    printf '%s rtk %s %s built (latest stable compatible)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$rtkhead" >> "$AI_STATE_DIR/audit.log"
    ok "rtk $ver built from source ($tag, $rtkhead)"
}

# ---------------------------------------------------------------- dropped tools (owner decision 2026-11-12)

# Grounded Docs (service, unit, port 6280, npm package, firewall rules) and the GitHub MCP (binary, MCP
# entries) were dropped: agents use context7 and the gh CLI. Earlier installs recorded every piece, so the
# removal replays exactly those undo records (uninstall stays symmetric: nothing left to undo later).
DROPPED_SYSTEM_KEYS='^(cmd:npm:docs-mcp|cmd:systemd:ai-docs-mcp|cmd:ufw:.*:6280|file:/etc/systemd/system/ai-docs-mcp\.service|file:/etc/default/ai-docs-mcp|cmd:bin:github-mcp-server)$'
DROPPED_USER_KEYS='^(cmd|restore):(codex|hermes)-mcp:(github|grounded-docs)$|^json:.*opencode\.json:mcp/(github|grounded-docs)$'

tools_drop_system() {
    [ "$AI_OS" = linux ] || return 0
    [ "$AI_MODE" = user ] && return 0
    if [ -f "$AI_SYSTEM_STATE_FILE" ] || [ "$AI_DRY_RUN" = 1 ]; then
        aiconf_root undo --only "$DROPPED_SYSTEM_KEYS"
    fi
    if [ "$AI_DRY_RUN" != 1 ] && systemctl list-unit-files ai-docs-mcp.service >/dev/null 2>&1 \
        && systemctl cat ai-docs-mcp.service >/dev/null 2>&1; then
        warn "ai-docs-mcp.service still exists (not recorded by this setup): remove it by hand"
    fi
    ok "dropped tools removed from the system: Grounded Docs server, GitHub MCP binary (recorded undo replayed)"
}

# Agents a Linux server does not use (owner decision 2026-11-12: Claude, Codex, Hermes). An earlier install of
# opencode or herdr is undone from its records; AI_EXTRA_AGENTS=opencode,herdr brings them back.
AGENT_USER_KEYS_opencode='^(json|json-del|json-item):[^:]*/opencode/opencode\.json:|^link:.*/opencode/plugin/|^file:.*/opencode/'
AGENT_USER_KEYS_herdr='^cmd:herdr-integration:|^toml:[^:]*/herdr/config\.toml:'
AGENT_SYSTEM_KEYS_opencode='^cmd:npm:opencode$|^(json|json-item|json-add):/etc/opencode/'
AGENT_SYSTEM_KEYS_herdr='^cmd:bin:herdr$'
agents_dropped() {
    [ "$AI_OS" = linux ] || return 0
    local a
    for a in opencode herdr; do want "$a" || printf '%s\n' "$a"; done
}
agents_drop_user() {
    local a keys
    for a in $(agents_dropped); do
        keys=AGENT_USER_KEYS_$a
        aiconf undo --only "${!keys}"
    done
    [ -z "$(agents_dropped)" ] || ok "agents not used on this server, their user config undone: $(agents_dropped | tr '\n' ' ')"
}
agents_drop_system() {
    [ "$AI_MODE" = user ] && return 0
    local a keys
    for a in $(agents_dropped); do
        keys=AGENT_SYSTEM_KEYS_$a
        aiconf_root undo --only "${!keys}"
    done
    [ -z "$(agents_dropped)" ] || ok "agents not used on this server removed (recorded undo): $(agents_dropped | tr '\n' ' ')"
}

# User side: our codex/hermes/opencode registrations of github, grounded-docs and the global serena.
tools_drop_user() {
    aiconf undo --only "$DROPPED_USER_KEYS"
    ok "dropped MCP registrations removed (github, grounded-docs)"
}

# ---------------------------------------------------------------- Claude sandbox dependencies (Linux)

# The Claude Bash sandbox needs bubblewrap, socat and ripgrep (code.claude.com/docs/en/sandboxing). Ubuntu
# restricts unprivileged user namespaces through AppArmor: bubblewrap needs the profile the docs give.
AI_BWRAP=/usr/local/lib/ai/bwrap

tools_sandbox_deps() {
    [ "$AI_OS" = linux ] || return 0
    local missing="" c
    for c in bwrap socat rg; do has "$c" || missing="$missing $c"; done
    if [ -n "$missing" ]; then
        run_root apt-get install -y -q bubblewrap socat ripgrep && ok "apt-get install bubblewrap socat ripgrep (sandbox)"
    fi
    [ "$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)" = 1 ] || return 0
    # Ubuntu's bwrap-userns-restrict confines /usr/bin/bwrap's children (unpriv_bwrap: no capabilities), which
    # breaks the sandbox's apply-seccomp step. A root-owned copy at its own path gets the docs' bubblewrap
    # profile (unconfined + userns); /usr/bin/bwrap and the sysctl stay as Ubuntu set them. Re-copied every
    # install so it follows apt updates of bubblewrap.
    # Only the user the agents run as may start it: group ai-sandbox (that user alone, not hermes, not admin),
    # mode 0750. A user added just now must log in again before Claude can start.
    if ! getent group ai-sandbox >/dev/null 2>&1; then
        run_root groupadd --system ai-sandbox
        aiconf_root record-cmd group:ai-sandbox -- groupdel ai-sandbox
    fi
    if [ -n "${AI_FOR_USER:-}" ] && ! id -nG "$AI_FOR_USER" 2>/dev/null | tr ' ' '\n' | grep -qx ai-sandbox; then
        run_root usermod -aG ai-sandbox "$AI_FOR_USER"
        aiconf_root record-cmd "group:ai-sandbox:$AI_FOR_USER" -- gpasswd -d "$AI_FOR_USER" ai-sandbox
        manual "$AI_FOR_USER was added to group ai-sandbox: log in again (new ssh session) before starting Claude"
    fi
    if [ "$AI_DRY_RUN" = 1 ] || ! cmp -s /usr/bin/bwrap "$AI_BWRAP" 2>/dev/null; then
        run_root install -d -o root -g root -m 755 /usr/local/lib/ai
        run_root install -o root -g ai-sandbox -m 750 /usr/bin/bwrap "$AI_BWRAP"
        aiconf_root record-cmd bin:ai-bwrap -- rm -f "$AI_BWRAP"
    fi
    run_root chown root:ai-sandbox "$AI_BWRAP"
    run_root chmod 750 "$AI_BWRAP"
    aiconf_root file-put /etc/apparmor.d/ai-claude-bwrap "$AI_HOME/ai/adapters/linux/apparmor-bwrap" --mode 644
    run_root apparmor_parser -r /etc/apparmor.d/ai-claude-bwrap
    aiconf_root record-cmd apparmor:ai-claude-bwrap -- apparmor_parser -R /etc/apparmor.d/ai-claude-bwrap
    ok "Claude sandbox: bubblewrap copy $AI_BWRAP (root:ai-sandbox 0750, group = ${AI_FOR_USER:-?} only) with its own AppArmor profile"
}
