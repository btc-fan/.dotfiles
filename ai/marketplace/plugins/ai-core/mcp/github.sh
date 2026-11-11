#!/bin/sh
# GitHub MCP (github/github-mcp-server), stdio, full access (SPEC 4). The binary is installed by
# install.sh at the version in ai/pins.env. The token comes from the environment or
# ~/.config/ai/secrets.env (GITHUB_PERSONAL_ACCESS_TOKEN). Never in this repo, never in argv.
set -eu
. "$(dirname "$0")/load-secrets.sh"
load_secrets GITHUB_PERSONAL_ACCESS_TOKEN
if [ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]; then
    echo "github MCP: GITHUB_PERSONAL_ACCESS_TOKEN is not set (add it to ~/.config/ai/secrets.env)" >&2
    exit 1
fi
export GITHUB_TOOLSETS="${GITHUB_TOOLSETS:-all}"
exec "${AI_GITHUB_MCP_BIN:-github-mcp-server}" stdio "$@"
