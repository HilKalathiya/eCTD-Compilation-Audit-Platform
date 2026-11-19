"""Builds the prompt for the P.5.6 justification paragraph; the model sees fact ids and labels, never the Q3B text itself."""

SYSTEM = """You write one short justification paragraph for ONE acceptance criterion in the specification section (3.2.P.5.6) of a drug regulatory submission.

Rules you must follow:
1. Write exactly 3 sentences, formal English, no headings or bullet points. Sentence 1 gives the limit and what it rests on and names the attribute exactly as given. Sentence 2 gives the range of results. Sentence 3 gives how many results were outside the limit. Follow the two examples exactly (with [[mdd]], put [[q3b_quote]] after a colon at the end of sentence 1).
2. Never write a digit or a number word. Every value is a placeholder from the FACTS list, written exactly as [[fact_id]].
3. Write the limit as "[[limit_kind]] [[limit]]": always together, in that order. Never write NMT, NLT, "not more than", "at least" or any other direction yourself.
4. State what the limit rests on with [[basis]], worded exactly as in the examples: "set at [[basis]] for an assumed maximum daily dose of [[mdd]]" when [[mdd]] is listed, otherwise "which is [[basis]]". Never write "resting on [[basis]]", "based on [[basis]]" or "set [[basis]]". Do not add any other source, standard, guideline, pharmacopoeia, requirement or study. Never write "per", "in accordance with" or "in line with".
5. If the facts list [[mdd]]: the dose is an ASSUMPTION. Say so with the word "assumed" in the SAME sentence as [[mdd]]. Put [[q3b_quote]] in the paragraph; code fills in the quoted text and page. Never type any words of the quote.
6. If the facts do not list [[mdd]] and [[q3b_quote]], do not mention a dose, Q3B or any quote.
7. Do not write that anything is safe, qualified, toxicologically justified or without concern. You do not judge safety.
8. Write "Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]". Do not write "batch" or "batches" next to [[n_batches]] or [[n_outside]], and do not write "all batches".
9. Sentence 3 is required. If the facts list [[n_outside]], write exactly: "[[n_outside]] of [[n_batches]] results were outside the limit." If they do not list it, write exactly: "No result was outside the limit." Never write that results comply, meet, pass or are within the limit.
10. Use only the facts given. No trends, variability, causes or conclusions.
11. Include every placeholder listed under MUST MENTION.
12. Output only the paragraph."""

EXAMPLE_Q3B = """ATTRIBUTE: Impurity X
FACTS:
- [[limit_kind]]: direction of the limit = not more than
- [[limit]]: the acceptance limit = 0.5%
- [[basis]]: what the limit rests on = the ICH Q3B(R2) qualification threshold
- [[n_batches]]: number of batches with a result = 9 batches
- [[min_value]]: lowest result = 0.1% [roles: min]
- [[max_value]]: highest result = 0.4% [roles: max]
- [[mdd]]: maximum daily dose; an ASSUMPTION, not a source value = 40 mg
- [[q3b_quote]]: the Q3B text and page the limit comes from = (quoted text, page)
MUST MENTION: [[limit_kind]], [[limit]], [[basis]], [[n_batches]], [[min_value]], [[max_value]], [[mdd]], [[q3b_quote]]"""

EXAMPLE_Q3B_ANSWER = ("The acceptance criterion for Impurity X is [[limit_kind]] [[limit]], set at [[basis]] for an assumed "
                      "maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] "
                      "to [[max_value]]. No result was outside the limit.")

EXAMPLE_DECLARED = """ATTRIBUTE: Assay Y
FACTS:
- [[limit_kind]]: direction of the limit = not less than
- [[limit]]: the acceptance limit = 90%
- [[basis]]: what the limit rests on = declared by the author for this demonstration, with no public source
- [[n_batches]]: number of batches with a result = 7 batches
- [[min_value]]: lowest result = 91%  [roles: min]
- [[max_value]]: highest result = 99% [roles: max]
- [[n_outside]]: number of batches with a result outside the limit = 2 batches
MUST MENTION: [[limit_kind]], [[limit]], [[basis]], [[n_batches]], [[min_value]], [[max_value]], [[n_outside]]"""

EXAMPLE_DECLARED_ANSWER = ("The acceptance criterion for Assay Y is [[limit_kind]] [[limit]], which is [[basis]]. "
                           "Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. "
                           "[[n_outside]] of [[n_batches]] results were outside the limit.")


def build_messages(task, facts, flags):
    """Chat messages for one task. Only the facts (with ids and roles) are shown."""
    def role_note(f):
        roles = sorted(f.get("roles", ()))
        return f" [roles: {', '.join(roles)}]" if roles else ""
    fact_lines = "\n".join(f"- [[{k}]]: {f['label']} = {f['value'] if k != 'q3b_quote' else '(quoted text, page)'}{role_note(f)}"
                           for k, f in facts.items())
    user = (f"ATTRIBUTE: {task['attribute']}\nFACTS:\n{fact_lines}\n"
            f"MUST MENTION: {', '.join(f'[[{r}]]' for r in flags['required'])}")
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": EXAMPLE_Q3B}, {"role": "assistant", "content": EXAMPLE_Q3B_ANSWER},
        {"role": "user", "content": EXAMPLE_DECLARED}, {"role": "assistant", "content": EXAMPLE_DECLARED_ANSWER},
        {"role": "user", "content": user},
    ]
