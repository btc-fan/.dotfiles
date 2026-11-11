# oh-my-codex (OMX)

Pin: 0.22.6. sha512 `sha512-ZpMHipwnaiHV/T8rp/czmF5U+ugqVdUOb28obL5U61q9WQwvfKAmzP4k1V82EnUXYMvsBgZIzFl0I3HADBbFEQ==` (compare with `npm view oh-my-codex@0.22.6 dist.integrity` at install). Published 2026-11-10. Install NOT before 2026-11-17. Source: https://github.com/Yeachan-Heo/oh-my-codex

## Vendor rules (verbatim)
The verbatim template is the file `ai/rules/vendor/omx-0.22.6-AGENTS.md` (from `package/templates/AGENTS.md` of the sha512-verified package, 23,904 bytes). Markers: OMX:RUNTIME, OMX:TEAM:WORKER, OMX:GUIDANCE:OPERATING, OMX:GUIDANCE:SPECIALIST-ROUTING, OMX:MODELS (each `<!-- X:START --> ... <!-- X:END -->`).
Deviation: 4 U+2014 characters replaced by "-". No other change.WARNING: the template starts with an autonomy directive: "DO NOT STOP TO ASK 'SHOULD I PROCEED?' - PROCEED." That clashes with the owner rule to confirm hard-to-reverse and outward actions. The owner rule wins. Never edit inside the OMX block. Our short form in AGENTS.md says it.

## When / when not
- Use: Codex-side orchestration and team runs.
- Do not use: for Claude Code work (use OMC). Never in one session together with OMC. Not with native features until the unsigned download is solved.
- Non-interactive: `omx exec [codex exec args] "<prompt>"`. JSON: Codex `--json`. `omx ask claude|gemini` writes a markdown file.

## Enforcement
- L0: 3 lines, no vendor text. L1, L2: Codex SessionStart and UserPromptSubmit hooks if supported. OMX hook names and the one-time `/hooks` trust prompt: UNVERIFIED.
- OMX repairs its managed `config.toml` region at launch. Our keys stay outside that region.
- L4: the audit gate covers `npm i -g oh-my-codex`.
- L7: ai-doctor runs `omx doctor` and checks `OMX_AUTO_UPDATE=0`, `OMX_NATIVE_AUTO_FETCH=0`.
- Our markers `<!-- AI:<tool> v<N> START/END -->` stay apart from OMX markers. A project with an OMX block counts as a vendor-installed block: skip ours and report.
- Size: the OMX block plus the 30 KB root needs `project_doc_max_bytes = 65536`.

## Proof
- Should fire (EN): "ralph: keep going until all tests pass" in Codex with OMX. Keyword from the template: UNVERIFIED.
- Should fire (RU): "Сделай deep interview по новому проекту". Match inside Russian text: UNVERIFIED.
- Should not fire: "list files in this dir". Plain Codex, no OMX state.
- Signal: OMX state under `.omx/` (path UNVERIFIED), `omx doctor`, smoke string `OMX-EXEC-OK`.

## Setup checklist
1. `npm i -g --ignore-scripts oh-my-codex@0.22.6`. Verify integrity. After 2026-11-17.
2. Env in shell and every unit file: `OMX_AUTO_UPDATE=0`, `OMX_NATIVE_AUTO_FETCH=0`. `OMX_REPLY_ENABLED` unset. No native binaries.
3. Codex first (device-code login). Then `omx setup` in a throwaway HOME. Read the diff. Then real. Set `project_doc_max_bytes = 65536`. File list touched by setup: UNVERIFIED.
4. Per project: gitignore `.omx/` (path UNVERIFIED). No block by us if OMX added its own.
5. herdr transport of OMX: keep off. Never follow its `curl ... | sh` error text.
6. Verify: `omx --version` says 0.22.6. `omx doctor` clean. `omx exec --skip-git-repo-check -C . "Reply with exactly OMX-EXEC-OK"` prints it.
7. Cleanup: `npm rm -g oh-my-codex`. Remove the OMX block and its `config.toml` part (command UNVERIFIED). Delete `~/.cache/oh-my-codex/` and `.omx/`.
