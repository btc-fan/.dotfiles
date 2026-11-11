# RTK (Rust Token Killer)

Pin: tag v1.2.0, built from source on CPUs without AVX2. Source: https://github.com/rtk-ai/rtk

## Vendor rules (verbatim)
The owner block A.4 is the source text. It sits in `ai/agents-md/20-rtk.md`. Vendor facts, verbatim:
- "The hook only fires on Bash tool calls. Built-in tools like `Read`, `Grep` and `Glob` do not pass through it. Use shell commands (`cat`, `rg`, `find`) or call `rtk read`, `rtk grep`, `rtk find` directly."
- "`rtk proxy <cmd>` is a deprecated alias of `rtk bypass <cmd>`."
- "Not the same thing as `rtk llm-proxy`."
- Telemetry: "off by default ... it sends nothing until you opt in ... via `rtk telemetry enable`."
- "If `rtk gain` fails, you have the wrong package installed" (reachingforthejack/rtk).

## When / when not
- Always, for every agent with a Bash tool and a supported hook: Claude (PreToolUse), Codex (PreToolUse plus AGENTS.md), Hermes (Python plugin).
- The agent does not call `rtk` itself. The hook rewrites. Manual use only for `rtk gain`, `rtk gain --history`, `rtk discover`, `rtk bypass <cmd>`, `rtk pipeline explain`.
- Not for built-in Read, Grep, Glob. `uv run` is not rewritten: in a project that needs it, type `uv run rtk pytest` by hand.
- Use `rtk bypass` for debugging and always for security tools (agent-audit, gitleaks, osv-scanner), so findings are not truncated.
- Mac: the owner turned the hook off. Never turn it on silently. Ask. Macs are out of scope now.

## Enforcement
- L0: block A.4. L1 to L3: none. L4: RTK's own pipeline gate (run `rtk pipeline explain` when refused).
- L5: Claude subagents inherit the hook. Codex and Hermes use their own config.
- L7: `rtk gain --history` lists rewritten commands. `rtk discover` lists misses.
- Our gates read the Bash command. After a rewrite the text has `rtk` in front. Our regexes use `\b`. Test it. Put our gates before RTK when the order is configurable.

## Proof
- Should fire (EN): "show git status and the last 5 commits". Bash calls become `rtk git status`, `rtk git log ...`.
- Should fire (RU): "покажи статус git и последние 5 коммитов".
- Should not fire: "read src/md999/gql.py" (built-in Read). A command already prefixed `rtk bypass`.
- Signal: new row in `rtk gain --history` with non-zero reduction. Whether the transcript shows the rewritten command: UNVERIFIED.

## Setup checklist
1. Ubuntu without AVX2: `apt install cargo rustc pkg-config libssl-dev`, `git clone --depth 1 --branch v1.2.0 https://github.com/rtk-ai/rtk`, `agent-audit dir`, `cargo build --release --locked`, `install -m 755 target/release/rtk /usr/local/bin/rtk` (about 8 min). Same route on other machines for one uniform pin. No `brew install rtk`. No curl installer.
2. Edition (full or oss) and the BUSL-1.1 license of the full edition: owner confirms. UNVERIFIED.
3. Always `rtk init ... --dry-run` first and read the diff. Decline the proxy daemon. Skip the CLAUDE.md edit (AGENTS.md has the block).
4. Per agent, after the dry run: `rtk init -g` (Claude), `rtk init -g --codex` (Codex), `rtk init --agent hermes` (Hermes). Restart the agent. Hermes global scope: UNVERIFIED.
5. Telemetry: never run `rtk telemetry enable`. Status command UNVERIFIED. Auto-update: none for a source build.
6. Verify: `rtk --version` prints `rtk 1.2.0`. `which rtk`. `rtk gain` works. In a session run `git status`, then `rtk gain --history` shows it.
7. Cleanup: `rtk init -g --uninstall` (flag UNVERIFIED, check `rtk init --help`). Fallback: remove the PreToolUse entry, `RTK.md`, any `@RTK.md` line, the Codex and Hermes entries, `/usr/local/bin/rtk`.
