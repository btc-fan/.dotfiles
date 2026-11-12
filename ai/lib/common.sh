# ai/lib/common.sh: shared helpers for install.sh, uninstall.sh and ai/adapters/*.sh.
# bash 3.2 compatible (macOS /bin/bash): no associative arrays, no mapfile, no ${x,,}.
# Every command that changes the machine goes through run / run_root / as_hermes so that
# --dry-run prints it instead.

# AI_MODE: all = one process does everything (macOS, or a Linux user with sudo);
#          system = admin, as root, for --for-user <user> (root steps only, then the user part);
#          user = the target user, never calls sudo.
AI_MODE=${AI_MODE:-all}
AI_FOR_USER=${AI_FOR_USER:-}
AI_DRY_RUN=${AI_DRY_RUN:-0}
AI_YES=${AI_YES:-0}
AI_STATE_DIR="$HOME/.local/state/ai"
AI_STATE_FILE="$AI_STATE_DIR/managed-keys.json"
AI_SYSTEM_STATE_FILE=/var/lib/ai/managed-keys.json
HERMES_USER=${HERMES_USER:-hermes}
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ in the repo or caches from dry runs

STEP_N=0
STEP_TOTAL=0
DONE_LIST=()
SKIP_LIST=()
MANUAL_LIST=()
WARN_LIST=()

# ---------------------------------------------------------------- output

