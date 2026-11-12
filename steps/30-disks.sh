#!/usr/bin/env bash
# Disks from host.env (by serial): mount by UUID with nofail, format only empty disks with --format.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

ROOT_DISK=$(lsblk -rsno NAME,TYPE "$(findmnt -no SOURCE /)" | awk '$2=="disk" {print $1; exit}')

main() {
    apt_install parted e2fsprogs smartmontools
    local entry serial label mnt role
    if [ -z "${DISKS[*]:-}" ]; then
        log "no DISKS in host.env: nothing to do"
        return 0
    fi
    for entry in "${DISKS[@]}"; do
        IFS='|' read -r serial label mnt role <<< "$entry"
        [ -n "$serial" ] && [ -n "$label" ] && [ -n "$mnt" ] || die "bad DISKS line: $entry (need SERIAL|LABEL|MOUNT|ROLE)"
        handle_disk "$serial" "$label" "$mnt" "$role"
    done
    if ! dry; then systemctl daemon-reload; fi
    write_disk_roles
}

dev_for_serial() {
    lsblk -dnro NAME,SERIAL | awk -v s="$1" '$2==s {print "/dev/"$1; exit}'
}

partitions() {
    lsblk -rno NAME,TYPE "$1" | awk '$2=="part" {print "/dev/"$1}'
}

handle_disk() {
    local serial=$1 label=$2 mnt=$3 role=$4 dev part fstype uuid cur parts=()
    log "disk $label ($serial) -> $mnt"
    dev=$(dev_for_serial "$serial")
    if [ -z "$dev" ]; then
        warn "not found. Skipped. The fstab line (if any) has nofail, so boot does not wait."
        return 0
    fi
    [ "${dev#/dev/}" != "$ROOT_DISK" ] || die "$dev is the system disk. Remove it from DISKS."
    mapfile -t parts < <(partitions "$dev")

    if [ "${#parts[@]}" -eq 0 ]; then
        # Whole disk without partitions. Format only when it is truly empty and --format was given.
        if wipefs -n "$dev" 2>/dev/null | grep -q .; then
            wipefs -n "$dev" | sed 's/^/   /'
            die "REFUSE: $dev has data signatures but no partitions. Check it by hand."
        fi
        if [ "$FORMAT" != 1 ]; then
            warn "$dev is empty. To format it: sudo /opt/server-setup/setup.sh --only disks --format"
            return 0
        fi
        info "formatting $dev: GPT, one ext4 partition, label $label"
        run parted -s "$dev" mklabel gpt mkpart "$label" ext4 1MiB 100%
        run udevadm settle
        if dry; then
            info "would run: mkfs.ext4 -q -L $label -m 1 <first partition of $dev>"
            return 0
        fi
        mapfile -t parts < <(partitions "$dev")
        [ "${#parts[@]}" -eq 1 ] || die "partition of $dev did not appear"
        mkfs.ext4 -q -L "$label" -m 1 "${parts[0]}"
        udevadm settle
    fi

    if [ "${#parts[@]}" -eq 1 ]; then
        part=${parts[0]}
    else
        part=$(for p in "${parts[@]}"; do
            [ "$(blkid -s LABEL -o value "$p" 2>/dev/null)" = "$label" ] && echo "$p"
        done | head -1)
        [ -n "$part" ] || die "$dev has ${#parts[@]} partitions and none has label $label"
    fi

    fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || true)
    case "$fstype" in
        ext4|xfs|btrfs) ;;
        *) die "$part has filesystem '${fstype:-none}'. Expected ext4, xfs or btrfs." ;;
    esac
    uuid=$(blkid -s UUID -o value "$part")

    # Both checks come BEFORE fstab is touched: a wrong disk must never get the mount point.
    # 1. Something already mounted on MOUNT must be this very filesystem.
    local src cur rename
    src=$(findmnt -no SOURCE --mountpoint "$mnt" 2>/dev/null || true)
    if [ -n "$src" ] && [ "$(blkid -s UUID -o value "$src" 2>/dev/null || true)" != "$uuid" ]; then
        die "REFUSE: $mnt is already mounted from $src, not from $part. fstab not changed. Fix by hand."
    fi
    # 2. The filesystem label must match host.env: the serial picked the disk, the label proves
    #    it is the filesystem you meant (a swapped or reused disk fails here).
    cur=$(blkid -s LABEL -o value "$part" 2>/dev/null || true)
    if [ "$cur" != "$label" ]; then
        case "$fstype" in
            ext4) rename="sudo e2label $part $label" ;;
            xfs) rename="sudo xfs_admin -L $label $part (unmounted)" ;;
            btrfs) rename="sudo btrfs filesystem label $part $label" ;;
        esac
        die "REFUSE: $part label is '${cur:-none}', host.env says '$label'. fstab not changed. If this IS the right disk: $rename, then run again."
    fi

    set_fstab "$uuid" "$mnt" "$fstype" "$label" "$role"

    # Mount now if not mounted. Never unmount or move a disk that is in use.
    if [ -z "$src" ]; then
        run install -d -m 755 "$mnt"
        run mount "$mnt"
    fi
    info "$part ($fstype, UUID $uuid) on $mnt"
}

