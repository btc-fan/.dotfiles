#!/usr/bin/env bash
# Offline tests for files/sbin/pg-backup and files/sbin/pg-restore-drill (bash 4+, GNU date: Linux).
# Fakes on PATH: runuser (drops "-u USER --"), psql, pg_dump, pg_dumpall, pg_restore, createdb,
# dropdb, mountpoint, date (FAKE_NOW). host.env is a temp file. Run as a normal user:
#   bash tests/pg-backup.test.sh
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/.." && pwd)
[ "${BASH_VERSINFO[0]}" -ge 4 ] || { echo "needs bash 4 or newer (Linux)"; exit 1; }
date -d 2026-01-01 +%F >/dev/null 2>&1 || { echo "needs GNU date"; exit 1; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/backup" "$T/data"
REALDATE=$(command -v date)
cat > "$T/host.env" <<EOF
BACKUP_DIR="$T/data/backups"
BACKUP_MOUNT="$T/backup"
PG_BACKUP_SKIP_DBS="bigdb laterdb"
INSTALL_POSTGRES="yes"
EOF
for s in pg-backup pg-restore-drill; do
    sed "s|/etc/server/host.env|$T/host.env|; s|/usr/local/sbin/discord-notify|$T/bin/discord-notify|; s|/var/lib/server-info|$T/info|g" \
        "$REPO/files/sbin/$s" > "$T/$s"
done
cat > "$T/bin/runuser" <<'EOF'
#!/bin/bash
while [ $# -gt 0 ] && [ "$1" != -- ]; do shift; done; shift; exec "$@"
EOF
cat > "$T/bin/psql" <<EOF
#!/bin/bash
q="\$*"
case "\$q" in
    *"select datname from pg_database"*) printf 'appdb\nbigdb\npostgres\n' ;;
    *pg_database_size*) echo 1000 ;;
    *data_directory*) echo "$T/data" ;;
    *"count(*) from pg_class"*) echo "\${FAKE_TABLES:-3}" ;;
    *) echo 0 ;;
esac
EOF
cat > "$T/bin/pg_dump" <<'EOF'
#!/bin/bash
[ "$1" = --version ] && { echo "pg_dump (PostgreSQL) 16.15"; exit 0; }
[ -n "${FAKE_DUMP_FAIL:-}" ] && exit 1
echo "DUMP ${!#}"
EOF
printf '#!/bin/bash\necho "-- globals"\n' > "$T/bin/pg_dumpall"
cat > "$T/bin/pg_restore" <<'EOF'
#!/bin/bash
if [ "$1" = -l ]; then
    grep -q '^DUMP' || exit 1
    [ -n "${FAKE_EMPTY:-}" ] && { printf '1; 2615 1 SCHEMA - public\n'; exit 0; }
    printf '1; 2615 1 SCHEMA - public\n2; 1259 16390 TABLE public a u\n3; 1259 16391 TABLE public b u\n4; 1259 16392 TABLE public c u\n'
    exit 0
fi
cat > /dev/null; exit "${FAKE_RESTORE_RC:-0}"
EOF
printf '#!/bin/bash\nexit 0\n' > "$T/bin/createdb"
printf '#!/bin/bash\necho "dropdb $*" >> %s/drops\n' "$T" > "$T/bin/dropdb"
printf '#!/bin/bash\nexit 0\n' > "$T/bin/mountpoint"
printf '#!/bin/bash\nexec %s -d "${FAKE_NOW:-now}" "$@"\n' "$REALDATE" > "$T/bin/date"
printf '#!/bin/bash\nshift_t=0\n[ "$1" = --test ] && shift\necho "POST $1 $2" >> %s/posts\n' "$T" > "$T/bin/discord-notify"
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH"

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }
count() { find "$1" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | wc -l; }

echo "== 20 days of normal and big dumps: 7 daily, 4 weekly"
for i in $(seq 0 19); do
    day=$($REALDATE -d "2026-03-02 +$i day" +%F)
    FAKE_NOW="$day 07:30" bash "$T/pg-backup" > "$T/out" 2>&1 || bad "pg-backup $day: $(cat "$T/out")"
    FAKE_NOW="$day 04:30" bash "$T/pg-backup" --big > "$T/out" 2>&1 || bad "pg-backup --big $day: $(cat "$T/out")"
