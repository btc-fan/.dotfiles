# verify-ai-setup run: run-name

Feature: the run folder name `<branch>_<feature>_<DD-MM-YYYY>_<HH-MM-SS>`. Fixture: `python-with-tests`.

| Step | Result | File |
|---|---|---|
| `launch --label run-name` names this folder with the branch, the label and the EU time | PASS | this folder name |
| Doctor (`--no-agents`) | PASS | `run.log` |
| `ai-adopt --yes` on the fixture | PASS | `01-cli.txt` |
| `verify evidence` after cleanup finds this run (newest by folder time) and calls `run.log` proof | PASS | `run.log` |
