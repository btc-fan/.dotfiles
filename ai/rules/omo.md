# oh-my-openagent (omo), OPTIONAL

Not installed by default. Full intake audit before the first install. No routing.yaml row until the owner enables it.
Pin: UNVERIFIED. Run `npm view omo-ai version` before pinning. Source: https://github.com/code-yeongyu/oh-my-openagent (branch `dev`), omo.dev

## Vendor rules
NOT FOUND. Facts from the `dev` README on 2026-11-11: standalone `omo` CLI built on senpi. The opencode plugin is the legacy edition. License: Sustainable Use License 1.0 (internal and personal non-commercial use only). The owner's use for 1 to 2 friends may count as distribution: read the license text at intake.

## When / when not
- Use only when the owner asks. Keywords `ultrawork` / `ulw`, `mass ulw`.
- Do not use by default. Never `/bug` on a private project: it uploads the engine log, env, config, session transcript, device name and install id.
- No non-interactive model call and no JSON flag known. Helpers: `omo doctor [--models|--fix]`, `omo setup --yes|--dry-run`, `omo update --print`.

## Enforcement
- L0: none while off. When enabled, ai-adopt adds one line in a managed block `<!-- AI:omo vN START --> ... END -->` in the project AGENTS.md.
- L4: the gate blocks `curl -fsSL https://get.omo.dev/install.sh | bash`. Use `npm i -g --ignore-scripts omo-ai@<exact>` after the audit. Do not confuse it with the unrelated npm package `omo`.
- Proposed: add `/bug` to the denylist for private projects.
- L7: ai-doctor skips omo while off.
- On the first run omo migrates `~/.config/opencode` plugin config into `~/.omo` with a backup: run it in a throwaway HOME first.
- Never mix omo, OMC and OMX in one session.

## Proof
- Only after enabling. Should fire (EN): "ulw: refactor the parser". (RO): "ulw: refactorizeaza parserul". Should not fire: any prompt in a project without omo. Keyword matching in non-English text: UNVERIFIED.
- Signal: an omo agent name in the session. `omo doctor` clean.

## Setup checklist
1. Node 24 or newer. `npm i -g --ignore-scripts omo-ai@<exact>` after the audit.
2. Config `~/.omo/omo.jsonc`: `"telemetry": {"enabled": false}`, `"disabled_hooks": ["auto-update-checker", "startup-toast"]`, `"model_capabilities": {"auto_refresh_on_start": false}`.
3. Env: `OMO_DISABLE_TELEMETRY=1`, `OMO_SEND_ANONYMOUS_TELEMETRY=0`, `OMO_DISABLE_POSTHOG=1`. These names came from a summary: verify them in the code at the audit.
4. Login: `/login` inside omo. Details UNVERIFIED.
5. Verify: `omo --version`, `omo doctor`, `omo setup --dry-run`.
6. Cleanup: `npm uninstall -g omo-ai` or `rm ~/.local/bin/omo`. Delete `~/.omo/` and `.omo/`. Restore the opencode config from the migration backup if needed.
