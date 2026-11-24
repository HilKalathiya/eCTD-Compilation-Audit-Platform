"""Builds the prompt for the T-073 Module 2.3 writer: slot names, digit-free labels, plain-words rules; NO few-shot example, so no answer sentence is in the prompt.

T-072 showed one allowed sentence inside its spec example (copied 20 of 20 times) and example sentences whose wording was still an accepted shape. Here the
structure is described in words (WHAT TO WRITE) and Gemma chooses its own wording from the closed list of regulatory phrases in rule E.
"""
import re

SYSTEM = """You write one short block of text for the quality overall summary of a drug regulatory submission.

Rules you must follow:
A. Write in plain regulatory wording, short sentences, one statement each. Each sentence must follow one of the ALLOWED WORDINGS listed for it in the unit message; you choose which one.
B. Never write a digit, a number word, a degree sign, a percent sign or a unit. Every value is a placeholder from the FACTS list, written exactly as [[name]]. A placeholder already holds its own unit.
C. Use every placeholder under MUST MENTION, and only in the sentence where it belongs. Write each attribute name exactly as given, with its placeholder if it has one.
D. Add nothing that is not asked: no conclusion, no judgement, no cause, no trend, no source, no words such as stable, robust, meets or complies. The word demonstrated is allowed only when the line DEMONSTRATED says allowed.
E. Only the words that regulatory summaries normally use are accepted: for example proposed shelf life, stored at, excursions, permitted, stability, data cover, data are available, long-term conditions, accelerated conditions, ranged from, between, outside the limit, within the specification limits.
F. The demo label is exactly the words "In illustrative demonstration data," and the sentence goes on in lower case. Use it only where WHAT TO WRITE asks for it.
G. DEMONSTRATED: not allowed means the data do not support that word: say only that stability data cover, or data are available for, the periods.
H. Output only the text, as plain text."""

PUBLIC_WRITE = ("WHAT TO WRITE: three sentences without the demo label, in this order: first the proposed shelf life with the storage temperature "
                "range; second the permitted temperature excursions; third how long data cover long-term conditions and accelerated conditions.")
RESULT_WRITE = ("WHAT TO WRITE: two sentences, each starting with the demo label: first the range of the stored results; second whether any stored "
                "result was outside the limit, as OUTSIDE LIMIT says (none = no result outside the limit, some = at least one result outside the limit).")
SPEC_WRITE = ("WHAT TO WRITE: the first line is one short sentence that starts with the demo label and introduces the table that follows; "
              "it names the drug product specification, its tests and their acceptance criteria, and it ends with a full stop. Then one line per test, in the order given: "
              "the test name, a colon, the limit kind, then the placeholder. No full stop after these lines.")


# DEV tuning (T-073, after dev/run1 scored 0/10: with no wording guidance Gemma almost never hit the closed list): each unit message now lists the
# ALLOWED WORDINGS of its sentence kinds as PATTERNS with blanks <like this>. A pattern is not a sentence of the answer: its blanks are not [[placeholders]]
# and not words, so it fails every gate until the model fills it. It is, however, the closed list itself, so the copy rate after blanking names is high by design.
INTRO_PATTERNS = ["In illustrative demonstration data, the drug product specification lists <word-a> tests and acceptance criteria.",
                  "In illustrative demonstration data, the drug product specification below lists <word-b> tests and their acceptance criteria."]
INTRO_NOTE = "  (<word-a> is the word these; <word-b> is the word the)"       # DEV tuning after dev/run4: the one-line a|b form was garbled by the model


def _pattern(template, slots, units_has_tp):
    """A wording of the closed list with every field turned into a <blank>."""
    names = iter([s for s in slots if s != "attr"])

    def sub(m):
        f = m.group(1)
        return {"s": lambda: f"<{next(names, 'its placeholder')}>", "attr": lambda: "<attribute>", "cond": lambda: "<condition word>",
                "test": lambda: "<test name>", "kind": lambda: "<NMT or NLT>"}[f]()
    return re.sub(r"\{(s|test|attr|cond|kind)\}", sub, template)


def wording_menu(view):
    """The ALLOWED WORDINGS block of a unit message, built from review/shapes.py M23C_SHAPES (so the menu and the gate can never differ)."""
    from ectd_engine.review import shapes as S
    ctx, kind = view["context"], view["kind"]
    kinds = {"spec": ["spec_intro", "spec_row"], "public": ["shelf", "excursion", "study"], "result": ["range", "claim"]}[kind]
    lines = ["ALLOWED WORDINGS (use exactly one per sentence; write each <name> as the placeholder [[name]]; fill <attribute>, <condition word> and <test name> with the given words, copied exactly as given, with the same capital letters and without any < >; <limit> is the placeholder of that test; every sentence ends with a full stop except the test lines):"]
    for k in kinds:
        shapes = S.M23C_SHAPES[k]
        if k == "claim":
            shapes = [s for s in shapes if s[3] == ("zero" if ctx.get("outside", "none") == "none" else "some")]
        if k == "study" and ctx.get("demonstrated") == "not allowed":
            shapes = [s for s in shapes if s[3] is None]
        lines.append(f"{k.replace('_', ' ')}:")
        if k == "spec_intro":
            lines += ["  - " + p for p in INTRO_PATTERNS] + [INTRO_NOTE]
        else:
            lines += ["  - " + _pattern(t, sl, False) for _, t, sl, _ in shapes]
    return "\n".join(lines)


def unit_message(view):
    """The user message for one unit: only digit-free words from the view."""
    ctx = view["context"]
    kind = view["kind"]
    lines = [f"UNIT: {'specification' if kind == 'spec' else 'results' if kind == 'result' else 'public'}"]
    if kind == "spec":
        lines += ["TESTS, in this order: " + ", ".join(ctx["tests"]), SPEC_WRITE]
    elif kind == "public":
        lines += [f"DEMONSTRATED: {ctx['demonstrated']}", PUBLIC_WRITE]
    else:
        lines += [f"ATTRIBUTE: {ctx['attribute']}", f"CONDITION WORD: {ctx['condition']}", f"OUTSIDE LIMIT: {ctx.get('outside', 'none')}",
                  RESULT_WRITE + " Write the whole ATTRIBUTE line in each sentence: every word with its capital letters" +
                  (" and its placeholder in brackets." if "[[" in ctx["attribute"] else ".")]
    lines.append("FACTS:")
    lines += [f"- [[{k}]]: {label}" for k, label in view["slots"].items()]
    lines.append("MUST MENTION: " + ", ".join(f"[[{r}]]" for r in view["required"]))
    lines.append(wording_menu(view))
    return "\n".join(lines)


def build_messages(view, feedback=()):
    """Chat messages for one unit. view = a task builder's view_of(unit). feedback = [(earlier draft, [problem, ...]), ...], digits already removed.

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
