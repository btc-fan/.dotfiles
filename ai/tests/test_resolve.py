#!/usr/bin/env python3
"""Tests for the newest-stable model (owner decision 2026-11-14): ai/lib/resolve.py against fake registries
(fixtures, no network), HOLD lines, the offline fallback, resolved.json and audit.log records, the npm and
plugin-source install paths, the Claude plugin update path (a fake `claude` on PATH, temp HOME and
CLAUDE_CONFIG_DIR) and context7.sh version discovery. Nothing is written outside the temp dir.

Run: python3 ai/tests/test_resolve.py   (bash ai/tests/run.sh runs it too)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(TESTS)
REPO = os.path.dirname(AI_DIR)
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(AI_DIR, "lib"))
import resolve  # noqa: E402

FAILS = []
NPM = "https://registry.npmjs.org/"
LIBS = ('. "$AI_HOME/ai/lib/common.sh"; for f in base tools claude codex hermes; do . "$AI_HOME/ai/adapters/$f.sh"; '
        'done; load_pins; AI_OS=macos; AI_ARCH=$(uname -m); SUDO_UNDO=""; ')
ENV_KEYS = ("AI_PINS", "AI_RESOLVE_FIXTURES", "AI_RESOLVE_OFFLINE", "AI_RESOLVE_MEMO", "AI_STATE_DIR")


def main():
    work = tempfile.mkdtemp(prefix="ai-resolve-tests-")
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        for test in (t_npm, t_pypi, t_github, t_git_tags, t_git_head, t_hold, t_offline_fallback, t_memo,
                     t_record, t_checksum, t_verify_npm, t_status, t_pins_file, t_bash_npm_global,
                     t_bash_offline_keep, t_bash_context7, t_context7_discovery, t_bash_plugin_clone,
                     t_claude_plugin_replace, t_claude_plugin_update, t_claude_plugin_fallback,
                     t_codex_plugin_refresh):
            for k in ENV_KEYS:
                os.environ.pop(k, None)
            resolve._FIXTURES = None
            try:
                d = os.path.join(work, test.__name__)
                os.makedirs(d)
                test(d)
                print("ok   " + test.__name__)
            except AssertionError as exc:
                FAILS.append("%s: %s" % (test.__name__, exc))
                print("FAIL %s: %s" % (test.__name__, exc))
            except Exception as exc:        # a crash in one test must not stop the others
                FAILS.append("%s: %s: %s" % (test.__name__, type(exc).__name__, exc))
                print("FAIL %s: crashed: %s: %s" % (test.__name__, type(exc).__name__, exc))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(work, ignore_errors=True)
    print("%d resolve tests failed" % len(FAILS))
    return 1 if FAILS else 0


# ---------------------------------------------------------------- helpers

def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)


def read(path):
    with open(path) as fh:
        return fh.read()


def setup(work, pins, http=None, git=None):
    """A pins file, a fixtures file and a state dir for in-process resolve calls."""
    write(os.path.join(work, "pins.env"), pins)
    write(os.path.join(work, "fx.json"), json.dumps({"http": http or {}, "git": git or {}}))
    os.environ["AI_PINS"] = os.path.join(work, "pins.env")
    os.environ["AI_RESOLVE_FIXTURES"] = os.path.join(work, "fx.json")
    os.environ["AI_STATE_DIR"] = os.path.join(work, "state")
    resolve._FIXTURES = None
    return os.path.join(work, "state")


def git(*args, cwd=None):
    res = subprocess.run(["git"] + list(args), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid",
                                  GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid",
                                  GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1"))
    assert res.returncode == 0, res.stdout.decode()
    return res.stdout.decode().strip()


def upstream(path, mname, plugin, versions, tags=True):
    """A local git repo that looks like a plugin marketplace; one commit (and tag) per version. {version: sha}."""
    os.makedirs(path)
    git("init", "-q", "-b", "main", path)
    shas = {}
    for v in versions:
        write(os.path.join(path, ".claude-plugin", "marketplace.json"),
              json.dumps({"name": mname, "plugins": [{"name": plugin, "source": "./"}]}))
        write(os.path.join(path, ".claude-plugin", "plugin.json"), json.dumps({"name": plugin, "version": v}))
        git("add", "-A", cwd=path)
        git("commit", "-q", "-m", "v" + v, cwd=path)
        if tags:
            git("tag", "-a", "v" + v, "-m", "v" + v, cwd=path)
        shas[v] = git("rev-parse", "HEAD", cwd=path)
    return shas


def bash_env(work, pins, extra=None):
    home = os.path.join(work, "home")
    bindir = os.path.join(work, "bin")
    os.makedirs(home, exist_ok=True)
    os.makedirs(bindir, exist_ok=True)
    write(os.path.join(work, "pins.env"), pins)
    env = {"PATH": bindir + ":" + os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LANG": "C.UTF-8",
           "AI_HOME": REPO, "PYTHONDONTWRITEBYTECODE": "1", "AI_PINS": os.path.join(work, "pins.env"),
           "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude"), "CODEX_HOME": os.path.join(home, ".codex"),
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "AI_PROJ_AGENT_PATH": "/nonexistent/proj-agent", "AI_PROJ_AGENT_SOCK": "/nonexistent/proj-agent.sock"}
    env.update(extra or {})
    return env, home, bindir


def bash(script, env):
    res = subprocess.run(["bash", "-c", "set -euo pipefail; " + script], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env)
    return res.returncode, res.stdout.decode()


def stub(path, body):
    write(path, body, 0o755)


def ls_remote_text(repo):
    return subprocess.run(["git", "ls-remote", "--tags", repo], stdout=subprocess.PIPE).stdout.decode()


# ---------------------------------------------------------------- resolver unit tests

def t_npm(work):
    """npm: dist-tags.latest (the /latest document) with its dist.integrity; scoped names are encoded."""
    setup(work, 'X_SOURCE="npm @scope/x stable"\n',
          http={NPM + "@scope%2Fx/latest": {"version": "2.1.0", "dist": {"integrity": "sha512-AAA"}}})
    r = resolve.resolve("x")
    assert (r["version"], r["integrity"], r["status"]) == ("2.1.0", "sha512-AAA", "new"), r
    assert r["source"] == "npm @scope/x", r
    st = json.load(open(os.path.join(work, "state", "resolved.json")))
    assert st["tools"]["x"]["newest"]["version"] == "2.1.0", st


def t_pypi(work):
    """PyPI: newest version that is not a pre-release and not yanked (all files yanked = yanked)."""
    rel = {"1.9.0": [{"yanked": False}], "2.0.0": [{"yanked": True}], "2.1.0rc1": [{"yanked": False}],
           "1.10.0": [{"yanked": False}], "1.10.0.post1": [{"yanked": False}], "3.0.0.dev1": [{"yanked": False}],
           "4.0.0": []}
    setup(work, 'P_SOURCE="pypi p stable"\n', http={"https://pypi.org/pypi/p/json": {"releases": rel}})
    r = resolve.resolve("p")
    assert r["version"] == "1.10.0.post1" and r["status"] == "new", r


def t_github(work):
    """GitHub releases: no draft, no pre-release, plain semver; highest version, not the newest date; the
    commit from ls-remote (peeled tag); the checksum asset URL."""
    rels = [{"tag_name": "v2.0.0-rc.1", "prerelease": True, "draft": False, "assets": []},
            {"tag_name": "v1.9.0", "prerelease": False, "draft": True, "assets": []},
            {"tag_name": "preview-2026", "prerelease": False, "draft": False, "assets": []},
            {"tag_name": "v1.2.10", "prerelease": False, "draft": False,
             "assets": [{"name": "tool_SHA256SUMS", "browser_download_url": "https://x/sums"}]},
            {"tag_name": "v1.2.9", "prerelease": False, "draft": False, "assets": []}]
    tags = "a" * 40 + "\trefs/tags/v1.2.10\n" + "b" * 40 + "\trefs/tags/v1.2.10^{}\n"
    setup(work, 'T_SOURCE="github o/t stable"\n',
          http={"https://api.github.com/repos/o/t/releases?per_page=100": rels},
          git={"https://github.com/o/t --tags": tags})
    r = resolve.resolve("t")
    assert (r["version"], r["ref"], r["sha"], r["checksums"]) == ("1.2.10", "v1.2.10", "b" * 40, "https://x/sums"), r


def t_git_tags(work):
    """git: newest vX.Y.Z tag without a suffix; the peeled commit of an annotated tag."""
    tags = "\n".join(["1" * 40 + "\trefs/tags/v1.0.0", "2" * 40 + "\trefs/tags/v1.10.0",
                      "3" * 40 + "\trefs/tags/v1.10.0^{}", "4" * 40 + "\trefs/tags/v2.0.0-beta.1",
                      "5" * 40 + "\trefs/tags/nightly"])
    setup(work, 'G_SOURCE="git https://example.invalid/g stable"\n', git={"https://example.invalid/g --tags": tags})
    r = resolve.resolve("g")
    assert (r["version"], r["ref"], r["sha"]) == ("1.10.0", "v1.10.0", "3" * 40), r


def t_git_head(work):
    """git without a semver tag: HEAD of the default branch (version = short commit, no ref)."""
    setup(work, 'G_SOURCE="git https://example.invalid/g stable"\n',
          git={"https://example.invalid/g --tags": "1" * 40 + "\trefs/tags/latest\n",
               "https://example.invalid/g HEAD": "9" * 40 + "\tHEAD\n"})
    r = resolve.resolve("g")
    assert (r["version"], r["ref"], r["sha"]) == ("9" * 12, "", "9" * 40), r


def t_hold(work):
    """<PREFIX>_HOLD installs exactly that version: npm, pypi, git tag, git commit."""
    setup(work, 'N_SOURCE="npm n stable"\nN_HOLD=1.0.0\nP_SOURCE="pypi p stable"\nP_HOLD=0.5.0\n'
                'G_SOURCE="git https://example.invalid/g stable"\nG_HOLD=v1.0.0\n'
                'H_SOURCE="git https://example.invalid/h stable"\nH_HOLD=' + "c" * 40 + "\n",
          http={NPM + "n/1.0.0": {"version": "1.0.0", "dist": {"integrity": "sha512-OLD"}},
                "https://pypi.org/pypi/p/json": {"releases": {"0.5.0": [{}], "0.6.0": [{}]}}},
          git={"https://example.invalid/g --tags": "1" * 40 + "\trefs/tags/v1.0.0\n" + "2" * 40 + "\trefs/tags/v2.0.0\n",
               "https://example.invalid/h --tags": ""})
    n, p, g, h = (resolve.resolve(t) for t in ("n", "p", "g", "h"))
    assert (n["version"], n["integrity"], n["status"]) == ("1.0.0", "sha512-OLD", "hold"), n
    assert "N_HOLD=1.0.0" in n["note"], n
    assert (p["version"], p["status"]) == ("0.5.0", "hold"), p
    assert (g["version"], g["sha"]) == ("1.0.0", "1" * 40), g
    assert (h["sha"], h["status"]) == ("c" * 40, "hold"), h


def t_offline_fallback(work):
    """Registry error: the last resolved value (status cached); nothing cached: status none. A cached value is
    not used for a HOLD that asks for another version."""
    pins = 'N_SOURCE="npm n stable"\n'
    setup(work, pins, http={NPM + "n/latest": {"version": "3.0.0", "dist": {"integrity": "sha512-N"}}})
    assert resolve.resolve("n")["status"] == "new"
    setup(work, pins)                                   # same state dir, no answers now
    r = resolve.resolve("n")
    assert (r["version"], r["integrity"], r["status"]) == ("3.0.0", "sha512-N", "cached"), r
    os.environ["AI_STATE_DIR"] = os.path.join(work, "other-state")
    r = resolve.resolve("n")
    assert (r["version"], r["status"]) == ("", "none"), r
    setup(work, pins + "N_HOLD=2.0.0\n")
    r = resolve.resolve("n")
    assert r["status"] == "none", "a cached 3.0.0 must not stand in for a hold at 2.0.0: %r" % r
    os.environ.pop("AI_RESOLVE_FIXTURES")
    os.environ["AI_RESOLVE_OFFLINE"] = "1"
    resolve._FIXTURES = None
    assert resolve.resolve("n")["status"] == "none"


def t_memo(work):
    """AI_RESOLVE_MEMO: one answer per tool per run (the install steps do not ask the registry again)."""
    setup(work, 'N_SOURCE="npm n stable"\n', http={NPM + "n/latest": {"version": "1.0.0", "dist": {"integrity": "i"}}})
    os.environ["AI_RESOLVE_MEMO"] = os.path.join(work, "memo.json")
    assert resolve.resolve("n")["version"] == "1.0.0"
    write(os.environ["AI_RESOLVE_FIXTURES"], json.dumps({"http": {}, "git": {}}))
    resolve._FIXTURES = None
    assert resolve.resolve("n")["version"] == "1.0.0" and resolve.resolve("n")["status"] == "new"


def t_record(work):
    """record: resolved.json "installed" and one audit.log line that the audit gate never reads as a PASS."""
    state = setup(work, 'N_SOURCE="npm n stable"\n')
    resolve.record("n", "1.2.3", integrity="sha512-Z")
    st = json.load(open(os.path.join(state, "resolved.json")))
    assert st["tools"]["n"]["installed"]["version"] == "1.2.3" and st["tools"]["n"]["source"] == "npm n", st
    line = read(os.path.join(state, "audit.log")).strip().split()
    assert line[1:5] == ["install", "n", "1.2.3", "INSTALLED"] and line[5] == "sha512-Z" and line[6] == "npm:n", line
    sys.path.insert(0, os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "hooks"))
    import hooklib
    os.environ["AI_STATE_DIR"] = state
    assert hooklib.audit_status("npm", "n", "1.2.3") is None, "an install line is not an audit result"


def t_checksum(work):
    """checksum: from the release's checksum file, else from the <PREFIX>_CHECKSUMS manifest (herdr form)."""
    rel = {"assets": [{"name": "osv_SHA256SUMS", "browser_download_url": "https://x/sums"}]}
    setup(work, 'O_SOURCE="github o/o stable"\nH_SOURCE="github h/h stable"\nH_CHECKSUMS=https://h/latest.json\n',
          http={"https://api.github.com/repos/o/o/releases/tags/v2.0.0": rel,
                "https://x/sums": "%s  osv_linux_amd64\n%s  osv_darwin_arm64\n" % ("a" * 64, "B" * 64),
                "https://h/latest.json": {"version": "0.9.5", "releases": {"0.9.5": {"sha256": {"macos-aarch64": "c" * 64}}}}})
    assert resolve.checksum("o", "2.0.0", "osv_darwin_arm64") == "b" * 64
    assert resolve.checksum("h", "0.9.5", "herdr-macos-aarch64", "macos-aarch64") == "c" * 64
    try:
        resolve.checksum("o", "2.0.0", "osv_windows")
        raise AssertionError("an asset without a published checksum must fail")
    except resolve.Unavailable:
        pass


