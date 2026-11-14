# ai/adapters/tools.sh: installs of harnesses and tools at the newest stable release (owner decision
# 2026-11-14), each audited first and installed as an exact version. Sourced by install.sh. bash 3.2.
# Each function does nothing when the resolved version is present, and moves the tool when it differs.

AI_BUILD_DIR="$HOME/.cache/ai/build"

# ---------------------------------------------------------------- newest stable (owner decision 2026-11-14)

# ai/pins.env names where each tool comes from; ai/lib/resolve.py finds the newest stable release (no
# pre-release, draft or yanked version; no cooldown) or the version a <PREFIX>_HOLD line asks for.
AI_RESOLVE="$AI_HOME/ai/lib/resolve.py"
resolver() { AI_STATE_DIR="$AI_STATE_DIR" python3 "$AI_RESOLVE" "$@"; }

# resolve_tool <tool id>: sets R_TOOL R_VERSION R_REF R_SHA R_INTEGRITY R_CHECKSUMS R_SOURCE R_STATUS R_NOTE.
# R_STATUS: new | hold | cached (offline or registry error: the last resolved value) | none. False when nothing
# is known (offline and never resolved): the caller keeps what is installed; the install goes on.
resolve_tool() {
    local out nw=""
    R_TOOL=$1; R_VERSION=""; R_REF=""; R_SHA=""; R_INTEGRITY=""; R_CHECKSUMS=""; R_SOURCE=""; R_STATUS=none; R_NOTE=""
    [ "$AI_DRY_RUN" = 1 ] && nw=--no-write
    out=$(resolver shell "$1" $nw 2>/dev/null) || out=""
    case "$out" in R_VERSION=*) eval "$out" ;; esac
    case "$R_STATUS" in
        new)    info "$1: newest stable $R_VERSION${R_SHA:+ (${R_SHA:0:12})} from $R_SOURCE" ;;
        hold)   info "$1: held at $R_VERSION${R_SHA:+ (${R_SHA:0:12})} ($R_NOTE)" ;;
        cached) info "$1: newest stable not checked ($R_NOTE): using the last resolved $R_VERSION" ;;
        *)      warn "$1: newest stable unknown (${R_NOTE:-resolver failed}): kept as it is"; return 1 ;;
    esac
}

# aud_word: how a package install was checked ("audit skipped" on profile dev-mac, said on every install).
aud_word() { if [ "${PROFILE_PACKAGE_AUDIT:-1}" = 0 ]; then printf 'audit skipped'; else printf 'audited'; fi; }

# ver_eq <a> <b>: the same version, trailing ".0" parts ignored (1.0 = 1.0.0; uv and some tools print the short form).
ver_eq() {
    [ -n "$1" ] && [ "$(printf '%s' "$1" | sed -E 's/(\.0+)+$//')" = "$(printf '%s' "$2" | sed -E 's/(\.0+)+$//')" ]
}

# r_keep <installed version>: true when nothing should change: the installed version is the resolved one, or
# the resolver had no answer (status cached) and something is installed (kept, and said so).
r_keep() {
    ver_eq "$1" "$R_VERSION" && return 0
    if [ -n "$1" ] && [ "$R_STATUS" = cached ]; then info "$R_TOOL $1 kept (offline: not moved to $R_VERSION)"; return 0; fi
    return 1
}

# r_record [sha]: what was just installed goes to resolved.json ("installed") and one audit.log line.
r_record() {
    [ "$AI_DRY_RUN" = 1 ] && return 0
    resolver record "$R_TOOL" --version "$R_VERSION" --sha "${1:-$R_SHA}" --integrity "$R_INTEGRITY" >/dev/null 2>&1 \
        || warn "$R_TOOL: resolved.json not written"
}

# tool_version <command>: the first dotted number in `<command> --version`, or nothing.
tool_version() {
    has "$1" || return 0
    "$1" --version 2>/dev/null | awk '!f && match($0, /[0-9]+\.[0-9]+(\.[0-9]+)*/) { print substr($0, RSTART, RLENGTH); f = 1 }' || true
}

# npm_dir_version <base> <name>: the highest <name>-<version> folder under <base> (per-version npm installs).
npm_dir_version() {
    { ls -1 "$1" 2>/dev/null || true; } | sed -n "s/^$2-\([0-9][0-9.]*\)\$/\1/p" | sort -t. -k1,1n -k2,2n -k3,3n | tail -n 1
}

# npm_owns <command>: true when the command on PATH is a file of the global npm tree (not brew, not a standalone
# installer). A copy from elsewhere is never shadowed by a second npm copy.
npm_owns() {
    local p root
    p=$(command -v "$1" 2>/dev/null) || return 1
    root=$(npm root -g 2>/dev/null) || return 1
    python3 -c 'import os,sys; r=os.path.realpath(sys.argv[2]); sys.exit(0 if os.path.realpath(sys.argv[1]).startswith(r + os.sep) else 1)' \
        "$p" "$root"
}

# ---------------------------------------------------------------- helpers

# npm global install of the resolved version: audited first, scripts off, then the installed version (and the
# integrity, where npm writes a lockfile) checked against the registry answer.
# npm_global <tool id> <package> <command> [undo id]. 0 = installed or moved now; 1 = nothing changed
# (present, kept offline, a copy not from npm, audit findings, failure: the reason is printed).
npm_global() {
    local tool=$1 pkg=$2 bin=$3 id=${4:-$1} have prefix got
    resolve_tool "$tool" || return 1
    have=$(tool_version "$bin")
    if [ -n "$have" ] && ! npm_owns "$bin"; then
        info "$bin $have is not from npm ($(command -v "$bin")): left as it is (newest stable: $R_VERSION)"; return 1
    fi
    if r_keep "$have"; then ver_eq "$have" "$R_VERSION" && info "$bin $have present (newest stable)"; return 1; fi
    if [ "$AI_DRY_RUN" != 1 ]; then
        got=$(npm view "$pkg@$R_VERSION" dist.integrity 2>/dev/null || true)
        if [ "$got" != "$R_INTEGRITY" ]; then
            warn "$pkg@$R_VERSION: npm sees integrity ${got:-none}, the registry answer was $R_INTEGRITY: not installed"
            return 1
        fi
    fi
    audit_ok npm "$pkg" "$R_VERSION" || { [ -z "$have" ] || warn "$bin $have kept"; return 1; }
    prefix=$(npm prefix -g 2>/dev/null || echo /usr)
    if [ -w "$prefix/lib" ] || [ -w "$prefix" ]; then
        run npm install -g --ignore-scripts "$pkg@$R_VERSION" || { warn "npm install -g $pkg@$R_VERSION failed"; return 1; }
    elif [ "$AI_MODE" = user ]; then
        manual "needs admin: npm install -g --ignore-scripts $pkg@$R_VERSION ($(admin_cmd))"; return 1
    else
        run_root npm install -g --ignore-scripts "$pkg@$R_VERSION" || { warn "npm install -g $pkg@$R_VERSION failed"; return 1; }
    fi
    if [ "$AI_DRY_RUN" != 1 ]; then
        resolver verify-npm "$(dirname "$(npm root -g)")" "$pkg" "$R_VERSION" "$R_INTEGRITY" >/dev/null \
            || { warn "$pkg after install is not $R_VERSION with the registry integrity: check it"; return 1; }
    fi
    aiconf record-cmd "npm:$id" -- $SUDO_UNDO npm rm -g "$pkg"
    r_record
    ok "$bin ${have:+$have -> }$R_VERSION (newest stable, $(aud_word), scripts off)"
    return 0
}

