# shellcheck shell=bash
# Shared helpers for setup.sh and every step. Sourced, never run directly.
# Rules: every change goes through put (files) or run (commands), so --dry-run works
# and a second run changes nothing.

set -euo pipefail
export LC_ALL=C.UTF-8 DEBIAN_FRONTEND=noninteractive

REPO_DIR=${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
DRY_RUN=${DRY_RUN:-0}
FORMAT=${FORMAT:-0}
CHANGED=0
SERVER_ETC=/etc/server

log()  { printf '\n== %s\n' "$*"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '   WARN: %s\n' "$*" >&2; }
die()  { printf '   ERROR: %s\n' "$*" >&2; exit 1; }
dry()  { [ "$DRY_RUN" = 1 ]; }
changed() { [ "$CHANGED" = 1 ]; }

need_root() {
    [ "$(id -u)" -eq 0 ] || die "run as root: sudo /opt/server-setup/setup.sh"
}

# host.env lives in /etc/server/host.env (root:root 644). It is plain bash (variables and arrays),
# sourced by root: so it must be root-owned and writable by root only. A clone holds only the
# example (host.env.example); a host.env left in a clone is not read.
HOST_ENV=$SERVER_ETC/host.env
SETUP_REPO_URL_DEFAULT=https://github.com/btc-fan/.dotfiles.git

host_env_trusted() {
    [ -f "$HOST_ENV" ] || die "missing $HOST_ENV. First install: sudo install -D -m 644 $REPO_DIR/host.env.example $HOST_ENV ; sudo nano $HOST_ENV"
    local d
    for d in "$HOST_ENV" "$SERVER_ETC" /etc; do
        [ "$(stat -c %u "$d")" = 0 ] || die "$d is not owned by root. Root sources $HOST_ENV: refused."
        case "$(stat -c %A "$d")" in
            ?????w????|????????w?) die "$d is writable by group or others. Root sources $HOST_ENV: refused (sudo chmod go-w $d)." ;;
        esac
    done
}

load_env() {
    [ "${SOURCE_GUARD_OK:-0}" = 1 ] || source_guard
    host_env_trusted
    # shellcheck source=/dev/null
    . "$HOST_ENV"
    MAIN_USER=${MAIN_USER:?MAIN_USER is empty in host.env}
    LAN_CIDR=${LAN_CIDR:?LAN_CIDR is empty in host.env}
    SSH_PORT=${SSH_PORT:-22}
    TIMEZONE=${TIMEZONE:-UTC}
}

# git_root ARGS: the real git (never a wrapper in PATH), no hooks, and the clone trusted even when
# the admin user owns it. Only called after source_guard has checked who owns the clone.
git_root() {
    /usr/bin/git -c safe.directory="$REPO_DIR" -c core.hooksPath=/dev/null -c core.fsmonitor=false "$@"
}

# guard_fail WHY: the one message for every refused source, with the commands that work.
guard_fail() {
    local url=${SETUP_REPO_URL:-$SETUP_REPO_URL_DEFAULT}
    cat >&2 <<EOF
   ERROR: $1
   Root runs setup only from a clean git clone owned by root (or by ${ADMIN_USER:-the admin user}),
   never from a folder another user (or an agent running as that user) can change.
   Once, as the admin user:
       sudo git clone -b ubuntu-server $url /opt/server-setup
   Then every time (fetches what was pushed, fast-forward only, then runs it):
       sudo /opt/server-setup/setup.sh --update [--only STEP] [--dry-run]
EOF
    exit 1
}

# env_value KEY: one plain value from host.env, read as text (nothing runs). For the guard only.
env_value() {
    sed -n "s/^$1=\"\{0,1\}\([^\" ]*\)\"\{0,1\}.*/\1/p" "$HOST_ENV" | tail -n 1
}

