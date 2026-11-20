"""The one number-finder shared by the renderer and its gates, and the explicit list of tokens it ignores."""
import re

from ectd_engine.validator.validator import ALLOWED_TOKENS, NUMBER_WORDS

ORDINALS = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|"
    r"fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth)\b", re.I)
FRACTION_CHARS = "½¼¾"   # the characters for one half, one quarter, three quarters
# digits with thousands commas ("1,000"), plain digits and decimals, a leading-dot decimal (".5"), then words and fractions
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+|" + NUMBER_WORDS.pattern + "|" + ORDINALS.pattern
                    + "|[" + FRACTION_CHARS + "]", re.I)
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


def uncovered_digits(text, covered, batch_ids=(), table_first_cell=False):
    """Second check, not using NUMBER: ["uncovered:<context>"] for every digit that sits in no covered span and no exempt span.

    covered = [(start, end)] placement spans (or [] when the whole text is checked on its own)."""
    skip = [(s, e) for s, e, _ in exempt_spans(text, set(batch_ids), table_first_cell)] + list(covered)
    out = []
    for i, ch in enumerate(text):
        if ch.isdigit() and not any(s <= i < e for s, e in skip):
            out.append("uncovered:" + text[max(0, i - 12):i + 13].replace("\t", " ").replace("\n", " "))
    return out