# npm install of the resolved version into a private prefix (no global install, no runtime npx): audited,
# scripts off, then version and lockfile integrity checked. Prints nothing on success.
npm_local() {
    # npm_local <pkg> <version> <integrity> <prefix dir> [as-user]
    local pkg=$1 ver=$2 want=$3 dir=$4 user=${5:-} got
    if [ "$AI_DRY_RUN" != 1 ]; then
        got=$(npm view "$pkg@$ver" dist.integrity 2>/dev/null || true)
        if [ -z "$want" ] || [ "$got" != "$want" ]; then
            warn "$pkg@$ver: npm sees integrity ${got:-none}, the registry answer was ${want:-none}: not installed"
            return 1
        fi
    fi
    audit_ok npm "$pkg" "$ver" || return 1
    local cmd="npm install --prefix $(quote "$dir") --ignore-scripts --no-audit --no-fund --save-exact $(quote "$pkg@$ver")"
    if [ -n "$user" ]; then as_hermes "$cmd"; return; fi
    run sh -c "$cmd" || return 1
    [ "$AI_DRY_RUN" = 1 ] && return 0
    resolver verify-npm "$dir" "$pkg" "$ver" "$want" >/dev/null || { warn "$pkg in $dir is not $ver with the registry integrity"; return 1; }
}

# uv tool install of an exact version, as the user (never root), wheels only (--no-build). Files are copied
# (UV_LINK_MODE=copy), never hard-linked to the uv cache; a tool an older install linked is reinstalled.
uv_pinned() {
    # uv_pinned <pypi-name> <version> [python]
    local name=$1 ver=$2 py=${3:-} re=()
    audit_ok pypi "$name" "$ver" || return 1
    uv_tool_linked "$name" && re=(--reinstall)
    [ -n "$py" ] && re+=(-p "$py")
    uv_install_wheels_first "$name==$ver" ${re[@]+"${re[@]}"}
}

# uv_tool <tool id> <pypi name> <command> [python]: install or move a uv tool to the resolved version.
uv_tool() {
    local tool=$1 name=$2 bin=$3 py=${4:-} have
    resolve_tool "$tool" || return 0
    have=$(tool_version "$bin")
    if ! uv_tool_linked "$name" && r_keep "$have"; then
        ver_eq "$have" "$R_VERSION" && info "$bin $have present (newest stable)"; return 0
    fi
    if uv_pinned "$name" "$R_VERSION" "$py"; then
        aiconf record-cmd "uv:$bin" -- uv tool uninstall "$name"
        r_record
        ok "$bin ${have:+$have -> }$R_VERSION (newest stable, $(aud_word), wheels only)"
    else
        warn "$bin $R_VERSION not installed${have:+: $have kept}"
    fi
}

