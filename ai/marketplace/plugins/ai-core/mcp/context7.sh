#!/bin/sh
# context7 MCP (upstash). The key comes from the environment or ~/.config/ai/secrets.env
# (CONTEXT7_API_KEY). It goes in the server env, never in argv (argv is visible in ps).
# No npx at runtime: install.sh installs the newest stable release once per version (integrity checked,
# audited, --ignore-scripts) under ~/.local/share/ai/npm/context7-mcp-<version>/. This script starts the
# highest installed version, so it has no version line to keep in step (owner decision 2026-11-14).
set -eu
base="${AI_NPM_DIR:-$HOME/.local/share/ai/npm}"
bin=""
for v in $(ls -1 "$base" 2>/dev/null | sed -n 's/^context7-mcp-\([0-9][0-9.]*\)$/\1/p' | sort -t. -k1,1nr -k2,2nr -k3,3nr); do
    if [ -x "$base/context7-mcp-$v/node_modules/.bin/context7-mcp" ]; then
        bin="$base/context7-mcp-$v/node_modules/.bin/context7-mcp"
        break
    fi
done
if [ -z "$bin" ]; then
    echo "context7 MCP: no installed @upstash/context7-mcp under $base. Run install.sh (it installs the newest stable)." >&2
    exit 1
fi
. "$(dirname "$0")/load-secrets.sh"
load_secrets CONTEXT7_API_KEY
# Owner-approved exception (SPEC section 13): a free context7 key is committed as the default.
# A key in secrets.env or the environment wins. Rotate: change it here and in secrets.env.
: "${CONTEXT7_API_KEY:=ctx7sk-9779e36c-d13b-4453-9770-4f17e438c19b}"
export CONTEXT7_API_KEY
exec "$bin" "$@"
