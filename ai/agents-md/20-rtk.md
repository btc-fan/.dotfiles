RTK
A hook rewrites shell commands to rtk (example: git status becomes rtk git status) to cut output.
- Full output (security tools, debugging): rtk bypass <cmd>.
- A refused command: rtk pipeline explain shows the rule. Never use --ultra-compact (removed in 1.0).
- uv run is not rewritten: write uv run rtk pytest and uv run rtk ruff check by hand.
