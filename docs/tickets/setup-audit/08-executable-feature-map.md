# 08: One verify command per feature, and a map check without an agent

**What to build:** a generated `verify-<app>` tool has one command that runs the checks of one feature file (`verify <feature>`), and one command that compares the feature map with the app's real surfaces (routes, commands). An agent proves a change with one command. Drift in the map is found by a script, not by an agent pass.

Source: the kody project (`control-kody`). Its skill is 68 lines. `verify <id>` runs the request lines of the feature notes. `map --check` runs in CI after a route file changes. Our setup finds drift with `maintain-verification-skill`: one subagent per feature plus a live pass. That costs many tokens each time.

**Blocked by:** None (can start immediately)

**Status:** needs-triage (the verify-enforcement spec put "a feature map check in CI" out of scope; this ticket asks to look at that again)

- [ ] The owner decides if this is in scope.
- [ ] The generator text ("Our additions") asks for the two commands and gives the line format that the tool can run.
- [ ] The scenario fixture has both commands. A removed route makes the map check fail.
- [ ] The verify hooks accept a `verify <feature>` run as proof.
- [ ] `maintain-verification-skill` starts with the map check and reads only the features that the check names.
