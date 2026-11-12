#!/usr/bin/env bash
# The host-side work of proj (as done for proj-agent calls) under the SAME sandbox settings as
# proj-agent@.service, read from steps/70-hosting.sh. Catches a hardening option that breaks
# proj (2026-11-12: RestrictSUIDSGID made "chmod 2775" on a new workspace fail).
#   as root (admin: sudo bash tests/proj-agent-unit.test.sh): every option, in a system unit
#     (systemd-run), working in WORK_ROOT/.unit-test-<pid> like proj does, plus an incus query;
#   as a normal user: only the options a user unit can apply (seccomp: no mounts), in a temp dir.
# Also a negative check: the same work with RestrictSUIDSGID=yes must fail, so the test can see it.
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/.." && pwd)
command -v systemd-run >/dev/null || { echo "needs systemd-run (Linux)"; exit 1; }

# The [Service] options of proj-agent@.service, as step 70 writes them.
mapfile -t props < <(awk '
    /put \/etc\/systemd\/system\/proj-agent@\.service/ {u = 1; next}
    u && /^EOF$/ {exit}
    u && /^\[Service\]/ {s = 1; next}
    u && s && /^[A-Za-z]+=/ {print}' "$REPO/steps/70-hosting.sh" \
    | grep -vE '^(Type|ExecStart|StandardInput|StandardOutput|StandardError|User|RuntimeMaxSec|TimeoutStopSec|KillMode)=')
[ "${#props[@]}" -ge 5 ] || { echo "could not read the unit options from steps/70-hosting.sh"; exit 1; }

if [ "$(id -u)" = 0 ]; then
    mode=root
    # shellcheck source=/dev/null
    . /etc/server/host.env
    G=${SHARED_GROUP:-devs}
    MU=$MAIN_USER
    D=${WORK_ROOT:-/srv/proj/work}/.unit-test-$$
    run=(systemd-run --quiet --wait --pipe --collect)
else
    mode=user
    G=$(id -gn); MU=$(id -un)
    D=$(mktemp -d)/w
    run=(systemd-run --user --quiet --wait --pipe --collect)
    user_ok='^(NoNewPrivileges|RestrictSUIDSGID|RestrictRealtime|LockPersonality|SystemCallArchitectures|RestrictAddressFamilies)='
    mapfile -t props < <(printf '%s\n' "${props[@]}" | grep -E "$user_ok")
fi
cleanup() { rm -rf -- "$D"; [ "$mode" = root ] || rm -rf -- "$(dirname "$D")"; rm -f /var/log/proj-unit-test.log 2>/dev/null; }
trap cleanup EXIT
mkdir -p "$D"

# The work, as proj does it on the host (ws_make, ws_acl, ws_fix_modes, registry, lock, log).
cat > "$D/work.sh" <<'EOF'
set -e
D=$1 G=$2 MU=$3 MODE=$4
as_main() { if [ "$MODE" = root ]; then runuser -u "$MU" -- "$@"; else "$@"; fi; }
mkdir "$D/ws"
[ "$MODE" != root ] || chown "$MU:$G" "$D/ws"
chmod 2775 "$D/ws"
setfacl -m "g:$G:rwx" "$D/ws"
setfacl -d -m "u::rwx,g::rwx,g:$G:rwx,o::rx" "$D/ws"
as_main mkdir "$D/ws/sub"
as_main chmod g+s "$D/ws/sub"
as_main sh -c 'echo code > "$1/sub/main.py"' sh "$D/ws"
t=$(mktemp); echo registry > "$t"; mv "$t" "$D/REGISTRY.json"
exec 7> "$D/x.lock"; flock -w 2 7
if [ "$MODE" = root ]; then
    mkdir -p /run/lock/proj && touch /run/lock/proj/.unit-test && rm -f /run/lock/proj/.unit-test
    echo test >> /var/log/proj-unit-test.log
    incus query /1.0 > /dev/null
fi
echo ALL-OK
EOF
args=()
for p in "${props[@]}"; do args+=(-p "$p"); done

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }

echo "== $mode mode, ${#props[@]} unit options: ${props[*]}"
out=$("${run[@]}" "${args[@]}" bash "$D/work.sh" "$D" "$G" "$MU" "$mode" 2>&1)
grep -qx ALL-OK <<< "$out" && ok || bad "proj's host work fails under the unit options: $out"

rm -rf -- "$D/ws" "$D/REGISTRY.json"
out=$("${run[@]}" "${args[@]}" -p RestrictSUIDSGID=yes bash "$D/work.sh" "$D" "$G" "$MU" "$mode" 2>&1)
grep -qx ALL-OK <<< "$out" && bad "negative check: RestrictSUIDSGID=yes did not fail (the test cannot see the bug)" || ok

echo "proj-agent unit tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
