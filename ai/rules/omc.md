# oh-my-claudecode (OMC), package oh-my-claude-sisyphus

Pin: 5.8.4. sha512 `sha512-6J2v4YomI8vK4mmhDTMV8SqS2Bj4dUvPz3ApapKsYVN6P04rGs0/L78p3/Rda0mq1UuHOYII8ubj+ehlgmxxwA==`. Source: https://github.com/Yeachan-Heo/oh-my-claudecode

## Vendor rules (verbatim)
The verbatim template is the file `ai/rules/vendor/omc-5.8.4-CLAUDE.md` (from `package/docs/CLAUDE.md` of the sha512-verified 5.8.4 package, 6,001 bytes). Markers: `<!-- OMC:START -->`, `<!-- OMC:VERSION:5.8.4 -->`, `<!-- OMC:END -->`.
Deviation: one U+2014 character in the original text was replaced by "-" (repo rule: no em dash). No other change.
The OMC block is never copied into AGENTS.md. Only the short form is.

## When / when not
- Use: multi-step coding, planning, review, verification in Claude Code. `/team`, ralph, autopilot loops. OMC state tools. Flow: plan, execute, review, verify.
- Do not use: single commands, small clarifications (OMC's own rule). Where a root rule decides the route: Serena for code symbols, Grounded Docs for library docs.
- `omc ask <provider> --prompt "..."` returns a markdown file in `.omc/artifacts/ask/`. No `--json`.
- Never run `omc intake schedule`. It writes the user crontab.
- Code facts go to Serena memories. Session notes go to OMC notepad.

## Enforcement
- L0: short form in AGENTS.md. Do not copy the vendor text.
- L1 to L3: OMC's own keyword hook fires first. Our L2 should skip prompts with an OMC keyword. This needs a new routing field `suppress_if_omc_keyword`: PROPOSED, not in routing.yaml v2.
- L4: the audit gate covers `npm i -g oh-my-claude-sisyphus`. Exact version only.
- L5: OMC agents (executor, writer, designer) do not carry our skills. SubagentStart context injects the L0 table.
- L7: ai-doctor checks `omc --version` is 5.8.4, `disableAutoUpdate` set, `OMC_REPLY_ENABLED` unset, `OMC_UPDATE_REGISTRY_BASE` set, no OMC line in crontab.
- Text order: owner text first, OMC block after. On a clash the owner text and hard rules win. Known clash: "verify before claiming completion" against the 60-word limit. Report the proof in telegraph style. Do not drop the verification.

## Proof
- Should fire (EN): "autopilot: build a CLI that converts CSV to JSON". Skill `oh-my-claudecode:autopilot`, files in `.omc/state/`.
- Should fire (RO): "Fa un deep interview despre aplicatia noua". Skill `oh-my-claudecode:deep-interview`. Keyword match inside Romanian text: UNVERIFIED, the test decides.
- Should not fire: "Ce face functia asta?". No OMC skill, no `.omc/state/` write.
- Signal: Skill tool_use with an `oh-my-claudecode:` name. `.omc/state/*.json`.
Tie-breaks (routing.yaml): "grill me" goes to matt grilling. "deep interview" goes to OMC. Research goes to OMC research. Wiki: llmwiki only where the project enabled it.

## Setup checklist
1. `npm i -g --ignore-scripts oh-my-claude-sisyphus@5.8.4`. Check `npm view oh-my-claude-sisyphus@5.8.4 dist.integrity` against the sha512. Optional: `npm rebuild better-sqlite3` in the package dir. One route per machine (plugin or npm). Whether the plugin route matches the pin: UNVERIFIED.
2. Merge `~/.claude/claude-omc/config.jsonc`: `{"security":{"disableAutoUpdate":true}}`.
3. Env in shell and unit files: `OMC_UPDATE_REGISTRY_BASE=http://127.0.0.1:9` (the daily npm ping ignores the setting). Never set `OMC_REPLY_ENABLED`.
4. Run `omc-setup` in a throwaway HOME first. Read the diff. Then real. How it upserts the CLAUDE.md block: UNVERIFIED. Diff the Mac's template against the 5.8.4 template.
5. Per project: gitignore `.omc/` except `.omc/skills/`.
6. Verify: `omc --version` says 5.8.4. `/oh-my-claudecode:omc-doctor` is clean. Run the proof prompts.
7. Cleanup: `/plugin uninstall` or `npm rm -g oh-my-claude-sisyphus`. Remove the OMC block from `~/.claude/CLAUDE.md`. Delete `~/.claude/claude-omc/` and `.omc/`. Check `crontab -l`.
Open: tmux nesting of `/team` under herdr is UNVERIFIED. Test on the server.
