"""ai/lib/ai_profile.py: which profile this machine runs (owner decision 2026-11-14). Python 3.9, stdlib only.

Order: AI_PROFILE (install.sh exports it for what it runs) > ~/.config/ai/profile > OS default
(Linux: server, macOS: dev-mac). Each profile is ai/profiles/<name>.env (KEY=VALUE, shell syntax).
"""
import os
import sys

AI_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def profile_file(home=None):
    return os.environ.get("AI_PROFILE_FILE") or os.path.join(home or os.path.expanduser("~"), ".config", "ai", "profile")


def resolve(home=None, os_name=None):
    """(name, source): source is env, file or default. An unknown name is returned as it is (load() fails)."""
    name = (os.environ.get("AI_PROFILE") or "").strip()
    if name:
        return name, "env"
    try:
        with open(profile_file(home)) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line, "file"
    except OSError:
        pass
    os_name = os_name or os.environ.get("AI_OS_FORCE") or ("macos" if sys.platform == "darwin" else "linux")
    return ("dev-mac" if os_name in ("macos", "Darwin") else "server"), "default"


def names():
    try:
        return sorted(n[:-4] for n in os.listdir(os.path.join(AI_DIR, "profiles")) if n.endswith(".env"))
    except OSError:
        return []


def load(name):
    """The KEY=VALUE pairs of ai/profiles/<name>.env (quotes and trailing comments dropped). ValueError if unknown."""
    if name not in names():
        raise ValueError("unknown profile %r (known: %s)" % (name, ", ".join(names())))
    out = {}
    with open(os.path.join(AI_DIR, "profiles", name + ".env")) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip()
            if val[:1] in "\"'":
                val = val[1:val.index(val[0], 1)]
            else:
                val = val.split("#", 1)[0].strip()
            out[key.strip()] = val
    return out
