"""Turn table cells into claims, deterministically.

A numeric cell becomes a claim only when it carries its context: a row label, a
column header chain (spanning headers propagated across the columns they cover), and
a value grounded in a single layout block. Magnitude and currency are read from the
header legend so a bare cell number is reunited with the scale stated above it. Scope
and period are taken from the header chain via the lexicon. The cell value is never
read by a model; if it cannot be grounded in one block, the cell is rejected and the
reason recorded. Where a row or column label is missing, the cell does not become a
claim — a number without its context is not stored.
"""

from typing import Callable, Optional

from factledger.parse import Page, Block, Table
from factledger.extract import Claim, Evidence, Qualifiers, Rejection
from factledger.normalize import normalize_scope, normalize_period, unit_context


def build_table_claims(page: Page, doc_id: str) -> tuple[list[Claim], list[Rejection]]:
    claims, rejections = [], []
    for table in page.tables:
        locate = _locator(table, page.blocks)
        c, r = table_to_claims(table.rows, table.caption, locate, doc_id, page.number)
        claims.extend(c)
        rejections.extend(r)
    return claims, rejections


def table_to_claims(
    rows: list[list[Optional[str]]],
    caption: Optional[str],
    locate: Callable[[int, int, str], Optional[tuple[int, int]]],
    doc_id: str,
    page: int,
) -> tuple[list[Claim], list[Rejection]]:
    header_rows = _header_row_count(rows)
    magnitude, currency = unit_context(" ".join(_header_text(rows, header_rows) + [caption or ""]))

    claims, rejections = [], []
    for r in range(header_rows, len(rows)):
        for c in range(1, len(rows[r])):
            value = _cell(rows, r, c)
            if not _is_number(value):
                continue
            candidate = {"row": r, "col": c, "value": value}
            row_label = _row_label(rows, header_rows, r)
            if not row_label:
                rejections.append(Rejection("table cell without row label", candidate))
                continue
            header = _column_header(rows, header_rows, c)
            if not header:
                rejections.append(Rejection("table cell without column header", candidate))
                continue
            span = locate(r, c, value)
            if span is None:
                rejections.append(Rejection("table value not grounded in a single block", candidate))
                continue
            if "%" in value:  # a percentage is not a currency amount; keep it as-is
                value_raw = value
            else:
                value_raw = " ".join(part for part in (currency, value, magnitude) if part)
            claims.append(Claim(
                subject=(caption or "").strip(),
                measure=row_label,
                kind="numeric",
                value_raw=value_raw,
                qualifiers=Qualifiers(
                    period=normalize_period(header) or normalize_period(caption or ""),
                    scope=normalize_scope(header),
                    basis=None, as_of=None,
                ),
                evidence=Evidence(doc_id=doc_id, page=page, snippet=value, char_span=span),
            ))
    return claims, rejections


def in_table(block: Block, tables: list[Table]) -> bool:
    cx = (block.bbox[0] + block.bbox[2]) / 2
    cy = (block.bbox[1] + block.bbox[3]) / 2
    return any(t.bbox[0] <= cx <= t.bbox[2] and t.bbox[1] <= cy <= t.bbox[3] for t in tables)


def _header_row_count(rows: list[list[Optional[str]]]) -> int:
    count = 0
    for row in rows:
        if any(_is_number(_at(row, c)) for c in range(1, len(row))):
            break
        count += 1
    return count


def _row_label(rows, header_rows: int, r: int) -> str:
    label = _cell(rows, r, 0)
    if label:
        return label
    for rr in range(r - 1, header_rows - 1, -1):  # inherit a group heading above
        above = _cell(rows, rr, 0)
        if above:
            return above
    return ""


def _column_header(rows, header_rows: int, c: int) -> str:
    parts: list[str] = []
    for hr in range(header_rows):
        cell = _cell(rows, hr, c) or _inherit_left(rows[hr], c)
        if cell and cell not in parts:
            parts.append(cell)
    return " > ".join(parts)


def _inherit_left(header_row, c: int) -> str:
    for cc in range(min(c, len(header_row)) - 1, 0, -1):  # stop before the label column
        value = _at(header_row, cc)
        if value:
            return value
    return ""


def _header_text(rows, header_rows: int) -> list[str]:
    return [cell for hr in range(header_rows) for cell in (rows[hr] or []) if cell]


def _locator(table: Table, blocks: list[Block]):
    def locate(r: int, c: int, value: str) -> Optional[tuple[int, int]]:
        bbox = None
        if r < len(table.cell_bbox) and c < len(table.cell_bbox[r]):
            bbox = table.cell_bbox[r][c]
        block = _block_for(bbox, blocks) if bbox else None
        if block is None:
            return None
        idx = block.text.find(value)
        if idx < 0:
            return None
        return (block.char_start + idx, block.char_start + idx + len(value))
    return locate


def _block_for(bbox, blocks: list[Block]) -> Optional[Block]:
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for b in blocks:
        if b.bbox[0] <= cx <= b.bbox[2] and b.bbox[1] <= cy <= b.bbox[3]:
            return b
    return None


def _cell(rows, r: int, c: int) -> str:
    return _at(rows[r], c) if r < len(rows) else ""


def _at(row, c: int) -> str:
    if row is None or c >= len(row):
        return ""
    return (row[c] or "").strip()


def _is_number(value: str) -> bool:
    core = (value or "").strip().strip("()").replace(",", "").replace("%", "")
    core = core.replace("₹", "").replace("$", "").strip().lstrip("-").strip()
    if not core:
        return False
    try:
        float(core)
        return True
    except ValueError:
        return False
