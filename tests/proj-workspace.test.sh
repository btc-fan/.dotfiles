#!/usr/bin/env bash
# Offline tests for the workspace logic in files/proj/proj (new, fork, wipe, recreate, workspace).
# proj is loaded with PROJ_LIB=1 (functions only). Fakes on PATH: incus (keeps a small JSON state
# per box and records every call), setfacl and getent. Paths, owner and group point at a temp dir
# and the current user. Run as a NORMAL user: bash tests/proj-workspace.test.sh
set -uo pipefail
export LC_ALL=C

REPO=$(cd "$(dirname "$0")/.." && pwd)
[ "$(id -u)" -ne 0 ] || { echo "run the tests as a normal user, not root"; exit 1; }
command -v jq >/dev/null || { echo "jq is needed for this test"; exit 1; }

T=$(mktemp -d)
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/state" "$T/oldapp/sub"
CALLS=$T/calls
: > "$CALLS"
ME=$(id -un); MYUID=$(id -u); MYGROUP=$(id -gn); MYGID=$(id -g)

# incus: query answers from $T/state/<box>; launch/copy/delete/device add|set change it.
cat > "$T/bin/incus" <<EOF
#!/bin/bash
S=$T/state
if [ "\$1" = query ]; then
    p=\${2#/1.0/instances/}
    case "\$p" in
        */state) [ -f "\$S/\${p%/state}" ] || exit 1; echo '{"status":"Running"}'; exit 0 ;;
        *) [ -f "\$S/\$p" ] || exit 1; cat "\$S/\$p"; exit 0 ;;
    esac
fi
echo "incus \$*" >> "$CALLS"
case "\$1 \$2" in
    "launch "*) echo '{"devices":{}}' > "\$S/\$3" ;;
    "copy "*) cp "\$S/\${2%%/*}" "\$S/\$3" ;;
    "delete "*) rm -f "\$S/\${!#}" ;;
    "config device")
        src=""
        for a in "\$@"; do case "\$a" in source=*) src=\${a#source=} ;; esac; done
        jq --arg s "\$src" '.devices.app.source = \$s' "\$S/\$4" > "\$S/\$4.new" && mv "\$S/\$4.new" "\$S/\$4" ;;
    "storage volume") [ "\$3" != show ] || exit 1; [ "\$3" != list ] || echo '[]' ;;
    "list "*) echo '[]' ;;
    "exec "*) case "\$*" in *"tar -C /srv/app -cf - ."*) tar -C "$T/oldapp" -cf - . ;; esac ;;
esac
exit 0
EOF
cat > "$T/bin/setfacl" <<EOF
#!/bin/bash
echo "setfacl \$*" >> "$CALLS"
[ -z "\${FAIL_SETFACL:-}" ] || { echo "setfacl: Operation not permitted" >&2; exit 1; }
EOF
cat > "$T/bin/getent" <<EOF
#!/bin/bash
[ "\$1" = group ] && [ "\$2" = "$MYGROUP" ] && { echo "$MYGROUP:x:$MYGID:"; exit 0; }
exit 2
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH"

# Load proj, then point it at the temp dir. Each case runs in a subshell (proj's die exits).
# shellcheck source=../files/proj/proj
PROJ_LIB=1 . "$REPO/files/proj/proj" 2>/dev/null
set +e
export LC_ALL=C
WORK_ROOT=$T/work WS_GROUP=$MYGROUP WS_ROOT_OWNER=$ME BOX_UID=$MYUID MAIN_USER=$ME
LOG=$T/proj.log SHARE=$T/share HOST_PROJECTS=/dev/null SERVER_NAME=testhost
note() { :; }
notify() { :; }
cmd_registry() { :; }

pass=0 fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }
# line_of TEXT: line number of the first call that contains TEXT (0 = none).
line_of() { local n; n=$(grep -nF -- "$1" "$CALLS" | head -n 1 | cut -d: -f1); echo "${n:-0}"; }
dev_add() { echo "incus config device add $1 app disk source=$WORK_ROOT/$1 path=/srv/app shift=true"; }

echo "== ws_check"
out=$( (BOX_UID=4242; ws_check) 2>&1 ); rc=$?
[ "$rc" = 1 ] && grep -q "has uid $MYUID, not 4242" <<< "$out" && ok || bad "uid mismatch not refused: rc=$rc $out"
out=$( (WS_GROUP=nosuchgroup; ws_check) 2>&1 ); rc=$?
[ "$rc" = 1 ] && grep -q "group nosuchgroup is missing" <<< "$out" && ok || bad "missing group not refused: $out"
out=$( (BOX_UID=4242; cmd_new demox --tier try) 2>&1 ); rc=$?
[ "$rc" = 1 ] && [ "$(line_of 'launch')" = 0 ] && ok || bad "new with a bad uid must stop before launch: rc=$rc $out"

