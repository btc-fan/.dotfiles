#!/usr/bin/env bash
# Read-only checks. Stops the setup when the machine is not what host.env says.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

fail=0
refuse() { printf '   REFUSE: %s\n' "$*" >&2; fail=1; }
ok()     { printf '   ok    %s\n' "$*"; }

log "operating system"
. /etc/os-release
if [ "${ID:-}" != ubuntu ]; then
    refuse "this is ${PRETTY_NAME:-unknown}, not Ubuntu"
else
    ok "$PRETTY_NAME (kernel $(uname -r))"
    case "$VERSION_ID" in
        26.04) ;;
        24.04|24.10|25.04|25.10) warn "Ubuntu $VERSION_ID: should work, tested only on 26.04" ;;
        *) refuse "Ubuntu $VERSION_ID is not supported (need 24.04 or newer)" ;;
    esac
fi
[ "$(uname -m)" = x86_64 ] || refuse "CPU architecture $(uname -m): the downloads here are x86_64 only"
[ -d /run/systemd/system ] || refuse "systemd is not running"
# Both work: the reference server boots legacy BIOS (GPT with a bios_grub partition).
[ -d /sys/firmware/efi ] && ok "boot mode UEFI" || ok "boot mode legacy BIOS"

log "CPU and memory"
model=$(awk -F': ' '/^model name/ {print $2; exit}' /proc/cpuinfo)
ok "$model, $(nproc) threads, $(awk '/MemTotal/ {printf "%.1f GB", $2/1048576}' /proc/meminfo) RAM"
if grep -qw avx2 /proc/cpuinfo; then
    ok "AVX2 present"
else
    warn "NO AVX2. Prebuilt binaries made for x86-64-v3 crash here (illegal instruction)."
    warn "Build such tools from source (cargo build --release). See README, Quirks."
fi

log "disks"
lsblk -d -o NAME,SIZE,ROTA,TRAN,MODEL,SERIAL | sed 's/^/   /'
root_src=$(findmnt -no SOURCE /)
root_disk=$(lsblk -rsno NAME,TYPE "$root_src" | awk '$2=="disk" {print $1; exit}')
ok "system disk: /dev/$root_disk"
for entry in "${DISKS[@]:-}"; do
    [ -n "$entry" ] || continue
    IFS='|' read -r serial label mnt role <<< "$entry"
    dev=$(lsblk -dnro NAME,SERIAL | awk -v s="$serial" '$2==s {print "/dev/"$1}')
    if [ -z "$dev" ]; then
        warn "disk $label ($serial) not found. It is skipped (nofail)."
    elif [ "${dev#/dev/}" = "$root_disk" ]; then
        refuse "disk $label ($serial) is the system disk. Do not list it in DISKS."
    else
        ok "disk $label = $dev, mount $mnt ($role)"
    fi
done

log "network"
if [ -n "${NIC:-}" ] && ip link show "$NIC" >/dev/null 2>&1; then
    ok "interface $NIC: $(cat "/sys/class/net/$NIC/operstate")"
else
    refuse "interface NIC='${NIC:-}' does not exist. Pick one from: $(ls /sys/class/net | tr '\n' ' ')"
