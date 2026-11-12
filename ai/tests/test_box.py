#!/usr/bin/env python3
"""Offline tests for the box MCP server (ai-core mcp/box.py): MCP handshake, tools only where proj-agent
exists, the argv each tool sends, the socket wire format, the sudo fallback, output limits, bad input.
A fake root socket service (same wire format as the ubuntu-server branch proj-agent-socket) runs in a thread."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
BOX = os.path.join(os.path.dirname(HERE), "marketplace", "plugins", "ai-core", "mcp", "box.py")


class FakeService:
    """Answers one request per connection: records the argv, streams canned frames."""

    def __init__(self, path):
        self.path, self.seen, self.reply = path, [], None
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)
        self.srv.listen(8)
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                req = json.loads(buf.split(b"\n", 1)[0])
                self.seen.append(req)
                out, err, rc = self.reply(req["argv"]) if self.reply else (b"ok\n", b"", 0)
                for i in range(0, len(out), 1000):
                    part = out[i:i + 1000]
                    conn.sendall(b"O%d\n" % len(part) + part)
                if err:
                    conn.sendall(b"E%d\n" % len(err) + err)
                conn.sendall(b"X%d\n" % rc)


def session(env, msgs):
    """Run box.py over stdio with these JSON-RPC messages; return the replies by id."""
    data = "".join(json.dumps(m) + "\n" for m in msgs).encode()
    res = subprocess.run([sys.executable, "-I", BOX], input=data, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, timeout=60)
    assert res.returncode == 0, res.stderr
    out = {}
    for line in res.stdout.decode().splitlines():
        r = json.loads(line)
        out[r.get("id")] = r
    return out


def call(env, name, args):
    r = session(env, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}])
    return r[1]


def text(r):
    return r["result"]["content"][0]["text"]


def main():
    tmp = tempfile.mkdtemp(prefix="ai-box-", dir="/tmp")      # short path: AF_UNIX names are limited
    sock = os.path.join(tmp, "s")
    agent = os.path.join(tmp, "proj-agent")
    base = {"PATH": "/usr/bin:/bin", "AI_BOX_TEST": "1", "AI_BOX_SOCK": sock, "AI_BOX_AGENT": agent,
            "AI_BOX_SUDO": os.path.join(tmp, "nosudo")}
    failures = []

    def check(label, cond, detail=""):
        print(("ok   " if cond else "FAIL ") + label + ("" if cond else "\n     " + str(detail)[:600]))
        if not cond:
            failures.append(label)

    # 1. No proj-agent here: handshake works, no tools (no context cost on a Mac).
    r = session(base, [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
                       {"jsonrpc": "2.0", "method": "notifications/initialized"},
                       {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                       {"jsonrpc": "2.0", "id": 3, "method": "ping"},
                       {"jsonrpc": "2.0", "id": 4, "method": "nope"}])
    check("initialize answers with tools capability", r[1]["result"]["capabilities"] == {"tools": {}}, r[1])
    check("no proj-agent: no tools", r[2]["result"]["tools"] == [], r[2])
    check("ping and unknown method", r[3]["result"] == {} and r[4]["error"]["code"] == -32601, r)
    check("notifications get no reply", None not in r and len(r) == 4, r)

    svc = FakeService(sock)
    # 2. Socket present: the tools, each with the argv proj-agent expects.
    r = session(base, [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
    names = sorted(t["name"] for t in r[1]["result"]["tools"])
    check("tools listed", names == sorted(["list", "new", "exec", "logs", "status", "restart", "ports", "url",
                                           "snapshot", "doctor", "help"]), names)
    check("read-only tools are marked", all(t["annotations"]["readOnlyHint"] == (t["name"] in (
        "list", "logs", "status", "ports", "url", "doctor", "help")) for t in r[1]["result"]["tools"]))
    cases = [
        ("list", {}, ["list"]),
        ("new", {"name": "web", "tier": "mvp", "pg": True}, ["new", "web", "--tier", "mvp", "--pg"]),
        ("exec", {"box": "web", "command": "npm ci && npm test", "timeout": 1200},
         ["exec", "web", "--timeout", "1200", "--", "npm ci && npm test"]),
        ("exec", {"box": "web", "argv": ["echo", "a b", "$HOME"], "cwd": "/srv/app/x"},
         ["exec", "web", "--cwd", "/srv/app/x", "--", "echo 'a b' '$HOME'"]),
        ("logs", {"box": "web", "lines": 50}, ["logs", "box", "web", "-n", "50"]),
        ("logs", {"unit": "nginx"}, ["logs", "nginx"]),
        ("status", {"unit": "proj-agent.socket"}, ["status", "proj-agent.socket"]),
        ("restart", {"box": "web", "service": "app"}, ["restart", "web", "app"]),
        ("url", {"box": "web", "port": 8080}, ["url", "web", "8080"]),
        ("ports", {"box": "web"}, ["ports", "web"]),
        ("snapshot", {"name": "web"}, ["snapshot", "web"]),
    ]
    for name, args, want in cases:
        svc.seen.clear()
        res = call(base, name, args)
        got = svc.seen[-1]["argv"] if svc.seen else None
        check("%s %s -> %s" % (name, args, want), got == want and not res["result"]["isError"]
              and text(res).startswith("exit code 0"), (got, res))
    check("request carries v=1", all(req.get("v") == 1 for req in svc.seen))

    # 3. Bad input never reaches the service.
    svc.seen.clear()
    for name, args in (("exec", {"box": "web"}), ("exec", {"box": "web", "command": "x", "argv": ["y"]}),
                       ("exec", {"box": "web", "command": "x", "timeout": 9999}), ("new", {"name": "x", "tier": "long"}),
                       ("logs", {}), ("status", {})):
        res = call(base, name, args)
        check("refused locally: %s %s" % (name, args), res["result"]["isError"], res)
    check("nothing sent for bad input", svc.seen == [], svc.seen)
    res = session(base, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "rm", "arguments": {}}}])
    check("unknown tool is an error", res[1].get("error", {}).get("code") == -32602, res)

    # 4. Exit code, stderr and the output cut.
    svc.reply = lambda argv: (b"A" * 100000 + b"END", b"proj-agent: refused: nope\n", 2)
    res = call(base, "list", {})
    t = text(res)
    check("non-zero exit is an error with stderr", res["result"]["isError"] and t.startswith("exit code 2")
          and "refused: nope" in t, t[:200])
    check("long output is cut, head and tail kept", "characters cut" in t and t.count("A") < 45000 and "END" in t)
    svc.reply = None

    # 5. Socket gone, proj-agent present: the sudo fallback (absolute sudo, -n, absolute agent).
    svc.srv.close()
    os.unlink(sock)
    with open(agent, "w") as f:
        f.write("#!/bin/sh\n")
    os.chmod(agent, 0o755)
    fake_sudo = os.path.join(tmp, "sudo")
    with open(fake_sudo, "w") as f:
        f.write('#!/bin/sh\necho "sudo $*"\n')
    os.chmod(fake_sudo, 0o755)
    res = call(dict(base, AI_BOX_SUDO=fake_sudo), "list", {})
    check("fallback: sudo -n /path/proj-agent list", text(res) == "exit code 0\nsudo -n %s list" % agent, text(res))
    res = call(base, "list", {})
    check("fallback without sudo: clear error", res["result"]["isError"] and "cannot run" in text(res), text(res))

    print("%d box tests failed" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
