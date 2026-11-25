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
ENV_KEYS = ("AI_PINS", "AI_RESOLVE_FIXTURES", "AI_RESOLVE_OFFLINE", "AI_RESOLVE_MEMO", "AI_STATE_DIR",
            "AI_SYSTEM_STATE_DIR")


def main():
    work = tempfile.mkdtemp(prefix="ai-resolve-tests-")
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        for test in (t_npm, t_pypi, t_pypi_post, t_checksum_not_signature, t_list_survives_errors, t_github, t_git_tags, t_git_head, t_hold, t_offline_fallback, t_memo,
                     t_record, t_checksum, t_verify_npm, t_status, t_pins_file, t_bash_npm_global,
                     t_bash_offline_keep, t_bash_context7, t_context7_discovery, t_bash_plugin_clone,
                     t_claude_plugin_replace, t_claude_plugin_update, t_claude_plugin_fallback,
                     t_claude_dir_same_version, t_claude_fresh_install_checked, t_claude_own_replace_rollback,
                     t_claude_plugin_rejected_newest,
                     t_codex_plugin_refresh, t_bash_mattpocock_optin, t_bash_pstack, t_audit_accept_by_commit, t_uv_tool_normalized, t_uv_tool_broken_reinstalls, t_scanners,
                     t_osv_scanner, t_gitleaks_pin, t_herdr, t_src_swap_and_dry_sha, t_playwright_keep_only,
                     t_playwright_profile_audit):
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
    # No PATH entry under the real HOME: its ~/.local/bin (guarddog, osv-scanner, uv tools) would shadow the fakes.
    real_home = os.path.realpath(os.path.expanduser("~")) + os.sep
    path = [p for p in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep)
            if p and not os.path.realpath(p).startswith(real_home)]
    env = {"PATH": os.pathsep.join([bindir] + path), "HOME": home, "LANG": "C.UTF-8",
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


def t_pypi_post(work):
    """A post release of an older version never wins over a newer release (1.0.post5 < 1.0.1)."""
    setup(work, 'P_SOURCE="pypi p stable"\n', http={"https://pypi.org/pypi/p/json": {"releases": {
        "1.0.post5": [{}], "1.0.1": [{}], "1.0": [{}]}}})
    assert resolve.resolve("p")["version"] == "1.0.1"
    assert resolve.pypi_key("1.0") == resolve.pypi_key("1.0.0") and resolve.same_version("1.0", "1.0.0")
    assert not resolve.same_version("1.1", "1.10")


def t_checksum_not_signature(work):
    """The checksum file is never its signature (.sig, .asc, .pem next to it)."""
    rels = [{"tag_name": "v1.0.0", "prerelease": False, "draft": False, "assets": [
        {"name": "t_SHA256SUMS.sig", "browser_download_url": "https://x/sig"},
        {"name": "checksums.txt.pem", "browser_download_url": "https://x/pem"},
        {"name": "t_SHA256SUMS", "browser_download_url": "https://x/sums"}]}]
    setup(work, 'T_SOURCE="github o/t stable"\n',
          http={"https://api.github.com/repos/o/t/releases?per_page=100": rels}, git={"https://github.com/o/t --tags": ""})
    assert resolve.resolve("t")["checksums"] == "https://x/sums"


def t_list_survives_errors(work):
    """`list`: a resolver that crashes for one tool gives that tool status none; the others still resolve."""
    setup(work, 'A_SOURCE="npm a stable"\nB_SOURCE="pypi b stable"\n',
          http={NPM + "a/latest": {"version": "1.0.0", "dist": {"integrity": "i"}}})
    old = resolve.RESOLVERS["pypi"]
    resolve.RESOLVERS["pypi"] = lambda name, hold="": 1 / 0
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert resolve.main(["list", "--no-write"]) == 0
    finally:
        resolve.RESOLVERS["pypi"] = old
    lines = {ln.split()[0]: ln for ln in buf.getvalue().splitlines()}
    assert "1.0.0" in lines["a"] and " none " in lines["b"] and "ZeroDivisionError" in lines["b"], lines


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
    os.environ["AI_SYSTEM_STATE_DIR"] = os.path.join(work, "system-state")   # never /var/lib/ai in a test
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
              "mattpocock-skills", "pstack", "llm-wiki", "rtk", "guarddog", "skill-scanner", "osv-scanner"):
        assert t in specs and specs[t]["channel"] == "stable" and not specs[t]["hold"], t
    keys = [ln.split("=", 1)[0] for ln in text.splitlines() if "=" in ln and not ln.startswith("#")]
    for k in keys:
        if k.startswith("GITLEAKS_SHA256_") and "GITLEAKS_HOLD" in keys:
            continue        # review S6: the archive sha256 of the held gitleaks release, checked by tools_gitleaks
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


