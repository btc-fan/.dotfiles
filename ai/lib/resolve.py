#!/usr/bin/env python3
"""resolve.py: the newest stable release of each tool of the ai setup (owner decision 2026-11-14).

ai/pins.env names WHERE each tool comes from: <PREFIX>_SOURCE="<type> <name> <channel>", and optionally
<PREFIX>_HOLD=<version> (install exactly that version). The tool id is the prefix in lower case with "-" for
"_" (CODEX -> codex, OMC_PLUGIN -> omc-plugin). This file finds the version. One place, python 3.9 stdlib only.

Source types (channel "stable" = not a pre-release, not a draft, not yanked; no cooldown):
  npm    <package>          dist-tags.latest of the registry, with that version's dist.integrity
  pypi   <project>          newest version that is not a pre-release and not yanked
  github <owner/repo>       newest semver release that is not a draft and not a pre-release, its commit
                            (git ls-remote) and the release's checksum file when it has one
  git    <clone URL>        newest vX.Y.Z tag (no suffix) and its commit; no such tag: HEAD of the default branch

Offline or a registry error: the last resolved value from resolved.json (status "cached"), else nothing
(status "none"). Callers keep what is installed then; the install never fails for that.

  resolve.py shell <tool> [--no-write]      shell assignments R_VERSION R_REF R_SHA R_INTEGRITY R_CHECKSUMS
                                            R_SOURCE R_STATUS (new|hold|cached|none) R_NOTE, for bash eval
  resolve.py json <tool>                    the same as JSON
  resolve.py list [--offline] [--no-write]  every tool, one line each (install.sh prints it)
  resolve.py record <tool> --version V [--sha S] [--integrity I]
                                            installed now: resolved.json "installed" + one audit.log line
  resolve.py checksum <tool> <version> <asset> [--target T]
                                            sha256 of a release asset from the release's published checksums
  resolve.py verify-npm <prefix> <package> <version> [integrity]
                                            the installed package has that version (and integrity, from the
                                            lockfile where npm writes one)
  resolve.py status [--network]             JSON for ai-doctor: per tool installed and newest
  resolve.py reject <tool> --version V [--sha S] [--findings TEXT]
                                            skill-scanner rejected that version (HIGH or CRITICAL): kept in
                                            resolved.json ("rejected") for ai-doctor; an install of that same
                                            version clears it
  resolve.py candidates <tool> [--max N] [--below V]
                                            git sources: the stable tags newest first (below V), one
                                            "<version> <tag> <commit>" line each: the fallback when the newest
                                            is rejected or incomplete (owner QA 2026-11-15, OMC 5.8.6)
  resolve.py installed-info <tool>          shell assignments I_VERSION I_SHA I_SCANNED (1: recorded after this
                                            setup audited it) X_VERSION (the rejected version, or empty)

State: $AI_STATE_DIR (default ~/.local/state/ai)/resolved.json and audit.log. Tests: AI_PINS (pins file),
AI_RESOLVE_FIXTURES (a JSON file {"http": {url: body}, "git": {url: ls-remote text}}; a URL not in it is
"offline"), AI_RESOLVE_OFFLINE=1, AI_RESOLVE_MEMO (one JSON file per install run: each tool resolved once).
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
AI_DIR = os.path.dirname(HERE)
TIMEOUT = float(os.environ.get("AI_RESOLVE_TIMEOUT") or 15)
SEMVER = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
PYPI_STABLE = re.compile(r"(\d+(?:\.\d+)*)(?:\.post(\d+))?")
CHECKSUM_ASSET = re.compile(r"(?i)(sha256sums|checksums?(\.txt)?$|\.sha256$)")
SIGNATURE_ASSET = re.compile(r"(?i)\.(sig|asc|pem|sigstore|bundle|crt|cert)$")
FIELDS = ("version", "ref", "sha", "integrity", "checksums", "source", "status", "note")


class Unavailable(Exception):
    """Offline, timeout, HTTP error, bad answer: the caller falls back to the cached value."""


# ---------------------------------------------------------------- sources (ai/pins.env)

def pins_path():
    return os.environ.get("AI_PINS") or os.path.join(AI_DIR, "pins.env")


def read_pins(path=None):
    out = {}
    with open(path or pins_path(), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)=(.*)$", line)
            if not m:
                continue
            try:
                words = shlex.split(m.group(2), comments=True)
            except ValueError:
                continue
            out[m.group(1)] = " ".join(words)
    return out


def tool_id(prefix):
    return prefix.lower().replace("_", "-")


def tools(pins=None):
    """{tool id: {"prefix", "type", "name", "channel", "hold", "checksums"}} for every <PREFIX>_SOURCE line."""
    pins = read_pins() if pins is None else pins
    out = {}
    for key, value in pins.items():
        if not key.endswith("_SOURCE"):
            continue
        prefix = key[:-len("_SOURCE")]
        words = value.split()
        if len(words) < 2:
            continue
        out[tool_id(prefix)] = {
            "prefix": prefix, "type": words[0], "name": words[1],
            "channel": words[2] if len(words) > 2 else "stable",
            "hold": pins.get(prefix + "_HOLD", ""),
            "checksums": pins.get(prefix + "_CHECKSUMS", ""),
        }
    return out


# ---------------------------------------------------------------- network (or fixtures)

_FIXTURES = None


def fixtures():
    global _FIXTURES
    path = os.environ.get("AI_RESOLVE_FIXTURES")
    if not path:
        return None
    if _FIXTURES is None:
        with open(path) as fh:
            _FIXTURES = json.load(fh)
    return _FIXTURES


def offline():
    return os.environ.get("AI_RESOLVE_OFFLINE") == "1"


def http_get(url, accept="application/json"):
    fx = fixtures()
    if fx is not None:
        body = (fx.get("http") or {}).get(url)
        if body is None:
            raise Unavailable("no answer for %s" % url)
        return body if isinstance(body, str) else json.dumps(body)
    if offline():
        raise Unavailable("offline")
    # curl first (a prerequisite of install.sh, and it uses the system CA store); urllib when it is missing.
    try:
        res = subprocess.run(["curl", "-fsSL", "--max-time", str(int(TIMEOUT)), "-H", "Accept: " + accept,
                              "-A", "ai-setup-resolver", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=TIMEOUT + 5)
        if res.returncode != 0:
            raise Unavailable("curl %s: exit %d" % (url, res.returncode))
        return res.stdout.decode("utf-8", "replace")
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        raise Unavailable("timeout: %s" % url)
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "ai-setup-resolver"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception as exc:          # URLError, HTTPError, ssl, socket.timeout
        raise Unavailable("%s: %s" % (url, exc))


def http_json(url, accept="application/json"):
    try:
        return json.loads(http_get(url, accept))
    except ValueError:
        raise Unavailable("not JSON: %s" % url)


def git_ls_remote(url, *args):
    fx = fixtures()
    key = " ".join((url,) + args)
    if fx is not None:
        text = (fx.get("git") or {}).get(key)
        if text is None:
            raise Unavailable("no answer for git ls-remote %s" % key)
        return text
    if offline():
        raise Unavailable("offline")
    try:
        opts = [a for a in args if a.startswith("-")]
        patterns = [a for a in args if not a.startswith("-")]
        res = subprocess.run(["git", "ls-remote"] + opts + [url] + patterns, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=TIMEOUT,
                             env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unavailable("git ls-remote %s: %s" % (url, exc))
    if res.returncode != 0:
        raise Unavailable("git ls-remote %s: exit %d" % (url, res.returncode))
    return res.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------- resolvers

def semver_key(tag):
    m = SEMVER.fullmatch(tag)
    return tuple(int(x) for x in m.groups()) if m else None


def resolve_npm(name, hold=""):
    path = name.replace("/", "%2F") if name.startswith("@") else name
    doc = http_json("https://registry.npmjs.org/%s/%s" % (path, hold or "latest"))
    version, integrity = doc.get("version"), (doc.get("dist") or {}).get("integrity")
    if not version or not integrity:
        raise Unavailable("npm %s: no version or integrity in the registry answer" % name)
    return {"version": version, "integrity": integrity}


def pypi_key(v):
    """(release padded with zeros, post number): 1.0.post5 < 1.0.1, 1.0 == 1.0.0."""
    m = PYPI_STABLE.fullmatch(v)
    if not m:
        return None
    release = [int(x) for x in m.group(1).split(".")]
    return (tuple(release + [0] * (12 - len(release))), int(m.group(2) or 0))


def same_version(a, b):
    """1.0 == 1.0.0 (trailing zero parts ignored); anything else compares as text."""
    def norm(v):
        return re.sub(r"(\.0+)+$", "", v or "")
    return norm(a) == norm(b)


def is_checksum_asset(name):
    return bool(CHECKSUM_ASSET.search(name or "")) and not SIGNATURE_ASSET.search(name or "")


def resolve_pypi(name, hold=""):
    doc = http_json("https://pypi.org/pypi/%s/json" % name)
    releases = doc.get("releases") or {}

    def usable(v):
        files = releases.get(v) or []
        return bool(files) and not all(f.get("yanked") for f in files)

    if hold:
        if not usable(hold):
            raise Unavailable("pypi %s: held version %s not found or yanked" % (name, hold))
        return {"version": hold}
    best = None
    for v in releases:
        k = pypi_key(v)
        if k is not None and usable(v) and (best is None or k > pypi_key(best)):
            best = v
    if best is None:
        raise Unavailable("pypi %s: no stable release" % name)
    return {"version": best}


def tag_commit(url, tag):
    """Commit of a tag (the peeled ^{} line for an annotated tag), or "" when unknown."""
    try:
        text = git_ls_remote(url, "--tags")
    except Unavailable:
        return ""
    plain = peeled = ""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        if parts[1] == "refs/tags/%s^{}" % tag:
            peeled = parts[0]
        elif parts[1] == "refs/tags/%s" % tag:
            plain = parts[0]
    return peeled or plain


def resolve_github(repo, hold=""):
    rels = http_json("https://api.github.com/repos/%s/releases?per_page=100" % repo,
                     accept="application/vnd.github+json")
    if not isinstance(rels, list):
        raise Unavailable("github %s: unexpected answer" % repo)
    best = None
    for r in rels:
        tag = r.get("tag_name") or ""
        if r.get("draft") or r.get("prerelease") or semver_key(tag) is None:
            continue
        if hold:
            if tag in (hold, "v" + hold.lstrip("v")):
                best = r
                break
            continue
        if best is None or semver_key(tag) > semver_key(best["tag_name"]):
            best = r
    if best is None:
        raise Unavailable("github %s: %s" % (repo, "held release %s not found" % hold if hold else "no stable release"))
    tag = best["tag_name"]
    sums = [a.get("browser_download_url") for a in best.get("assets") or []
            if is_checksum_asset(a.get("name"))]
    return {"version": tag.lstrip("v"), "ref": tag, "sha": tag_commit("https://github.com/%s" % repo, tag),
            "checksums": sums[0] if sums else ""}


def resolve_git(url, hold=""):
    tags = {}
    for line in git_ls_remote(url, "--tags").splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        if name.endswith("^{}"):
            tags[name[:-3]] = parts[0]           # the peeled commit wins over the tag object
        else:
            tags.setdefault(name, parts[0])
    if hold:
        for t in (hold, "v" + hold.lstrip("v")):
            if t in tags:
                return {"version": t.lstrip("v"), "ref": t, "sha": tags[t]}
        if re.fullmatch(r"[0-9a-f]{40}", hold):
            return {"version": hold[:12], "ref": "", "sha": hold}
        raise Unavailable("git %s: held tag %s not found" % (url, hold))
    stable = [t for t in tags if semver_key(t) is not None]
    if stable:
        best = max(stable, key=semver_key)
        return {"version": best.lstrip("v"), "ref": best, "sha": tags[best]}
    for line in git_ls_remote(url, "HEAD").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "HEAD":
            return {"version": parts[0][:12], "ref": "", "sha": parts[0]}
    raise Unavailable("git %s: no tags and no HEAD" % url)


RESOLVERS = {"npm": resolve_npm, "pypi": resolve_pypi, "github": resolve_github, "git": resolve_git}


# ---------------------------------------------------------------- state (resolved.json, audit.log)

def state_dir():
    return os.environ.get("AI_STATE_DIR") or os.path.expanduser("~/.local/state/ai")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_state(path=None):
    try:
        with open(path or os.path.join(state_dir(), "resolved.json")) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) and isinstance(data.get("tools"), dict) else {"version": 1, "tools": {}}
    except (OSError, ValueError):
        return {"version": 1, "tools": {}}


def save_state(data):
    d = state_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "resolved.json")
    tmp = path + ".tmp.%d" % os.getpid()
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def source_text(spec):
    return "%s %s" % (spec["type"], spec["name"])


def resolve(tool, write=True, specs=None, use_memo=True):
    """{version, ref, sha, integrity, checksums, source, status, note}. status: new | hold | cached | none."""
    specs = tools() if specs is None else specs
    if tool not in specs:
        return dict({k: "" for k in FIELDS}, status="none", note="no %s source in ai/pins.env" % tool)
    spec = specs[tool]
    memo_path = os.environ.get("AI_RESOLVE_MEMO") if use_memo else None
    memo = {}
    if memo_path:
        try:
            with open(memo_path) as fh:
                memo = json.load(fh)
        except (OSError, ValueError):
            memo = {}
        if tool in memo:
            return memo[tool]
    out = {k: "" for k in FIELDS}
    out["source"] = source_text(spec)
    try:
        if spec["channel"] != "stable":
            raise Unavailable("channel %s is not known (only stable)" % spec["channel"])
        out.update(RESOLVERS[spec["type"]](spec["name"], spec["hold"]))
        out["status"] = "hold" if spec["hold"] else "new"
        if spec["hold"]:
            out["note"] = "%s_HOLD=%s in ai/pins.env" % (spec["prefix"], spec["hold"])
        if write:
            data = load_state()
            entry = data["tools"].setdefault(tool, {})
            entry["source"] = out["source"]
            entry["newest"] = dict({k: out[k] for k in ("version", "ref", "sha", "integrity", "checksums")},
                                   time=now(), hold=bool(spec["hold"]))
            save_state(data)
    except (Unavailable, KeyError, ValueError, TypeError, AttributeError) as exc:   # odd registry answers too
        cached = (load_state()["tools"].get(tool) or {}).get("newest") or {}
        held = spec["hold"]
        if cached.get("version") and (not held or held.lstrip("v") == cached["version"] or held == cached.get("sha")):
            out.update({k: cached.get(k, "") for k in ("version", "ref", "sha", "integrity", "checksums")})
            out["status"] = "cached"
            out["note"] = "%s; last resolved %s" % (exc, cached.get("time", "?"))
        else:
            out["status"] = "none"
            out["note"] = str(exc)
    if memo_path:
        memo[tool] = out
        try:
            with open(memo_path, "w") as fh:
                json.dump(memo, fh)
        except OSError:
            pass
    return out


def safe_resolve(tool, specs):
    """resolve() for `list`: one broken tool never stops the others."""
    try:
        return resolve(tool, write=False, specs=specs, use_memo=False)
    except Exception as exc:
        return dict({k: "" for k in FIELDS}, source=source_text(specs[tool]), status="none",
                    note="resolver error: %s: %s" % (type(exc).__name__, exc))


def record(tool, version, sha="", integrity="", specs=None):
    specs = tools() if specs is None else specs
    spec = specs.get(tool)
    source = source_text(spec) if spec else "?"
    data = load_state()
    entry = data["tools"].setdefault(tool, {})
    entry["source"] = source
    entry["installed"] = {"version": version, "sha": sha, "integrity": integrity, "time": now(), "scanned": True}
    if (entry.get("rejected") or {}).get("version") in (version, None, "", "-"):
        entry.pop("rejected", None)     # a rejected NEWER version stays recorded (ai-doctor, the fallback)
    save_state(data)
    # Same line shape as agent-audit (<time> <kind> <name> <version> <result>), kind "install": the audit
    # gate's 24 h PASS lookup reads only npm, pypi and dir lines, so these never count as an audit result.
    with open(os.path.join(state_dir(), "audit.log"), "a") as fh:
        fh.write("%s install %s %s INSTALLED %s %s\n" % (now(), tool, version or "-", sha or integrity or "-",
                                                        source.replace(" ", ":")))


def reject(tool, version, sha="", findings=""):
    """skill-scanner HIGH or CRITICAL (owner rule 2026-11-14): this version is never installed; ai-doctor reads it."""
    data = load_state()
    entry = data["tools"].setdefault(tool, {})
    old = (entry.get("rejected") or {}).get("version") or ""
    if semver_key(old) and semver_key(version) and semver_key(version) < semver_key(old):
        return          # an older fallback candidate failing too: the newest rejected version stays on record
    entry["rejected"] = {"version": version, "sha": sha, "findings": findings[:500], "time": now(),
                         "by": "skill-scanner"}
    save_state(data)


def rejected():
    """{tool: rejected entry} from resolved.json."""
    return {t: v["rejected"] for t, v in (load_state().get("tools") or {}).items()
            if isinstance(v, dict) and v.get("rejected")}


def candidates(tool, below="", limit=5, specs=None):
    """[(version, tag, commit)] of a git source, stable tags newest first, only versions below `below`."""
    specs = tools() if specs is None else specs
    spec = specs.get(tool)
    if not spec or spec["type"] != "git":
        return []
    tags = {}
    for line in git_ls_remote(spec["name"], "--tags").splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        if name.endswith("^{}"):
            tags[name[:-3]] = parts[0]
        else:
            tags.setdefault(name, parts[0])
    stable = sorted((t for t in tags if semver_key(t) is not None), key=semver_key, reverse=True)
    if below and semver_key(below) is not None:
        stable = [t for t in stable if semver_key(t) < semver_key(below)]
    return [(t.lstrip("v"), t, tags[t]) for t in stable[:limit]]


def installed_info(tool):
    entry = load_state()["tools"].get(tool) or {}
    inst = entry.get("installed") or {}
    return {"I_VERSION": inst.get("version") or "", "I_SHA": inst.get("sha") or "",
            "I_SCANNED": "1" if inst.get("scanned") else "0",
            "X_VERSION": (entry.get("rejected") or {}).get("version") or ""}


# ---------------------------------------------------------------- checksums, npm verify

def checksum(tool, version, asset, target=""):
    """sha256 hex of <asset> of release <version>, from the release's checksum file, else from the
    <PREFIX>_CHECKSUMS JSON manifest (herdr: releases.<version>.sha256.<target>)."""
    specs = tools()
    spec = specs.get(tool)
    if not spec:
        raise Unavailable("no %s source" % tool)
    if spec["type"] == "github":
        tag = version if version.startswith("v") else "v" + version
        try:
            rel = http_json("https://api.github.com/repos/%s/releases/tags/%s" % (spec["name"], tag),
                            accept="application/vnd.github+json")
        except Unavailable:
            rel = {}
        for a in rel.get("assets") or []:
            if is_checksum_asset(a.get("name")):
                for line in http_get(a["browser_download_url"], accept="text/plain").splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[-1].lstrip("*") == asset and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                        return parts[0].lower()
    if spec["checksums"]:
        doc = http_json(spec["checksums"])
        rel = (doc.get("releases") or {}).get(version.lstrip("v")) or (doc if doc.get("version") == version.lstrip("v") else {})
        value = (rel.get("sha256") or {}).get(target or asset) or ""
        if re.fullmatch(r"[0-9a-fA-F]{64}", value):
            return value.lower()
    raise Unavailable("%s %s: no published checksum for %s" % (tool, version, asset))


def verify_npm(prefix, package, version, integrity=""):
    """(ok, message). prefix = the folder that holds node_modules (npm --prefix, or the global lib folder)."""
    pj = os.path.join(prefix, "node_modules", package, "package.json")
    try:
        with open(pj) as fh:
            got = json.load(fh).get("version")
    except (OSError, ValueError):
        return False, "%s missing" % pj
    if got != version:
        return False, "%s is %s, want %s" % (package, got, version)
    if not integrity:
        return True, "%s %s installed (no integrity to compare)" % (package, version)
    for lock in (os.path.join(prefix, "package-lock.json"), os.path.join(prefix, "node_modules", ".package-lock.json")):
        try:
            with open(lock) as fh:
                pkgs = json.load(fh).get("packages") or {}
        except (OSError, ValueError):
            continue
        entry = pkgs.get("node_modules/" + package) or {}
        if entry.get("integrity"):
            if entry["integrity"] != integrity:
                return False, "%s %s integrity %s, registry said %s" % (package, version, entry["integrity"], integrity)
            return True, "%s %s installed, integrity matches the registry" % (package, version)
    return True, "%s %s installed (npm writes no lockfile here: npm checked the tarball against the registry)" % (
        package, version)


# ---------------------------------------------------------------- installed versions (ai-doctor)

VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)*)")
BINARIES = {"codex": "codex", "omc": "omc", "omx": "omx", "opencode": "opencode", "herdr": "herdr",
            "serena": "serena", "graphify": "graphify", "rtk": "rtk", "guarddog": "guarddog",
            "skill-scanner": "skill-scanner", "osv-scanner": "osv-scanner", "gitleaks": "gitleaks"}
PLUGIN_SOURCES = {"ponytail": "ponytail", "i-have-adhd": "i-have-adhd", "claude-seo": "claude-seo",
                  "claude-blog": "claude-blog"}
CLAUDE_PLUGINS = {"omc-plugin": "oh-my-claudecode@omc", "last30days": "last30days@last30days-skill"}


def plugin_src_dir(name):
    if sys.platform.startswith("linux"):
        return "/opt/agent-plugins/" + name
    return os.path.expanduser("~/.local/share/ai/plugins/" + name)


def cmd_version(binary):
    import shutil
    if not shutil.which(binary):
        return ""
    try:
        res = subprocess.run([binary, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = VERSION_RE.search(res.stdout.decode("utf-8", "replace"))
    return m.group(1) if m else ""


def git_head(path):
    try:
        with open(os.path.join(path, ".git", "HEAD")) as fh:
            head = fh.read().strip()
    except OSError:
        return ""
    return head if re.fullmatch(r"[0-9a-f]{40}", head) else ""


def npm_dir_versions(base, name):
    out = []
    try:
        for d in os.listdir(base):
            m = re.fullmatch(re.escape(name) + r"-(\d+(?:\.\d+)*)", d)
            if m:
                out.append(m.group(1))
    except OSError:
        pass
    return sorted(out, key=lambda v: tuple(int(x) for x in v.split(".")))


def installed(tool):
    """(version, sha) of what is on this machine, or ("", "") when not found."""
    if tool in BINARIES:
        return cmd_version(BINARIES[tool]), ""
    npm = os.path.expanduser("~/.local/share/ai/npm")
    if tool == "context7-mcp":
        v = npm_dir_versions(npm, "context7-mcp")
        return (v[-1] if v else ""), ""
    if tool == "playwright-mcp":
        v = npm_dir_versions(npm, "playwright-mcp")
        return (v[-1] if v else ""), ""
    if tool in PLUGIN_SOURCES:
        sha = git_head(plugin_src_dir(PLUGIN_SOURCES[tool]))
        return "", sha
    if tool == "mattpocock-skills":
        try:
            with open(os.path.join(plugin_src_dir("mattpocock-skills"), ".commit")) as fh:
                return "", fh.read().strip()
        except OSError:
            return "", ""
    if tool in CLAUDE_PLUGINS:
        cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
        try:
            with open(os.path.join(cfg, "plugins", "installed_plugins.json")) as fh:
                rows = (json.load(fh).get("plugins") or {}).get(CLAUDE_PLUGINS[tool]) or []
        except (OSError, ValueError):
            rows = []
        if rows:
            return rows[0].get("version") or "", rows[0].get("gitCommitSha") or ""
    return "", ""


def status(network=False):
    """[{tool, installed, installed_sha, newest, newest_sha, state, note}] for every tool found on this machine.
    state: current | update | hold | unknown."""
    specs = tools()
    system = os.path.join(os.environ.get("AI_SYSTEM_STATE_DIR") or "/var/lib/ai", "resolved.json")
    states = [load_state(), load_state(system)]
    rows = []
    for tool in sorted(specs):
        ver, sha = installed(tool)
        if not ver and not sha:
            for st in states:
                inst = (st["tools"].get(tool) or {}).get("installed") or {}
                if inst.get("version"):
                    ver, sha = inst["version"], inst.get("sha", "")
                    break
        if not ver and not sha:
            continue
        if network:
            r = resolve(tool, write=False, specs=specs)
        else:
            cached = {}
            for st in states:
                cached = (st["tools"].get(tool) or {}).get("newest") or {}
                if cached.get("version"):
                    break
            r = {"version": cached.get("version", ""), "sha": cached.get("sha", ""),
                 "status": "cached" if cached.get("version") else "none", "note": "from resolved.json"}
        row = {"tool": tool, "installed": ver, "installed_sha": sha, "newest": r.get("version", ""),
               "newest_sha": r.get("sha", ""), "note": r.get("note", ""), "hold": specs[tool]["hold"]}
        if not row["newest"]:
            row["state"] = "unknown"
        elif (sha and row["newest_sha"] and sha == row["newest_sha"]) or (ver and same_version(ver, row["newest"])):
            row["state"] = "hold" if specs[tool]["hold"] else "current"
        else:
            row["state"] = "update"
        rows.append(row)
    return rows


# ---------------------------------------------------------------- command line

def shell_lines(out):
    return "\n".join("R_%s=%s" % (k.upper(), shlex.quote(out.get(k) or "")) for k in FIELDS)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    write = "--no-write" not in rest
    rest = [a for a in rest if a != "--no-write"]
    if cmd in ("shell", "json") and rest:
        out = resolve(rest[0], write=write)
        print(shell_lines(out) if cmd == "shell" else json.dumps(out, sort_keys=True))
        return 0
    if cmd == "list":
        if "--offline" in rest:
            os.environ["AI_RESOLVE_OFFLINE"] = "1"
        specs = tools()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda t: (t, safe_resolve(t, specs)), sorted(specs)))
        memo_path = os.environ.get("AI_RESOLVE_MEMO")
        if memo_path:
            try:
                with open(memo_path, "w") as fh:
                    json.dump(dict(results), fh)
            except OSError:
                pass
        if write:
            data = load_state()
            for t, r in results:
                if r["status"] in ("new", "hold"):
                    entry = data["tools"].setdefault(t, {})
                    entry["source"] = r["source"]
                    entry["newest"] = dict({k: r[k] for k in ("version", "ref", "sha", "integrity", "checksums")},
                                           time=now(), hold=r["status"] == "hold")
            save_state(data)
        for t, r in results:
            ver = r["version"] or "?"
            extra = (" " + r["ref"]) if r["ref"] and r["ref"].lstrip("v") != ver else ""
            sha = (" " + r["sha"][:12]) if r["sha"] else ""
            print("%-20s %-12s %-8s %s%s%s%s" % (t, ver, r["status"], r["source"], extra, sha,
                                                 ("  (" + r["note"] + ")") if r["note"] else ""))
        return 0
    if cmd == "record" and rest:
        opts = {"--version": "", "--sha": "", "--integrity": ""}
        i = 1
        while i < len(rest):
            if rest[i] in opts and i + 1 < len(rest):
                opts[rest[i]] = rest[i + 1]
                i += 2
            else:
                i += 1
        record(rest[0], opts["--version"], opts["--sha"], opts["--integrity"])
        return 0
    if cmd == "reject" and rest:
        opts = {"--version": "", "--sha": "", "--findings": ""}
        i = 1
        while i < len(rest):
            if rest[i] in opts and i + 1 < len(rest):
                opts[rest[i]] = rest[i + 1]
                i += 2
            else:
                i += 1
        reject(rest[0], opts["--version"], opts["--sha"], opts["--findings"])
        return 0
    if cmd == "candidates" and rest:
        limit = int(rest[rest.index("--max") + 1]) if "--max" in rest else 5
        below = rest[rest.index("--below") + 1] if "--below" in rest else ""
        try:
            for row in candidates(rest[0], below, limit):
                print("%s %s %s" % row)
        except Unavailable as exc:
            print("resolve.py: %s" % exc, file=sys.stderr)
            return 1
        return 0
    if cmd == "installed-info" and rest:
        print("\n".join("%s=%s" % (k, shlex.quote(v)) for k, v in installed_info(rest[0]).items()))
        return 0
    if cmd == "checksum" and len(rest) >= 3:
        target = rest[rest.index("--target") + 1] if "--target" in rest and rest.index("--target") + 1 < len(rest) else ""
        try:
            print(checksum(rest[0], rest[1], rest[2], target))
        except Unavailable as exc:
            print("resolve.py: %s" % exc, file=sys.stderr)
            return 1
        return 0
    if cmd == "verify-npm" and len(rest) >= 3:
        ok, msg = verify_npm(rest[0], rest[1], rest[2], rest[3] if len(rest) > 3 else "")
        print(msg)
        return 0 if ok else 1
    if cmd == "status":
        print(json.dumps(status(network="--network" in rest), indent=1, sort_keys=True))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
