#!/usr/bin/env bash
# Base tools, Docker CE + Compose, uv, Node LTS, PostgreSQL (PGDG) with data on the data disk.
# shellcheck source=../lib/common.sh
. "$(dirname "$0")/../lib/common.sh"
need_root
load_env

KEYS=/etc/apt/keyrings
PG_VERSION=${PG_VERSION:-16}
DATA_MOUNT=${DATA_MOUNT:-}
APT_CHANGED=0

main() {
    run install -d -m 755 "$KEYS"
    install_base
    add_repos
    shell_comforts
    if is_yes "${INSTALL_DOCKER:-yes}"; then setup_docker; fi
    if is_yes "${INSTALL_NODE:-yes}"; then apt_install nodejs; fi
    install_uv
    if is_yes "${INSTALL_DOCKER:-yes}"; then install_lazydocker; fi
    if is_yes "${INSTALL_POSTGRES:-yes}"; then setup_postgres; fi
    report
}

# Distro packages. fd and bat have Debian names; add the usual short names.
install_base() {
    log "base packages"
    # shellcheck disable=SC2086
    apt_install git curl jq tmux htop btop build-essential ethtool ripgrep fd-find fzf bat \
        lazygit ncdu iotop glances unzip rsync acl python3-venv ca-certificates gnupg \
        ${EXTRA_PACKAGES:-}
    [ "$(readlink /usr/local/bin/fd 2>/dev/null)" = /usr/bin/fdfind ] || run ln -sfn /usr/bin/fdfind /usr/local/bin/fd
    [ "$(readlink /usr/local/bin/bat 2>/dev/null)" = /usr/bin/batcat ] || run ln -sfn /usr/bin/batcat /usr/local/bin/bat
    # glances is wanted as a TUI only; the package also ships a web server daemon.
    if systemctl is-enabled -q glances.service 2>/dev/null; then
        run systemctl disable --now glances.service
    fi
}

# fetch_key URL DEST FINGERPRINT NAME [dearmor]: download a repo signing key, refuse it unless its
# primary key is FINGERPRINT (constants in lib/common.sh), write only if it changed.
fetch_key() {
    local url=$1 dst=$2 fpr=$3 name=$4 tmp
    tmp=$(mktemp)
    curl -fsSL "$url" -o "$tmp"
    check_key_fpr "$tmp" "$fpr" "$name"
    if [ "${5:-}" = dearmor ]; then
        gpg --dearmor --yes -o "$tmp.gpg" "$tmp"
        mv "$tmp.gpg" "$tmp"
    fi
    put "$dst" 644 < "$tmp"
    rm -f "$tmp"
    if changed; then APT_CHANGED=1; fi
}

repo() {  # repo FILE LINE
    put "/etc/apt/sources.list.d/$1" 644 <<< "$2"
    if changed; then APT_CHANGED=1; fi
}

# Official signed repos only: Docker, PGDG, GitHub CLI, NodeSource.
add_repos() {
    log "apt repos"
    . /etc/os-release
    if is_yes "${INSTALL_DOCKER:-yes}"; then
        fetch_key https://download.docker.com/linux/ubuntu/gpg "$KEYS/docker.asc" "$FPR_DOCKER" Docker
        repo docker.list "deb [arch=amd64 signed-by=$KEYS/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable"
    fi
    if is_yes "${INSTALL_POSTGRES:-yes}"; then
        fetch_key https://www.postgresql.org/media/keys/ACCC4CF8.asc "$KEYS/pgdg.asc" "$FPR_PGDG" PGDG
        repo pgdg.list "deb [signed-by=$KEYS/pgdg.asc] https://apt.postgresql.org/pub/repos/apt $VERSION_CODENAME-pgdg main"
    fi
    fetch_key https://cli.github.com/packages/githubcli-archive-keyring.gpg "$KEYS/githubcli.gpg" "$FPR_GITHUB_CLI" "GitHub CLI"
    repo github-cli.list "deb [arch=amd64 signed-by=$KEYS/githubcli.gpg] https://cli.github.com/packages stable main"
    if is_yes "${INSTALL_NODE:-yes}"; then
        local major=${NODE_MAJOR:-}
        if [ -z "$major" ]; then
            major=$(curl -fsSL https://nodejs.org/dist/index.json \
                | jq -r '[.[] | select(.lts != false)][0].version' | sed 's/^v//; s/\..*//')
        fi
        info "Node LTS major: $major"
        fetch_key https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key "$KEYS/nodesource.gpg" "$FPR_NODESOURCE" NodeSource dearmor
        repo nodesource.list "deb [signed-by=$KEYS/nodesource.gpg] https://deb.nodesource.com/node_$major.x nodistro main"
        put /etc/apt/preferences.d/nodesource 644 <<'EOF'
Package: nodejs
Pin: origin deb.nodesource.com
Pin-Priority: 600
EOF
        if changed; then APT_CHANGED=1; fi
    fi
    if [ "$APT_CHANGED" = 1 ]; then run apt-get update -q; fi
    apt_install gh
}