def t_bash_mattpocock_optin(work):
    """mattpocock_src: the six global picks (ask-matt since 2026-11-15) plus the opt-in picks (found under any category except misc/ and
    in-progress/; a missing one is skipped with a warning, the five still install); the pick list is in the marker;
    mattpocock_link links only the five global names."""
    up = os.path.join(work, "up", "mp")
    os.makedirs(up)
    git("init", "-q", "-b", "main", up)
    for rel in ("productivity/grilling", "productivity/grill-me", "productivity/wait-what",
                "productivity/writing-for-agents", "engineering/retro", "engineering/grill-with-docs",
                "engineering/domain-modeling", "engineering/to-tickets", "engineering/tdd", "engineering/codebase-design",
                "engineering/code-review", "engineering/pr", "engineering/diagnosing-bugs", "misc/to-spec",
                "engineering/implement", "engineering/ask-matt"):
        write(os.path.join(up, "skills", rel, "SKILL.md"), "---\nname: %s\n---\nbody\n" % rel.split("/")[1])
    git("add", "-A", cwd=up)
    git("commit", "-q", "-m", "v1", cwd=up)
    git("tag", "-a", "v1.0.0", "-m", "v1", cwd=up)
    env, home, _ = bash_env(work, 'MATTPOCOCK_SKILLS_SOURCE="git %s stable"\n' % up)
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; audit_ok() { return 0; }; mattpocock_src', env)
    assert code == 0, out
    dest = os.path.join(home, ".local", "share", "ai", "plugins", "mattpocock-skills")
    have = sorted(n for n in os.listdir(dest) if not n.startswith("."))
    assert have == sorted(["grilling", "grill-me", "wait-what", "writing-for-agents", "retro", "grill-with-docs",
                           "domain-modeling", "to-tickets", "tdd", "codebase-design", "code-review", "pr",
                           "diagnosing-bugs", "implement", "ask-matt"]), have
    assert "opt-in skill to-spec not found" in out and "improve-codebase-architecture not found" in out, out
    assert "wayfinder not found" in out, "a missing opt-in name is reported: " + out
    assert "grill-with-docs" in read(os.path.join(dest, ".picks")), "pick list missing from the marker"
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; mattpocock_src', env)
    assert "(newest stable)" in out, "same commit and picks: nothing to do: " + out
    write(os.path.join(dest, ".picks"), "old list\n")
    code, out = bash(LIBS + 'AI_OS=macos; AI_SKIP_PACKAGES=0; audit_ok() { return 0; }; mattpocock_src', env)
    assert "(newest stable)" not in out and "audited" in out, "a changed pick list copies again: " + out
    target = os.path.join(home, "skills")
    code, out = bash(LIBS + 'AI_OS=macos; mattpocock_link "%s"' % target, env)
    assert sorted(os.listdir(target)) == sorted(["grilling", "grill-me", "wait-what", "writing-for-agents", "retro",
                                                 "ask-matt"]), \
        "only the six global picks are linked globally: %s" % os.listdir(target)


def t_bash_pstack(work):
    """pstack_check (owner 2026-11-25: repo copy only): a new upstream commit gives a warning and downloads
    nothing; the vendored commit gives an info line; an old automatic download is removed. link_skills points
    the skill links at ai/skills, also when they pointed at the old download, and a second run changes nothing."""
    up = os.path.join(work, "up", "plugins")
    os.makedirs(up)
    git("init", "-q", "-b", "main", up)
    write(os.path.join(up, "pstack", "LICENSE"), "MIT License\nCopyright (c) 2026 Lauren Tan\n")
    git("add", "-A", cwd=up)
    git("commit", "-q", "-m", "one", cwd=up)
    sha = git("rev-parse", "HEAD", cwd=up)
    env, home, _ = bash_env(work, 'PSTACK_SOURCE="git %s stable"\n' % up)
    old = os.path.join(home, ".local", "share", "ai", "plugins", "pstack-verification")
    write(os.path.join(old, ".commit"), "an-old-download\n")
    # Linux root layer: the folder is root-owned, so the removal goes through run_root.
    code, out = bash(LIBS + 'root_layer() { return 0; }; plugin_src_dir() { echo "%s"; }; run_root() { echo "ROOT $*"; }; '
                            'pstack_check' % old, env)
    assert "ROOT rm -rf %s" % old in out, out
    code, out = bash(LIBS + 'AI_SKIP_PACKAGES=0; pstack_check', env)
    assert code == 0 and "moved upstream" in out and "repo copy stays in use" in out, out
    assert not os.path.exists(old), "the old automatic download is removed: " + out
    code, out = bash(LIBS + 'AI_SKIP_PACKAGES=0; pstack_vendor_commit() { echo %s; }; pstack_check' % sha, env)
    assert "the repo copy (ai/skills" in out and "moved upstream" not in out, out
    target = os.path.join(home, "skills")
    os.makedirs(target)
    os.symlink(os.path.join(old, "create-verification-skill"), os.path.join(target, "create-verification-skill"))
    for run in (1, 2):
        code, out = bash(LIBS + 'link_skills "%s"' % target, env)
        for n in ("create-verification-skill", "maintain-verification-skill"):
            assert os.readlink(os.path.join(target, n)) == os.path.join(REPO, "ai", "skills", n), out
    changed = [l for l in out.splitlines() if "verification-skill" in l and l.strip().startswith("link")]
    assert not changed, "run 2 changes no link: " + out


def t_audit_accept_by_commit(work):
    """dir acceptances are keyed by the full commit: a tag (which can move) or a short commit never matches."""
    env, _home, bindir = bash_env(work, "")
    rtk = "e288a18c04452fd26192f59132e5324a8bb6924d"
    code, out = bash(LIBS + 'audit_accepted dir rtk %s; echo "|"; audit_accepted dir rtk v1.2.0; echo "|"; '
                     'audit_accepted dir rtk %s; echo "|"' % (rtk, rtk[:12]), env)
    parts = out.split("|")
    assert "cargo update" in parts[0] and parts[1].strip() == "" and parts[2].strip() == "", out
    for line in read(os.path.join(AI_DIR, "audit-accepted.txt")).splitlines():
        if line.startswith("dir "):
            assert len(line.split()[2]) == 40, "dir line not keyed by a full commit: " + line
    stub(os.path.join(bindir, "agent-audit"), "#!/bin/sh\nexit 1\n")    # findings
    code, out = bash(LIBS + 'AI_STATE_DIR=$HOME/st; audit_ok dir /tmp v1.2.0 rtk || echo refused; '
                     'audit_ok dir /tmp %s rtk && echo accepted' % rtk, env)
    assert "refused" in out and "accepted" in out, out


