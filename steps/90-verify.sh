#!/usr/bin/env bash
# Report: PASS / FAIL / INFO for everything the steps set up. Read only, except proj selftest.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env
set +e   # a failed check is a report line, not a stop

fails=0
p()   { printf '%-5s %s\n' "$1" "$2"; }
chk() {  # chk "label" command...
    local label=$1; shift
    if "$@" >/dev/null 2>&1; then p PASS "$label"; else p FAIL "$label"; fails=$((fails + 1)); fi
}
sh_chk() { chk "$1" bash -c "$2"; }
PG_VERSION=${PG_VERSION:-16}

# Step 70, AGENT_SUDO_ALLOW: agents may run proj-agent as root without a password, and nothing
# else without a password. Read only: sudo -n -l -U lists rules, it runs nothing.
agents_proj_checks() {
    local f=/etc/sudoers.d/zzz-agents-proj pa=/usr/local/sbin/proj-agent u got last
    sh_chk "proj-agent root:root 755" "[ \"\$(stat -c %U:%G:%a $pa)\" = root:root:755 ]"
    sh_chk "/var/log/proj-agent.log root 640" "[ \"\$(stat -c %U:%a /var/log/proj-agent.log)\" = root:640 ]"
    if [ "${AGENT_SUDO_ALLOW-proj-agent}" != proj-agent ]; then
        sh_chk "no $f (AGENT_SUDO_ALLOW is empty)" "[ ! -e $f ]"
        return 0
    fi
    if [ ! -e "$f" ]; then
        p INFO "$f not written (no agent user exists yet?)"
        return 0
    fi
    sh_chk "$f is valid (visudo)" "visudo -c -f $f"
    # The last matching rule wins: no other sudoers.d file may sort after ours (sudo skips names with . or ~).
    last=$(find /etc/sudoers.d -maxdepth 1 -type f ! -name '*.*' ! -name '*~' -printf '%f\n' | LC_ALL=C sort | tail -n 1)
    if [ "$last" = zzz-agents-proj ]; then p PASS "zzz-agents-proj sorts last in /etc/sudoers.d"
    else p FAIL "$last sorts after zzz-agents-proj in /etc/sudoers.d (the last rule wins)"; fails=$((fails + 1)); fi
    for u in "$MAIN_USER" "${AGENT_USER:-}"; do
        [ -n "$u" ] && id "$u" >/dev/null 2>&1 || continue
        chk "$u may run proj-agent (sudo -l)" sudo -n -l -U "$u" "$pa"
        got=$(sudo -n -l -U "$u" 2>/dev/null | nopasswd_effective | sort -u | tr '\n' ' ')
        got=${got% }
        if [ "$u" = "${AGENT_USER:-}" ] && [ "${AGENT_SUDO:-none}" = full ]; then
            p INFO "$u: AGENT_SUDO=full, passwordless sudo for everything ($got)"
        elif [ "$u" = "$MAIN_USER" ] && [ ! -f /etc/sudoers.d/zz-server-main-password ]; then
            p INFO "$MAIN_USER: passwordless sudo for: ${got:-nothing} (--drop-main-sudo not done)"
        elif [ "$got" = "$pa" ]; then
            p PASS "$u: the only passwordless sudo command is proj-agent"
        else
            p FAIL "$u: passwordless sudo for '${got:-nothing}', expected only $pa (sudo -l -U $u)"
            fails=$((fails + 1))
        fi
    done
}

echo "### setup copy"
sh_chk "/opt/server-setup is root-owned, nobody else can write" "[ \"\$(stat -c %U:%G /opt/server-setup)\" = root:root ] && [ -z \"\$(find /opt/server-setup \\( ! -user root -o -perm /022 \\) -print -quit)\" ]"
sh_chk "/etc/server/host.env root:root 644" "[ \"\$(stat -c %U:%G:%a $SERVER_ETC/host.env)\" = root:root:644 ]"

