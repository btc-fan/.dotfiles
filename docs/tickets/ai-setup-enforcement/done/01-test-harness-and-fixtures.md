# 01: Test harness and fixtures

**What to build:** one command makes the fixture repos (empty git repo, docs-only repo, folder without git, small app with code, tests, make check and a verify-<app> skill, throwaway copy of an adopted project) and runs the install level (ai-adopt, second run, ai-doctor, uninstall) and the behaviour level (headless Claude and Codex sessions on the eval prompts, 3 runs, score from the router logs and the transcript).

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Fixtures are generated in a temp folder; no real repo is touched
- [x] Install level reports pass or fail per fixture
- [x] Behaviour level reports a score per rule and per skill, per agent
- [x] A dry mode runs without network and without agent sessions, for CI
