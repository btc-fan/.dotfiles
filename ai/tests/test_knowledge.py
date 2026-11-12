#!/usr/bin/env python3
"""Tests for the knowledge layer: ai-libs (the Libraries block of AGENTS.md) and the ai-adopt Map and opt-ins.

Offline: a throwaway HOME, fake lockfiles, fake serena/graphify/claude on PATH, and a local HTTP
server on 127.0.0.1 that plays the context7 search API.
Run: python3 ai/tests/test_knowledge.py   (bash ai/tests/run.sh runs it too)
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
BIN = os.path.join(AI_DIR, "bin")
FAILS = []
DEAD_URL = "http://127.0.0.1:9"       # nothing listens on port 9: every request fails fast

PYPROJECT = """[project]
name = "demo"
version = "0.1.0"
dependencies = ["httpx>=0.27", "FastAPI[standard]>=0.115", "my_local_pkg"]
"""
UV_LOCK = """version = 1

[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "fastapi"
version = "0.115.6"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "my-local-pkg"
version = "0.0.1"
source = { editable = "libs/my_local_pkg" }
"""
PACKAGE_JSON = json.dumps({"name": "web", "dependencies": {"react": "^18.3.1", "shared": "workspace:*"},
                           "devDependencies": {"vitest": "^2.1.0"}})
PACKAGE_LOCK = json.dumps({"lockfileVersion": 3, "packages": {
    "": {"name": "web"},
    "node_modules/react": {"version": "18.3.1", "resolved": "https://registry.npmjs.org/react/-/react-18.3.1.tgz"},
    "node_modules/vitest": {"version": "2.1.4"},
    "node_modules/react/node_modules/loose-envify": {"version": "1.4.0"}}})
GO_MOD = """module example.com/demo

go 1.22

require (
\tgithub.com/spf13/cobra v1.8.1
\tgolang.org/x/sys v0.25.0 // indirect
)
"""
CARGO_TOML = """[package]
name = "demo"
version = "0.1.0"

[dependencies]
serde = { version = "1", features = ["derive"] }
helper = { path = "../helper" }
"""
CARGO_LOCK = """version = 3

[[package]]
name = "serde"
version = "1.0.210"
"""


def main():
    work = tempfile.mkdtemp(prefix="ai-knowledge-tests-")
    server = FakeServer()
    try:
        for test in (t_libs_offline, t_libs_cache_and_notes, t_libs_online_fake, t_libs_check_stale,
                     t_libs_private_sources, t_libs_check_refuses_sync, t_libs_old_file_migrates, t_adopt_knowledge,
                     t_adopt_optin_serena_graph, t_adopt_gitignore_block, t_adopt_secret_in_map, t_optin_claude_plugins,
                     t_map_tools_read_only):
            try:
                test(work, server)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
    finally:
        server.stop()
        shutil.rmtree(work, ignore_errors=True)
    print("%d knowledge tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- ai-libs

def t_libs_offline(work, server):
    repo = make_repo(work, "offline")
    res = libs(work, repo, "--sync", url=DEAD_URL)
    assert res.returncode == 0, res.stdout
    assert "context7 not reachable" in res.stdout, res.stdout
    rows = table(repo)
    assert set(rows) == {"httpx", "fastapi", "my-local-pkg", "react", "shared", "vitest", "github.com/spf13/cobra",
                         "serde", "helper"}, sorted(rows)
    assert rows["httpx"]["version"] == "0.28.1" and rows["fastapi"]["version"] == "0.115.6", rows
    assert rows["react"]["version"] == "18.3.1" and rows["vitest"]["version"] == "2.1.4", rows
    assert rows["github.com/spf13/cobra"]["version"] == "v1.8.1" and rows["serde"]["version"] == "1.0.210", rows
    assert "golang.org/x/sys" not in rows, "indirect go dependency listed"
    assert rows["httpx"]["context7"] == "?", "offline lookup must leave ? (retried next sync)"
    assert rows["my-local-pkg"]["note"] == "local package" and rows["my-local-pkg"]["context7"] == "-", rows
    assert rows["shared"]["note"] == "local package" and rows["helper"]["note"] == "local package", rows
    text = open(os.path.join(repo, "AGENTS.md")).read()
    assert text.startswith("# offline\n"), "AGENTS.md created with a title: " + text[:40]
    start = [ln for ln in text.splitlines() if ln.startswith("<!-- AI:libraries START")][0]
    for name in ("uv.lock", "package-lock.json", "Cargo.lock"):
        assert name + " sha256:" in start, start
    assert "## Libraries" in text and "<!-- AI:libraries END -->" in text
    assert not os.path.exists(os.path.join(repo, ".ai", "libs.md")), "old .ai/libs.md written"
    before = open(os.path.join(repo, "AGENTS.md")).read()
    res = libs(work, repo, "--sync", "--offline", url=DEAD_URL)
    assert open(os.path.join(repo, "AGENTS.md")).read() == before and "up to date" in res.stdout, "resync changed bytes"


def t_libs_cache_and_notes(work, server):
    repo = make_repo(work, "cache")
    libs(work, repo, "--sync", url=DEAD_URL)
    path = os.path.join(repo, "AGENTS.md")
    text = open(path).read()
    assert "| httpx | 0.28.1 | ? |  |" in text, text
    text = text.replace("| httpx | 0.28.1 | ? |  |", "| httpx | 0.28.1 | ? | keep me |")
    text = text.replace("# cache\n", "# cache\n\nOwner text above the block.\n") + "\nOwner text below the block.\n"
    open(path, "w").write(text)
    state = os.path.join(work, "state-cache")
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "docs-ids.jsonl"), "w") as fh:
        fh.write(json.dumps({"ts": "x", "repo": repo, "server": "context7", "lib": "httpx", "id": "/encode/httpx"}) + "\n")
        fh.write(json.dumps({"ts": "x", "repo": "/other", "server": "context7", "lib": "react", "id": "/facebook/react"}) + "\n")
        # router format (router.py log_docs_ids): context7 field; lib may be the version tail of a versioned ID
        fh.write(json.dumps({"ts": "x", "repo": repo, "tool": "mcp__plugin_ai-core_context7__query-docs",
                             "lib": "v2.1", "version": "", "context7": "/vitest-dev/vitest/v2.1", "grounded": ""}) + "\n")
    res = libs(work, repo, "--sync", url=DEAD_URL, state=state)
    rows = table(repo)
    assert rows["httpx"]["context7"] == "/encode/httpx", "router log not used: %s" % rows["httpx"]
    assert rows["httpx"]["note"] == "keep me", "note column lost"
    assert rows["react"]["context7"] == "/facebook/react", "log of another repo not used as fallback"
    assert rows["vitest"]["context7"] == "/vitest-dev/vitest/v2.1", "router-format log row not used: %s" % rows["vitest"]
    res = libs(work, repo, "--sync", "--offline", state=os.path.join(work, "empty-state"))
    assert table(repo)["httpx"]["context7"] == "/encode/httpx", "offline run dropped an existing ID: " + res.stdout
    text = open(path).read()
    assert "Owner text above the block." in text and text.rstrip().endswith("Owner text below the block."), text
    assert text.count("<!-- AI:libraries START") == 1, "block duplicated"


def t_libs_old_file_migrates(work, server):
    repo = make_repo(work, "migrate")
    os.makedirs(os.path.join(repo, ".ai"))
    with open(os.path.join(repo, ".ai", "libs.md"), "w") as fh:
        fh.write("# Library docs map.\nlock: uv.lock sha256:000000000000  synced: 2026-11-11\n\n"
                 "| lib | version | context7 | grounded-docs | note |\n|---|---|---|---|---|\n"
                 "| httpx | 0.28.1 | /encode/httpx | httpx@0.28.x | old note |\n")
    res = libs(work, repo, "--sync", "--offline")
    row = table(repo)["httpx"]
    assert row["context7"] == "/encode/httpx" and row["note"] == "old note", row
    assert "no longer used" in res.stdout, res.stdout


def t_libs_online_fake(work, server):
    repo = make_repo(work, "online")
    res = libs(work, repo, "--sync", url=server.url)
    assert res.returncode == 0, res.stdout
    rows = table(repo)
    assert rows["httpx"]["context7"] == "/encode/httpx/0.28.1", "exact version ID expected: %s" % rows["httpx"]
    assert rows["fastapi"]["context7"] == "/fastapi/fastapi", rows["fastapi"]
    assert rows["serde"]["context7"] == "-", "no exact match must give -, not a guess: %s" % rows["serde"]
    for name in ("my_local_pkg", "my-local-pkg", "shared", "helper"):
        assert all(name not in q for q in server.queries), "local or private name %s sent: %s" % (name, server.queries)
    assert server.auth and all(a == "Bearer test-key" for a in server.auth), server.auth
    before = len(server.queries)
    libs(work, repo, "--sync", url=server.url)
    assert len(server.queries) == before, "second sync looked up cached libraries again"


PY_ONLY = {"pyproject.toml": '[project]\nname = "p"\nversion = "0"\ndependencies = ["httpx", "fastapi"]\n'}
NODE_ONLY = {"package.json": json.dumps({"name": "n", "dependencies": {"react": "^18", "zod": "^3"}})}
GO_ONLY = {"go.mod": "module example.com/x\n\ngo 1.22\n\nrequire github.com/spf13/cobra v1.8.1\n"}
RUST_ONLY = {"Cargo.toml": '[package]\nname = "r"\nversion = "0.1.0"\n\n[dependencies]\nserde = "1"\n'}
FAKE_GO = "#!/bin/sh\n[ \"$1\" = env ] && printf '%s\\n' 'corp.example/*' '' '' 'https://proxy.golang.org,direct' ''\n"


def t_libs_private_sources(work, server):
    """Any non-public index anywhere: no name of that ecosystem goes out, every row is marked private."""
    cases = [
        ("uv-lock-lookalike-host", PY_ONLY, {"uv.lock": '[[package]]\nname = "httpx"\nversion = "0.28.1"\n'
                                             'source = { registry = "https://pypi.org.corp.example/simple" }\n'}, {}, ["httpx", "fastapi"]),
        ("pip-env", PY_ONLY, {}, {"PIP_INDEX_URL": "https://pypi.corp.example/simple"}, ["httpx", "fastapi"]),
        ("uv-extra-index-env", PY_ONLY, {}, {"UV_INDEX": "corp=https://pypi.corp.example/simple"}, ["httpx", "fastapi"]),
        ("uv-index-pyproject", {"pyproject.toml": PY_ONLY["pyproject.toml"] + '\n[[tool.uv.index]]\nname = "corp"\n'
                                'url = "https://pypi.corp.example/simple"\n'}, {}, {}, ["httpx", "fastapi"]),
        ("poetry-source", {"pyproject.toml": PY_ONLY["pyproject.toml"] + '\n[[tool.poetry.source]]\nname = "corp"\n'
                           'url = "https://pypi.corp.example/simple"\n'}, {}, {}, ["httpx", "fastapi"]),
        ("requirements-extra-index", {"requirements.txt": "--extra-index-url https://pypi.corp.example/simple\nhttpx==0.28.1\n"},
         {}, {}, ["httpx"]),
        ("pip-conf-home", PY_ONLY, {"HOME:.config/pip/pip.conf": "[global]\nindex-url = https://pypi.corp.example/simple\n"},
         {}, ["httpx", "fastapi"]),
        ("npmrc-unscoped", NODE_ONLY, {".npmrc": "registry=https://npm.corp.example/\n"}, {}, ["react", "zod"]),
        ("npmrc-scoped", NODE_ONLY, {".npmrc": "@corp:registry=https://npm.corp.example/\n"}, {}, ["react", "zod"]),
        ("npm-env", NODE_ONLY, {}, {"npm_config_registry": "https://npm.corp.example/"}, ["react", "zod"]),
        ("package-lock-resolved", NODE_ONLY, {"package-lock.json": json.dumps({"packages": {"node_modules/zod": {
            "version": "3.23.8", "resolved": "https://npm.corp.example/zod/-/zod-3.23.8.tgz"}}})}, {}, ["react", "zod"]),
        ("yarn-lock-resolved", NODE_ONLY, {"yarn.lock": 'zod@^3:\n  version "3.23.8"\n'
                                           '  resolved "https://npm.corp.example/zod/-/zod-3.23.8.tgz#abc"\n'}, {}, ["react", "zod"]),
        ("pnpm-lock-tarball", NODE_ONLY, {"pnpm-lock.yaml": "packages:\n  zod@3.23.8:\n    resolution: "
                                          "{tarball: https://npm.corp.example/zod-3.23.8.tgz}\n"}, {}, ["react", "zod"]),
        ("goprivate-env", GO_ONLY, {}, {"GOPRIVATE": "corp.example/*"}, ["github.com/spf13/cobra"]),
        ("go-env-command", GO_ONLY, {"BIN:go": FAKE_GO}, {}, ["github.com/spf13/cobra"]),
        ("cargo-registries", RUST_ONLY, {".cargo/config.toml": '[registries.corp]\nindex = "sparse+https://crates.corp.example/"\n'},
         {}, ["serde"]),
    ]
    for name, base, extra, env, libs_expected in cases:
        repo = os.path.join(work, "priv-" + name)
        home = os.path.join(work, "home-priv-" + name)
        fake = os.path.join(work, "bin-priv-" + name)
        for d in (repo, home, fake):
            os.makedirs(d)
        run(["git", "init", "-q", repo])
        for rel, text in list(base.items()) + list(extra.items()):
            if rel.startswith("HOME:"):
                path = os.path.join(home, rel[5:])
            elif rel.startswith("BIN:"):
                path = os.path.join(fake, rel[4:])
            else:
                path = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
            if rel.startswith("BIN:"):
                os.chmod(path, 0o755)
        before = len(server.queries)
        full = {"HOME": home, "PATH": fake + os.pathsep + "/usr/bin:/bin", "AI_CONTEXT7_URL": server.url,
                "CONTEXT7_API_KEY": "test-key",
                "AI_STATE_DIR": os.path.join(home, "state")}
        full.update(env)
        res = run([sys.executable, os.path.join(BIN, "ai-libs"), "--dir", repo, "--sync"], env=full)
        assert res.returncode == 0, "%s: %s" % (name, res.stdout)
        assert len(server.queries) == before, "%s: names sent: %s" % (name, server.queries[before:])
        assert "non-public index configured" in res.stdout, "%s: no notice: %s" % (name, res.stdout)
        rows = table(repo)
        for lib in libs_expected:
            assert rows[lib]["note"] == "private registry" and rows[lib]["context7"] == "-", "%s: %s" % (name, rows[lib])
    # control: public-only config still looks names up
    repo = os.path.join(work, "pub-control")
    os.makedirs(repo)
    run(["git", "init", "-q", repo])
    for rel, text in list(PY_ONLY.items()) + [("uv.lock", '[[package]]\nname = "httpx"\nversion = "0.28.1"\n'
                                                         'source = { registry = "https://pypi.org/simple" }\n')]:
        with open(os.path.join(repo, rel), "w") as fh:
            fh.write(text)
    before = len(server.queries)
    res = libs(work, repo, "--sync", url=server.url)
    assert "non-public" not in res.stdout and len(server.queries) == before + 2, (res.stdout, server.queries[before:])


def t_libs_check_refuses_sync(work, server):
    repo = make_repo(work, "check-sync")
    for combo in (["--check", "--sync"], ["--sync", "--check"], ["--check", "--refresh"], ["--check", "--offline"]):
        res = libs(work, repo, *combo, url=server.url)
        assert res.returncode != 0 and "read-only" in res.stdout, "%s accepted: %s" % (combo, res.stdout)
    assert not os.path.exists(os.path.join(repo, "AGENTS.md")), "refused run wrote AGENTS.md"


def t_libs_check_stale(work, server):
    repo = make_repo(work, "stale")
    assert libs(work, repo, "--check", url=DEAD_URL).returncode == 1, "no Libraries block must fail --check"
    libs(work, repo, "--sync", url=DEAD_URL)
    res = libs(work, repo, "--check", url=DEAD_URL)
    assert res.returncode == 0, res.stdout
    with open(os.path.join(repo, "uv.lock"), "a") as fh:
        fh.write('\n[[package]]\nname = "rich"\nversion = "13.9.4"\n')
    res = libs(work, repo, "--check", url=DEAD_URL)
    assert res.returncode == 1 and "uv.lock changed" in res.stdout, res.stdout


# ---------------------------------------------------------------- ai-adopt knowledge steps

FAKE_SERENA = """#!/bin/sh
case "$1 $2" in
  "project create")
    root="$4"; mkdir -p "$root/.serena/cache"
    printf '/cache\\n/project.local.yml\\n' > "$root/.serena/.gitignore"
    printf 'project_name: demo\\ninitial_prompt: ""\\n' > "$root/.serena/project.yml" ;;
