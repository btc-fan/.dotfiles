# verify-ai-setup run: evidence-in-git

Feature: verify evidence in git (spec `docs/specs/verify-evidence-in-git.md`). Fixture: `python-with-tests`.

| Step | Result | File |
|---|---|---|
| Doctor (`--no-agents`) | PASS | `run.log` |
| `ai-adopt --yes`: the block has `.verify/*`, `!.verify/evidence/`; `.verify/data/app.db` is not staged | PASS | `02-cli.txt` |
| `ai-evidence-prune` on a branch: removes the 18-day-old run, keeps the newest run of `cart` | PASS | `03-cli.txt` |