# uv tool install, wheels only. On macOS only: when a pinned dependency has no wheel for this macOS version
# (older Intel Macs: cryptography, yara-python, yara-x ship macOS 13/14+ wheels), retry as a source build of
# the same pinned versions (needs the Command Line Tools; Rust parts need cargo).
uv_install_wheels_first() {
    local spec=$1; shift
    run env UV_LINK_MODE=copy uv tool install --force --no-build "$@" "$spec" && return 0
    [ "$AI_OS" = macos ] || return 1
    info "$spec: no wheel for this macOS, building from source"
    run env UV_LINK_MODE=copy uv tool install --force "$@" "$spec"
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

# bin_foreign <name>: true (and said) when <name> on PATH is not the copy this setup installs in bin_dir
# (brew, another installer): that copy is left alone and not shadowed.
bin_foreign() {
    local p; p=$(command -v "$1" 2>/dev/null) || return 1
    [ "$p" = "$(bin_dir)/$1" ] && return 1
    info "$1 at $p is not installed by this setup: left as it is"
    return 0
}

# download_checked <url> <sha256> <file>: download and compare with the published checksum.
download_checked() {
    curl -fsSL --max-time 300 -o "$3" "$1" || { warn "download of $1 failed"; return 1; }
    sha256_is "$3" "$2" || { warn "$1: sha256 differs from the published checksum: not installed"; return 1; }
}

# Audited plugin source at the resolved tag. Linux: /opt/agent-plugins/<name>, root-owned, read-only.
plugin_src_dir() {
    if [ "$AI_OS" = linux ]; then echo "/opt/agent-plugins/$1"; else echo "$HOME/.local/share/ai/plugins/$1"; fi
}

# src_head <dir>: the commit a plugin source clone is at (read from .git/HEAD: a detached checkout holds the
# sha; git itself refuses a root-owned tree for other users), or nothing.
src_head() {
    local h
    h=$(cat "$1/.git/HEAD" 2>/dev/null || true)
    case "$h" in *[!0-9a-f]*|'') return 0 ;; esac
    [ ${#h} -eq 40 ] && printf '%s\n' "$h"
    return 0
}

# src_swap <new tree> <dest> <state key>: put a new tree at <dest>. The new tree is moved next to <dest> first,
# then the two are swapped by rename, so the source is never missing while the slow copy runs. Linux: root-owned,
# read-only for others (S8: the caller checked the tree has no links).
src_swap() {
    local new=$1 dest=$2 key=$3 tag=".new.$$" old=".old.$$"
    if [ "$AI_OS" = linux ]; then
        run_root mkdir -p "$(dirname "$dest")"
        run_root rm -rf "$dest$tag" "$dest$old"
        run_root mv "$new" "$dest$tag"
        run_root chown -R root:root "$dest$tag"
        run_root chmod -R a+rX,go-w "$dest$tag"
        if [ -e "$dest" ]; then run_root mv "$dest" "$dest$old"; fi
        run_root mv "$dest$tag" "$dest"
        run_root rm -rf "$dest$old"
        aiconf record-cmd "$key" -- $SUDO_UNDO rm -rf "$dest"
    else
        mkdir -p "$(dirname "$dest")"
        rm -rf "$dest$tag" "$dest$old"
        mv "$new" "$dest$tag"
        if [ -e "$dest" ]; then mv "$dest" "$dest$old"; fi
        mv "$dest$tag" "$dest"
        rm -rf "$dest$old"
        aiconf record-cmd "$key" -- rm -rf "$dest"
    fi
}

# src_sha_for <name>: the commit the plugin source clone is at; in a dry run the commit it would move to (the
# clone step only printed its plan), so the plugin steps show the real plan.
src_sha_for() {
    if [ "$AI_DRY_RUN" = 1 ]; then
        ( resolve_tool "$1" >/dev/null 2>&1 && printf '%s\n' "$R_SHA" ) || true
    else
        src_head "$(plugin_src_dir "$1")"
    fi
}

plugin_clone() {
    # plugin_clone <name> <tool id>: the source of a plugin at the resolved tag (newest stable, or the HOLD),
    # audited before it replaces an older clone. Each run moves it when a newer tag exists.
    local name=$1 tool=$2 dest tmp have repo
    dest=$(plugin_src_dir "$name")
    have=$(src_head "$dest")
    resolve_tool "$tool" || return 1
    repo=${R_SOURCE#git }
    if [ -n "$have" ] && [ "$have" = "$R_SHA" ]; then
        info "$name source at $dest is at ${R_REF:-commit} ${R_SHA:0:7} (newest stable)"; return 0
    fi
    if [ -n "$have" ] && [ "$R_STATUS" = cached ]; then info "$name source kept at ${have:0:7} (offline)"; return 0; fi
    if [ -e "$dest" ] && [ -z "$have" ]; then
        warn "$dest exists but is not a clone made by this setup: left alone, fix by hand"
        return 1
    fi
    [ "$AI_SKIP_PACKAGES" = 1 ] && { skip "$name source (--skip-packages)"; return 1; }
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone $repo; checkout ${R_REF:-HEAD} (${R_SHA:0:12}); agent-audit dir; ${have:+replace ${have:0:7} in }$dest"
        return 0
    fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-$name.XXXXXX")
    git clone -q "$repo" "$tmp/$name" || { warn "clone of $repo failed"; rm -rf "$tmp"; return 1; }
    git -C "$tmp/$name" -c advice.detachedHead=false checkout -q "$R_SHA" \
        || { warn "$name: commit $R_SHA not found"; rm -rf "$tmp"; return 1; }
    [ "$(git -C "$tmp/$name" rev-parse HEAD)" = "$R_SHA" ] || { warn "$name not at $R_SHA"; rm -rf "$tmp"; return 1; }
    # Accept-list key: the full commit (a tag can move; SPEC 22).
    if ! audit_ok dir "$tmp/$name" "$R_SHA" "$name"; then
        rm -rf "$tmp"; [ -z "$have" ] || warn "$name ${have:0:7} kept"; return 1
    fi
    # S8: a recursive chown/chmod as root must never follow a link out of the tree.
    if [ -n "$(find "$tmp/$name" -type l -print -quit)" ]; then
        warn "$name tree contains symlinks: not installed${have:+, ${have:0:7} kept} (review the upstream tree for links)"
        rm -rf "$tmp"; return 1
    fi
    src_swap "$tmp/$name" "$dest" "plugin-src:$name"
    rm -rf "$tmp"
    r_record
    ok "$name source ${have:+${have:0:7} -> }${R_REF:-${R_SHA:0:7}} (${R_SHA:0:7}) in $dest (audited)"
}

# mattpocock/skills (rules/mattpocock-skills.md step 2): the five picked folders only, at the resolved tag,
# audited. The repo has a symlink (AGENTS.md), so the tree is not moved as a whole: only the five folders,
# checked for links, are copied to <plugin src>/mattpocock-skills/<name>.
MATTPOCOCK_PICKS="productivity/grilling productivity/grill-me productivity/wait-what productivity/writing-for-agents engineering/retro"
# Opt-in per project (owner plan section 9, pocock-skills-audit): copied and audited with the five, but linked only
# into a project that lists them on its `skills:` line in .ai/enabled (ai-adopt makes the project links). Bare
# names: the folder is found under any category except misc/ and in-progress/. A name missing upstream is
# skipped with a warning; it never stops the five. Skipped on purpose: implement, implement-spec, research,
# triage, wayfinder, misc/*, in-progress/*.
MATTPOCOCK_OPTIN_PICKS="grill-with-docs domain-modeling to-spec to-tickets tdd codebase-design code-review pr diagnosing-bugs improve-codebase-architecture"

mattpocock_src() {
    local dest tmp p n have repo
    dest=$(plugin_src_dir mattpocock-skills)
    have=$(cat "$dest/.commit" 2>/dev/null || true)
    resolve_tool mattpocock-skills || return 1
    repo=${R_SOURCE#git }
    # The pick list is part of the marker: a changed list at the same commit copies (and audits) again.
    if [ -n "$have" ] && [ "$have" = "$R_SHA" ] && [ "$(cat "$dest/.picks" 2>/dev/null)" = "$MATTPOCOCK_OPTIN_PICKS" ]; then
        info "mattpocock skills at $dest are at ${R_REF:-commit} ${R_SHA:0:7} (newest stable)"; return 0
    fi
    if [ -n "$have" ] && [ "$R_STATUS" = cached ]; then info "mattpocock skills kept at ${have:0:7} (offline)"; return 0; fi
    [ "$AI_SKIP_PACKAGES" = 1 ] && { skip "mattpocock skills (--skip-packages)"; return 1; }
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone $repo; checkout ${R_REF:-HEAD} (${R_SHA:0:12}); agent-audit dir; copy $MATTPOCOCK_PICKS to $dest"
        return 0
    fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-mattpocock.XXXXXX")
    git clone -q "$repo" "$tmp/src" || { warn "clone of $repo failed"; rm -rf "$tmp"; return 1; }
    git -C "$tmp/src" -c advice.detachedHead=false checkout -q "$R_SHA" \
        || { warn "mattpocock skills: commit not found"; rm -rf "$tmp"; return 1; }
    mkdir -p "$tmp/out"
    for p in $MATTPOCOCK_PICKS; do
        [ -f "$tmp/src/skills/$p/SKILL.md" ] || { warn "mattpocock skills: skills/$p missing at ${R_REF:-$R_SHA}${have:+: ${have:0:7} kept}"; rm -rf "$tmp"; return 1; }
        if [ -n "$(find "$tmp/src/skills/$p" -type l -print -quit)" ]; then
            warn "mattpocock skills: skills/$p contains a symlink: not installed"; rm -rf "$tmp"; return 1
        fi
        cp -R "$tmp/src/skills/$p" "$tmp/out/$(basename "$p")"
    done
    for n in $MATTPOCOCK_OPTIN_PICKS; do
        p=$(cd "$tmp/src/skills" && ls -d -- */"$n" 2>/dev/null | grep -vE '^(misc|in-progress)/' | head -n 1 || true)
        if [ -z "$p" ] || [ ! -f "$tmp/src/skills/$p/SKILL.md" ]; then
            warn "mattpocock opt-in skill $n not found at ${R_REF:-$R_SHA}: skipped (projects that list it get no link)"; continue
        fi
        if [ -n "$(find "$tmp/src/skills/$p" -type l -print -quit)" ]; then
            warn "mattpocock opt-in skill $n contains a symlink: skipped"; continue
        fi
        cp -R "$tmp/src/skills/$p" "$tmp/out/$n"
    done
    printf '%s\n' "$R_SHA" > "$tmp/out/.commit"
    printf '%s\n' "$MATTPOCOCK_OPTIN_PICKS" > "$tmp/out/.picks"
    audit_ok dir "$tmp/out" "$R_SHA" mattpocock-skills || { rm -rf "$tmp"; return 1; }
    src_swap "$tmp/out" "$dest" "plugin-src:mattpocock-skills"
    rm -rf "$tmp"
    r_record
    ok "mattpocock skills ($MATTPOCOCK_PICKS; opt-in: $MATTPOCOCK_OPTIN_PICKS) ${have:+${have:0:7} -> }${R_REF:-${R_SHA:0:7}} in $dest (audited)"
}

# pstack verification skills (SPEC 26, ai/rules/verification-skill.md): create-verification-skill and
# maintain-verification-skill from github.com/cursor/plugins (folder pstack/, MIT). The repo ships an adapted copy in
# ai/skills/ (linked like every own skill) made from the vendor copy at a known commit. When the newest commit
# upstream differs, this copies the two folders, audits them, applies the same transform (ai/lib/pstack_adapt.py)
# into <plugin src>/pstack-verification, and pstack_link points the skill links there. The vendor copy is then
# behind: the run says so (review the diff, refresh ai/rules/vendor/pstack-verification and ai/skills).
PSTACK_SKILLS="create-verification-skill maintain-verification-skill"

pstack_vendor_commit() {
    sed -n 's/^commit: //p' "$AI_HOME/ai/rules/vendor/pstack-verification/SOURCE.md" 2>/dev/null
}

pstack_src() {
    local dest tmp n have repo vend
    dest=$(plugin_src_dir pstack-verification)
    have=$(cat "$dest/.commit" 2>/dev/null || true)
    vend=$(pstack_vendor_commit)
    resolve_tool pstack || return 1
    repo=${R_SOURCE#git }
    if [ "$R_SHA" = "$vend" ]; then
        info "pstack verification skills: the repo copy (ai/skills, commit ${vend:0:7}) is the newest"; return 0
    fi
    if [ -n "$have" ] && [ "$have" = "$R_SHA" ]; then
        info "pstack verification skills at $dest are at ${R_SHA:0:7} (newest; repo copy at ${vend:0:7})"; return 0
    fi
    if [ "$R_STATUS" = cached ]; then info "pstack verification skills: newest not checked (offline), kept"; return 0; fi
    [ "$AI_SKIP_PACKAGES" = 1 ] && { skip "pstack verification skills (--skip-packages)"; return 1; }
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] git clone $repo; checkout ${R_SHA:0:12}; adapt $PSTACK_SKILLS; agent-audit dir; copy to $dest"
        return 0
    fi
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-pstack.XXXXXX")
    git clone -q "$repo" "$tmp/src" || { warn "clone of $repo failed"; rm -rf "$tmp"; return 1; }
    git -C "$tmp/src" -c advice.detachedHead=false checkout -q "$R_SHA" \
        || { warn "pstack: commit not found"; rm -rf "$tmp"; return 1; }
    for n in $PSTACK_SKILLS; do
        [ -f "$tmp/src/pstack/skills/$n/SKILL.md" ] || { warn "pstack: skills/$n missing at ${R_SHA:0:7}: repo copy kept"; rm -rf "$tmp"; return 1; }
        if [ -n "$(find "$tmp/src/pstack/skills/$n" -type l -print -quit)" ]; then
            warn "pstack: skills/$n contains a symlink: repo copy kept"; rm -rf "$tmp"; return 1
        fi
    done
    python3 "$AI_HOME/ai/lib/pstack_adapt.py" "$tmp/src/pstack" "$tmp/out" "$R_SHA" >/dev/null \
        || { warn "pstack: adapt failed (upstream layout changed?): repo copy kept"; rm -rf "$tmp"; return 1; }
    printf '%s\n' "$R_SHA" > "$tmp/out/.commit"
    audit_ok dir "$tmp/out" "$R_SHA" pstack || { rm -rf "$tmp"; return 1; }
    src_swap "$tmp/out" "$dest" "plugin-src:pstack-verification"
    rm -rf "$tmp"
    r_record
    warn "pstack verification skills moved upstream: ${vend:0:7} -> ${R_SHA:0:7} (audited, adapted, in $dest). Review the diff, then refresh ai/rules/vendor/pstack-verification and ai/skills (python3 ai/lib/pstack_adapt.py)"
}

# The newer audited copy wins over the repo copy (link_skills links ai/skills first; this runs after it).
pstack_link() {
    local dir=$1 src n
    src=$(plugin_src_dir pstack-verification)
    [ -f "$src/.commit" ] && [ "$(cat "$src/.commit")" != "$(pstack_vendor_commit)" ] || return 0
    for n in $PSTACK_SKILLS; do
        [ -f "$src/$n/SKILL.md" ] || continue
        if [ -d "$dir/$n" ] && [ ! -L "$dir/$n" ]; then warn "$dir/$n is a real folder (not ours): not linked"; continue; fi
        aiconf link "$dir/$n" "$src/$n"
    done
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
        # Codex from another installer (standalone, brew) is left as it is; an npm copy follows the newest stable.
        npm_global codex @openai/codex codex codex || true
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
    npm_global omc oh-my-claude-sisyphus omc omc || true
    has omc || [ "$AI_DRY_RUN" = 1 ] || return 0
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
    OMX_AUTO_UPDATE=0 OMX_NATIVE_AUTO_FETCH=0 npm_global omx oh-my-codex omx omx || true
    has omx || [ "$AI_DRY_RUN" = 1 ] || return 0
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
    npm_global opencode opencode-ai opencode opencode || return 0
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
        ok "opencode $R_VERSION binary linked ($pkg)"
    else
        warn "opencode binary not found at $bin: check the package layout"
    fi
}

# Release binaries (herdr, osv-scanner) are NOT agent-audited: agent-audit cannot scan a closed binary. Each
# download is checked against the sha256 the project publishes (same release, so it proves the download, not
# the build). An independent check runs only where the verifier exists on this machine; otherwise every change
# of version prints "unaudited binary update" (SPEC 23 lists this exception).
#
# binary_provenance <tool> <file> <repo> <tag> <provenance asset url or ->: 0 = verified, 1 = a verifier ran and
# FAILED (do not install), 2 = no independent check possible here (said so by the caller).
binary_provenance() {
    local tool=$1 file=$2 repo=$3 tag=$4 prov=$5 tmp rc
    # SLSA provenance (osv-scanner publishes multiple.intoto.jsonl): slsa-verifier checks the build came from
    # that repo and tag.
    if [ "$prov" != - ] && has slsa-verifier; then
        tmp=$(mktemp "${TMPDIR:-/tmp}/ai-prov.XXXXXX")
        if ! curl -fsSL --max-time 120 -o "$tmp" "$prov"; then rm -f "$tmp"; return 2; fi
        slsa-verifier verify-artifact "$file" --provenance-path "$tmp" --source-uri "github.com/$repo" --source-tag "$tag" \
            >/dev/null 2>&1; rc=$?
        rm -f "$tmp"
        [ $rc = 0 ] && { info "$tool $tag: SLSA provenance verified (slsa-verifier)"; return 0; }
        warn "$tool $tag: slsa-verifier rejected the binary against its SLSA provenance"; return 1
    fi
    # GitHub artifact attestation (herdr publishes them): only when the API lists one for this digest, and only
    # with an authenticated gh, which does the signature check.
    if has gh && gh auth status >/dev/null 2>&1; then
        local digest; digest=$( (sha256sum "$file" 2>/dev/null || shasum -a 256 "$file") | cut -d' ' -f1)
        if curl -fsS --max-time 20 -o /dev/null "https://api.github.com/repos/$repo/attestations/sha256:$digest" 2>/dev/null; then
            if gh attestation verify "$file" --repo "$repo" >/dev/null 2>&1; then
                info "$tool $tag: GitHub artifact attestation verified (gh attestation verify)"; return 0
            fi
            warn "$tool $tag: gh attestation verify rejected the binary"; return 1
        fi
    fi
    return 2
}

# herdr: the release binary from GitHub, checked against the sha256 herdr publishes in its own release manifest
# (HERDR_CHECKSUMS; the GitHub release has no checksum file). Its installer script is not used.
tools_herdr() {
    local have os arch asset want tmp hb
    resolve_tool herdr || return 0
    bin_foreign herdr && return 0
    have=$(tool_version herdr)
    if r_keep "$have"; then ver_eq "$have" "$R_VERSION" && info "herdr $have present (newest stable)"; return 0; fi
    case "$AI_OS" in linux) os=linux ;; macos) os=macos ;; esac
    case "$AI_ARCH" in x86_64|amd64) arch=x86_64 ;; arm64|aarch64) arch=aarch64 ;; *) warn "herdr: no build for $AI_ARCH"; return 0 ;; esac
    asset="herdr-$os-$arch"
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] download $asset of herdr $R_REF, check the published sha256 ($(has gh && echo 'and the GitHub attestation when gh is logged in' || echo 'no gh: unaudited binary update')), install to $(bin_dir)/herdr"
        return 0
    fi
    want=$(resolver checksum herdr "$R_VERSION" "$asset" --target "$os-$arch" 2>/dev/null) \
        || { warn "herdr $R_VERSION: no published checksum for $asset: not installed${have:+, $have kept}"; return 0; }
    tmp=$(mktemp "${TMPDIR:-/tmp}/ai-herdr.XXXXXX")
    download_checked "https://github.com/${R_SOURCE#github }/releases/download/$R_REF/$asset" "$want" "$tmp" \
        || { rm -f "$tmp"; return 0; }
    local prc=0
    binary_provenance herdr "$tmp" "${R_SOURCE#github }" "$R_REF" - || prc=$?
    [ $prc = 1 ] && { rm -f "$tmp"; [ -z "$have" ] || warn "herdr $have kept"; return 0; }
    [ $prc = 2 ] && warn "unaudited binary update: herdr ${have:-none} -> $R_VERSION (sha256 from the herdr release manifest only; no gh attestation check on this machine)"
    install_bin "$tmp" herdr; rm -f "$tmp"
    aiconf record-cmd bin:herdr -- $SUDO_UNDO rm -f "$(bin_dir)/herdr"
    hb="$(bin_dir)/herdr"
    if [ "$("$hb" --version 2>/dev/null | awk 'match($0, /[0-9]+\.[0-9]+(\.[0-9]+)*/) { print substr($0, RSTART, RLENGTH); exit }')" != "$R_VERSION" ]; then
        warn "herdr installed reports $("$hb" --version 2>/dev/null | head -n1), resolved was $R_VERSION: check before use"
    else
        r_record
        ok "herdr ${have:+$have -> }$R_VERSION (release binary, not agent-audited; published sha256 checked, version verified)"
    fi
}

