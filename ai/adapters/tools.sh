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

# uv tool install of an exact version, as the user (never root), wheels only (--no-build).
uv_pinned() {
    # uv_pinned <pypi-name> <version> [python]
    local name=$1 ver=$2 py=${3:-}
    audit_ok pypi "$name" "$ver" || return 1
    if [ -n "$py" ]; then run uv tool install --force --no-build -p "$py" "$name==$ver"
    else run uv tool install --force --no-build "$name==$ver"; fi
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
    # plugin_clone <name> <repo> <sha>
    local name=$1 repo=$2 sha=$3 dest tmp
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
    audit_ok dir "$tmp/$name" || { rm -rf "$tmp"; return 1; }
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

    if has serena && serena --version 2>/dev/null | grep -q "$SERENA_VERSION"; then info "serena $SERENA_VERSION present"
    else uv_pinned serena-agent "$SERENA_VERSION" "$SERENA_PYTHON" && ok "serena $SERENA_VERSION" \
        && aiconf record-cmd uv:serena -- uv tool uninstall serena-agent; fi

    if has graphify && graphify --version 2>/dev/null | grep -q "$GRAPHIFY_VERSION"; then info "graphify $GRAPHIFY_VERSION present"
    else uv_pinned graphifyy "$GRAPHIFY_VERSION" && ok "graphify $GRAPHIFY_VERSION (no extras)" \
        && aiconf record-cmd uv:graphify -- uv tool uninstall graphifyy; fi

    tools_context7
    # Root pieces this user needs: report what is missing with the one admin command.
    if [ "$AI_MODE" = user ]; then
        has rtk || manual "rtk missing (system part): $(admin_cmd)"
        has github-mcp-server || manual "github-mcp-server missing (system part): $(admin_cmd)"
        [ -d "$(plugin_src_dir ponytail)" ] || manual "Ponytail source missing (system part): $(admin_cmd)"
    fi
    return 0
}

# System tools: binaries in /usr/local/bin and audited plugin sources in /opt (root on Linux).
tools_system() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "system tool installs (--skip-packages)"; return 0; fi
    tools_rtk
    tools_github_mcp
    plugin_clone ponytail "$PONYTAIL_REPO" "$PONYTAIL_SHA" || true
    plugin_clone i-have-adhd "$IHAVEADHD_REPO" "$IHAVEADHD_SHA" || true
    return 0
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

# RTK from source at the pinned tag: prebuilt x86_64 binaries need AVX2 (contracts-mcp-a 4.6).
tools_rtk() {
    if has rtk && rtk --version 2>/dev/null | grep -q "$RTK_VERSION"; then info "rtk $RTK_VERSION present"; return 0; fi
    if ! has cargo; then
        if [ "$AI_OS" = linux ] && confirm "apt-get install cargo rustc pkg-config libssl-dev (to build RTK)?" y; then
            run_root apt-get install -y -q cargo rustc pkg-config libssl-dev
        else
            manual "install a Rust toolchain, then re-run to build rtk $RTK_TAG from source"; return 0
        fi
    fi
    local src
    if [ "$AI_MODE" = system ]; then src="$AI_TARGET_HOME/.cache/ai/build/rtk"; else src="$AI_BUILD_DIR/rtk"; fi
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone --depth 1 --branch $RTK_TAG $RTK_REPO $src; agent-audit dir; cargo build --release --locked; install"
        return 0
    fi
    # Build as the user (system mode: the target user), never as root; only the install is root.
    as_target rm -rf "$src"; as_target mkdir -p "$(dirname "$src")"
    as_target git clone -q --depth 1 --branch "$RTK_TAG" "$RTK_REPO" "$src" || { warn "rtk clone failed"; return 0; }
    local rtkhead
    if [ "$AI_MODE" = system ]; then rtkhead=$(sudo -u "$AI_FOR_USER" git -C "$src" rev-parse HEAD)
    else rtkhead=$(git -C "$src" rev-parse HEAD); fi
    if [ "$rtkhead" != "$RTK_COMMIT" ]; then
        warn "rtk tag $RTK_TAG now points to $rtkhead, pin is $RTK_COMMIT: not built (tag moved, new audit needed)"
        return 0
    fi
    audit_ok dir "$src" || return 0
    as_target sh -c "cd '$src' && cargo build --release --locked" || { warn "rtk build failed"; return 0; }
    install_bin "$src/target/release/rtk" rtk
    aiconf record-cmd bin:rtk -- $SUDO_UNDO rm -f "$(bin_dir)/rtk"
    ok "rtk $RTK_VERSION built from source"
}

