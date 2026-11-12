#!/usr/bin/env bash
# Offline tests for files/sbin/proj-agent-socket (Linux: SO_PEERCRED). A tiny accept loop stands
# in for systemd (Accept=yes: one "serve" process per connection, the connection on stdin), and a
# fake proj-agent prints what it got. Run as a normal user: bash tests/proj-agent-socket.test.sh
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/.." && pwd)
[ "$(uname -s)" = Linux ] || { echo "needs Linux (SO_PEERCRED)"; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "run as a normal user"; exit 1; }

T=$(mktemp -d)
SRV=$REPO/files/sbin/proj-agent-socket
SOCK=$T/s.sock
cleanup() { [ -z "${LOOP:-}" ] || kill "$LOOP" 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT

cat > "$T/agent" <<EOF
#!/bin/bash
case "\$1" in
    list) echo "LIST by \$PROJ_AGENT_CALLER via \$PROJ_AGENT_VIA" ;;
    rc3) echo "bad thing" >&2; exit 3 ;;
    stream) echo first; sleep 2; echo second ;;
    sleep) echo \$\$ > "$T/agent.pid"; sleep 60 ;;
    args) shift; printf '<%s>\n' "\$@" ;;
    flood) echo \$\$ > "$T/flood.pid"; exec yes flooding-the-client ;;
    env) env | sort ;;
esac
EOF
chmod +x "$T/agent"
id -gn > "$T/group"

# The accept loop: like systemd's Accept=yes.
cat > "$T/loop.py" <<'EOF'
import os, socket, subprocess, sys
sock, srv, gfile = sys.argv[1:4]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(sock); s.listen(8)
while True:
    c, _ = s.accept()
    env = dict(os.environ, PROJ_AGENT_GROUP=open(gfile).read().strip())
    subprocess.Popen([sys.executable, "-I", srv, "serve"], stdin=c, env=env, stderr=subprocess.DEVNULL)
    c.close()
EOF
export PROJ_AGENT_SOCKET_TEST=1 PROJ_AGENT_SOCK=$SOCK PROJ_AGENT_BIN=$T/agent
python3 "$T/loop.py" "$SOCK" "$SRV" "$T/group" & LOOP=$!
for _ in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }
call() { python3 -I "$SRV" call "$@"; }

out=$(call list 2>&1); rc=$?
[ "$rc" = 0 ] && [ "$out" = "LIST by $(id -un) via socket" ] && ok || bad "list: rc=$rc out=$out"

out=$(call rc3 2>&1); rc=$?
[ "$rc" = 3 ] && grep -qx "bad thing" <<< "$out" && ok || bad "exit code / stderr passthrough: rc=$rc out=$out"
out=$(call rc3 2>/dev/null); [ -z "$out" ] && ok || bad "stderr came out on stdout: $out"

call stream > "$T/stream.out" 2>&1 & c=$!
sleep 1
[ "$(cat "$T/stream.out")" = first ] && ok || bad "output is not streamed (after 1 s: $(cat "$T/stream.out"))"
wait "$c"
[ "$(tr '\n' ' ' < "$T/stream.out")" = "first second " ] && ok || bad "stream end: $(cat "$T/stream.out")"

out=$(call args '$(touch '"$T"'/pwned)' 'a b;c' '' 'x"y' 2>&1)
[ "$out" = "<\$(touch $T/pwned)>
<a b;c>
<>
<x\"y>" ] && [ ! -e "$T/pwned" ] && ok || bad "arguments changed or a shell ran: $out"

out=$(call env 2>&1)
grep -qx "PROJ_AGENT_CALLER=$(id -un)" <<< "$out" && ! grep -q '^HOME=' <<< "$out" && ok || bad "child env not clean: $out"

big=$(head -c 70000 /dev/zero | tr '\0' a)
out=$(call args "$big" 2>&1); rc=$?
[ "$rc" = 2 ] && grep -q "too big" <<< "$out" && ok || bad "client must refuse 70 KB: rc=$rc"

raw() { python3 -I -c 'import socket,sys
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.sendall(sys.stdin.buffer.read())
print(s.makefile("rb").read().decode(errors="replace"))' "$SOCK"; }
out=$(head -c 70000 /dev/zero | tr '\0' a | raw)
grep -q "refused: request too big" <<< "$out" && grep -q '^X2$' <<< "$out" && ok || bad "server must refuse a 70 KB request: $(head -c 200 <<< "$out")"
out=$(printf 'not json\n' | raw)
grep -q "not valid JSON" <<< "$out" && ok || bad "bad JSON not refused: $out"
out=$(printf '{"v":1,"argv":["list",5]}\n' | raw)
grep -q "must be text" <<< "$out" && ok || bad "non-text argument not refused: $out"

echo nosuchgroup-zz > "$T/group"
out=$(call list 2>&1); rc=$?
[ "$rc" = 2 ] && grep -q "is not in group nosuchgroup-zz" <<< "$out" && ok || bad "a user outside the group must be refused: rc=$rc out=$out"
id -gn > "$T/group"

python3 -I "$SRV" call sleep >/dev/null 2>&1 & c=$!   # not the call function: kill must reach python
for _ in $(seq 1 30); do [ -s "$T/agent.pid" ] && break; sleep 0.1; done
kill "$c" 2>/dev/null; wait "$c" 2>/dev/null
sleep 3
p=$(cat "$T/agent.pid" 2>/dev/null)
[ -n "$p" ] && ! kill -0 "$p" 2>/dev/null && ok || bad "the command kept running after the client went away (pid $p)"

# A client that sends the request and then never reads: the root process must not hang on it.
kill "$LOOP"; wait "$LOOP" 2>/dev/null; rm -f "$SOCK"
PROJ_AGENT_SEND_TIMEOUT=2 python3 "$T/loop.py" "$SOCK" "$SRV" "$T/group" & LOOP=$!
for _ in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
python3 -I -c 'import socket,sys,time
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.sendall(b"{\"v\":1,\"argv\":[\"flood\"]}\n"); time.sleep(12)' "$SOCK" &
stall=$!
sleep 8
p=$(cat "$T/flood.pid" 2>/dev/null)
[ -n "$p" ] && ! kill -0 "$p" 2>/dev/null && ok || bad "a client that stops reading kept the command running (pid $p)"
kill "$stall" 2>/dev/null; wait "$stall" 2>/dev/null

kill "$LOOP"; wait "$LOOP" 2>/dev/null; rm -f "$SOCK"
PROJ_AGENT_RUN_TIMEOUT=2 python3 "$T/loop.py" "$SOCK" "$SRV" "$T/group" & LOOP=$!
for _ in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
rm -f "$T/agent.pid"
out=$(call sleep 2>&1); rc=$?
[ "$rc" != 0 ] && grep -q "ran longer than 2 s" <<< "$out" && ok || bad "run time limit: rc=$rc out=$out"

rm -f "$SOCK"
out=$(call list 2>&1); rc=$?
[ "$rc" = 1 ] && grep -q "cannot reach" <<< "$out" && ok || bad "no socket: rc=$rc out=$out"

echo "proj-agent-socket tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
