"""Builds the prompt for the T-074 Module 2.3 writer, a TEMPLATE FILLER: the model picks the sentence pattern that is TRUE for the data lines and fills its blanks; code writes every value.

The menu lists EVERY pattern of each sentence kind (T-073 hid the patterns that did not fit the data, so the model could not choose wrongly and the claim and
"demonstrated" gates could never fire). Now the data lines (OUTSIDE LIMIT, DEMONSTRATED, SHELF PROPOSAL) are the only hint: choosing the right pattern is the test.
No digit is ever in the prompt, and no finished sentence: every pattern keeps its <blanks>.
"""
import re

from ectd_engine.summary.m23_prompt3 import INTRO_NOTE, INTRO_PATTERNS, SPEC_WRITE, _pattern

SYSTEM = """You fill sentence patterns for the quality overall summary of a drug regulatory submission. You do not write free text.

Rules you must follow:
A. For every sentence choose exactly ONE pattern from the PATTERNS list of the unit message and fill its <blanks>. Do not change the other words of the pattern.
B. Never write a digit, a number word, a degree sign, a percent sign or a unit. Every value is a placeholder from the FACTS list, written exactly as [[name]]. A placeholder already holds its own unit.
C. Use every placeholder under MUST MENTION, and only in the sentence where it belongs. Write each attribute name exactly as given, with its placeholder if it has one.
D. Add nothing that is not asked: no conclusion, no judgement, no cause, no trend, no source, no words such as stable, robust, meets or complies.
E. The data lines tell you which pattern is TRUE. OUTSIDE LIMIT none: pick a pattern that says no result is outside the limit or that results are within the specification limits. OUTSIDE LIMIT some: pick the pattern that says results were outside the limit. OUTSIDE LIMIT not stated: write no sentence about the limit at all.
F. DEMONSTRATED allowed: you may use a pattern with the word demonstrated or a neutral one. DEMONSTRATED not allowed: never use a pattern with the word demonstrated; use a pattern with the words cover or available.
G. SHELF PROPOSAL blocked: write no sentence about the proposed shelf life or the storage temperature and use no placeholder for them; the code writes a human review notice itself.
H. The demo label is exactly the words "In illustrative demonstration data," and the sentence goes on in lower case. Use it only where WHAT TO WRITE asks for it.
I. Never leave a <blank> or any < > mark in the text: every blank must be filled. Output only the text, as plain text."""

PUBLIC_WRITE = ("WHAT TO WRITE: three sentences without the demo label, in this order: first the proposed shelf life with the storage temperature "
                "range; second the permitted temperature excursions; third how long data cover long-term conditions and accelerated conditions.")
PUBLIC_WRITE_BLOCKED = ("WHAT TO WRITE: two sentences without the demo label, in this order: first the permitted temperature excursions; second how long data "
                        "cover long-term conditions and accelerated conditions. No sentence about the shelf life or the storage temperature.")
RESULT_WRITE = ("WHAT TO WRITE: two sentences, each starting with the demo label: first the range of the stored results; second whether any stored "
                "result was outside the limit, as OUTSIDE LIMIT says.")
RESULT_WRITE_RANGE_ONLY = ("WHAT TO WRITE: one sentence, starting with the demo label: the range of the stored results. Nothing about the limit "
                           "(this attribute has no specification fact).")


def patterns_menu(view):
    """The PATTERNS block of a unit message: every pattern of every sentence kind the unit expects, from review/shapes.py M23D_SHAPES (never filtered by the data)."""
    from ectd_engine.review import shapes as S
    kinds = list(dict.fromkeys(view["expect"]))
    lines = ["PATTERNS (choose exactly one per sentence; write each <name> as the placeholder [[name]]; fill <attribute>, <condition word> and <test name> with "
             "the given words, copied exactly as given, with the same capital letters and without any < >; <limit> is the placeholder of that test; every "
             "sentence ends with a full stop except the test lines):"]
    for k in kinds:
        lines.append(f"{k.replace('_', ' ')}:")
        if k == "spec_intro":
            lines += ["  - " + p for p in INTRO_PATTERNS] + [INTRO_NOTE,
                                                                "  (the blank is only the word these or the word the; it is never a count, so write no number word there)"]   # DEV tuning, dev/run3
        else:
            lines += ["  - " + _pattern(t, sl, False) for _, t, sl, _ in S.M23D_SHAPES[k]]
    return "\n".join(lines)


def unit_message(view):
    """The user message for one unit: only digit-free words from the view."""
    ctx, kind = view["context"], view["kind"]
    lines = [f"UNIT: {'specification' if kind == 'spec' else 'results' if kind == 'result' else 'public'}"]
    if kind == "spec":
        lines += ["TESTS, in this order: " + ", ".join(ctx["tests"]), SPEC_WRITE]
    elif kind == "public":
        blocked = ctx.get("shelf") == "blocked"
        lines += [f"DEMONSTRATED: {ctx['demonstrated']}", f"SHELF PROPOSAL: {'blocked (human review)' if blocked else 'written'}",
                  PUBLIC_WRITE_BLOCKED if blocked else PUBLIC_WRITE]
    else:
        range_only = ctx.get("outside") == "not stated"
        lines += [f"ATTRIBUTE: {ctx['attribute']}", f"CONDITION WORD: {ctx['condition']}", f"OUTSIDE LIMIT: {ctx.get('outside', 'none')}",
                  (RESULT_WRITE_RANGE_ONLY if range_only else RESULT_WRITE) + " Write the whole ATTRIBUTE line in each sentence: every word with its capital letters" +
                  (" and its placeholder in brackets." if "[[" in ctx["attribute"] else ".")]
    lines.append("FACTS:")
    lines += [f"- [[{k}]]: {label}" for k, label in view["slots"].items()]
    lines.append("MUST MENTION: " + ", ".join(f"[[{r}]]" for r in view["required"]))
    lines.append(patterns_menu(view))
    return "\n".join(lines)


def build_messages(view, feedback=()):
    """Chat messages for one unit. view = m23_tasks4.view_of4(unit). feedback = [(earlier draft, [problem, ...]), ...], digits already removed.

    Raises if a digit would be sent: the model must never see one."""
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": unit_message(view)}]
    for draft, problems in feedback:
        msgs.append({"role": "assistant", "content": draft})
        msgs.append({"role": "user", "content": "That draft was rejected. Fix these problems and write the whole text again:\n"
                     + "\n".join("- " + p for p in problems)})
    for m in msgs:
        if re.search(r"\d", m["content"]):
            raise ValueError("a digit is in the prompt; the model must never see one: " + m["content"][:80])
    return msgs
