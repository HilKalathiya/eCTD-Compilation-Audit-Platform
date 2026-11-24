"""T-073 claim rules for the 2.3 writer, worked out from graph rows only: one limit source (R7), outside-limit counts, significant change, and when "demonstrated" and a longer shelf life are allowed.

Sources (stored chunks of the public ICH guidelines, see data/public/SOURCES.md):
  ICH Q1A(R2) page 15, chunk Q1A_R2:p15-c1 / p15-c2: "In general, significant change for a drug product is defined as: 1. A 5% change in assay from its
    initial value ... 2. Any degradation product's exceeding its acceptance criterion; ... 5. Failure to meet the acceptance criteria for dissolution
    for 12 dosage units." (tests we have: Assay, Degradation product, Dissolution; the others of the list have no data here.)
  ICH Q1A(R2) page 15, chunk Q1A_R2:p15-c1: significant change at the accelerated condition makes testing at the intermediate condition necessary.
  ICH Q1E page 8, chunk Q1E:p8-c2: the shelf life may go beyond the long-term data only "with little or no change over time" (extrapolation).
Rules made from them (our reading, stated here so a reviewer can disagree):
  * "Stability was demonstrated for ..." needs at least one long-term group and NO result outside its limit in any long-term or intermediate group.
  * A shelf life longer than the long-term data needs: no long-term / intermediate result outside its limit, AND for every attribute that has data an
    accelerated group exists AND shows no significant change (no accelerated data = no basis for extrapolation, so it is refused).
  * Significant change at 5%: "a 5% change" is read as a change of 5% or more (>=) from the initial (month 0) value; if there is no month 0 result the
    change cannot be judged and it counts as significant (the safe side).
Nothing here is typed as a number for the text: every value is computed (Decimal) from the rows each time.
"""
from decimal import Decimal

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import plan as P

# R7: a stability attribute whose limit is ALSO shown in the 2.3.P.5 table takes its limit from that graph spec fact (never set a second time).
# Only Dissolution maps unambiguously (spec test "Dissolution" = stability attribute "Dissolution (15 min)"). "Degradation product" could be any of the
# impurity rows and "Assay" has no spec fact in the plan, so those two keep the one limit their own stored rows carry (a single source, checked to be consistent).
SPEC_LINK = {"Dissolution (15 min)": "dissolution_av"}
# How Q1A(R2) significant change is judged for each attribute we have.
SIG_RULE = {"Assay": "change", "Degradation product": "criterion", "Dissolution (15 min)": "criterion"}
FIVE_PERCENT = Decimal("0.05")


