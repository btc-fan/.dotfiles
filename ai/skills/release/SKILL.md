---
name: release
description: 'Use when the owner says release, cut a version, tag v1.2, "lansare", "релиз". Runs a full audit of the app before the tag (web, SEO, performance, UI, accessibility, usability, mobile, API, migrations, blog, security; each only where it applies), turns findings into fix PRs for the owner, then tags the version. Not for one feature branch (use the ship skill).'
---

# Release: full audit, then the tag

A release holds several merged features. This audit looks at the whole app, not one diff.
Work on a branch `release-<version>`. Every fix is a PR for the owner (ship skill per fix). Never tag before the
owner says the fixes are merged or accepted.

## 1. Scope

- `git log --oneline <last tag>..main` (no tag: the whole history). List the features in this release.
- Detect what exists: web pages, mobile app (iOS, Android), API, DB migrations, blog content, design system.
  Skip an area that does not exist and say so in the report.

## 2. Audit (one section per area that exists)

| Area | How |
|---|---|
| Security | `/security-review` on `<last tag>..main`; dependency audit (`pip-audit`, `npm audit`, `osv-scanner scan -r .`); secrets (the secret-scan gate covers commits) |
| Architecture | `/improve-codebase-architecture` focused on the release changes; graphify clusters for hot modules |
| Web performance | Lighthouse on the main pages (`npx lighthouse@<exact version> <url> --output json`, ask first), or the project's own perf test |
| SEO | `claude-seo` site audit (`/seo audit <url>`), when the tool is on here; else suggest `ai-adopt --tools seo` |
| Blog | `claude-blog` review of posts changed in this release, when on here |
| UI, accessibility, usability | ui-ux-pro-max pre-delivery checklist on every changed screen against `design-system/<app>/MASTER.md`; keyboard, contrast 4.5:1, touch targets 44 px |
| Mobile | both platforms build; app size compared with the last release; the verify skill on a device or simulator |
| API | compare the API surface with the last tag; a breaking change needs an ADR and a version bump |
| Migrations | each migration since the last tag runs up and down on a copy; expand-then-contract for renames |
| Tests | `make check` green; the ratchet did not get worse since the last tag |
| Verify tool | the project has a `verify-<app>` skill: run `maintain-verification-skill` yourself (Skill tool, or read its SKILL.md). It drives every feature of the map; its corrections are one fix PR |

## 3. Report

Write `docs/releases/<version>.md`: features, one line per area (pass, findings, skipped and why), and the fix PRs.
Tell the owner the result in 5 lines.

## 4. Tag (only after the owner's OK)

`git tag -a v<version> -m "<one line>"` on main, then `git push origin v<version>`. Add the release notes with
`gh release create v<version> --notes-file docs/releases/<version>.md`.
