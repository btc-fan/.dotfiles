#!/usr/bin/env bash
# Project hosting: Incus LTS + ZFS pool on its own disk, box profiles, firewall, the proj CLI.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

POOL=boxes
BRIDGE=incusbr0
INCUS_CHANNEL=lts-7.0
# Zabbly signing key fingerprint: FPR_ZABBLY in lib/common.sh. The key is refused if it differs.
BOX_DISK_SERIAL=${BOX_DISK_SERIAL:-}
BOX_SUBNET=${BOX_SUBNET:-10.99.0.1/24}
# RAM budget on the reference machine: see docs/HOSTING.md. No nr_hugepages here (the md999
# move sets that for its own Postgres).
BOX_MEMORY_BUDGET=${BOX_MEMORY_BUDGET:-4GiB}
BOX_EGRESS_REJECT=${BOX_EGRESS_REJECT:-10.0.0.0/8 192.168.0.0/16 172.16.0.0/12 100.64.0.0/10 169.254.0.0/16}
ZFS_ARC_MAX_MB=${ZFS_ARC_MAX_MB:-1536}
UNITS=0
unit_changed() { if changed; then UNITS=1; fi; }

main() {
    if [ -z "$BOX_DISK_SERIAL" ]; then
        log "BOX_DISK_SERIAL is empty: project hosting is off, step skipped"
        return 0
    fi
    apt_install zfsutils-linux jq zstd smartmontools curl gnupg iptables
    incus_repo
    apt_install incus
    subid_ranges
    enable_unit incus --now
    zfs_arc
    zed_alerts
    storage_pool
    bridge
    egress_acl        # before the profiles: box-base names the ACL on every box NIC
    profiles
    memory_budget
    firewall
    docker_fix
    install_proj
    workspaces
    agents_sudo       # after install_proj: the rule and the binary it allows land together
    proj_agent_socket # after workspaces: the socket's group must exist
    host_marker
    host_projects
    timers
    if [ "$UNITS" = 1 ]; then run systemctl daemon-reload; fi
    enable_unit proj-backup.timer --now
    enable_unit proj-expire.timer --now
    groups_check
    dry || /usr/local/sbin/proj registry >/dev/null
    info "next: sudo proj doctor ; first box: sudo proj new test1 --tier try"
}

# Where Incus comes from (host.env INCUS_SOURCE):
#   ubuntu (default): Ubuntu archive, incus 6.0.x LTS (6.0.5 on 26.04), Ubuntu-signed, no extra repo.
#                     Pinned to 6.0.* so it never jumps series.
#   zabbly:           Incus 7.0 LTS from the Zabbly repo (run by the Incus maintainers, LTS to 2031).
#                     Audit: key fetched with curl (no pipe to shell), fingerprint checked,
#                     channel lts-7.0 only, apt pinned to that origin.
# Going back from 7.0 to 6.0 is not possible (the Incus database only moves forward): refused.
incus_repo() {
    local src=${INCUS_SOURCE:-ubuntu} have
    have=$(dpkg-query -W -f='${Version}' incus 2>/dev/null || true)
    case "$src" in
        ubuntu)
            log "Incus from the Ubuntu archive (6.0 LTS, pinned)"
            case "$have" in ''|6.0.*|1:6.0.*) ;; *) die "incus $have is installed; the Ubuntu archive has 6.0. A downgrade is not possible. Set INCUS_SOURCE=zabbly." ;; esac
            remove_legacy "/etc/apt/sources.list.d/zabbly-incus-$INCUS_CHANNEL.sources"
            put /etc/apt/preferences.d/incus 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 70-hosting): Incus 6.0 LTS series only.
Package: incus*
Pin: version 6.0.*
Pin-Priority: 1001
EOF
            if changed; then run apt-get update -q; fi
            ;;
        zabbly) incus_repo_zabbly ;;
        *) die "INCUS_SOURCE must be ubuntu or zabbly, not '$src'" ;;
    esac
}

incus_repo_zabbly() {
    log "Incus repo: Zabbly $INCUS_CHANNEL (pinned)"
    local tmp any=0
    . /etc/os-release
    tmp=$(mktemp)
    curl -fsSL https://pkgs.zabbly.com/key.asc -o "$tmp"
    check_key_fpr "$tmp" "$FPR_ZABBLY" Zabbly
    put /etc/apt/keyrings/zabbly.asc 644 < "$tmp"
    rm -f "$tmp"
    if changed; then any=1; fi
    put "/etc/apt/sources.list.d/zabbly-incus-$INCUS_CHANNEL.sources" 644 <<EOF
Enabled: yes
Types: deb
URIs: https://pkgs.zabbly.com/incus/$INCUS_CHANNEL
Suites: $VERSION_CODENAME
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/zabbly.asc
EOF
    if changed; then any=1; fi
    put /etc/apt/preferences.d/incus 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 70-hosting): Incus only from the Zabbly LTS channel.
Package: incus*
Pin: origin pkgs.zabbly.com
Pin-Priority: 1001
EOF
    if changed; then any=1; fi
    if [ "$any" = 1 ]; then run apt-get update -q; fi
}

