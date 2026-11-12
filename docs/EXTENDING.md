# Extending

How to add or change a part. Every new tool follows the same path:

intake + audit -> usage contract -> routing row -> evals -> reinstall -> `ai-doctor`.

Do not skip a step. A tool without a contract and evals fails `ai-doctor`.

Related: what each tool is and how tools overlap is in [TOOLS.md](TOOLS.md). How to change a rule in the root AGENTS.md, with examples, is in [AGENTS-MD.md](AGENTS-MD.md), section 6. Do not repeat that text here.

## 0. Intake and audit (for every new tool)

1. Investigate: maintainer, license, release dates, what data it sends out.
2. Audit the code and the installer before anything runs: `agent-audit npm|pypi|dir|skill <target>`. Read the install script. A finding means stop: show it to the owner.
3. Check overlap with tools we have. Write how they clash and what the impact is.
4. Decide: add, put in `ai/TOOLBOX.md`, or reject.
5. If added: write the contract, the routing row and the evals (below). Record the decision in `ai/SPEC.md` and the reason in `ai/SPEC-LOG.md`.
Judge the latest audited release for future machines. Do not rely on what one machine has installed.

## 1. Add a skill

1. Intake and audit (section 0). `agent-audit skill <path>`.
2. Own skill: put it in `ai/skills/<name>/SKILL.md`. Copy it to `ai/marketplace/plugins/ai-core/skills/<name>/`. Keep both equal.
   Third-party skill: pin the commit sha in `ai/pins.env`. Copy the whole folder at that sha. No `@latest`.
3. Description: triggers first, under 1,536 characters. Add Romanian and Russian trigger phrases.
4. Contract: `ai/rules/<name>.md` (section 5).
5. Routing: add a row in `ai/routing.yaml` (section 6) and a tie-break row if it overlaps another skill.
6. Evals: 3 should-fire prompts (English, Romanian, Russian) and 2 should-not-fire prompts. Put them in `ai/evals/`.
7. Reinstall and check: macOS `~/.dotfiles-ai/install.sh`; server: the admin command `sudo /opt/ai-setup/install.sh --update --for-user <user>`. Then `ai-doctor`.
Note: plugin skills cannot be hidden one by one. Think about the context cost.

## 2. Add an MCP server

1. Intake and audit. Check telemetry and set it off in the server `env`. Check what leaves the machine.
2. Pin the exact version in `ai/pins.env`. No `@latest`.
3. Default: per project, not global (every global server costs context in every session; owner decision 2026-11-12). Add it to `project_mcp_plan` in `ai/bin/ai-start` with an opt-in routing row, like Playwright. Only a server every project needs (today: context7) goes into `ai/marketplace/plugins/ai-core/.mcp.json`. Keys: `${VAR}` from `~/.config/ai/secrets.env`, and add the name to `secrets.env.example`. Do not commit a key. (One owner exception exists: the free context7 key.)
4. Codex: the installer runs `codex mcp add`. Hermes: `hermes mcp add`.
5. Plugin tool names are `mcp__plugin_ai-core_<server>__<tool>`. Use these names in hook matchers and in routing rows.
6. If the server must be per project (like Playwright), do not put it in `.mcp.json` of the plugin. Add it through `ai-start` and `ai-adopt`.
7. Contract, routing row, evals (sections 5 to 7). Reinstall. `ai-doctor` must show it connected.

## 3. Add a plugin

1. Intake and audit. Check its hooks: what do they run, what do they send.
2. Install from a pinned commit sha. Local path marketplace has no auto-update. For a third-party marketplace, turn auto-update off and record the sha.
3. Decide: a pinned `dependency` of `ai-core`, or a separate plugin that the installer adds. Global plugins only if every project needs them. Otherwise opt-in per project.
4. Check collisions: hooks on the same event, same skill names, same triggers.
5. Contract with a setup checklist (install, files touched, telemetry off, keys, per-machine steps, verify, cleanup). Routing row, evals.
6. Reinstall. `claude plugin list` and `ai-doctor`.

## 4. Add a routing rule

