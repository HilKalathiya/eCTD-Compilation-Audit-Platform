"""Checks our shelf life and poolability against R's expirest, and our regression against NIST's Norris values."""
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal, localcontext
from pathlib import Path
from unittest import mock

from ectd_engine.stats.pool import COMMON_SLOPE, POOLED, SEPARATE, poolability
from ectd_engine.stats.q1e import fit, shelf_life
from tests.test_pool import CASE_A, CASE_B, CASE_C, SPEC_MIN
from tests.test_q1e import ASSAY, IMPURITY

NIST = Path(__file__).resolve().parent.parent / "data" / "public" / "nist"
NUM = r"([-0-9.eE+]+)"
R_SCRIPT = Path(__file__).resolve().parent / "r" / "q1e.R"
D = Decimal


def find_rscript():
    """Rscript on PATH, else the newest standard Windows install; None if R is missing."""
    found = shutil.which("Rscript")
    if found:
        return found
    candidates = sorted(Path("C:/Program Files/R").glob("R-*/bin/Rscript.exe"))
    return str(candidates[-1]) if candidates else None


def run_expirest(batches, limit, side="lower"):
    """Write the batches to a CSV, run tests/r/q1e.R, return its JSON answer. Fails (not skips) if R is missing."""
    rscript = find_rscript()
    if rscript is None:
        raise AssertionError("install R (Rscript not found), then: Rscript -e \"install.packages('expirest')\"")
    env = dict(os.environ)
    personal = sorted((Path.home() / "R" / "win-library").glob("*"))  # per-user package folder on Windows
    if personal and "R_LIBS_USER" not in env:
        env["R_LIBS_USER"] = str(personal[-1])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "data.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["batch", "month", "value"])
            for bid, pts in batches.items():
                for month, value in pts:
                    w.writerow([bid, month, value])
        done = subprocess.run([rscript, str(R_SCRIPT), str(path), str(limit), side],
                              capture_output=True, text=True, env=env)
    if done.returncode != 0:
        raise AssertionError(f"Rscript failed (is expirest installed?): {done.stderr}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def agree(ours, theirs):
    """Same shelf life to 0.1 month (both rounded half up) and within 0.01 month before rounding."""
    theirs = D(repr(theirs))
    tenth = D("0.1")
    return (ours.quantize(tenth, rounding="ROUND_HALF_UP") == theirs.quantize(tenth, rounding="ROUND_HALF_UP")
            and abs(ours - theirs) <= D("0.01"))


def digits15(x):
    """Round to 15 significant digits (NIST prints 15)."""
    with localcontext() as ctx:
        ctx.prec = 15
        return +x


def load_norris(lines=None):
    """Certified B0, B1, residual SD from the file header; data (y, x) from line 61 on."""
    lines = lines or (NIST / "Norris.dat").read_text().splitlines()
    cert = {}
    for line in lines[:60]:
        for key, pat in (("b0", r"\s+B0\s+" + NUM), ("b1", r"\s+B1\s+" + NUM),
                         ("sd", r"\s+Standard Deviation\s+" + NUM)):
            m = re.match(pat, line)
            if m and key not in cert:
                cert[key] = Decimal(m.group(1))
    data = []
    for line in lines[60:]:
        if line.strip():
            y, x = line.split()
            data.append((Decimal(x), Decimal(y)))  # fit() takes (month, value) = (x, y)
    return cert, data


class TestNorris(unittest.TestCase):
    def test_fit_matches_certified_values(self):
        cert, data = load_norris()
        self.assertEqual(len(data), 36)
        f = fit(data)
        self.assertEqual(digits15(f.slope), digits15(cert["b1"]))
        self.assertEqual(digits15(f.intercept), digits15(cert["b0"]))
        self.assertEqual(digits15(f.residual_sd), digits15(cert["sd"]))

    def test_planted_error_in_data_fails(self):
        cert, data = load_norris()
        data[0] = (data[0][0], data[0][1] + Decimal("0.1"))  # planted error, in memory only
        f = fit(data)
        self.assertNotEqual(digits15(f.slope), digits15(cert["b1"]))
        self.assertNotEqual(digits15(f.residual_sd), digits15(cert["sd"]))


class TestExpirest(unittest.TestCase):
    def check_pool(self, batches, decision):
        ours = poolability(batches, spec_min=SPEC_MIN)
        theirs = run_expirest(batches, SPEC_MIN)
        self.assertEqual(ours.decision, decision)
        self.assertEqual(theirs["decision"], ours.decision)
        self.assertTrue(agree(ours.shelf.months, theirs["shelf"]), (ours.shelf.months, theirs["shelf"]))
        for bid, months in ours.per_batch.items():
            self.assertTrue(agree(months, theirs["per_batch"][bid]), (bid, months, theirs["per_batch"][bid]))
        return ours, theirs

    def test_case_a_fully_pooled(self):
        self.check_pool(CASE_A, POOLED)

    def test_case_b_common_slope(self):
        self.check_pool(CASE_B, COMMON_SLOPE)

    def test_case_c_separate(self):
        self.check_pool(CASE_C, SEPARATE)

    def test_single_batch_assay_lower(self):
        theirs = run_expirest({"x": ASSAY}, SPEC_MIN)
        ours = shelf_life(ASSAY, spec_min=SPEC_MIN)
        self.assertFalse(ours.capped)
        self.assertTrue(agree(ours.months, theirs["shelf"]), (ours.months, theirs["shelf"]))

    def test_single_batch_impurity_upper(self):
        theirs = run_expirest({"x": IMPURITY}, "0.40", "upper")
        ours = shelf_life(IMPURITY, spec_max=D("0.40"))
        self.assertFalse(ours.capped)
        self.assertTrue(agree(ours.months, theirs["shelf"]), (ours.months, theirs["shelf"]))

    def test_planted_error_is_caught(self):
        theirs = run_expirest({"x": ASSAY}, SPEC_MIN)
        wrong = list(ASSAY)
        wrong[-1] = (wrong[-1][0], wrong[-1][1] - D("1.5"))  # planted error in a copy, in memory only
        self.assertFalse(agree(shelf_life(wrong, spec_min=SPEC_MIN).months, theirs["shelf"]))
        self.assertFalse(agree(D("24.38") + D("0.2"), theirs["shelf"]))

    def test_missing_r_fails_with_install_message(self):
        with mock.patch(f"{__name__}.find_rscript", return_value=None):
            with self.assertRaisesRegex(AssertionError, "install R"):
                run_expirest({"x": ASSAY}, SPEC_MIN)


if __name__ == "__main__":
    unittest.main()
