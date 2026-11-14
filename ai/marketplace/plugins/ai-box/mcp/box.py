#!/usr/bin/python3 -I
"""box: MCP server (stdio) for proj-agent, the box tool of a server install. Python standard library only.

Why: agents must not get unix sockets inside their sandbox (Claude's sandbox keeps them blocked; one open
socket on a host can be a database superuser or a tmux session). MCP servers run OUTSIDE the agent's
sandbox, as the user. This server talks to the root socket service /run/proj-agent.sock (ubuntu-server
branch, files/sbin/proj-agent-socket: one JSON request {"v": 1, "argv": [...]}, frames O<n>/E<n> with
stdout/stderr, X<code> at the end). Where the socket is missing it falls back to
`/usr/bin/sudo -n /usr/local/sbin/proj-agent` (works only where sudo is allowed and not in a sandbox).
proj-agent itself is the allow-list: it checks every argument and refuses anything off its menu.

No proj-agent on this machine (a Mac, a desktop): the server lists no tools, so it costs no context.
Output is cut to MAX_OUT characters per stream (head and tail kept). exec runs up to 3600 s; the MCP
client timeout is set by install.sh (Claude: "timeout" in .mcp.json, Codex: tool_timeout_sec).
"""
import json
import os
import shlex
import socket
import subprocess
import sys

SOCK = "/run/proj-agent.sock"
AGENT = "/usr/local/sbin/proj-agent"
SUDO = "/usr/bin/sudo"
if os.environ.get("AI_BOX_TEST") == "1":      # offline tests only: fake socket and agent
    SOCK = os.environ.get("AI_BOX_SOCK", SOCK)
    AGENT = os.environ.get("AI_BOX_AGENT", AGENT)
    SUDO = os.environ.get("AI_BOX_SUDO", SUDO)
MAX_OUT = 40000
MAX_TIMEOUT = 3600
PROTOCOL = "2025-06-18"

NAME = {"type": "string", "description": "box name"}
RO = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
RW = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}


def tool(name, desc, props=None, required=(), ann=RO):
    return {"name": name, "description": desc, "annotations": ann,
            "inputSchema": {"type": "object", "properties": props or {}, "required": list(required),
                            "additionalProperties": False}}