# source_guard: SECURITY. Before root runs anything more from REPO_DIR:
#   - /etc/server/host.env is root-owned and writable by root only (it is sourced);
#   - REPO_DIR and every folder above it belong to root or ADMIN_USER and nobody else can write them;
#   - every file in the clone (.git included) belongs to root or ADMIN_USER, and there is no symlink;
#   - git status is clean: no edited, staged or untracked file runs as root.
# setup.sh itself was read by bash before this check: so the guard stops mistakes, and the docs
# give the admin only commands that start from /opt/server-setup. setup.sh exports
# SOURCE_GUARD_OK=1 for its steps after the check passed.
source_guard() {
    [ "$(id -u)" -eq 0 ] || return 0
    host_env_trusted
    local auid=-1 agid=-1 d bad
    ADMIN_USER=$(env_value ADMIN_USER)
    ADMIN_USER=${ADMIN_USER:-admin}
    SETUP_REPO_URL=$(env_value SETUP_REPO_URL)
    if id "$ADMIN_USER" >/dev/null 2>&1; then auid=$(id -u "$ADMIN_USER"); agid=$(id -g "$ADMIN_USER"); fi
    d=$REPO_DIR
    while :; do
        case "$(stat -c %u "$d")" in 0|"$auid") ;; *) guard_fail "$d belongs to $(stat -c %U "$d")." ;; esac
        case "$(stat -c %A "$d")" in ????????w?) guard_fail "$d is writable by everybody." ;; esac
        case "$(stat -c %A "$d")" in
            ?????w????) case "$(stat -c %g "$d")" in 0|"$agid") ;; *) guard_fail "$d is writable by group $(stat -c %G "$d")." ;; esac ;;
        esac
        [ "$d" != / ] || break
        d=$(dirname "$d")
    done
    [ -d "$REPO_DIR/.git" ] && [ ! -L "$REPO_DIR/.git" ] || guard_fail "$REPO_DIR is not a git clone (an old copy?)."
    [ "$auid" != -1 ] || auid=0
    [ "$agid" != -1 ] || agid=0
    bad=$(find "$REPO_DIR" -xdev \( \( ! -uid 0 ! -uid "$auid" \) -o -type l \
        -o \( ! -type l -perm -002 \) -o \( ! -type l -perm -020 ! -gid 0 ! -gid "$agid" \) \) -print -quit)
    [ -z "$bad" ] || guard_fail "$bad: owned by another user, a symlink, or writable by others."
    bad=$(git_root -C "$REPO_DIR" status --porcelain --untracked-files=all 2>&1) \
        || guard_fail "git status failed in $REPO_DIR: $bad"
    [ -z "$bad" ] || guard_fail "the clone $REPO_DIR has local changes (they would run as root):
$(printf '%s\n' "$bad" | head -n 10 | sed 's/^/       /')
   Look at them (sudo git -C $REPO_DIR status), then drop them (sudo git -C $REPO_DIR checkout -- .)."
    SOURCE_GUARD_OK=1
    export SOURCE_GUARD_OK
}

# update_clone: fetch the current branch from origin and fast-forward to it. Refused when the
# branch has local commits or the remote history was rewritten (a force push): look first.
update_clone() {
    local branch old new
    branch=$(git_root -C "$REPO_DIR" symbolic-ref --short -q HEAD) \
        || die "$REPO_DIR is not on a branch (detached HEAD). Fix: sudo git -C $REPO_DIR checkout ubuntu-server"
    old=$(git_root -C "$REPO_DIR" rev-parse HEAD)
    log "update $REPO_DIR: fetch origin $branch"
    git_root -C "$REPO_DIR" fetch --quiet origin "$branch" || die "git fetch failed. Nothing changed."
    new=$(git_root -C "$REPO_DIR" rev-parse FETCH_HEAD)
    if [ "$old" = "$new" ]; then
        info "already at $(git_root -C "$REPO_DIR" log -1 --format='%h %s')"
        return 0
    fi
    git_root -C "$REPO_DIR" merge-base --is-ancestor "$old" "$new" \
        || die "origin/$branch ($new) does not continue $old: local commits or rewritten history. Look first: sudo git -C $REPO_DIR log --oneline -5 FETCH_HEAD. Nothing changed."
    info "new commits:"
    git_root -C "$REPO_DIR" log --oneline "$old..$new" | sed 's/^/     /'
    git_root -C "$REPO_DIR" merge --ff-only --quiet "$new"
    SOURCE_GUARD_OK=0
    source_guard
}

# run CMD...: run a command, or only print it in dry-run mode.
run() {
    if dry; then
        printf '   would run: %s\n' "$*"
        return 0
    fi
    "$@"
}

# put PATH MODE [OWNER:GROUP] < content
# Writes the file only when the content differs. Sets CHANGED=1 when it wrote.
put() {
    local dst=$1 mode=$2 own=${3:-root:root} tmp
    tmp=$(mktemp)
    cat > "$tmp"
    CHANGED=0
    if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then
        rm -f "$tmp"
        dry || chmod "$mode" "$dst"
        return 0
    fi
    CHANGED=1
    if dry; then
        info "would write $dst"
        if [ -f "$dst" ]; then
            diff -u "$dst" "$tmp" | sed 's/^/     /' | head -n 40 || true
        fi
        rm -f "$tmp"
        return 0
    fi
    install -D -m "$mode" -o "${own%%:*}" -g "${own##*:}" "$tmp" "$dst"
    rm -f "$tmp"
    info "wrote $dst"
}

# put_file SRC_IN_REPO DST MODE: install a file from files/ in this repo.
put_file() {
    put "$2" "$3" < "$REPO_DIR/files/$1"
}

