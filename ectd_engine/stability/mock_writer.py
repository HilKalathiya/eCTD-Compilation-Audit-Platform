"""Drafts a P.8.3 stability paragraph straight from the facts with no model; code formats every number."""
from ectd_engine.stability import facts as F

DEMO_LABEL_PREFIX = "In illustrative demonstration data, "


def _n(x):
    return str(x)


def draft_paragraph(p83):
    """Sentences for shelf life, storage, excursions, study length, then demo results (each labelled as demo)."""
    p = p83["public"]
    deg = "°"
    out = [
        "The proposed shelf life is %s months when stored at %s%sC to %s%sC." % (
            _n(p["shelf_life_months"]), _n(p["storage_low"]), deg, _n(p["storage_high"]), deg),
        "Excursions are permitted from %s%sC to %s%sC." % (_n(p["excursion_low"]), deg, _n(p["excursion_high"]), deg),
        "Stability was demonstrated for %s months at long-term conditions and %s months at accelerated conditions." % (
            _n(p["long_term_months"]), _n(p["accel_months"])),
    ]
    for (cond, attr), f in sorted(p83["demo"].items()):
        head = "%s%s at %s " % (DEMO_LABEL_PREFIX, attr, cond)
        out.append(head + "ranged from %s to %s over %s time points." % (_n(f.min), _n(f.max), _n(f.n)))
        if f.n_outside == 0:
            out.append(head + "had none of its %s results outside the limit." % _n(f.n))
        else:
            out.append(head + "had %s of its %s results outside the limit." % (_n(f.n_outside), _n(f.n)))
    return " ".join(out)


def draft_from_csv(path=F.DEFAULT_CSV):
    """Load the CSV, build the facts and draft the paragraph."""
    return draft_paragraph(F.p83_facts(F.load_rows(path)))