def groups_in(rows):
    """Sorted [(condition, attribute)] of every stored demo stability group in the graph rows."""
    return sorted({(r["condition"], r["attribute"]) for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo"})


def _grp(rows, cond, attr):
    return MG.group_rows(rows, cond, attr)


def spec_limit_text(rows, attr):
    """The limit text of the linked spec fact ('NLT 80'), or None when the attribute has no link or the graph does not hold the spec fact."""
    sid = G.spec_id(SPEC_LINK[attr]) if attr in SPEC_LINK else None
    if sid is None or sid not in rows:
        return None
    return f"{rows[sid]['limit_kind']} {rows[sid]['value_text']}"


def limit_problems(rows):
    """R7: [reason, ...]. Every group's rows must carry ONE limit, a readable one, and for a linked attribute it must equal the spec fact's limit."""
    out = []
    for cond, attr in groups_in(rows):
        want = spec_limit_text(rows, attr)
        if attr in SPEC_LINK and want is None:
            out.append(f"R7: {attr} takes its limit from the specification fact {G.spec_id(SPEC_LINK[attr])}, which is not in the graph")
            continue
        parsed = {MG.parse_limit(r.get("limit_text", "")) for r in _grp(rows, cond, attr)}
        if None in parsed or not parsed:
            out.append(f"R7: {cond} | {attr} has a stored result with no readable limit")
        elif len(parsed) > 1:
            out.append(f"R7: {cond} | {attr} rows carry different limits")
        elif want is not None and parsed != {MG.parse_limit(want)}:
            out.append(f"R7: {cond} | {attr} counts its results against {sorted(r.get('limit_text', '') for r in _grp(rows, cond, attr))[0]!r} "
                       f"but the specification table shows {want!r} ({G.spec_id(SPEC_LINK[attr])})")
    return out


def outside_count(rows, cond, attr):
    """How many stored results of one group break the limit. A linked attribute uses the spec fact's limit, others their rows' own limit."""
    want = spec_limit_text(rows, attr)
    return sum(1 for r in _grp(rows, cond, attr) if MG.outside(r["value_text"], want if want is not None else r.get("limit_text", "")))


def significant_change(rows, attr):
    """True / False for the accelerated group of this attribute (Q1A(R2) p15); None when the graph holds no accelerated group for it."""
    grp = _grp(rows, P.ACCEL, attr)
    if not grp:
        return None
    rule = SIG_RULE[attr]                                   # an attribute with no rule raises KeyError: nothing is guessed
    if rule == "criterion":
        return outside_count(rows, P.ACCEL, attr) > 0
    first = [r for r in grp if r["month"] != "" and Decimal(r["month"]) == 0]
    if not first:
        return True
    v0 = Decimal(first[0]["value_text"])
    return any(abs(Decimal(r["value_text"]) - v0) >= v0 * FIVE_PERCENT for r in grp)


def outside_id(cond, attr):
    return P.stat_id(cond, attr, "outside_limit_count")


def significant_id(attr):
    return P.stat_id(P.ACCEL, attr, "significant_change")


def derived(rows, fact_id):
    """The value text of a derived claim fact: its outside-limit count, or significant change as '1' / '0'. KeyError for anything else."""
    cond, attr, which = fact_id[len(G.PREFIX + "STAT|"):].split("|")
    if which == "outside_limit_count":
        return str(outside_count(rows, cond, attr))
    if which == "significant_change" and cond == P.ACCEL:
        got = significant_change(rows, attr)
        if got is None:
            raise KeyError(fact_id)
        return "1" if got else "0"
    raise KeyError(fact_id)


def _long_inter(rows):
    return [(c, a) for c, a in groups_in(rows) if c != P.ACCEL]


def study_blockers(rows):
    """[reason, ...] why "Stability was demonstrated" may not be written; [] = allowed."""
    gs = _long_inter(rows)
    if not any(c == P.LONG for c, _ in gs):
        return ["no long-term result is stored, so nothing is demonstrated at long-term conditions"]
    return [f"{c} | {a}: {n} stored result(s) outside the limit" for c, a in gs for n in [outside_count(rows, c, a)] if n]


def extrapolation_blockers(rows):
    """[reason, ...] why a shelf life beyond the long-term data may not be proposed (Q1E p8, Q1A p15); [] = allowed."""
    out = study_blockers(rows)
    for attr in sorted({a for _, a in groups_in(rows)}):
        sig = significant_change(rows, attr)
        if sig is None:
            out.append(f"{attr}: no accelerated result is stored, so a significant change cannot be ruled out")
        elif sig:
            out.append(f"{attr}: significant change at accelerated conditions (Q1A(R2) p15)")
    return out


def study_claim_ids(rows):
    """The derived facts a "demonstrated" sentence depends on: the outside-limit count of every long-term and intermediate group."""
    return [outside_id(c, a) for c, a in _long_inter(rows)]


def extrapolation_claim_ids(rows):
    """The derived facts a shelf life beyond the data depends on: those of study_claim_ids plus the significant-change fact of every attribute."""
    return study_claim_ids(rows) + [significant_id(a) for a in sorted({a for _, a in groups_in(rows)}) if significant_change(rows, a) is not None]


def normalized_rows(rows):
    """A copy of the rows in which each linked attribute's results carry the limit text of the spec fact (so any reader of row limits reads the one source)."""
    out = {k: dict(r) for k, r in rows.items()}
    for r in out.values():
        if r["family"] == "stability" and r["kind"] == "demo":
            want = spec_limit_text(rows, r["attribute"])
            if want is not None:
                r["limit_text"] = want
    return out