FAKE_UV = r'''#!/usr/bin/env python3
import os, re, sys
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write("uv " + " ".join(a) + "\n")
if a[:2] == ["tool", "dir"]:
    print(os.path.join(os.environ["HOME"], "uvtools")); sys.exit(0)
if a[:2] == ["tool", "install"]:
    spec = [x for x in a if "==" in x][0]
    name, ver = spec.split("==")
    name = re.sub(r"\[.*\]$", "", name)       # an extra ("pkg[mcp]") names the same package
    binname = os.environ.get("FAKE_UV_BIN_" + re.sub(r"[^A-Za-z0-9]", "_", name), name)
    path = os.path.join(os.environ["FAKE_BIN"], binname)
    open(path, "w").write("#!/bin/sh\necho %s %s\n" % (binname, os.environ.get("FAKE_UV_PRINTS", ver)))
    os.chmod(path, 0o755)
sys.exit(0)
'''


def uv_env(work, pins, pypi):
    env, home, bindir = bash_env(work, pins)
    stub(os.path.join(bindir, "uv"), FAKE_UV)
    fx = os.path.join(work, "fx.json")
    write(fx, json.dumps({"http": {"https://pypi.org/pypi/%s/json" % n: {"releases": {v: [{}] for v in vs}}
                                   for n, vs in pypi.items()}}))
    env.update({"FAKE_LOG": os.path.join(work, "log"), "FAKE_BIN": bindir, "AI_RESOLVE_FIXTURES": fx,
                "FAKE_UV_BIN_cisco_ai_skill_scanner": "skill-scanner", "FAKE_UV_BIN_serena_agent": "serena"})
    return env, home, bindir


def t_uv_tool_normalized(work):
    """uv_tool: a tool that prints 2.1 for 2.1.0 is current (no reinstall on every run)."""
    env, home, bindir = uv_env(work, 'TOOLQ_SOURCE="pypi toolq-agent stable"\n', {"toolq-agent": ["2.1.0"]})
    env["FAKE_UV_BIN_toolq_agent"] = "toolq"
    run = LIBS + 'audit_ok() { return 0; }; uv_tool toolq toolq-agent toolq 3.13'
    code, out = bash(run, dict(env, FAKE_UV_PRINTS="2.1"))
    assert code == 0 and "toolq 2.1.0 (newest stable" in out, out
    os.remove(os.path.join(work, "log"))
    code, out = bash(run, env)
    assert "toolq 2.1 present" in out and "tool install" not in read(os.path.join(work, "log")), out


def t_uv_tool_broken_reinstalls(work):
    """uv_tool: a present newest version that fails its smoke test is reinstalled with the extra (graphify 0.9.118
    printed its version, but every query crashed until the mcp extra brought anyio)."""
    env, home, bindir = uv_env(work, 'TOOLQ_SOURCE="pypi toolq-agent stable"\n', {"toolq-agent": ["2.1.0"]})
    env.update({"FAKE_UV_BIN_toolq_agent": "toolq", "FAKE_UV_PRINTS": "2.1.0"})
    run = LIBS + 'audit_ok() { return 0; }; uv_tool toolq toolq-agent toolq "" "[mcp]"'
    code, out = bash(run, env)
    os.remove(os.path.join(work, "log"))
    code, out = bash(run.replace("uv_tool toolq", "tool_works() { return 1; }; uv_tool toolq"), env)
    assert "present but fails its smoke test" in out, out
    assert "toolq-agent[mcp]==2.1.0" in read(os.path.join(work, "log")), read(os.path.join(work, "log"))


def t_scanners(work):
    """guarddog / skill-scanner: the first bootstrap (no guarddog) installs guarddog unaudited with a warning, and
    audits skill-scanner with it; a later new version is audited first, and findings keep the old one."""
    pins = 'GUARDDOG_SOURCE="pypi guarddog stable"\nSKILL_SCANNER_SOURCE="pypi cisco-ai-skill-scanner stable"\n'
    env, home, bindir = uv_env(work, pins, {"guarddog": ["3.2.0"], "cisco-ai-skill-scanner": ["2.3.2"]})
    audits = os.path.join(work, "audits")
    run = LIBS + 'SCANNER_PYTHON=3.12; AI_SKIP_PACKAGES=0; audit_ok() { echo "$*" >> %s; return ${AUDIT_RC:-0}; }; tools_scanners' % audits
    code, out = bash(run, env)
    assert code == 0 and "bootstrap: guarddog 3.2.0 installed WITHOUT audit" in out, out
    assert read(audits).split("\n")[0] == "pypi cisco-ai-skill-scanner 2.3.2", read(audits)
    assert "skill-scanner 2.3.2 (newest stable, wheels only, audited)" in out, out
    write(env["AI_RESOLVE_FIXTURES"], json.dumps({"http": {
        "https://pypi.org/pypi/guarddog/json": {"releases": {"3.2.0": [{}], "3.3.0": [{}]}},
        "https://pypi.org/pypi/cisco-ai-skill-scanner/json": {"releases": {"2.3.2": [{}]}}}}))
    code, out = bash(run, dict(env, AUDIT_RC="1"))
    assert "guarddog 3.3.0 not installed: 3.2.0 kept" in out and "pypi guarddog 3.3.0" in read(audits), out
    code, out = bash(run, env)
    assert "guarddog 3.2.0 -> 3.3.0 (newest stable, wheels only, audited)" in out, out


