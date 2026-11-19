# 19: Writes through a shell script skip the writing-for-agents gate and the em dash lint

**What to build:** a Bash command that writes an agent document (AGENTS.md, CLAUDE.md, CLAUDE.local.md, SKILL.md) through an interpreter (`python3 - <<EOF ... write_text`, `perl -pi`, `node -e ... writeFileSync`) gets the same writing-for-agents gate as `cat > AGENTS.md`. Text written through Bash is linted for the em dash too.

**Blocked by:** None (can start immediately)

**Status:** done (R-014)

Reproduced 2026-11-19 with verify-ai-setup (`.verify/evidence/20261119T093247Z-nav-first-audit`; again on 59ce5b8: `20261119T122655Z-gate-bypass-before`, fixed: `20261119T123431Z-gate-bypass-after`), a session without the skill loaded:
- `cat > AGENTS.md <<EOF`: deny (the gate parses shell redirections);
- `python3 - <<EOF` with `pathlib.Path("AGENTS.md").write_text(...)`: allow (the bug).
The `no-em-dash` row triggers only on Edit and Write (`tool_after: 'Edit|Write'`).

- [x] Red: a writing-for-agents case with a python heredoc that writes AGENTS.md expects deny.
- [x] Green: the gate also matches an agent-document path named in an interpreter heredoc or `-c`/`-e` script of the command.
- [x] A PostToolUse check after Bash: a changed tracked file with U+2014 gets the no-em-dash nudge.