echo "### 10 security"
sh_chk "ssh: password login off" "sshd -T | grep -qx 'passwordauthentication no'"
sh_chk "ssh: root login off" "sshd -T | grep -qx 'permitrootlogin no'"
sh_chk "ssh: AllowUsers has $MAIN_USER" "sshd -T | grep -i '^allowusers' | grep -qw '$MAIN_USER'"
sh_chk "ssh: MaxAuthTries 3" "sshd -T | grep -qx 'maxauthtries 3'"
ADMIN_USER=${ADMIN_USER:-admin}
chk "admin user $ADMIN_USER exists" id "$ADMIN_USER"
sh_chk "ssh: AllowUsers has $ADMIN_USER" "sshd -T | grep -i '^allowusers' | grep -qw '$ADMIN_USER'"
sh_chk "$ADMIN_USER has an SSH key" "[ -s \"\$(getent passwd '$ADMIN_USER' | cut -d: -f6)/.ssh/authorized_keys\" ]"
sh_chk "$ADMIN_USER has passwordless sudo (valid sudoers file)" "visudo -c -f /etc/sudoers.d/10-server-admin"
if [ -f /etc/sudoers.d/zz-server-main-password ]; then
    p INFO "main user $MAIN_USER: sudo WITH password (--drop-main-sudo done)"
    sh_chk "$MAIN_USER not in docker group" "! id -nG '$MAIN_USER' | tr ' ' '\n' | grep -qx docker"
    # Added later to --drop-main-sudo: a hint until it runs again, not a FAIL.
    extra_groups=$(id -nG "$MAIN_USER" | tr ' ' '\n' | grep -xE 'lxd|adm|incus-admin' | tr '\n' ' ')
    [ -z "$extra_groups" ] || p INFO "$MAIN_USER still in: $extra_groups(run: sudo ./setup.sh --only security --drop-main-sudo)"
else
    p INFO "main user $MAIN_USER still has passwordless sudo (see README: --drop-main-sudo)"
fi
sh_chk "ssh safety timer NOT armed" "! systemctl is-active -q server-rollback.timer"
sh_chk "ufw active" "ufw status | grep -q 'Status: active'"
sh_chk "ufw: SSH from LAN $LAN_CIDR" "ufw status | grep -F '$LAN_CIDR' | grep -q '$SSH_PORT'"
sh_chk "fail2ban: sshd + recidive" "fail2ban-client status | grep -q sshd && fail2ban-client status | grep -q recidive"
sh_chk "fail2ban: growing bans" "grep -q '^bantime.increment = true' /etc/fail2ban/jail.local"
sh_chk "fail2ban: sshd jail reads sshd-session (OpenSSH 10)" "grep -q '_COMM=sshd-session' /etc/fail2ban/jail.local && grep -q 'sshd-session' /etc/fail2ban/filter.d/sshd.conf"
chk "unattended-upgrades active" systemctl is-active -q unattended-upgrades
sh_chk "no automatic reboot" "apt-config dump | grep -q 'Unattended-Upgrade::Automatic-Reboot \"false\"'"
chk "needrestart installed" command -v needrestart
sh_chk "needrestart never restarts postgresql, incus, docker" "grep -q 'qr(^postgresql)} = 0' /etc/needrestart/conf.d/50-auto.conf && grep -q 'qr(^incus)} = 0' /etc/needrestart/conf.d/50-auto.conf && grep -q 'qr(^docker)} = 0' /etc/needrestart/conf.d/50-auto.conf"
sh_chk "timezone $TIMEZONE" "[ \"\$(timedatectl show -p Timezone --value)\" = '$TIMEZONE' ]"
sh_chk "sysctl: rp_filter + syncookies" "[ \"\$(sysctl -n net.ipv4.conf.all.rp_filter)\" = 1 ] && [ \"\$(sysctl -n net.ipv4.tcp_syncookies)\" = 1 ]"
chk "tailscale installed" command -v tailscale
tailscale status >/dev/null 2>&1 && p INFO "tailscale: logged in" || p INFO "tailscale: NOT logged in (manual step: sudo tailscale up --hostname=$(hostname))"

echo "### 20 always on"
for t in sleep suspend hibernate hybrid-sleep suspend-then-hibernate; do
    sh_chk "$t.target masked" "systemctl is-enabled $t.target 2>&1 | grep -qx masked"
