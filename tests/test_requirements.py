"""Checks docs/requirements.md: ids are unique, every risk has a control and a test, every requirement is covered."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "requirements.md"


def parse_rows(text):
    """Return table rows (list of cell lists) whose first cell looks like UR-nn or RK-nn."""
    rows = []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if re.fullmatch(r"(UR|RK)-\d+", cells[0]):
                rows.append(cells)
    return rows


def check(text, root=ROOT):
    """Return a list of problems found in the requirements text (empty list = all good)."""
    problems = []
    rows = parse_rows(text)
    ids = [r[0] for r in rows]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate id {i}")
    urs = [r for r in rows if r[0].startswith("UR-")]
    rks = [r for r in rows if r[0].startswith("RK-")]
    if len(urs) > 20:
        problems.append(f"{len(urs)} requirements (max 20)")
    ur_ids = {r[0] for r in urs}
    covered = set()
    for r in rks:
        if len(r) != 6:
            problems.append(f"{r[0]} has {len(r)} columns, expected 6")
            continue
        _, _, sev, control, test, covers = r
        if sev not in ("H", "M", "L"):
            problems.append(f"{r[0]} severity '{sev}' is not H/M/L")
        if not control:
            problems.append(f"{r[0]} has no control")
        if not test:
            problems.append(f"{r[0]} has no test or chunk id")
        elif not test.startswith("future:") and not (root / test).exists():
            problems.append(f"{r[0]} test path '{test}' does not exist")
        for u in re.findall(r"UR-\d+", covers):
            if u not in ur_ids:
                problems.append(f"{r[0]} covers unknown {u}")
            covered.add(u)
    for u in sorted(ur_ids - covered):
        problems.append(f"{u} is covered by no risk")
    return problems


class RequirementsFile(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_real_file_is_clean(self):
        self.assertEqual(check(self.text), [])

    def test_must_have_topics_present(self):
        low = self.text.lower()
        for phrase in ("never writes a number", "source", "copies never count", "rounding",
                       "hash-chained", "sign-off is blocked"):
            self.assertIn(phrase, low)


class PlantedMistakes(unittest.TestCase):
    """Each broken copy (in memory only) must make the check fail."""

    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_duplicate_id_fails(self):
        bad = self.text.replace("| UR-02 |", "| UR-01 |", 1)
        self.assertTrue(any("duplicate id UR-01" in p for p in check(bad)))

    def test_risk_without_control_fails(self):
        lines = self.text.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("| RK-01 |"))
        cells = lines[i].strip("|").split("|")
        cells[3] = " "
        lines[i] = "|" + "|".join(cells) + "|"
        bad = "\n".join(lines)
        self.assertTrue(any("RK-01 has no control" in p for p in check(bad)))

    def test_risk_without_test_fails(self):
        lines = self.text.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("| RK-05 |"))
        cells = lines[i].strip("|").split("|")
        cells[4] = " "
        lines[i] = "|" + "|".join(cells) + "|"
        bad = "\n".join(lines)
        self.assertTrue(any("RK-05 has no test" in p for p in check(bad)))

    def test_requirement_with_no_risk_fails(self):
        bad = self.text + "\n| UR-20 | A promise nobody tests. | Step 9 |\n"
        self.assertTrue(any("UR-20 is covered by no risk" in p for p in check(bad)))

    def test_missing_test_file_fails(self):
        bad = self.text.replace("tests/test_watch.py", "tests/no_such_file.py", 1)
        self.assertTrue(any("does not exist" in p for p in check(bad)))


if __name__ == "__main__":
    unittest.main()
