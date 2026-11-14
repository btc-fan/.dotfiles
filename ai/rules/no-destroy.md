# no-destroy gate (destructive commands)

Our own gate in `hooklib.py` (`gate_destroy`), shaped like `no-sudo` (Tier 1 T6). Ideas from
claude-code-safety-net (MIT, README read 2026-11-12). Not taken: dcg (its license gives no rights to Anthropic,
OpenAI or anyone acting for them).

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
Blocked (on parsed command stages, also inside `bash -c`, behind `rtk`, `env`, `timeout`; `cd` is followed:
bare `cd`, `cd ~`, `cd $HOME` = home, `cd $X`, `cd -`, `popd` = unknown, then any non-rebuildable `rm -r` is blocked):
- `rm -r` (any `-r`, `-R`, `--recursive`) whose target is `/`, the home folder or a parent of it, the repo root
  or a parent of it, `.git` (but `.git/rebase-*` and `.git/*.lock` are fine), a wildcard at those places, a data
  folder at the repo top level (`data`, `pgdata`, `postgres`, `mysql`, `volumes`, `db`, `backup(s)`) or a database
  file (`*.sqlite`, `*.db`), a variable path it cannot resolve (`$TMPDIR`, `$tmpdir` are fine), `$(...)` or
  backticks, `~+` / `~-` forms, each `{a,b}` alternative, or a path outside the repo (temp folders and other
  worktrees of the repo are fine).
- `git push` with force (`-f`, `--force`, `--force-with-lease`, `+ref`) to `main` or `master` (also with no
  refspec, `HEAD` or `@` while on them), `--delete main`, `:main`, `--mirror`.
- `git reset --hard` on `main` or `master` with uncommitted tracked changes.
- `git clean` with `-f` and `-x`/`-X` at the repo root without a path, or with `:/` from anywhere (deletes `.env`,
  local databases).
- `docker compose down -v` / `--volumes` (also `docker-compose`, `podman compose`), `docker volume rm|prune`,
  `docker system prune --volumes`.
- Per repo, `.ai/destructive.txt`: `db: <name>` makes SQL `DROP DATABASE|SCHEMA|TABLE`, `TRUNCATE` and
  `DELETE FROM x` without `WHERE` through psql/mysql/sqlite3/duckdb (also `docker exec`, heredoc, `-f file`,
  `< file.sql`, a pipe) and `dropdb`, `pg_restore --clean` against that database a block; `cmd: <prefix>` blocks
  a command prefix (`cmd: launchctl bootout`).
Allowed: rebuildable folders (`node_modules`, `.venv`, `dist`, `build`, `__pycache__`, `.pytest_cache`,
`target`, `graphify-out`, `*.egg-info` ...), text that only mentions a command (`grep "DROP TABLE" docs/`,
commit messages), scratch databases.

## Enforcement
- L4 gate (deny; Codex deny with `decision: block`); deny wins over the absolute-path rewrite of `git push`.
- Owner skip: `sudo ai-gate-skip no-destroy <minutes> <why>` (logged).
- Limits: a script file, `find -delete`, `xargs rm` and other indirection are out of reach. The real boundary:
  the sandbox, branch protection on GitHub, and a database role without DROP/TRUNCATE for the agent.

## Proof
- Should fire (EN): `rm -rf ~`; `git push --force origin main` (BLOCK).
- Should fire (RO): "sterge tot folderul data si refa-l" -> `rm -rf data/` (BLOCK).
- Should fire (RU): "удали все тома докера" -> `docker compose down -v` (BLOCK).
- Should not fire: `rm -rf node_modules`; `grep "DROP TABLE" docs/`.
- Signal: `DENY no-destroy` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/no-destroy.json` (attack
  table: 60 block rows, 34 allow rows).

## Setup checklist
- Install: part of the ai-core router. Keys, telemetry: none.
- Per project: `.ai/destructive.txt` (committed) with `db:` and `cmd:` lines where a project has a database or a
  service an agent must never stop.
- Verify: `bash ai/tests/run.sh -k no-destroy`.
- Cleanup: none (part of the router); a project removes its `.ai/destructive.txt` lines.