def t_verify_npm(work):
    """verify-npm: version from the package, integrity from the lockfile where npm writes one."""
    pre = os.path.join(work, "pre")
    write(os.path.join(pre, "node_modules", "@s", "p", "package.json"), json.dumps({"version": "1.0.0"}))
    ok, msg = resolve.verify_npm(pre, "@s/p", "1.0.0", "sha512-X")
    assert ok and "no lockfile" in msg, msg
    write(os.path.join(pre, "package-lock.json"), json.dumps({"packages": {"node_modules/@s/p": {"integrity": "sha512-X"}}}))
    assert resolve.verify_npm(pre, "@s/p", "1.0.0", "sha512-X")[0]
    assert not resolve.verify_npm(pre, "@s/p", "1.0.0", "sha512-Y")[0]
    assert not resolve.verify_npm(pre, "@s/p", "1.0.1", "sha512-X")[0]


def t_status(work):
    """status (ai-doctor): installed against the cached newest: current, update, unknown."""
    state = setup(work, 'CONTEXT7_MCP_SOURCE="npm c7 stable"\nPLAYWRIGHT_MCP_SOURCE="npm pw stable"\n')
    home = os.path.join(work, "home")
    os.makedirs(os.path.join(home, ".local", "share", "ai", "npm", "context7-mcp-4.6.0"))
    os.makedirs(os.path.join(home, ".local", "share", "ai", "npm", "playwright-mcp-0.0.85"))
    write(os.path.join(state, "resolved.json"), json.dumps({"version": 1, "tools": {
        "context7-mcp": {"newest": {"version": "4.7.0"}}}}))
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        rows = {r["tool"]: r for r in resolve.status()}
    finally:
        os.environ["HOME"] = old
    assert rows["context7-mcp"]["state"] == "update" and rows["context7-mcp"]["installed"] == "4.6.0", rows
    assert rows["playwright-mcp"]["state"] == "unknown", rows


