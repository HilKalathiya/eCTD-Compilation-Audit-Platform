"""T-074 claim rules for the 2.3 writer: EVERY stability group takes its limit from ONE graph spec fact (R7), and bad data goes to human review.

links = {(condition, attribute): spec fact id or None}, read from the task file (ids only). A group with a link is counted against that spec fact's limit
and may carry a within/outside-limit claim. A group with no link (the real Kerendia Assay and Degradation product have no public spec fact) keeps the one
limit its own stored rows carry, but it is used ONLY to block ("demonstrated", extrapolation, review route), never to write a within/outside claim.
A group whose limit cannot be read is UNKNOWN: it blocks "demonstrated" and extrapolation; it is never counted as "zero outside" (T-073 did that).
Review route (item 3 of the T-074 card): if any long-term or intermediate result is outside its limit, code blocks every shelf-life proposal sentence and
writes the 2.3.P.8 marker "HUMAN REVIEW REQUIRED: <reason>" linked (data-src) to the outside-limit counts that caused it.
Everything is Decimal and worked out from the rows each time. Sources of the rules: ICH Q1A(R2) p15 (Q1A_R2:p15-c1/c2), ICH Q1E p8 (Q1E:p8-c2); see m23_rules.
"""
from decimal import Decimal

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_rules as R0
from ectd_engine.summary import plan as P

SIG_RULE, FIVE_PERCENT = R0.SIG_RULE, R0.FIVE_PERCENT
outside_id, significant_id, groups_in = R0.outside_id, R0.significant_id, R0.groups_in


class LimitUnknown(Exception):
    """The limit of a group cannot be read (no link and no single readable limit in its rows)."""


def links_of(task):
    """{(condition, attribute): spec fact id or None} from a task file."""
    return {(g["condition"], g["attribute"]): g.get("spec_fact") for g in task["results"]}


def spec_limit_text(rows, fact_id):
    """'NLT 80' from a spec fact row, or None when the graph does not hold it."""
    r = rows.get(fact_id) if fact_id else None
    return None if r is None else f"{r['limit_kind']} {r['value_text']}"


def limit_of(rows, links, cond, attr):
    """The parsed limit (low, high) of one group: the linked spec fact's, else the single readable limit of its own rows; None = unknown."""
    fid = links.get((cond, attr))
    if fid:
        text = spec_limit_text(rows, fid)
        return MG.parse_limit(text) if text else None
    parsed = {MG.parse_limit(r.get("limit_text", "")) for r in MG.group_rows(rows, cond, attr)}
    return next(iter(parsed)) if len(parsed) == 1 and None not in parsed else None


def _breaks(value_text, lim):
    v = Decimal(value_text)
    return (lim[0] is not None and v < lim[0]) or (lim[1] is not None and v > lim[1])


def outside_count(rows, links, cond, attr):
    """How many stored results of one group break its limit. Raises LimitUnknown when the limit is unknown (never 0 by default)."""
    lim = limit_of(rows, links, cond, attr)
    if lim is None:
        raise LimitUnknown(f"{cond} | {attr}")
    return sum(1 for r in MG.group_rows(rows, cond, attr) if _breaks(r["value_text"], lim))


def limit_problems(rows, links):
    """R7: [reason, ...]. A linked group's spec fact must be in the graph and every stored row of the group must carry exactly its limit;
    an unlinked group must carry one readable limit. [] = ok."""
    out = []
    for cond, attr in groups_in(rows):
        fid = links.get((cond, attr))
        if (cond, attr) not in links:
            out.append(f"R7: {cond} | {attr} has no entry in the task's links")
            continue
        grp = MG.group_rows(rows, cond, attr)
        parsed = {MG.parse_limit(r.get("limit_text", "")) for r in grp}
        if fid:
            want = spec_limit_text(rows, fid)
            if want is None:
                out.append(f"R7: {cond} | {attr} takes its limit from {fid}, which is not in the graph")
            elif parsed != {MG.parse_limit(want)}:
                out.append(f"R7: {cond} | {attr} rows carry the limit {sorted({r.get('limit_text', '') for r in grp})} but {fid} says {want!r}")
        elif None in parsed or len(parsed) != 1:
            out.append(f"R7: {cond} | {attr} has no spec fact and its rows do not carry one readable limit")
    return out