# ---------------------------------------------------------------- tools (step 6)

# User tools: installed as the user, never root (uv tools, per-user npm prefix).
tools_user() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "user tool installs (--skip-packages)"; return 0; fi

    uv_tool serena serena-agent serena "$SERENA_PYTHON"
    uv_tool graphify graphifyy graphify
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
    plugin_clone ponytail ponytail || true
    plugin_clone i-have-adhd i-have-adhd || true
    # Readable skill files of the Claude-only packs for agents that cannot hand off to Claude (Codex,
    # Hermes, opencode without a Claude login): the router points them here (claude_handoff).
    plugin_clone claude-seo claude-seo || true
    plugin_clone claude-blog claude-blog || true
    mattpocock_src || true
    pstack_src || true
    return 0
}

# Audit scanners for agent-audit (guarddog, skill-scanner, osv-scanner). Every other install is audited with
# them, so they come first. Newest stable like every tool (owner decision 2026-11-14), wheels only. A new
# guarddog or skill-scanner is audited (agent-audit pypi) by the scanners already installed before it replaces
# them; only the very first bootstrap (no guarddog yet: nothing can audit) installs unaudited, with a warning.
# osv-scanner is a binary: see binary_provenance.
# Linux: system-wide (/opt/uv-tools, links in /usr/local/bin, root-owned). macOS: the user's uv tools and ~/.local/bin.
tools_scanners() {
    if [ "$AI_SKIP_PACKAGES" = 1 ]; then skip "audit scanners (--skip-packages)"; return 0; fi
    scanners_drop
    local triple tool name bin have aud gd_ready=0 mp=()
    for triple in "guarddog:guarddog:guarddog" "skill-scanner:cisco-ai-skill-scanner:skill-scanner"; do
        tool=${triple%%:*}; name=${triple#*:}; name=${name%%:*}; bin=${triple##*:}
        profile_has_scanner "$tool" || continue
        # skill-scanner 2.1+ ships macOS 13+ binaries only; older macOS gets the last pure-Python release.
        if [ "$tool" = skill-scanner ] && [ "$AI_OS" = macos ] \
            && [ "$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)" -lt 13 ] 2>/dev/null; then
            R_TOOL=$tool; R_VERSION=$SKILL_SCANNER_MACOS_LEGACY_VERSION; R_SHA=""; R_INTEGRITY=""; R_STATUS=hold
            info "skill-scanner: macOS < 13 takes $R_VERSION (SKILL_SCANNER_MACOS_LEGACY_VERSION)"
        else
            resolve_tool "$tool" || continue
        fi
        have=$(tool_version "$bin")
        if r_keep "$have"; then ver_eq "$have" "$R_VERSION" && info "$bin $have present (newest stable)"; continue; fi
        aud=", audited"
        if [ "${PROFILE_PACKAGE_AUDIT:-1}" = 0 ]; then
            # Profile dev-mac: skill-scanner is the only scanner and nothing audits packages; uv's own Python.
            mp=(--managed-python)
            if [ -z "$have" ]; then
                aud=", first install not audited (profile $AI_PROFILE)"
                info "$bin $R_VERSION: first install, not audited (profile $AI_PROFILE audits no packages)"
            else
                audit_ok pypi "$name" "$R_VERSION"; aud=", audit skipped (profile $AI_PROFILE)"
            fi
        elif has guarddog || [ $gd_ready = 1 ]; then      # (gd_ready: a dry run only planned the guarddog install)
            audit_ok pypi "$name" "$R_VERSION" || { warn "$bin $R_VERSION not installed${have:+: $have kept}"; continue; }
        else
            aud=", NOT audited (bootstrap)"
            warn "bootstrap: $bin $R_VERSION installed WITHOUT audit (no guarddog on this machine yet to audit it)"
        fi
        if [ "$AI_OS" = linux ]; then
            run_root env UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin UV_LINK_MODE=copy \
                uv tool install --force --no-build -p "$SCANNER_PYTHON" "$name==$R_VERSION" \
                || { warn "$bin $R_VERSION install failed${have:+: $have kept}"; continue; }
            aiconf record-cmd "uv-root:$bin" -- $SUDO_UNDO env UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin uv tool uninstall "$name"
        else
            uv_install_wheels_first "$name==$R_VERSION" ${mp[@]+"${mp[@]}"} -p "$SCANNER_PYTHON" \
                || { warn "$bin $R_VERSION install failed${have:+: $have kept}"; continue; }
            aiconf record-cmd "uv:$bin" -- uv tool uninstall "$name"
        fi
        r_record
        [ "$tool" = guarddog ] && gd_ready=1
        ok "$bin ${have:+$have -> }$R_VERSION (newest stable, wheels only$aud)"
    done
    profile_has_scanner osv-scanner && tools_osv_scanner
    return 0
}

# Scanners the profile does not use (dev-mac: guarddog, osv-scanner) are removed when this setup installed them:
# the recorded undo, else a copy that resolved.json says this setup installed (uv tool, binary in bin_dir).
scanners_drop() {
    local s gone=""
    profile_has_scanner guarddog && profile_has_scanner osv-scanner && return 0      # server: all scanners
    for s in guarddog osv-scanner; do
        profile_has_scanner "$s" && continue
        if [ "$s" = guarddog ]; then
            if state_has cmd:uv:guarddog || state_has cmd:uv-root:guarddog; then
                aiconf undo --only '^cmd:uv(-root)?:guarddog$'; gone="$gone guarddog"
            elif r_installed guarddog && uv tool list 2>/dev/null | grep -q '^guarddog '; then
                run uv tool uninstall guarddog; gone="$gone guarddog"
            fi
        elif state_has cmd:bin:osv-scanner; then
            aiconf undo --only '^cmd:bin:osv-scanner$'; gone="$gone osv-scanner"
        elif r_installed osv-scanner && [ -e "$(bin_dir)/osv-scanner" ]; then
            run rm -f "$(bin_dir)/osv-scanner"; gone="$gone osv-scanner"
        fi
    done
    if [ -n "$gone" ]; then ok "scanners not used by profile $AI_PROFILE removed:$gone"
    else info "scanners not used by profile $AI_PROFILE (guarddog, osv-scanner): none installed by this setup"; fi
}

# r_installed <tool id>: true when resolved.json says this setup installed that tool.
r_installed() {
    python3 - "$AI_STATE_DIR/resolved.json" "$1" <<'EOS'
import json, sys
try:
    t = (json.load(open(sys.argv[1])).get("tools") or {}).get(sys.argv[2]) or {}
except (OSError, ValueError):
    t = {}
sys.exit(0 if (t.get("installed") or {}).get("version") else 1)
EOS
}

tools_osv_scanner() {
    local have os arch asset want tmp
    resolve_tool osv-scanner || return 0
    bin_foreign osv-scanner && return 0
    have=$(tool_version osv-scanner)
    if r_keep "$have"; then ver_eq "$have" "$R_VERSION" && info "osv-scanner $have present (newest stable)"; return 0; fi
    case "$AI_OS" in linux) os=linux ;; macos) os=darwin ;; esac
    case "$AI_ARCH" in x86_64|amd64) arch=amd64 ;; arm64|aarch64) arch=arm64 ;; *) warn "osv-scanner: no build for $AI_ARCH"; return 0 ;; esac
    asset="osv-scanner_${os}_${arch}"
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] download $asset of osv-scanner $R_REF, check it against the release's SHA256SUMS ($(has slsa-verifier && echo 'and SLSA provenance' || echo 'no slsa-verifier: unaudited binary update')), install"; return 0; fi
    want=$(resolver checksum osv-scanner "$R_VERSION" "$asset" 2>/dev/null) \
        || { warn "osv-scanner $R_VERSION: no published checksum for $asset: not installed${have:+, $have kept}"; return 0; }
    tmp=$(mktemp "${TMPDIR:-/tmp}/osv.XXXXXX")
    download_checked "https://github.com/${R_SOURCE#github }/releases/download/$R_REF/$asset" "$want" "$tmp" \
        || { rm -f "$tmp"; return 0; }
    local prc=0 prov=-
    prov="https://github.com/${R_SOURCE#github }/releases/download/$R_REF/multiple.intoto.jsonl"
    binary_provenance osv-scanner "$tmp" "${R_SOURCE#github }" "$R_REF" "$prov" || prc=$?
    [ $prc = 1 ] && { rm -f "$tmp"; [ -z "$have" ] || warn "osv-scanner $have kept"; return 0; }
    [ $prc = 2 ] && warn "unaudited binary update: osv-scanner ${have:-none} -> $R_VERSION (sha256 from the same release only; slsa-verifier not installed)"
    install_bin "$tmp" osv-scanner; rm -f "$tmp"
    aiconf record-cmd bin:osv-scanner -- $SUDO_UNDO rm -f "$(bin_dir)/osv-scanner"
    r_record
    ok "osv-scanner ${have:+$have -> }$R_VERSION (release binary, not agent-audited; published sha256 checked)"
}

