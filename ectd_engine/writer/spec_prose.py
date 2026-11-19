"""The prose rules for a finished P.5.6 paragraph: each is a named pattern that must NOT match (one source of truth for the loop and the tests)."""
import re

NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                "sixteen|seventeen|eighteen|nineteen|twenty")

PROSE_RULES = {
    # T-049 rules
    "batches of": re.compile(r"\bbatch(?:es)? of\b"),
    "resting on declared": re.compile(r"resting on declared"),
    "set declared": re.compile(r"set declared"),
    "batches results": re.compile(r"\bbatch(?:es)? results"),
    "U+FFFD": re.compile("�"),
    "mojibake": re.compile("â€|Âµ"),
    "starts lower-case": re.compile(r"^[a-z]"),
    "lower-case after full stop": re.compile(r"\. [a-z]"),
    # T-050 rules
    "upon": re.compile(r"\bupon\b", re.I),
    "number word as a count": re.compile(rf"\b(?:{NUMBER_WORDS})\b", re.I),
    "1 of N ... were": re.compile(r"\b1 of \d+ results were\b"),
    "N>1 of M ... was": re.compile(r"\b(?:[2-9]|\d{2,}) of \d+ results was\b"),
}


def prose_problems(text):
    """Names of the rules the finished text breaks (empty list = clean)."""
    return [name for name, rx in PROSE_RULES.items() if rx.search(text)]