tools_github_mcp() {
    if has github-mcp-server && github-mcp-server --version 2>/dev/null | grep -q "$GITHUB_MCP_VERSION"; then
        info "github-mcp-server $GITHUB_MCP_VERSION present"; return 0
    fi
    local asset sum os
    case "$AI_OS:$AI_ARCH" in
        linux:x86_64) asset="github-mcp-server_Linux_x86_64.tar.gz"; sum=$GITHUB_MCP_SHA256_LINUX_X86_64 ;;
        macos:arm64)  asset="github-mcp-server_Darwin_arm64.tar.gz"; sum=$GITHUB_MCP_SHA256_DARWIN_ARM64 ;;
        *) skip "github-mcp-server: no pinned asset for $AI_OS $AI_ARCH"; return 0 ;;
    esac
    if [ -z "$sum" ]; then
        skip "github-mcp-server $GITHUB_MCP_VERSION: checksum not pinned yet (audit owed, contracts-mcp-b)"
        manual "after the GitHub MCP audit, set GITHUB_MCP_SHA256_* in ai/pins.env and re-run"
        return 0
    fi
    local url="https://github.com/github/github-mcp-server/releases/download/v$GITHUB_MCP_VERSION/$asset"
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] agent-audit dir on tag v$GITHUB_MCP_VERSION source; download $url; sha256 $sum; install"
        return 0
    fi
    local tmp; tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-ghmcp.XXXXXX")
    # Audit the tag source first (SPEC 21), then take the release binary only if its sha256 is the pin.
    git clone -q --depth 1 --branch "v$GITHUB_MCP_VERSION" https://github.com/github/github-mcp-server "$tmp/src" \
        || { warn "github-mcp-server tag source clone failed"; rm -rf "$tmp"; return 0; }
    audit_ok dir "$tmp/src" "v$GITHUB_MCP_VERSION" github-mcp-server || { rm -rf "$tmp"; return 0; }
    curl -fsSL -o "$tmp/$asset" "$url" || { warn "download failed: $url"; rm -rf "$tmp"; return 0; }
    sha256_is "$tmp/$asset" "$sum" || { warn "github-mcp-server checksum mismatch: not installed"; rm -rf "$tmp"; return 0; }
    mkdir -p "$tmp/x" && tar -xzf "$tmp/$asset" -C "$tmp/x"
    install_bin "$tmp/x/github-mcp-server" github-mcp-server
    rm -rf "$tmp"
    aiconf record-cmd bin:github-mcp-server -- $SUDO_UNDO rm -f "$(bin_dir)/github-mcp-server"
    ok "github-mcp-server $GITHUB_MCP_VERSION installed (sha256 checked)"
}

# ---------------------------------------------------------------- Grounded Docs server role (step 13)

tools_docs_server() {
    [ "$AI_OS" = linux ] || { skip "Grounded Docs server role is Linux only"; return 0; }
    if [ -z "$DOCS_MCP_INTEGRITY" ]; then
        skip "Grounded Docs $DOCS_MCP_VERSION: integrity not pinned in ai/pins.env"
        manual "after the Grounded Docs audit, set DOCS_MCP_INTEGRITY in ai/pins.env and re-run with --docs-server"
        return 0
    fi
    if ! (has docs-mcp-server && npm ls -g --depth=0 2>/dev/null | grep -q "@arabold/docs-mcp-server@$DOCS_MCP_VERSION"); then
        npm_pinned @arabold/docs-mcp-server "$DOCS_MCP_VERSION" "$DOCS_MCP_INTEGRITY" || return 0
        aiconf_root record-cmd npm:docs-mcp -- npm rm -g @arabold/docs-mcp-server
    fi
    local d="$AI_HOME/ai/mcp/docs-server"
    aiconf_root file-put /etc/systemd/system/ai-docs-mcp.service "$d/ai-docs-mcp.service" --mode 644
    [ -f /etc/default/ai-docs-mcp ] || aiconf_root file-put /etc/default/ai-docs-mcp "$d/ai-docs-mcp.default" --mode 644

    # S9: the server binds all interfaces, so the firewall must be ON and limit the port to the LAN
    # interface and tailscale0 BEFORE it starts. Clients are read-only (DOCS_MCP_READ_ONLY=true in the
    # unit), so nobody on the network can add a scrape source (no SSRF through the server).
    has ufw || { warn "ufw not found: Grounded Docs NOT started (it would listen on every interface)"; return 0; }
    local lan ifc
    lan=$(ip route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}' || true)
    for ifc in $lan tailscale0; do
        [ -n "$ifc" ] || continue
        run_root ufw allow in on "$ifc" to any port "$DOCS_MCP_PORT" proto tcp comment "ai grounded docs"
        aiconf_root record-cmd "ufw:$ifc:$DOCS_MCP_PORT" -- ufw delete allow in on "$ifc" to any port "$DOCS_MCP_PORT" proto tcp
    done
    if [ "$AI_DRY_RUN" != 1 ]; then
        local st; st=$(sudo ufw status 2>/dev/null || true)
        if ! printf '%s\n' "$st" | grep -q '^Status: active' \
            || ! printf '%s\n' "$st" | grep -qE "^$DOCS_MCP_PORT/tcp on "; then
            warn "ufw is not active or has no $DOCS_MCP_PORT/tcp rule: Grounded Docs NOT started"
            manual "enable ufw with the LAN/tailscale0 rules for $DOCS_MCP_PORT, then: sudo systemctl enable --now ai-docs-mcp"
            return 0
        fi
    fi
    run_root systemctl daemon-reload
    run_root systemctl enable --now ai-docs-mcp.service
    aiconf_root record-cmd systemd:ai-docs-mcp -- systemctl disable --now ai-docs-mcp.service
    ok "Grounded Docs server on port $DOCS_MCP_PORT (telemetry off)"
    manual "check flags in /etc/default/ai-docs-mcp against 'docs-mcp-server --help' (flag names UNVERIFIED), then index libraries"
}