# The Mac sends LC_CTYPE=UTF-8, which is not a locale name on Linux. Map it to C.UTF-8.
shell_comforts() {
    log "shell: fix LC_CTYPE=UTF-8 sent by macOS terminals"
    put /etc/profile.d/00-fix-lc-ctype.sh 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh: macOS sends LC_CTYPE=UTF-8, not a Linux locale name.
[ "${LC_CTYPE:-}" = "UTF-8" ] && export LC_CTYPE=C.UTF-8
EOF
    local rc
    rc="$(getent passwd "$MAIN_USER" | cut -d: -f6)/.bashrc"
    if [ -f "$rc" ] && ! grep -q 'LC_CTYPE=C.UTF-8' "$rc"; then
        # Non-login shells (tmux) do not read profile.d.
        run sed -i '1i [ "${LC_CTYPE:-}" = "UTF-8" ] \&\& export LC_CTYPE=C.UTF-8' "$rc"
    fi
}

# Images and containers stay on the SSD (/var/lib/docker). Named volumes live on the data
# disk through a bind mount. Published ports bind to 127.0.0.1 unless a compose file names
# another address: Docker writes its own iptables rules and skips ufw.
setup_docker() {
    log "Docker CE + Compose"
    # Ubuntu's docker.io and Docker CE fight over the same files and units. Never mix them.
    if dpkg-query -W -f='${Status}' docker.io 2>/dev/null | grep -q 'install ok installed'; then
        die "REFUSE: Ubuntu's docker.io is installed. Move your containers off it and remove it first (apt-get remove docker.io)."
    fi
    if [ -n "$DATA_MOUNT" ]; then
        mountpoint -q "$DATA_MOUNT" || die "DATA_MOUNT $DATA_MOUNT is not mounted. Run step 30-disks first."
        if ! grep -q '[[:space:]]/var/lib/docker/volumes[[:space:]]' /etc/fstab; then
            if [ -d /var/lib/docker/volumes ] \
                && [ -n "$(ls -A /var/lib/docker/volumes 2>/dev/null | grep -vxE 'metadata.db|backingFsBlockDev' || true)" ]; then
                die "/var/lib/docker/volumes already holds volumes on the SSD. Move them to $DATA_MOUNT/docker-volumes by hand first."
            fi
            run install -d -m 711 /var/lib/docker
            run install -d -m 701 /var/lib/docker/volumes "$DATA_MOUNT/docker-volumes"
            local tmp
            tmp=$(mktemp)
            cat /etc/fstab > "$tmp"
            printf '# setup: Docker named volumes live on the data disk.\n%s\n' \
                "$DATA_MOUNT/docker-volumes /var/lib/docker/volumes none bind,nofail,x-systemd.requires-mounts-for=$DATA_MOUNT 0 0" >> "$tmp"
            dry || cp -a /etc/fstab "/etc/fstab.bak-$(date +%F-%H%M%S)"
            put /etc/fstab 644 < "$tmp"
            rm -f "$tmp"
            run systemctl daemon-reload
        fi
        findmnt --mountpoint /var/lib/docker/volumes >/dev/null || run mount /var/lib/docker/volumes
        put /etc/systemd/system/docker.service.d/10-data-disk.conf 644 <<'EOF'
# Managed by ~/.dotfiles setup.sh: never start Docker with the volumes on the SSD by mistake.
[Unit]
RequiresMountsFor=/var/lib/docker/volumes
EOF
        if changed; then run systemctl daemon-reload; fi
    fi

    # daemon.json is written BEFORE the first install, so a fresh Docker starts with it.
    local was_active=0
    systemctl is-active -q docker 2>/dev/null && was_active=1
    docker_daemon_json
    local daemon_changed=$CHANGED
    apt_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    enable_unit containerd --now
    enable_unit docker --now
    if [ "$daemon_changed" = 1 ] && [ "$was_active" = 1 ] && ! dry; then
        # Never restart a running Docker by surprise. reload applies live-restore and the
        # reloadable keys now; ip and log settings apply at the next Docker start.
        systemctl reload docker
        warn "daemon.json changed. ip and log settings apply at the next Docker restart:"
        warn "  sudo systemctl restart docker   (live-restore keeps containers running)"
    fi
    # After --drop-main-sudo (step 10) the main user stays OUT of the docker group:
    # the docker group is root on the host.
    if [ -f /etc/sudoers.d/zz-server-main-password ]; then
        info "$MAIN_USER not added to docker (main sudo was dropped; use the admin user)"
    elif ! id -nG "$MAIN_USER" | tr ' ' '\n' | grep -qx docker; then
        run usermod -aG docker "$MAIN_USER"
        info "$MAIN_USER must log in again to use docker without sudo"
    fi
}

