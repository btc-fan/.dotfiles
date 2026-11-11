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
    [ "$(id -u)" -eq 0 ] || die "run as root: sudo ./setup.sh"
}

# host.env lives next to setup.sh. It is plain bash (variables and one array).
load_env() {
    local f=$REPO_DIR/host.env
    [ -f "$f" ] || die "missing $f. Copy host.env.example to host.env and edit it."
    # shellcheck source=/dev/null
    . "$f"
    MAIN_USER=${MAIN_USER:?MAIN_USER is empty in host.env}
    LAN_CIDR=${LAN_CIDR:?LAN_CIDR is empty in host.env}
    SSH_PORT=${SSH_PORT:-22}
    TIMEZONE=${TIMEZONE:-UTC}
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

is_yes() {
    case "${1:-}" in yes|y|true|1|on) return 0 ;; *) return 1 ;; esac
}