def t_pins_file(work):
    """The real ai/pins.env: every tool has a source, no exact tool version or integrity is left, bash can
    source it, and the agent rule for project packages is unchanged."""
    text = read(os.path.join(AI_DIR, "pins.env"))
    specs = resolve.tools(resolve.read_pins(os.path.join(AI_DIR, "pins.env")))
    for t in ("codex", "omc", "omc-plugin", "omx", "opencode", "herdr", "serena", "context7-mcp", "playwright-mcp",
              "ponytail", "i-have-adhd", "graphify", "claude-seo", "claude-blog", "ui-ux-pro-max",
              "mattpocock-skills", "llm-wiki", "rtk", "guarddog", "skill-scanner", "osv-scanner"):
        assert t in specs and specs[t]["channel"] == "stable" and not specs[t]["hold"], t
    keys = [ln.split("=", 1)[0] for ln in text.splitlines() if "=" in ln and not ln.startswith("#")]
    for k in keys:
        assert not k.endswith(("_INTEGRITY", "_SHA", "_REF", "_TAG", "_COMMIT", "_COOLDOWN_DAYS", "_NOT_BEFORE")) \
            and "_SHA256" not in k, "exact pin left in pins.env: " + k
        assert not k.endswith("_VERSION") or k in ("SKILL_SCANNER_MACOS_LEGACY_VERSION", "PYYAML_VERSION"), k
    res = subprocess.run(["/bin/bash", "-c", 'set -u; . "$1"; echo "$CODEX_SOURCE"', "_",
                          os.path.join(AI_DIR, "pins.env")], stdout=subprocess.PIPE)
    assert res.stdout.decode().strip() == "npm @openai/codex stable", res.stdout
    rule = read(os.path.join(AI_DIR, "agents-md", "40-audit-before-use.md"))
    assert "@latest" in rule, "the project-package rule (no @latest) stays"


