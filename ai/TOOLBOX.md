# Toolbox

Good tools that are not part of daily work. Not installed by default and not loaded into agent context.
Root AGENTS.md has one pointer line to this file. Before the first install of any tool here: full audit
(agent-audit + code read), then move it into the setup if it becomes a default.

### rea
What: Lets an agent reverse engineer binaries, Electron apps and websites and explain how they work, with evidence.
Use when: you want to see how a closed app feature works, or inspect an Electron/JS app or a suspicious binary.
Install: `npx rea-agents setup` (adds an MCP server to your agent config).
Needs: Node 22+; Hopper, Ghidra or IDA for native binaries; no API keys.
Status: not audited yet / edits agent config, no sandbox, curl-to-bash installer exists, very fast star growth, check the npm publisher first

### hypit
What: Skill and CLI that lets an agent build and clone short videos (captions, B-roll, many variants).
Use when: you need many short video or ad variants from one script or reference clip.
Install: `npx skills add hypit-ai/hypit -g` (the agent downloads the executable on first use).
Needs: Node 22.15+, pnpm, headless Chromium; paid model APIs (HypiHub, Pollo or your own keys).
Status: not audited yet / custom license with commercial limits, sends media to third-party APIs, cloning videos has copyright risk, young repo

### MiroFish
What: Runs thousands of LLM agents on news or documents to simulate a scenario and write a prediction report.
Use when: you want to test how a policy, PR move or story might play out before acting.
Install: clone, copy `.env.example` to `.env`, add keys, then `npm run setup:all` (Docker also possible).
Needs: LLM API key (OpenAI-compatible) and a Zep Cloud key; Node 18+, Python 3.11 or 3.12, uv.
Status: not audited yet / AGPL-3.0, seed data goes to LLM and Zep Cloud, high token cost, last release March 2026

### thinking-orbs
What: Animated dotted "thinking" loading indicators for AI and agent UIs (9 types, 2 sizes, auto dark/light). React component, plus a React Native port.
Use when: you build a chat or agent interface and need a polished "agent is thinking" indicator.
Install: npm package in the app project (check the exact package name in its README).
Needs: nothing (UI component, no keys, no network).
Status: not audited yet / MIT, UI library only (not an agent tool), last push 2026-08-16

### claude-watch
What: Lets Claude watch a video: scene-change frames, transcript and a structured report (hook analysis of the first 10 s, optional Obsidian save). Claude + Codex plugin.
Use when: you need Claude to analyse a video (YouTube link or local file), for example ad or short-form content review.
Install: Claude plugin from taoufik123-collab/claude-watch (pin commit 7711231 when audited); then run its setup.py once.
Needs: ffmpeg, ffprobe, yt-dlp; optional GROQ_API_KEY or OPENAI_API_KEY for Whisper when a video has no captions.
Status: not audited yet / reads videos, not Claude sessions; SessionStart hook only prints setup status; setup.py runs brew install; audio goes to Groq/OpenAI only if a key is set; keeps its own keys in ~/.config/watch/.env (move to secrets.env if adopted)
