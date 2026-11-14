#!/usr/bin/env bash
# Run all ai-core tests: router (every routing.yaml rule, fire + no-fire), commands, JSON files,
# knowledge layer (ai-libs, ai-adopt knowledge steps), installer setup (Codex trust, permissions, env),
# the box MCP server, the newest-stable resolver and update paths, the owner decisions of 2026-11-14
# (drops, off-by-default plugins, Serena take over, Homebrew rtk, OMX node path, last30days).
# Usage: bash ai/tests/run.sh [-v] [-k <name part>]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
rc=0
python3 "$here/test_router.py" "$@" || rc=1
if [ $# -eq 0 ] || [ "$1" = "-v" ]; then
    python3 "$here/test_commands.py" || rc=1
    python3 "$here/test_knowledge.py" || rc=1
    python3 "$here/test_info.py" || rc=1
    python3 "$here/test_setup.py" || rc=1
    python3 "$here/test_box.py" || rc=1
    python3 "$here/test_resolve.py" || rc=1
    python3 "$here/test_m3.py" || rc=1
fi
exit "$rc"