# Our keys in /etc/docker/daemon.json. Other keys already in the file are kept (merged, ours win).
DOCKER_OURS='{"ip":"127.0.0.1","log-driver":"local","log-opts":{"max-size":"10m","max-file":"3"},"live-restore":true}'

# docker_daemon_json: compare by meaning (jq -S on both sides), not by bytes, so a file that only
# differs in spaces or key order is left alone. Refused (nothing written): a file that is not a
# JSON object, a data-root (images must stay where step 40 expects them), or a merged file that
# dockerd rejects (an unknown or misspelled key). Sets CHANGED like put.
docker_daemon_json() {
    local f=/etc/docker/daemon.json merged extra tmp
    CHANGED=0
    if ! command -v jq >/dev/null; then
        if dry; then info "would write $f (jq is not installed yet, compare skipped)"; CHANGED=1; return 0; fi
        die "jq is missing (base packages failed?)"
    fi
    if [ -s "$f" ]; then
        jq -e 'type == "object"' "$f" >/dev/null 2>&1 || die "REFUSE: $f is not a JSON object. Fix it by hand. Nothing changed."
        if jq -e 'has("data-root") or has("graph")' "$f" >/dev/null; then
            die "REFUSE: $f sets data-root. This setup keeps images on the system disk and volumes on DATA_MOUNT. Remove data-root by hand (and move the data) first. Nothing changed."
        fi
        extra=$(jq -r --argjson o "$DOCKER_OURS" '[keys[] | select(. as $k | $o | has($k) | not)] | join(" ")' "$f")
        [ -z "$extra" ] || warn "$f has keys this setup does not manage (kept as they are): $extra"
        merged=$(jq -S --argjson o "$DOCKER_OURS" '. * $o' "$f")
        if [ "$merged" = "$(jq -S . "$f")" ]; then
            info "$f: same content (compared with jq -S)"
            dry || chmod 644 "$f"
            return 0
        fi
    else
        merged=$(jq -S -n --argjson o "$DOCKER_OURS" '$o')
    fi
    if [ -n "${extra:-}" ] && command -v dockerd >/dev/null; then
        tmp=$(mktemp)
        printf '%s\n' "$merged" > "$tmp"
        if ! dockerd --validate --config-file "$tmp" >/dev/null 2>&1; then
            dockerd --validate --config-file "$tmp" 2>&1 | sed 's/^/   /' || true
            rm -f "$tmp"
            die "REFUSE: dockerd does not accept the merged $f (unknown key?). Nothing changed."
        fi
        rm -f "$tmp"
    fi
    put "$f" 644 <<< "$merged"
}

