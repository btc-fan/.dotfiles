## Server projects (boxes)

These rules are imported into AGENTS.md by the `ai` branch. Source: `ubuntu-server` branch,
`docs/AGENTS-hosting.md`. Human rules: `docs/HOSTING.md`.

- You work inside one box. Your project is /srv/app. Your data is /srv/data.
- Stay in your box. Do not try to reach the host, other boxes or the home network.
- Inside your box you may install, change and restart anything.
- Do not create new projects or boxes. Ask the owner to run `proj new`.
- Do not delete boxes, volumes, snapshots or databases outside your box. Only the owner runs `proj`.
- Never run `docker system prune`, `docker volume prune` or `docker compose down -v`
  unless the task says so and it is inside your box.
- Never drop a database unless the task says so and it lives inside your box.
- Before a risky change, ask the owner for `proj snapshot <box>`, or say it in your plan.
- Secrets live in /srv/app/.env. Never print them, commit them or send them anywhere.
- Never commit .env, keys or dumps.
- Use git worktrees under /srv/app/wt/<task> when more than one agent works on the project.
- In a long box, data is precious: no destructive migration without a backup and the owner's OK.
- Host projects (listed in /srv/proj/REGISTRY.md) are never yours to change.
- If you find yourself on the host (not inside a box), stop and tell the owner.
- Read /srv/proj/REGISTRY.md (if you can see it) to learn names. Do not change it.