esac
"""
FAKE_GRAPHIFY = """#!/bin/sh
if [ "$1 $2" = "hook status" ]; then
    if [ -f .git/hooks/post-commit ]; then echo "post-commit: installed"; else echo "post-commit: not installed"; fi
    exit 0
fi
if [ "$1 $2" = "hook install" ]; then echo "# graphify" > .git/hooks/post-commit; echo "post-commit: installed"; exit 0; fi
[ "$GRAPHIFY_BACKEND" = none ] || { echo "no LLM API key found" >&2; exit 3; }
[ "$1 $2 $3" = "extract . --code-only" ] || exit 4
mkdir -p graphify-out && echo '{"nodes": []}' > graphify-out/graph.json
"""
FAKE_CLAUDE = """#!/bin/sh
case "$*" in *conventions*) ;; *) exit 5 ;; esac
case "$*" in *Edit*|*Write*|*"Bash "*|*"Bash,"*) exit 6 ;; esac
[ -n "$FAKE_SECRET" ] && { echo "- token = $FAKE_SECRET"; exit 0; }
echo "Here are the conventions:"
echo "- New HTTP handlers go in src/app/handlers/, one file per route."
echo "- Never edit generated files under src/gen/."
"""


def t_adopt_knowledge(work, server):
    repo, env = adopt_repo(work, "adopt")
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--dry-run"], env=env, cwd=repo)
    assert res.returncode == 0, res.stdout
    # Serena and graphify are on by default (owner 2026-11-12, evening): planned without any --tools.
    for step in ("would write AGENTS.md", "would run Map conventions", "would run ai-libs --sync",
                 "would run serena project create --index", "would run GRAPHIFY_BACKEND=none graphify extract . --code-only",
                 "would run graphify hook install", "would write .gitignore"):
        assert step in res.stdout, "%s missing: %s" % (step, res.stdout)
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes"], env=env, cwd=repo)
    assert res.returncode == 0, res.stdout
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    assert "AGENTS.md" in files and "CLAUDE.md" in files, files
    assert ".serena/project.yml" in files, files
    assert not any(f.startswith(("graphify-out", ".ai/libs.md", ".serena/cache")) for f in files), files
    assert os.path.isfile(os.path.join(repo, ".git", "hooks", "post-commit")), "graphify hooks not installed"
    text = open(os.path.join(repo, "AGENTS.md")).read()
    assert text.index("<!-- AI:map START") < text.index("<!-- AI:libraries START"), "Map must come first"
    m = text[text.index("## Map"):text.index("<!-- AI:map END -->")]
    assert len(m.splitlines()) <= 61, "Map over 60 lines"
    for want in ("- What: adopt (Python)", "`src/` (1 code files)", "`app` -> `app.main:run`", "`uv run pytest`",
                 "- Conventions:", "New HTTP handlers go in src/app/handlers/"):
        assert want in m, "%s not in Map:\n%s" % (want, m)
    assert "Here are the conventions" not in m, "non-bullet chatter copied into the Map"
    assert "| httpx | 0.28.1 |" in text, "Libraries block missing"
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes"], env=env, cwd=repo)
    assert "nothing to change" in res.stdout, "rerun must be idempotent: " + res.stdout
    # owner edits inside the Map survive a rerun; --refresh-map rewrites it
    edited = open(os.path.join(repo, "AGENTS.md")).read().replace("- Conventions:", "- Owner note: keep me.\n- Conventions:")
    open(os.path.join(repo, "AGENTS.md"), "w").write(edited)
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes", "--no-onboard"], env=env, cwd=repo)
    assert "Owner note: keep me." in open(os.path.join(repo, "AGENTS.md")).read(), "rerun overwrote the Map"


def t_adopt_optin_serena_graph(work, server):
    repo, env = adopt_repo(work, "optin-sg")
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--tools", "serena,graph", "--yes",
               "--no-onboard"], env=env, cwd=repo)
    assert res.returncode == 0, res.stdout
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    for rel in (".serena/project.yml", ".claude/settings.json", ".gitignore"):
        assert rel in files, "%s not committed: %s" % (rel, files)
    assert ".serena/.gitignore" not in files, "only .serena/project.yml is shared"
    assert ".codex/config.toml" not in files, "Serena is global for Codex now: no project entry"
    assert ".mcp.json" not in files, "project .mcp.json is blocked by managed settings: Serena must use the plugin"
    assert not any(f.startswith(("graphify-out/", ".serena/cache")) for f in files), files
    plugins = json.load(open(os.path.join(repo, ".claude", "settings.json")))["enabledPlugins"]
    assert plugins == {"ai-serena@ai": True}, plugins
    gi = open(os.path.join(repo, ".gitignore")).read().splitlines()
    for line in (".serena/*", "!.serena/project.yml", "graphify-out/"):
        assert line in gi, "gitignore misses " + line
    assert os.path.isfile(os.path.join(repo, "graphify-out", "graph.json")), "graph not built"
    assert enabled_ids(repo) == ["graph", "serena"], enabled_ids(repo)
    agents = open(os.path.join(repo, "AGENTS.md")).read()
    assert "<!-- AI:serena v" in agents and "Details: ~/.config/ai/rules/serena.md" in agents, agents
    assert len(agents) < 4000, "opt-in blocks must stay short: %d bytes" % len(agents)


GI_BLOCK = [".omc/*", "!.omc/skills/", ".codex/", ".claude/*", "!.claude/settings.json", ".serena/*",
            "!.serena/project.yml", "graphify-out/", ".ai/*", "!.ai/enabled"]


def t_adopt_gitignore_block(work, server):
    """One managed .gitignore block: after ai-adopt only the shared files are new, everything else is ignored."""
    repo, env = adopt_repo(work, "gitignore")
    with open(os.path.join(repo, ".gitignore"), "a") as fh:     # an older ai-adopt run left an unmarked block
        fh.write("\n# AI tools (ai-adopt): caches and generated graph\n.serena/cache/\ngraphify-out/\n")
    run(["git", "-C", repo, "commit", "-qam", "old block"], env=env)
    for rel in (".codex/config.toml", ".omc/state/session.json", ".claude/settings.local.json"):   # tool state
        os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
        with open(os.path.join(repo, rel), "w") as fh:
            fh.write("{}\n")
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--tools", "omc", "--yes"],
              env=env, cwd=repo)
    assert res.returncode == 0, res.stdout
    files = set(run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split())
    want = {"AGENTS.md", "CLAUDE.md", ".gitignore", ".claude/settings.json", ".ai/enabled", ".serena/project.yml"}
    assert files == want, "committed %s, want %s" % (sorted(files), sorted(want))
    status = run(["git", "-C", repo, "status", "--porcelain", "--untracked-files=all"]).stdout
    assert status.strip() == "", "local tool files not ignored:\n" + status
    for local in (".ai/base-version", ".codex/config.toml", ".serena/cache", "graphify-out/graph.json"):
        assert os.path.exists(os.path.join(repo, local)), "%s was not created, the test proves nothing" % local
    gi = open(os.path.join(repo, ".gitignore")).read()
    lines = gi.splitlines()
    assert lines[0] == "node_modules/", "owner lines must stay first: %s" % lines[:2]
    assert "# AI tools (ai-adopt): caches and generated graph" not in gi, "old unmarked block not removed"
    start = lines.index("# >>> AI tools (managed by ai-adopt; edit outside this block) >>>")
    end = lines.index("# <<< AI tools <<<")
    assert lines[start + 1:end] == GI_BLOCK, lines[start + 1:end]
    assert gi.count(">>> AI tools") == 1
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes"], env=env, cwd=repo)
    assert "nothing to change" in res.stdout, "rerun must be idempotent: " + res.stdout
    # a project that already tracks .claude/commands keeps them shared
    os.makedirs(os.path.join(repo, ".claude", "commands"))
    with open(os.path.join(repo, ".claude", "commands", "deploy.md"), "w") as fh:
        fh.write("deploy\n")
    run(["git", "-C", repo, "add", "-f", ".claude/commands/deploy.md"], env=env)
    run(["git", "-C", repo, "commit", "-qm", "command"], env=env)
    run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes"], env=env, cwd=repo)
    assert "!.claude/commands/" in open(os.path.join(repo, ".gitignore")).read().splitlines()


def t_adopt_secret_in_map(work, server):
    repo, env = adopt_repo(work, "secret")
    env["FAKE_SECRET"] = "ghp" + "_" + "Q7" * 18
    head = run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--yes"], env=env, cwd=repo)
    assert res.returncode == 1 and "secret scan found" in res.stdout, res.stdout
    assert run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout == head, "commit happened despite a secret"


def t_map_tools_read_only(work, server):
    """The headless Map pass may only read: no Edit, Write, plain Bash, or any MCP tool."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("ai_start_mod", os.path.join(BIN, "ai-start"))
    spec = importlib.util.spec_from_loader("ai_start_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    loader.exec_module(mod)
    tools = mod.MAP_TOOLS
    assert set(tools) <= {"Read", "Grep", "Glob", "Bash(git ls-files:*)", "Bash(rg:*)"}, tools
    assert not any(t.startswith("mcp__") or t in ("Edit", "Write", "Bash") for t in tools), tools


def t_optin_claude_plugins(work, server):
    repo, env = adopt_repo(work, "optin")
    settings = os.path.join(repo, ".claude", "settings.json")
    os.makedirs(os.path.dirname(settings))
    with open(settings, "w") as fh:
        json.dump({"permissions": {"allow": ["Bash(ls:*)"]}}, fh)
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--tools", "seo", "--no-knowledge",
               "--yes"], env=env, cwd=repo)
    assert res.returncode == 0, res.stdout
    data = json.load(open(settings))
    assert data["enabledPlugins"] == {"claude-seo@agricidaniel-claude-seo": True}, data
    assert data["permissions"] == {"allow": ["Bash(ls:*)"]}, "other settings lost"
    assert enabled_ids(repo) == ["seo"], enabled_ids(repo)
    res = run([sys.executable, os.path.join(BIN, "ai-adopt"), "--dir", repo, "--tools", "blog", "--no-knowledge",
               "--yes"], env=env, cwd=repo)
    data = json.load(open(settings))
    assert data["enabledPlugins"] == {"claude-seo@agricidaniel-claude-seo": True,
                                      "claude-blog@agricidaniel-blog": True}, data
    files = run(["git", "-C", repo, "show", "--name-only", "--format=", "HEAD"]).stdout.split()
    assert ".claude/settings.json" in files, files


