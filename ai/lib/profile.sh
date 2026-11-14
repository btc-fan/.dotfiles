# ai/lib/profile.sh: which profile this machine runs (owner decision 2026-11-14). bash 3.2.
# Order: install.sh --profile NAME (or AI_PROFILE for the tools install.sh runs) > ~/.config/ai/profile >
# OS default (Linux: server, macOS: dev-mac). Each profile is ai/profiles/<name>.env (KEY=VALUE).

# ai_profile_resolve <ai dir> <os> [name]: sets AI_PROFILE, AI_PROFILE_FROM (flag|file|default) and the
# PROFILE_* keys of ai/profiles/<name>.env. False (message on stderr) for an unknown name.
ai_profile_resolve() {
    local dir=$1 os=$2 want=${3:-} from=flag file
    file=${AI_PROFILE_FILE:-$HOME/.config/ai/profile}
    if [ -z "$want" ] && [ -r "$file" ]; then
        want=$(sed -n '/^[[:space:]]*[^#[:space:]]/{s/[[:space:]]//g;p;q;}' "$file"); from=file
    fi
    if [ -z "$want" ]; then
        from=default
        case "$os" in macos) want=dev-mac ;; *) want=server ;; esac
    fi
    case "$want" in */*|.*|"") want=invalid ;; esac
    if [ ! -f "$dir/profiles/$want.env" ]; then
        printf 'ERROR: unknown profile "%s" (%s): use one of: %s\n' "$want" "$from" \
            "$(ls "$dir/profiles" 2>/dev/null | sed -n 's/\.env$//p' | tr '\n' ' ')" >&2
        return 1
    fi
    # shellcheck disable=SC1090
    . "$dir/profiles/$want.env"
    AI_PROFILE=$want
    AI_PROFILE_FROM=$from
    export AI_PROFILE AI_PROFILE_FROM PROFILE_SCANNERS PROFILE_PACKAGE_AUDIT PROFILE_AUDIT_GATE PROFILE_OPENCODE PROFILE_BOX PROFILE_LAST30DAYS
}

# profile_has_scanner <name>: true when this profile installs and runs that scanner.
profile_has_scanner() { case " ${PROFILE_SCANNERS:-guarddog skill-scanner osv-scanner} " in *" $1 "*) return 0 ;; esac; return 1; }