done
sh_chk "logind: power key = poweroff" "grep -qs 'HandlePowerKey=poweroff' /etc/systemd/logind.conf.d/10-server.conf"
sh_chk "journal is persistent" "[ -d /var/log/journal ] && journalctl --list-boots --no-pager | grep -q ."
chk "hdd-no-spindown enabled" systemctl is-enabled -q hdd-no-spindown.service
chk "caffeinate installed" test -x /usr/local/bin/caffeinate
chk "watchdog device present" test -e /dev/watchdog0
sh_chk "systemd pings the watchdog" "[ \"\$(systemctl show -p RuntimeWatchdogUSec --value)\" != 0 ]"
p INFO "watchdog: $(cat /sys/class/watchdog/watchdog0/identity 2>/dev/null || echo none)"
sh_chk "kernel.panic = 10" "[ \"\$(sysctl -n kernel.panic)\" = 10 ]"
sh_chk "fsck.repair=yes on kernel command line" "grep -q 'fsck.repair=yes' /proc/cmdline"
chk "kdump-tools active" systemctl is-active -q kdump-tools
sh_chk "crashkernel reserved" "grep -q crashkernel= /proc/cmdline"
sh_chk "Wake-on-LAN g on $NIC" "ethtool '$NIC' | grep -q '^[[:space:]]*Wake-on: g'"
p INFO "crash dumps in /var/crash: $(find /var/crash -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)"

echo "### 30 disks"
for entry in "${DISKS[@]:-}"; do
    [ -n "$entry" ] || continue
    IFS='|' read -r serial label mnt role <<< "$entry"
    chk "$mnt mounted ($label: $role)" mountpoint -q "$mnt"
    sh_chk "$mnt in fstab with nofail, 90 s device timeout" "awk '\$2==\"$mnt\" && /nofail/ && /x-systemd.device-timeout=90s/' /etc/fstab | grep -q ."
done
[ -z "${DATA_MOUNT:-}" ] || chk "DISK-ROLES.md on $DATA_MOUNT" test -s "$DATA_MOUNT/DISK-ROLES.md"

echo "### 40 tools"
for c in git curl jq tmux htop btop gh rg fzf ncdu uv; do chk "cmd $c" command -v "$c"; done
if is_yes "${INSTALL_DOCKER:-yes}"; then
    chk "docker running" systemctl is-active -q docker
    chk "docker compose" docker compose version
    sh_chk "docker default bind 127.0.0.1" "jq -e '.ip == \"127.0.0.1\"' /etc/docker/daemon.json"
    sh_chk "Ubuntu docker.io not installed" "! dpkg-query -W -f='\${Status}' docker.io 2>/dev/null | grep -q 'install ok installed'"
    [ -z "${DATA_MOUNT:-}" ] || sh_chk "docker volumes on $DATA_MOUNT" "findmnt --mountpoint /var/lib/docker/volumes | grep -q ."
    p INFO "published ports: $(docker ps --format '{{.Names}}={{.Ports}}' 2>/dev/null | tr '\n' ' ')"
fi
is_yes "${INSTALL_NODE:-yes}" && chk "node" command -v node
if is_yes "${INSTALL_POSTGRES:-yes}"; then
    chk "postgresql@$PG_VERSION-main running" systemctl is-active -q "postgresql@$PG_VERSION-main"
    sh_chk "postgres listens on localhost only" "runuser -u postgres -- psql -XAtc 'show listen_addresses' | grep -qx localhost"
    [ -z "${DATA_MOUNT:-}" ] || sh_chk "postgres data on $DATA_MOUNT" "runuser -u postgres -- psql -XAtc 'show data_directory' | grep -q '^$DATA_MOUNT/'"
    p INFO "databases: $(runuser -u postgres -- psql -XAtc "select string_agg(datname||'='||pg_size_pretty(pg_database_size(datname)), ', ') from pg_database where not datistemplate" 2>/dev/null)"
fi