fi
addr=$(ip -4 -o addr show dev "${NIC:-lo}" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
if [ -n "$addr" ] && in_cidr "$addr" "$LAN_CIDR"; then
    ok "address $addr is inside LAN_CIDR $LAN_CIDR"
else
    refuse "address '${addr:-none}' is not inside LAN_CIDR $LAN_CIDR (SSH would be blocked)"
fi
ip route show default | grep -q . && ok "default route: $(ip route show default | head -1)" || refuse "no default route"
getent hosts download.docker.com >/dev/null && ok "DNS works" || refuse "DNS does not resolve download.docker.com"

# Every open SSH connection must come from the LAN, Tailscale or this machine, or the firewall
# cuts it. ss sees every TCP connection (also tmux, scp and sessions without a utmp entry, which
# `who` misses). Peer looks like 192.168.1.5:50000, [::ffff:192.168.1.5]:50000 or [fe80::1%eth0]:50000.
sessions=0
while read -r src; do
    [ -n "$src" ] || continue
    sessions=$((sessions + 1))
    if in_cidr "$src" "$LAN_CIDR" || in_cidr "$src" 100.64.0.0/10 || in_cidr "$src" 127.0.0.0/8 || [ "$src" = ::1 ]; then
        ok "SSH connection from $src is allowed"
    else
        refuse "SSH connection from $src is outside LAN_CIDR and Tailscale. The firewall would drop it."
    fi
done < <(ss -Htn state established "( sport = :$SSH_PORT )" 2>/dev/null | awk '{print $4}' \
    | sed -E 's/:[0-9]+$//; s/^\[//; s/\]$//; s/^::ffff://' | sort -u)
[ "$sessions" -gt 0 ] || ok "no SSH connection open (console run)"

log "users and SSH keys"
if id "$MAIN_USER" >/dev/null 2>&1; then
    home=$(getent passwd "$MAIN_USER" | cut -d: -f6)
    keys=$(grep -cE '^(ssh-|ecdsa-|sk-)' "$home/.ssh/authorized_keys" 2>/dev/null || true)
    if [ "${keys:-0}" -gt 0 ]; then
        ok "$MAIN_USER has $keys SSH key(s)"
    else
        refuse "$MAIN_USER has no key in $home/.ssh/authorized_keys. Password login is turned off later: add a key first (ssh-copy-id)."
    fi
else
    refuse "MAIN_USER=$MAIN_USER does not exist"
fi

log "host.env"
[ -e "/usr/share/zoneinfo/$TIMEZONE" ] && ok "timezone $TIMEZONE" || refuse "unknown TIMEZONE=$TIMEZONE"
for t in PG_BACKUP_TIME PG_BIG_BACKUP_TIME PG_DRILL_TIME DIGEST_TIME SMART_DIGEST_TIME WORK_SNAPSHOT_TIME BACKUP_MIRROR_TIME PROJ_BACKUP_TIME PROJ_EXPIRE_TIME; do
    v=${!t:-}
    [ -z "$v" ] || [[ "$v" =~ ^[0-2][0-9]:[0-5][0-9]$ ]] || refuse "$t=$v is not HH:MM"
done
[ "${ADMIN_USER:-admin}" != "$MAIN_USER" ] || refuse "ADMIN_USER and MAIN_USER must be different users"
[[ "${ADMIN_USER:-admin}" =~ ^[a-z_][a-z0-9_-]*$ ]] || refuse "ADMIN_USER=${ADMIN_USER} is not a valid user name"
if [ -n "${BOX_DISK_SERIAL:-}" ]; then
    for entry in "${DISKS[@]:-}"; do
        [ "${entry%%|*}" != "$BOX_DISK_SERIAL" ] || refuse "BOX_DISK_SERIAL is also listed in DISKS. A disk is either a data disk or the box pool."
    done
fi
case "$SSH_PORT" in ''|*[!0-9]*) refuse "SSH_PORT=$SSH_PORT is not a number" ;; esac
# Retention: 0 would delete every backup, including the one just made.
for k in PG_BACKUP_KEEP_DAYS PG_BACKUP_KEEP_DAILY PG_BACKUP_KEEP_WEEKLY PG_BIG_KEEP_DAILY PG_BIG_KEEP_WEEKLY WORK_SNAPSHOT_KEEP_DAYS PROJ_BACKUP_KEEP; do
    v=${!k:-}
    [ -z "$v" ] || { [[ "$v" =~ ^[0-9]+$ ]] && [ "$v" -ge 1 ]; } || refuse "$k=$v must be a number, 1 or more"
done
if [ -n "${AGENT_USER:-}" ]; then
    [[ "$AGENT_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || refuse "AGENT_USER=$AGENT_USER is not a valid user name"
fi
case "${AGENT_SUDO:-none}" in none|full) ;; *) refuse "AGENT_SUDO=${AGENT_SUDO} must be none or full" ;; esac
case "${AGENT_SUDO_ALLOW-proj-agent}" in proj-agent|"") ;; *) refuse "AGENT_SUDO_ALLOW=${AGENT_SUDO_ALLOW} must be proj-agent or empty" ;; esac
# Keys that exist in the example but not in host.env: the defaults apply.
missing=$(comm -23 <(grep -oE '^[A-Z_]+=' "$REPO_DIR/host.env.example" | sort -u) \
                   <(grep -oE '^[A-Z_]+=' "$HOST_ENV" | sort -u) | tr -d '=' | tr '\n' ' ')
[ -z "$missing" ] || warn "not in host.env (defaults used): $missing"

if is_yes "${INSTALL_DOCKER:-yes}" && dpkg-query -W -f='${Status}' docker.io 2>/dev/null | grep -q 'install ok installed'; then
    refuse "Ubuntu's docker.io is installed. Step 40 installs Docker CE from Docker's repo; the two conflict. Move your containers off it and remove it first (apt-get remove docker.io)."
fi
if dpkg-query -W -f='${Status}' gdm3 2>/dev/null | grep -q 'install ok installed'; then
    warn "a desktop (gdm3) is installed. Sleep is still blocked by masked targets."
fi

if [ "$fail" = 1 ]; then
    die "preflight found problems (REFUSE lines above). Nothing was changed."
fi
log "preflight ok"
