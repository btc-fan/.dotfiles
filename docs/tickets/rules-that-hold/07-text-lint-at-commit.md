# 07: The commit hook refuses the em dash and warns on a long sentence

**What to build:** `git commit` refuses a staged added line that holds the em dash character (U+2014), for each person and each agent. It warns on a Markdown sentence over 25 words. The PR text check (ticket 06) covers the PR body. The reminder rows `no-em-dash` and `ste-sentence` leave the router, and one em dash check stays.

**Why:** The owner wants zero em dashes in code, docs, commit messages, PR text and replies (E1, row 151, MOVE-TO-CHECK). Today the rule is a PostToolUse reminder with no proof that it worked. The same check is written in many places: E1 names the reminder, `ai-docs-check --md`, `ai-render` and `ai-doctor`. E2 (list 3, item 5) also names `pstack_adapt.py` and `test_commands.py`.

**Solution:**
- `ai-precommit` calls the `text` gate of `ai-check` (ticket 05) on the staged added lines of text files. An em dash fails. A long Markdown sentence prints a warning and passes.
- The warning becomes a failure when the owner sets one key (`AI_STE_STRICT=1` in the owner config). The default is a warning.
- A `commit-msg` hook checks the commit message for the em dash. `ai-adopt` writes it next to the pre-commit hook, with the same conditions.
- The one function lives in `hooklib`. `ai-docs-check`, `ai-render` and `ai-doctor` call it. Their own regexes go.
- `pstack_adapt.py` replaces the character in vendored upstream text. That is a transform, not a check, so it stays and imports the same character constant.
- Remove the rows `no-em-dash` and `ste-sentence`, their case files, and their action placeholders.

**Rules kept:** "Never write the em dash character" moves from a reminder to the commit hook, the commit message hook and the PR text check. The STE 25-word rule stays text in the global file (KEEP-TEXT, E1 row 6), and its length part gets the commit warning. The rule text in `60-characters.md` stays until ticket 14 cuts it.

**Edge cases:**
1. The lint's own source must name the character. It is written as its code point escape, never as the literal character. A test greps the repo for the literal character and expects 0 hits.
2. Vendored and generated files (`ai/rules/vendor/`, `node_modules/`, lock files, `graphify-out/`): an allow list file `.ai/text-lint-allow` with globs. The default list holds these globs.
3. Binary files: `git diff --cached --numstat` marks them with `-`. They are skipped.
4. Quotes of other people (for example a research note that quotes another repo): the author adds the file glob to `.ai/text-lint-allow`. The refusal message names this way out.
5. Commit messages: the new `commit-msg` hook covers them. A repo with `core.hooksPath` (husky, lefthook) keeps its own hooks, and `ai-adopt` prints the 2 lines to add there (see `docs/tickets/setup-audit/07-commit-gate-with-own-hooks.md`).
6. Codex `apply_patch` and Claude `Write` no longer get feedback at write time. The agent learns at commit time, and the refusal names each file and line. This is the accepted cost of the move.
7. An existing file that already holds the character: only added lines are checked, so an old line does not block an unrelated commit.
8. `--no-verify` skips both hooks. The `no-verify` gate denies it in a session, and CI (ticket 06) checks the PR text.
9. Difference: `pstack_adapt.py` held the literal character, not the escape. It now imports `hooklib.EM_DASH`. `.verify/evidence/` (captured tool output) holds it too: it is in the default allow list.
10. Difference: the default globs live in `hooklib.TEXT_LINT_DEFAULT`, so a project needs no file. `.ai/text-lint-allow` only adds globs. Defaults: `vendor/`, `node_modules/`, `graphify-out/`, `.verify/evidence/`, lock files.
11. Difference: binary files have no added lines in `git diff --cached -U0`, so no `--numstat` call is needed. A rename adds no line either.
12. Difference: `long_sentences` moved from `router.py` to `hooklib`. The sentence check reads each run of added lines alone, so a new line inside an old paragraph is read without its old part.
13. Difference: `ai-docs-check --md` now also refuses an em dash inside a Markdown code block, because it calls the same function as the commit hook. It uses the same allow list.
14. Difference: the commit message check cuts the text at the `git commit -v` scissors line. It keeps the `#` lines, because `git commit -F` keeps them in the message.
15. A file that must hold the character on purpose: add its glob to `.ai/text-lint-allow`. Code builds it from the code point (`chr(0x2014)`).
16. Difference: the PR title and body go into one file, and the job `pr-text` runs `ai-check text --pr-body` on it after `pr-rules`.

**Owner steps:** None.

**Blocked by:** 05

**Status:** ready-for-agent

**Size:** S

- [x] `git commit` in a plain terminal refuses a staged line with the em dash and names the file and line.
- [x] A commit message with the em dash is refused by the `commit-msg` hook.
- [x] A Markdown sentence of 30 words gives a warning, and the commit passes.
- [x] `ai/routing.yaml` has no row `no-em-dash` and no row `ste-sentence`.
- [x] `grep` proof in the PR: one em dash pattern in code, in `hooklib`.
- [x] A file glob in `.ai/text-lint-allow` lets a quote pass.

**Verify:**
- Unit: `ai/tests/test_flow.py` gets `t_precommit_em_dash`, `t_commit_msg_em_dash`, `t_ste_warning_only` and `t_text_lint_allow`. Remove `ai/tests/cases/no-em-dash.json` and `ai/tests/cases/ste-sentence.json`.
- Drive: `$H drive cli --fixture docs-only` with a staged em dash, then a real `git commit` in the fixture. Gate change: a real Claude session drive that writes the character and commits, and a Codex payload drive of the same commit.
- Behaviour scenario: the ticket 02 gate scenarios still pass.

**Rollback:** Revert. The reminder rows and their case files come back.
