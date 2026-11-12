#!/usr/bin/env bash
# 24/7: no sleep, no HDD spin-down, watchdog, reboot on panic, fsck repair, kdump, Wake-on-LAN.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

UNITS_CHANGED=0
note_unit() { if changed; then UNITS_CHANGED=1; fi; }
reboot_needed() { run touch /var/run/reboot-required; }

main() {
    apt_install hdparm ethtool smartmontools
    block_sleep
    setup_logind
    persistent_journal
    disable_spindown
    install_caffeinate
    setup_watchdog
    setup_panic_reboot
    setup_kdump
    setup_grub
    setup_wol
    setup_wait_online
    no_multipathd
    if [ "$UNITS_CHANGED" = 1 ]; then run systemctl daemon-reload; fi
    wait_online_reset
}

# Nothing can put the machine to sleep: the targets are masked and sleep.conf says no.
block_sleep() {
    log "sleep, suspend, hibernate: masked"
    local t
    for t in sleep suspend hibernate hybrid-sleep suspend-then-hibernate; do
        [ "$(systemctl is-enabled "$t.target" 2>/dev/null || true)" = masked ] || run systemctl mask "$t.target"
    done
    put /etc/systemd/sleep.conf.d/10-server.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on): 24/7 server, never sleep.
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
EOF
}

# Keys, lid and idle never sleep. The power key does a clean poweroff.
setup_logind() {
    log "logind: power key = clean poweroff, everything else ignored"
    put /etc/systemd/logind.conf.d/10-server.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on).
[Login]
HandlePowerKey=poweroff
HandleSuspendKey=ignore
HandleHibernateKey=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
    if changed; then
        # A logind restart can end sessions; reload is safe. Without reload support: next boot.
        run systemctl reload systemd-logind 2>/dev/null || info "logind change applies after reboot"
    fi
}

# The boot message (step 50) needs the old boot logs to tell power cut from clean shutdown.
persistent_journal() {
    log "journal: persistent, max 1 GB"
    put /etc/systemd/journald.conf.d/10-server.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on).
[Journal]
Storage=persistent
SystemMaxUse=1G
EOF
    if changed; then
        run install -d -m 2755 -g systemd-journal /var/log/journal
        run systemctl restart systemd-journald
    fi
}

disable_spindown() {
    log "HDD spin-down off (hdd-no-spindown.service)"
    # Old udev rule from the first build: dracut copied it into the initrd. Remove it once.
    if [ -f /etc/udev/rules.d/69-hdd-no-spindown.rules ]; then
        remove_legacy /etc/udev/rules.d/69-hdd-no-spindown.rules
        run udevadm control --reload
        if command -v update-initramfs >/dev/null; then run update-initramfs -u -k all; fi
    fi
    put_file sbin/hdd-no-spindown /usr/local/sbin/hdd-no-spindown 755
    put /etc/systemd/system/hdd-no-spindown.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on).
[Unit]
Description=Turn off HDD spin-down
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/hdd-no-spindown

[Install]
WantedBy=multi-user.target
EOF
    note_unit
    if changed; then
        run systemctl daemon-reload
        run systemctl start hdd-no-spindown.service
    fi
    enable_unit hdd-no-spindown.service
}

install_caffeinate() {
    log "/usr/local/bin/caffeinate (systemd-inhibit wrapper)"
    put_file bin/caffeinate /usr/local/bin/caffeinate 755
}

# Hardware watchdog: if the kernel or systemd hangs, the board resets itself.
setup_watchdog() {
    log "watchdog: iTCO_wdt (softdog fallback), RuntimeWatchdogSec=30s"
    put_file sbin/load-watchdog /usr/local/sbin/load-watchdog 755
    put /etc/systemd/system/load-watchdog.service 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on).
# Load the hardware watchdog early so systemd can ping it.
[Unit]
Description=Load hardware watchdog (iTCO_wdt, softdog fallback)
DefaultDependencies=no
Before=sysinit.target
ConditionPathExists=!/dev/watchdog0

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/load-watchdog

