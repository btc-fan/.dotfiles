#!/usr/bin/env bash
# Run all ai-core tests: router (every routing.yaml rule, fire + no-fire), commands, JSON files.
# Usage: bash ai/tests/run.sh [-v] [-k <name part>]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
rc=0
python3 "$here/test_router.py" "$@" || rc=1
if [ $# -eq 0 ] || [ "$1" = "-v" ]; then
    python3 "$here/test_commands.py" || rc=1
fi
exit "$rc"