# context7 MCP: one install per user and version (~/.local/share/ai/npm/context7-mcp-<version>), run by
# mcp/context7.sh, which starts the highest installed version (no runtime npx, B3). A newer release is installed
# next to the old one, then the old folders go.
AI_NPM_DIR="$HOME/.local/share/ai/npm"
tools_context7() {
    local have dir d
    resolve_tool context7-mcp || return 0
    have=$(npm_dir_version "$AI_NPM_DIR" context7-mcp)
    [ -n "$have" ] && [ ! -x "$AI_NPM_DIR/context7-mcp-$have/node_modules/.bin/context7-mcp" ] && have=""
    if r_keep "$have"; then ver_eq "$have" "$R_VERSION" && info "context7-mcp $have present (newest stable)"; return 0; fi
    dir="$AI_NPM_DIR/context7-mcp-$R_VERSION"
    npm_local @upstash/context7-mcp "$R_VERSION" "$R_INTEGRITY" "$dir" || { [ -z "$have" ] || warn "context7-mcp $have kept"; return 0; }
    aiconf record-cmd "npm-local:context7" -- sh -c 'rm -rf "$1"/context7-mcp-*' _ "$AI_NPM_DIR"
    if [ "$AI_DRY_RUN" != 1 ]; then
        for d in "$AI_NPM_DIR"/context7-mcp-*; do
            [ -d "$d" ] && [ "$d" != "$dir" ] && rm -rf "$d"
        done
    fi
    r_record
    ok "context7-mcp ${have:+$have -> }$R_VERSION in $dir ($(aud_word), integrity checked, scripts off)"
}

