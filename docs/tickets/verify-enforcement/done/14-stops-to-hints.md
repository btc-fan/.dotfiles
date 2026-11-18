# 14: diagnosing-bugs and tdd become hints

**What to build:** a bug or tests-first prompt still shows the hint to use the skill, but no longer blocks the end of the turn. Measured: diagnosing-bugs 6 of 6 false stops, tdd 1 of 1.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Both rules are nudges in the routing table; the rendered rules and the skill card say so.
- [x] A research turn that mentions "debug" or "broken" ends without a block.
