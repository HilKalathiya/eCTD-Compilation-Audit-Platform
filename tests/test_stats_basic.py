"""Checks the Decimal stats against NIST certified values and the half-up rounding traps."""
import re
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

from ectd_engine.stats.basic import conforms, mean, rsd_percent, round_to, sd

NIST = Path(__file__).resolve().parent.parent / "data" / "public" / "nist"
FILES = ["NumAcc1", "NumAcc2", "NumAcc3", "NumAcc4", "Michelso"]
NUM = r"([-0-9.eE+]+)"


def load(name):
    """Read certified mean/SD from the file header and the data from line 61 on."""
    lines = (NIST / f"{name}.dat").read_text().splitlines()
    cert_mean = cert_sd = None
    for line in lines[:60]:
        m = re.match(r"Sample Mean\s+ybar:\s+" + NUM, line)
        if m:
            cert_mean = m.group(1)
        m = re.match(r"Sample Standard Deviation.*s:\s+" + NUM, line)
        if m:
            cert_sd = m.group(1)
    data = [Decimal(x.strip()) for x in lines[60:] if x.strip()]
    return Decimal(cert_mean), Decimal(cert_sd), data


def digits15(x):
    """Round to 15 significant digits (the NIST files print at most 15)."""
    with localcontext() as ctx:
        ctx.prec = 15
        return +x


class TestNist(unittest.TestCase):
    def test_all_files_match_certified(self):
        for name in FILES:
            with self.subTest(file=name):
                cert_mean, cert_sd, data = load(name)
                self.assertGreaterEqual(len(data), 3)
                self.assertEqual(digits15(mean(data)), digits15(cert_mean))
                self.assertEqual(digits15(sd(data)), digits15(cert_sd))

    def test_planted_wrong_certified_value_fails(self):
        cert_mean, cert_sd, data = load("NumAcc4")
        data[0] += Decimal("0.1")  # planted error in a copy, in memory
        self.assertNotEqual(digits15(sd(data)), digits15(cert_sd))

    def test_rsd(self):
        self.assertEqual(round_to(rsd_percent([Decimal(1), Decimal(2), Decimal(3)]), 2), Decimal("50.00"))


class TestRounding(unittest.TestCase):
    def test_half_up_trap(self):
        self.assertEqual(round_to(Decimal("0.125"), 2), Decimal("0.13"))
        self.assertEqual(round(0.125, 2), 0.12)  # shows why Python round() is not used

    def test_conforms(self):
        self.assertTrue(conforms(Decimal("0.1049"), spec_max=Decimal("0.10")))
        self.assertFalse(conforms(Decimal("0.105"), spec_max=Decimal("0.10")))
        self.assertTrue(conforms(Decimal("98.0"), Decimal("98.0"), Decimal("102.0")))
        self.assertFalse(conforms(Decimal("97.94"), Decimal("98.0"), Decimal("102.0")))

    def test_bad_input(self):
        with self.assertRaises(TypeError):
            mean([1.5, 2.5])
        with self.assertRaises(TypeError):
            round_to(0.125, 2)
        with self.assertRaises(TypeError):
            conforms(0.1, spec_max=Decimal("0.10"))
        with self.assertRaises(ValueError):
            sd([Decimal(1)])


if __name__ == "__main__":
    unittest.main()