# RTK: newest stable release (owner decisions 2026-11-12 and 2026-11-14: no cooldown, no pin), resolved from
# its GitHub releases (no pre-release, no draft, plain vX.Y.Z). Always built from source (prebuilt x86_64
# binaries need AVX2, contracts-mcp-a 4.6), so every OS and arch gets the same path, and the source tree is
# audited before the build. Offline: the installed rtk stays. The tag and commit go to the audit log.
tools_rtk() {
    local tag ver have bb
    resolve_tool rtk || return 0
    if bb=$(rtk_brew_bin); then
        tools_rtk_brew "$bb" && return 0     # 1 = build from source instead (RTK_BREW_MISMATCH=build)
    fi
    tag=$R_REF; ver=$R_VERSION
    have=$(tool_version rtk)
    # The build stamp says how the installed binary was built; a changed build mode (cargo update on/off) rebuilds.
    local stamp="$AI_STATE_DIR/rtk.build" want_stamp="$tag cargo-update=${RTK_CARGO_UPDATE:-0}"
    if ver_eq "$have" "$ver" && [ "$(cat "$stamp" 2>/dev/null)" = "$want_stamp" ]; then
        info "rtk $ver present (newest stable)"; return 0
    fi
    if [ -n "$have" ] && [ "$R_STATUS" = cached ]; then info "rtk $have kept (offline: not rebuilt)"; return 0; fi
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
        info "[dry-run] git clone --depth 1 --branch $tag https://github.com/${R_SOURCE#github } $src; check commit ${R_SHA:0:12}; agent-audit dir; cargo build --release --locked; install"
        return 0
    fi
    # Build as the user (system mode: the target user), never as root; only the install is root.
    as_target rm -rf "$src"; as_target mkdir -p "$(dirname "$src")"
    as_target git clone -q --depth 1 --branch "$tag" "https://github.com/${R_SOURCE#github }" "$src" || { warn "rtk clone failed"; return 0; }
    local rtkhead
    if [ "$AI_MODE" = system ]; then rtkhead=$(sudo -u "$AI_FOR_USER" git -C "$src" rev-parse HEAD)
    else rtkhead=$(git -C "$src" rev-parse HEAD); fi
    # The clone must be the commit the resolver saw for this tag (a tag moved between the two is not built).
    if [ -n "$R_SHA" ] && [ "$rtkhead" != "$R_SHA" ]; then
        warn "rtk tag $tag points to $rtkhead now, the resolver saw $R_SHA: not built (tag moved, run again)"
        return 0
    fi
    # Owner decision 2026-11-12: patch the lockfile before the audit, so known CVEs that a semver-compatible
    # update fixes are gone (rustls, webpki, rustix ...). Breaking updates (quick-xml 0.37->0.41, libsqlite3-sys)
    # need upstream: those stay, and the accept list names them for this exact tag.
    if [ "${RTK_CARGO_UPDATE:-0}" = 1 ]; then
        as_target sh -c "cd '$src' && cargo update -q" || { warn "rtk cargo update failed"; return 0; }
    fi
    audit_ok dir "$src" "$rtkhead" rtk || { [ -z "$have" ] || warn "rtk $have kept"; return 0; }
    as_target sh -c "cd '$src' && cargo build --release --locked" || { warn "rtk build failed"; return 0; }
    install_bin "$src/target/release/rtk" rtk
    aiconf record-cmd bin:rtk -- $SUDO_UNDO rm -f "$(bin_dir)/rtk"
    mkdir -p "$AI_STATE_DIR"
    printf '%s rtk %s %s built (newest stable)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$rtkhead $want_stamp" >> "$AI_STATE_DIR/audit.log"
    printf '%s\n' "$want_stamp" > "$stamp"
    r_record "$rtkhead"
    ok "rtk ${have:+$have -> }$ver built from source ($tag, $rtkhead)"
}

