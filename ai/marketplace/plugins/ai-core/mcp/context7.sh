#!/bin/sh
# context7 MCP (upstash), pinned. The key comes from the environment or ~/.config/ai/secrets.env
# (CONTEXT7_API_KEY). It goes in the server env, never in argv (argv is visible in ps).
# Version must equal CONTEXT7_MCP_VERSION in ai/pins.env (install.sh checks it).
set -eu
. "$(dirname "$0")/load-secrets.sh"
load_secrets CONTEXT7_API_KEY
# Owner-approved exception (SPEC section 13): a free context7 key is committed as the default.
# A key in secrets.env or the environment wins. Rotate: change it here and in secrets.env.
: "${CONTEXT7_API_KEY:=ctx7sk-9779e36c-d13b-4453-9770-4f17e438c19b}"
export CONTEXT7_API_KEY
exec npx -y @upstash/context7-mcp@4.6.0 "$@"
