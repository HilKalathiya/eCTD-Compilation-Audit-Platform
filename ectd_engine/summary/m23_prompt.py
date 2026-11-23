"""Builds the prompt for the Module 2.3 writer: Gemma sees slot names, digit-free labels, plain-words instructions and ONE example from another attribute; never a value, a digit or the answer."""
import re

SYSTEM = """You write one short block of text for the quality overall summary of a drug regulatory submission.

Rules you must follow:
A. Write in plain regulatory wording, short sentences, one statement each. Choose your own wording; do not copy the example. The example is about another attribute and uses other placeholder names, so you must adapt it to the facts you are given.
B. Never write a digit, a number word, a degree sign, a percent sign or a unit. Every value is a placeholder from the FACTS list, written exactly as [[name]]. A placeholder already holds its own unit.
C. Use every placeholder under MUST MENTION, and only in the sentence where it belongs. Write each attribute name exactly as given, with its placeholder if it has one.
D. Add nothing that is not asked: no conclusion, no judgement, no cause, no trend, no source, no words such as stable, robust, meets, complies or demonstrates results.
E. Only the words that regulatory summaries normally use are accepted: for example proposed shelf life, stored at, excursions, permitted, stability, demonstrated, long-term conditions, accelerated conditions, ranged from, between, outside the limit, within the specification limits.
F. Output only the text, as plain text."""

# One example per unit type. Each is about a DIFFERENT attribute, uses DIFFERENT placeholder names and a different condition than any real task,
# so the example text can never be the answer to a task.
SPEC_EXAMPLE = """UNIT: specification
TESTS, in this order: Colour, Hardness
WHAT TO WRITE: the first line is one sentence that starts with the demo label and says that the drug product specification lists the tests and their acceptance criteria. Then one line per test, in the order given: the test name, a colon, the limit kind, then the placeholder. No full stop after these lines.
FACTS:
- [[limit_colour]]: acceptance limit for Colour (NMT)
- [[limit_hardness]]: acceptance limit for Hardness (NLT)
MUST MENTION: [[limit_colour]], [[limit_hardness]]"""
SPEC_ANSWER = ("In illustrative demonstration data, the drug product specification below lists the tests and their acceptance criteria.\n"
               "Colour: NMT [[limit_colour]]\n"
               "Hardness: NLT [[limit_hardness]]")

PUBLIC_EXAMPLE = """UNIT: public
WHAT TO WRITE: three sentences without the demo label, in this order: first the proposed shelf life with the storage temperature range; second the permitted temperature excursions; third how long stability was demonstrated at long-term conditions and at accelerated conditions.
FACTS:
- [[period]]: proposed shelf life in months
- [[cold_end]]: lowest storage temperature
- [[warm_end]]: highest storage temperature
- [[dip]]: lowest permitted excursion temperature
- [[peak]]: highest permitted excursion temperature
- [[slow_run]]: months of stability demonstrated at long-term conditions
- [[fast_run]]: months of stability demonstrated at accelerated conditions
MUST MENTION: [[period]], [[cold_end]], [[warm_end]], [[dip]], [[peak]], [[slow_run]], [[fast_run]]"""
PUBLIC_ANSWER = ("When stored at [[cold_end]] to [[warm_end]], the proposed shelf life is [[period]]. "
                 "Temperature excursions between [[dip]] and [[peak]] are permitted. "
                 "Stability data cover [[slow_run]] at long-term conditions and [[fast_run]] at accelerated conditions.")


def _result_example(outside):
    claim = ("In illustrative demonstration data, no Hardness result under accelerated conditions was outside the limit." if outside == "none"
             else "In illustrative demonstration data, Hardness under accelerated conditions had results outside the limit.")
    return (f"""UNIT: results
ATTRIBUTE: Hardness
CONDITION WORD: accelerated
OUTSIDE LIMIT: {outside}
WHAT TO WRITE: two sentences, each starting with the demo label: first the range of the stored results; second whether any stored result was outside the limit, as OUTSIDE LIMIT says (none = no result outside the limit, some = at least one result outside the limit).
FACTS:
- [[smallest]]: lowest stored result
- [[largest]]: highest stored result
MUST MENTION: [[smallest]], [[largest]]""",
            "In illustrative demonstration data, Hardness under accelerated conditions was between [[smallest]] and [[largest]]. " + claim)