# ---------------------------------------------------------------- bash install paths

FAKE_NPM = r'''#!/usr/bin/env python3
import json, os, sys
prefix = os.environ["FAKE_NPM_PREFIX"]
root = os.path.join(prefix, "lib", "node_modules")
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write("npm " + " ".join(a) + "\n")
ints = json.loads(os.environ.get("FAKE_INTEGRITY", "{}"))
if a[:1] == ["view"]:
    print(ints.get(a[1], "")); sys.exit(0)
if a == ["prefix", "-g"]:
    print(prefix); sys.exit(0)
if a == ["root", "-g"]:
    print(root); sys.exit(0)
if a[:1] == ["install"]:
    spec = a[-1]
    name, ver = spec.rsplit("@", 1)
    if "-g" in a:
        base = root
    else:
        base = os.path.join(a[a.index("--prefix") + 1], "node_modules")
    d = os.path.join(base, name)
    os.makedirs(os.path.join(d, "bin"), exist_ok=True)
    json.dump({"name": name, "version": ver}, open(os.path.join(d, "package.json"), "w"))
    tool = name.split("/")[-1]
    exe = os.path.join(d, "bin", tool)
    open(exe, "w").write("#!/bin/sh\necho %s %s\n" % (tool, ver)); os.chmod(exe, 0o755)
    if "-g" in a:
        os.makedirs(os.path.join(prefix, "bin"), exist_ok=True)
        link = os.path.join(prefix, "bin", tool)
        if os.path.lexists(link): os.remove(link)
        os.symlink(exe, link)
    else:
        bindir = os.path.join(base, ".bin"); os.makedirs(bindir, exist_ok=True)
        link = os.path.join(bindir, tool)
        if os.path.lexists(link): os.remove(link)
        os.symlink(exe, link)
        lock = os.path.join(os.path.dirname(base), "package-lock.json")
        json.dump({"packages": {"node_modules/" + name: {"version": ver, "integrity": ints.get(spec, "")}}}, open(lock, "w"))
    sys.exit(0)
sys.exit(0)
'''


