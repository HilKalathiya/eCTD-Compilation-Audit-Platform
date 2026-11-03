"""Builds the prompt for the batch-analyses paragraph (3.2.P.5.4); the model never sees the results table."""

SYSTEM = """You write one short discussion paragraph for the batch analyses section (3.2.P.5.4) of a drug regulatory submission.

Rules you must follow:
1. Write one paragraph of 2 to 4 sentences, formal regulatory English, no headings or bullet points.
2. Never write a digit or a number word (such as one, three or twelve). Every value must be a placeholder from the FACTS list, written exactly as [[fact_id]]. The only exception is the attribute name, which you may copy exactly as given.
3. A placeholder is replaced by its value exactly as listed in FACTS, unit and batch ids included. Do not write %, "percent", "batch" or "batches" next to a placeholder that already contains them: write "for [[n_batches]]", not "for [[n_batches]] batches".
4. Do not write a batch id or name a batch in words (no "the first batch", "the other batches"). Do not state how many batches in words ("several", "both", "a single"); use [[n_batches]].
5. [[mean_value]] is a mean, never a range: write "with a mean of [[mean_value]]". A range is "from [[min_value]] to [[max_value]]" (lowest first) or [[value_range]]. Use "highest" only next to [[max_value]] and "lowest" only next to [[min_value]].
6. There is no specification for these data. Never write that results comply, meet, pass, fail, are acceptable, are within or outside limits or a specification.
7. If the facts list [[n_excluded]] and [[excluded_batches]], say that those batches were quarantined and are not included, using both placeholders, and keep that out of any sentence that uses [[n_batches]]. If they are not listed, say nothing about exclusion.
8. Use only the facts given. Do not describe trends, variability, causes, comparisons or conclusions. Batches are not in time order.
9. Include every placeholder listed under MUST MENTION.
10. Output only the paragraph."""

EXAMPLE_USER = """ATTRIBUTE: Impurity L
UNIT: %
EXCLUDED BATCHES: none
FACTS:
- [[n_batches]]: number of batches with a result = twelve batches
- [[min_value]]: lowest result, with its batch(es) = 0.05% (Batch 7) [roles: min]
- [[max_value]]: highest result, with its batch(es) = 0.20% (Batches 3 and 9) [roles: max]
- [[value_range]]: range of the results, lowest to highest = 0.05–0.20% [roles: range]
- [[mean_value]]: mean of the results = 0.11% [roles: mean]
MUST MENTION: [[n_batches]], [[min_value]], [[max_value]], [[mean_value]]"""

EXAMPLE_ASSISTANT = ("Impurity L results for [[n_batches]] ranged from [[min_value]] to [[max_value]], "
                     "with a mean of [[mean_value]]. The highest result was [[max_value]] and the lowest result "
                     "was [[min_value]].")

EXAMPLE_USER_EXCLUDED = """ATTRIBUTE: Total impurities
UNIT: %
EXCLUDED BATCHES: yes, quarantined
FACTS:
- [[n_batches]]: number of batches with a result = eleven batches
- [[n_excluded]]: number of batches excluded because their result is quarantined = one batch
- [[excluded_batches]]: the excluded (quarantined) batches = Batch 60
- [[min_value]]: lowest result, with its batch(es) = 0.09% (Batch 3) [roles: min]
- [[max_value]]: highest result, with its batch(es) = 0.36% (Batches 9 and 11) [roles: max]
- [[value_range]]: range of the results, lowest to highest = 0.09–0.36% [roles: range]
- [[mean_value]]: mean of the results = 0.25% [roles: mean]
MUST MENTION: [[n_batches]], [[min_value]], [[max_value]], [[mean_value]], [[n_excluded]], [[excluded_batches]]"""

EXAMPLE_ASSISTANT_EXCLUDED = ("Total impurities were determined for [[n_batches]]. The results covered the range "
                              "[[value_range]], with a mean of [[mean_value]]. The highest result was [[max_value]] "
                              "and the lowest result was [[min_value]]. Results for [[n_excluded]], [[excluded_batches]], "
                              "were quarantined and are not included.")


def build_messages(task, facts, flags):
    """Chat messages for one task. Only the facts (with ids and roles) are shown, never the table."""
    def role_note(f):
        roles = sorted(f.get("roles", ()))
        return f" [roles: {', '.join(roles)}]" if roles else ""
    fact_lines = "\n".join(f"- [[{k}]]: {f['label']} = {f['value']}{role_note(f)}" for k, f in facts.items())
    user = (f"ATTRIBUTE: {task['attribute']}\n"
            f"UNIT: {task['unit']}\n"
            f"EXCLUDED BATCHES: {'yes, quarantined' if flags['n_excluded'] else 'none'}\n"
            f"FACTS:\n{fact_lines}\n"
            f"MUST MENTION: {', '.join(f'[[{r}]]' for r in flags['required'])}")
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": EXAMPLE_USER},
        {"role": "assistant", "content": EXAMPLE_ASSISTANT},
        {"role": "user", "content": EXAMPLE_USER_EXCLUDED},
        {"role": "assistant", "content": EXAMPLE_ASSISTANT_EXCLUDED},
        {"role": "user", "content": user},
    ]


def opening_sentence(task, facts):
    """Fixed text written by code, not by the model."""
    attr = task["attribute"][0].lower() + task["attribute"][1:]
    text = f"Batch analysis results for {attr} of {task['product']} are presented below for {facts['n_batches']['value']}."
    if "n_excluded" in facts:
        text += (f" Results for {facts['n_excluded']['value']} ({facts['excluded_batches']['value']}) "
                 f"are shown as excluded (quarantined).")
    return text