say()    { printf '%s\n' "$*"; }
info()   { printf '  %s\n' "$*"; }
step()   { STEP_N=$((STEP_N + 1)); printf '\n[%d/%d] %s\n' "$STEP_N" "$STEP_TOTAL" "$*"; }
ok() {
    if [ "$AI_DRY_RUN" = 1 ]; then DONE_LIST+=("(planned) $*"); printf '  planned: %s\n' "$*"
    else DONE_LIST+=("$*"); printf '  done: %s\n' "$*"; fi
}
skip()   { SKIP_LIST+=("$*"); printf '  skip: %s\n' "$*"; }
manual() { MANUAL_LIST+=("$*"); printf '  manual: %s\n' "$*"; }
warn()   { WARN_LIST+=("$*"); printf '  WARN: %s\n' "$*" >&2; }
die()    { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Print a list safely under `set -u` in bash 3.2 (empty arrays are "unbound" there).
print_list() {
    local title=$1; shift
    [ $# -eq 0 ] && return 0
    printf '\n%s (%d)\n' "$title" "$#"
    local x
    for x in "$@"; do printf '  - %s\n' "$x"; done
}

summary() {
    printf '\n==== summary ====\n'
    print_list "done" ${DONE_LIST[@]+"${DONE_LIST[@]}"}
    print_list "skipped" ${SKIP_LIST[@]+"${SKIP_LIST[@]}"}
    print_list "warnings" ${WARN_LIST[@]+"${WARN_LIST[@]}"}
    print_list "manual steps left" ${MANUAL_LIST[@]+"${MANUAL_LIST[@]}"}
    [ "$AI_DRY_RUN" = 1 ] && printf '\n(dry run: nothing was changed)\n'
    return 0
}

# ---------------------------------------------------------------- running commands

quote() { local a out=""; for a in "$@"; do out="$out $(printf '%q' "$a")"; done; printf '%s' "${out# }"; }

# Hide secret values in printed commands (K=V with a secret-like K, and token shapes).
redact() {
    sed -E 's/(([A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PAT)[A-Za-z0-9_]*)=)[^ ]+/\1***/g;
            s/(ctx7sk-|ghp_|gho_|github_pat_|sk-ant-)[A-Za-z0-9_-]+/\1***/g'
}

run() {
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] $(quote "$@" | redact)"
        return 0
    fi
    "$@"
}

is_root() { [ "$(id -u)" -eq 0 ]; }

run_root() {
    if [ "$AI_MODE" = user ]; then manual "needs admin: $(quote "$@" | redact)"; return 0; fi
    if is_root; then run "$@"; else run sudo "$@"; fi
}

# The one command admin runs for this user (printed when a root piece is missing in --user mode).
AI_ROOT_REPO=/usr/local/lib/ai/repo
admin_cmd() { printf 'sudo /opt/ai-setup/install.sh --update --for-user %s   (admin)' "${AI_FOR_USER:-$(id -un)}"; }

has() { command -v "$1" >/dev/null 2>&1; }

# The box tool of a server install (ubuntu-server branch): the root socket service or proj-agent itself.
# One agreed path: /usr/local/sbin/proj-agent (a normal user's call hands over to the socket).
AI_PROJ_AGENT=${AI_PROJ_AGENT_PATH:-/usr/local/sbin/proj-agent}
AI_PROJ_AGENT_SOCK=${AI_PROJ_AGENT_SOCK:-/run/proj-agent.sock}
box_present() {
    [ "$AI_OS" = linux ] || return 1
    [ "${AI_PROJ_AGENT_FORCE:-0}" = 1 ] || [ -S "$AI_PROJ_AGENT_SOCK" ] || [ -x "$AI_PROJ_AGENT" ]
}

# Run a command line as the hermes user (login shell for its PATH). Only on Linux.
# Always from hermes' own home: the caller's cwd (admin's home) is closed to hermes, and tools that
# look at the cwd (serena --project-from-cwd in `hermes mcp add` probes) fail there.
hermes_exists() { [ "$AI_OS" = linux ] && getent passwd "$HERMES_USER" >/dev/null 2>&1; }
hermes_home()   { getent passwd "$HERMES_USER" | cut -d: -f6; }
as_hermes()     {
    if [ "$AI_MODE" = user ]; then manual "needs admin (Hermes): $1"; return 0; fi
    ( cd / && run sudo -u "$HERMES_USER" -H bash -lc "cd ~ && $1" )
}
as_hermes_ro()  { ( cd / && sudo -n -u "$HERMES_USER" -H bash -lc "cd ~ && $1" 2>/dev/null ); }

confirm() {
    # confirm "question" [default y|n]
    local q=$1 def=${2:-n} ans
    [ "$AI_YES" = 1 ] && return 0
    if [ ! -t 0 ]; then [ "$def" = y ]; return; fi
    printf '%s [%s] ' "$q" "$( [ "$def" = y ] && echo Y/n || echo y/N )"
    read -r ans || ans=""
    ans=${ans:-$def}
    case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# ---------------------------------------------------------------- merge engine wrappers

aiconf() {
    local dry=""
    [ "$AI_DRY_RUN" = 1 ] && dry="--dry-run"
    python3 "$AI_HOME/ai/lib/aiconf.py" --state "$AI_STATE_FILE" $dry "$@"
}

# System files (Linux, root). Their state lives in /var/lib/ai so the user state stays user-owned.
# sudo runs a root-owned copy of the helper (S7), never the user-writable file in the work tree.
AI_ROOT_HELPER=/usr/local/lib/ai/aiconf.py

aiconf_root() {
    if [ "$AI_MODE" = user ]; then manual "needs admin: aiconf $(quote "$@")"; return 0; fi
    if [ "$AI_DRY_RUN" = 1 ]; then
        python3 "$AI_HOME/ai/lib/aiconf.py" --state "$AI_SYSTEM_STATE_FILE" --dry-run "$@"
        return
    fi
    [ -f "$AI_ROOT_HELPER" ] || die "root helper $AI_ROOT_HELPER missing (sudo_ready was not run)"
    if is_root; then python3 -I "$AI_ROOT_HELPER" --state "$AI_SYSTEM_STATE_FILE" "$@"
    else sudo python3 -I "$AI_ROOT_HELPER" --state "$AI_SYSTEM_STATE_FILE" "$@"; fi
}

# S7: before the first sudo step, the work tree must be exactly the pushed branch (clean, HEAD ==
# origin/ai), so root never runs code that is only on this disk. Override for development:
# --allow-dirty (or AI_ALLOW_DIRTY=1). Then copy the helper to a root-owned place.
# sudo_ready [noninteractive]
sudo_ready() {
    [ "$AI_OS" = linux ] || return 0
    [ "$AI_MODE" = user ] && return 0     # the user part never calls sudo
    [ "$AI_MODE" = system ] && return 0   # system mode prepared by root_prepare
    [ "$AI_DRY_RUN" = 1 ] && { info "[dry-run] repo gate, sudo -v, install $AI_ROOT_HELPER (root:root)"; return 0; }
    local dirty head remote
    dirty=$(git -C "$AI_HOME" status --porcelain 2>/dev/null || echo "not a git work tree")
    head=$(git -C "$AI_HOME" rev-parse HEAD 2>/dev/null || echo none)
    remote=$(git -C "$AI_HOME" rev-parse origin/ai 2>/dev/null || echo none)
    if [ -n "$dirty" ] || [ "$head" != "$remote" ]; then
        if [ "${AI_ALLOW_DIRTY:-0}" = 1 ]; then
            warn "work tree is not the pushed origin/ai (dirty or other commit): continuing because of --allow-dirty"
        else
            printf 'ERROR: %s is not exactly origin/ai (uncommitted changes or HEAD %s != origin/ai %s).\n' \
                "$AI_HOME" "${head:0:12}" "${remote:0:12}" >&2
            printf '       Root steps refuse to run code that is not pushed. Commit+push, or re-run with --allow-dirty (development only).\n' >&2
            return 1
        fi
    fi
    if [ "${1:-}" = noninteractive ]; then sudo -n true 2>/dev/null || return 1; else sudo -v; fi
    if ! sudo cmp -s "$AI_HOME/ai/lib/aiconf.py" "$AI_ROOT_HELPER" 2>/dev/null; then
        sudo install -d -o root -g root -m 755 /usr/local/lib/ai
        sudo install -o root -g root -m 755 "$AI_HOME/ai/lib/aiconf.py" "$AI_ROOT_HELPER"
    fi
}

# Files of the hermes user. The owner's home may be closed to hermes, so the helper and any
# content file are first copied into hermes' own ~/.local/share/ai/stage/.
hermes_stage() {
    # hermes_stage <local file> <name>  -> prints the staged path
    local src=$1 name=$2 hh
    hh=$(hermes_home)
    if [ "$AI_DRY_RUN" != 1 ]; then
        sudo -u "$HERMES_USER" -H sh -c "mkdir -p '$hh/.local/share/ai/stage' && cat > '$hh/.local/share/ai/stage/$name'" < "$src"
    fi
    printf '%s/.local/share/ai/stage/%s' "$hh" "$name"
}

aiconf_hermes() {
    local helper dry=""
    helper=$(hermes_stage "$AI_HOME/ai/lib/aiconf.py" aiconf.py)
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] (as $HERMES_USER) aiconf $(quote "$@")"
        return 0
    fi
    # login shell: hermes' own PATH (its `hermes` binary lives in its home); cwd = hermes' home
    ( cd / && sudo -u "$HERMES_USER" -H bash -lc "cd ~ && python3 $(quote "$helper") --state \"\$HOME/.local/state/ai/managed-keys.json\" $(quote "$@")" )
}

# ---------------------------------------------------------------- facts

detect_os() {
    case "$(uname -s)" in
        Darwin)
            AI_OS=macos
            # Non-login shells (ssh, cron, IDE terminals) often lack Homebrew (Apple Silicon /opt/homebrew,
            # Intel /usr/local) and ~/.local/bin (uv tools, our links).
            local d
            for d in "$HOME/.local/bin" /usr/local/bin /opt/homebrew/bin; do
                [ -d "$d" ] || continue
                case ":$PATH:" in *":$d:"*) ;; *) PATH="$d:$PATH" ;; esac
            done
            export PATH
            ;;
        Linux)
            AI_OS=linux
            AI_DISTRO=$(. /etc/os-release 2>/dev/null; printf '%s' "${ID:-unknown}")
            ;;
        *) die "unsupported OS $(uname -s)" ;;
    esac
    AI_ARCH=$(uname -m)
    # Prefix for recorded undo commands of system-wide installs (word-split on purpose).
    SUDO_UNDO=""
    [ "$AI_OS" = linux ] && ! is_root && SUDO_UNDO=sudo
    return 0
}

