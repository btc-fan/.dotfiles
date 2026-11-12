#!/usr/bin/env bash
# Offline tests for files/sbin/git-workspace-guard (installed as /usr/local/bin/git by step 70).
# Builds a temp WORK_ROOT with a "box" workspace, installs the guard there with WORK_ROOT and the
# real git filled in, then tries every known bypass (each payload would create a marker file)
# and the normal work (status, add, commit, log, diff, checkout, push to a bare remote outside).
# Run as a normal user: bash tests/git-guard.test.sh
set -uo pipefail
export LC_ALL=C

REPO=$(cd "$(dirname "$0")/.." && pwd)
REALGIT=/usr/bin/git
[ -x /opt/homebrew/bin/git ] && REALGIT=/opt/homebrew/bin/git   # macOS: Apple git is old
T=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/work/box" "$T/outside" "$T/home" "$T/bin"
WS=$T/work/box
G=$T/bin/git
sed -e "s|@WORK_ROOT@|$T/work|" -e "s|@AGENT_USER@|guard-test-agent-nobody|" -e "s|^REAL=/usr/bin/git|REAL=$REALGIT|" \
    "$REPO/files/sbin/git-workspace-guard" > "$G"
chmod 755 "$G"
export HOME=$T/home GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR
# The tests may run inside an agent: start as "the owner" (no agent markers).
unset GIT_GUARD_AGENT CLAUDECODE CODEX_SANDBOX CODEX_THREAD_ID
"$REALGIT" config --global user.name tester
"$REALGIT" config --global user.email tester@example.invalid
"$REALGIT" config --global init.defaultBranch main
"$REALGIT" config --global safe.directory '*'

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*"; }
pwned() { [ -n "$(ls "$T"/pwned-* 2>/dev/null)" ]; }
clear_pwned() { rm -f "$T"/pwned-*; }

# fresh: a clean repo with one commit in the workspace (made with the real git).
fresh() {
    cd "$T" && rm -rf "$WS" && mkdir -p "$WS"
    "$REALGIT" -C "$WS" init -q
    echo hello > "$WS/a.txt"
    "$REALGIT" -C "$WS" add a.txt
    "$REALGIT" -C "$WS" commit -qm first
    clear_pwned
}

# refused NAME CMD...: the guard must refuse (exit 1, "refused") and nothing may run.
refused() {
    local name=$1 out rc; shift
    out=$("$@" 2>&1); rc=$?
    if [ "$rc" -ne 0 ] && grep -q 'git-workspace-guard: refused' <<< "$out" && ! pwned; then ok
    else bad "$name: rc=$rc pwned=$(pwned && echo yes || echo no) out=$(head -c 300 <<< "$out")"; fi
    clear_pwned
}
# not_run NAME CMD...: whatever the exit code, the payload must not run.
not_run() {
    local name=$1; shift
    "$@" >/dev/null 2>&1
    if pwned; then bad "$name: payload ran"; else ok; fi
    clear_pwned
}
# works NAME CMD...: must succeed.
works() {
    local name=$1 out; shift
    if out=$("$@" 2>&1); then ok; else bad "$name: $(head -c 300 <<< "$out")"; fi
}

# ---- normal use ----
fresh
cd "$WS" || exit 1
works "status" "$G" status
echo more >> a.txt
works "diff" "$G" diff
works "add" "$G" add a.txt
works "commit" "$G" commit -qm second
works "log" "$G" log --oneline
works "checkout -b" "$G" checkout -q -b feature
works "checkout back" "$G" checkout -q main
"$REALGIT" init -q --bare "$T/outside/remote.git"
works "remote add (local bare outside)" "$G" remote add origin "$T/outside/remote.git"
works "push to local bare remote" "$G" push -q origin main
works "fetch" "$G" fetch -q origin
works "remote https url" "$G" remote add gh https://github.com/example/repo.git
works "remote scp-like url" "$G" remote add gh2 git@github.com:example/repo.git
works "status after remotes" "$G" status
works "git -C from outside" bash -c "cd '$T' && '$G' -C '$WS' log --oneline"
works "git outside any workspace" bash -c "cd '$T/outside' && '$G' --version"

# ---- hooks never run ----
fresh
printf '#!/bin/sh\ntouch %s/pwned-hook\n' "$T" > "$WS/.git/hooks/pre-commit"
chmod +x "$WS/.git/hooks/pre-commit"
echo x >> "$WS/a.txt"
not_run "pre-commit hook" bash -c "cd '$WS' && '$G' commit -qam hook"

