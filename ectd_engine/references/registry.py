"""The closed list of citations (ICH guideline ids, CTD section numbers) that may appear in text without counting as numbers.

Nothing here is a pattern: a token is exempt only if the WHOLE token is in this list (full match, word boundaries checked).
Sources:
- ICH guideline ids: the ICH "Quality Guidelines" page (https://www.ich.org/page/quality-guidelines), as named in the T-069 card.
  The ids Q3B(R2), Q1E, Q1A and Q6A also already appear in this repo (specs, stability and writer code).
  Not re-checked online in this task (no network). Q3C(R9) comes from the card list; it is the id to re-check first.
  Bare ids (Q3B) are the same entries without the revision, made in code from the list.
- CTD section numbers: built in code from CONTENT_PLAN (render/plan.py), SUMMARY_PLAN (summary/plan.py), the P.8.3 part,
  and the standard CTD headings 3.2.P.5.1-5.6, 3.2.P.8.1-8.3, 3.2.P.5, 3.2.P.8, 3.2.P, 2.3.P, 2.3.P.5, 2.3.P.8.
The plans are read on first use (not at import) so this module can be imported by the validator without a cycle.
"""
import re

ICH_IDS = ("Q1A(R2)", "Q1B", "Q1C", "Q1D", "Q1E", "Q2(R2)", "Q3A(R2)", "Q3B(R2)", "Q3C(R9)", "Q3D(R2)",
           "Q6A", "Q6B", "Q8(R2)", "Q9(R1)", "Q10", "Q11", "Q12", "Q14")
STABILITY_PART = "3.2.P.8.3"                      # the P.8.3 paragraph's own section (no plan dict holds it)
STANDARD_SECTIONS = tuple([f"3.2.P.5.{n}" for n in range(1, 7)] + [f"3.2.P.8.{n}" for n in range(1, 4)]
                          + ["3.2.P.5", "3.2.P.8", "3.2.P", "2.3.P", "2.3.P.5", "2.3.P.8"])


def ich_tokens():
    """Every exact ICH token: the listed ids plus each id without its revision, e.g. Q3B(R2) and Q3B."""
    out = set(ICH_IDS)
    out.update(re.sub(r"\(R\d+\)$", "", i) for i in ICH_IDS)
    return out


def section_tokens():
    """Every exact section number, read from the plans in code."""
    from ectd_engine.render.plan import CONTENT_PLAN
    from ectd_engine.summary.plan import SUMMARY_PLAN
    return set(CONTENT_PLAN) | set(SUMMARY_PLAN) | {STABILITY_PART} | set(STANDARD_SECTIONS)


def registry():
    """The whole closed list as one sorted tuple."""
    return tuple(sorted(ich_tokens() | section_tokens()))


class ExemptTokens:
    """Looks like a compiled regex (finditer, sub, search) but only ever matches a whole registry token."""
    _re = None

    def regex(self):
        if self._re is None:
            ich = sorted(ich_tokens(), key=len, reverse=True)
            sec = sorted(section_tokens(), key=len, reverse=True)
            self._re = re.compile(
                r"(?<![\w.])(?:(?:ICH\s+)?(?:" + "|".join(map(re.escape, ich)) + r")(?!\w)"
                r"|(?:" + "|".join(map(re.escape, sec)) + r")(?!\w|\.\d))")
        return self._re

    def finditer(self, text):
        return self.regex().finditer(text)

    def sub(self, repl, text):
        return self.regex().sub(repl, text)

    def search(self, text):
        return self.regex().search(text)


ALLOWED_TOKENS = ExemptTokens()
