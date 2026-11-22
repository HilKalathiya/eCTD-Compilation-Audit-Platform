"""Checks that every quote in evidence/T-063/extract.md is found, word for word, on its page of the FDA review text."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ws = lambda s: re.sub(r"\s+", " ", s)


def pages():
    text = (ROOT / "evidence" / "T-062" / "chemr.txt").read_text(encoding="utf-8")
    return [None] + [_ws(p) for p in text.split("\f")]


def quotes():
    out = []
    for line in (ROOT / "evidence" / "T-063" / "extract.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| p\.(\d+) \|", line)
        if m:
            out += [(int(m.group(1)), _ws(q)) for q in re.findall(r'"([^"]+)"', line)]
    return out


class QuotesAreVerbatim(unittest.TestCase):
    def test_there_are_quotes(self):
        self.assertGreaterEqual(len(quotes()), 10)

    def test_every_quote_is_on_its_page(self):
        P = pages()
        for page, q in quotes():
            self.assertIn(q, P[page], "p.%d: %s" % (page, q[:60]))

    def test_planted_changed_quote_is_not_found(self):
        P = pages()
        page, q = quotes()[0]
        self.assertNotIn(q.replace("36 months", "48 months"), P[page])
        self.assertNotIn(q.replace("long- term", "long-term"), P[5])

    def test_excursion_range_is_in_the_review_and_csv(self):
        self.assertIn("Excursions are permitted from 15°C to 30°C", pages()[3])
        from ectd_engine.stability import facts
        f = facts.compute_facts(facts.load_rows())
        self.assertEqual((int(f[("15-30C excursion", "excursion_permitted_low")].last),
                          int(f[("15-30C excursion", "excursion_permitted_high")].last)), (15, 30))


if __name__ == "__main__":
    unittest.main()
