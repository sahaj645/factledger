"""PDF -> layout blocks with page numbers and character offsets.

A block is a run of lines that sit together on the page: vertically close and
horizontally overlapping (same column). Each block records its verbatim text, its
bounding box, and its character span within the page's reconstructed text, so that
a span can be quoted back exactly from the page later.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber


@dataclass(frozen=True)
class Block:
    index: int
    text: str
    char_start: int
    char_end: int
    bbox: tuple[float, float, float, float]  # x0, top, x1, bottom
    # (char_start, char_end, bbox) per word, in page-text coordinates. Lets a table
    # cell be located by where it sits on the page rather than by the first place its
    # digits happen to appear.
    words: list = field(default_factory=list)


@dataclass(frozen=True)
class Table:
    rows: list[list[Optional[str]]]              # cell text grid
    cell_bbox: list[list[Optional[tuple]]]       # parallel grid of cell bboxes
    bbox: tuple[float, float, float, float]
    caption: Optional[str]                       # nearest heading/line above, if any


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    text: str
    blocks: list[Block]
    tables: list[Table] = field(default_factory=list)


@dataclass(frozen=True)
class Document:
    doc_id: str
    path: str
    pages: list[Page]


def parse_pdf(path: str) -> Document:
    doc_id = Path(path).stem
    pages: list[Page] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append(_parse_page(page, i))
    return Document(doc_id=doc_id, path=str(path), pages=pages)


def _parse_page(page, number: int) -> Page:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    lines = _group_lines(words)
    line_groups = _group_blocks(lines)

    blocks: list[Block] = []
    page_text_parts: list[str] = []
    cursor = 0
    for idx, group in enumerate(line_groups):
        start = cursor
        text, words = _text_and_words(group, start)
        end = start + len(text)
        blocks.append(Block(index=idx, text=text, char_start=start, char_end=end,
                            bbox=_group_bbox(group), words=words))
        page_text_parts.append(text)
        cursor = end + 2  # blocks are joined by "\n\n"

    page_obj_text = "\n\n".join(page_text_parts)
    tables = _extract_tables(page, blocks)
    return Page(number=number, text=page_obj_text, blocks=blocks, tables=tables)


def _extract_tables(page, blocks: list[Block]) -> list[Table]:
    found = page.find_tables()
    if not found:
        found = page.find_tables(table_settings={"vertical_strategy": "text",
                                                 "horizontal_strategy": "text"})
    tables = []
    for t in found:
        grid = t.extract()
        if not grid or not any(any(cell for cell in row) for row in grid):
            continue
        cell_bbox = [list(row.cells) for row in t.rows]
        tables.append(Table(rows=grid, cell_bbox=cell_bbox, bbox=t.bbox,
                            caption=_caption_above(t.bbox, blocks)))
    return tables


def _caption_above(table_bbox, blocks: list[Block]) -> Optional[str]:
    """The line of text that introduces the table.

    A block may sit wholly above the table, in which case the line nearest the table
    is its last. Or it may begin above the table and run past its top, which happens
    when line grouping pulls a heading and the table body into one block; there the
    heading is the block's first line. Requiring a block to end above the table missed
    that second case entirely and left the table with no caption at all.
    """
    tx0, ttop, tx1, _ = table_bbox
    candidates = [
        b for b in blocks
        if b.bbox[1] < ttop and min(tx1, b.bbox[2]) - max(tx0, b.bbox[0]) > 0
    ]
    if not candidates:
        return None
    block = max(candidates, key=lambda b: b.bbox[1])  # starts closest above the table
    lines = [line.strip() for line in block.text.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1] if block.bbox[3] <= ttop + 2 else lines[0]


def _line_text(line: list[dict]) -> str:
    return " ".join(w["text"] for w in line)


def _text_and_words(group: list[list[dict]], base: int) -> tuple[str, list]:
    """Build the block's text and, alongside it, where each word landed in the page
    text. Lines join with a newline and words with a space, matching _line_text."""
    parts: list[str] = []
    words: list = []
    offset = 0
    for line_no, line in enumerate(group):
        if line_no:
            parts.append("\n")
            offset += 1
        for word_no, w in enumerate(line):
            if word_no:
                parts.append(" ")
                offset += 1
            token = w["text"]
            words.append((base + offset, base + offset + len(token),
                          (w["x0"], w["top"], w["x1"], w["bottom"])))
            parts.append(token)
            offset += len(token)
    return "".join(parts), words


def _group_lines(words: list[dict]) -> list[list[dict]]:
    """Cluster words into visual lines by vertical position, ordered top-to-bottom
    then left-to-right."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    tol = _median_height(words) * 0.6
    lines: list[list[dict]] = [[ordered[0]]]
    for w in ordered[1:]:
        if abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def _group_blocks(lines: list[list[dict]]) -> list[list[list[dict]]]:
    """Group lines into blocks: a line joins the previous block when it is close
    below it and their horizontal ranges overlap (same column)."""
    if not lines:
        return []
    groups: list[list[list[dict]]] = [[lines[0]]]
    for line in lines[1:]:
        prev = groups[-1][-1]
        gap = _line_top(line) - _line_bottom(prev)
        height = _line_bottom(prev) - _line_top(prev)
        same_column = _x_overlap(line, prev)
        if same_column and gap <= height * 1.2:
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def _x_overlap(a: list[dict], b: list[dict]) -> bool:
    a0, a1 = min(w["x0"] for w in a), max(w["x1"] for w in a)
    b0, b1 = min(w["x0"] for w in b), max(w["x1"] for w in b)
    return min(a1, b1) - max(a0, b0) > 0


def _line_top(line: list[dict]) -> float:
    return min(w["top"] for w in line)


def _line_bottom(line: list[dict]) -> float:
    return max(w["bottom"] for w in line)


def _median_height(words: list[dict]) -> float:
    heights = sorted(w["bottom"] - w["top"] for w in words)
    return heights[len(heights) // 2]


def _group_bbox(group: list[list[dict]]) -> tuple[float, float, float, float]:
    words = [w for line in group for w in line]
    return (min(w["x0"] for w in words), min(w["top"] for w in words),
            max(w["x1"] for w in words), max(w["bottom"] for w in words))