# ---- audit bypass 1: extensions.worktreeConfig + filter in config.worktree ----
fresh
"$REALGIT" -C "$WS" config extensions.worktreeConfig true
"$REALGIT" -C "$WS" config --worktree filter.x.clean "touch $T/pwned-wtcfg"
echo '* filter=x' > "$WS/.gitattributes"
touch "$WS/a.txt"
refused "worktreeConfig filter (git status)" bash -c "cd '$WS' && '$G' status"
fresh
printf '[filter "x"]\n\tclean = touch %s/pwned-wtcfg2\n' "$T" > "$WS/.git/config.worktree"
echo '* filter=x' > "$WS/.gitattributes"
refused "config.worktree without the extension" bash -c "cd '$WS' && '$G' status"

# ---- audit bypass 2: core.worktree outside the workspace ----
fresh
mkdir -p "$T/outside/victim"; echo keep > "$T/outside/victim/.bashrc"
"$REALGIT" -C "$WS" config core.worktree "$T/outside/victim"
refused "core.worktree outside" bash -c "cd '$WS' && '$G' checkout -- ."
[ "$(cat "$T/outside/victim/.bashrc")" = keep ] && ok || bad "core.worktree: file outside was overwritten"

# ---- audit bypass 3: --git-dir / GIT_DIR / -C from outside ----
fresh
"$REALGIT" -C "$WS" config core.pager "touch $T/pwned-pager"
"$REALGIT" -C "$WS" config alias.st "!touch $T/pwned-alias"
refused "--git-dir=<ws> from outside" bash -c "cd '$T' && '$G' --git-dir='$WS/.git' --work-tree='$WS' -p log"
refused "--git-dir <ws> (separate form)" bash -c "cd '$T' && '$G' --git-dir '$WS/.git' st"
refused "GIT_DIR=<ws> from outside" bash -c "cd '$T' && GIT_DIR='$WS/.git' '$G' -p log"
refused "-C <ws> from outside" bash -c "cd '$T' && '$G' -C '$WS' st"
refused "-C chain into ws" bash -c "cd '$T' && '$G' -C work -C box st"
ln -s "$WS" "$T/outside/link"
refused "symlink into ws" bash -c "cd '$T/outside/link' && '$G' st"
refused "GIT_WORK_TREE=<ws>, GIT_DIR relative" bash -c "cd '$T/work' && GIT_DIR=box/.git GIT_WORK_TREE=box '$G' st"

# ---- keys outside the allow-list ----
for kv in "submodule.s.update=!touch $T/pwned-1" "pager.status=touch $T/pwned-2" \
          "interactive.diffFilter=touch $T/pwned-3" "trailer.t.command=touch $T/pwned-4" \
          "core.fsmonitor=touch $T/pwned-5" "core.hooksPath=$T/outside" "core.editor=touch $T/pwned-6" \
          "core.sshCommand=touch $T/pwned-7" "diff.external=touch $T/pwned-8" \
          "diff.x.textconv=touch $T/pwned-9" "merge.x.driver=touch $T/pwned-10" \
          "include.path=$T/outside/inc" "includeIf.gitdir:/.path=$T/outside/inc" \
          "credential.helper=!touch $T/pwned-11" "gpg.program=touch $T/pwned-12" \
          "uploadpack.packObjectsHook=touch $T/pwned-13" "url.x.insteadOf=https://github.com/" \
          "remote.origin.uploadpack=touch $T/pwned-14" "remote.origin.vcs=evil" \
          "lfs.customtransfer.x.path=touch $T/pwned-15" "sequence.editor=touch $T/pwned-16" \
          "extensions.worktreeConfig=true" "extensions.partialclone=origin" "color.ui=always"; do
    fresh
    "$REALGIT" -C "$WS" config "${kv%%=*}" "${kv#*=}"
    refused "key ${kv%%=*}" bash -c "cd '$WS' && '$G' status"
done

# ---- remote URLs ----
for u in "ext::sh -c touch% $T/pwned-ext" "-oProxyCommand=touch $T/pwned-u" \
         "ssh://-oProxyCommand=x/y" "evil::address" "fd::17" "ssh://git@-oProxyCommand=x/y"; do
    fresh
    "$REALGIT" -C "$WS" config remote.origin.url "$u"
    refused "remote url $u" bash -c "cd '$WS' && '$G' fetch origin"
done
fresh
"$REALGIT" -C "$WS" config submodule.s.url "ext::sh -c touch% $T/pwned-sub"
refused "submodule url ext::" bash -c "cd '$WS' && '$G' status"

# ---- a .git file that points to a host repository ----
fresh
"$REALGIT" init -q "$T/outside/hostrepo"
rm -rf "$WS/.git"
echo "gitdir: $T/outside/hostrepo/.git" > "$WS/.git"
refused ".git file to a host repo" bash -c "cd '$WS' && '$G' status"

