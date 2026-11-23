"""The code-owned plan for 2.3.P.5 and 2.3.P.8: headings, sentences, and exactly which graph fact each number comes from."""
from ectd_engine.graph.summary_graph import LABEL, PREFIX, spec_id, stab_id

TITLE = "Quality overall summary, drug product"   # no digits on purpose: every digit in the document must come from a fact

# How a unit is written after its number. A unit that is not listed here stops the build (nothing is guessed).
UNIT_TEXT = {"months": " months", "C": "°C", "%": "%", "% label claim": "% label claim", "% area": "% area",
             "% dissolved": "% dissolved", "min": " min"}   # "min" = the dissolution time point (T-072)

LONG, INTER, ACCEL = "25C/60%RH", "30C/75%RH", "40C/75%RH"
# Condition names hold digits, so the text uses a word for them; the number itself is never typed.
COND_WORD = {LONG: "long-term", INTER: "intermediate", ACCEL: "accelerated"}
# The attribute "Dissolution (15 min)" holds digits too, so it is shown as "Dissolution".
ATTR_SHOWN = {"Assay": "Assay", "Degradation product": "Degradation product", "Dissolution (15 min)": "Dissolution"}

PUBLIC_REFS = {
    "shelf": stab_id("20-25C CRT", "expiry_period_proposed", "36"),
    "st_low": stab_id("20-25C CRT", "storage_low", "36"),
    "st_high": stab_id("20-25C CRT", "storage_high", "36"),
    "ex_low": stab_id("15-30C excursion", "excursion_permitted_low", "0"),
    "ex_high": stab_id("15-30C excursion", "excursion_permitted_high", "0"),
    "long": stab_id(LONG, "study_duration_demonstrated", "36"),
    "accel": stab_id(ACCEL, "study_duration_demonstrated", "6"),
}
PUBLIC_TEXT = ("The proposed shelf life is [[shelf]] when stored at [[st_low]] to [[st_high]]. "
               "Excursions are permitted from [[ex_low]] to [[ex_high]]. "
               "Stability was demonstrated for [[long]] at long-term conditions and [[accel]] at accelerated conditions.")

SPEC_ATTRIBUTES = ["dissolution_av", "impurity_o", "impurity_l", "impurities_total", "resodual_solvent"]
SPEC_INTRO = "the drug product specification lists these tests and acceptance criteria."
SPEC_HEAD = ("Test", "Acceptance criterion")

STAT_GROUPS = [(c, a) for c in (LONG, INTER, ACCEL) for a in ATTR_SHOWN]


def stat_id(condition, attribute, which):
    """The id of a derived result: the lowest or highest stored result of one condition x attribute (which = 'min' or 'max')."""
    return f"{PREFIX}STAT|{condition}|{attribute}|{which}"


# part -> {"title", "sections"}; "kind" says how the builder writes it.
SUMMARY_PLAN = {
    "2.3.P.5": {"title": "Control of drug product", "sections": [
        {"name": "spec_intro", "kind": "spec_intro", "demo": True, "text": SPEC_INTRO},
        {"name": "spec_table", "kind": "spec_table", "demo": True, "attributes": SPEC_ATTRIBUTES, "head": SPEC_HEAD},
    ]},
    "2.3.P.8": {"title": "Stability", "sections": [
        {"name": "public", "kind": "template", "demo": False, "text": PUBLIC_TEXT, "refs": PUBLIC_REFS},
        {"name": "results", "kind": "results", "demo": True, "groups": STAT_GROUPS},
    ]},
}
