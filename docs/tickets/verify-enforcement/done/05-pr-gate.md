# 05: Hook 4, the PR gate proves the final tree

**What to build:** `gh pr create`, `gh pr edit` and `gh pr ready` are denied when the PR changes app code and no valid tool log exists from a run on the PR head commit that is newer than the last code commit. Root and HEAD come from the checkout the command acts on. The old text-only check goes.

**Blocked by:** 03

**Status:** done

- [x] Red: a PR head with app code and only older logs: denied on create, edit and ready.
- [x] Green: a valid log at the head SHA: allowed.
- [x] A docs-only PR is not gated.
- [x] `cd <worktree> && gh pr create` reads the worktree HEAD, not the main checkout.