[Install]
WantedBy=sysinit.target
EOF
    note_unit
    # Unit name from the first build.
    if [ -f /etc/systemd/system/itco-watchdog.service ]; then
        run systemctl disable itco-watchdog.service
        remove_legacy /etc/systemd/system/itco-watchdog.service
        UNITS_CHANGED=1
    fi
    remove_legacy /etc/modules-load.d/watchdog.conf
    if [ "$UNITS_CHANGED" = 1 ]; then run systemctl daemon-reload; UNITS_CHANGED=0; fi
    enable_unit load-watchdog.service
    [ -e /dev/watchdog0 ] || run /usr/local/sbin/load-watchdog

    put /etc/systemd/system.conf.d/10-watchdog.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on): systemd pings the hardware watchdog.
# No ping for 30 s = hard reset. A stuck reboot is forced after 10 min.
[Manager]
RuntimeWatchdogSec=30s
RebootWatchdogSec=10min
EOF
    if changed; then run systemctl daemon-reexec; fi
    info "$(cat /sys/class/watchdog/watchdog0/identity 2>/dev/null || echo 'no watchdog device yet')"
}

# Kernel panic, oops or soft lockup: reboot after 10 s (kdump saves a dump first if it can).
setup_panic_reboot() {
    log "sysctl: reboot 10 s after a kernel panic"
    put /etc/sysctl.d/61-panic-reboot.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh (step 20-always-on).
kernel.panic = 10
kernel.panic_on_oops = 1
kernel.softlockup_panic = 1
EOF
    if changed; then run sysctl --system >/dev/null; fi
}

# kdump: after a kernel crash a small second kernel saves a dump to /var/crash, then reboots.
# The boot message (step 50) reads /var/crash to report "crash".
setup_kdump() {
    log "kdump-tools"
    if ! dpkg-query -W -f='${Status}' kdump-tools 2>/dev/null | grep -q 'install ok installed'; then
        run sh -c "echo 'kdump-tools kdump-tools/use_kdump boolean true' | debconf-set-selections"
        apt_install kdump-tools
        reboot_needed
    fi
    enable_unit kdump-tools
}

# After a power cut, fsck repairs the disk by itself instead of waiting at a prompt.
# After a failed boot, GRUB never waits more than 5 s at its menu.
setup_grub() {
    log "GRUB: fsck.repair=yes, recordfail timeout 5 s"
    local g=/etc/default/grub new
    new=$(sed -E '/^GRUB_CMDLINE_LINUX_DEFAULT=/{/fsck\.repair=yes/!s/"$/ fsck.repair=yes"/;s/=" /="/;}' "$g")
    grep -q '^GRUB_RECORDFAIL_TIMEOUT=' <<< "$new" || new=$(printf '%s\nGRUB_RECORDFAIL_TIMEOUT=5' "$new")
    if [ "$new" != "$(cat "$g")" ]; then
        [ -e "$g.bak-setup" ] || run cp -a "$g" "$g.bak-setup"
        put "$g" 644 <<< "$new"
        run update-grub
        reboot_needed
    fi
    grep -E '^GRUB_(CMDLINE_LINUX_DEFAULT|TIMEOUT|RECORDFAIL_TIMEOUT)=' "$g" | sed 's/^/   /'
}