echo "== new"
out=$( (cmd_new demo --tier try) 2>&1 ); rc=$?
[ "$rc" = 0 ] || bad "new demo: rc=$rc $out"
l_launch=$(line_of 'incus launch images:ubuntu/26.04 demo')
l_dev=$(line_of "$(dev_add demo)")
l_push=$(line_of 'box-bootstrap.sh demo/root/box-bootstrap.sh')
l_boot=$(line_of "incus exec demo -- bash /root/box-bootstrap.sh demo no no $MYGID $MYGROUP")
[ "$l_launch" -gt 0 ] && [ "$l_dev" -gt "$l_launch" ] && [ "$l_push" -gt "$l_dev" ] && [ "$l_boot" -gt "$l_push" ] \
    && ok || bad "new: order launch($l_launch) < device add($l_dev) < push($l_push) < bootstrap with shared gid($l_boot)"
[ -d "$WORK_ROOT/demo" ] && ls -ld "$WORK_ROOT/demo" | grep -q '^drwxrwsr-x' && ok || bad "workspace not 2775: $(ls -ld "$WORK_ROOT/demo")"
ls -ld "$WORK_ROOT" | grep -q '^drwxr-x---' && ok || bad "workspace root not 750: $(ls -ld "$WORK_ROOT")"
grep -qxF "setfacl -m g:$MYGROUP:rwx $WORK_ROOT/demo" "$CALLS" \
    && grep -qxF "setfacl -d -m u::rwx,g::rwx,g:$MYGROUP:rwx,o::rx $WORK_ROOT/demo" "$CALLS" && ok || bad "default ACL not set on the workspace"
[ "$(jq -r .devices.app.source "$T/state/demo")" = "$WORK_ROOT/demo" ] && ok || bad "device source not recorded"
grep -q "Code: $WORK_ROOT/demo on the host" <<< "$out" && ok || bad "new does not tell where the code is: $out"
echo hello > "$WORK_ROOT/demo/app.txt"

echo "== fork (own copy of the workspace, device moved to it)"
: > "$CALLS"
out=$( (cmd_fork demo demo--a) 2>&1 ); rc=$?
[ "$rc" = 0 ] || bad "fork: rc=$rc $out"
grep -qx hello "$WORK_ROOT/demo--a/app.txt" 2>/dev/null && ok || bad "fork did not copy the workspace"
grep -qxF "incus config device set demo--a app source=$WORK_ROOT/demo--a" "$CALLS" && ok || bad "fork device not moved to its own workspace"
[ "$(line_of 'incus config device add demo--a')" = 0 ] && ok || bad "fork added a second app device"
[ "$(line_of "device set demo--a app source")" -lt "$(line_of 'incus start demo--a')" ] && ok || bad "fork: device moved after start"
[ "$(jq -r .devices.app.source "$T/state/demo")" = "$WORK_ROOT/demo" ] && ok || bad "fork changed the source box"
out=$( (cmd_fork demo demo--a) 2>&1 ); rc=$?
[ "$rc" = 1 ] && ok || bad "fork onto an existing name must fail: $out"

echo '{"devices":{}}' > "$T/state/plain"
: > "$CALLS"
out=$( (cmd_fork plain plain--a) 2>&1 ); rc=$?
[ "$rc" = 0 ] && [ ! -e "$WORK_ROOT/plain--a" ] && [ "$(line_of 'device add plain--a')" = 0 ] \
    && grep -q 'has no workspace' <<< "$out" && ok || bad "fork of a box without workspace must not mount an empty one: $out"

echo "== wipe --yes keeps the workspace in .trash"
out=$( (cmd_wipe demo--a --yes) 2>&1 ); rc=$?
t=$(ls -d "$WORK_ROOT/.trash/demo--a-"* 2>/dev/null | head -n 1)
[ "$rc" = 0 ] && [ ! -e "$WORK_ROOT/demo--a" ] && [ -n "$t" ] && grep -qx hello "$t/app.txt" && ok || bad "wipe --yes: rc=$rc trash='$t' $out"
ls -ld "$WORK_ROOT/.trash" | grep -q '^drwx------' && ok || bad ".trash not 700"

echo "== recreate re-attaches the same workspace"
: > "$CALLS"
out=$( (cmd_recreate demo --yes) 2>&1 ); rc=$?
l_del=$(line_of 'incus delete demo')
l_launch=$(line_of 'incus launch images:ubuntu/26.04 demo')
l_dev=$(line_of "$(dev_add demo)")
[ "$rc" = 0 ] && [ "$l_del" -gt 0 ] && [ "$l_launch" -gt "$l_del" ] && [ "$l_dev" -gt "$l_launch" ] \
    && ok || bad "recreate: rc=$rc delete($l_del) launch($l_launch) device add($l_dev) $out"
