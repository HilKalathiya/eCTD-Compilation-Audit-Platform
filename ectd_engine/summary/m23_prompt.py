"""Builds the prompt for the Module 2.3 writer: Gemma sees slot names, digit-free labels and sentence forms, never a value and never a digit."""
import re

SYSTEM = """You write one short block of text for the quality overall summary of a drug regulatory submission.

Rules you must follow:
A. Use ONLY the sentence forms shown in the example for the same UNIT, word for word. Only the words given under ATTRIBUTE, CONDITION WORD or TESTS may change. Do not add, drop, reorder or reword any sentence.
B. Never write a digit, a number word, a degree sign, a percent sign or a unit. Every value is a placeholder from the FACTS list, written exactly as [[name]]. A placeholder already holds its own unit.
C. Use every placeholder under MUST MENTION exactly once, in the place the example shows for it.
D. For UNIT results and UNIT specification, the sentences start with exactly: "In illustrative demonstration data, " (the first sentence only for the specification). For UNIT public, no sentence has that start.
E. Write no conclusion and no claim: not "stable", "no change", "meets", "complies", "demonstrates", no trend, no cause, no source.
F. Output only the text, as plain text."""

SPEC_EXAMPLE = """UNIT: specification
TESTS, in this order: Colour, Hardness
FACTS:
- [[spec_colour]]: acceptance limit for Colour (NMT)
- [[spec_hardness]]: acceptance limit for Hardness (NLT)
MUST MENTION: [[spec_colour]], [[spec_hardness]]"""
SPEC_ANSWER = ("In illustrative demonstration data, the drug product specification lists these tests and acceptance criteria.\n"
               "Colour: NMT [[spec_colour]]\n"
               "Hardness: NLT [[spec_hardness]]")

PUBLIC_EXAMPLE = """UNIT: public
FACTS:
- [[shelf]]: proposed shelf life in months
- [[st_low]]: lowest storage temperature
- [[st_high]]: highest storage temperature
- [[ex_low]]: lowest permitted excursion temperature
- [[ex_high]]: highest permitted excursion temperature
- [[long]]: months of stability demonstrated at long-term conditions
- [[accel]]: months of stability demonstrated at accelerated conditions
MUST MENTION: [[shelf]], [[st_low]], [[st_high]], [[ex_low]], [[ex_high]], [[long]], [[accel]]"""
PUBLIC_ANSWER = ("The proposed shelf life is [[shelf]] when stored at [[st_low]] to [[st_high]]. "
                 "Excursions are permitted from [[ex_low]] to [[ex_high]]. "
                 "Stability was demonstrated for [[long]] at long-term conditions and [[accel]] at accelerated conditions.")

RESULT_EXAMPLE = """UNIT: results
ATTRIBUTE: Assay
CONDITION WORD: intermediate
FACTS:
- [[low]]: lowest stored result
- [[high]]: highest stored result
MUST MENTION: [[low]], [[high]]"""
RESULT_ANSWER = "In illustrative demonstration data, Assay under intermediate conditions ranged from [[low]] to [[high]]."

EXAMPLES = {"spec": (SPEC_EXAMPLE, SPEC_ANSWER), "public": (PUBLIC_EXAMPLE, PUBLIC_ANSWER), "result": (RESULT_EXAMPLE, RESULT_ANSWER)}


def unit_message(view):
    """The user message for one unit: only digit-free words from the view."""
    ctx = view["context"]
    lines = [f"UNIT: {'specification' if view['kind'] == 'spec' else 'results' if view['kind'] == 'result' else 'public'}"]
    if view["kind"] == "spec":
        lines.append("TESTS, in this order: " + ", ".join(ctx["tests"]))
    if view["kind"] == "result":
        lines += [f"ATTRIBUTE: {ctx['attribute']}", f"CONDITION WORD: {ctx['condition']}"]
    if view["kind"] == "result":
        lines.append(f"WRITE EXACTLY THIS FORM (the words are already filled in for this unit): In illustrative demonstration data, "
                     f"{ctx['attribute']} under {ctx['condition']} conditions ranged from [[low]] to [[high]].")
    lines.append("FACTS:")
    lines += [f"- [[{k}]]: {label}" for k, label in view["slots"].items()]
    lines.append("MUST MENTION: " + ", ".join(f"[[{r}]]" for r in view["required"]))
    return "\n".join(lines)


def build_messages(view, feedback=()):
    """Chat messages for one unit. view = m23_tasks.view_of(unit). feedback = [(earlier draft, [problem, ...]), ...], digits already removed.

    Raises if a digit would be sent: the model must never see one."""
    q, a = EXAMPLES[view["kind"]]
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}, {"role": "assistant", "content": a},
            {"role": "user", "content": unit_message(view)}]
    for draft, problems in feedback:
        msgs.append({"role": "assistant", "content": draft})
        msgs.append({"role": "user", "content": "That draft was rejected. Fix these problems and write the whole text again, "
                     "using only the sentence forms from the example:\n" + "\n".join("- " + p for p in problems)})
    for m in msgs:
        if re.search(r"\d", m["content"]):
            raise ValueError("a digit is in the prompt; the model must never see one: " + m["content"][:80])
    return msgs
