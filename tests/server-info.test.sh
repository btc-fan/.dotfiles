#!/usr/bin/env bash
# Offline tests for files/bin/server-info (Linux: GNU timeout). Fake files under a temp root
# (SERVER_INFO_ROOT) and fake commands on PATH. Checks: the sections, the short form (at most
# 15 lines), speed (under 2 s with a hanging agent CLI), and that no IP address, URL or webhook
# from host.env ever shows up. Run as a normal user: bash tests/server-info.test.sh
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/.." && pwd)
command -v timeout >/dev/null || { echo "needs GNU timeout (Linux)"; exit 1; }
command -v jq >/dev/null || { echo "needs jq"; exit 1; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
R=$T/root
mkdir -p "$R/etc/server" "$R/srv/proj" "$R/var/lib/server-info" "$R/var/run" "$R/data" "$R/backup" "$T/bin"
cat > "$R/etc/server/host.env" <<'EOF'
SERVER_NAME="testbox"             # hostname
MAIN_USER="alice"
LAN_CIDR="192.168.77.0/24"
NIC="enp9s0"
AGENT_USER="hermes"
DATA_MOUNT="/data"
BACKUP_MOUNT="/backup"
SETUP_REPO_URL="https://example.invalid/secret-repo.git"
PG_BACKUP_SKIP_DBS="bigdb"
EOF
printf 'host=testbox\nrole=host\n' > "$R/etc/proj-host"
cat > "$R/srv/proj/REGISTRY.json" <<'EOF'
{"boxes":[{"name":"radar","tier":"long","state":"Running","expires":null},
          {"name":"trybox","tier":"try","state":"Stopped","expires":"2026-12-01T10:00:00Z"}],
 "host_projects":[{"name":"md999"}]}
EOF
now=$(date +%s)
echo "$((now - 7200)) 1234" > "$R/var/lib/server-info/pg-appdb"
echo "missing" > "$R/var/lib/server-info/pg-bigdb"
touch "$R/var/run/reboot-required"

cat > "$T/bin/systemctl" <<'EOF'
#!/bin/bash
case "$*" in *--failed*) printf 'a.service loaded failed failed A\nb.service loaded failed failed B\n' ;; esac
EOF
cat > "$T/bin/zpool" <<'EOF'
#!/bin/bash
echo "boxes	ONLINE	3%"
EOF
printf '#!/bin/bash\necho "up 2 days, 3 hours"\n' > "$T/bin/uptime"
printf '#!/bin/bash\necho "2.1.311 (Claude Code)"\n' > "$T/bin/claude"
printf '#!/bin/bash\nsleep 10; echo never\n' > "$T/bin/codex"
printf '#!/bin/bash\nexit 0\n' > "$T/bin/pgrep"
printf '#!/bin/bash\n[ "$1" = hermes ] && exit 0; exec /usr/bin/id "$@"\n' > "$T/bin/id"
cat > "$T/bin/ai-info" <<'EOF'
#!/bin/bash
if [ "${1:-}" = --short ]; then echo "ai short ok"; else echo "== ai"; echo "ai layer ok"; fi
EOF
printf '#!/bin/bash\nexit 1\n' > "$T/bin/sudo"
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH"
export SERVER_INFO_ROOT=$R

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }
has() { grep -qF -- "$2" <<< "$1" && ok || bad "missing '$2'"; }

start=$(date +%s%N)
full=$(bash "$REPO/files/bin/server-info"); rc=$?
ms=$(( ($(date +%s%N) - start) / 1000000 ))
[ "$rc" = 0 ] && ok || bad "exit $rc"
[ "$ms" -lt 2000 ] && ok || bad "full output took $ms ms (a hanging CLI must be cut at 1.5 s)"
has "$full" "== testbox"
has "$full" "role: host: one Incus box per project"
has "$full" "failed units: 2"
has "$full" "reboot needed: YES"
has "$full" "ZFS: boxes ONLINE 3%"
has "$full" "appdb 2 h"
has "$full" "bigdb not there yet"
has "$full" "radar  long  Running"
has "$full" "trybox  try  Stopped  until 2026-12-01"
has "$full" "md999  (host project, not a box)"
has "$full" "claude 2.1.311 (Claude Code)"
has "$full" "codex installed"
has "$full" "hermes gateway: running"
has "$full" "sudo proj-agent exec <box> -- <command>"
has "$full" "sudo /opt/server-setup/setup.sh --update"
has "$full" "sudo /opt/ai-setup/install.sh --update --for-user <user>"
has "$full" "/etc/proj-rules/AGENTS.md"
has "$full" "ai layer ok"

short=$(bash "$REPO/files/bin/server-info" --short)
n=$(printf '%s\n' "$short" | wc -l)
[ "$n" -le 15 ] && ok || bad "short form has $n lines"
has "$short" "boxes 2: radar (long), trybox (try to 12-01)"
has "$short" "failed units 2, reboot needed YES"
has "$short" "server-info"
has "$short" "ai short ok"

for out in "$full" "$short"; do
    if grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}|https?://|enp9s0|example\.invalid|webhook' <<< "$out"; then
        bad "an address, URL or private value leaked: $(grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}|https?://[^ ]*|enp9s0' <<< "$out" | head -3)"
    else ok; fi
done

printf 'name=radar\ntier=long\n' > "$R/etc/proj-box"
out=$(bash "$REPO/files/bin/server-info" --short)
has "$out" "inside box radar"

echo "server-info tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
