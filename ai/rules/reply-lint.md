# reply lint (Stop: reply length and em dash)

Our own wall (code `reply_lint_stop` in `router.py`). No `routing.yaml` row, as `pr-url`.

## When / when not
- At Stop, the router reads the reply (`last_assistant_message`). An agent without this field is not checked.
- Em dash: one or more U+2014 characters outside code block the stop.
- Length: more than the limit plus 30 words blocks the stop. The limit is 60.
- The length check does not count fenced code, a `State:` line or a `Next:` line. Tables and lists count.
- No length check after a prompt that asks for detail, or a prompt that starts with `/`.
- One block per chain. A continuation stop (`stop_hook_active`) passes.

## Enforcement
- Stop wall `reply-lint`. Owner skip: `sudo ai-gate-skip reply-lint <min> <why>`.
- `AI_REPLY_WORDS` (env or `~/.config/ai/config.env`) sets the limit. The value 0 turns the length check off.

## Proof
- Should fire: 95 words after "fix it"; an em dash.
- Should not fire: the same reply after "explain in depth", "explica detaliat" or "объясни подробно".
- Tests: `ai/tests/cases/reply-lint.json`.

## Setup checklist
- Install: part of the ai-core router.
- Verify: `python3 ai/tests/test_router.py -k reply-lint`.
