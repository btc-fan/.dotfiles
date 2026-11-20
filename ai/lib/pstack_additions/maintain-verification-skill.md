## Our additions

These rules come from our AI setup, not from pstack. Where they differ from the steps above, these rules win. The full contract is the section `Our additions` of the `create-verification-skill` skill.

- Index hygiene also checks: each feature file has the `Proof paths` H2 (success, cancel, error, empty, persistence, and unreachable paths with their blockers); `features/README.md` keeps a full sweep order; `multi-surface-journeys.md` matches the flows that cross surfaces.
- A surface the repo has but the skill does not drive is drift. Add its driver.
- The live pass drives the features in the sweep order of `features/README.md`, then each journey. The doctor checks this checkout's own instance (its own port and data folder).
- The live pass is a run. The project helper writes `.verify/evidence/<run>/run.log` with the `commit`, `doctor`, `db_writes` and `finished` lines.
- Commit each run folder with the PR, like every run (`summary.md` first, no secrets). See the evidence rules of `create-verification-skill`.
