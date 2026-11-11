#!/usr/bin/env bash
# Offline tests for files/sbin/proj-agent: fake proj, incus, journalctl and systemctl on PATH.
# Run as a NORMAL user (test mode is ignored as root): bash tests/proj-agent.test.sh
# Also checks nopasswd_effective (lib/common.sh) on sample `sudo -l -U` listings, and the
# sudoers.d sort order that the zzz-agents-proj name relies on.
set -uo pipefail
export LC_ALL=C

REPO=$(cd "$(dirname "$0")/.." && pwd)
AGENT=$REPO/files/sbin/proj-agent
[ "$(id -u)" -ne 0 ] || { echo "run the tests as a normal user, not root"; exit 1; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
CALLS=$T/calls
LOGF=$T/proj-agent.log
HOSTP=$T/host-projects
printf '%s\n' '# name|tier|unit|notes' 'md999|long|md999-crawler.service|crawler on the host' > "$HOSTP"
printf '%s\n' demo web-1 > "$T/boxes"

# Each fake writes one line to $T/calls: its name, the environment that matters, its arguments.
# The path is baked in: proj-agent starts every child with env -i.
for tool in proj incus journalctl systemctl; do
    cat > "$T/bin/$tool" <<EOF
#!/bin/bash
if [ "\$(basename "\$0")" = incus ] && [ "\${1:-}" = query ]; then
    grep -qx "\${2#/1.0/instances/}" "$T/boxes"; exit
fi
printf '%s|SUDO_USER=%s|PAGER=%s|SYSTEMD_PAGER=[%s]|LESSSECURE=%s|EVIL=%s|%s\n' \\
    "\$(basename "\$0")" "\${SUDO_USER:-}" "\${PAGER:-}" "\${SYSTEMD_PAGER-unset}" "\${LESSSECURE:-}" "\${EVIL:-}" "\$*" >> "$CALLS"
EOF
    chmod +x "$T/bin/$tool"
done

pass=0 fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }

run_agent() {  # run_agent ARGS...: sets rc, out
    : > "$CALLS"
    out=$(env PATH="$T/bin:/usr/bin:/bin" PROJ_AGENT_TEST=1 PROJ_AGENT_LOG="$LOGF" \
        PROJ_AGENT_HOST_PROJECTS="$HOSTP" SUDO_USER=agent1 EVIL=1 bash -p "$AGENT" "$@" 2>&1)
    rc=$?
}

# allow "expected tool call" ARGS...: must exit 0 and make exactly that one call.
allow() {
    local want=$1; shift
    run_agent "$@"
    local got
    got=$(cut -d'|' -f1,7 "$CALLS")
    if [ "$rc" = 0 ] && [ "$got" = "$want" ]; then ok; else bad "allow [$*]: rc=$rc call='$got' want='$want' out=$out"; fi
}

# deny "text in the message" ARGS...: must exit 2, run nothing, say why.
deny() {
    local want=$1; shift
    run_agent "$@"
    if [ "$rc" = 2 ] && [ ! -s "$CALLS" ] && grep -qF -- "$want" <<< "$out"; then ok
    else bad "deny [$*]: rc=$rc calls='$(cat "$CALLS")' out=$out (wanted: $want)"; fi
}

echo "== allowed forms"
allow "proj|new demo2 --tier try" new demo2 --tier try
allow "proj|new demo2 --tier mvp" new demo2 --tier mvp
allow "proj|new demo2 --tier mvp --docker --pg" new demo2 --tier mvp --docker --pg
allow "proj|new demo2 --tier try --docker --pg" new demo2 --pg --docker --tier try
allow "proj|list" list
allow "proj|snapshot demo" snapshot demo
allow "proj|doctor" doctor
allow "journalctl|--no-pager -u nginx.service -n 200" logs nginx.service
allow "journalctl|--no-pager -u ssh -n 50" logs ssh -n 50
allow "journalctl|--no-pager -u postgresql@16-main -n 2000" logs postgresql@16-main -n 2000
allow "incus|exec -T demo -- journalctl --no-pager -n 200" logs box demo
allow "incus|exec -T web-1 -- journalctl --no-pager -n 1" logs box web-1 -n 1
allow "systemctl|--no-pager status incus" status incus
allow "systemctl|--no-pager status proj-backup.timer" status proj-backup.timer
allow "incus|exec -T demo -- systemctl restart nginx" restart demo nginx
allow "incus|exec -T demo -- systemctl restart app@1.service" restart demo app@1.service
run_agent help
[ "$rc" = 0 ] && grep -q 'restart <box> <service>' <<< "$out" && ok || bad "help: rc=$rc"

