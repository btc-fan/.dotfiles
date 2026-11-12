# opencode (opencode-ai)

Pin: 1.19.5. sha512 `sha512-tEqMvQahfhdDj8vceYpXtoIrvjPXm5XRfetWnPN5YISueU7adNx9JcUA3zZ+2GKuDVgDpGdQe1ZLtCZDjqodvA==`. Binary package `opencode-linux-x64@1.19.5`: `sha512-i1qh7VooLGML9xX6ud93y0JA8j/1aPeDYRKjsmYXrJX1TjIWHgBBMkEbEJPZthpWbsJg//XfBgR6Kb7+NPaJiQ==`. Docs: https://opencode.ai/docs/, https://opencode.ai/docs/skills/
Linux servers: not installed by default (owner decision 2026-11-12; the defaults there are Claude, Codex and Hermes). An earlier install is undone from its records. Bring it back with `AI_EXTRA_AGENTS=opencode,herdr` in the environment of install.sh. macOS: always installed.

## Vendor rules
NOT FOUND. opencode ships no rules template. It reads AGENTS.md as is, so the root file carries the rules. It reads `~/.claude/skills` and `~/.agents/skills`. It does not see Claude plugin skills.

## When / when not
- Use: as a second model front-end (Grok, Kimi, DeepSeek keys), as a fallback, for scripted runs.
- Do not use: for SEO and blog work. Hand it to Claude Code (`omc ask claude` or `claude -p`, no `--bare`) only when `claude` is logged in for this user. Else follow the claude-seo or claude-blog skill files directly (paths in `claude-seo.md`). The per-project opt-in is for Claude only; for opencode the skill files are always available.
- Non-interactive: `opencode run "<prompt>" --format json`. Other: `-m provider/model`, `--agent`, `-f file`. `opencode session list --format json`.
- Never run `opencode upgrade` (pipes an install script to bash).
- `opencode serve` is an HTTP API: bind to localhost or Tailscale only, with `OPENCODE_SERVER_USERNAME` and `OPENCODE_SERVER_PASSWORD`.

## Enforcement
- L0 only: AGENTS.md via the `instructions` key. No hooks found. Plugin per-prompt injection: UNVERIFIED. Do not rely on L2 or L3.
- L4: our audit gate does not run inside opencode, so `npm i` is ungated there. Mitigation: the rule text, and an empty or pinned `plugin` list (plugins install from npm at runtime).
- L6: skills in `~/.agents/skills` carry our descriptions. RO and RU phrases are in L0.
- L7: ai-doctor checks env vars and `opencode.json`. There is no miss log for opencode. This is a known gap.

## Proof
- Should fire (EN): `opencode run "Reply OPENCODE-OK" --format json`. The event stream contains the string.
- Should fire (RO): "Foloseste skill-ul writing-for-agents ca sa verifici AGENTS.md". A skill load from `~/.agents/skills`. Event shape: UNVERIFIED.
- Should not fire: an SEO request. Expect the hand-off to Claude Code, or the skill-file path when Claude is not logged in.

## Setup checklist
1. macOS, or a server with `AI_EXTRA_AGENTS=opencode`: `npm i -g --ignore-scripts opencode-ai@1.19.5`. Then `ln -f "$(npm root -g)/opencode-ai/node_modules/opencode-linux-x64/bin/opencode" "$(npm root -g)/opencode-ai/bin/opencode.exe"`. No AVX2 (`grep -c avx2 /proc/cpuinfo` is 0): use `opencode-linux-x64-baseline`. macOS package name and path: UNVERIFIED.
2. Env: `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1`, `OPENCODE_DISABLE_LSP_DOWNLOAD=1`. Optional `OPENCODE_DISABLE_CLAUDE_CODE=1`. Leave `OPENCODE_AUTO_SHARE` and `OTEL_EXPORTER_OTLP_ENDPOINT` unset.
3. Merge `~/.config/opencode/opencode.json`: `{"autoupdate":false,"share":"disabled"}` and the `instructions` key pointing at `~/.config/ai/AGENTS.md`.
4. Keys from `~/.config/ai/secrets.env`. Login commands: UNVERIFIED.
5. Verify: `opencode --version` says 1.19.5. The proof command works.
6. Cleanup: `npm rm -g opencode-ai`. Delete `~/.config/opencode/`, the data dir (path UNVERIFIED), the cache.