# put_sudoers FILE < content: install a sudoers file only when visudo accepts it.
# A broken sudoers file can lock everybody out of sudo, so it is checked before it lands.
put_sudoers() {
    local dst=$1 tmp
    tmp=$(mktemp)
    cat > "$tmp"
    chmod 440 "$tmp"
    if ! visudo -c -f "$tmp" >/dev/null; then
        rm -f "$tmp"
        die "visudo rejects the new $dst. Nothing changed."
    fi
    put "$dst" 440 < "$tmp"
    rm -f "$tmp"
}

# Apt signing keys: primary key fingerprints, checked on the live server 2026-11-11.
# A downloaded key with any other primary key is refused (a rotated key means: check, then update here).
FPR_DOCKER=9DC858229FC7DD38854AE2D88D81803C0EBFCD88
FPR_PGDG=B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8
FPR_NODESOURCE=6F71F525282841EEDAF851B42F59B5F99B1BE0B4
FPR_GITHUB_CLI="2C6106201985B60E6C7AC87323F3D4EA75716059 7F38BBB59D064DBCB3D84D725612B36462313325"   # GitHub ships 2 keys (old + new)
FPR_TAILSCALE=2596A99EAAB33821893C0A79458CA832957F5868
FPR_ZABBLY=4EFC590696CB15B87C73A3AD82CC8797C838DCFD

# check_key_fpr FILE EXPECTED NAME: the key file must hold exactly the primary keys in EXPECTED
# (one fingerprint, or several separated by spaces in sorted order), nothing more, nothing less.
# Read only: gpg runs with a throwaway home, root's keyring is not touched.
check_key_fpr() {
    local file=$1 want=$2 name=$3 home got
    home=$(mktemp -d)
    got=$(GNUPGHOME=$home gpg --batch --show-keys --with-colons "$file" 2>/dev/null \
        | awk -F: '/^pub/ {p = 1; next} /^sub/ {p = 0} /^fpr/ && p {print $10; p = 0}' | sort -u | tr '\n' ' ' || true)
    rm -rf "$home"
    got=${got% }
    [ "$got" = "$want" ] || die "$name signing key: fingerprint '${got:-none}', expected $want. Refused, nothing changed."
}

# remove_legacy PATH...: delete files that older versions of this setup wrote.
remove_legacy() {
    local f
    for f in "$@"; do
        if [ -e "$f" ] || [ -L "$f" ]; then
            info "remove old file $f"
            run rm -f "$f"
            CHANGED=1
        fi
    done
}

# apt_install PKG...: install only the packages that are missing.
apt_install() {
    local missing=() p
    for p in "$@"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || missing+=("$p")
    done
    if [ "${#missing[@]}" -eq 0 ]; then
        return 0
    fi
    info "install: ${missing[*]}"
    run apt-get update -q
    run apt-get install -y -q "${missing[@]}"
}

# in_cidr IP CIDR: true when IP is inside CIDR.
in_cidr() {
    python3 -I -c 'import ipaddress, sys
sys.exit(0 if ipaddress.ip_address(sys.argv[1]) in ipaddress.ip_network(sys.argv[2], strict=False) else 1)' \
        "$1" "$2" 2>/dev/null
}

# enable_unit UNIT [--now]: enable only when not enabled yet.
enable_unit() {
    local unit=$1 now=${2:-}
    if [ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" != enabled ]; then
        run systemctl enable $now "$unit"
    elif [ "$now" = --now ] && ! systemctl is-active -q "$unit"; then
        run systemctl start "$unit"
    fi
}

# rollback_armed: the 10 min SSH safety timer from step 10 is running.
rollback_armed() { systemctl is-active -q server-rollback.timer 2>/dev/null; }

# nopasswd_effective < `sudo -n -l -U USER` output: print the NOPASSWD commands that still count.
# sudo uses the LAST matching rule, so a later password rule for ALL ("PASSWD: ALL" from
# zz-server-main-password, or a plain "ALL") cancels every NOPASSWD line listed before it;
# NOPASSWD lines after it still count.
# Only rule lines are read (indented, starting with "("); Defaults lines are skipped.
nopasswd_effective() {
    awk '
        /^[[:space:]]+\(/ {
            line = $0
            if (line !~ /NOPASSWD:/ && line ~ /[[:space:]]ALL[[:space:]]*$/) { n = 0; next }
            if (line ~ /NOPASSWD:/) {
                sub(/.*NOPASSWD:[[:space:]]*/, "", line)
                sub(/[[:space:]]+$/, "", line)
                out[++n] = line
            }
        }
        END { for (i = 1; i <= n; i++) print out[i] }'
}

is_yes() {
    case "${1:-}" in yes|y|true|1|on) return 0 ;; *) return 1 ;; esac
}