echo "### 50 alerts"
chk "notify-failure for every service" test -f /etc/systemd/system/service.d/10-notify-failure.conf
sh_chk "handler does not alert on itself" "[ \"\$(readlink /etc/systemd/system/notify-failure@.service.d/10-notify-failure.conf)\" = /dev/null ]"
chk "smartd running" systemctl is-active -q smartmontools
sh_chk "smartd calls smartd-notify" "grep -q 'smartd-notify' /etc/smartd.conf"
sh_chk "smartd starts no self-tests (no -s schedule)" "! grep -v '^#' /etc/smartd.conf | grep -qE '(^|[[:space:]])-s[[:space:]]'"
chk "disk-usage-check timer" systemctl is-active -q disk-usage-check.timer
chk "boot-notify enabled" systemctl is-enabled -q boot-notify.service
sh_chk "SSH login hook in PAM" "grep -q ssh-login-notify /etc/pam.d/sshd"
for c in alerts info; do
    if [ -s "$SERVER_ETC/webhooks/$c.url" ]; then
        sh_chk "webhook $c is root-only (600)" "[ \"\$(stat -c %a $SERVER_ETC/webhooks/$c.url)\" = 600 ]"
    else
        p INFO "webhook $c not set: its alerts do nothing (sudo discord-notify --set $c)"
    fi
done

if [ -n "${AGENT_USER:-}" ]; then
    echo "### 55 shared users"
    chk "user $AGENT_USER exists" id "$AGENT_USER"
    sh_chk "$AGENT_USER not in the sudo/docker/adm groups" "! id -nG '$AGENT_USER' | tr ' ' '\n' | grep -qx -e sudo -e docker -e adm"
    # Default and owner decision: AGENT_SUDO=none, no file. With AGENT_SUDO=full a valid file is accepted.
    if [ "${AGENT_SUDO:-none}" = none ]; then
        sh_chk "$AGENT_USER has no sudoers file (AGENT_SUDO=none)" "[ ! -e /etc/sudoers.d/90-$AGENT_USER ]"
    elif [ -e "/etc/sudoers.d/90-$AGENT_USER" ]; then
        sh_chk "$AGENT_USER sudoers file is valid" "visudo -c -f /etc/sudoers.d/90-$AGENT_USER"
        p INFO "$AGENT_USER has full passwordless sudo (AGENT_SUDO=${AGENT_SUDO:-none}): root on this host"
    fi
    sh_chk "${WORK_DIR:-/work} is setgid ${SHARED_GROUP:-devs}" "[ \"\$(stat -c %G '${WORK_DIR:-/work}')\" = '${SHARED_GROUP:-devs}' ] && [ -g '${WORK_DIR:-/work}' ]"
fi

if [ -n "${BACKUP_DIR:-}" ]; then
    echo "### 60 backups"
    is_yes "${INSTALL_POSTGRES:-yes}" && chk "pg-backup timer" systemctl is-active -q pg-backup.timer
    [ -z "${WORK_DIR:-}" ] || chk "work-snapshot timer" systemctl is-active -q work-snapshot.timer
    if [ -n "${BACKUP_MOUNT:-}" ]; then
        chk "backup-mirror timer" systemctl is-active -q backup-mirror.timer
        p INFO "last mirror: $(cat "$BACKUP_MOUNT/data-backups/.last-mirror" 2>/dev/null || echo never)"
    fi
    p INFO "newest pg dump: $(ls -1d "$BACKUP_DIR"/postgres/20* 2>/dev/null | tail -1 || true)"
    for u in pg-backup work-snapshot backup-mirror; do
        r=$(systemctl show -p Result --value "$u.service" 2>/dev/null)
        if [ -n "$r" ] && [ "$r" != success ]; then
            p FAIL "last $u run: $r (journalctl -u $u)"
            fails=$((fails + 1))
        fi
    done
fi