FAKE_CURL = r'''#!/usr/bin/env python3
import os, shutil, sys
a = sys.argv[1:]
url = [x for x in a if x.startswith("http")][-1]
out = a[a.index("-o") + 1] if "-o" in a else None
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write("curl " + url + "\n")
src = os.path.join(os.environ["FAKE_WEB"], url.replace("/", "_"))
if not os.path.exists(src):
    sys.exit(22)
if out and out != "/dev/null":
    shutil.copy(src, out)
elif not out:
    sys.stdout.write(open(src).read())
'''


def web_env(work, pins, files, http):
    """A fake curl that serves <files> by URL, resolver fixtures <http>, no gh and no slsa-verifier."""
    env, home, bindir = bash_env(work, pins)
    web = os.path.join(work, "web")
    for url, body in files.items():
        write(os.path.join(web, url.replace("/", "_")), body)
    stub(os.path.join(bindir, "curl"), FAKE_CURL)
    stub(os.path.join(bindir, "gh"), "#!/bin/sh\nexit 1\n")              # not logged in: no attestation check
    fx = os.path.join(work, "fx.json")
    write(fx, json.dumps({"http": http, "git": {}}))
    env.update({"FAKE_LOG": os.path.join(work, "log"), "FAKE_WEB": web, "AI_RESOLVE_FIXTURES": fx,
                "PATH": os.path.join(home, ".local", "bin") + ":" + env["PATH"]})   # what detect_os adds on macOS
    return env, home, bindir


