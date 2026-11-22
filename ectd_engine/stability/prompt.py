"""Builds the prompt for the P.8.3 stability paragraph: the model sees fact ids and labels and writes [[slot]] placeholders only."""

SYSTEM = """You write one short paragraph for the stability section (3.2.P.8.3) of a drug regulatory submission.

Rules you must follow:
1. Use ONLY the sentence forms shown in the examples, word for word. Only the [[placeholders]] stay as they are; code fills them in. Do not add, drop, reorder or reword any sentence.
2. Never write a digit, a number word, a degree sign or a unit. Every value, name and unit is a placeholder from the FACTS list, written exactly as [[fact_id]].
3. For KIND "demonstration data", every sentence starts with exactly: "In illustrative demonstration data, ". For KIND "public facts", NO sentence has that start or any other added words: copy the three example sentences exactly.
4. Write no conclusion: not "stable", "no significant change", "meets", "complies", "within specification", no trend, no cause, no source.
5. Include every placeholder listed under MUST MENTION. Use only ids from the FACTS list.
6. Output only the paragraph, as plain text."""

PUBLIC_EXAMPLE = """KIND: public facts
FACTS:
- [[shelf_life_months]]: proposed shelf life in months = 24
- [[storage_low]]: lowest storage temperature = 2°C
- [[storage_high]]: highest storage temperature = 8°C
- [[excursion_low]]: lowest permitted excursion temperature = 5°C
- [[excursion_high]]: highest permitted excursion temperature = 40°C
- [[long_term_months]]: months studied at long-term conditions = 24
- [[accel_months]]: months studied at accelerated conditions = 3
MUST MENTION: [[shelf_life_months]], [[storage_low]], [[storage_high]], [[excursion_low]], [[excursion_high]], [[long_term_months]], [[accel_months]]"""

PUBLIC_ANSWER = ("The proposed shelf life is [[shelf_life_months]] months when stored at [[storage_low]] to [[storage_high]]. "
                 "Excursions are permitted from [[excursion_low]] to [[excursion_high]]. "
                 "Stability was demonstrated for [[long_term_months]] months at long-term conditions and "
                 "[[accel_months]] months at accelerated conditions.")

DEMO_EXAMPLE = """KIND: demonstration data, none outside the limit
FACTS:
- [[attribute]]: attribute name = Colour
- [[condition]]: storage condition = Zone A
- [[min]]: lowest result = 1.5
- [[max]]: highest result = 2.5
- [[n]]: number of time points = 6
MUST MENTION: [[attribute]], [[condition]], [[min]], [[max]], [[n]]"""

DEMO_ANSWER = ("In illustrative demonstration data, [[attribute]] at [[condition]] ranged from [[min]] to [[max]] over [[n]] time points. "
               "In illustrative demonstration data, [[attribute]] at [[condition]] had none of its [[n]] results outside the limit.")

DEMO_OUT_EXAMPLE = """KIND: demonstration data, some outside the limit
FACTS:
- [[attribute]]: attribute name = Colour
- [[condition]]: storage condition = Zone A
- [[min]]: lowest result = 1.5
- [[max]]: highest result = 2.5
- [[n]]: number of time points = 6
- [[n_outside]]: number of results outside the limit = 2
MUST MENTION: [[attribute]], [[condition]], [[min]], [[max]], [[n]], [[n_outside]]"""

DEMO_OUT_ANSWER = ("In illustrative demonstration data, [[attribute]] at [[condition]] ranged from [[min]] to [[max]] over [[n]] time points. "
                   "In illustrative demonstration data, [[attribute]] at [[condition]] had [[n_outside]] of its [[n]] results outside the limit.")


def _examples(task):
    """The one or two worked examples that match this task's kind."""
    if task["kind"] == "public":
        return [(PUBLIC_EXAMPLE, PUBLIC_ANSWER)]
    if "n_outside" in task["slots"]:
        return [(DEMO_OUT_EXAMPLE, DEMO_OUT_ANSWER)]
    return [(DEMO_EXAMPLE, DEMO_ANSWER)]


def kind_label(task):
    """The KIND line text for a task."""
    if task["kind"] == "public":
        return "public facts"
    return "demonstration data, some outside the limit" if "n_outside" in task["slots"] else "demonstration data, none outside the limit"


def build_messages(task, feedback=()):
    """Chat messages for one task. feedback = [(earlier draft, [problem, ...]), ...]; each is sent back so a retry can fix it."""
    lines = "\n".join(f"- [[{k}]]: {s['label']} = {s['value']}" for k, s in task["slots"].items())
    user = f"KIND: {kind_label(task)}\nFACTS:\n{lines}\nMUST MENTION: {', '.join(f'[[{r}]]' for r in task['required'])}"
    msgs = [{"role": "system", "content": SYSTEM}]
    for q, a in _examples(task):
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": user})
    for draft, problems in feedback:
        msgs.append({"role": "assistant", "content": draft})
        msgs.append({"role": "user", "content": "That draft was rejected. Fix these problems and write the whole paragraph again, "
                     "using only the sentence forms from the examples:\n" + "\n".join("- " + p for p in problems)})
    return msgs
