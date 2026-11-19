"""Test helper: chunking the five guideline PDFs takes about 12 s, so the tests share one copy (each caller gets its own deep copy)."""
import copy

from ectd_engine.knowledge import chunk as ch

_real_chunk_document = ch.chunk_document
_cache = {}


def _cached_chunk_document(doc_id, path=None):
    """The same chunks the real function returns (only for the standard PDF; a custom path is never cached)."""
    if path is not None:
        return _real_chunk_document(doc_id, path)
    if doc_id not in _cache:
        _cache[doc_id] = _real_chunk_document(doc_id)
    return copy.deepcopy(_cache[doc_id])


def install():
    """Idempotent. chunk_all() and load.build_all() call ch.chunk_document, so they use the cache too."""
    if ch.chunk_document is not _cached_chunk_document:
        ch.chunk_document = _cached_chunk_document


install()
