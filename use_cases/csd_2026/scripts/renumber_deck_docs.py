"""Renumber slide references in the deck companion documents.

Three slides were inserted into the middle of the 60-slide deck:
    new 30  Rejection reason x resolution code
    new 36  Deep dive - Invalid- discontinued title
    new 37  How often is a ticket failed by more than one rule?

so every slide from old 30 onward moved, and both companion documents are keyed to
slide numbers. Mapping: 1-29 unchanged | 30-34 shift +1 | 35-60 shift +3.

Everything happens in ONE left-to-right re.sub pass. Sequential passes are the
obvious way to write this and they are wrong: re.sub does not re-examine text it
has already replaced, but a SECOND sub call does, so "Slide 53" becomes 56 and then
59. One pass, alternation ordered most-specific-first.
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DOCS = [BASE / "docs" / "CSD_2026_deck_talking_points.md",
        BASE / "docs" / "CSD_2026_stakeholder_QA.md"]
MARKER = "<!-- slide numbers renumbered for the 63-slide deck -->"
N_NEW = 63


def newnum(n: int) -> int:
    if n <= 29:
        return n
    if n <= 34:
        return n + 1
    return n + 3


PATTERN = re.compile(
    r"(?P<list>present )(?P<nums>(?:\d+, )+\d+)(?=\.)"
    r"|(?P<s3>[Ss]lides )(?P<a3>\d+)(?P<m3>, )(?P<b3>\d+)(?P<n3> and )(?P<c3>\d+)"
    r"|(?P<s2>[Ss]lides )(?P<a2>\d+)(?P<n2> and )(?P<b2>\d+)"
    r"|(?P<sr>[Ss]lides )(?P<ar>\d+)(?P<dr>\s*[–-]\s*)(?P<br>\d+)"
    r"|(?P<s1>[Ss]lides? )(?P<a1>\d+)"
    r"|(?P<pp>\()(?P<ap>\d{1,2})(?P<dp>–)(?P<bp>\d{1,2})(?P<pq>\))"
)


def repl(m: re.Match) -> str:
    g = m.groupdict()
    if g["list"]:
        return g["list"] + ", ".join(str(newnum(int(x))) for x in g["nums"].split(", "))
    if g["s3"]:
        return (f"{g['s3']}{newnum(int(g['a3']))}{g['m3']}{newnum(int(g['b3']))}"
                f"{g['n3']}{newnum(int(g['c3']))}")
    if g["s2"]:
        return f"{g['s2']}{newnum(int(g['a2']))}{g['n2']}{newnum(int(g['b2']))}"
    if g["sr"]:
        return f"{g['sr']}{newnum(int(g['ar']))}{g['dr']}{newnum(int(g['br']))}"
    if g["s1"]:
        return f"{g['s1']}{newnum(int(g['a1']))}"
    # Bare "(53–60)" - only treat it as a slide range if both ends look like slides.
    a, b = int(g["ap"]), int(g["bp"])
    if 1 <= a < b <= 60:
        return f"{g['pp']}{newnum(a)}{g['dp']}{newnum(b)}{g['pq']}"
    return m.group(0)


for path in DOCS:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"  {path.name}: already renumbered, skipped")
        continue
    out = PATTERN.sub(repl, text)
    changed = sum(1 for a, b in zip(text.split("\n"), out.split("\n")) if a != b)
    path.write_text(out.rstrip("\n") + "\n\n" + MARKER + "\n", encoding="utf-8")

    heads = [int(x) for x in re.findall(r"^### Slides? (\d+)", out, re.M)]
    refs = [int(x) for x in re.findall(r"(?i)slides? (\d+)", out)]
    over = sorted({n for n in heads + refs if n > N_NEW})
    print(f"  {path.name}: {changed} lines changed"
          + (f"  |  headings {min(heads)}..{max(heads)}" if heads else "")
          + (f"  |  ** refs above {N_NEW}: {over}" if over else "  |  no out-of-range refs"))
