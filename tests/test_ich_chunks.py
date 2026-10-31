"""Tests that the ICH guideline chunks keep document, version, page and table id, and that tables stay whole."""
import contextlib
import io
import unittest

import fitz

from ectd_engine.db import postgres
from ectd_engine.knowledge import chunk as ch
from ectd_engine.knowledge import load
from tests.test_migrate import require_database

Q3B_ROWS = {  # table_id -> every row of the Q3B(R2) Attachment 1 table (page 11), exactly as printed
    "p11-t1": ["Reporting Thresholds", "Maximum Daily Dose1 | Threshold2,3", "≤ 1 g | 0.1%", "> 1 g | 0.05%"],
    "p11-t2": ["Identification Thresholds", "< 1 mg | 1.0% or 5 µg TDI, whichever is lower",
               "1 mg - 10 mg | 0.5% or 20 µg TDI, whichever is lower",
               ">10 mg - 2 g | 0.2% or 2 mg TDI, whichever is lower", "> 2 g | 0.10%"],
    "p11-t3": ["Qualification Thresholds", "< 10 mg | 1.0% or 50 µg TDI, whichever is lower",
               "10 mg - 100 mg | 0.5% or 200 µg TDI, whichever is lower",
               ">100 mg - 2 g | 0.2% or 3 mg TDI, whichever is lower", "> 2 g | 0.15%"],
}


def missing_rows(chunk, rows):
    """Return the expected rows that are not a whole line of the chunk text (empty list = table complete)."""
    lines = chunk["text"].splitlines()
    return [r for r in rows if r not in lines]


class IchChunkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_doc = load.build_all()  # also validates every chunk
        cls.pages = {d: len(fitz.open(ch.ICH_DIR / n)) for d, n in ch.DOCS.items()}

    def test_five_documents(self):
        self.assertEqual(sorted(self.by_doc), ["M4Q_R1", "Q1A_R2", "Q1E", "Q3B_R2", "Q6A"])

    def test_every_chunk_has_doc_version_page_text(self):
        for doc_id, chunks in self.by_doc.items():
            self.assertGreater(len(chunks), 20, doc_id)
            for c in chunks:
                self.assertEqual(c["doc_id"], doc_id)
                self.assertRegex(c["doc_version"], r"^Step 4 \d{4}-\d{2}-\d{2}$")
                self.assertTrue(1 <= c["page"] <= self.pages[doc_id], c["chunk_id"])
                self.assertTrue(c["text"].strip(), c["chunk_id"])
                self.assertEqual(c["sha256"], ch.sha(c["text"]))

    def test_chunk_ids_unique(self):
        ids = [c["chunk_id"] for cs in self.by_doc.values() for c in cs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_text_chunks_about_800_characters(self):
        sizes = [len(c["text"]) for cs in self.by_doc.values() for c in cs if not c["table_id"]]
        self.assertLess(max(sizes), 1600)
        self.assertGreater(sum(sizes) / len(sizes), 300)

    def test_versions_read_from_the_pdf(self):
        self.assertEqual(self.by_doc["Q3B_R2"][0]["doc_version"], "Step 4 2006-06-02")
        self.assertEqual(self.by_doc["Q1A_R2"][0]["doc_version"], "Step 4 2003-02-06")

    def test_no_private_use_characters(self):
        for cs in self.by_doc.values():
            for c in cs:
                self.assertFalse(any(0xE000 <= ord(x) <= 0xF8FF for x in c["text"]), c["chunk_id"])

    def test_q3b_threshold_tables_complete(self):
        tables = {c["table_id"]: c for c in self.by_doc["Q3B_R2"] if c["page"] == 11 and c["table_id"]}
        self.assertEqual(sorted(tables), sorted(Q3B_ROWS))
        for tid, rows in Q3B_ROWS.items():
            self.assertEqual(missing_rows(tables[tid], rows), [], tid)
            self.assertEqual(tables[tid]["chunk_id"], f"Q3B_R2:{tid}")

    def test_planted_missing_row_is_caught(self):
        c = dict(next(c for c in self.by_doc["Q3B_R2"] if c["table_id"] == "p11-t2"))
        c["text"] = "\n".join(l for l in c["text"].splitlines() if not l.startswith("1 mg - 10 mg"))
        self.assertEqual(missing_rows(c, Q3B_ROWS["p11-t2"]), ["1 mg - 10 mg | 0.5% or 20 µg TDI, whichever is lower"])

    def test_q3b_attachment_2_rounding_tables(self):
        c = next(c for c in self.by_doc["Q3B_R2"] if c["table_id"] == "p13-t1")
        self.assertIn("0.2143 | 0.2 | 100 | None | None", c["text"].splitlines())

    def test_q1a_storage_table_is_a_table_chunk(self):
        tables = [c for c in self.by_doc["Q1A_R2"] if c["page"] == 9 and c["table_id"]]
        self.assertTrue(any("25°C ± 2°C/60% RH ± 5% RH" in c["text"] for c in tables))

    def test_q1e_has_no_table_but_keeps_decision_tree_text_with_page(self):
        # Q1E's decision tree (page 12) is a drawing, so it is text chunks, not a table chunk.
        self.assertEqual([c["table_id"] for c in self.by_doc["Q1E"] if c["page"] == 12], [None] * sum(
            1 for c in self.by_doc["Q1E"] if c["page"] == 12))
        self.assertTrue(any("shelf life" in c["text"] for c in self.by_doc["Q1E"] if c["page"] == 12))

    def test_table_chunks_exist_with_table_id(self):
        for doc_id, chunks in self.by_doc.items():
            for c in chunks:
                if c["table_id"]:
                    self.assertRegex(c["table_id"], r"^p%d-t\d+$" % c["page"])

    def test_big_table_is_cut_between_rows_never_inside(self):
        rows = [["Row %03d" % i, "x" * 60, "value %d" % i] for i in range(80)]
        groups = ch.table_groups(rows)
        self.assertGreater(len(groups), 1)
        whole = {" | ".join(r) for r in rows}
        seen = set()
        for g in groups:
            self.assertLessEqual(len(g), ch.TABLE_MAX + 200)
            for line in g.splitlines():
                self.assertIn(line, whole)  # every line is one complete row
                seen.add(line)
        self.assertEqual(seen, whole)

    def test_headings_and_pages_land_in_path(self):
        c = next(c for c in self.by_doc["Q3B_R2"] if c["table_id"] == "p11-t2")
        self.assertTrue(c["heading_path"].startswith("Attachment 1"))

    def test_dry_run_prints_counts(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            load.main(["--dry-run"])
        text = out.getvalue()
        for doc_id in ch.DOCS:
            self.assertIn(f"{doc_id} (", text)
        self.assertRegex(text, r"Q3B_R2 \(Step 4 2006-06-02\): \d+ chunks, [1-9]\d* table chunks")


class RefusedChunkTests(unittest.TestCase):
    def good(self):
        text = "A sentence."
        return {"chunk_id": "X:p1-c1", "doc_id": "X", "doc_version": "Step 4 2000-01-01", "page": 1,
                "table_id": None, "heading_path": "", "text": text, "sha256": ch.sha(text)}

    def test_good_chunk_passes(self):
        load.validate(self.good(), 5)

    def test_planted_bad_chunks_refused(self):
        plants = [("page 0", {"page": 0}), ("page past end", {"page": 6}), ("no doc", {"doc_id": ""}),
                  ("doc missing", {"doc_id": None}), ("no version", {"doc_version": ""}),
                  ("empty text", {"text": "  ", "sha256": ch.sha("  ")}), ("wrong hash", {"sha256": "0" * 64}),
                  ("bad table id", {"table_id": "table1"})]
        for name, change in plants:
            c = {**self.good(), **change}
            with self.assertRaises(load.BadChunk, msg=name):
                load.validate(c, 5)


class LiveStoreTests(unittest.TestCase):
    def setUp(self):
        require_database()
        from ectd_engine.db import migrate
        migrate.migrate()
        self.conn = postgres.connect()
        self.chunks = ch.chunk_document("Q3B_R2")

    def tearDown(self):
        self.conn.close()

    def count(self):
        return self.conn.execute("SELECT count(*) FROM kb_chunks WHERE doc_id = 'Q3B_R2'").fetchone()[0]

    def test_reload_makes_no_duplicates(self):
        load.store(self.conn, self.chunks)
        first = self.count()
        load.store(self.conn, self.chunks)
        self.assertEqual(self.count(), first)
        self.assertEqual(first, len(self.chunks))

    def test_table_chunk_row_survives_round_trip(self):
        load.store(self.conn, self.chunks)
        text = self.conn.execute("SELECT text FROM kb_chunks WHERE chunk_id = 'Q3B_R2:p11-t3'").fetchone()[0]
        self.assertIn("> 2 g | 0.15%", text.splitlines())

    def test_database_refuses_page_zero(self):
        c = {**self.chunks[0], "chunk_id": "Q3B_R2:planted", "page": 0}
        with self.assertRaises(Exception):
            load.store(self.conn, [c])
        self.conn.rollback()

    def test_no_number_columns_beyond_page(self):
        cols = self.conn.execute("SELECT column_name, data_type FROM information_schema.columns "
                                 "WHERE table_name = 'kb_chunks'").fetchall()
        numeric = [n for n, t in cols if t in ("numeric", "real", "double precision", "integer", "bigint")]
        self.assertEqual(numeric, ["page"])
        self.assertEqual([x for x in postgres.float_columns(self.conn) if x[0] == "kb_chunks"], [])


if __name__ == "__main__":
    unittest.main()
