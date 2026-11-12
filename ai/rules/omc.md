# oh-my-claudecode (OMC), package oh-my-claude-sisyphus

Pin: 5.8.4. Default route (owner decision 2026-11-12): Claude plugin `oh-my-claudecode@omc` from marketplace `Yeachan-Heo/oh-my-claudecode#v5.8.4`, commit `b93059fb7c10ae28934a0bc950e26c9a17437a94` (`OMC_PLUGIN_REF`, `OMC_PLUGIN_SHA` in `ai/pins.env`). Old npm route (`AI_OMC_WIRING=cli`): package `oh-my-claude-sisyphus@5.8.4`, sha512 `sha512-6J2v4YomI8vK4mmhDTMV8SqS2Bj4dUvPz3ApapKsYVN6P04rGs0/L78p3/Rda0mq1UuHOYII8ubj+ehlgmxxwA==`. Source: https://github.com/Yeachan-Heo/oh-my-claudecode

## Vendor rules (verbatim)
The verbatim template is the file `ai/rules/vendor/omc-5.8.4-CLAUDE.md` (from `package/docs/CLAUDE.md` of the sha512-verified 5.8.4 package, 6,001 bytes). Markers: `<!-- OMC:START -->`, `<!-- OMC:VERSION:5.8.4 -->`, `<!-- OMC:END -->`.
Deviation: one U+2014 character in the original text was replaced by "-" (repo rule: no em dash). No other change.
The OMC block is never copied into AGENTS.md. Only the short form is.

## When / when not
- Servers: off by default (owner decision 2026-11-12): installed, `enabledPlugins` false at user scope. On for one project: `ai-adopt --tools omc` (sets `"enabledPlugins": {"oh-my-claudecode@omc": true}` in the project `.claude/settings.json`; the session start line then says "oh-my-claudecode is on here"). macOS: on everywhere. In a project where it is off, OMC skills, agents, hooks and its `t` MCP server do not load: do not call them.
- Use: multi-step coding, planning, review, verification in Claude Code. `/team`, ralph, autopilot loops. OMC state tools. Flow: plan, execute, review, verify.
- Do not use: single commands, small clarifications (OMC's own rule). Where a root rule decides the route: the repo AGENTS.md Map then rg for code, context7 for library docs.
- `omc ask <provider> --prompt "..."` returns a markdown file in `.omc/artifacts/ask/`. No `--json`. It needs the `omc` command line. The plugin route no longer installs it (a CLI installed earlier is left alone): if `omc` is not on PATH, use `claude -p` or `codex exec` directly.
- exa (OMC's web search MCP) is off: it sends search queries to an outside service. Do not turn it on, and never set `EXA_API_KEY` (OMC reads it from the environment and turns exa back on).
- What the plugin adds: MCP server `t` (tools `mcp__plugin_oh-my-claudecode_t__*`: state, notepad, project memory, LSP, ast-grep), hooks on SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest, PreCompact, SubagentStart, SubagentStop, Stop and SessionEnd, plus its skills and agents. Library docs: Grounded Docs and context7.
- Never run `omc intake schedule`. It writes the user crontab.
- Code facts go to the Map section of the repo AGENTS.md. Session notes go to the OMC notepad. OMC `project_memory` does not hold code facts.

## Enforcement
- L0: short form in AGENTS.md. Do not copy the vendor text.
- L1 to L3: OMC's own keyword hook fires first. Our L2 should skip prompts with an OMC keyword. This needs a new routing field `suppress_if_omc_keyword`: PROPOSED, not in routing.yaml v2.
- L4: the audit gate covers `npm i -g oh-my-claude-sisyphus` (cli route). Exact version only. Plugin route: install.sh installs only when the marketplace clone is at the pinned commit, else it warns and skips.
- L5: OMC agents (executor, writer, designer) do not carry our skills. SubagentStart context injects the L0 table.
- L7: ai-doctor checks the OMC version is 5.8.4 (plugin list, or `omc --version` on the cli route), `disableAutoUpdate` set, exa off, `OMC_REPLY_ENABLED` unset, `OMC_UPDATE_REGISTRY_BASE` set, no OMC line in crontab.
- Text order: owner text first, OMC block after. On a clash the owner text and hard rules win. Known clash: "verify before claiming completion" against the 60-word limit. Report the proof in telegraph style. Do not drop the verification.

## Proof
- Should fire (EN): "autopilot: build a CLI that converts CSV to JSON". Skill `oh-my-claudecode:autopilot`, files in `.omc/state/`.
- Should fire (RO): "Fa un deep interview despre aplicatia noua". Skill `oh-my-claudecode:deep-interview`. Keyword match inside Romanian text: UNVERIFIED, the test decides.
- Should not fire: "Ce face functia asta?". No OMC skill, no `.omc/state/` write.
- Signal: Skill tool_use with an `oh-my-claudecode:` name. `.omc/state/*.json`.
Tie-breaks (routing.yaml): "grill me" goes to matt grilling. "deep interview" goes to OMC. Research goes to OMC research. Wiki: llmwiki only where the project enabled it.

## Setup checklist
1. Plugin route (default, `AI_OMC_WIRING=plugin`): install.sh runs `claude plugin marketplace add Yeachan-Heo/oh-my-claudecode#v5.8.4`, checks `git -C ~/.claude/plugins/marketplaces/omc rev-parse HEAD` equals `OMC_PLUGIN_SHA` (refuses on mismatch; plugin.json at that commit says 5.8.4), then `claude plugin install oh-my-claudecode@omc --scope user`. Servers: install.sh then writes `enabledPlugins` false for it at user scope. Then once in Claude: `/oh-my-claudecode:omc-setup` (CLAUDE.md block, HUD), on a server inside a project with `omc` enabled. Old route: `AI_OMC_WIRING=cli` (`npm i -g --ignore-scripts oh-my-claude-sisyphus@5.8.4`, integrity against the sha512). `AI_OMC_WIRING=remove` drops the npm CLI. One route per machine.
2. Merge `${XDG_CONFIG_HOME:-~/.config}/claude-omc/config.jsonc`: `{"security":{"disableAutoUpdate":true},"mcpServers":{"exa":{"enabled":false}}}` (install.sh does it; a file with comments is a manual step).
3. Env in shell and unit files: `OMC_UPDATE_REGISTRY_BASE=http://127.0.0.1:9` (the daily npm ping ignores the setting). Never set `OMC_REPLY_ENABLED`.
4. Run `omc-setup` in a throwaway HOME first. Read the diff. Then real. How it upserts the CLAUDE.md block: UNVERIFIED. Diff the Mac's template against the 5.8.4 template.
5. Per project: gitignore `.omc/` except `.omc/skills/`.
6. Verify: `claude plugin list` shows oh-my-claudecode 5.8.4 (cli route: `omc --version`). `/oh-my-claudecode:omc-doctor` is clean. `/mcp` shows no exa server. Run the proof prompts.
7. Cleanup: `claude plugin uninstall oh-my-claudecode@omc` and `claude plugin marketplace remove omc`, or `npm rm -g oh-my-claude-sisyphus` on the cli route. Remove the OMC block from `~/.claude/CLAUDE.md`. Delete `~/.claude/claude-omc/` and `.omc/`. Check `crontab -l`.
Open: tmux nesting of `/team` under herdr is UNVERIFIED. Test on the server.
