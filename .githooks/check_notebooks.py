#!/usr/bin/env python3
"""Pre-commit checks for research notes in _notebooks/.

Catches the problems that have previously broken the fastpages build or
needed follow-up fix commits:

  ERRORS (block the commit)
    - stray files staged (.virtual_documents, Untitled*.ipynb, checkpoints, __pycache__)
    - notebook name not YYYY-MM-DD-slug.ipynb (CI would date it by mtime -> unstable URL)
    - first cell is not the front-matter markdown cell (# title / > subtitle / categories)
    - Liquid delimiters {{ or {% in markdown/raw cells (only code cells are {% raw %}-wrapped)
    - categories changed on an already-published note (categories are part of the permalink)
    - malformed markdown links like "](]https://..."

  WARNINGS (printed, commit continues)
    - large outputs (per notebook / per cell)
    - <placeholder> text in markdown that will be swallowed as HTML
    - **** (renders as bold/garbage)
    - table cell starting with <br>
    - duplicate or empty categories, missing toc/badges

Usage:
    check_notebooks.py                 # check staged files (pre-commit mode)
    check_notebooks.py PATH [PATH...]  # check given notebooks on disk
    check_notebooks.py --all           # check every notebook on disk

Bypass a failing hook for one commit with: git commit --no-verify
"""
import json
import os
import re
import subprocess
import sys