# isolated idmap: every box needs its own 65536 IDs. Give root a large range.
subid_ranges() {
    local f any=0
    for f in /etc/subuid /etc/subgid; do
        if ! grep -q '^root:' "$f" 2>/dev/null; then
            info "add root:1000000:1000000000 to $f (ID ranges for isolated boxes)"
            run sh -c "echo 'root:1000000:1000000000' >> $f"
            any=1
        fi
    done
    if [ "$any" = 1 ] && systemctl is-active -q incus; then run systemctl restart incus; fi
}

# ZFS cache (ARC) capped, so it does not take RAM from Postgres.
zfs_arc() {
    log "ZFS ARC max ${ZFS_ARC_MAX_MB} MB"
    local bytes=$((ZFS_ARC_MAX_MB * 1024 * 1024)) p=/sys/module/zfs/parameters/zfs_arc_max
    put /etc/modprobe.d/zfs.conf 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 70-hosting): cap the ZFS cache.
options zfs zfs_arc_max=$bytes
EOF
    if [ -w "$p" ] && [ "$(cat "$p")" != "$bytes" ]; then run sh -c "echo $bytes > $p"; fi
}

# ZFS events (device faulted, data errors, scrub or resilver with errors) to Discord #alerts:
# zed's mail hook calls zed-discord (step 50) instead of mailing root, which nobody reads.
# The webhook URL stays in /etc/server/webhooks (root only), never in zed.rc (world-readable).
zed_alerts() {
    local rc=/etc/zfs/zed.d/zed.rc tmp k v
    [ -f "$rc" ] || { warn "$rc missing: ZFS events not sent to Discord"; return 0; }
    log "ZFS events -> #alerts (zed.rc: ZED_EMAIL_PROG=zed-discord)"
    tmp=$(mktemp)
    cp "$rc" "$tmp"
    for kv in 'ZED_EMAIL_ADDR=discord' 'ZED_EMAIL_PROG=/usr/local/sbin/zed-discord' "ZED_EMAIL_OPTS='@SUBJECT@'" 'ZED_NOTIFY_INTERVAL_SECS=3600'; do
        k=${kv%%=*}; v=${kv#*=}
        if grep -qE "^#?[[:space:]]*$k=" "$tmp"; then
            awk -v k="$k" -v v="$v" 'done == 0 && $0 ~ "^#?[[:space:]]*" k "=" { print k "=\"" v "\""; done = 1; next } { print }' "$tmp" > "$tmp.new"
        else
            { cat "$tmp"; echo "$k=\"$v\""; } > "$tmp.new"
        fi
        mv "$tmp.new" "$tmp"
    done
    put "$rc" 644 < "$tmp"
    rm -f "$tmp"
    if changed && ! dry; then systemctl restart zfs-zed 2>/dev/null || warn "zfs-zed did not restart"; fi
}

dev_for_serial() { lsblk -dnro NAME,SERIAL | awk -v s="$1" '$2==s {print "/dev/"$1; exit}'; }

# pool_stop MSG: a real run stops here (nothing changed). A dry run warns and goes on.
pool_stop() {
    if dry; then warn "$* (dry-run goes on)"; return 0; fi
    die "$*"
}

# release_check DEV: read only. A mounted box disk may be released (with --format) only when
# every mounted filesystem on it holds nothing but an empty lost+found, and none is swap.
# Returns 1 (after pool_stop) when it may not.
release_check() {
    local dev=$1 name mp extra
    while read -r name mp; do
        [ -n "$mp" ] || continue
        mp=$(printf '%b' "$mp")   # lsblk -r writes a space as \x20
        case "$mp" in
            /*) ;;
            *) pool_stop "/dev/$name is in use as '$mp' (not a folder). Release it by hand."; return 1 ;;
        esac
        extra=$(find "$mp" -xdev -mindepth 1 -maxdepth 1 ! -name lost+found -print -quit 2>/dev/null || echo "?unreadable")
        [ -z "$extra" ] && [ -d "$mp/lost+found" ] && extra=$(find "$mp/lost+found" -mindepth 1 -print -quit 2>/dev/null || echo "?unreadable")
        if [ -n "$extra" ]; then
            pool_stop "$mp (/dev/$name, on the box disk) is not empty (found $extra). Nothing changed. Empty it or release it by hand."
            return 1
        fi
        info "$mp (/dev/$name) is empty (only lost+found): can be released"
    done < <(lsblk -nro NAME,MOUNTPOINT "$dev")
    return 0
}

# release_disk DEV: --format only, after release_check and the SMART gate. Unmounts every empty
# filesystem on DEV, comments out its fstab lines (by mount point, UUID, LABEL or device; a copy
# of fstab is kept), then wipes the signatures. The normal guards run after this.
release_disk() {
    local dev=$1 name mp uuid label tmp stamp
    stamp=$(date +%F)
    tmp=$(mktemp)
    cat /etc/fstab > "$tmp"
    while read -r name mp; do
        [ -n "$mp" ] || continue
        mp=$(printf '%b' "$mp")
        uuid=$(blkid -s UUID -o value "/dev/$name" 2>/dev/null || true)
        label=$(blkid -s LABEL -o value "/dev/$name" 2>/dev/null || true)
        info "release $mp (/dev/$name): unmount, comment out its fstab line"
        run umount "$mp"
        awk -v m="$mp" -v u="${uuid:+UUID=$uuid}" -v l="${label:+LABEL=$label}" -v d="/dev/$name" -v stamp="$stamp" '
            /^[[:space:]]*#/ || NF == 0 { print; next }
            ($2 == m || (u != "" && $1 == u) || (l != "" && $1 == l) || $1 == d) {
                print "# replaced by setup.sh " stamp " (box disk released for the ZFS pool): " $0; next }
            { print }
        ' "$tmp" > "$tmp.new"
        mv "$tmp.new" "$tmp"
    done < <(lsblk -nro NAME,MOUNTPOINT "$dev")
    if ! cmp -s "$tmp" /etc/fstab; then
        dry || cp -a /etc/fstab "/etc/fstab.bak-$(date +%F-%H%M%S)"
        put /etc/fstab 644 < "$tmp"
        run systemctl daemon-reload
    fi
    rm -f "$tmp"
    # Partitions first, then the disk (GPT and its backup at the end), then reread the table.
    for name in $(lsblk -nro NAME,TYPE "$dev" | awk '$2 == "part" {print $1}'); do
        run wipefs -a "/dev/$name"
    done
    run wipefs -a "$dev"
    run blockdev --rereadpt "$dev"
    run udevadm settle
}

# The pool takes the WHOLE box disk. Created once, only when:
# the disk is not the system disk, not in DISKS, not mounted, completely empty,
# smartctl -H says PASSED, and --format was given. Scripts never start a SMART test (owner rule).
# With --format, a box disk that is still mounted with an EMPTY filesystem (only lost+found) is
# released first: unmounted, fstab line commented out, signatures wiped. Then the guards above.
storage_pool() {
    log "storage pool $POOL (ZFS, whole disk $BOX_DISK_SERIAL)"
    if incus storage show "$POOL" >/dev/null 2>&1; then
        info "pool $POOL exists ($(incus storage get "$POOL" source 2>/dev/null || true))"
        pool_atime
        return 0
    fi
    local dev root entry byid l
    dev=$(dev_for_serial "$BOX_DISK_SERIAL")
    [ -n "$dev" ] || { pool_stop "box disk $BOX_DISK_SERIAL not found (lsblk -d -o NAME,SERIAL)"; return 0; }
    root=$(lsblk -rsno NAME,TYPE "$(findmnt -no SOURCE /)" | awk '$2=="disk" {print $1; exit}')
    [ "${dev#/dev/}" != "$root" ] || die "$dev is the system disk"
    for entry in "${DISKS[@]:-}"; do
        if [ "${entry%%|*}" = "$BOX_DISK_SERIAL" ]; then
            pool_stop "$BOX_DISK_SERIAL is also in DISKS. Remove that line and its fstab line first."
            return 0
        fi
    done
    local mounted=0 released=0
    if lsblk -nro MOUNTPOINT "$dev" | grep -q .; then
        if [ "$FORMAT" != 1 ]; then
            pool_stop "$dev (or a partition) is mounted. Unmount it and remove it from /etc/fstab first (or, if it is empty, run with --format to let this step release it)."
            return 0
        fi
        # With --format, an EMPTY filesystem may be released by this step. Read-only check first.
        release_check "$dev" || return 0
        mounted=1
    fi

    # SMART gate (owner decision): the disk's own health verdict must be PASSED. Read only:
    # smartctl -H starts nothing. A long test, if wanted, is the owner's call, by hand.
    local health
    health=$(smartctl -H "$dev" 2>/dev/null | grep -E 'overall-health self-assessment test result:|SMART Health Status:' | head -1 || true)
    if ! grep -qE 'result: PASSED|Health Status: OK' <<< "$health"; then
        warn "SMART health of $dev is not PASSED: ${health:-no answer from smartctl -H}"
        warn "check by hand: sudo smartctl -a $dev"
        pool_stop "box disk not proven healthy. Nothing changed."
        return 0
    fi
    info "SMART health: $health"

    # Released only after the SMART gate: a failing disk is never touched.
    if [ "$mounted" = 1 ]; then
        release_disk "$dev"
        released=1
    fi

    if [ "$released" = 1 ] && dry; then
        info "would check that no signature is left on $dev (wipefs -n), then create the pool"
    elif lsblk -nro TYPE "$dev" | grep -q part || wipefs -n "$dev" 2>/dev/null | grep -q .; then
        lsblk -o NAME,SIZE,FSTYPE,LABEL "$dev" | sed 's/^/   /'
        pool_stop "$dev is not empty. If you are SURE nothing on it is needed: sudo wipefs -a ${dev}1 ; sudo wipefs -a $dev ; then run with --format."
        return 0
    fi
    if [ "$FORMAT" != 1 ]; then
        pool_stop "$dev is empty and healthy. To make the ZFS pool on it: sudo /opt/server-setup/setup.sh --only hosting --format"
        return 0
    fi

    byid=""
    for l in /dev/disk/by-id/ata-* /dev/disk/by-id/wwn-* /dev/disk/by-id/nvme-*; do
        [ -e "$l" ] || continue
        case "$l" in *-part*) continue ;; esac
        if [ "$(readlink -f "$l")" = "$dev" ]; then byid=$l; break; fi
    done
    [ -n "$byid" ] || byid=$dev
    info "create ZFS pool $POOL on $byid"
    run incus storage create "$POOL" zfs "source=$byid"
    dry || pool_atime
}

# atime=off on the pool (children inherit): no write for every read. Nothing here needs atime.
pool_atime() {
    local zp
    zp=$(incus storage get "$POOL" zfs.pool_name 2>/dev/null || true)
    zp=${zp:-$POOL}
    [ "$(zfs get -H -o value atime "$zp" 2>/dev/null)" = off ] || run zfs set atime=off "$zp"
}

bridge() {
    log "network $BRIDGE ($BOX_SUBNET, NAT, no IPv6)"
    if ! incus network show "$BRIDGE" >/dev/null 2>&1; then
        run incus network create "$BRIDGE" "ipv4.address=$BOX_SUBNET" ipv4.nat=true ipv6.address=none
    fi
}

# apply_yaml KIND NAME FILE: create the Incus object if missing, load the YAML when it changed.
apply_yaml() {
    local kind=$1 name=$2 file=$3 was=$CHANGED
    if ! incus "$kind" show "$name" >/dev/null 2>&1; then
        run incus "$kind" create "$name"
        was=1
    fi
    if [ "$was" = 1 ]; then
        if dry; then info "would load $file into $kind $name"; else incus "$kind" edit "$name" < "$file"; fi
    fi
}

profiles() {
    log "profiles: box-base, tier-try, tier-mvp, tier-long, docker"
    local p
    for p in box-base tier-try tier-mvp tier-long docker; do
        put_file "incus/$p.yaml" "/etc/proj/incus/$p.yaml" 644
        apply_yaml profile "$p" "/etc/proj/incus/$p.yaml"
    done
}

# Boxes may reach the internet, not the home network, the tailnet or Docker networks.
# A reject range that holds the box network itself (10.0.0.0/8 holds 10.99.0.0/24) is split so
# the box network stays out of it: Incus applies reject before allow, so an allow rule could not
# make the exception. Box to box is blocked anyway (port isolation), DHCP and DNS to the bridge
# are Incus baseline rules.
egress_acl() {
    local dst
    dst=$(python3 -I -c 'import ipaddress, sys
box = ipaddress.ip_network(sys.argv[1], strict=False)
out = []
for c in sys.argv[2:]:
    n = ipaddress.ip_network(c, strict=False)
    if n.version == box.version and box.subnet_of(n):
        out += [str(x) for x in sorted(n.address_exclude(box))]
    elif n.version == box.version and n.subnet_of(box):
        continue
    else:
        out.append(str(n))
print(",".join(out))' "$BOX_SUBNET" $BOX_EGRESS_REJECT) || die "BOX_EGRESS_REJECT or BOX_SUBNET is not a valid network"
    log "network ACL box-egress: reject ${BOX_EGRESS_REJECT} (box network $BOX_SUBNET left out)"
    put /etc/proj/incus/box-egress.yaml 644 <<EOF
description: proj boxes - no LAN, tailnet or Docker networks (managed by ~/.dotfiles step 70-hosting)
egress:
- action: reject
  state: enabled
  destination: $dst
  description: no home network, tailnet, docker or link-local
ingress: []
config: {}
EOF
    if ! incus network acl show box-egress >/dev/null 2>&1; then
        run incus network acl create box-egress
        CHANGED=1
    fi
    # Always (re)load: cheap, idempotent, and it repairs a load that failed on an earlier run.
    if dry; then info "would load box-egress ACL"; else incus network acl edit box-egress < /etc/proj/incus/box-egress.yaml; fi
    # Once an ACL is set, unmatched traffic gets a default action (reject on the network, drop on
    # a bridged NIC; the docs differ between pages). Never rely on it: set allow explicitly, here
    # and on every box NIC (box-base). The ACL only lists what is forbidden.
    # DHCP and DNS to the bridge are "baseline" rules that come before any ACL;
    # proj selftest proves a fresh box still gets an address and DNS.
    local k v
    for k in security.acls security.acls.default.egress.action security.acls.default.ingress.action; do
        case "$k" in security.acls) v=box-egress ;; *) v=allow ;; esac
        [ "$(incus network get "$BRIDGE" "$k" 2>/dev/null || true)" = "$v" ] || run incus network set "$BRIDGE" "$k=$v"
    done
}

# The sum of all box memory caps. A new box that does not fit is refused by Incus.
memory_budget() {
    log "box memory budget $BOX_MEMORY_BUDGET (sum of limits.memory, project default)"
    [ "$(incus project get default limits.memory 2>/dev/null || true)" = "$BOX_MEMORY_BUDGET" ] \
        || run incus project set default "limits.memory=$BOX_MEMORY_BUDGET"
}

ufw_rule() {
    local out
    if dry; then info "would run: ufw $*"; return 0; fi
    out=$(ufw "$@")
    case "$out" in *Skipping*) ;; *) info "$out" ;; esac
}

# Boxes need DHCP and DNS from the host, and a route out. Narrower than the Incus how-to
# ("ufw allow in on incusbr0" = every host port): only DHCP and DNS.
# Routing: new connections from boxes only out through the uplink NIC (the internet; the LAN on
# that NIC is rejected by the box-egress ACL). Nothing new INTO boxes. Replies come back through
# ufw's own RELATED,ESTABLISHED rule (before.rules), so no "route allow out on incusbr0".
firewall() {
    log "ufw: DHCP + DNS from boxes to the host, boxes out to the internet via $NIC only"
    ufw_rule allow in on "$BRIDGE" to any port 67 proto udp comment 'incus DHCP'
    ufw_rule allow in on "$BRIDGE" to any port 53 comment 'incus DNS'
    ufw_rule route allow in on "$BRIDGE" out on "$NIC" comment 'incus boxes to internet'
    # Wider rules from the first version of this step.
    local added
    added=$(ufw show added 2>/dev/null || true)
    if grep -qxF "ufw route allow in on $BRIDGE comment 'incus boxes out'" <<< "$added"; then
        ufw_rule route delete allow in on "$BRIDGE"
    fi
    if grep -qxF "ufw route allow out on $BRIDGE comment 'incus boxes back'" <<< "$added"; then
        ufw_rule route delete allow out on "$BRIDGE"
    fi
}

docker_fix() {
    command -v docker >/dev/null || return 0
    log "DOCKER-USER: box replies accepted, box traffic handed on to the ufw route rules (persistent unit)"
    put_file sbin/incus-docker-fix /usr/local/sbin/incus-docker-fix 755
    local script_changed=$CHANGED
    put /etc/systemd/system/incus-docker-fix.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 70-hosting).
[Unit]
Description=Let Incus boxes through the Docker FORWARD drop (DOCKER-USER)
After=docker.service incus.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/incus-docker-fix

[Install]
WantedBy=docker.service multi-user.target
EOF
    unit_changed
    if [ "$UNITS" = 1 ]; then run systemctl daemon-reload; UNITS=0; fi
    enable_unit incus-docker-fix.service --now
    # New rules: run the script again now (the old blanket ACCEPT is removed by it).
    if [ "$script_changed" = 1 ] && systemctl is-active -q incus-docker-fix.service 2>/dev/null; then
        run systemctl restart incus-docker-fix.service
    fi
    if grep -qs '"firewall-backend": *"nftables"' /etc/docker/daemon.json; then
        warn "Docker uses the nftables backend: no DOCKER-USER chain, boxes may lose network"
    fi
}

install_proj() {
    log "proj CLI"
    run install -d -m 755 /etc/proj /srv/proj /usr/local/share/proj
    [ -z "${BACKUP_DIR:-}" ] || run install -d -m 700 "$BACKUP_DIR/boxes"
    put_file proj/proj /usr/local/sbin/proj 755
    put_file proj/box-bootstrap.sh /usr/local/share/proj/box-bootstrap.sh 755
    # proj pushes these agent rules into every box (/etc/proj-rules/AGENTS.md).
    put /usr/local/share/proj/AGENTS-hosting.md 644 < "$REPO_DIR/docs/AGENTS-hosting.md"
    [ -e /var/log/proj.log ] || run install -m 640 /dev/null /var/log/proj.log
    # The one root command agents may run (sudo, no password, see agents_sudo).
    put_file sbin/proj-agent /usr/local/sbin/proj-agent 755
    [ -e /var/log/proj-agent.log ] || run install -m 640 -o root -g root /dev/null /var/log/proj-agent.log
    # Both logs grow with every call: weekly, 12 kept (about 3 months), compressed.
    put /etc/logrotate.d/proj 644 <<'EOF'
# Managed by setup.sh (step 70-hosting).
/var/log/proj.log /var/log/proj-agent.log {
    weekly
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF
}

# proj-agent without sudo (owner decision 2026-11-12): sandboxed agents (no_new_privs) cannot use
# sudo, but they can connect to a socket. /run/proj-agent.sock, root:SHARED_GROUP 0660: only the
# main user and the agent user reach it. Accept=yes: one short-lived root process per call
# (proj-agent-socket serve): it reads the caller's uid from the kernel (SO_PEERCRED), checks the
# group, and runs the same /usr/local/sbin/proj-agent allow-list with the argv as a list, no
# shell. A normal user's `proj-agent ...` is the client. sudo proj-agent keeps working.
# Hardening: only what proj and incus still work with (they write /srv, /var/log, /var/backups,
# /root/.config/incus and talk to the incus socket); no new privileges, no kernel tunables.
proj_agent_socket() {
    local g=${SHARED_GROUP:-devs}
    run install -d -m 755 /usr/local/lib/proj-agent
    put_file sbin/proj-agent-socket /usr/local/lib/proj-agent/proj-agent-socket 755
    put /etc/systemd/system/proj-agent.socket 644 <<EOF
# Managed by setup.sh (step 70-hosting). proj-agent without sudo, for group $g only.
[Unit]
Description=proj-agent socket (agents' allow-listed root commands, no sudo)

[Socket]
ListenStream=/run/proj-agent.sock
SocketUser=root
SocketGroup=$g
SocketMode=0660
Accept=yes
MaxConnections=16
MaxConnectionsPerSource=8
PollLimitIntervalSec=2s
PollLimitBurst=40
RemoveOnStop=yes

[Install]
WantedBy=sockets.target
EOF
    unit_changed
    put /etc/systemd/system/proj-agent@.service 644 <<'EOF'
# Managed by setup.sh (step 70-hosting). One call of proj-agent through the socket, as root.
[Unit]
Description=proj-agent call (via socket)
After=incus.service

[Service]
Type=exec
ExecStart=/usr/bin/python3 -I /usr/local/lib/proj-agent/proj-agent-socket serve
StandardInput=socket
StandardOutput=journal
StandardError=journal
User=root
RuntimeMaxSec=3720
TimeoutStopSec=15
KillMode=control-group
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=-/root/.config/incus -/root/.cache
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
SystemCallArchitectures=native
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
MemoryMax=512M
TasksMax=128
EOF
    unit_changed
    if [ "$UNITS" = 1 ] && ! dry; then systemctl daemon-reload; UNITS=0; fi
    enable_unit proj-agent.socket --now
}

# Workspaces (owner decision 2026-11-11): agents run on the host and edit a box's code in
# WORK_ROOT/<box>, which is /srv/app inside the box (disk device, shift=true). proj makes one per
# box; this step makes the root (root:SHARED_GROUP 750: the group may look, only proj adds) and
# .trash (root 700, workspaces of wiped boxes). Both host users are in SHARED_GROUP.
# shift=true shows host uid N as uid N in the box, so MAIN_USER must be uid 1000 (dev in a box).
workspaces() {
    local root=${WORK_ROOT:-/srv/proj/work} g=${SHARED_GROUP:-devs} u uid
    log "workspaces $root (root:$g 750, one folder per box made by proj, = /srv/app in the box)"
    apt_install acl git
    getent group "$g" >/dev/null || run groupadd "$g"
    for u in "$MAIN_USER" "${AGENT_USER:-}"; do
        [ -n "$u" ] && id "$u" >/dev/null 2>&1 || continue
        id -nG "$u" | tr ' ' '\n' | grep -qx "$g" || run usermod -aG "$g" "$u"
    done
    [ -d "$root" ] || run mkdir -p "$root"
    [ "$(stat -c %U:%G "$root" 2>/dev/null)" = "root:$g" ] || run chown "root:$g" "$root"
    [ "$(stat -c %a "$root" 2>/dev/null)" = 750 ] || run chmod 750 "$root"
    [ -d "$root/.trash" ] || run install -d -m 700 -o root -g root "$root/.trash"
    workspace_nosuid "$root"
    # SECURITY: boxes can write .git/config and .git/hooks in their workspace. /usr/local/bin/git
    # (before /usr/bin in PATH) turns hooks and fsmonitor off there and refuses repo configs that can
    # start a program. Everywhere else it is plain /usr/bin/git.
    sed "s|@WORK_ROOT@|$root|" "$REPO_DIR/files/sbin/git-workspace-guard" | put /usr/local/bin/git 755
    # git refuses a repository owned by another user: AGENT_USER works in MAIN_USER's checkouts.
    git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$root/*" \
        || run git config --system --add safe.directory "$root/*"
    uid=$(id -u "$MAIN_USER" 2>/dev/null || echo "?")
    [ "$uid" = 1000 ] || warn "$MAIN_USER has uid $uid, not 1000: proj refuses workspaces (the box shows host uid N as uid N, dev is 1000). See docs/HOSTING.md."
}

# workspace_nosuid ROOT: SECURITY. The workspace device uses shift=true, so root inside a box
# writes files owned by real uid 0 on the host. A setuid-root file made in a box would then run as
# root on the host (proven 2026-11-12). ROOT is bind-mounted onto itself with nosuid,nodev before
# Incus starts: the host ignores setuid bits and device files there. Hard dependency: incus.service and incus.socket Require= the mount (drop-ins),
# so when the mount fails, Incus does not start at all. proj doctor and proj selftest check this.
workspace_nosuid() {
    local root=$1 unit opts u
    unit="$(systemd-escape -p --suffix=mount "$root")"
    put "/etc/systemd/system/$unit" 644 <<EOF
# Managed by setup.sh (step 70-hosting). Box root writes real uid 0 here (shift=true):
# no setuid programs and no device files may work on the host.
[Unit]
Description=proj workspaces without setuid or device files
Before=incus.service incus.socket
After=local-fs-pre.target

[Mount]
What=$root
Where=$root
Type=none
Options=bind,nosuid,nodev

[Install]
WantedBy=local-fs.target
EOF
    for u in incus.service incus.socket; do
        put "/etc/systemd/system/$u.d/10-workspace-nosuid.conf" 644 <<EOF
# Managed by setup.sh (step 70-hosting). SECURITY: Incus starts only after $root is mounted
# nosuid,nodev. If that mount fails, Incus does not start (and no box runs).
[Unit]
Requires=$unit
After=$unit
EOF
    done
    if dry; then info "[dry-run] systemctl daemon-reload; enable + start $unit"; return 0; fi
    systemctl daemon-reload
    systemctl enable -q "$unit"
    opts=$(findmnt -no OPTIONS -M "$root" 2>/dev/null || true)
    if [ -z "$opts" ]; then
        systemctl start "$unit"
    elif [[ ",$opts," != *,nosuid,* || ",$opts," != *,nodev,* ]]; then
        # Never restart the unit here: Incus Requires= it, a restart would restart Incus (and
        # stop every box). A remount changes only the flags.
        mount -o remount,bind,nosuid,nodev "$root"
    fi
    opts=$(findmnt -no OPTIONS -M "$root" 2>/dev/null || true)
    [[ ",$opts," == *,nosuid,* && ",$opts," == *,nodev,* ]] \
        || die "$root is not mounted nosuid,nodev (got '$opts'): boxes could plant setuid-root files"
    info "$root mounted nosuid,nodev; incus.service and incus.socket require it"
    for u in incus.service incus.socket; do
        systemctl show -p Requires --value "$u" | tr ' ' '\n' | grep -qxF "$unit" \
            || die "$u does not Require= $unit after daemon-reload"
    done
    # Report only. A root chmod here could be sent through a symlink an agent swaps in between
    # find and chmod; on a nosuid mount the bits do nothing on the host anyway.
    find "$root" -xdev -type f -perm /6000 -print 2>/dev/null | head -n 20 \
        | sed 's/^/   WARN setuid\/setgid file (does nothing here, nosuid): /' || true
}

# host.env AGENT_SUDO_ALLOW (default "proj-agent", owner decision 2026-11-11): MAIN_USER and
# AGENT_USER may run /usr/local/sbin/proj-agent as root without a password. Nothing else: no
# general sudo for agents. "" = no agent sudo at all (our file is removed).
#
# File name zzz-agents-proj, on purpose: sudo reads /etc/sudoers.d in sorted order and the LAST
# matching rule wins. zz-server-main-password (step 10, --drop-main-sudo) says MAIN_USER needs a
# password for ALL, and ALL also matches proj-agent. "zzz-a" sorts after "zz-s" ("z" > "-"), so
# this NOPASSWD rule comes later and wins for this one command; everything else keeps the password.
AGENTS_SUDOERS=/etc/sudoers.d/zzz-agents-proj
AGENTS_SUDOERS_HEADER='# Managed by ~/.dotfiles setup.sh (step 70-hosting): host.env AGENT_SUDO_ALLOW'

agents_sudo_remove() {
    [ -e "$AGENTS_SUDOERS" ] || return 0
    if grep -qF "$AGENTS_SUDOERS_HEADER" "$AGENTS_SUDOERS"; then
        info "$1: removing $AGENTS_SUDOERS"
        run rm -f "$AGENTS_SUDOERS"
        dry || visudo -c >/dev/null || die "visudo check failed after removing $AGENTS_SUDOERS"
    else
        warn "$AGENTS_SUDOERS was written by hand: left as is. To remove it: sudo rm $AGENTS_SUDOERS"
    fi
}

agents_sudo() {
    local allow=${AGENT_SUDO_ALLOW-proj-agent} users="" u tmp
    case "$allow" in
        proj-agent) ;;
        "") log "agents: no sudo at all (AGENT_SUDO_ALLOW is empty)"; agents_sudo_remove "AGENT_SUDO_ALLOW is empty"; return 0 ;;
        *) die "AGENT_SUDO_ALLOW must be proj-agent or empty, not '$allow'" ;;
    esac
    for u in "$MAIN_USER" "${AGENT_USER:-}"; do
        [ -n "$u" ] || continue
        [[ "$u" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "user name '$u' is not valid for sudoers"
        if ! id "$u" >/dev/null 2>&1; then
            info "$u does not exist (yet): not in $AGENTS_SUDOERS"
            continue
        fi
        case ",$users," in *",$u,"*) continue ;; esac
        users=${users:+$users,}$u
    done
    if [ -z "$users" ]; then
        agents_sudo_remove "no agent user exists"
        return 0
    fi
    log "agents ($users): sudo without password for /usr/local/sbin/proj-agent only"
    tmp=$(mktemp)
    cat > "$tmp" <<EOF
$AGENTS_SUDOERS_HEADER="proj-agent".
# $users may run ONE command as root without a password: /usr/local/sbin/proj-agent, a strict
# allow-list (new try/mvp box, list, snapshot, doctor, logs, status, restart inside a box,
# exec / ports / url inside a box: commands run there as dev, never as root, never on the host).
# Agents have no other sudo. Everything else: they give the owner the exact command.
# Name: sudo reads /etc/sudoers.d in sorted order and the LAST matching rule wins. This file must
# sort after zz-server-main-password ("zzz-a" > "zz-s"), or MAIN_USER would need a password here.
# proj-agent does not trust this environment either: it fixes PATH and runs every child with env -i.
# Undo: AGENT_SUDO_ALLOW="" in host.env and run step 70, or: sudo rm $AGENTS_SUDOERS
Defaults!/usr/local/sbin/proj-agent env_reset, secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
$users ALL=(root) NOPASSWD: /usr/local/sbin/proj-agent
EOF
    # The command-scoped Defaults line is the only part a sudo build might not know (sudo-rs).
    # Read-only check first; without it env_reset and secure_path still come from /etc/sudoers
    # (sudo-rs always resets the environment), and proj-agent cleans its own environment.
    if ! visudo -c -f "$tmp" >/dev/null 2>&1; then
        warn "visudo does not accept the 'Defaults!/usr/local/sbin/proj-agent' line: written without it"
        grep -v '^Defaults!' "$tmp" > "$tmp.2"
        mv "$tmp.2" "$tmp"
    fi
    put_sudoers "$AGENTS_SUDOERS" < "$tmp"
    rm -f "$tmp"
}

# "Where am I?" marker for agents: /etc/proj-host on the host, /etc/proj-box in every box (proj).
host_marker() {
    log "marker /etc/proj-host (agents: you are on the host)"
    put /etc/proj-host 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 70-hosting). Read by agents and hooks: where am I?
host=${SERVER_NAME:-$(hostname)}
role=host
host: never build projects here, see /srv/proj/REGISTRY.md
EOF
}

# Host projects: run on the host, not in a box. proj lists and checks them, never changes them.
host_projects() {
    log "host projects (protected)"
    {
        echo "# Managed by ~/.dotfiles setup.sh (step 70-hosting) from host.env HOST_PROJECTS."
        echo "# name|tier|systemd unit to check (optional)|notes"
        local h
        for h in "${HOST_PROJECTS[@]:-}"; do [ -z "$h" ] || echo "$h"; done
    } | put /etc/proj/host-projects 644
    local n
    for h in "${HOST_PROJECTS[@]:-}"; do
        [ -n "$h" ] || continue
        n=${h%%|*}
        info "$n: protected host project"
        if ! dry && incus query "/1.0/instances/$n" >/dev/null 2>&1; then
            warn "a box is ALSO named $n. proj refuses to touch it; rename or remove it by hand."
        fi
    done
}

timers() {
    log "timers: proj-backup (long boxes) ${PROJ_BACKUP_TIME:-07:15}, proj-expire ${PROJ_EXPIRE_TIME:-09:00}"
    put /etc/systemd/system/proj-backup.service 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 70-hosting).
[Unit]
Description=Back up long-term proj boxes to ${BACKUP_DIR:-/var/backups}/boxes
After=incus.service
RequiresMountsFor=${BACKUP_DIR:-/var/backups}

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/proj backup --long
Nice=10
IOSchedulingClass=idle
EOF
    unit_changed
    put /etc/systemd/system/proj-backup.timer 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 70-hosting). Before backup-mirror, which copies it to the backup disk.
[Unit]
Description=Back up long-term proj boxes at ${PROJ_BACKUP_TIME:-07:15}

[Timer]
OnCalendar=*-*-* ${PROJ_BACKUP_TIME:-07:15}
RandomizedDelaySec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
    unit_changed
    put /etc/systemd/system/proj-expire.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 70-hosting).
[Unit]
Description=Warn, stop and delete expired try boxes
After=incus.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/proj expire
EOF
    unit_changed
    put /etc/systemd/system/proj-expire.timer 644 <<EOF
# Managed by ~/.dotfiles setup.sh (step 70-hosting).
[Unit]
Description=Expire try boxes daily at ${PROJ_EXPIRE_TIME:-09:00}

[Timer]
OnCalendar=*-*-* ${PROJ_EXPIRE_TIME:-09:00}
Persistent=true

[Install]
WantedBy=timers.target
EOF
    unit_changed
}

# incus-admin = full control of Incus = root on the host: the admin user only.
# (Group "incus" = a per-user socket only. Nobody here needs it.)
groups_check() {
    local admin=${ADMIN_USER:-admin} u
    if id "$admin" >/dev/null 2>&1 && getent group incus-admin >/dev/null \
        && ! id -nG "$admin" | tr ' ' '\n' | grep -qx incus-admin; then
        run usermod -aG incus-admin "$admin"
    fi
    for u in $(getent group incus-admin 2>/dev/null | cut -d: -f4 | tr ',' ' '); do
        [ "$u" = "$admin" ] && continue
        warn "$u is in incus-admin (= root on the host). Remove: sudo gpasswd -d $u incus-admin"
    done
}

main "$@"
