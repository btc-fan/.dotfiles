# Playwright MCP (microsoft/playwright-mcp)

Pin: `@playwright/mcp` 0.0.85 (Apache-2.0). Intake done 2026-11-11 (SPEC section 21). Never `@latest`. Source: https://github.com/microsoft/playwright-mcp

## Vendor rules
No rule text. README: "coding agents increasingly favor CLI-based workflows exposed as SKILLs over MCP because CLI invocations are more token-efficient". The vendor itself points away from an always-on MCP. Flags: `--headless`, `--isolated`, `--caps`.

## When / when not
- Per project only. NOT registered at user scope. Claude has no default-off switch for user servers.
- Use for screenshots, clicking through pages, e2e checks.
- Outside a project that enabled it, the `browser-not-enabled` row says: ask the owner to run ai-start. Do not install a browser tool yourself.
- On servers: `--headless --isolated`.

## Enforcement
- L3: opt-in row `browser` (in enabled projects). Global row `browser-not-enabled` elsewhere.
- Added per project by ai-adopt or ai-start: `claude mcp add --scope project playwright -- npx @playwright/mcp@<pin> --headless --isolated`. Codex: project `.codex/config.toml`.

## Proof
- Should fire (EN, enabled project): "open http://localhost:8501 and take a screenshot".
- Should fire (RO): "deschide pagina si da click pe butonul de login".
- Should not fire (project without it): the same prompt gets the ai-start pointer and no install.
- Signal: tool_use `mcp__playwright__*` in an enabled project. The nudge text in a project without it.

## Setup checklist
1. Per machine: nothing global. Browser download happens at first use per project: pre-install with the pinned package and note the size (UNVERIFIED).
2. Per project: ai-start or ai-adopt adds the entry. Project `.mcp.json` servers need approval in Claude.
3. Telemetry: not checked in the intake (0 threat hits, no install scripts). Keep it per project and read its README flags at install.
4. Verify: `claude mcp list` in the project shows it. In another project it is absent.
5. Cleanup: `claude mcp remove playwright --scope project`, remove the Codex table.
Intake done 2026-11-11: 0 threat hits, no install scripts (SPEC section 21).