def npm_env(work, pins, latest, integ, extra=None):
    env, home, bindir = bash_env(work, pins, extra)
    prefix = os.path.join(work, "npmprefix")
    os.makedirs(os.path.join(prefix, "bin"), exist_ok=True)
    stub(os.path.join(bindir, "npm"), FAKE_NPM)
    fx = os.path.join(work, "fx.json")
    write(fx, json.dumps({"http": latest, "git": {}}))
    env.update({"FAKE_NPM_PREFIX": prefix, "FAKE_LOG": os.path.join(work, "log"), "FAKE_INTEGRITY": json.dumps(integ),
                "AI_RESOLVE_FIXTURES": fx, "PATH": os.path.join(prefix, "bin") + ":" + env["PATH"]})
    return env, home


def t_bash_npm_global(work):
    """npm_global: installs the newest stable after the audit, records it; a second run changes nothing; a HOLD
    moves it to exactly that version; audit findings keep the old version."""
    pins = 'TOOLX_SOURCE="npm toolx stable"\n'
    latest = {NPM + "toolx/latest": {"version": "2.0.0", "dist": {"integrity": "sha512-two"}},
              NPM + "toolx/1.5.0": {"version": "1.5.0", "dist": {"integrity": "sha512-one"}}}
    env, home = npm_env(work, pins, latest, {"toolx@2.0.0": "sha512-two", "toolx@1.5.0": "sha512-one"})
    audit = os.path.join(work, "audit.calls")
    run = LIBS + 'audit_ok() { echo "$*" >> %s; return 0; }; npm_global toolx toolx toolx toolx && echo rc=0 || echo rc=$?' % audit
    code, out = bash(run, env)
    assert code == 0 and "rc=0" in out and "toolx 2.0.0 (newest stable" in out, out
    assert "npm toolx 2.0.0" in read(audit), "audit before the install"
    st = json.load(open(os.path.join(home, ".local", "state", "ai", "resolved.json")))
    assert st["tools"]["toolx"]["installed"] == dict(st["tools"]["toolx"]["installed"], version="2.0.0",
                                                     integrity="sha512-two"), st
    assert " install toolx 2.0.0 INSTALLED sha512-two npm:toolx" in read(os.path.join(home, ".local", "state", "ai", "audit.log"))
    keys = [e["key"] for e in json.load(open(os.path.join(home, ".local", "state", "ai", "managed-keys.json")))["entries"]]
    assert "cmd:npm:toolx" in keys, keys
    code, out = bash(run, env)
    assert "rc=1" in out and "toolx 2.0.0 present" in out, out
    write(env["AI_PINS"], pins + "TOOLX_HOLD=1.5.0\n")
    code, out = bash(run, env)
    assert "held at 1.5.0" in out and "toolx 2.0.0 -> 1.5.0" in out, out
    write(env["AI_PINS"], pins)                    # hold removed: 2.0.0 again, but the audit finds problems
    code, out = bash(LIBS + 'audit_ok() { return 1; }; npm_global toolx toolx toolx toolx && echo rc=0 || echo rc=$?', env)
    assert "rc=1" in out and "toolx 1.5.0 kept" in out, out
    res = subprocess.run([os.path.join(work, "npmprefix", "bin", "toolx")], stdout=subprocess.PIPE)
    assert res.stdout.decode().strip() == "toolx 1.5.0", res.stdout


def t_bash_offline_keep(work):
    """Offline: an installed tool stays (said so) and the run goes on; with nothing resolved before, the tool is
    skipped with a warning, never a failed install. A copy not from npm is never shadowed."""
    pins = 'TOOLX_SOURCE="npm toolx stable"\n'
    env, home = npm_env(work, pins, {NPM + "toolx/latest": {"version": "2.0.0", "dist": {"integrity": "i2"}}},
                        {"toolx@2.0.0": "i2"})
    run = LIBS + 'audit_ok() { return 0; }; npm_global toolx toolx toolx toolx || true; echo end'
    code, out = bash(run, env)
    assert code == 0 and "toolx 2.0.0 (newest" in out, out
    write(env["AI_RESOLVE_FIXTURES"], json.dumps({"http": {}, "git": {}}))
    code, out = bash(run, env)
    assert code == 0 and "using the last resolved 2.0.0" in out and "toolx 2.0.0 present" in out, out
    code, out = bash(run, dict(env, HOME=os.path.join(work, "home2")))
    assert code == 0 and "newest stable unknown" in out and "end" in out, out
    os.makedirs(os.path.join(work, "home2"), exist_ok=True)
    stub(os.path.join(work, "bin", "toolz"), "#!/bin/sh\necho toolz 0.1.0\n")
    write(env["AI_PINS"], pins + 'TOOLZ_SOURCE="npm toolz stable"\n')
    write(env["AI_RESOLVE_FIXTURES"], json.dumps({"http": {NPM + "toolz/latest": {"version": "0.2.0", "dist": {"integrity": "z"}}}}))
    code, out = bash(LIBS + 'audit_ok() { return 0; }; npm_global toolz toolz toolz toolz || true', env)
    assert "is not from npm" in out and "toolz@" not in read(env["FAKE_LOG"]), out