# ---------------------------------------------------------------- system mode (admin, root)

# Run a command as the target user (system mode) or as yourself (all mode).
as_target() {
    if [ "$AI_MODE" = system ]; then run sudo -u "$AI_FOR_USER" -H "$@"; else run "$@"; fi
}

# S7 for admin installs: check the user's work tree as that user (clean, HEAD == origin/ai unless
# --allow-dirty), then copy it to a root-owned tree that is the only code root runs.
# root_prepare <source work tree>   -> sets AI_HOME to the root-owned copy
root_prepare() {
    # src is the admin-owned clone (root-guard.sh refused anything else); git runs as its owner.
    local src=$1 dirty head remote new owner g
    owner=$(stat -c %U "$src" 2>/dev/null || stat -f %Su "$src")
    if [ "$owner" = root ]; then g="git -C $src"; else g="sudo -u $owner git -C $src"; fi
    dirty=$($g status --porcelain 2>/dev/null || echo "not a git work tree")
    head=$($g rev-parse HEAD 2>/dev/null || echo none)
    remote=$($g rev-parse origin/ai 2>/dev/null || echo none)
    if [ -n "$dirty" ] || [ "$head" != "$remote" ]; then
        if [ "${AI_ALLOW_DIRTY:-0}" = 1 ]; then
            warn "$src is not exactly origin/ai: copying the work tree as it is (--allow-dirty)"
        else
            printf 'ERROR: %s is not exactly origin/ai (uncommitted changes, or HEAD %s != origin/ai %s).\n' \
                "$src" "${head:0:12}" "${remote:0:12}" >&2
            printf '       Root runs only pushed code. Fetch and check out origin/ai as %s, or add --allow-dirty (development only).\n' "$owner" >&2
            return 1
        fi
    fi
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] copy $src to root-owned $AI_ROOT_REPO"; return 0; fi
    new="$AI_ROOT_REPO.new.$$"
    rm -rf "$new"; mkdir -p "$new"
    if [ "${AI_ALLOW_DIRTY:-0}" = 1 ]; then
        ( cd "$src" && tar --exclude ./.git -cf - . ) | ( cd "$new" && tar -xf - )
    else
        $g archive --format=tar HEAD | ( cd "$new" && tar -xf - )
    fi
    # root:root, not writable by others; never follow a link out of the tree (uutils-safe: no -R on links)
    find "$new" ! -type l -exec chown root:root {} + 
    find "$new" ! -type l -exec chmod go-w {} +
    rm -rf "$AI_ROOT_REPO"; mv "$new" "$AI_ROOT_REPO"
    install -d -o root -g root -m 755 /usr/local/lib/ai
    install -o root -g root -m 755 "$AI_ROOT_REPO/ai/lib/aiconf.py" "$AI_ROOT_HELPER"
    AI_HOME=$AI_ROOT_REPO
    export AI_HOME
}

