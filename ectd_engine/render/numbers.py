"""The one number-finder shared by the renderer and its gates, and the explicit list of tokens it ignores."""
import re

from ectd_engine.validator.validator import ALLOWED_TOKENS, NUMBER_WORDS

NUMBER = re.compile(r"\d+(?:\.\d+)?|" + NUMBER_WORDS.pattern, re.I)
BATCH_RUN = re.compile(r"\bBatch(?:es)?\s+([\w-]+(?:(?:,\s*|\s+and\s+)[\w-]+)*)")
ID_TOKEN = re.compile(r"[\w-]+")

# The only tokens that are not traced to a fact. Each has a test that shows it hides nothing else.
EXEMPT_KINDS = ("guideline_or_section_name", "batch_id_in_text", "batch_id_table_cell")


def exempt_spans(text, batch_ids, table_first_cell=False):
    """[(start, end, kind)] for every exempt token in text. A batch id counts only if it is one of batch_ids."""
    spans = [(m.start(), m.end(), "guideline_or_section_name") for m in ALLOWED_TOKENS.finditer(text)]
    for run in BATCH_RUN.finditer(text):
        for tok in ID_TOKEN.finditer(run.group(1)):
            if tok.group(0) in batch_ids:
                spans.append((run.start(1) + tok.start(), run.start(1) + tok.end(), "batch_id_in_text"))
    if table_first_cell:
        cell = text.split("\t", 1)[0]
        if cell in batch_ids:
            spans.append((0, len(cell), "batch_id_table_cell"))
    return spans


def find_numbers(text, batch_ids=(), table_first_cell=False):
    """[(offset, text)] for every number in text that is not on the exempt list."""
    skip = exempt_spans(text, set(batch_ids), table_first_cell)
    return [(m.start(), m.group(0)) for m in NUMBER.finditer(text)
            if not any(s <= m.start() and m.end() <= e for s, e, _ in skip)]