# ---------------------------------------------------------------- helpers

def make_repo(work, name):
    repo = os.path.join(work, name)
    os.makedirs(repo)
    run(["git", "init", "-q", repo])
    for rel, text in (("pyproject.toml", PYPROJECT), ("uv.lock", UV_LOCK), ("package.json", PACKAGE_JSON),
                      ("package-lock.json", PACKAGE_LOCK), ("go.mod", GO_MOD), ("Cargo.toml", CARGO_TOML),
                      ("Cargo.lock", CARGO_LOCK)):
        with open(os.path.join(repo, rel), "w") as fh:
            fh.write(text)
    return repo


def adopt_repo(work, name):
    repo = os.path.join(work, name)
    os.makedirs(os.path.join(repo, "src"))
    run(["git", "init", "-q", repo])
    files = {"src/app.py": "def main():\n    return 1\n", "uv.lock": UV_LOCK, ".gitignore": "node_modules/\n",
             "tests/test_app.py": "def test_x():\n    assert True\n",
             "pyproject.toml": PYPROJECT + '\n[project.scripts]\napp = "app.main:run"\n'}
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
        with open(os.path.join(repo, rel), "w") as fh:
            fh.write(text)
    fake = os.path.join(work, "fakebin-" + name)
    os.makedirs(fake)
    for tool, text in (("serena", FAKE_SERENA), ("graphify", FAKE_GRAPHIFY), ("claude", FAKE_CLAUDE)):
        with open(os.path.join(fake, tool), "w") as fh:
            fh.write(text)
        os.chmod(os.path.join(fake, tool), 0o755)
    home = os.path.join(work, "home-" + name)
    os.makedirs(home)
    env = {"HOME": home, "PATH": fake + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
           "AI_GITHUB_OWNERS": "someone", "AI_CONTEXT7_URL": DEAD_URL,
           "AI_STATE_DIR": os.path.join(home, "state"), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"}
    run(["git", "-C", repo, "add", "-A"], env=env)
    run(["git", "-C", repo, "commit", "-q", "-m", "init"], env=env)
    return repo, env


def libs(work, repo, *args, url=DEAD_URL, state=None):
    env = {"HOME": os.path.join(work, "home-libs"), "AI_CONTEXT7_URL": url, "CONTEXT7_API_KEY": "test-key",
           "AI_STATE_DIR": state or os.path.join(work, "no-state")}
    return run([sys.executable, os.path.join(BIN, "ai-libs"), "--dir", repo] + list(args), env=env)


def enabled_ids(repo):
    text = open(os.path.join(repo, ".ai", "enabled")).read()
    return [ln.split("#", 1)[0].strip() for ln in text.splitlines() if ln.split("#", 1)[0].strip()]


def table(repo):
    rows = {}
    text = open(os.path.join(repo, "AGENTS.md")).read()
    block = text[text.index("<!-- AI:libraries START"):text.index("<!-- AI:libraries END -->")]
    for line in block.splitlines():
        if line.startswith("| ") and not line.startswith("| lib |"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[cells[0]] = dict(zip(["lib", "version", "context7", "note"], cells))
    return rows


def run(cmd, env=None, cwd=None):
    full = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
    full.update(env or {})
    res = subprocess.run(cmd, env=full, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=120)
    res.stdout = res.stdout.decode("utf-8", "replace")
    return res


class FakeServer:
    """context7 search API (GET /api/v2/libs/search)."""

    C7 = {
        "httpx": [{"id": "/websites/python-httpx-guide", "title": "HTTPX guide"},
                  {"id": "/encode/httpx", "title": "HTTPX", "versions": ["0.27.2", "0.28.1"]}],
        "fastapi": [{"id": "/fastapi/fastapi", "title": "FastAPI", "versions": []}],
        "serde": [{"id": "/someone/serde-json-tutorial", "title": "Serde JSON tutorial"}],
    }

    def __init__(self):
        self.queries, self.auth = [], []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_GET(self):
                from urllib.parse import parse_qs, urlparse
                u = urlparse(self.path)
                lib = parse_qs(u.query).get("libraryName", [""])[0]
                outer.queries.append(lib)
                outer.auth.append(self.headers.get("Authorization"))
                self.reply({"results": outer.C7.get(lib, [])})

            def reply(self, doc, sse=False):
                data = json.dumps(doc).encode()
                if sse:
                    data = b"event: message\ndata: " + data + b"\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if sse else "application/json")
                self.send_header("Mcp-Session-Id", "s1")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