1. First ask: would one line in the root AGENTS.md or the project Map do? Passive context beats nudges, and v4 removed the nudges the logs showed ignored. A new nudge must show in `fired.jsonl` and `misses.jsonl` that it is followed. Then edit `ai/routing.yaml`. Fields: `id`, `scope` (global or opt-in), `trigger` (prompt regex, tool, command, paths, state), `action` (one short sentence), `strength` (nudge or gate).
2. Use a gate only for a rule with no exception. Its escape hatch is the owner-only `sudo ai-gate-skip <gate> <minutes> <why>`; never an in-command variable an agent could type.
3. A rule that overlaps another: add a row to `tiebreaks`.
4. Keep regexes strict. A loose prompt regex fires on unrelated prompts.
5. Run `ai-render`. It rebuilds `routing.json` and the L0 table. Check the root file size (under 30 KB). On other machines, `git pull` plus `ai-sync` delivers it (see [AGENTS-MD.md](AGENTS-MD.md)).
6. Add evals: one should-fire and one should-not-fire prompt for the rule.
7. Reinstall. `ai-doctor`. Look at `~/.local/state/ai/misses.jsonl` after a few days.

## 5. Write a usage contract

File `ai/rules/<tool>.md`. Sections, in order:
1. Vendor rules: the tool's own recommended rules text, verbatim, with the pin and the source link. If the vendor has none, say "NOT FOUND". Never paraphrase a block marked verbatim. Long text goes in `ai/rules/vendor/` as a byte copy. Replace U+2014 with "-" and say so.
2. When / when not.
3. Enforcement: which layers (L0 to L7) apply, the exact trigger, what the tool enforces itself.
4. Proof: should-fire and should-not-fire prompts (English, Romanian, Russian), and the signal that shows it fired.
5. Setup checklist: install and pin per OS, every config file and setting, telemetry and auto-update off, keys (required or optional), per-machine steps, per-project steps, verify command, cleanup paths.
For an MCP server or tool that can cache facts, add one more section, "Knowledge home, freshness, maintenance": where the cached facts live in the repo (one home per fact, see [TOOLS.md](TOOLS.md) "Where project knowledge lives"; for a repo that is its AGENTS.md), when they count as stale, and which command or nudge refreshes them. If a cache would go stale too fast (issues, PRs), say "none on purpose". Examples: `context7.md` (the Libraries section), `graphify.md` (graphify-out/), `playwright.md` (the Map).
Mark every fact you did not verify as UNVERIFIED. Do not guess.
Only if every agent needs it in every session: one short line in `ai/agents-md/90-toolbox-and-vendor-rules.md`. The root file stays well under 12 KB.

## 6. Add evals

1. Put cases in `ai/evals/`. Format: tool | FIRE (EN ; RO ; RU) | NOT (a ; b) | signal.
2. Pass bar: all fire cases fire, no NOT case fires.
3. Run method: `ai/evals/HOWTO.md`.
4. Re-run on every model change and every pin bump.

## 7. Add a toolbox entry

For good tools that are not part of daily work.
1. Light intake: what it does, license, what it sends, status.
2. Add an entry to `ai/TOOLBOX.md`: What, Use when, Install, Needs, Status.
3. The status says "not audited yet" until the full audit is done.
4. Before the first install: full audit (`agent-audit` and a code read). If it becomes a default, go to section 1, 2 or 3.
No routing row and no contract for a toolbox entry.

## 8. Bump a pin (re-audit)

1. Find the new release. Read its changelog.
2. Audit it again: `agent-audit` and a read of what changed.
3. Check the contract: did the vendor rules text change? Update the verbatim block, the pin line and the sha.
4. Change the pin in `ai/pins.env` and in the contract. Update the table in `docs/CONTEXT.md`.
5. Run the evals again.
6. Reinstall. `ai-doctor`.
A tool is never updated by the tool itself. Auto-update stays off.

## 9. Retire a tool

1. Remove the tool from the installer and the plugin (`.mcp.json`, hooks, skills).
2. Remove its routing rows and tie-break rows. Run `ai-render`.
3. Remove its short form from `ai/agents-md/90-toolbox-and-vendor-rules.md`.
4. Move the contract to a note in `ai/SPEC-LOG.md` (why it was dropped). Delete the file in `ai/rules/` and its evals. `ai-doctor` must not list it.
5. Follow the cleanup steps in the old contract on each machine.
6. Record the decision in `ai/SPEC.md` (section "Not adopted").
7. Reinstall. `ai-doctor`.