echo "== environment of the child"
run_agent status incus
line=$(cat "$CALLS")
case "$line" in
    "systemctl|SUDO_USER=agent1|PAGER=cat|SYSTEMD_PAGER=[]|LESSSECURE=1|EVIL=|--no-pager status incus") ok ;;
    *) bad "child env: $line" ;;
esac
run_agent new demo2 --tier try
grep -q '^proj|SUDO_USER=agent1|' "$CALLS" && ok || bad "proj does not get SUDO_USER (box owner)"
out=$(env PATH="$T/bin:/usr/bin:/bin" PROJ_AGENT_TEST=1 PROJ_AGENT_LOG="$LOGF" SUDO_USER='x;id' bash -p "$AGENT" list 2>&1)
tail -n 1 "$LOGF" | grep -q ' user=unknown ' && ok || bad "a strange SUDO_USER is not logged as unknown"

echo "== refusals"
deny "tier long is the owner's call" new demo2 --tier long
deny "--tier must be try or mvp" new demo2 --tier prod
deny "--tier try|mvp is required" new demo2
deny "--tier given twice" new demo2 --tier try --tier mvp
deny "--docker given twice" new demo2 --tier try --docker --docker
deny "not allowed for new" new demo2 --tier try --repo x
deny "not allowed for new" new demo2 --tier try --ttl 30d
deny "not allowed for new" new demo2 --tier try --owner root
deny "bad box name" new Demo --tier try
deny "bad box name" new a --tier try
deny "bad box name" new 1abc --tier try
deny "bad box name" new -x --tier try
deny "bad box name" new abcdefghijklmnopqrstuvwxyz0123456 --tier try
deny "not allowed" new 'demo;id' --tier try
deny "not allowed" new 'demo$(id)' --tier try
deny "not allowed" new 'demo`id`' --tier try
deny "not allowed" new 'demo x' --tier try
deny "not allowed" new demo2 --tier 'try;reboot'
deny "not allowed" new "$(printf 'demo\nid')" --tier try
deny "not allowed" logs 'ssh;id'
deny "not allowed" logs 'ssh$(id)'
deny "not allowed" logs 'ssh`id`'
deny "not allowed" status 'ssh incus'
deny "not allowed" restart demo 'nginx;reboot'
deny "not allowed" restart demo 'a b'
deny "not allowed" logs ''
deny "protected HOST project" new md999 --tier try
deny "protected HOST project" snapshot md999
deny "protected HOST project" restart md999 md999-crawler
deny "protected HOST project" logs box md999
deny "no box named" restart nobox nginx
deny "no box named" snapshot nobox
deny "no box named" logs box nobox
deny "unknown command" wipe demo
deny "unknown command" shell demo
deny "unknown command" exec demo
deny "unknown command" promote demo
deny "unknown command" selftest
deny "unknown command" NEW demo --tier try
deny "no command given"
deny "-n must be a number from 1 to 2000" logs ssh -n 99999
deny "-n must be a number from 1 to 2000" logs ssh -n 2001
deny "-n must be a number from 1 to 2000" logs ssh -n 0
deny "-n must be a number from 1 to 2000" logs ssh -n 007
deny "-n must be a number from 1 to 2000" logs ssh -n abc
deny "-n must be a number from 1 to 2000" logs box demo -n 99999
deny "only '-n N' is allowed" logs ssh -f
deny "only '-n N' is allowed" logs ssh -n 5 -n 6
deny "only '-n N' is allowed" logs ssh -n
deny "not allowed" logs ../etc/passwd
deny "not allowed" logs a/b
deny "not allowed" status a/b
deny "not allowed" status /dev/sda
deny "not allowed" restart demo a/b
deny "not allowed" logs 'ssh*'
deny "bad unit name" logs -n
deny "bad unit name" status --all
deny "bad unit name" restart demo --now
deny "bad unit name" status .hidden
deny "usage: logs box <name>" logs box     # "box" alone is never read as a host unit name
deny "usage: logs <unit>" logs
deny "usage: status <unit>" status
deny "usage: status <unit>" status a b
deny "usage: restart <box> <service>" restart demo
deny "usage: restart <box> <service>" restart demo a b
deny "usage: snapshot <name>" snapshot demo mylabel
deny "list takes no arguments" list --all
deny "doctor takes no arguments" doctor --net

