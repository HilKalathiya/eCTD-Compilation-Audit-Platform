"""Tests that a guideline quote is accepted only when it is word for word on the stated page of the original PDF."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ectd_engine.db import migrate, postgres
from ectd_engine.knowledge import chunk, cite, embed, load, search
from tests.test_migrate import require_database
from tests.test_retrieval import GOLD, require_ollama

ROW = "1 mg - 10 mg 0.5% or 20 µg TDI, whichever is lower"  # Q3B(R2) page 11, identification table
QUOTE_LE = "Reporting Thresholds Maximum Daily Dose1 Threshold2,3 ≤ 1 g 0.1% > 1 g 0.05%"  # Q3B(R2) page 11
MIN_VERIFIED = 28  # of 30


def flat(c):
    """A table chunk is 'cell | cell' rows; the page reads cell after cell, so a quote of it is the cells joined by spaces."""
    return c["text"].replace(" | ", " ").replace("\n", " ") if c["table_id"] else c["text"]


class VerifyTests(unittest.TestCase):
    """No database needed: only the PDFs in data/public/ich."""

    def test_correct_quote_is_accepted_with_all_fields(self):
        c = cite.verify("Q3B_R2", 11, ROW)
        self.assertEqual((c.doc_id, c.version, c.page, c.quote), ("Q3B_R2", "Step 4 2006-06-02", 11, ROW))
        self.assertEqual(c.pdf_sha256, cite.source_sha("Q3B_R2"))

    def test_layout_differences_are_accepted(self):
        self.assertEqual(cite.verify("Q3B_R2", 11, "  1 mg  -  10 mg\n0.5% or 20 µg   TDI,\twhichever is lower ").page, 11)

    def test_planted_one_word_changed_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "not found"):
            cite.verify("Q3B_R2", 11, ROW.replace("lower", "higher"))

    def test_planted_one_digit_changed_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "not found"):
            cite.verify("Q3B_R2", 11, ROW.replace("20 ", "21 "))

    def test_planted_right_text_wrong_page_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "page 10"):
            cite.verify("Q3B_R2", 10, ROW)

    def test_planted_page_outside_document_is_rejected(self):
        for page in (0, 999, -1):
            with self.assertRaisesRegex(cite.CitationRejected, "outside"):
                cite.verify("Q3B_R2", page, ROW)

    def test_planted_empty_quote_is_rejected(self):
        for q in ("", "   \n\t "):
            with self.assertRaisesRegex(cite.CitationRejected, "empty"):
                cite.verify("Q3B_R2", 11, q)

    def test_planted_unknown_document_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "unknown document"):
            cite.verify("Q9Z", 1, ROW)

    def test_planted_altered_pdf_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / chunk.DOCS["Q3B_R2"]
            shutil.copy(chunk.ICH_DIR / chunk.DOCS["Q3B_R2"], copy)
            self.assertEqual(cite.verify("Q3B_R2", 11, ROW, pdf_dir=tmp).page, 11)  # untouched copy is fine
            with open(copy, "ab") as f:
                f.write(b"\n% one extra byte")
            with self.assertRaisesRegex(cite.CitationRejected, "sha256"):
                cite.verify("Q3B_R2", 11, ROW, pdf_dir=tmp)

    def test_planted_wrong_sha_in_sources_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "SOURCES.md"
            bad.write_text(cite.SOURCES.read_text(encoding="utf-8").replace(cite.source_sha("Q3B_R2"), "0" * 64),
                           encoding="utf-8")
            with mock.patch.object(cite, "SOURCES", bad), self.assertRaisesRegex(cite.CitationRejected, "sha256"):
                cite.verify("Q3B_R2", 11, ROW)

    def test_planted_short_quote_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "too short"):
            cite.verify("Q3B_R2", 11, "the")

    def test_normalisation_is_only_the_four_allowed_changes(self):
        n = cite.normalise
        self.assertEqual(n("a  b\n\tc"), "a b c")                      # whitespace collapse
        self.assertEqual(n("sta-\nbility"), "stability")                 # end-of-line hyphen join
        self.assertEqual(n("ﬁnal ﬂow"), "final flow")          # fi / fl ligatures
        self.assertEqual(n("“the” ‘x’"), "\"the\" 'x'")  # curly quotes
        self.assertEqual(n("()  "), "(≤) ± •")  # Symbol-font codes (chunk.SYMBOL_MAP)
        self.assertNotEqual(n("<"), n("≤"))                        # a look-alike sign is never accepted
        self.assertNotEqual(n("20 mg"), n("21 mg"))                      # digits are never touched
        self.assertNotEqual(n("lower"), n("Lower"))                      # case is never touched
        self.assertNotEqual(n("a - b"), n("a b"))                        # a hyphen inside a line stays

    def test_q3b_threshold_tables_verify(self):
        tables = {c["table_id"]: c for c in chunk.chunk_document("Q3B_R2") if c["table_id"] and c["page"] == 11}
        self.assertEqual(sorted(tables), ["p11-t1", "p11-t2", "p11-t3"])
        for tid in ("p11-t2", "p11-t3"):  # whole table text, header and every row
            self.assertEqual(cite.verify("Q3B_R2", 11, flat(tables[tid])).page, 11, tid)
        t1 = flat(tables["p11-t1"])
        self.assertEqual(cite.verify("Q3B_R2", 11, t1.split("≤")[0]).page, 11)  # heading and column titles
        self.assertEqual(cite.verify("Q3B_R2", 11, "Threshold2,3 ≤ 1 g 0.1% > 1 g 0.05% Identification").page, 11)

    def test_planted_changed_table_number_is_rejected(self):
        t2 = flat([c for c in chunk.chunk_document("Q3B_R2") if c["chunk_id"] == "Q3B_R2:p11-t2"][0])
        self.assertEqual(cite.verify("Q3B_R2", 11, t2).page, 11)
        with self.assertRaises(cite.CitationRejected):
            cite.verify("Q3B_R2", 11, t2.replace("0.2%", "0.3%"))

    def test_q3b_quote_with_less_or_equal_sign_verifies(self):
        self.assertEqual(cite.verify("Q3B_R2", 11, QUOTE_LE).page, 11)

    def test_planted_same_quote_with_less_than_sign_is_rejected(self):
        with self.assertRaisesRegex(cite.CitationRejected, "not found"):
            cite.verify("Q3B_R2", 11, QUOTE_LE.replace("≤", "<"))


class GoldCitationTests(unittest.TestCase):
    """Needs Docker (Postgres) and Ollama, like the retrieval tests. The reranker scores are read from the disk cache."""

    @classmethod
    def setUpClass(cls):
        require_database()
        require_ollama()
        migrate.migrate()
        cls.conn = postgres.connect()
        load.store(cls.conn, [c for cs in load.build_all().values() for c in cs])
        embed.embed_missing(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_gold_top1_first_200_chars_verify(self):
        """First 200 chars of each rerank top-1 hit (table chunks: cells joined by spaces) are checked against the PDF.

        Every rejection is printed with its reason. A rejection is correct when the chunk text is not a verbatim stretch
        of the PDF page (for example a footnote marker that sits elsewhere on the page).
        """
        verified, rejected = [], {}
        for q in GOLD:
            top = search.search(q["q"], 5, self.conn, "rerank")[0]
            try:
                cite.verify(top.doc_id, top.page, flat({"text": top.text, "table_id": top.table_id})[:200])
                verified.append(q["id"])
            except cite.CitationRejected as e:
                rejected[q["id"]] = f"{top.chunk_id}: {e}"
        print(f"citations verified {len(verified)} of {len(GOLD)}")
        for qid, why in rejected.items():
            print(f"  REJECTED {qid} {why}")
        self.assertEqual(len(verified) + len(rejected), len(GOLD))
        self.assertGreaterEqual(len(verified), MIN_VERIFIED)


if __name__ == "__main__":
    unittest.main()
