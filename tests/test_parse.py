"""Parsing is only useful if a character span can be quoted back verbatim from the
page it came from. These tests assert that round-trip on the development corpus."""

from pathlib import Path

import pytest

from factledger.parse import parse_pdf

DEV = Path(__file__).resolve().parent.parent / "data" / "dev"
DEV_PDFS = sorted(DEV.glob("*.pdf"))


@pytest.fixture(scope="module", params=[p.name for p in DEV_PDFS])
def document(request):
    return parse_pdf(str(DEV / request.param))


def test_document_has_pages_with_text(document):
    assert document.pages
    assert any(page.text.strip() for page in document.pages)


def test_every_block_span_round_trips(document):
    for page in document.pages:
        for block in page.blocks:
            assert page.text[block.char_start:block.char_end] == block.text


def test_inner_span_quotes_back_verbatim(document):
    quoted = 0
    for page in document.pages:
        for block in page.blocks:
            if len(block.text) < 4:
                continue
            start = block.char_start + 1
            end = block.char_end - 1
            snippet = block.text[1:-1]
            assert page.text[start:end] == snippet
            quoted += 1
    assert quoted > 0


def test_blocks_are_ordered_and_non_overlapping(document):
    for page in document.pages:
        cursor = 0
        for block in page.blocks:
            assert block.char_start >= cursor
            assert block.char_end >= block.char_start
            cursor = block.char_end