def claim_allowed(links, cond, attr):
    """A within/outside-limit sentence may be written only for a group with a spec fact."""
    return bool(links.get((cond, attr)))


def significant_change(rows, links, attr):
    """Q1A(R2) p15 at the accelerated condition: True / False, None when no accelerated group exists. An unknown limit counts as significant (safe side)."""
    grp = MG.group_rows(rows, P.ACCEL, attr)
    if not grp:
        return None
    rule = SIG_RULE[attr]
    if rule == "criterion":
        try:
            return outside_count(rows, links, P.ACCEL, attr) > 0
        except LimitUnknown:
            return True
    first = [r for r in grp if r["month"] != "" and Decimal(r["month"]) == 0]
    if not first:
        return True
    v0 = Decimal(first[0]["value_text"])
    return any(abs(Decimal(r["value_text"]) - v0) >= v0 * FIVE_PERCENT for r in grp)


def derived(rows, links, fact_id):
    """The value text of a derived claim fact (outside-limit count, or significant change as '1' / '0'). KeyError for anything else."""
    cond, attr, which = fact_id[len(G.PREFIX + "STAT|"):].split("|")
    if which == "outside_limit_count":
        return str(outside_count(rows, links, cond, attr))
    if which == "significant_change" and cond == P.ACCEL:
        got = significant_change(rows, links, attr)
        if got is None:
            raise KeyError(fact_id)
        return "1" if got else "0"
    raise KeyError(fact_id)


def _long_inter(rows):
    return [(c, a) for c, a in groups_in(rows) if c != P.ACCEL]


def review_reasons(rows, links):
    """[(condition, attribute, count)] for every long-term / intermediate group with a result outside its limit. Non-empty = the review route."""
    out = []
    for c, a in _long_inter(rows):
        try:
            n = outside_count(rows, links, c, a)
        except LimitUnknown:
            continue                                   # unknown is a blocker for claims, not a review trigger (the card says: result outside its limit)
        if n:
            out.append((c, a, n))
    return out


def review_ids(rows, links):
    """The derived facts the review marker is linked to."""
    return [outside_id(c, a) for c, a, _ in review_reasons(rows, links)]


def study_blockers(rows, links):
    """[reason, ...] why "Stability was demonstrated" may not be written; [] = allowed."""
    gs = _long_inter(rows)
    if not any(c == P.LONG for c, _ in gs):
        return ["no long-term result is stored, so nothing is demonstrated at long-term conditions"]
    out = []
    for c, a in gs:
        try:
            n = outside_count(rows, links, c, a)
        except LimitUnknown:
            out.append(f"{c} | {a}: the limit is unknown, so no result can be called inside it")
            continue
        if n:
            out.append(f"{c} | {a}: {n} stored result(s) outside the limit")
    return out


def extrapolation_blockers(rows, links):
    """[reason, ...] why a shelf life beyond the long-term data may not be proposed (Q1E p8, Q1A p15); [] = allowed."""
    out = study_blockers(rows, links)
    for attr in sorted({a for _, a in groups_in(rows)}):
        sig = significant_change(rows, links, attr)
        if sig is None:
            out.append(f"{attr}: no accelerated result is stored, so a significant change cannot be ruled out")
        elif sig:
            out.append(f"{attr}: significant change at accelerated conditions (Q1A(R2) p15)")
    return out


def bad_data_to_writer(rows, links):
    """Which kind of bad data the writer is shown: 'review' (long-term/intermediate result outside its limit), 'significant_change' (accelerated, no
    extrapolation), 'outside_accelerated' (an accelerated result outside its limit only) or None. Used to count the bad-data tasks of a set."""
    if review_reasons(rows, links):
        return "review"
    accel = [a for c, a in groups_in(rows) if c == P.ACCEL]
    if any(_safe_outside(rows, links, P.ACCEL, a) > 0 for a in accel):
        return "outside_accelerated"
    if any(significant_change(rows, links, a) for a in {a for _, a in groups_in(rows)}):
        return "significant_change"
    return None


def _safe_outside(rows, links, cond, attr):
    try:
        return outside_count(rows, links, cond, attr)
    except LimitUnknown:
        return 0
