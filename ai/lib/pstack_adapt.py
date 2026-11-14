#!/usr/bin/env python3
"""pstack_adapt: our copies of the pstack verification skills, made from the upstream tree by a fixed transform.

  python3 ai/lib/pstack_adapt.py <pstack dir> <out dir> <commit> [--vendor]

<pstack dir> is the `pstack/` folder of github.com/cursor/plugins (or ai/rules/vendor/pstack-verification/).
Writes <out>/create-verification-skill/ and <out>/maintain-verification-skill/ (SKILL.md, references, LICENSE).
--vendor writes the vendor copy instead: the same files byte for byte, except U+2014 (em dash) becomes " - "
(repo rule), plus SOURCE.md.

The adapted copy changes only what must change here (SPEC 25):
  - the project skill path `.cursor/skills/` becomes `.agents/skills/` (Codex reads project skills there;
    ai-adopt links .claude/skills/verify-<app> to it for Claude);
  - one attribution and path note after the frontmatter;
  - Romanian and Russian trigger phrases at the end of the description (docs/EXTENDING.md section 1);
  - U+2014 becomes " - ".
The installer (tools.sh pstack_src) runs the same transform on a newer upstream commit, after its audit.
"""
import os
import re
import shutil
import sys

SKILLS = ("create-verification-skill", "maintain-verification-skill")
EM = "—"
TRIGGERS = {
    "create-verification-skill": ' RO: "creeaza skill-ul de verificare pentru proiect". RU: "создай навык проверки для проекта".',
    "maintain-verification-skill": ' RO: "actualizeaza skill-ul de verificare". RU: "обнови навык проверки".',
}
NOTE = ("> Adapted from pstack (MIT, Copyright (c) 2026 Lauren Tan; LICENSE in this folder), github.com/cursor/plugins "
        "commit %s. Change here: project skills live in `.agents/skills/verify-<app>/` (Codex reads them there); "
        "`ai-adopt` adds the committed link `.claude/skills/verify-<app>` -> `../../.agents/skills/verify-<app>` for "
        "Claude.\n")


def dash(text):
    return text.replace(" " + EM + " ", " - ").replace(EM, " - ")


def adapt_skill(text, name, commit):
    text = dash(text).replace(".cursor/skills/", ".agents/skills/")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit("pstack_adapt: %s has no frontmatter" % name)
    front = m.group(1)
    front = re.sub(r'^(description: ".*?)("\s*)$', lambda d: d.group(1) + TRIGGERS[name].replace('"', '\\"') + d.group(2),
                   front, count=1, flags=re.M)
    return "---\n%s\n---\n\n%s%s" % (front, NOTE % commit, text[m.end():])


def copy_tree(src, dst, fn):
    for dirpath, _dirs, files in os.walk(src):
        for f in sorted(files):
            s = os.path.join(dirpath, f)
            d = os.path.join(dst, os.path.relpath(s, src))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            with open(s, encoding="utf-8") as fh:
                text = fh.read()
            with open(d, "w", encoding="utf-8") as fh:
                fh.write(fn(os.path.relpath(s, src), text))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, out, commit = argv[0], argv[1], argv[2]
    vendor = "--vendor" in argv
    skills_root = os.path.join(src, "skills") if os.path.isdir(os.path.join(src, "skills")) else src
    lic = os.path.join(src, "LICENSE")
    if not os.path.isfile(lic):
        raise SystemExit("pstack_adapt: no LICENSE in %s" % src)
    for name in SKILLS:
        s = os.path.join(skills_root, name)
        if not os.path.isfile(os.path.join(s, "SKILL.md")):
            raise SystemExit("pstack_adapt: %s/SKILL.md missing" % s)
        d = os.path.join(out, "skills", name) if vendor else os.path.join(out, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        if vendor:
            copy_tree(s, d, lambda _rel, t: dash(t))
        else:
            copy_tree(s, d, lambda rel, t, n=name: adapt_skill(t, n, commit) if rel == "SKILL.md" else dash(t))
            shutil.copyfile(lic, os.path.join(d, "LICENSE"))
    if vendor:
        shutil.copyfile(lic, os.path.join(out, "LICENSE"))
        with open(os.path.join(out, "SOURCE.md"), "w", encoding="utf-8") as fh:
            fh.write("# pstack verification skills, vendor copy\n\n"
                     "source: https://github.com/cursor/plugins (folder pstack/, plugin version 0.15.36)\n"
                     "commit: %s\n"
                     "license: MIT, Copyright (c) 2026 Lauren Tan (LICENSE here, unchanged)\n"
                     "files: skills/create-verification-skill/ (SKILL.md, references/feature-map-example/),\n"
                     "       skills/maintain-verification-skill/SKILL.md\n"
                     "deviation: every U+2014 (em dash) became \" - \" (repo rule). No other change.\n"
                     "our copy: ai/skills/<name>/ = python3 ai/lib/pstack_adapt.py ai/rules/vendor/pstack-verification "
                     "ai/skills %s\n" % (commit, commit))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
