# Sourced by the MCP wrappers. Reads KEY=VALUE lines from ~/.config/ai/secrets.env without
# running the file as code, and exports only the keys asked for. Never prints a value.
# Usage: load_secrets KEY [KEY...]
load_secrets() {
    _f="${AI_SECRETS_FILE:-$HOME/.config/ai/secrets.env}"
    [ -r "$_f" ] || return 0
    for _k in "$@"; do
        eval "_cur=\${$_k:-}"
        [ -n "$_cur" ] && continue
        _v=$(sed -n "s/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}$_k=//p" "$_f" | tail -n 1)
        _v=${_v%\"}; _v=${_v#\"}; _v=${_v%\'}; _v=${_v#\'}
        [ -n "$_v" ] && export "$_k=$_v"
    done
    unset _f _k _v _cur
}