echo "== log"
grep -q "user=agent1 args=\[new demo2 --tier try\] result=ok" "$LOGF" && ok || bad "allowed call not logged with result"
grep -q "user=agent1 args=\[wipe demo\] result=refused" "$LOGF" && ok || bad "refused call not logged"
grep -qF 'args=[new $'"'"'demo\nid'"'"' --tier try] result=refused' "$LOGF" && ok || bad "newline in an argument not escaped in the log"
[ "$(grep -c '' "$LOGF")" = "$(grep -cE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T.* user=' "$LOGF")" ] && ok || bad "a log line does not start with time + user"
rc=0; env PATH="$T/bin:/usr/bin:/bin" bash -p "$AGENT" list >/dev/null 2>&1 || rc=$?
[ "$rc" = 1 ] && ok || bad "without sudo and without test mode it must refuse (rc=$rc)"

echo "== nopasswd_effective (lib/common.sh)"
# shellcheck source=../lib/common.sh
( . "$REPO/lib/common.sh"
  agent_listing='Matching Defaults entries for agent1 on host:
    env_reset, secure_path=/usr/sbin\:/usr/bin

Runas and Command-specific defaults for agent1:
    Defaults!/usr/local/sbin/proj-agent env_reset

User agent1 may run the following commands on host:
    (root) NOPASSWD: /usr/local/sbin/proj-agent'
  main_listing='User mainuser may run the following commands on host:
    (ALL : ALL) ALL
    (ALL) NOPASSWD: ALL
    (ALL : ALL) PASSWD: ALL
    (root) NOPASSWD: /usr/local/sbin/proj-agent'
  wrong_order='User mainuser may run the following commands on host:
    (root) NOPASSWD: /usr/local/sbin/proj-agent
    (ALL : ALL) PASSWD: ALL'
  still_root='User mainuser may run the following commands on host:
    (ALL) NOPASSWD: ALL
    (root) NOPASSWD: /usr/local/sbin/proj-agent'
  r=0
  [ "$(nopasswd_effective <<< "$agent_listing")" = /usr/local/sbin/proj-agent ] || { echo "FAIL: agent listing"; r=1; }
  [ "$(nopasswd_effective <<< "$main_listing")" = /usr/local/sbin/proj-agent ] || { echo "FAIL: main listing after zz- rule"; r=1; }
  [ -z "$(nopasswd_effective <<< "$wrong_order")" ] || { echo "FAIL: rule before PASSWD: ALL must not count"; r=1; }
  [ "$(nopasswd_effective <<< "$still_root" | tr '\n' ' ')" = "ALL /usr/local/sbin/proj-agent " ] || { echo "FAIL: NOPASSWD ALL must show"; r=1; }
  exit "$r" ) && ok || bad "nopasswd_effective"

echo "== sudoers.d order (the last matching rule wins)"
last=$(printf '%s\n' 90-cloud-init-users zz-server-main-password zzz-agents-proj 10-server-admin 90-agent1 | sort | tail -n 1)
[ "$last" = zzz-agents-proj ] && ok || bad "zzz-agents-proj does not sort last ($last)"

echo
echo "proj-agent tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