# gh_latest OWNER/REPO: newest release tag.
gh_latest() {
    curl -fsSL "https://api.github.com/repos/$1/releases/latest" | jq -r .tag_name
}

# uv from the GitHub release, checked against its published sha256.
install_uv() {
    log "uv"
    local ver tmp asset=uv-x86_64-unknown-linux-gnu
    # Pinned by default (host.env UV_VERSION); "latest" follows the newest release.
    ver=${UV_VERSION:-0.13.7}
    [ "$ver" != latest ] || ver=$(gh_latest astral-sh/uv)
    if command -v uv >/dev/null && [ "$(uv --version | awk '{print $2}')" = "$ver" ]; then
        info "uv $ver already installed"
        return 0
    fi
    if dry; then info "would install uv $ver to /usr/local/bin"; return 0; fi
    tmp=$(mktemp -d)
    curl -fsSL -o "$tmp/$asset.tar.gz" "https://github.com/astral-sh/uv/releases/download/$ver/$asset.tar.gz"
    curl -fsSL -o "$tmp/$asset.tar.gz.sha256" "https://github.com/astral-sh/uv/releases/download/$ver/$asset.tar.gz.sha256"
    (cd "$tmp" && sha256sum -c "$asset.tar.gz.sha256")
    tar -xzf "$tmp/$asset.tar.gz" -C "$tmp"
    install -m 755 "$tmp/$asset/uv" "$tmp/$asset/uvx" /usr/local/bin/
    rm -rf "$tmp"
    uv --version
}

