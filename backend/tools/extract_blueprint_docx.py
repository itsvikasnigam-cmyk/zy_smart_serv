"""Extract Whatsapp Manager Blueprint.docx to markdown-ish text.

Usage:
  python backend/tools/extract_blueprint_docx.py "C:\\path\\to\\Whatsapp Manager Blueprint.docx"
  python backend/tools/extract_blueprint_docx.py   # default Desktop path below

Writes: blueprint_extract.txt in repo root.
"""

from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_DOCX = Path(
    r"c:\Users\TV_Station\OneDrive\Desktop\ZY Smart AI\Whatsapp Automate Script\Whatsapp Manager Blueprint.docx"
)
OUT = Path(__file__).resolve().parents[2] / "blueprint_extract.txt"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t")).strip()


def heading_level(p: ET.Element) -> int | None:
    pPr = p.find(f"{W}pPr")
    if pPr is None:
        return None
    ps = pPr.find(f"{W}pStyle")
    if ps is not None:
        v = ps.get(f"{W}val") or ""
        for name, lvl in (("Heading1", 1), ("Heading2", 2), ("Heading3", 3), ("Heading4", 4), ("Title", 1)):
            if name in v:
                return lvl
    ol = pPr.find(f"{W}outlineLvl")
    if ol is not None:
        try:
            return int(ol.get(f"{W}val")) + 1  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass
    return None


def extract(docx: Path) -> list[str]:
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{W}body")
    if body is None:
        raise RuntimeError("no document body in docx")

    lines: list[str] = []
    for el in body:
        tag = el.tag.split("}")[-1]
        if tag == "p":
            text = para_text(el)
            if not text:
                lines.append("")
                continue
            lvl = heading_level(el)
            if lvl:
                lines.append("#" * min(max(lvl, 1), 6) + " " + text)
            elif re.match(r"^M\d+(\.\d+)*\b", text):
                lines.append("## " + text)
            else:
                lines.append(text)
        elif tag == "tbl":
            rows: list[list[str]] = []
            for tr in el.findall(f".//{W}tr"):
                row: list[str] = []
                for tc in tr.findall(f"{W}tc"):
                    bits = [para_text(p) for p in tc.findall(f".//{W}p") if para_text(p)]
                    row.append(" ".join(bits))
                if any(c.strip() for c in row):
                    rows.append(row)
            if rows:
                ncol = max(len(r) for r in rows)
                rows = [r + [""] * (ncol - len(r)) for r in rows]
                lines += ["", "| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * ncol) + " |"]
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                lines.append("")
    return lines


def main() -> int:
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOCX
    if not docx.is_file():
        print(f"ERROR: not found: {docx}")
        return 1
    lines = extract(docx)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