def t_bash_context7(work):
    """tools_context7: the newest stable goes into its own version folder, the old folder goes, context7.sh
    starts the new one; offline the installed one stays."""
    pins = 'CONTEXT7_MCP_SOURCE="npm @upstash/context7-mcp stable"\n'
    latest = {NPM + "@upstash%2Fcontext7-mcp/latest": {"version": "4.7.0", "dist": {"integrity": "sha512-c7"}}}
    env, home = npm_env(work, pins, latest, {"@upstash/context7-mcp@4.7.0": "sha512-c7"})
    npmdir = os.path.join(home, ".local", "share", "ai", "npm")
    old = os.path.join(npmdir, "context7-mcp-4.6.0", "node_modules", ".bin", "context7-mcp")
    stub(old, "#!/bin/sh\necho c7-old\n")
    code, out = bash(LIBS + 'audit_ok() { return 0; }; tools_context7', env)
    assert code == 0 and "context7-mcp 4.6.0 -> 4.7.0" in out, out
    assert sorted(os.listdir(npmdir)) == ["context7-mcp-4.7.0"], os.listdir(npmdir)
    res = subprocess.run(["sh", os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "mcp", "context7.sh")],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(env, CONTEXT7_API_KEY="k"))
    assert res.stdout.decode().strip() == "context7-mcp 4.7.0", res.stdout
    write(env["AI_RESOLVE_FIXTURES"], json.dumps({"http": {}}))
    code, out = bash(LIBS + 'audit_ok() { return 0; }; tools_context7', env)
    assert code == 0 and "context7-mcp 4.7.0 present" in out, out


