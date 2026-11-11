#!/usr/bin/env bash
# box-bootstrap.sh: runs as root INSIDE a new box (pushed and started by `proj`).
# Makes the standard box: user dev (uid 1000, sudo inside the box), /srv/app, /srv/data,
# base tools, and on request Docker and/or PostgreSQL with data on /srv/data.
# Usage (inside the box): box-bootstrap.sh <box-name> <docker yes|no> <pg yes|no> [shared-gid] [shared-group]
# /srv/app is normally the workspace from the host (proj mounts it first): then it is left as is.
# shared-gid: the host's shared group (devs). dev joins a group with that gid, so dev may write
# files that the host agent user made in the workspace. Safe to run again.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8

box=${1:?box name}
docker=${2:-no}
pg=${3:-no}
shared_gid=${4:-}
shared_group=${5:-devs}

# Wait for the network (DHCP on incusbr0 can take a few seconds after start).
for _ in $(seq 1 60); do
    if getent hosts archive.ubuntu.com >/dev/null 2>&1; then break; fi
    sleep 2
done

apt-get update -q
apt-get install -y -q sudo git tmux curl ca-certificates jq rsync bubblewrap socat locales

# User dev = uid 1000. If the image already has a uid 1000 user (for example "ubuntu"), rename it.
if ! id dev >/dev/null 2>&1; then
    other=$(getent passwd 1000 | cut -d: -f1 || true)
    if [ -n "$other" ]; then
        usermod -l dev -d /home/dev -m "$other"
        groupmod -n dev "$other" 2>/dev/null || true
    else
        useradd -m -u 1000 -s /bin/bash dev
    fi
fi
echo "dev ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/10-dev
chmod 440 /etc/sudoers.d/10-dev

# The workspace mount belongs to the host (owner, group, setgid, ACL): never chown or chmod it.
if mountpoint -q /srv/app; then
    echo "/srv/app is the workspace from the host: left as is"
else
    install -d -o dev -g dev -m 755 /srv/app
fi
if [[ "$shared_gid" =~ ^[0-9]+$ ]]; then
    g=$(getent group "$shared_gid" | cut -d: -f1 || true)
    if [ -z "$g" ]; then
        getent group "$shared_group" >/dev/null && g=proj-shared || g=$shared_group
        groupadd -g "$shared_gid" "$g"
    fi
    id -nG dev | tr ' ' '\n' | grep -qx "$g" || usermod -aG "$g" dev
fi
install -d -m 755 /srv/data
chown dev:dev /srv/data

if [ "$docker" = yes ] && ! command -v docker >/dev/null; then
    # Docker from the Ubuntu archive inside the box. The box profile "docker" allows nesting.
    apt-get install -y -q docker.io docker-compose-v2
    usermod -aG docker dev
    systemctl enable --now docker
fi

if [ "$pg" = yes ]; then
    db=${box//-/_}
    if ! command -v pg_lsclusters >/dev/null; then
        apt-get install -y -q postgresql-common
        sed -i -E 's/^#?[[:space:]]*create_main_cluster.*/create_main_cluster = false/' \
            /etc/postgresql-common/createcluster.conf
        apt-get install -y -q postgresql
    fi
    ver=$(ls /usr/lib/postgresql | sort -V | tail -1)
    if ! pg_lsclusters -h | awk '{print $1"-"$2}' | grep -qx "$ver-main"; then
        install -d -o postgres -g postgres -m 700 /srv/data/pg
        pg_createcluster "$ver" main -d "/srv/data/pg/$ver/main" --start -- --data-checksums
    fi
    systemctl enable --now "postgresql@$ver-main"
    sleep 2
    runuser -u postgres -- psql -XAtc "select 1 from pg_roles where rolname='dev'" | grep -q 1 \
        || runuser -u postgres -- createuser -s dev
    runuser -u postgres -- psql -XAtc "select 1 from pg_database where datname='$db'" | grep -q 1 \
        || runuser -u postgres -- createdb -O dev "$db"
    echo "postgres $ver: database $db, role dev (peer login: psql $db)"
fi
echo "bootstrap done: $box"