NOTEBOOK_DIR = "_notebooks/"
NAME_RE = re.compile(r"^[12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-[^/\s]+\.ipynb$")
STRAY_RE = re.compile(r"(^|/)(\.virtual_documents|\.ipynb_checkpoints|__pycache__)/|(^|/)Untitled[^/]*\.ipynb$")
LIQUID_RE = re.compile(r"\{\{|\{%")
CATEGORIES_RE = re.compile(r"^\s*-\s*categories:\s*\[(.*)\]\s*$", re.M)
FENCE_RE = re.compile(r"^\s*(```|~~~).*?^\s*\1", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
ANGLE_RE = re.compile(r"<(/?)([A-Za-z][\w.-]*)([^<>\n]*)>")
HTML_TAGS = {
    "a", "b", "i", "u", "s", "p", "br", "hr", "em", "strong", "code", "pre", "kbd",
    "sub", "sup", "del", "ins", "mark", "small", "span", "div", "center", "font",
    "img", "video", "audio", "source", "iframe", "picture", "figure", "figcaption",
    "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tr", "td", "th",
    "details", "summary", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "style",
    "script", "svg", "path", "abbr", "cite", "q", "tt",
}

NB_OUTPUT_WARN = 500 * 1024   # total output bytes per notebook
CELL_OUTPUT_WARN = 100 * 1024  # output bytes per cell


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def staged_paths():
    r = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    if r.returncode != 0:
        sys.exit("check_notebooks: git diff failed: " + r.stderr)
    return [p for p in r.stdout.split("\0") if p]


def read_staged(path):
    r = git("show", ":" + path)
    return r.stdout if r.returncode == 0 else None


def read_head(path):
    r = git("show", "HEAD:" + path)
    return r.stdout if r.returncode == 0 else None


def src(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else s


def categories(front):
    m = CATEGORIES_RE.search(front)
    if not m:
        return None
    return [c.strip() for c in m.group(1).split(",")]


def strip_code(md):
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", md))


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def check_notebook(path, text, old_text, errors, warnings):
    def err(msg):
        errors.append(f"{path}: {msg}")

    def warn(msg):
        warnings.append(f"{path}: {msg}")

    name = os.path.basename(path)
    if not NAME_RE.match(name):
        err("filename must be YYYY-MM-DD-slug.ipynb (undated notes get an mtime date in CI, so the URL changes)")
    if " " in name:
        err("filename contains spaces")

    try:
        nb = json.loads(text)
    except ValueError as e:
        err(f"not valid JSON: {e}")
        return
    cells = nb.get("cells", [])
    if not cells:
        err("notebook has no cells")
        return

    # --- front matter -----------------------------------------------------
    # nbdev skips empty cells, so the front matter is the first non-empty cell
    fm_idx = next((i for i, c in enumerate(cells) if src(c).strip()), 0)
    if fm_idx:
        warn(f"{fm_idx} empty cell(s) before the front-matter cell; delete them")
    first = cells[fm_idx]
    front = src(first)
    if first.get("cell_type") != "markdown" or not front.strip():
        err("first cell must be the front-matter markdown cell (title / > subtitle / - categories)")
    else:
        lines = [l for l in front.splitlines() if l.strip()]
        if not lines or not lines[0].startswith("# "):
            err("front matter: first line must be '# Title'")
        if len(lines) < 2 or not lines[1].startswith("> "):
            err("front matter: second line must be '> Subtitle'")
        cats = categories(front)
        if cats is None:
            err("front matter: missing '- categories: [a,b,c]'")
        else:
            if any(c == "" for c in cats):
                warn("categories contain an empty entry (trailing/double comma)")
            dupes = sorted({c for c in cats if c and cats.count(c) > 1})
            if dupes:
                warn(f"duplicate categories: {dupes}")
            if any("." in c for c in cats):
                warn("category contains '.', use e.g. 'dotnet' instead of '.NET'")
        for key in ("toc", "badges"):
            if not re.search(rf"^\s*-\s*{key}:", front, re.M):
                warn(f"front matter: missing '- {key}: true'")

        # categories are part of the permalink: /cat1/cat2/YYYY/MM/DD/slug.html
        if old_text is not None and cats is not None:
            try:
                old_cells = json.loads(old_text).get("cells", [])
                old_front = next((src(c) for c in old_cells if src(c).strip()), "")
                old_cats = categories(old_front)
            except (ValueError, IndexError):
                old_cats = None
            if old_cats is not None and old_cats != cats:
                err(f"categories changed {old_cats} -> {cats}; this changes the published URL and breaks existing links")

    # --- per cell ---------------------------------------------------------
    nb_out = 0
    for i, cell in enumerate(cells):
        ctype = cell.get("cell_type")
        s = src(cell)
        where = f"cell {i} ({ctype})"

        if ctype in ("markdown", "raw"):
            for m in LIQUID_RE.finditer(s):
                snippet = s[max(0, m.start() - 20):m.end() + 20].replace("\n", " ")
                err(f"{where} line {line_of(s, m.start())}: Liquid delimiter '{m.group(0)}' breaks the Jekyll build "
                    f"(move it into a code cell or use an image): ...{snippet}...")

        if ctype == "markdown" and i > fm_idx:
            if "](]" in s:
                err(f"{where}: malformed link '](]' (stray ']' before the URL)")
            prose = strip_code(s)
            for m in ANGLE_RE.finditer(prose):
                tag = m.group(2).lower()
                if tag not in HTML_TAGS and not tag.startswith(("http", "mailto")):
                    warn(f"{where}: '{m.group(0)}' will be treated as an HTML tag and disappear; use [..] or backticks")
            if re.search(r"(?<![\w*])\*{4}(?![\w*])", prose):
                warn(f"{where}: '****' renders as bold markup; use [redacted]")
            if re.search(r"\|\s*<br\s*/?>", prose):
                warn(f"{where}: table cell starts with <br> (adds a stray blank line)")

        if ctype == "code":
            cell_out = sum(len(json.dumps(o)) for o in cell.get("outputs", []))
            nb_out += cell_out
            if cell_out > CELL_OUTPUT_WARN:
                warn(f"{where}: output is {cell_out // 1024} KB; consider clearing it and linking the dump")

    if nb_out > NB_OUTPUT_WARN:
        warn(f"total output is {nb_out // 1024} KB")


def main(argv):
    errors, warnings = [], []
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    if not top:
        sys.exit("check_notebooks: not inside a git repository")
    # normalise user-supplied paths to repo-relative, then run from the repo root
    argv = [a if a.startswith("--") else os.path.relpath(os.path.abspath(a), top) for a in argv]
    os.chdir(top)

    if argv and argv[0] == "--all":
        mode = "disk"
        paths = sorted(NOTEBOOK_DIR + f for f in os.listdir(NOTEBOOK_DIR) if f.endswith(".ipynb"))
    elif argv:
        mode = "disk"
        paths = argv
    else:
        mode = "staged"
        paths = staged_paths()

    for p in paths:
        if STRAY_RE.search(p):
            errors.append(f"{p}: stray Jupyter/Python file staged; unstage it (git rm --cached '{p}')")

    notebooks = [p for p in paths
                 if p.endswith(".ipynb") and not STRAY_RE.search(p)
                 and os.path.dirname(os.path.normpath(p)) == NOTEBOOK_DIR.rstrip("/")]

    for p in notebooks:
        if mode == "staged":
            text = read_staged(p)
        else:
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                errors.append(f"{p}: {e}")
                continue
        if text is None:
            continue
        check_notebook(p, text, read_head(p), errors, warnings)

    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    for e in errors:
        print("error:   " + e, file=sys.stderr)
    if errors:
        print(f"\ncheck_notebooks: {len(errors)} error(s). Fix them, or bypass with 'git commit --no-verify'.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
