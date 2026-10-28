"""Build the prompt. The model only writes the short discussion paragraph;
code writes the fixed opening sentence and the data table.
"""
from .facts import fmt

SYSTEM = """You write discussion paragraphs for the stability section (3.2.P.8.3) of a drug regulatory submission.

Rules you must follow:
1. Write one paragraph of 2 to 4 sentences, formal regulatory English, no headings or bullet points.
2. Never write a digit or a number word (such as one, three or thirty). Every value must be a placeholder from the FACTS list, written exactly as [[fact_id]]. The only exception is the attribute name, which you may copy exactly as given.
3. Each placeholder is replaced by its value exactly as listed in FACTS, unit included, so do not write %, months or °C after it. A result placeholder already contains its batch and month; never write a batch or month yourself, and never name a batch in words. Read each sentence with the values in place: it must still be correct English. Write "a mean change of [[mean_change]]", not "a [[mean_change]]", and "[[n_batches]] batches", not "[[n_batches]]" alone.
4. Describe the trend exactly as given in TREND. Never claim a trend the data do not show, and do not describe timing or shape (early, late, then, rapid, levelled off); you are not given that information.
5. State compliance exactly as given in COMPLIANCE. If it is OUT OF SPECIFICATION, state plainly that [[oos_results]] did not meet the acceptance criterion of [[spec]].
6. Use only the facts given. Do not add causes, mechanisms or conclusions about shelf life.
7. Include every placeholder listed under MUST MENTION. Use a role word (highest, lowest, initial, last) only directly next to a placeholder marked with that role in FACTS.
8. Only [[initial_range]] and [[final_range]] are ranges. Never call one result a range, never write "initial results of" or "final results of" before a single result, and describe a change only from [[initial_range]] to [[final_range]]. A range placeholder already ends with its month, so do not add "at Month", "at the last time point" or "[[duration]]" after it. Say that a result, not the condition or a batch, is out of specification.
9. Output only the paragraph."""

EXAMPLE_USER = """ATTRIBUTE: Related compound C
UNIT: %
CONDITION: [[condition]]
FACTS:
- [[condition]]: storage condition = 30°C/65% RH
- [[spec]]: acceptance criterion = NMT 0.30%
- [[initial_range]]: range of initial results, with its time point = 0.05–0.06% at Month 0 [roles: initial]
- [[final_range]]: range of results at the last time point, with its time point = 0.09–0.11% at Month 12 [roles: final]
- [[max_value]]: highest result, with its batch and month = 0.11% (Batch C2, Month 12) [roles: max, final]
TREND: increasing
COMPLIANCE: all results within specification
MUST MENTION: [[spec]], [[max_value]]"""

EXAMPLE_ASSISTANT = ("Related compound C increased at [[condition]], from [[initial_range]] to "
                     "[[final_range]]. The highest result was [[max_value]]. "
                     "All results remained within the acceptance criterion of [[spec]].")

EXAMPLE_USER_OOS = """ATTRIBUTE: Related compound D
UNIT: %
CONDITION: [[condition]]
FACTS:
- [[condition]]: storage condition = 40°C/75% RH
- [[n_batches]]: number of batches = three
- [[spec]]: acceptance criterion = NMT 0.20%
- [[initial_range]]: range of initial results, with its time point = 0.04–0.05% at Month 0 [roles: initial]
- [[final_range]]: range of results at the last time point, with its time point = 0.16–0.23% at Month 6 [roles: final]
- [[max_value]]: highest result, with its batch and month = 0.23% (Batch D1, Month 6) [roles: max, final]
- [[oos_results]]: results outside the acceptance criterion, with batch and month = 0.23% (Batch D1, Month 6) [roles: max, final, oos]
TREND: increasing
COMPLIANCE: OUT OF SPECIFICATION
MUST MENTION: [[spec]], [[max_value]], [[oos_results]]"""

EXAMPLE_ASSISTANT_OOS = ("Related compound D increased in all [[n_batches]] batches at [[condition]], from "
                         "[[initial_range]] to [[final_range]]. The highest result was [[max_value]]. "
                         "The result of [[oos_results]] did not meet the acceptance criterion of [[spec]] "
                         "and is out of specification.")


def data_table(task):
    head = "| Batch | " + " | ".join(f"Month {m}" for m in task["months"]) + " |"
    sep = "|" + "---|" * (len(task["months"]) + 1)
    rows = [f"| {b} | " + " | ".join(fmt(v, task["decimals"]) for v in vals) + " |"
            for b, vals in task["batches"].items()]
    return "\n".join([head, sep] + rows)


def build_messages(task, facts, flags):
    compliance = "all results within specification" if flags["all_within_spec"] else "OUT OF SPECIFICATION"
    def role_note(f):
        roles = sorted(r for r in f.get("roles", ()) if r != "change")
        return f" [roles: {', '.join(roles)}]" if roles else ""
    fact_lines = "\n".join(f"- [[{k}]]: {f['label']} = {f['value']}{role_note(f)}" for k, f in facts.items())
    user = (f"ATTRIBUTE: {task['attribute']}\n"
            f"UNIT: {task['unit']}\n"
            f"CONDITION: [[condition]]\n"
            f"DATA (for your understanding only; do not copy numbers):\n{data_table(task)}\n"
            f"FACTS:\n{fact_lines}\n"
            f"TREND: {flags['trend']}\n"
            f"COMPLIANCE: {compliance}\n"
            f"MUST MENTION: {', '.join(f'[[{r}]]' for r in flags['required'])}")
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": EXAMPLE_USER},
        {"role": "assistant", "content": EXAMPLE_ASSISTANT},
        {"role": "user", "content": EXAMPLE_USER_OOS},
        {"role": "assistant", "content": EXAMPLE_ASSISTANT_OOS},
        {"role": "user", "content": user},
    ]


def opening_sentence(task, facts):
    """Fixed text written by code, not by the model."""
    return (f"Stability data for {facts['n_batches']['value']} batches of {task['product']} stored at "
            f"{facts['condition']['value']} for up to {facts['duration']['value']} are presented below for "
            f"{task['attribute'][0].lower() + task['attribute'][1:]}. "
            f"The acceptance criterion is {facts['spec']['value']}.")
