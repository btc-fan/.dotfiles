# 09: The risk of a change comes from a script, and the proof follows the risk

**What to build:** a script reads the diff of a branch against a short map of the system parts and gives one risk class. The PR body gets its Merge Danger from that result. The verify hooks ask for proof that fits the class.

Source: the kody project (`visual-recap`). A classifier reads the diff against `primitives.yaml` (part id, owned paths, invariants, decision records). The result is `composes` (low: only wiring), `extends` (medium: local verify) or `adds` (high: map update plus verify). A second script checks the Mermaid block and replaces only the marked block in the PR body.

Today in our setup the agent writes Door and Blast Radius as free text, and the pr-rules gate only looks for the words. Each app-code change gets the same verify walls, small or large. The walls review of 2026-11-18 found many false blocks; proof that fits the risk gives fewer walls.

**Blocked by:** 08 (the low class needs the one-command verify to be cheap)

**Status:** needs-triage (the verify-enforcement spec put "kody's risk classes and visual recap" out of scope)

- [ ] The owner decides if this is in scope, and if the Map section of a project's `AGENTS.md` can be the map of parts.
- [ ] A script prints the class and the touched parts for a branch, as JSON.
- [ ] The PR body block comes from the script. Text outside the block is not changed.
- [ ] Verify hooks 2 and 4 ask for a run only for the medium and high classes, or the owner keeps them for all.
- [ ] A scenario shows one low change that passes with no wall and one high change that is blocked without proof.
