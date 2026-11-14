"""minitoml: a small TOML reader for python 3.9 (/usr/bin/python3 on macOS has no tomllib).

loads(text) -> dict. Enough for pyproject.toml, uv.lock, poetry.lock, Cargo.toml/.lock, uv.toml and
.cargo/config.toml: [table], [a.b."c"], [[array.of.tables]], dotted keys, basic and literal strings (also
triple-quoted), integers, floats, booleans, dates as strings, arrays (also multi-line, nested), inline tables.
Raises ValueError on text it cannot read. Callers use tomllib when it exists and this only as the fallback.
"""
import re

_BARE = re.compile(r"[A-Za-z0-9_-]+")


def loads(text):
    root = {}
    cur = root
    s = _Src(text)
    while True:
        s.skip_ws_comments()
        if s.eof():
            return root
        if s.peek(2) == "[[":
            s.pos += 2
            keys = s.keys("]]")
            parent = _walk(root, keys[:-1])
            arr = parent.setdefault(keys[-1], [])
            if not isinstance(arr, list):
                raise ValueError("not an array of tables: %s" % ".".join(keys))
            cur = {}
            arr.append(cur)
        elif s.peek() == "[":
            s.pos += 1
            cur = _walk(root, s.keys("]"))
        else:
            keys = s.keys("=")
            s.skip_inline_ws()
            target = _walk(cur, keys[:-1])
            target[keys[-1]] = s.value()
        s.end_of_line()


def _walk(d, keys):
    for k in keys:
        nxt = d.setdefault(k, {})
        if isinstance(nxt, list):
            if not nxt:
                nxt.append({})
            nxt = nxt[-1]
        if not isinstance(nxt, dict):
            raise ValueError("key %s is not a table" % k)
        d = nxt
    return d


class _Src(object):
    def __init__(self, text):
        self.t = text
        self.pos = 0

    def eof(self):
        return self.pos >= len(self.t)

    def peek(self, n=1):
        return self.t[self.pos:self.pos + n]

    def skip_inline_ws(self):
        while not self.eof() and self.t[self.pos] in " \t":
            self.pos += 1

    def skip_ws_comments(self):
        while not self.eof():
            c = self.t[self.pos]
            if c in " \t\r\n":
                self.pos += 1
            elif c == "#":
                nl = self.t.find("\n", self.pos)
                self.pos = len(self.t) if nl < 0 else nl
            else:
                return

    def end_of_line(self):
        self.skip_inline_ws()
        if self.peek() == "#":
            nl = self.t.find("\n", self.pos)
            self.pos = len(self.t) if nl < 0 else nl
        self.skip_inline_ws()
        if not self.eof() and self.peek() not in "\r\n":
            raise ValueError("junk after a value at %d" % self.pos)

    def keys(self, end):
        out = []
        while True:
            self.skip_inline_ws()
            if self.peek() in ('"', "'"):
                out.append(self.string())
            else:
                m = _BARE.match(self.t, self.pos)
                if not m:
                    raise ValueError("bad key at %d" % self.pos)
                out.append(m.group(0))
                self.pos = m.end()
            self.skip_inline_ws()
            if self.peek() == ".":
                self.pos += 1
                continue
            if self.peek(len(end)) != end:
                raise ValueError("expected %r at %d" % (end, self.pos))
            self.pos += len(end)
            return out

    def string(self):
        q = self.peek()
        if self.peek(3) == q * 3:
            self.pos += 3
            end = self.t.find(q * 3, self.pos)
            if end < 0:
                raise ValueError("open string")
            raw = self.t[self.pos:end]
            self.pos = end + 3
            raw = raw[1:] if raw.startswith("\n") else raw
            return _unescape(raw) if q == '"' else raw
        self.pos += 1
        if q == "'":
            end = self.t.find("'", self.pos)
            if end < 0:
                raise ValueError("open string")
            raw = self.t[self.pos:end]
            self.pos = end + 1
            return raw
        buf = []
        while not self.eof():
            c = self.t[self.pos]
            if c == "\\":
                buf.append(self.t[self.pos:self.pos + 2])
                self.pos += 2
                continue
            if c == '"':
                self.pos += 1
                return _unescape("".join(buf))
            buf.append(c)
            self.pos += 1
        raise ValueError("open string")

    def value(self):
        c = self.peek()
        if c in ('"', "'"):
            return self.string()
        if c == "[":
            self.pos += 1
            out = []
            while True:
                self.skip_ws_comments()
                if self.peek() == "]":
                    self.pos += 1
                    return out
                out.append(self.value())
                self.skip_ws_comments()
                if self.peek() == ",":
                    self.pos += 1
        if c == "{":
            self.pos += 1
            out = {}
            while True:
                self.skip_inline_ws()
                if self.peek() == "}":
                    self.pos += 1
                    return out
                keys = self.keys("=")
                self.skip_inline_ws()
                _walk(out, keys[:-1])[keys[-1]] = self.value()
                self.skip_inline_ws()
                if self.peek() == ",":
                    self.pos += 1
        m = re.compile(r"[^\s,\]}#]+").match(self.t, self.pos)
        if not m:
            raise ValueError("bad value at %d" % self.pos)
        self.pos = m.end()
        word = m.group(0)
        if word in ("true", "false"):
            return word == "true"
        w = word.replace("_", "")
        try:
            if re.match(r"^[+-]?0[xob]", w):
                return int(w, 0)
            if re.match(r"^[+-]?\d+$", w):
                return int(w)
            return float(w)
        except ValueError:
            return word         # dates, times, inf/nan words stay strings


_ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "b": "\b", "f": "\f"}


def _unescape(s):
    def one(m):
        g = m.group(1)
        if g[0] in "uU" and len(g) > 1:
            return chr(int(g[1:], 16))
        return _ESC.get(g, g)
    return re.sub(r"\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)", one, s)