# lazydocker from the GitHub release, checked against checksums.txt.
install_lazydocker() {
    log "lazydocker"
    local tag ver tmp file
    # Pinned by default (host.env LAZYDOCKER_VERSION, without the v); "latest" follows the newest.
    ver=${LAZYDOCKER_VERSION:-0.25.2}
    if [ "$ver" = latest ]; then tag=$(gh_latest jesseduffield/lazydocker); else tag=v${ver#v}; fi
    ver=${tag#v}
    if command -v lazydocker >/dev/null && lazydocker --version | grep -q "Version: $ver"; then
        info "lazydocker $ver already installed"
        return 0
    fi
    if dry; then info "would install lazydocker $ver to /usr/local/bin"; return 0; fi
    file="lazydocker_${ver}_Linux_x86_64.tar.gz"
    tmp=$(mktemp -d)
    curl -fsSL -o "$tmp/$file" "https://github.com/jesseduffield/lazydocker/releases/download/$tag/$file"
    curl -fsSL -o "$tmp/checksums.txt" "https://github.com/jesseduffield/lazydocker/releases/download/$tag/checksums.txt"
    (cd "$tmp" && grep " $file\$" checksums.txt | sha256sum -c -)
    tar -xzf "$tmp/$file" -C "$tmp" lazydocker
    install -m 755 "$tmp/lazydocker" /usr/local/bin/lazydocker
    rm -rf "$tmp"
}

# PostgreSQL from PGDG. Data on the data disk, listens on localhost only
# (reach it from another machine with an SSH tunnel). Data checksums on.
setup_postgres() {
    log "PostgreSQL $PG_VERSION"
    local base=/var/lib/postgresql cc=/etc/postgresql-common/createcluster.conf
    if [ -n "$DATA_MOUNT" ]; then
        mountpoint -q "$DATA_MOUNT" || die "DATA_MOUNT $DATA_MOUNT is not mounted. Run step 30-disks first."
        base=$DATA_MOUNT/postgresql
    fi
    local data=$base/$PG_VERSION/main

    # postgresql-common first, so its createcluster.conf exists before we change it:
    # no automatic cluster in the default place, we create ours on the data disk.
    apt_install postgresql-common
    if ! dry && ! grep -qx 'create_main_cluster = false' "$cc"; then
        if grep -qE '^#?[[:space:]]*create_main_cluster' "$cc"; then
            sed -i -E 's/^#?[[:space:]]*create_main_cluster.*/create_main_cluster = false/' "$cc"
        else
            echo "create_main_cluster = false" >> "$cc"
        fi
    fi
    apt_install "postgresql-$PG_VERSION" "postgresql-client-$PG_VERSION"

    put /etc/systemd/system/postgresql@.service.d/10-data-disk.conf 644 <<EOF
# Managed by ~/.dotfiles setup.sh: never start PostgreSQL without its data disk.
[Unit]
RequiresMountsFor=$base
EOF
    if changed; then run systemctl daemon-reload; fi

    local created=0
    if dry; then
        info "would create cluster $PG_VERSION/main in $data if missing"
        return 0
    fi
    install -d -o postgres -g postgres -m 700 "$base"
    if ! pg_lsclusters -h | awk '{print $1"-"$2}' | grep -qx "$PG_VERSION-main"; then
        pg_createcluster "$PG_VERSION" main -d "$data" --locale C.UTF-8 -- --data-checksums
        created=1
    fi
    local actual
    actual=$(pg_lsclusters -h | awk -v v="$PG_VERSION" '$1==v && $2=="main" {print $6}')
    [ "$actual" = "$data" ] || warn "cluster $PG_VERSION/main uses $actual, not $data. Left as is."

    put "/etc/postgresql/$PG_VERSION/main/conf.d/10-tuning.conf" 644 postgres:postgres < <(pg_tuning)
    local tuned=$CHANGED unit="postgresql@$PG_VERSION-main"
    # Only a cluster made by THIS run is enabled and started. An existing cluster that is
    # stopped or disabled was stopped on purpose (a move, a restore): setup never starts it.
    if [ "$created" = 1 ]; then
        enable_unit "$unit"
        systemctl restart "$unit"
    elif ! systemctl is-active -q "$unit"; then
        warn "$unit exists but is not running. Setup does not start it. When ready: sudo systemctl start $unit"
        [ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" = enabled ] \
            || warn "$unit is not enabled either (no start at boot): sudo systemctl enable $unit"
        return 0
    elif [ "$tuned" = 1 ]; then
        # Never restart a live database by surprise. Reload now; memory settings need a restart.
        systemctl reload "$unit"
        warn "tuning changed. shared_buffers needs: sudo systemctl restart $unit"
    fi
    [ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" = enabled ] \
        || warn "$unit runs but is not enabled (no start after a reboot): sudo systemctl enable $unit"
    sleep 2
    if ! runuser -u postgres -- psql -XAtc "select 1 from pg_roles where rolname='$MAIN_USER'" | grep -q 1; then
        runuser -u postgres -- createuser -s "$MAIN_USER"
    fi
    runuser -u postgres -- psql -XAtc "show data_directory; show listen_addresses; show data_checksums" | sed 's/^/   /'
}

# Memory from RAM size: shared_buffers about 1/7, effective_cache_size about 4/7.
# HDD or SSD from host.env PG_DISK.
pg_tuning() {
    local mb sb ec io rpc
    mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
    sb=$((mb / 7 / 256 * 256)); [ "$sb" -ge 256 ] || sb=256
    ec=$((mb * 4 / 7 / 256 * 256))
    if [ "${PG_DISK:-hdd}" = ssd ]; then io=200; rpc=1.1; else io=2; rpc=4; fi
    cat <<EOF
# Managed by ~/.dotfiles setup.sh: ${mb} MB RAM, data on ${PG_DISK:-hdd}.
# listen_addresses stays at the default: localhost only.
shared_buffers = ${sb}MB
effective_cache_size = ${ec}MB
maintenance_work_mem = 512MB
work_mem = 32MB
max_wal_size = 4GB
wal_compression = on
effective_io_concurrency = $io
random_page_cost = $rpc
EOF
}

report() {
    log "versions"
    local c
    for c in git gh docker node npm uv psql rg fd fzf bat lazygit lazydocker btop; do
        if command -v "$c" >/dev/null; then
            printf '   %-11s %s\n' "$c" "$("$c" --version 2>/dev/null | head -1)"
        else
            printf '   %-11s %s\n' "$c" "missing"
        fi
    done
}

main "$@"