sha256_is() {
    # sha256_is <file> <expected hex>
    local got
    if has sha256sum; then got=$(sha256sum "$1" | cut -d' ' -f1); else got=$(shasum -a 256 "$1" | cut -d' ' -f1); fi
    [ "$got" = "$2" ]
}

cpu_has_avx2() {
    if [ "$AI_OS" = linux ]; then grep -qw avx2 /proc/cpuinfo
    else sysctl -n machdep.cpu.leaf7_features 2>/dev/null | grep -qi avx2 || [ "$AI_ARCH" = arm64 ]
    fi
}

load_pins() {
    local f="$AI_HOME/ai/pins.env"
    [ -r "$f" ] || die "missing $f"
    # shellcheck disable=SC1090
    . "$f"
}

today() { date +%Y-%m-%d; }

# version_ge A B: true when version A >= B (dotted numbers).
version_ge() {
    [ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -n1)" = "$2" ]
}

# Snapshot and diff a set of files around a vendor command, so the report says what it changed.
snap_files() {
    local f
    for f in "$@"; do
        if [ -e "$f" ]; then printf '%s %s\n' "$(cksum < "$f" | tr -d ' \t')" "$f"; else printf 'absent %s\n' "$f"; fi
    done
}
report_changes() {
    # report_changes "<before snapshot>" files...
    local before=$1; shift
    local after line
    after=$(snap_files "$@")
    if [ "$before" = "$after" ]; then info "files unchanged"; return 0; fi
    printf '%s\n' "$after" | while read -r line; do
        printf '%s\n' "$before" | grep -qxF "$line" || info "changed by vendor: ${line#* }"
    done
}

# Audit gate: an install runs only after agent-audit passed for that exact target.
audit_ok() {
    # audit_ok <ecosystem> <target> [version] [name]
    # name: for `dir` audits of a temp folder, the tool name to look up in ai/audit-accepted.txt.
    local eco=$1 target=$2 ver=${3:-} name=${4:-$2} reason
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] agent-audit $eco $target${ver:+ $ver}"; return 0; fi
    if ! has agent-audit; then warn "agent-audit not found: cannot audit $target, not installing it"; return 1; fi
    if [ "$eco" = dir ]; then agent-audit dir "$target" && return 0
    else agent-audit "$eco" "$target" ${ver:+"$ver"} && return 0; fi
    # Findings. Go on only for an owner-reviewed EXACT version (SPEC 22, ai/audit-accepted.txt).
    reason=$(audit_accepted "$eco" "$name" "$ver")
    if [ -n "$reason" ]; then
        info "ACCEPTED owner-reviewed: $eco $name $ver ($reason)"
        mkdir -p "$AI_STATE_DIR"
        printf '%s %s %s %s ACCEPTED owner-reviewed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$eco" "$name" "${ver:--}" \
            >> "$AI_STATE_DIR/audit.log"
        return 0
    fi
    warn "agent-audit found problems in $name${ver:+ $ver}: not installed, show the owner"
    return 1
}

# audit_accepted <ecosystem> <name> <version>: prints the reviewed reason if that exact version is listed.
audit_accepted() {
    local f="$AI_HOME/ai/audit-accepted.txt"
    [ -n "$3" ] && [ -f "$f" ] || return 0
    awk -v e="$1" -v n="$2" -v v="$3" '!/^#/ && $1==e && $2==n && $3==v { $1=$2=$3=""; sub(/^ +/, ""); print; exit }' "$f"
}
