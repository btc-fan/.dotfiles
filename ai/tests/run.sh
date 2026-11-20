#!/usr/bin/env bash
# Run all ai-core tests: router (every routing.yaml rule, fire + no-fire), commands, JSON files,
# knowledge layer (ai-libs, ai-adopt knowledge steps), installer setup (Codex trust, permissions, env),
# the box MCP server, the newest-stable resolver and update paths, the owner decisions of 2026-11-14
# (drops, off-by-default plugins, Serena take over, Homebrew rtk, OMX node path, last30days),
# Tier 1 (checks, stop check, ledger, ratchet), the ship/merge/release flow with scenario and bypass tests,
# the eval harness (ai-eval: fixtures, install level on fake binaries, stream scorer, behaviour --dry).
# Usage: bash ai/tests/run.sh [-v] [-k <name part>]
# AI_TESTS_NO_AGENT=1 (CI) leaves out the test files that need a logged-in agent, and names them.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
rc=0

# Test files that need a logged-in agent. None today: each test uses a fake claude and codex.
agent_tests=""
if [ "${AI_TESTS_NO_AGENT:-}" = 1 ]; then
    echo "left out (needs a logged-in agent): ${agent_tests:-none}"
fi

python3 "$here/test_router.py" "$@" || rc=1
if [ $# -eq 0 ] || [ "$1" = "-v" ]; then
    python3 "$here/test_commands.py" || rc=1
    python3 "$here/test_knowledge.py" || rc=1
    python3 "$here/test_info.py" || rc=1
    python3 "$here/test_setup.py" || rc=1
    python3 "$here/test_box.py" || rc=1
    python3 "$here/test_resolve.py" || rc=1
    python3 "$here/test_m3.py" || rc=1
    python3 "$here/test_cleanup.py" || rc=1
    python3 "$here/test_evidence.py" || rc=1
    python3 "$here/test_tier1.py" || rc=1
    python3 "$here/test_flow.py" || rc=1
    python3 "$here/test_profiles.py" || rc=1
    python3 "$here/test_eval.py" || rc=1
    python3 "$here/test_skills.py" || rc=1
    python3 "$here/test_verify.py" || rc=1
    if [ "${AI_TESTS_NO_AGENT:-}" != 1 ]; then
        for t in $agent_tests; do python3 "$here/$t" || rc=1; done
    fi
fi
exit "$rc"