def t_context7_discovery(work):
    """context7.sh has no version line: it starts the highest installed version (numeric order), and says
    what to do when none is installed."""
    script = os.path.join(AI_DIR, "marketplace", "plugins", "ai-core", "mcp", "context7.sh")
    text = read(script)
    assert "\nv=4" not in text and "CONTEXT7_MCP_VERSION" not in text, "no fixed version in context7.sh"
    base = os.path.join(work, "npm")
    for v in ("4.6.0", "4.10.0", "4.9.1"):
        stub(os.path.join(base, "context7-mcp-" + v, "node_modules", ".bin", "context7-mcp"), "#!/bin/sh\necho c7-%s\n" % v)
    os.makedirs(os.path.join(base, "context7-mcp-9.9.9"))            # a folder without the binary is not "installed"
    os.makedirs(os.path.join(base, "context7-mcp-latest"))
    env = {"PATH": os.environ["PATH"], "HOME": work, "AI_NPM_DIR": base, "CONTEXT7_API_KEY": "k"}
    res = subprocess.run(["sh", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    assert res.stdout.decode().strip() == "c7-4.10.0", res.stdout
    res = subprocess.run(["sh", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(env, AI_NPM_DIR=os.path.join(work, "none")))
    assert res.returncode == 1 and "Run install.sh" in res.stdout.decode(), res.stdout


def t_bash_plugin_clone(work):
    """plugin_clone: a source clone at an older tag moves to the newest tag (audited first); audit findings keep
    the old clone; a folder that is not our clone is left alone."""
    up = os.path.join(work, "up", "plug")
    shas = upstream(up, "plug", "plug", ["1.0.0", "1.1.0"])
    env, home, _ = bash_env(work, 'PLUG_SOURCE="git %s stable"\n' % up)
    dest = os.path.join(home, ".local", "share", "ai", "plugins", "plug")
    git("clone", "-q", up, dest)
    git("-c", "advice.detachedHead=false", "checkout", "-q", shas["1.0.0"], cwd=dest)
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; audit_ok() { return 1; }; plugin_clone plug plug || true', env)
    assert git("rev-parse", "HEAD", cwd=dest) == shas["1.0.0"] and "kept" in out, out
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; audit_ok() { return 0; }; plugin_clone plug plug', env)
    assert code == 0 and git("rev-parse", "HEAD", cwd=dest) == shas["1.1.0"], out
    assert "-> v1.1.0" in out, out
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; plugin_clone plug plug', env)
    assert "is at v1.1.0" in out, out
    shutil.rmtree(dest)
    write(os.path.join(dest, "mine.txt"), "x")
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; audit_ok() { return 0; }; plugin_clone plug plug || true', env)
    assert "not a clone made by this setup" in out and os.path.exists(os.path.join(dest, "mine.txt")), out


FAKE_CLAUDE = r'''#!/usr/bin/env python3
"""Fake `claude plugin ...`: the behaviour seen in a temp CLAUDE_CONFIG_DIR on 2026-11-14 (remove uninstalls the
marketplace's plugins; add Owner/repo#ref stores {source: github, repo, ref}; update + plugin update move)."""
import json, os, shutil, subprocess, sys
pd = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "plugins")
km, ip = os.path.join(pd, "known_marketplaces.json"), os.path.join(pd, "installed_plugins.json")
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write("claude " + " ".join(a) + "\n")
def load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d
def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w"))
k, i = load(km, {}), load(ip, {"version": 2, "plugins": {}})
def git(*args):
    return subprocess.run(["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode().strip()
def root(name):
    src = k[name]["source"]
    return src["path"] if src["source"] == "directory" else os.path.join(pd, "marketplaces", name)
if a[:3] == ["plugin", "marketplace", "add"]:
    src = a[3]
    if src.startswith("/"):
        name = json.load(open(os.path.join(src, ".claude-plugin", "marketplace.json")))["name"]
        k[name] = {"source": {"source": "directory", "path": src}}
    else:
        repo, _, ref = src.partition("#")
        tmp = os.path.join(pd, "tmp-clone"); shutil.rmtree(tmp, True)
        git("clone", "-q", os.path.join(os.environ["FAKE_REPOS"], repo), tmp)
        if ref:
            git("-C", tmp, "-c", "advice.detachedHead=false", "checkout", "-q", ref)
        name = json.load(open(os.path.join(tmp, ".claude-plugin", "marketplace.json")))["name"]
        dest = os.path.join(pd, "marketplaces", name); shutil.rmtree(dest, True)
        os.makedirs(os.path.dirname(dest), exist_ok=True); os.rename(tmp, dest)
        k[name] = {"source": dict({"source": "github", "repo": repo}, **({"ref": ref} if ref else {}))}
elif a[:3] == ["plugin", "marketplace", "remove"]:
    name = a[3]
    k.pop(name, None)
    for p in [p for p in i["plugins"] if p.endswith("@" + name)]:
        del i["plugins"][p]
    shutil.rmtree(os.path.join(pd, "marketplaces", name), True)
elif a[:3] == ["plugin", "marketplace", "update"]:
    src = k[a[3]]["source"]
    if src["source"] == "github" and not src.get("ref"):
        d = root(a[3]); git("-C", d, "pull", "-q", "--ff-only")
elif a[:3] == ["plugin", "marketplace", "list"]:
    print("\n".join(k))
elif a[:2] == ["plugin", "install"] or (a[:2] == ["plugin", "update"] and not os.environ.get("FAKE_UPDATE_BROKEN")):
    p = a[2]; m = p.split("@")[1]
    if m not in k:
        sys.exit(1)
    if a[1] == "update" and p not in i["plugins"]:
        sys.exit(1)
    r = root(m)
    row = {"scope": "user", "version": json.load(open(os.path.join(r, ".claude-plugin", "plugin.json")))["version"]}
    if k[m]["source"]["source"] != "directory":
        row["gitCommitSha"] = git("-C", r, "rev-parse", "HEAD")
    i["plugins"][p] = [row]
elif a[:2] == ["plugin", "uninstall"]:
    i["plugins"].pop(a[2], None)
elif a[:2] == ["plugin", "list"]:
    print("\n".join(i["plugins"]))
save(km, k); save(ip, i)
'''


def claude_env(work, pins):
    env, home, bindir = bash_env(work, pins)
    stub(os.path.join(bindir, "claude"), FAKE_CLAUDE)
    env.update({"FAKE_LOG": os.path.join(work, "log"), "FAKE_REPOS": os.path.join(work, "up")})
    return env, home


def claude_files(home):
    pd = os.path.join(home, ".claude", "plugins")
    return (json.load(open(os.path.join(pd, "known_marketplaces.json"))),
            json.load(open(os.path.join(pd, "installed_plugins.json")))["plugins"])


def mutations(work):
    if not os.path.exists(os.path.join(work, "log")):
        return []
    return [ln for ln in read(os.path.join(work, "log")).splitlines()
            if not ln.endswith(" list") and " list" not in ln]


def t_claude_plugin_replace(work):
    """A marketplace someone else added at an older tag is replaced by ours at the newest tag (remove + add,
    plugin installed again, at the tag's commit), with a restore record for uninstall; a second run changes nothing."""
    shas = upstream(os.path.join(work, "up", "Owner", "plug"), "tp", "plug", ["1.0.0", "1.1.0"])
    env, home = claude_env(work, 'TESTPLUG_SOURCE="git %s stable"\n' % os.path.join(work, "up", "Owner", "plug"))
    code, out = bash('claude plugin marketplace add "Owner/plug#v1.0.0" && claude plugin install plug@tp --scope user', env)
    assert code == 0, out
    os.remove(os.path.join(work, "log"))
    script = LIBS + 'audit_ok() { echo "AUDIT $*"; return 0; }; claude_git_plugin testplug tp Owner/plug plug@tp'
    code, out = bash(script, env)
    assert code == 0, out
    known, plugins = claude_files(home)
    assert known["tp"]["source"] == {"source": "github", "repo": "Owner/plug", "ref": "v1.1.0"}, known
    assert plugins["plug@tp"][0]["gitCommitSha"] == shas["1.1.0"], plugins
    assert "AUDIT dir" in out and "v1.1.0 testplug" in out, "the new source is audited before the move: " + out
    log = mutations(work)
    assert log[:2] == ["claude plugin marketplace remove tp", "claude plugin marketplace add Owner/plug#v1.1.0"], log
    entries = json.load(open(os.path.join(home, ".local", "state", "ai", "managed-keys.json")))["entries"]
    keys = [e["key"] for e in entries]
    assert keys.index("cmd:claude-marketplace-restore:tp") < keys.index("cmd:claude-marketplace:tp") \
        < keys.index("cmd:claude-plugin:plug@tp"), keys
    restore = [e for e in entries if e["key"] == "cmd:claude-marketplace-restore:tp"][0]["undo"]
    assert "Owner/plug#v1.0.0" in restore and "plug@tp" in restore, restore
    st = json.load(open(os.path.join(home, ".local", "state", "ai", "resolved.json")))
    assert st["tools"]["testplug"]["installed"]["sha"] == shas["1.1.0"], st
    os.remove(os.path.join(work, "log"))
    code, out = bash(script, env)
    assert code == 0 and mutations(work) == [] and "newest stable" in out, (mutations(work), out)


def t_claude_plugin_update(work):
    """Same marketplace source (a repo without tags follows its default branch): marketplace update + plugin
    update move the plugin to the new commit; no remove."""
    up = os.path.join(work, "up", "Owner", "plug2")
    shas = upstream(up, "tp2", "plug2", ["1.0.0"], tags=False)
    env, home = claude_env(work, 'TESTPLUG2_SOURCE="git %s stable"\n' % up)
    code, out = bash('claude plugin marketplace add Owner/plug2 && claude plugin install plug2@tp2 --scope user', env)
    assert code == 0, out
    write(os.path.join(up, ".claude-plugin", "plugin.json"), json.dumps({"name": "plug2", "version": "1.0.1"}))
    git("commit", "-q", "-am", "next", cwd=up)
    new = git("rev-parse", "HEAD", cwd=up)
    os.remove(os.path.join(work, "log"))
    code, out = bash(LIBS + 'audit_ok() { return 0; }; claude_git_plugin testplug2 tp2 Owner/plug2 plug2@tp2', env)
    assert code == 0, out
    _known, plugins = claude_files(home)
    assert plugins["plug2@tp2"][0]["gitCommitSha"] == new != shas["1.0.0"], plugins
    log = mutations(work)
    assert "claude plugin update plug2@tp2" in log and not any("remove" in ln or "uninstall" in ln for ln in log), log


def t_claude_plugin_fallback(work):
    """`claude plugin update` that does not move the plugin: uninstall + install, then the version is checked.
    A local (directory) marketplace follows its source folder the same way."""
    src = os.path.join(work, "up", "Owner", "plug3")
    upstream(src, "tp3", "plug3", ["1.0.0"])
    env, home = claude_env(work, "")
    code, out = bash('claude plugin marketplace add %s && claude plugin install plug3@tp3 --scope user' % src, env)
    assert code == 0, out
    write(os.path.join(src, ".claude-plugin", "plugin.json"), json.dumps({"name": "plug3", "version": "2.0.0"}))
    git("commit", "-q", "-am", "v2", cwd=src)
    head = git("rev-parse", "HEAD", cwd=src)
    os.remove(os.path.join(work, "log"))
    code, out = bash(LIBS + 'claude_plugin tp3 %s plug3@tp3 %s "$(plugin_json_version %s)"' % (src, head, src),
                     dict(env, FAKE_UPDATE_BROKEN="1"))
    assert code == 0, out
    _known, plugins = claude_files(home)
    assert plugins["plug3@tp3"][0]["version"] == "2.0.0", plugins
    log = mutations(work)
    assert log[-2:] == ["claude plugin uninstall plug3@tp3", "claude plugin install plug3@tp3 --scope user"], log
    assert read(os.path.join(home, ".local", "state", "ai", "claude-plugin.plug3.src")).strip() == head


def t_codex_plugin_refresh(work):
    """Codex: an installed plugin whose source clone moved is refreshed in place (codex plugin add again)."""
    env, home, bindir = bash_env(work, "")
    log = os.path.join(work, "log")
    stub(os.path.join(bindir, "codex"), '#!/bin/sh\necho "codex $*" >> %s\n'
                                        '[ "$1 $2" = "plugin list" ] && echo "ponytail@ponytail installed"\nexit 0\n' % log)
    code, out = bash(LIBS + 'codex_marketplace_plugin /x ponytail ponytail@ponytail %s' % ("a" * 40), env)
    assert code == 0 and "codex plugin add ponytail@ponytail" in read(log), out
    os.remove(log)
    code, out = bash(LIBS + 'codex_marketplace_plugin /x ponytail ponytail@ponytail %s' % ("a" * 40), env)
    assert "plugin add" not in read(log) and "installed at aaaaaaa" in out, out
    code, out = bash(LIBS + 'codex_marketplace_plugin /x ponytail ponytail@ponytail %s' % ("b" * 40), env)
    assert "codex plugin add ponytail@ponytail" in read(log) and "refreshed" in out, out


if __name__ == "__main__":
    sys.exit(main())
