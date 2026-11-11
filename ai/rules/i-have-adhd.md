# i-have-adhd

Pin: commit 1ecea1993b7fce257ffbd686c070948b5e07eda6 (package.json 0.4.1). Source: https://github.com/ayghri/i-have-adhd

## Vendor rules (verbatim)
The verbatim skill text is the file `ai/rules/vendor/i-have-adhd-1ecea19-SKILL.md` (byte copy of `skills/i-have-adhd/SKILL.md` at the pin). The repo has no CLAUDE.md snippet. Its AGENTS.md is a contributor map.

## When / when not
- Always on, every reply, every session. It is a typed-only skill (`disable-model-invocation: true`), so the always-on flag does the work.
- Off only on "stop adhd mode" or "normal mode", for that session.
- Break the rules in the six cases of the vendor list (explain, destructive action, debug spiral, real ambiguity, rule fights the task, rule fights the harness).
- Not for generated documents, code comments, PR bodies. They follow the writing style (STE).

## Enforcement
- L0: AGENTS.md "Output shape". Only layer for opencode. For Hermes the rules are appended to SOUL.md.
- L1: the vendor SessionStart hook (`startup|resume|clear|compact`) injects "ADHD MODE ACTIVE (always-on)" when the flag file exists.
- L2 to L5: none.
- L7: ai-doctor checks the injected string. Stop hook samples answers for preamble and closers.
- Conflict: the 60-word limit wins, except for the state line and the Next line.

## Proof
- Should fire (EN): "How do I rotate the JWT secret in this repo?" First line is an action. Numbered steps. Last line starts with `Next:`.
- Should fire (RO): "Cum adaug o coloana noua in tabelul listings?"
- Should not fire: "walk me through how the diff engine works" (long body allowed, no preamble). "stop adhd mode" gets a one-line confirm.
- Signal: SessionStart context contains `ADHD MODE ACTIVE (always-on)`.

## Setup checklist
1. Prerequisite: `node` on PATH (fallback hook `always-on.sh`).
2. Do not paste the README "install from url" prompt (unpinned).
3. Clone to the audited location, `git checkout 1ecea1993b7fce257ffbd686c070948b5e07eda6`, run `agent-audit dir`.
4. Claude: `claude plugin marketplace add <path>`, `claude plugin install i-have-adhd@i-have-adhd --scope user`.
5. Flag file: `touch ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.i-have-adhd-always`. The hook reads the same path for Codex.
6. Hermes: append the rules to SOUL.md in a managed block with a version marker. opencode: vendor plugin path UNVERIFIED, test it.
7. Codex: plugin command and one-time `/hooks` trust UNVERIFIED.
8. Telemetry: none found. Auto-update: none (local path marketplace).
9. Verify: new session shows "ADHD MODE ACTIVE (always-on)". `claude plugin list` shows it enabled.
10. Cleanup: `rm` the flag file, `claude plugin uninstall i-have-adhd@i-have-adhd`, `claude plugin marketplace remove i-have-adhd`, remove the SOUL.md block.
