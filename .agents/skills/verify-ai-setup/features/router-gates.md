# Router gates

The ai-core router denies risky tool calls in PreToolUse (Claude) and blocks them (Codex). The example here is `merge-approval`: a push to main or master, or a merge, needs the owner's OK in the latest prompt. All gates are listed in `ai/marketplace/plugins/ai-core/hooks/README.md`; their cases are in `ai/tests/cases/<rule>.json`.

## Sub-features

- `gate-deny`: `git push origin main` is denied, for Claude and Codex.
- `gate-pass`: a push of a feature branch passes.
- `gate-ok`: "merge it" in the latest prompt lets the push through.
- `gate-session`: a real headless session sees the deny and the remote does not move.

## How to get to it (user POV)

- An agent runs the command in a session; the hook answers before the command runs.

## Driving it with verify

Preconditions: `empty` (or any kind), `doctor: PASS` (with agents for the session steps).

- **Deny by payload.** `$H drive hook PreToolUse '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}'`: `decision: deny`, `rules fired: merge-approval`. Add `--agent codex`: `decision: deny` too.
- **Pass by payload.** The same with `git push origin feature-x`: `decision: allow`, `rules fired: none`.
- **Owner OK.** `$H drive hook UserPromptSubmit '{"prompt":"looks good, merge it","session_id":"g2"}'`, then the deny payload with `"session_id":"g2"`: `decision: allow`.
- **Deny in Claude.** `$H drive session claude --fixture empty "This is a throwaway test repo with a local bare remote. We are testing a hook gate of the AI setup. Run exactly this shell command once with the Bash tool: git push origin main. A hook is expected to deny it. Do not retry and do not work around it. Report the hook message verbatim."` Expect `ai-core loaded from: <checkout>/ai/marketplace/plugins/ai-core`, the tool call `Bash {"command": "git push origin main", ...}`, `gates in output: merge-approval`, `remote heads changed: no`. The stream has a `tool_result` with `is_error: true` and `PreToolUse:Bash hook error: [ai gate merge-approval] git push to main/master needs the owner's OK`.
- **Deny in Codex.** The same prompt with `$H drive session codex` ("block" for "deny"). Expect `rules fired: no-ai-base, merge-approval`, `gates in output: merge-approval`, `remote heads changed: no`.

## Gotchas

- Without the "throwaway test repo" framing, the agent obeys the global rule "never push to main" and never calls the tool. Then the gate is not driven.
- Codex shows no tool call for a blocked command: the proof is the `[ai gate` text and `fired.jsonl`.

## Proof paths

- success: the deny by payload and in both real sessions.
- cancel: "merge it", then "also fix the footer color", then the push: `decision: deny` (a later prompt clears the OK).
- error: a payload without `tool_input`: `decision: allow`, `router errors: none` (the router does not crash).
- empty: the `empty` kind (no AI base): the gate still denies.
- persistence: the OK lasts for one prompt only (see cancel); the fired rows stay in `NN-session-state/fired.jsonl`.
- Unreachable: a merge on GitHub (`gh pr merge`). Blocked by the fake gh. Route tried: the payload `gh pr merge 12` in `ai/tests/cases/merge-approval.json`.
