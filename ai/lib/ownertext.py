"""Owner text: the lines outside the managed AI blocks, and the lines an owner added inside one (owner decision
2026-11-17). A setup update only adds. `merge` keeps the owner's lines inside a block, `lost` tells a writer to
refuse (write nothing) when the owner text would change. Used by ai-start, ai-check-detect, aiconf and ai-doctor."""
import difflib
import re

# <!-- AI:<name> ... START ... --> to the nearest END of the same name ("# " before them in a shell file).
# An inner line may not be a marker of the same name: a START without its END is owner text, not a block.
HTML_RX = re.compile(r"^(?:# )?<!-- AI:([\w.-]+)\b[^>]*\bSTART\b[^>]*-->[ \t]*\n"
                     r"((?:(?!(?:# )?<!-- AI:\1\b).*\n)*?)"
                     r"(?:# )?<!-- AI:\1\b[^>]*\bEND\b[^>]*-->[ \t]*$", re.M)
# Line markers: the .gitignore block (ai-start) and the Makefile / justfile block (ai-check-detect).
LINE_PAIRS = (("# >>> AI tools ", "# <<< AI tools <<<"), ("# >>> ai checks ", "# <<< ai checks <<<"))
# Generator lines of files without markers: .ai/enabled has a comment head, the tier and the skills line.
GENERATED = {".ai/enabled": (r"^# ai-adopt:", r"^\s*tier\s*:", r"^\s*skills\s*:")}
CUSTOM_HINT = "custom line inside an AI block: move it under ## Project rules"


def blocks(text):
    """[(name, start, end, inner lines)] of the managed blocks, in file order."""
    out = [(m.group(1), m.start(), m.end(), m.group(2).splitlines()) for m in HTML_RX.finditer(text)]
    for start, end in LINE_PAIRS:
        rx = re.compile(r"^%s.*\n((?:.*\n)*?)%s[ \t]*$" % (re.escape(start), re.escape(end)), re.M)
        out += [(start, m.start(), m.end(), m.group(1).splitlines()) for m in rx.finditer(text)]
    return sorted(out, key=lambda b: b[1])


def outside(text, generated=()):
    """The non-blank lines outside the blocks, minus lines that match a `generated` regex (generator lines of a
    file without markers). Blank lines do not count: a block append may change the space around it."""
    parts, pos = [], 0
    for _n, start, end, _inner in blocks(text):
        parts.append(text[pos:start])
        pos = end
    parts.append(text[pos:])
    return [ln for ln in "".join(parts).splitlines() if ln.strip() and not any(re.match(g, ln) for g in generated)]


def key(line):
    """The generator slot of a line: a "- Label:" bullet, a numbered step, a table row's first cell, a short
    "Label: " lead; else the whole line. A new generator line replaces the old line with the same key."""
    m = re.match(r"\s*(\d+\.|- [^:`]{1,40}:|\|[^|]+\||[^:`|]{1,40}: )", line)
    return m.group(1).strip() if m else line


def merge(old, new):
    """The block lines to write: the generator's `new` lines, where an old line the owner extended (`new line` plus
    " ...") replaces its line, and every other old line that has no generator slot in `new` stays after the line
    it followed."""
    keys = {key(n) for n in new}
    out = []
    for n in new:
        ext = [o for o in old if n.strip() and o.startswith(n + " ")]
        out.append(ext[0] if ext else n)
    for i, o in enumerate(old):
        if not o.strip() or o in out or key(o) in keys:
            continue
        at = 0
        for p in reversed(old[:i]):
            hit = [j for j, x in enumerate(out) if x == p or (key(p) in keys and key(x) == key(p))]
            if hit:
                at = hit[0] + 1
                break
        out.insert(at, o)
    return out


def lost(old, new, generated=(), name="file", inside=True):
    """'' when `new` keeps the owner text of `old`; else a unified diff of the owner text that would change.
    inside=False: only the text outside the blocks counts (the global rule files: their blocks are all ours)."""
    before, after = outside(old, generated), outside(new, generated)
    rest = iter(after)
    ok = all(ln in rest for ln in before)
    now = {}
    for n, _s, _e, inner in blocks(new):
        now.setdefault(n, []).extend(inner)
    inside, kept = [], []
    for n, _s, _e, inner in blocks(old) if inside else ():
        if n not in now:
            continue     # shortcut: a block the generator drops takes its lines along; check them if that happens
        keys = {key(x) for x in now[n]}
        own = [ln for ln in inner if ln.strip() and key(ln) not in keys]
        inside += own
        kept += [ln for ln in own if ln in now[n]]
    if ok and inside == kept:
        return ""
    return "".join(difflib.unified_diff([ln + "\n" for ln in before + inside], [ln + "\n" for ln in after + kept],
                                        name, name + " (after the update)"))


def custom_lines(text):
    """[(line number, line)] inside the AGENTS.md Done block and the opt-in tool blocks that the generator does not
    write (Done: the heading and steps 1 to 6; a tool block: one line). The Map and Libraries are edited by design."""
    out = []
    for name, start, _end, inner in blocks(text):
        if name in ("map", "libraries") or name.startswith("#"):
            continue
        first = text.count("\n", 0, start) + 2
        body = [(first + i, ln) for i, ln in enumerate(inner) if ln.strip()]
        if name == "done":
            out += [(n, ln) for n, ln in body if not re.match(r"^(## Done|[1-6]\. )", ln)]
        else:
            out += body[1:]
    return out