# Wake-on-LAN: a manual way to start the box if the BIOS does not power on after a cut.
setup_wol() {
    log "Wake-on-LAN on $NIC"
    if ethtool "$NIC" 2>/dev/null | grep -q 'Supports Wake-on:.*g'; then
        ethtool "$NIC" | grep -q '^[[:space:]]*Wake-on: g' || run ethtool -s "$NIC" wol g
    else
        warn "$NIC does not support Wake-on-LAN (magic packet)"
        return 0
    fi
    # Netplan merges files. Only add ours when another file already defines this NIC by name.
    local f named=0
    for f in /etc/netplan/*.yaml; do
        [ -f "$f" ] && [ "$f" != /etc/netplan/90-wol.yaml ] || continue
        if grep -qs "^[[:space:]]*$NIC:" "$f"; then named=1; fi
    done
    if [ "$named" = 1 ]; then
        put /etc/netplan/90-wol.yaml 600 <<EOF
# Managed by ~/.dotfiles setup.sh (step 20-always-on): Wake-on-LAN, merged with the installer file.
network:
  version: 2
  ethernets:
    $NIC:
      wakeonlan: true
EOF
        if changed; then run netplan generate; fi
    else
        warn "$NIC is not named in /etc/netplan/*.yaml: WoL is set for this boot only"
    fi
    ethtool "$NIC" | grep -i 'wake-on' | sed 's/^/   /'
}

# Boot waits for the network at most WAIT_ONLINE_TIMEOUT seconds (default 30), not 2 minutes.
# Found on the server (2026-11-11, boot after a power cut): the NIC got its link only 235 s after
# boot, because the router came back after the server. systemd-networkd-wait-online waited its
# full 2 min, failed, and the boot carried a failed unit. Waiting longer helps nothing: services
# that need the network (Docker, Incus, boot-notify) cope with a late network, and boot-notify
# itself waits up to 15 min for DNS. Netplan's generated ExecStart lines are replaced (drop-in
# 50-*, sorts after netplan's 10-netplan.conf): wait for NIC routable, 30 s, and a timeout is not
# a failure ("-" prefix), so a slow router never marks the boot red. A real network problem
# still shows: boot-notify reports how late the network came.
setup_wait_online() {
    local t=${WAIT_ONLINE_TIMEOUT:-30}
    log "network wait at boot: $NIC routable, at most ${t}s, a timeout is not a failure"
    put /etc/systemd/system/systemd-networkd-wait-online.service.d/50-server.conf 644 <<EOF
# Managed by setup.sh (step 20-always-on). Why: a router that comes back after a power cut later
# than the server (seen: 235 s) made this wait 2 min and fail. Now: $NIC routable, ${t}s, and a
# timeout does not fail the unit. Services that need the network cope with a late one.
[Service]
ExecStart=
ExecStart=-/usr/lib/systemd/systemd-networkd-wait-online -i $NIC:routable --timeout=$t
EOF
    note_unit
}

# multipathd: for SAN disks with several paths. This box has plain local disks, nothing uses
# it, and its control socket (/run/multipathd.socket, mode 666) has had root bugs. Stopped and
# masked (a package upgrade cannot start it again) unless a multipath device exists or host.env
# KEEP_MULTIPATHD=yes. Undo: sudo systemctl unmask --now multipathd.socket multipathd.service
no_multipathd() {
    systemctl cat multipathd.service >/dev/null 2>&1 || return 0
    if is_yes "${KEEP_MULTIPATHD:-no}"; then info "multipathd kept (KEEP_MULTIPATHD=yes)"; return 0; fi
    if lsblk -rno TYPE 2>/dev/null | grep -qx mpath; then
        warn "a multipath device exists: multipathd left running"
        return 0
    fi
    log "multipathd off (local disks only; masked)"
    local u
    for u in multipathd.socket multipathd.service; do
        [ "$(systemctl is-enabled "$u" 2>/dev/null || true)" = masked ] && continue
        run systemctl stop "$u" 2>/dev/null || true
        run systemctl mask "$u"
    done
    # The daemon leaves its 666 socket file behind (no listener after the stop): remove it, so
    # nothing can mistake it for a live service. Only when nothing listens on it.
    if [ -S /run/multipathd.socket ] && ! systemctl is-active -q multipathd.service multipathd.socket \
        && ! ss -xlH 2>/dev/null | grep -qF /run/multipathd.socket; then
        info "remove the stale /run/multipathd.socket"
        run rm -f /run/multipathd.socket
    fi
}

# The unit failed on an earlier boot: clear that state once the fix is in, so the failed-unit
# checks (verify, proj doctor, digest) start clean.
wait_online_reset() {
    if [ "$(systemctl show -p Result --value systemd-networkd-wait-online.service 2>/dev/null)" != success ] \
        && [ -f /etc/systemd/system/systemd-networkd-wait-online.service.d/50-server.conf ]; then
        run systemctl reset-failed systemd-networkd-wait-online.service
    fi
}

main "$@"