# RTK from Homebrew (owner decision 2026-11-14, macOS): when the homebrew-core formula rtk (same project,
# rtk-ai/rtk) is installed, it is the one rtk. It moves only to the version this run resolved and audited
# (newest stable, or RTK_HOLD): the formula's stable version in the local tap (`brew info --json=v2 rtk`) must
# be exactly that version, from homebrew/core; then the source tree of that release tag is audited
# (agent-audit dir, the same accept-list key as the source build) and `brew upgrade rtk` runs without brew's
# auto-update, so it installs the version that was checked. Any mismatch: a WARN and the installed rtk stays
# (RTK_BREW_MISMATCH=build in ai/pins.env: the source build of the audited tag instead). No formula: source build.
rtk_brew_bin() {
    [ "$AI_OS" = macos ] && has brew || return 1
    local b real
    b="$(brew --prefix 2>/dev/null)/bin/rtk"
    [ -x "$b" ] || return 1
    real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$b")
    case "$real" in */Cellar/rtk/*) printf '%s\n' "$b" ;; *) return 1 ;; esac
}

bin_version() {
    "$1" --version 2>/dev/null | awk 'match($0, /[0-9]+\.[0-9]+(\.[0-9]+)*/) { print substr($0, RSTART, RLENGTH); exit }' || true
}

