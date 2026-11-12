# ai/lib/root-guard.sh: sourced FIRST by install.sh and uninstall.sh, before any other file of this tree.
# Root must never run code from a tree another user can change (the agent user's ~/.dotfiles-ai). As root
# the tree must be owned by root or by the admin who ran sudo (not by the --for-user target), with nothing
# in it writable by group or others, clean, and at a commit that is on the remote (origin/ai).
# Development override for the clean/pushed check only: --allow-dirty. Ownership is never overridden.
# Pure POSIX sh + git; it reads files, it changes nothing.

ai_root_guard() {
    # ai_root_guard <tree> <target user or ""> <allow dirty 0|1> <script name>
    tree=$1 target=$2 dirty_ok=$3 script=$4
    [ "$(id -u)" -eq 0 ] || return 0
    owner=$(stat -c %U "$tree" 2>/dev/null || stat -f %Su "$tree" 2>/dev/null || echo unknown)
    why=""
    if [ "$owner" != root ] && [ "$owner" != "${SUDO_USER:-}" ]; then
        why="the tree belongs to $owner, not to root or to you (${SUDO_USER:-root})"
    elif [ -n "$target" ] && [ "$owner" = "$target" ]; then
        why="the tree belongs to $target, the user the agents run as"
    elif [ -n "$(find "$tree" -path "$tree/.git" -prune -o \( ! -user "$owner" ! -user root \) -print 2>/dev/null | head -n 1)" ]; then
        why="files in the tree belong to other users"
    # Symlinks always show mode 777: only real files and folders count.
    elif [ -n "$(find "$tree" -path "$tree/.git" -prune -o ! -type l \( -perm -0020 -o -perm -0002 \) -print 2>/dev/null | head -n 1)" ]; then
        why="files in the tree are writable by group or others"
    fi
    if [ -z "$why" ] && [ "$dirty_ok" != 1 ]; then
        g="git -C $tree"
        [ "$owner" != root ] && g="sudo -u $owner git -C $tree"
        if [ -n "$($g status --porcelain 2>/dev/null || echo not-a-repo)" ]; then
            why="the tree has uncommitted changes (or is not a git work tree)"
        elif [ "$($g rev-parse HEAD 2>/dev/null)" != "$($g rev-parse origin/ai 2>/dev/null)" ]; then
            why="HEAD is not origin/ai (fetch and check out the pushed commit)"
        fi
    fi
    [ -z "$why" ] && return 0
    url=$(git -C "$tree" remote get-url origin 2>/dev/null || echo '<repo URL>')
    cat >&2 <<EOF
ERROR: refusing to run $script as root from $tree: $why.
Root runs only the root-owned clone /opt/ai-setup at the pushed commit (never a user's home). As the admin:
  sudo git clone --branch ai $url /opt/ai-setup                  # once
  sudo /opt/ai-setup/$script --update --for-user ${target:-<user>}   # fetch, fast-forward, run
EOF
    exit 1
}

# ai_update_clone <tree> <allow dirty>: root-owned clone only. Fetch origin ai and fast-forward; refuse a
# dirty tree, a detached or other branch, and history that does not continue (local commits, force push).
ai_update_clone() {
    tree=$1 dirty_ok=$2
    owner=$(stat -c %U "$tree" 2>/dev/null || stat -f %Su "$tree" 2>/dev/null || echo unknown)
    [ "$owner" = root ] || { echo "ERROR: --update needs a root-owned clone (this one belongs to $owner)" >&2; exit 1; }
    g="git -C $tree"
    [ "$($g symbolic-ref --short -q HEAD 2>/dev/null)" = ai ] \
        || { echo "ERROR: $tree is not on branch ai. Fix: sudo git -C $tree checkout ai" >&2; exit 1; }
    if [ "$dirty_ok" != 1 ] && [ -n "$($g status --porcelain 2>/dev/null)" ]; then
        echo "ERROR: $tree has uncommitted changes. Look: sudo git -C $tree status. Nothing changed." >&2; exit 1
    fi
    old=$($g rev-parse HEAD)
    $g fetch --quiet origin ai || { echo "ERROR: git fetch failed. Nothing changed." >&2; exit 1; }
    new=$($g rev-parse origin/ai)
    if [ "$old" != "$new" ]; then
        $g merge-base --is-ancestor "$old" "$new" \
            || { echo "ERROR: origin/ai does not continue $old (local commits or rewritten history). Nothing changed." >&2; exit 1; }
        $g merge --quiet --ff-only origin/ai || { echo "ERROR: fast-forward failed. Nothing changed." >&2; exit 1; }
        echo "updated $tree: $($g log -1 --format='%h %s')"
    else
        echo "$tree already at $($g log -1 --format='%h %s')"
    fi
}