if [ -n "${BOX_DISK_SERIAL:-}" ]; then
    echo "### 70 hosting"
    chk "incus running" systemctl is-active -q incus
    if [ "${INCUS_SOURCE:-ubuntu}" = zabbly ]; then
        sh_chk "incus from the Zabbly LTS repo" "apt-cache policy incus | grep -A1 '\\*\\*\\*' | grep -q pkgs.zabbly.com"
    else
        sh_chk "incus 6.0 LTS from the Ubuntu archive" "dpkg-query -W -f='\${Version}' incus | grep -Eq '^(1:)?6\\.0\\.'"
    fi
    chk "zfs pool boxes exists" zpool list boxes
    sh_chk "zfs pool boxes healthy" "zpool status -x boxes | grep -q 'is healthy'"
    for prof in box-base tier-try tier-mvp tier-long docker; do chk "profile $prof" incus profile show "$prof"; done
    sh_chk "box-base: isolated idmap" "incus profile get box-base security.idmap.isolated | grep -qx true"
    sh_chk "incusbr0 uses ACL box-egress" "incus network get incusbr0 security.acls | grep -qx box-egress"
    sh_chk "box memory budget set" "incus project get default limits.memory | grep -q ."
    sh_chk "ufw: boxes route out via $NIC only" "ufw show added | grep -qF 'route allow in on incusbr0 out on $NIC'"
    sh_chk "ufw: no blanket route rules for incusbr0" "! ufw show added | grep -qE 'route allow (in|out) on incusbr0 comment'"
    if command -v docker >/dev/null; then
        sh_chk "DOCKER-USER: replies to boxes accepted" "iptables -C DOCKER-USER -o incusbr0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT"
        sh_chk "DOCKER-USER: box traffic handed to ufw (RETURN, no blanket ACCEPT)" "iptables -C DOCKER-USER -i incusbr0 -j RETURN && ! iptables -C DOCKER-USER -i incusbr0 -j ACCEPT"
    fi
    chk "proj installed" test -x /usr/local/sbin/proj
    agents_proj_checks
    sh_chk "marker /etc/proj-host (root 644)" "[ \"\$(stat -c %U:%a /etc/proj-host)\" = root:644 ] && grep -q '^role=host' /etc/proj-host"
    chk "agent rules for boxes in /usr/local/share/proj" test -s /usr/local/share/proj/AGENTS-hosting.md
    sh_chk "REGISTRY.json is valid" "jq -e '.boxes and .host_projects' /srv/proj/REGISTRY.json"
    # Boxes made before markers existed: a hint, not a FAIL (fix: sudo proj sync-rules --all).
    nomark=""
    for b in $(incus list -f json 2>/dev/null | jq -r '.[] | select(.status == "Running" and .config["user.proj.tier"] != null) | .name'); do
        incus exec "$b" -- test -f /etc/proj-box 2>/dev/null || nomark="$nomark $b"
    done
    [ -z "$nomark" ] || p INFO "boxes without /etc/proj-box:$nomark (sudo proj sync-rules --all)"
    chk "proj-backup timer" systemctl is-active -q proj-backup.timer
    chk "proj-expire timer" systemctl is-active -q proj-expire.timer
    sh_chk "incus-admin holds only $ADMIN_USER" "[ -z \"\$(getent group incus-admin | cut -d: -f4 | tr ',' '\n' | grep -vx '$ADMIN_USER')\" ]"
    sh_chk "box-base NIC: port isolation + ACL" "incus profile device get box-base eth0 security.port_isolation | grep -qx true && incus profile device get box-base eth0 security.acls | grep -qx box-egress"
    p INFO "boxes: $(incus list -c n -f csv 2>/dev/null | tr '\n' ' ')"
    chk "proj doctor" /usr/local/sbin/proj doctor
    # Not read-only: launches one throwaway try box and deletes it (about 1 min).
    chk "proj selftest: fresh box gets DHCP + DNS + internet, home gateway blocked" /usr/local/sbin/proj selftest
fi

echo "### system"
p INFO "uptime: $(uptime -p), load $(cut -d' ' -f1-3 /proc/loadavg), free memory $(free -h | awk '/Mem/ {print $7}')"
p INFO "disk use: $(df -h --output=target,pcent / ${DATA_MOUNT:-} ${BACKUP_MOUNT:-} 2>/dev/null | tail -n +2 | tr -s ' ' | tr '\n' ';')"
p INFO "failed units: $(systemctl --failed --no-legend --plain | awk '{print $1}' | tr '\n' ' ')"
p INFO "pending updates: $(apt list --upgradable 2>/dev/null | tail -n +2 | wc -l)"
p INFO "reboot needed: $([ -f /var/run/reboot-required ] && echo yes || echo no)"

echo
if [ "$fails" -gt 0 ]; then
    echo "verify: $fails FAIL line(s). Fix them, then: sudo ./setup.sh --only verify"
    exit 1
fi
echo "verify: all PASS"