grep -qx hello "$WORK_ROOT/demo/app.txt" && ok || bad "recreate lost the workspace"
[ "$(line_of 'tar -C /srv/app')" = 0 ] && ok || bad "recreate copied /srv/app although the box had a workspace"

echo "== wipe asks: Enter keeps, delete deletes, no answer keeps"
out=$( (cmd_wipe demo) 2>&1 <<< "$(printf 'demo\n\n')" ); rc=$?
[ "$rc" = 0 ] && [ ! -e "$WORK_ROOT/demo" ] && ls -d "$WORK_ROOT/.trash/demo-"* >/dev/null 2>&1 && ok || bad "wipe + Enter must keep: rc=$rc $out"
(cmd_new demo2 --tier try) >/dev/null 2>&1
echo x > "$WORK_ROOT/demo2/f"
out=$( (cmd_wipe demo2) 2>&1 <<< "$(printf 'demo2\ndelete\n')" ); rc=$?
[ "$rc" = 0 ] && [ ! -e "$WORK_ROOT/demo2" ] && ! ls -d "$WORK_ROOT/.trash/demo2-"* >/dev/null 2>&1 && ok || bad "wipe + delete must delete: rc=$rc $out"
(cmd_new demo3 --tier try) >/dev/null 2>&1
out=$( (cmd_wipe demo3) 2>&1 <<< "demo3" ); rc=$?
[ "$rc" = 0 ] && ls -d "$WORK_ROOT/.trash/demo3-"* >/dev/null 2>&1 && ok || bad "wipe with no answer must keep: rc=$rc $out"
(cmd_new demo4 --tier try) >/dev/null 2>&1
out=$( (cmd_wipe demo4) 2>&1 <<< "$(printf 'demo4\nno\n')" ); rc=$?
[ "$rc" = 0 ] && ls -d "$WORK_ROOT/.trash/demo4-"* >/dev/null 2>&1 && ok || bad "wipe + 'no' must keep (only 'delete' deletes): $out"

echo "== workspace: an older box gets one, its /srv/app copied out safely"
echo '{"devices":{}}' > "$T/state/oldbox"
echo code > "$T/oldapp/main.py"
echo secret > "$T/oldapp/.env"; chmod 600 "$T/oldapp/.env"
echo tool > "$T/oldapp/sub/tool"; chmod 4755 "$T/oldapp/sub/tool"
ln -s /etc/passwd "$T/oldapp/link"
: > "$CALLS"
out=$( (cmd_workspace oldbox) 2>&1 ); rc=$?
w=$WORK_ROOT/oldbox
[ "$rc" = 0 ] && grep -qx code "$w/main.py" && ok || bad "workspace oldbox: rc=$rc $out"
[ ! -u "$w/sub/tool" ] && ok || bad "setuid bit kept from the box"
[ -L "$w/link" ] && [ "$(readlink "$w/link")" = /etc/passwd ] && ok || bad "a link from the box was not kept as a link"
ls -l "$w/.env" | grep -q '^-rw-------' && ok || bad ".env lost mode 600: $(ls -l "$w/.env")"
ls -l "$w/main.py" | grep -q '^-rw-rw-r--' && ok || bad "copied file not group-writable: $(ls -l "$w/main.py")"
ls -ld "$w/sub" | grep -q '^drwxrwsr-x' && ok || bad "copied folder not 2775: $(ls -ld "$w/sub")"
l_tar=$(line_of 'incus exec oldbox -- tar -C /srv/app -cf - .')
l_dev=$(line_of "$(dev_add oldbox)")
[ "$l_tar" -gt 0 ] && [ "$l_dev" -gt "$l_tar" ] && ok || bad "workspace: copy($l_tar) must come before the mount($l_dev)"
out=$( (cmd_workspace oldbox) 2>&1 ); rc=$?
[ "$rc" = 0 ] && grep -q 'already has its workspace' <<< "$out" && ok || bad "workspace twice: $out"
echo '{"devices":{}}' > "$T/state/oldbox2"
mkdir -p "$WORK_ROOT/oldbox2"; echo mine > "$WORK_ROOT/oldbox2/keep"
: > "$CALLS"
out=$( (cmd_workspace oldbox2) 2>&1 ); rc=$?
[ "$rc" = 0 ] && [ "$(line_of 'tar -C /srv/app')" = 0 ] && grep -qx mine "$WORK_ROOT/oldbox2/keep" && ok || bad "non-empty workspace must not be overwritten: $out"