TOOLS = [
    tool("list", "All boxes and host projects."),
    tool("new", "Make a new box (an isolated container with its own workspace). Tier long: ask the owner.",
         {"name": {"type": "string", "description": "lower case letters, digits, -; 2 to 31 chars"},
          "tier": {"type": "string", "enum": ["try", "mvp"], "description": "try = short-lived, mvp = stays up"},
          "docker": {"type": "boolean"}, "pg": {"type": "boolean", "description": "with Postgres"}},
         ("name", "tier"), RW),
    tool("exec", "Run a command INSIDE a box as user dev (never root), in /srv/app by default. Pipes, && and "
                 "redirects work: they run in the box. Give `command` (a bash string) or `argv` (a list).",
         {"box": NAME, "command": {"type": "string", "description": "run by bash -lc in the box"},
          "argv": {"type": "array", "items": {"type": "string"}, "description": "one program and its arguments"},
          "cwd": {"type": "string", "description": "absolute folder in the box (default /srv/app)"},
          "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT, "description": "seconds, default 600"}},
         ("box",), RW),
    tool("logs", "Journal lines: of a box (box) or of one host unit (unit).",
         {"box": NAME, "unit": {"type": "string"}, "lines": {"type": "integer", "minimum": 1, "maximum": 2000}}),
    tool("status", "systemctl status of one host unit (read only).", {"unit": {"type": "string"}}, ("unit",)),
    tool("restart", "Restart a systemd service INSIDE a box (never a host unit).",
         {"box": NAME, "service": {"type": "string"}}, ("box", "service"), RW),
    tool("ports", "Listening ports inside a box.", {"box": NAME}, ("box",)),
    tool("url", "How to reach a service in a box from this host (box IP:port).",
         {"box": NAME, "port": {"type": "integer", "minimum": 1, "maximum": 65535}}, ("box",)),
    tool("snapshot", "Snapshot a box, its data volume and its workspace.", {"name": NAME}, ("name",), RW),
    tool("doctor", "proj health checks (no network test, no box is made)."),
    tool("help", "The proj-agent menu."),
]


def available():
    return os.path.exists(SOCK) or os.path.exists(AGENT)


def argv_for(name, a):
    """The proj-agent argv for one tool call, or raise ValueError with a short reason."""
    def need(k):
        v = a.get(k)
        if v in (None, ""):
            raise ValueError("%s is required" % k)
        return str(v)
    if name in ("list", "doctor", "help"):
        return [name]
    if name == "new":
        tier = need("tier")
        if tier not in ("try", "mvp"):
            raise ValueError("tier must be try or mvp (long: ask the owner)")
        out = ["new", need("name"), "--tier", tier]
        out += ["--docker"] if a.get("docker") else []
        out += ["--pg"] if a.get("pg") else []
        return out
    if name == "exec":
        out = ["exec", need("box")]
        if a.get("cwd"):
            out += ["--cwd", str(a["cwd"])]
        if a.get("timeout") is not None:
            t = int(a["timeout"])
            if not 1 <= t <= MAX_TIMEOUT:
                raise ValueError("timeout must be 1 to %d seconds" % MAX_TIMEOUT)
            out += ["--timeout", str(t)]
        cmd, argv = a.get("command"), a.get("argv")
        if bool(cmd) == bool(argv):
            raise ValueError("give exactly one of command (a bash string) or argv (a list)")
        if argv:
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                raise ValueError("argv must be a list of strings")
            cmd = shlex.join(argv)
        return out + ["--", str(cmd)]
    if name == "logs":
        if bool(a.get("box")) == bool(a.get("unit")):
            raise ValueError("give exactly one of box or unit")
        out = ["logs", "box", str(a["box"])] if a.get("box") else ["logs", str(a["unit"])]
        return out + (["-n", str(int(a["lines"]))] if a.get("lines") else [])
    if name == "status":
        return ["status", need("unit")]
    if name == "restart":
        return ["restart", need("box"), need("service")]
    if name == "ports":
        return ["ports", need("box")]
    if name == "url":
        return ["url", need("box")] + ([str(int(a["port"]))] if a.get("port") else [])
    if name == "snapshot":
        return ["snapshot", need("name")]
    raise ValueError("unknown tool %s" % name)


def via_socket(argv, wait):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(wait)
    s.connect(SOCK)
    try:
        s.sendall(json.dumps({"v": 1, "argv": argv}).encode("utf-8") + b"\n")
        f = s.makefile("rb")
        out = {b"O": bytearray(), b"E": bytearray()}
        while True:
            head = f.readline()
            if not head:
                return 255, bytes(out[b"O"]), bytes(out[b"E"]) + b"\nbox: the connection ended without an exit code"
            kind, num = head[:1], head[1:].strip()
            if kind == b"X" and num.lstrip(b"-").isdigit():
                return int(num), bytes(out[b"O"]), bytes(out[b"E"])
            if kind not in out or not num.isdigit():
                return 255, bytes(out[b"O"]), bytes(out[b"E"]) + b"\nbox: bad answer from the service"
            out[kind] += f.read(int(num))
            for k in out:      # keep memory bounded: head and tail survive the cut below
                if len(out[k]) > 8 * MAX_OUT:
                    out[k] = out[k][:MAX_OUT] + out[k][-4 * MAX_OUT:]
    finally:
        s.close()


def via_sudo(argv, wait):
    res = subprocess.run([SUDO, "-n", AGENT] + argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, timeout=wait, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"})
    return res.returncode, res.stdout, res.stderr


def cut(b):
    t = b.decode("utf-8", "replace")
    if len(t) <= MAX_OUT:
        return t
    head = MAX_OUT // 4
    return t[:head] + "\n[... %d characters cut ...]\n" % (len(t) - MAX_OUT) + t[-(MAX_OUT - head):]


def run(argv, wait):
    if os.path.exists(SOCK):
        try:
            return via_socket(argv, wait)
        except socket.timeout:
            return 124, b"", b"box: no answer within %d s" % wait
        except OSError as e:
            if not os.path.exists(AGENT):
                return 1, b"", ("box: cannot reach %s (%s). Is proj-agent.socket running? Is this user in "
                                "the agents' group (log in again after joining)?" % (SOCK, e.strerror)).encode()
    if os.path.exists(AGENT):
        try:
            return via_sudo(argv, wait)
        except subprocess.TimeoutExpired:
            return 124, b"", b"box: no answer within %d s" % wait
        except OSError as e:
            return 1, b"", ("box: cannot run %s: %s" % (SUDO, e)).encode()
    return 1, b"", b"box: no proj-agent on this machine (server installs only)"


def call_tool(name, a):
    try:
        argv = argv_for(name, a or {})
    except (ValueError, TypeError) as e:
        return {"content": [{"type": "text", "text": "box %s: %s" % (name, e)}], "isError": True}
    wait = (int(a.get("timeout") or 600) + 120) if name == "exec" else 900
    rc, out, err = run(argv, wait)
    parts = ["exit code %d" % rc]
    if out:
        parts.append(cut(out).rstrip("\n"))
    if err:
        parts.append("--- stderr ---\n" + cut(err).rstrip("\n"))
    return {"content": [{"type": "text", "text": "\n".join(parts)}], "isError": rc != 0}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None                       # notifications (initialized, cancelled): nothing to answer
    if method == "initialize":
        want = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        result = {"protocolVersion": want, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "box", "version": "1.0.0"}}
        if available():
            result["instructions"] = ("Boxes: isolated containers for projects on this server. Make one with "
                                      "new, work in it with exec; the code is the box workspace.")
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS if available() else []}
    elif method == "tools/call":
        p = msg.get("params") or {}
        if not available() or p.get("name") not in {t["name"] for t in TOOLS}:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool"}}
        result = call_tool(p["name"], p.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
