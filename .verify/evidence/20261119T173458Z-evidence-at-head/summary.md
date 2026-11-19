# verify-ai-setup run: evidence-at-head

Feature: verify evidence in git, at the code commit of the PR. Fixture: `python-with-tests`.

| Step | Result | File |
|---|---|---|
| Doctor (`--no-agents`) | PASS | `run.log` |
| `ai-adopt --yes` writes the evidence lines in the managed block | PASS | `01-cli.txt` |
