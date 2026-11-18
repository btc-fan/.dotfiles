# 23: code smells from the review of PR #13

**What to build:** the smaller code smells that the PR #13 review found are removed. No behavior changes.

**Blocked by:** 22 (review fixes)

**Status:** ready-for-agent

- [ ] One UTC time format: replace the copies of `time.strftime("%Y-%m-%dT%H:%M:%SZ", ...)` with `hooklib.iso_now`, with an optional `ts` argument.
- [ ] One way to reach `log_wall`: today `ai-start` has its own `wall()`, `ai-precommit` imports hooklib, and `agent-audit` runs `python -c`.
- [ ] `ai-precommit` `git_text` copies `hooklib.git_quick`: use the hooklib helper.
- [ ] `router.verify_may_block` copies the loop limits of `stop-check.py`: one source for the limits.
- [ ] `gate_pr` does two jobs (the body template and the verify proof of hook 4): split it into two functions.
- [ ] `ai-render` reads a fixed index (`lines[3]`): parse the line by its content.
- [ ] The gitleaks rule contract and the SPEC-LOG line are missing: add them.
- [ ] Imports inside functions (hooklib and others): move them to the top of the module where no start-up cost speaks against it.
- [ ] The verify tool `decision()` and `ai-eval` `replay_hook` parse hook output in different ways: use one parser.
- [ ] The verify tool `fixture_env` and `ai-eval` `checkout_setup` build the same environment twice: use one.