# ---- a bare repository planted in the workspace ----
fresh
"$REALGIT" init -q --bare "$WS/planted.git"
"$REALGIT" --git-dir="$WS/planted.git" config core.fsmonitor "touch $T/pwned-bare"
not_run "planted bare repo (implicit use refused by git)" bash -c "cd '$WS/planted.git' && '$G' status"

# ---- alternates outside the workspaces ----
fresh
"$REALGIT" init -q --bare "$T/outside/objs.git"
echo "$T/outside/objs.git/objects" > "$WS/.git/objects/info/alternates"
refused "alternates outside" bash -c "cd '$WS' && '$G' status"

# ---- submodules: the module config is checked, and git never enters submodules ----
fresh
mkdir -p "$WS/.git/modules/s"
printf '[core]\n\tfsmonitor = touch %s/pwned-mod\n' "$T" > "$WS/.git/modules/s/config"
refused "modules/*/config" bash -c "cd '$WS' && '$G' status"
fresh
refused "git submodule" bash -c "cd '$WS' && '$G' submodule update --init"
refused "--recurse-submodules" bash -c "cd '$WS' && '$G' checkout --recurse-submodules main"

# ---- outside the workspaces: plain git, no checks ----
"$REALGIT" init -q "$T/outside/own"
"$REALGIT" -C "$T/outside/own" config color.ui auto
works "own repo outside, any key" bash -c "cd '$T/outside/own' && '$G' status"

# ---- agent mode: every repository, not only workspaces ----
plant() {   # a repository OUTSIDE the workspaces, planted by sandboxed code
    rm -rf "$T/outside/planted" "$T/outside/planted-remote.git"
    "$REALGIT" init -q "$T/outside/planted"
    echo x > "$T/outside/planted/f"; "$REALGIT" -C "$T/outside/planted" add f
    "$REALGIT" -C "$T/outside/planted" commit -qm one
    printf '#!/bin/sh\ntouch %s/pwned-agenthook\n' "$T" > "$T/outside/planted/.git/hooks/pre-push"
    printf '#!/bin/sh\ntouch %s/pwned-agenthook2\n' "$T" > "$T/outside/planted/.git/hooks/post-checkout"
    chmod +x "$T/outside/planted/.git/hooks/"*
    "$REALGIT" init -q --bare "$T/outside/planted-remote.git"
    "$REALGIT" -C "$T/outside/planted" remote add o "$T/outside/planted-remote.git"
    clear_pwned
}
for marker in CLAUDECODE=1 GIT_GUARD_AGENT=1 CODEX_SANDBOX=landlock CODEX_THREAD_ID=abc; do
    plant
    not_run "agent ($marker): pre-push hook outside workspaces" env "$marker" "$G" -C "$T/outside/planted" push -q o HEAD
    not_run "agent ($marker): post-checkout hook outside workspaces" env "$marker" "$G" -C "$T/outside/planted" checkout -q -b b2
done
plant
"$REALGIT" -C "$T/outside/planted" config core.pager "touch $T/pwned-agentpager"
refused "agent: core.pager in a repo outside workspaces" env CLAUDECODE=1 "$G" -C "$T/outside/planted" -p log
plant
"$REALGIT" -C "$T/outside/planted" config extensions.worktreeConfig true
"$REALGIT" -C "$T/outside/planted" config --worktree filter.x.clean "touch $T/pwned-agentfilter"
echo '* filter=x' > "$T/outside/planted/.gitattributes"
refused "agent: worktree filter outside workspaces" env GIT_GUARD_AGENT=1 "$G" -C "$T/outside/planted" status
plant
"$REALGIT" -C "$T/outside/planted" config core.hooksPath .githooks
"$REALGIT" -C "$T/outside/planted" config remote.o.gh-resolved base
works "agent: hooksPath and gh-resolved keys are fine outside workspaces" env CLAUDECODE=1 "$G" -C "$T/outside/planted" status
not_run "agent: hooksPath key does not run hooks" env CLAUDECODE=1 "$G" -C "$T/outside/planted" push -q o HEAD
refused "agent: submodule outside workspaces" env CLAUDECODE=1 "$G" -C "$T/outside/planted" submodule status
plant
works "owner (no marker): hooks run in the owner's own repos" "$G" -C "$T/outside/planted" push -q o HEAD
pwned && ok || bad "owner: the pre-push hook should have run (no agent marker)"
clear_pwned
works "agent: git clone outside workspaces" env CLAUDECODE=1 "$G" clone -q "$T/outside/planted-remote.git" "$T/outside/clone1"
works "agent: commit in a clean repo outside" env CLAUDECODE=1 bash -c "cd '$T/outside/clone1' && echo y > g && '$G' add g && '$G' commit -qm two && '$G' log --oneline"

echo "git-guard tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
