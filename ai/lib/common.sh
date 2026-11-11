# ai/lib/common.sh: shared helpers for install.sh, uninstall.sh and ai/adapters/*.sh.
# bash 3.2 compatible (macOS /bin/bash): no associative arrays, no mapfile, no ${x,,}.
# Every command that changes the machine goes through run / run_root / as_hermes so that
# --dry-run prints it instead.

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

run() {
    if [ "$AI_DRY_RUN" = 1 ]; then
        info "[dry-run] $(quote "$@")"
        return 0
    fi
    "$@"
}

is_root() { [ "$(id -u)" -eq 0 ]; }

run_root() {
    if is_root; then run "$@"; else run sudo "$@"; fi
}

has() { command -v "$1" >/dev/null 2>&1; }

# Run a command line as the hermes user (login shell for its PATH). Only on Linux.
hermes_exists() { [ "$AI_OS" = linux ] && getent passwd "$HERMES_USER" >/dev/null 2>&1; }
hermes_home()   { getent passwd "$HERMES_USER" | cut -d: -f6; }
as_hermes()     { run sudo -u "$HERMES_USER" -H bash -lc "$1"; }
as_hermes_ro()  { sudo -n -u "$HERMES_USER" -H bash -lc "$1" 2>/dev/null; }

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
aiconf_root() {
    if [ "$AI_DRY_RUN" = 1 ]; then
        python3 "$AI_HOME/ai/lib/aiconf.py" --state "$AI_SYSTEM_STATE_FILE" --dry-run "$@"
    elif is_root; then
        python3 "$AI_HOME/ai/lib/aiconf.py" --state "$AI_SYSTEM_STATE_FILE" "$@"
    else
        sudo python3 "$AI_HOME/ai/lib/aiconf.py" --state "$AI_SYSTEM_STATE_FILE" "$@"
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
    # login shell: hermes' own PATH (its `hermes` binary lives in its home)
    sudo -u "$HERMES_USER" -H bash -lc "python3 $(quote "$helper") --state \"\$HOME/.local/state/ai/managed-keys.json\" $(quote "$@")"
}

# ---------------------------------------------------------------- facts

detect_os() {
    case "$(uname -s)" in
        Darwin) AI_OS=macos ;;
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
    # audit_ok <ecosystem> <target> [version]
    if [ "$AI_DRY_RUN" = 1 ]; then info "[dry-run] agent-audit $*"; return 0; fi
    if ! has agent-audit; then warn "agent-audit not found: cannot audit $2, not installing it"; return 1; fi
    if agent-audit "$@"; then return 0; fi
    warn "agent-audit found problems in $2${3:+ $3}: not installed, show the owner"
    return 1
}
