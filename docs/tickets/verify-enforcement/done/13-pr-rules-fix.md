# 13: pr-rules reads the real body file and blocks only on the core template

**What to build:** the PR template gate reads the body file the command uses, and blocks only on the core parts. Measured: about 26 blocks, about half false.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `--body-file "$B"` and a body file written earlier in the same command are read correctly (or the gate says plainly it could not read them, and does not report every field as missing).
- [x] Blocks: Summary with a Mermaid diagram, Evidence, Merge Danger (Door, Blast Radius), the author-sessions block. Warns only: Docs, Changed guards.
- [x] The "could not diff against the base branch" case is fixed for a base other than main (seen on base `ai`).
