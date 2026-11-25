# 26: The reply shape has a check

**What to build:** A Stop check `reply-lint` in the router. It blocks a reply with an em dash outside code. It also blocks a reply that is too long, unless the owner asked for detail.

**Why:** The owner's first rule is the reply shape: the answer first, at most 60 words. In 5 real sessions, the final replies had 74 to 155 words. A rule with a check holds (32 of 32 PR bodies). A rule with text only does not hold.

**Solution:**
- `reply_lint_stop` in `router.py`, in the form of `pr_url_stop`. It reads `last_assistant_message` and joins its reasons into one block.
- The length check counts the words outside fenced code. It does not count a `State:` or a `Next:` line. Tables and lists count.
- The block starts above the limit plus 30 words. The limit is 60, and `AI_REPLY_WORDS` changes it (0: off).
- `remember_reply_detail` at UserPromptSubmit keeps `reply_detail` in the session state. A detail word (EN, RO, RU) or a typed `/skill` sets it.

**Edge cases:**
1. A continuation stop passes, so the check cannot loop.
2. A notification turn keeps the flag of the last owner prompt.
3. An em dash in code (fenced or inline) does not count.

**Status:** done

**Size:** S

- [x] Cases in `ai/tests/cases/reply-lint.json` (17 cases).
- [x] Rule file `ai/rules/reply-lint.md`.

**Verify:** `python3 ai/tests/test_router.py -k reply-lint`.

**Rollback:** Remove the `reply_lint_stop` call from `on_stop`.