# rtk_brew_formula: "<tap> <stable version>" of the rtk formula in the local Homebrew taps, or nothing.
rtk_brew_formula() {
    brew info --json=v2 rtk 2>/dev/null | python3 -c 'import json,sys
try:
    f = json.load(sys.stdin)["formulae"][0]
    print("%s %s" % (f.get("tap") or "-", (f.get("versions") or {}).get("stable") or "-"))
except Exception:
    pass' || true
}

# tools_rtk_brew <brew rtk>: 0 = done (moved, present or kept with a warning); 1 = build from source instead.
tools_rtk_brew() {
    local b=$1 have new formula tap stable
    have=$(bin_version "$b")
    if ver_eq "$have" "$R_VERSION"; then
        rtk_drop_own_copy "$b"
        if [ "$R_STATUS" = hold ]; then info "rtk $have present (Homebrew formula, held version)"
        else info "rtk $have present (Homebrew formula, newest stable)"; fi
        return 0
    fi
    if [ -n "$have" ] && [ "$R_STATUS" = cached ]; then info "rtk $have kept (Homebrew; offline: not moved to $R_VERSION)"; return 0; fi
    formula=$(rtk_brew_formula); tap=${formula%% *}; stable=${formula##* }
    if [ "$tap" != homebrew/core ] || ! ver_eq "$stable" "$R_VERSION"; then
        if [ "${RTK_BREW_MISMATCH:-skip}" = build ]; then
            warn "rtk: Homebrew formula is ${tap:-unknown} ${stable:-unknown}, the audited version is $R_VERSION: source build instead (RTK_BREW_MISMATCH=build); the Homebrew rtk stays on PATH too"
            return 1
        fi
        warn "rtk: Homebrew formula is ${tap:-unknown} ${stable:-unknown}, the audited version is $R_VERSION${R_NOTE:+ ($R_NOTE)}: brew upgrade rtk not run${have:+, $have kept} (brew update, or RTK_BREW_MISMATCH=build)"
        rtk_drop_own_copy "$b"
        return 0
    fi
    rtk_drop_own_copy "$b"
    git_source_audited rtk "https://github.com/${R_SOURCE#github }" "$R_REF" "$R_SHA" \
        || { warn "rtk $R_VERSION: audit findings: brew upgrade rtk not run${have:+, $have kept}"; return 0; }
    run env HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade rtk || { warn "brew upgrade rtk failed${have:+: $have kept}"; return 0; }
    if [ "$AI_DRY_RUN" = 1 ]; then ok "rtk ${have:+$have -> }$R_VERSION via brew upgrade rtk (Homebrew formula $tap $stable)"; return 0; fi
    new=$(bin_version "$b")
    if ver_eq "$new" "$R_VERSION"; then
        mkdir -p "$AI_STATE_DIR"
        printf '%s rtk brew-upgrade %s -> %s (homebrew/core; tag %s (%s) audited)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            "${have:-none}" "$new" "$R_REF" "$R_SHA" >> "$AI_STATE_DIR/audit.log"
        r_record
        ok "rtk ${have:+$have -> }$new (brew upgrade rtk; tag $R_REF ($R_SHA) audited)"
    else
        warn "brew upgrade rtk gave ${new:-nothing}, the audited version is $R_VERSION: check it (rtk --version)"
    fi
}

# rtk_drop_own_copy <brew rtk>: a copy this setup built earlier in ~/.local/bin would shadow (or be shadowed by)
# the Homebrew one, and its version check never matches. Ours (recorded build) is moved to the backup folder,
# with a restore record keyed as a tool (cmd:bin:, undone with the tools); one that is not ours is only reported.
rtk_drop_own_copy() {
    local own backup
    own="$(bin_dir)/rtk"
    [ -e "$own" ] || return 0
    if state_has cmd:bin:rtk || [ -f "$AI_STATE_DIR/rtk.build" ]; then
        backup="$AI_STATE_DIR/backup/rtk.$(date +%Y%m%d-%H%M%S)"
        run mkdir -p "$AI_STATE_DIR/backup"
        run mv "$own" "$backup"
        run rm -f "$AI_STATE_DIR/rtk.build"
        aiconf record-cmd "bin:rtk-own-copy-removed" -- sh -c '[ -e "$2" ] || mv "$1" "$2"' _ "$backup" "$own"
        ok "rtk: the copy this setup built ($own) moved to $backup; the Homebrew rtk ($1) is the only one on PATH"
    else
        warn "two rtk on PATH: $own (not from this setup) and $1 (Homebrew): remove one by hand"
    fi
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
    local a
    if [ "$AI_OS" = linux ]; then
        for a in opencode herdr; do want "$a" || printf '%s\n' "$a"; done
    elif [ "${PROFILE_OPENCODE:-1}" = 0 ]; then
        printf 'opencode\n'       # profile dev-mac (owner decision 2026-11-14)
    fi
}
agents_drop_user() {
    local a keys
    for a in $(agents_dropped); do
        keys=AGENT_USER_KEYS_$a
        aiconf undo --only "${!keys}"
        # macOS: the npm install was recorded in the user state too (no system part there).
        if [ "$AI_OS" = macos ]; then keys=AGENT_SYSTEM_KEYS_$a; aiconf undo --only "${!keys}"; fi
    done
    [ -z "$(agents_dropped)" ] || [ "$AI_OS" != linux ] || ok "agents not used on this server, their user config undone: $(agents_dropped | tr '\n' ' ')"
    [ -z "$(agents_dropped)" ] || [ "$AI_OS" = linux ] || ok "agents not used by profile $AI_PROFILE, undone: $(agents_dropped | tr '\n' ' ')"
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
