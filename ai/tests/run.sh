#!/usr/bin/env bash
# Run all ai-core tests: router (every routing.yaml rule, fire + no-fire), commands, JSON files,
# knowledge layer (ai-libs, ai-adopt knowledge steps), installer setup (Codex trust, permissions, env),
# the box MCP server, the newest-stable resolver and update paths, the owner decisions of 2026-11-14
# (drops, off-by-default plugins, Serena take over, Homebrew rtk, OMX node path, last30days),
# Tier 1 (checks, stop check, ledger, ratchet), the ship/merge/release flow with scenario and bypass tests,
# the eval harness (ai-eval: fixtures, install level on fake binaries, stream scorer, behaviour --dry).
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
    python3 "$here/test_tier1.py" || rc=1
    python3 "$here/test_flow.py" || rc=1
    python3 "$here/test_profiles.py" || rc=1
    python3 "$here/test_eval.py" || rc=1
    python3 "$here/test_skills.py" || rc=1
fi
exit "$rc"