echo "== restore of a workspace snapshot: extracted as MAIN_USER, links kept, no root chown"
echo '{"devices":{"app":{"source":"'"$WORK_ROOT"'/snapbox"}}}' > "$T/state/snapbox"
mkdir -p "$T/snapsrc/sub" "$T/outside"
echo v1 > "$T/snapsrc/main.py"
echo tool > "$T/snapsrc/sub/tool"; chmod 4755 "$T/snapsrc/sub/tool"
echo victim > "$T/outside/victim"; chmod 640 "$T/outside/victim"
ln -s "$T/outside/victim" "$T/snapsrc/link"
WS_SNAP_ROOT=$WORK_ROOT/.snapshots
mkdir -p "$WS_SNAP_ROOT/snapbox"
tar -C "$T/snapsrc" --zstd -cf "$WS_SNAP_ROOT/snapbox/l1.tar.zst" . 2>/dev/null \
    || tar -C "$T/snapsrc" -cf - . | zstd -q > "$WS_SNAP_ROOT/snapbox/l1.tar.zst"
mkdir -p "$WORK_ROOT/snapbox"; echo now > "$WORK_ROOT/snapbox/main.py"
out=$( (ws_unsnap snapbox l1) 2>&1 ); rc=$?
w=$WORK_ROOT/snapbox
[ "$rc" = 0 ] && grep -qx v1 "$w/main.py" && ok || bad "unsnap: rc=$rc $out"
[ -L "$w/link" ] && ok || bad "unsnap: link not kept as a link"
ls -l "$T/outside/victim" | grep -q '^-rw-r-----' && ok || bad "unsnap changed a file outside through a link: $(ls -l "$T/outside/victim")"
[ ! -u "$w/sub/tool" ] && ok || bad "unsnap kept a setuid bit"
ls -ld "$w/sub" | grep -q '^drwxrwsr-x' && ok || bad "unsnap folder not 2775: $(ls -ld "$w/sub")"
ls "$WORK_ROOT/.trash" | grep -q '^snapbox-' && ok || bad "unsnap: the current workspace was not kept in .trash"
# No root chown or chmod that walks a workspace is left in proj (only as_main ... find).
bad_lines=$(grep -nE '^[^#]*find [^|]*-exec ch(own|mod)' "$REPO/files/proj/proj" | grep -v 'as_main find' || true)
[ -z "$bad_lines" ] && ok || bad "root find -exec chown/chmod left in proj: $bad_lines"

echo "== new fails after the launch: the half-made box is removed, an older workspace is kept"
: > "$CALLS"
out=$( (set -e; FAIL_SETFACL=1 cmd_new halfbox --tier try) 2>&1 ); rc=$?
[ "$rc" != 0 ] && grep -q "new halfbox FAILED" <<< "$out" && ok || bad "failed new did not report: rc=$rc $out"
[ "$(line_of 'incus delete --force halfbox')" -gt 0 ] && ok || bad "failed new did not delete the box: $(cat "$CALLS")"
[ ! -e "$T/state/halfbox" ] && ok || bad "half box still in state"
[ ! -d "$WORK_ROOT/halfbox" ] && ok || bad "workspace made by the failed new was left behind"
mkdir -p "$WORK_ROOT/keptbox"; echo mine > "$WORK_ROOT/keptbox/code.py"
out=$( (set -e; FAIL_SETFACL=1 cmd_new keptbox --tier try) 2>&1 ); rc=$?
[ "$rc" != 0 ] && grep -qx mine "$WORK_ROOT/keptbox/code.py" && [ ! -e "$T/state/keptbox" ] && ok || bad "a workspace that existed before was touched, or the box stayed: rc=$rc"
out=$( (set -e; cmd_new goodbox --tier try) 2>&1 ); rc=$?
[ "$rc" = 0 ] && [ -e "$T/state/goodbox" ] && ok || bad "a good new was rolled back: rc=$rc $out"

echo "== lock: two proj commands on the same box name never run at once"
if command -v flock >/dev/null; then
    ( PROJ_LOCK_DIR=$T/locks; lock_box racebox; sleep 3 ) & holder=$!
    sleep 1
    out=$( (PROJ_LOCK_DIR=$T/locks PROJ_LOCK_WAIT=1; lock_box racebox) 2>&1 ); rc=$?
    [ "$rc" = 1 ] && grep -q "box racebox is busy" <<< "$out" && ok || bad "second lock on the same name was not refused: rc=$rc $out"
    out=$( (PROJ_LOCK_DIR=$T/locks PROJ_LOCK_WAIT=1; lock_box otherbox; echo got) 2>&1 )
    grep -qx got <<< "$out" && ok || bad "a lock on another name must not wait: $out"
    wait "$holder"
    out=$( (PROJ_LOCK_DIR=$T/locks PROJ_LOCK_WAIT=1; lock_box racebox; echo got) 2>&1 )
    grep -qx got <<< "$out" && ok || bad "the lock was not free after the first command ended: $out"
else
    echo "(no flock here: lock test skipped, it runs on Linux)"
fi

echo
echo "proj workspace tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
