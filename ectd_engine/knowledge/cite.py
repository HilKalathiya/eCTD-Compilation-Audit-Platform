"""Accepts a guideline quote only if it appears word for word on the stated page of the original PDF (checked fresh from the PDF)."""
import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF

from ectd_engine.knowledge import chunk

SOURCES = chunk.ROOT / "data" / "public" / "SOURCES.md"
MIN_QUOTE = 40  # characters (after normalising); shorter quotes prove nothing
# The ONLY changes made to both the page text and the quote before the exact comparison (plus chunk.SYMBOL_MAP):
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl"}
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
HYPHEN_BREAK = re.compile(r"(?<=\w)-\s*\n\s*(?=\w)")


class CitationRejected(Exception):
    """The quote is not on that page of that PDF (the message says why)."""


@dataclass(frozen=True)
class Citation:
    doc_id: str
    version: str
    page: int
    quote: str
    pdf_sha256: str


def normalise(text):
    """Symbol-font codes mapped (chunk.SYMBOL_MAP), end-of-line hyphen joined, ligatures and curly quotes replaced,
    whitespace collapsed. Nothing else."""
    text = HYPHEN_BREAK.sub("", chunk.fix_symbols(text))
    text = "".join(LIGATURES.get(c, QUOTES.get(c, c)) for c in text)
    return " ".join(text.split())


def source_sha(doc_id):
    """The sha256 that SOURCES.md records for this document's PDF."""
    name = f"ich/{chunk.DOCS[doc_id]}"
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == name:
            return cells[3]
    raise CitationRejected(f"{name} is not listed in SOURCES.md")


@lru_cache(maxsize=None)
def _sha_of(path, size, mtime_ns):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_sha(path):
    st = Path(path).stat()
    return _sha_of(str(path), st.st_size, st.st_mtime_ns)


def verify(doc_id, page, quote, pdf_dir=None):
    """Citation if `quote` is on 1-based `page` of the PDF whose sha256 matches SOURCES.md; else raises CitationRejected."""
    if doc_id not in chunk.DOCS:
        raise CitationRejected(f"unknown document {doc_id!r}")
    if not isinstance(quote, str) or not normalise(quote):
        raise CitationRejected("empty quote")
    if len(normalise(quote)) < MIN_QUOTE:
        raise CitationRejected(f"quote too short ({len(normalise(quote))} chars, minimum {MIN_QUOTE})")
    path = Path(pdf_dir or chunk.ICH_DIR) / chunk.DOCS[doc_id]
    if not path.is_file():
        raise CitationRejected(f"PDF not found: {path.name}")
    want, got = source_sha(doc_id), file_sha(path)
    if got != want:
        raise CitationRejected(f"PDF sha256 {got[:12]} does not match SOURCES.md {want[:12]}")
    with fitz.open(path) as doc:
        if not isinstance(page, int) or not 1 <= page <= len(doc):
            raise CitationRejected(f"page {page!r} is outside 1..{len(doc)}")
        text = doc[page - 1].get_text()
        version = chunk.doc_version(doc)
    if normalise(quote) not in normalise(text):
        raise CitationRejected(f"quote not found word for word on page {page} of {doc_id}")
    return Citation(doc_id, version, page, quote, got)