# One fstab line per disk, by UUID: nofail (boot never waits for a missing disk),
# 90 s device timeout (an HDD can be slow to spin up after a power cut), noatime.
# Old lines for the same mount point or UUID are commented out.
set_fstab() {
    local uuid=$1 mnt=$2 fstype=$3 label=$4 role=$5 line tmp conflicts
    line="UUID=$uuid $mnt $fstype noatime,nofail,x-systemd.device-timeout=90s 0 2"
    conflicts=$(awk -v u="UUID=$uuid" -v m="$mnt" -v l="$line" \
        '!/^[[:space:]]*#/ && NF && ($1 == u || $2 == m) && $0 != l' /etc/fstab)
    if grep -qxF "$line" /etc/fstab && [ -z "$conflicts" ]; then
        return 0
    fi
    tmp=$(mktemp)
    awk -v u="UUID=$uuid" -v m="$mnt" -v l="$line" -v label="$label" -v role="$role" -v stamp="$(date +%F)" '
        index($0, "# setup disk " label ":") == 1 { next }
        /^[[:space:]]*#/ || NF == 0 { print; next }
        $0 == l { next }
        ($1 == u || $2 == m) { print "# replaced by setup.sh " stamp ": " $0; next }
        { print }
        END { printf "# setup disk %s: %s\n%s\n", label, role, l }
    ' /etc/fstab > "$tmp"
    findmnt --verify --tab-file "$tmp" >/dev/null 2>&1 || warn "findmnt --verify reports issues in the new fstab (often only a missing mount dir)"
    if ! dry; then cp -a /etc/fstab "/etc/fstab.bak-$(date +%F-%H%M%S)"; fi
    put /etc/fstab 644 < "$tmp"
    rm -f "$tmp"
}

# DISK-ROLES.md on the data disk: who is who, for a human with a screwdriver.
# Only the block between the markers is generated; your own notes outside it stay.
write_disk_roles() {
    local dm=${DATA_MOUNT:-}
    [ -n "$dm" ] && mountpoint -q "$dm" || { info "DATA_MOUNT not mounted: DISK-ROLES.md skipped"; return 0; }
    local f="$dm/DISK-ROLES.md" block tmp entry serial label mnt role dev model size health
    block=$(
        echo "<!-- setup:begin (generated by ~/.dotfiles setup.sh step 30-disks; edit host.env, not this block) -->"
        echo "# Disk roles"
        echo
        echo "| Mount | Label | Role | Model | Size | Serial | SMART |"
        echo "|---|---|---|---|---|---|---|"
        dev="/dev/$ROOT_DISK"
        echo "| / | system | Ubuntu, Docker images | $(lsblk -dno MODEL "$dev" | xargs) | $(lsblk -dno SIZE "$dev" | xargs) | $(lsblk -dno SERIAL "$dev" | xargs) | $(smart_health "$dev") |"
        for entry in "${DISKS[@]}"; do
            IFS='|' read -r serial label mnt role <<< "$entry"
            dev=$(dev_for_serial "$serial")
            if [ -n "$dev" ]; then
                model=$(lsblk -dno MODEL "$dev" | xargs); size=$(lsblk -dno SIZE "$dev" | xargs); health=$(smart_health "$dev")
            else
                model="(not connected)"; size="-"; health="-"
            fi
            echo "| $mnt | $label | $role | $model | $size | $serial | $health |"
        done
        echo
        echo "All HDDs: spin-down off (hdd-no-spindown.service). Data disks mount with nofail:"
        echo "the server boots without them. Backups: see step 60-backups in the dotfiles README."
        echo "<!-- setup:end -->"
    )
    tmp=$(mktemp)
    if [ -f "$f" ] && grep -q '^<!-- setup:begin' "$f" && grep -q '^<!-- setup:end' "$f"; then
        { sed '/^<!-- setup:begin/,$d' "$f"; printf '%s\n' "$block"; sed '1,/^<!-- setup:end/d' "$f"; } > "$tmp"
    else
        { echo "$block"; [ -f "$f" ] && { echo; cat "$f"; }; } > "$tmp"
    fi
    put "$f" 644 < "$tmp"
    rm -f "$tmp"
}

smart_health() {
    smartctl -H "$1" 2>/dev/null | awk -F': ' '/overall-health|Health Status/ {print $2; exit}' | xargs || true
}

main "$@"