def _timed_result_example(outside):
    claim = ("no Disintegration ([[minutes]]) result under intermediate conditions was outside the limit." if outside == "none"
             else "Disintegration ([[minutes]]) under intermediate conditions had results outside the limit.")
    return (f"""UNIT: results
ATTRIBUTE: Disintegration ([[minutes]])
CONDITION WORD: intermediate
OUTSIDE LIMIT: {outside}
WHAT TO WRITE: two sentences, each starting with the demo label: first the range of the stored results; second whether any stored result was outside the limit, as OUTSIDE LIMIT says (none = no result outside the limit, some = at least one result outside the limit). Write the attribute name exactly as given, with its placeholder.
FACTS:
- [[minutes]]: disintegration time point
- [[shortest]]: lowest stored result
- [[longest]]: highest stored result
MUST MENTION: [[minutes]], [[shortest]], [[longest]]""",
            "In illustrative demonstration data, under intermediate conditions, Disintegration ([[minutes]]) ranged from [[shortest]] to [[longest]]. "
            "In illustrative demonstration data, " + claim)


def example_for(view):
    """(example question, example answer) for a unit: always another attribute, other placeholder names, no value."""
    if view["kind"] == "spec":
        return SPEC_EXAMPLE, SPEC_ANSWER
    if view["kind"] == "public":
        return PUBLIC_EXAMPLE, PUBLIC_ANSWER
    ctx = view["context"]
    outside = ctx.get("outside", "none")
    if "[[tp]]" in ctx.get("attribute", ""):
        return _timed_result_example(outside)
    return _result_example(outside)


def unit_message(view):
    """The user message for one unit: only digit-free words from the view."""
    ctx = view["context"]
    kind = view["kind"]
    lines = [f"UNIT: {'specification' if kind == 'spec' else 'results' if kind == 'result' else 'public'}"]
    if kind == "spec":
        lines.append("TESTS, in this order: " + ", ".join(ctx["tests"]))
        lines.append("WHAT TO WRITE: the first line is one sentence that starts with the demo label and says that the drug product specification "
                     "lists the tests and their acceptance criteria. Then one line per test, in the order given: the test name, a colon, the limit kind, "
                     "then the placeholder. No full stop after these lines.")
    elif kind == "public":
        lines.append("WHAT TO WRITE: three sentences without the demo label, in this order: first the proposed shelf life with the storage temperature "
                     "range; second the permitted temperature excursions; third how long stability was demonstrated at long-term conditions and at "
                     "accelerated conditions.")
    else:
        lines += [f"ATTRIBUTE: {ctx['attribute']}", f"CONDITION WORD: {ctx['condition']}", f"OUTSIDE LIMIT: {ctx.get('outside', 'none')}",
                  "WHAT TO WRITE: two sentences, each starting with the demo label: first the range of the stored results; second whether any stored "
                  "result was outside the limit, as OUTSIDE LIMIT says (none = no result outside the limit, some = at least one result outside the limit)."
                  + (" Write the attribute name exactly as given, with its placeholder." if "[[" in ctx["attribute"] else "")]
    lines.append("FACTS:")
    lines += [f"- [[{k}]]: {label}" for k, label in view["slots"].items()]
    lines.append("MUST MENTION: " + ", ".join(f"[[{r}]]" for r in view["required"]))
    return "\n".join(lines)


def build_messages(view, feedback=()):
    """Chat messages for one unit. view = a task builder's view_of(unit). feedback = [(earlier draft, [problem, ...]), ...], digits already removed.

    Raises if a digit would be sent: the model must never see one."""
    q, a = example_for(view)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}, {"role": "assistant", "content": a},
            {"role": "user", "content": unit_message(view)}]
    for draft, problems in feedback:
        msgs.append({"role": "assistant", "content": draft})
        msgs.append({"role": "user", "content": "That draft was rejected. Fix these problems and write the whole text again:\n"
                     + "\n".join("- " + p for p in problems)})
    for m in msgs:
        if re.search(r"\d", m["content"]):
            raise ValueError("a digit is in the prompt; the model must never see one: " + m["content"][:80])
    return msgs