def sha256(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def arch(kind):
    m = os.uname().machine
    if kind == "osv":
        return "amd64" if m in ("x86_64", "amd64") else "arm64"
    return "x86_64" if m in ("x86_64", "amd64") else "aarch64"


def t_osv_scanner(work):
    """osv-scanner: checked against the release's SHA256SUMS; without slsa-verifier every change prints
    "unaudited binary update"; a slsa-verifier that rejects the binary stops the install; one that accepts it is
    reported as verified; a checksum mismatch stops the install."""
    asset = "osv-scanner_darwin_%s" % arch("osv")
    binary = "#!/bin/sh\necho osv-scanner version: 2.8.0\n"
    base = "https://github.com/google/osv-scanner/releases/download/v2.8.0/"
    rel = {"tag_name": "v2.8.0", "prerelease": False, "draft": False,
           "assets": [{"name": "osv-scanner_SHA256SUMS", "browser_download_url": base + "osv-scanner_SHA256SUMS"}]}
    http = {"https://api.github.com/repos/google/osv-scanner/releases?per_page=100": [rel],
            "https://api.github.com/repos/google/osv-scanner/releases/tags/v2.8.0": rel,
            base + "osv-scanner_SHA256SUMS": "%s  %s\n" % (sha256(binary), asset)}
    env, home, bindir = web_env(work, 'OSV_SCANNER_SOURCE="github google/osv-scanner stable"\n',
                                {base + asset: binary, base + "multiple.intoto.jsonl": "{}"}, http)
    inst = os.path.join(home, ".local", "bin", "osv-scanner")
    stub(os.path.join(bindir, "slsa-verifier"), "#!/bin/sh\nexit 1\n")
    code, out = bash(LIBS + "tools_osv_scanner", env)
    assert "slsa-verifier rejected" in out and not os.path.exists(inst), out
    os.remove(os.path.join(bindir, "slsa-verifier"))
    code, out = bash(LIBS + "tools_osv_scanner", env)
    assert "unaudited binary update: osv-scanner none -> 2.8.0" in out and os.path.exists(inst), out
    assert "not agent-audited" in out, out
    os.remove(inst)
    stub(os.path.join(bindir, "slsa-verifier"), '#!/bin/sh\necho "$*" >> %s\nexit 0\n' % os.path.join(work, "slsa"))
    code, out = bash(LIBS + "tools_osv_scanner", env)
    assert "SLSA provenance verified" in out and "unaudited" not in out and os.path.exists(inst), out
    assert "--source-uri github.com/google/osv-scanner --source-tag v2.8.0" in read(os.path.join(work, "slsa"))
    code, out = bash(LIBS + "tools_osv_scanner", env)
    assert "osv-scanner 2.8.0 present" in out, out
    os.remove(inst)
    write(os.path.join(work, "web", (base + asset).replace("/", "_")), binary + "# changed\n")
    code, out = bash(LIBS + "tools_osv_scanner", env)
    assert "sha256 differs" in out and not os.path.exists(inst), out


def t_gitleaks_pin(work):
    """Review S6: gitleaks installs only when the archive's sha256 is the one pinned in ai/pins.env
    (GITLEAKS_SHA256_<OS>_<ARCH>, for GITLEAKS_HOLD), not only the one in the release's own checksums file."""
    import io
    import tarfile
    asset = "gitleaks_8.30.1_darwin_%s.tar.gz" % ("x64" if os.uname().machine in ("x86_64", "amd64") else "arm64")
    pin_var = "GITLEAKS_SHA256_DARWIN_%s" % ("X64" if "x64" in asset else "ARM64")
    binary = b"#!/bin/sh\necho gitleaks version 8.30.1\n"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo("gitleaks")
        info.size, info.mode = len(binary), 0o755
        tf.addfile(info, io.BytesIO(binary))
    import hashlib
    digest = hashlib.sha256(buf.getvalue()).hexdigest()
    base = "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/"
    sums = "gitleaks_8.30.1_checksums.txt"
    rel = {"tag_name": "v8.30.1", "prerelease": False, "draft": False,
           "assets": [{"name": sums, "browser_download_url": base + sums}]}
    http = {"https://api.github.com/repos/gitleaks/gitleaks/releases?per_page=100": [rel],
            "https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1": rel,
            base + sums: "%s  %s\n" % (digest, asset)}
    env, home, bindir = web_env(work, 'GITLEAKS_SOURCE="github gitleaks/gitleaks stable"\nGITLEAKS_HOLD=8.30.1\n',
                                {}, http)
    os.makedirs(os.path.join(work, "web"), exist_ok=True)
    with open(os.path.join(work, "web", (base + asset).replace("/", "_")), "wb") as fh:
        fh.write(buf.getvalue())
    inst = os.path.join(home, ".local", "bin", "gitleaks")
    code, out = bash(LIBS + '%s=%s; tools_gitleaks' % (pin_var, "0" * 64), env)
    assert "differs from the pin" in out and not os.path.exists(inst), out
    code, out = bash(LIBS + '%s=""; tools_gitleaks' % pin_var, env)
    assert "no pinned sha256" in out and not os.path.exists(inst), out
    code, out = bash(LIBS + '%s=%s; tools_gitleaks' % (pin_var, digest), env)
    assert os.path.exists(inst) and "pinned sha256 checked" in out, out


def t_herdr(work):
    """herdr: sha256 from herdr's release manifest; a GitHub attestation is checked only with a logged-in gh;
    otherwise "unaudited binary update"; a mismatch stops the install."""
    target = "macos-%s" % arch("herdr")
    asset = "herdr-" + target
    binary = "#!/bin/sh\necho herdr 0.9.6\n"
    base = "https://github.com/herdrdev/herdr/releases/download/v0.9.6/"
    http = {"https://api.github.com/repos/herdrdev/herdr/releases?per_page=100":
                [{"tag_name": "v0.9.6", "prerelease": False, "draft": False, "assets": []}],
            "https://herdr.dev/latest.json": {"version": "0.9.6", "releases": {"0.9.6": {"sha256": {target: sha256(binary)}}}}}
    env, home, bindir = web_env(work, 'HERDR_SOURCE="github herdrdev/herdr stable"\nHERDR_CHECKSUMS=https://herdr.dev/latest.json\n',
                                {base + asset: binary}, http)
    inst = os.path.join(home, ".local", "bin", "herdr")
    code, out = bash(LIBS + "tools_herdr", env)
    assert "unaudited binary update: herdr none -> 0.9.6" in out and "herdr 0.9.6 (release binary" in out, out
    os.remove(inst)
    att = "https://api.github.com/repos/herdrdev/herdr/attestations/sha256:" + sha256(binary)
    write(os.path.join(work, "web", att.replace("/", "_")), "{}")
    stub(os.path.join(bindir, "gh"), '#!/bin/sh\n[ "$1" = auth ] && exit 0\n[ "$1 $2" = "attestation verify" ] && exit ${GH_RC:-0}\nexit 1\n')
    code, out = bash(LIBS + "tools_herdr", env)
    assert "GitHub artifact attestation verified" in out and "unaudited" not in out and os.path.exists(inst), out
    os.remove(inst)
    code, out = bash(LIBS + "tools_herdr", dict(env, GH_RC="1"))
    assert "gh attestation verify rejected" in out and not os.path.exists(inst), out


def t_src_swap_and_dry_sha(work):
    """plugin_clone leaves no .new/.old folder next to the source; in a dry run the plugin steps get the commit
    the clone would move to, not the one on disk."""
    up = os.path.join(work, "up", "plug")
    shas = upstream(up, "plug", "plug", ["1.0.0", "1.1.0"])
    env, home, _ = bash_env(work, 'PLUG_SOURCE="git %s stable"\n' % up)
    dest = os.path.join(home, ".local", "share", "ai", "plugins", "plug")
    git("clone", "-q", up, dest)
    git("-c", "advice.detachedHead=false", "checkout", "-q", shas["1.0.0"], cwd=dest)
    code, out = bash(LIBS + 'echo "dry=$(AI_DRY_RUN=1 src_sha_for plug) real=$(src_sha_for plug)"', env)
    assert "dry=%s real=%s" % (shas["1.1.0"], shas["1.0.0"]) in out, out
    code, out = bash(LIBS + 'AI_SKIP_PACKAGES=0; audit_ok() { return 0; }; plugin_clone plug plug', env)
    assert code == 0 and git("rev-parse", "HEAD", cwd=dest) == shas["1.1.0"], out
    assert sorted(os.listdir(os.path.dirname(dest))) == ["plug"], os.listdir(os.path.dirname(dest))


def t_playwright_keep_only(work):
    """ai-start: after a HOLD back to an older Playwright MCP that is still on disk, only that folder stays, so
    ai-playwright-mcp (highest folder) starts the held version."""
    from importlib.machinery import SourceFileLoader
    import types
    loader = SourceFileLoader("ai_start", os.path.join(AI_DIR, "bin", "ai-start"))
    mod = types.ModuleType(loader.name)
    mod.__file__ = loader.path
    loader.exec_module(mod)
    home = os.path.join(work, "home")
    for v in ("0.0.85", "0.0.90"):
        stub(os.path.join(home, ".local", "share", "ai", "npm", "playwright-mcp-" + v, "node_modules", ".bin",
                          "mcp-server-playwright"), "#!/bin/sh\necho pw-%s\n" % v)
    setup(work, 'PLAYWRIGHT_MCP_SOURCE="npm @playwright/mcp stable"\nPLAYWRIGHT_MCP_HOLD=0.0.85\n',
          http={NPM + "@playwright%2Fmcp/0.0.85": {"version": "0.0.85", "dist": {"integrity": "sha512-pw"}}})
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        assert mod.ensure_playwright() is True
    finally:
        os.environ["HOME"] = old
    assert os.listdir(os.path.join(home, ".local", "share", "ai", "npm")) == ["playwright-mcp-0.0.85"]
    res = subprocess.run(["bash", os.path.join(AI_DIR, "bin", "ai-playwright-mcp")], stdout=subprocess.PIPE,
                         env={"HOME": home, "PATH": os.environ["PATH"]})
    assert res.stdout.decode().strip() == "pw-0.0.85", res.stdout


def t_playwright_profile_audit(work):
    """ai-adopt --tools browser (ticket 16): profile dev-mac audits no npm installs (owner 2026-11-14), so the
    pinned @playwright/mcp installs with "audit skipped: profile dev-mac"; profile server still needs a PASS."""
    pins = 'PLAYWRIGHT_MCP_SOURCE="npm @playwright/mcp stable"\n'
    latest = {NPM + "@playwright%2Fmcp/latest": {"version": "0.0.90", "dist": {"integrity": "sha512-pw"}}}
    for profile in ("dev-mac", "server"):
        env, home = npm_env(os.path.join(work, profile), pins, latest, {"@playwright/mcp@0.0.90": "sha512-pw"},
                            {"AI_PROFILE": profile, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
                             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"})
        proj = os.path.join(work, profile, "proj")
        git("init", "-q", proj)
        res = subprocess.run([sys.executable, os.path.join(AI_DIR, "bin", "ai-start"), "--dir", proj, "--tools",
                              "browser", "--yes", "--no-onboard", "--no-knowledge", "--no-measure"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=120)
        out = res.stdout.decode()
        pkg = os.path.join(home, ".local", "share", "ai", "npm", "playwright-mcp-0.0.90", "node_modules",
                           "@playwright", "mcp", "package.json")
        if profile == "dev-mac":
            assert "audit skipped: profile dev-mac" in out and os.path.isfile(pkg), out
        else:
            assert "no agent-audit PASS" in out and not os.path.exists(pkg), out


FAKE_CLAUDE = r'''#!/usr/bin/env python3
# Fake `claude plugin ...`: the behaviour seen in a temp CLAUDE_CONFIG_DIR on 2026-11-14 (remove uninstalls the
# marketplace's plugins; add Owner/repo#ref stores {source: github, repo, ref}; update + plugin update move).
# install writes enabledPlugins[p] = true in settings.json, uninstall drops the key (data kept with --keep-data).
# FAKE_FAIL_ADD=<source>: that add fails. FAKE_UPDATE_BROKEN=1: plugin update does nothing.
# FAKE_BAD_INSTALL=1: install records a wrong version. FAKE_UNINSTALL_FAIL=1, FAKE_MCP_REMOVE_FAIL=1: those fail.
import json, os, shutil, subprocess, sys
cfg = os.environ["CLAUDE_CONFIG_DIR"]
pd = os.path.join(cfg, "plugins")
km, ip, st = os.path.join(pd, "known_marketplaces.json"), os.path.join(pd, "installed_plugins.json"), os.path.join(cfg, "settings.json")
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
k, i, sett = load(km, {}), load(ip, {"version": 2, "plugins": {}}), load(st, {})
en = sett.setdefault("enabledPlugins", {})
def git(*args):
    return subprocess.run(["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode().strip()
def root(name):
    src = k[name]["source"]
    return src["path"] if src["source"] == "directory" else os.path.join(pd, "marketplaces", name)
def drop(p):
    i["plugins"].pop(p, None)
    en.pop(p, None)
if a[:3] == ["plugin", "marketplace", "add"]:
    src = a[3]
    if src == os.environ.get("FAKE_FAIL_ADD"):
        sys.exit(1)
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
        drop(p)
    shutil.rmtree(os.path.join(pd, "marketplaces", name), True)
elif a[:3] == ["plugin", "marketplace", "update"]:
    src = k[a[3]]["source"]
    if src["source"] == "github" and not src.get("ref"):
        d = root(a[3]); git("-C", d, "pull", "-q", "--ff-only")
elif a[:3] == ["plugin", "marketplace", "list"]:
    print("\\n".join(k))
elif a[:2] == ["plugin", "install"] or (a[:2] == ["plugin", "update"] and not os.environ.get("FAKE_UPDATE_BROKEN")):
    p = a[2]; m = p.split("@")[1]
    if m not in k:
        sys.exit(1)
    if a[1] == "update" and p not in i["plugins"]:
        sys.exit(1)
    r = root(m)
    ver = json.load(open(os.path.join(r, ".claude-plugin", "plugin.json")))["version"]
    row = {"scope": "user", "version": "9.9.9" if os.environ.get("FAKE_BAD_INSTALL") else ver,
           "files": git("-C", r, "rev-parse", "HEAD")}
    if k[m]["source"]["source"] != "directory":
        row["gitCommitSha"] = row["files"]
    if a[1] == "update" and k[m]["source"]["source"] == "directory" and i["plugins"][p][0]["version"] == ver:
        row = i["plugins"][p][0]          # same version: the real CLI keeps the old cache
    i["plugins"][p] = [row]
    if a[1] == "install":
        en[p] = True
elif a[:2] == ["plugin", "uninstall"]:
    if os.environ.get("FAKE_UNINSTALL_FAIL"):
        sys.exit(1)
    drop(a[2])
elif a[:2] == ["plugin", "list"]:
    print("\\n".join(i["plugins"]))
elif a[:2] == ["mcp", "remove"]:          # claude mcp remove --scope user NAME: the user scope of .claude.json
    if os.environ.get("FAKE_MCP_REMOVE_FAIL"):
        sys.exit(1)
    cj = os.path.join(cfg, ".claude.json")
    d = load(cj, {})
    if a[-1] not in (d.get("mcpServers") or {}):
        sys.exit(1)
    d["mcpServers"].pop(a[-1])
    save(cj, d)
save(km, k); save(ip, i); save(st, sett)
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


def enabled(home):
    return json.load(open(os.path.join(home, ".claude", "settings.json"))).get("enabledPlugins") or {}


def set_enabled(home, plugin, value):
    path = os.path.join(home, ".claude", "settings.json")
    data = json.load(open(path))
    data.setdefault("enabledPlugins", {})[plugin] = value
    write(path, json.dumps(data))


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
    set_enabled(home, "plug@tp", False)
    os.remove(os.path.join(work, "log"))
    script = LIBS + 'audit_ok() { echo "AUDIT $*"; return 0; }; claude_git_plugin testplug tp Owner/plug plug@tp'
    code, out = bash(script, env)
    assert code == 0, out
    known, plugins = claude_files(home)
    assert known["tp"]["source"] == {"source": "github", "repo": "Owner/plug", "ref": "v1.1.0"}, known
    assert plugins["plug@tp"][0]["gitCommitSha"] == shas["1.1.0"], plugins
    assert "AUDIT dir" in out and "%s testplug" % shas["1.1.0"] in out, "the new source is audited before the move: " + out
    log = mutations(work)
    assert log[:3] == ["claude plugin uninstall plug@tp --keep-data", "claude plugin marketplace remove tp",
                       "claude plugin marketplace add Owner/plug#v1.1.0"], log
    assert enabled(home)["plug@tp"] is False, "the user's enabledPlugins value survives the replace"
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
    set_enabled(home, "plug3@tp3", False)
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
    assert log[-2:] == ["claude plugin uninstall plug3@tp3 --keep-data", "claude plugin install plug3@tp3 --scope user"], log
    assert read(os.path.join(home, ".local", "state", "ai", "claude-plugin.plug3.src")).strip() == head
    assert enabled(home)["plug3@tp3"] is False, "the user's enabledPlugins value survives the reinstall"


def t_claude_dir_same_version(work):
    """Local folder marketplace, new commit with the SAME plugin.json version: the stamp (not the version) says
    it is new, so the plugin is reinstalled and the stamp moves only after the check. No stamp yet: refresh once."""
    src = os.path.join(work, "up", "Owner", "plug4")
    upstream(src, "tp4", "plug4", ["1.0.0"])
    env, home = claude_env(work, "")
    stamp = os.path.join(home, ".local", "state", "ai", "claude-plugin.plug4.src")
    def run():
        return LIBS + 'claude_plugin tp4 %s plug4@tp4 %s "$(plugin_json_version %s)"' % (src, git("rev-parse", "HEAD", cwd=src), src)
    code, out = bash(run(), env)
    assert code == 0 and os.path.exists(stamp), out
    assert read(stamp).strip() == git("rev-parse", "HEAD", cwd=src), out
    write(os.path.join(src, "README.md"), "new text, same version\n")
    git("add", "-A", cwd=src)
    git("commit", "-q", "-m", "docs", cwd=src)
    new = git("rev-parse", "HEAD", cwd=src)
    os.remove(os.path.join(work, "log"))
    code, out = bash(run(), env)
    _known, plugins = claude_files(home)
    assert code == 0 and plugins["plug4@tp4"][0]["files"] == new, (out, plugins)
    assert "claude plugin uninstall plug4@tp4 --keep-data" in mutations(work), mutations(work)
    assert read(stamp).strip() == new
    os.remove(os.path.join(work, "log"))
    code, out = bash(run(), env)
    assert code == 0 and mutations(work) == [], mutations(work)
    os.remove(stamp)                                   # an install from before the stamp existed: refresh once
    code, out = bash(run(), env)
    assert code == 0 and read(stamp).strip() == new and "claude plugin update plug4@tp4" in mutations(work), out


def t_claude_fresh_install_checked(work):
    """A fresh install is checked too: Claude reporting another version is a warning, and no stamp is written."""
    src = os.path.join(work, "up", "Owner", "plug5")
    upstream(src, "tp5", "plug5", ["1.0.0"])
    env, home = claude_env(work, "")
    code, out = bash(LIBS + 'claude_plugin tp5 %s plug5@tp5 %s 1.0.0 || echo rc=$?' % (src, git("rev-parse", "HEAD", cwd=src)),
                     dict(env, FAKE_BAD_INSTALL="1"))
    assert "rc=1" in out and "wanted 1.0.0" in out, out
    assert not os.path.exists(os.path.join(home, ".local", "state", "ai", "claude-plugin.plug5.src"))


def t_claude_own_replace_rollback(work):
    """Our own marketplace at an older tag, a new tag whose add fails: the old source and the plugin come back,
    with the user's enabledPlugins value (false: claude-seo and claude-blog are off at user scope)."""
    up = os.path.join(work, "up", "Owner", "plug6")
    upstream(up, "tp6", "plug6", ["1.0.0", "1.1.0"])
    env, home = claude_env(work, 'TESTPLUG6_SOURCE="git %s stable"\n' % up)
    code, out = bash(LIBS + 'AI_DRY_RUN=0; claude_plugin tp6 "Owner/plug6#v1.0.0" plug6@tp6', env)
    assert code == 0, out
    set_enabled(home, "plug6@tp6", False)
    os.remove(os.path.join(work, "log"))
    script = LIBS + 'audit_ok() { return 0; }; claude_git_plugin testplug6 tp6 Owner/plug6 plug6@tp6 || echo rc=$?'
    code, out = bash(script, dict(env, FAKE_FAIL_ADD="Owner/plug6#v1.1.0"))
    known, plugins = claude_files(home)
    assert "rc=1" in out and known["tp6"]["source"]["ref"] == "v1.0.0", (out, known)
    assert "plug6@tp6" in plugins and enabled(home)["plug6@tp6"] is False, (plugins, enabled(home))
    assert mutations(work)[0] == "claude plugin uninstall plug6@tp6 --keep-data", mutations(work)
    entries = json.load(open(os.path.join(home, ".local", "state", "ai", "managed-keys.json")))["entries"]
    assert not any(e["key"].startswith("cmd:claude-marketplace-restore:") for e in entries), "ours: no restore record"
    code, out = bash(script, env)                      # the add works now: moved, still off
    known, plugins = claude_files(home)
    assert known["tp6"]["source"]["ref"] == "v1.1.0" and enabled(home)["plug6@tp6"] is False, (out, known)


def t_claude_plugin_rejected_newest(work):
    """QA 2026-11-15 item 8 (OMC 5.8.6): the installed newest version was put on before the skill-scanner rule
    and fails it now. It is audited again (installed without "scanned"), and the plugin moves back to the newest
    older tag that passes (max 5 tried); a candidate whose plugin config names a file the tree lacks (OMC's
    bridge/mcp-server.cjs build output) is skipped. None passes: kept, a LOUD warning, ai-doctor FAILs it."""
    up = os.path.join(work, "up", "Owner", "plug7")
    shas = upstream(up, "tp7", "plug7", ["1.0.0", "1.1.0", "1.2.0", "1.3.0"])
    git("checkout", "-q", "v1.1.0", cwd=up)
    write(os.path.join(up, ".mcp.json"), json.dumps({"mcpServers": {"t": {"command": "node",
                                                                      "args": ["${CLAUDE_PLUGIN_ROOT}/bridge/x.cjs"]}}}))
    git("add", "-f", ".mcp.json", cwd=up)          # -f: a global excludes file may list .mcp.json
    git("commit", "-q", "-m", "1.1.0 without its build output", cwd=up)
    git("tag", "-f", "-a", "v1.1.0", "-m", "v1.1.0", cwd=up)
    shas["1.1.0"] = git("rev-parse", "HEAD", cwd=up)
    git("checkout", "-q", "main", cwd=up)
    env, home = claude_env(work, 'TESTPLUG7_SOURCE="git %s stable"\n' % up)
    code, out = bash(LIBS + 'AI_DRY_RUN=0; claude_plugin tp7 "Owner/plug7#v1.3.0" plug7@tp7 %s' % shas["1.3.0"], env)
    assert code == 0, out
    state = os.path.join(home, ".local", "state", "ai", "resolved.json")
    write(state, json.dumps({"tools": {"testplug7": {"installed": {"version": "1.3.0", "sha": shas["1.3.0"]}}}}))
    bad = " ".join([shas["1.3.0"], shas["1.2.0"]])
    script = LIBS + ('audit_ok() { case " %s " in *" $3 "*) resolver reject testplug7 --version "$R_VERSION" '
                     '--sha "$3"; return 1 ;; esac; echo "AUDIT ok $3"; return 0; }; '
                     'claude_git_plugin testplug7 tp7 Owner/plug7 plug7@tp7 || echo rc=$?') % bad
    code, out = bash(script, env)
    known, plugins = claude_files(home)
    assert known["tp7"]["source"]["ref"] == "v1.0.0" and plugins["plug7@tp7"][0]["gitCommitSha"] == shas["1.0.0"], (out, known)
    assert "bridge/x.cjs" in out and "not installable" in out, "1.1.0 lacks its MCP server file: " + out
    assert "moved to v1.0.0, the newest version that passes the audit (1.3.0 failed it)" in out, out
    st = json.load(open(state))["tools"]["testplug7"]
    assert st["installed"]["version"] == "1.0.0" and st["installed"]["scanned"] is True, st
    assert st["rejected"]["version"] == "1.3.0", "the newest rejected version stays on record: %s" % st
    code, out = bash(script, env)
    assert "rejected by skill-scanner before" in out and "the installed 1.0.0 (audited) stays" in out, out
    # none passes: the installed failing version stays, loudly
    code, out = bash(LIBS + 'AI_DRY_RUN=0; claude_plugin tp7 "Owner/plug7#v1.3.0" plug7@tp7 %s' % shas["1.3.0"], env)
    write(state, json.dumps({"tools": {"testplug7": {"installed": {"version": "1.3.0", "sha": shas["1.3.0"]}}}}))
    code, out = bash(LIBS + 'audit_ok() { resolver reject testplug7 --version "$R_VERSION" --sha "$3"; return 1; }; '
                            'claude_git_plugin testplug7 tp7 Owner/plug7 plug7@tp7 || echo rc=$?', env)
    assert "rc=1" in out and "LOUD: plug7@tp7 1.3.0 is installed and fails the audit itself" in out, out
    st = json.load(open(state))["tools"]["testplug7"]
    assert st["rejected"]["version"] == st["installed"]["version"] == "1.3.0", st


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