done
N=$T/backup/postgres
[ "$(count "$N/daily")" = 7 ] && ok || bad "normal daily kept: $(count "$N/daily")"
[ "$(count "$N/weekly")" = 3 ] && ok || bad "normal weekly kept (20 days = 3 ISO weeks): $(count "$N/weekly")"
last=$(ls -1 "$N/daily" | tail -n 1)
[ "$last" = 2026-03-21 ] && ok || bad "newest daily is $last"
[ -f "$N/daily/$last/appdb.dump" ] && [ -f "$N/daily/$last/postgres.dump" ] && [ -f "$N/daily/$last/globals.sql" ] && ok || bad "normal dump files missing"
[ ! -e "$N/daily/$last/bigdb.dump" ] && ok || bad "big db in the normal dump"
B=$T/backup/postgres-big/bigdb
[ "$(count "$B/daily")" = 7 ] && [ -f "$B/daily/$last/bigdb.dump" ] && ok || bad "big daily: $(count "$B/daily")"
w=$(ls -1 "$B/weekly" | head -n 1)
[ "$w" = 2026-W10 ] && ok || bad "first weekly is $w"
[ "$(stat -c %h "$B/weekly/$(ls -1 "$B/weekly" | tail -n 1)/bigdb.dump")" -ge 2 ] && ok || bad "weekly is not a hard link of the daily"
[ -e "$T/backup/postgres-big/laterdb/.not-there-yet" ] && [ ! -d "$T/backup/postgres-big/laterdb/daily" ] && ok || bad "missing db not noted as not there yet"
grep -q 'laterdb: not in this cluster yet' "$T/out" && ok || bad "missing db message"

[ "$(cut -d' ' -f1 "$T/info/pg-appdb")" = "$($REALDATE -d '2026-03-21 07:30' +%s)" ] && ok || bad "status note pg-appdb: $(cat "$T/info/pg-appdb" 2>&1)"
[ "$(cat "$T/info/pg-laterdb")" = missing ] && [ -s "$T/info/pg-bigdb" ] && ok || bad "status notes for big dbs"
[ "$(stat -c %a "$T/info/pg-appdb")" = 644 ] && ok || bad "status note not 644"

echo "== 30 more days: weekly stops at 4"
for i in $(seq 20 49); do
    day=$($REALDATE -d "2026-03-02 +$i day" +%F)
    FAKE_NOW="$day 07:30" bash "$T/pg-backup" > /dev/null 2>&1
done
[ "$(count "$N/weekly")" = 4 ] && [ "$(count "$N/daily")" = 7 ] && ok || bad "after 50 days: weekly $(count "$N/weekly"), daily $(count "$N/daily")"

echo "== a failed dump leaves no dated folder and keeps the old ones"
before=$(count "$N/daily")
FAKE_NOW="2026-05-01 07:30" FAKE_DUMP_FAIL=1 bash "$T/pg-backup" > /dev/null 2>&1 && bad "failed dump returned 0" || ok
[ ! -e "$N/daily/2026-05-01" ] && [ "$(count "$N/daily")" = "$before" ] && ok || bad "failed dump changed the daily folders"
FAKE_NOW="2026-05-02 07:30" bash "$T/pg-backup" > /dev/null 2>&1
[ -z "$(ls -A "$N/daily" | grep '^\.partial')" ] && ok || bad "a .partial folder was left after the next run"

echo "== restore drill"
rm -f "$T/posts" "$T/drops"
bash "$T/pg-restore-drill" > "$T/out" 2>&1 && ok || bad "drill failed: $(cat "$T/out")"
grep -q '^POST info restore drill passed' "$T/posts" && ok || bad "drill: no info post: $(cat "$T/posts" 2>/dev/null)"
grep -q 'ok   bigdb: 3 tables' "$T/out" && grep -q 'note laterdb: not in this cluster yet' "$T/out" && ok || bad "drill lines: $(cat "$T/out")"
grep -q 'restore_drill_appdb' "$T/drops" && ok || bad "drill did not drop its throwaway database"
rm -f "$T/posts"
FAKE_TABLES=2 bash "$T/pg-restore-drill" > "$T/out" 2>&1 && bad "drill with missing tables returned 0" || ok
grep -q '^POST alerts restore drill FAILED' "$T/posts" && ok || bad "drill failure not sent to alerts"

rm -f "$T/posts"
FAKE_TABLES=0 FAKE_EMPTY=1 bash "$T/pg-restore-drill" > "$T/out" 2>&1 && ok || bad "drill of empty databases failed: $(cat "$T/out")"
grep -q 'empty database' "$T/out" && ok || bad "empty database line missing: $(cat "$T/out")"

echo
echo "pg-backup tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
