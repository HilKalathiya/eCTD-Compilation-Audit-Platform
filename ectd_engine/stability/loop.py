"""The P.8.3 writing loop: build one task per public paragraph and per condition x attribute, ask the model, check, retry with feedback, render."""
import re
from collections import Counter

from ectd_engine.stability.prompt import build_messages
from ectd_engine.validator import stability as V

MAX_DRAFTS = 4
SEED = 42
PH = re.compile(r"\[\[([a-z_]+)\]\]")
NUMBER_WORDS = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
                          r"hundred|dozen|half|percent)\b", re.I)
DEGREE_SIGNS = "°º˚"
PUBLIC_NEEDED = ["shelf_life", "excursion", "study_length"]


def _s(x):
    return str(x)


def slug(text):
    """Letters and digits only, for task ids and file names."""
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def make_tasks(p83):
    """Tasks from the facts: first 'p83_public', then one 'demo_<condition>_<attribute>' per demonstration group (sorted).

    Each task = {"task_id", "kind", "slots": {id: {"label", "value"}}, "required": [ids], "_facts": the facts the checker uses}.
    Values are text made here by code (str of a Decimal); the model never sees a chance to type one."""
    pub, deg = p83["public"], "°C"
    slots = {
        "shelf_life_months": ("proposed shelf life in months", _s(pub["shelf_life_months"])),
        "storage_low": ("lowest storage temperature", _s(pub["storage_low"]) + deg),
        "storage_high": ("highest storage temperature", _s(pub["storage_high"]) + deg),
        "excursion_low": ("lowest permitted excursion temperature", _s(pub["excursion_low"]) + deg),
        "excursion_high": ("highest permitted excursion temperature", _s(pub["excursion_high"]) + deg),
        "long_term_months": ("months studied at long-term conditions", _s(pub["long_term_months"])),
        "accel_months": ("months studied at accelerated conditions", _s(pub["accel_months"])),
    }
    tasks = [{"task_id": "p83_public", "kind": "public",
              "slots": {k: {"label": a, "value": b} for k, (a, b) in slots.items()}, "required": list(slots),
              "_facts": {"public": pub, "demo": {}}}]
    for (cond, attr), f in sorted(p83["demo"].items()):
        s = {"attribute": ("attribute name", attr), "condition": ("storage condition", cond),
             "min": ("lowest result", _s(f.min)), "max": ("highest result", _s(f.max)), "n": ("number of time points", _s(f.n))}
        if f.n_outside:
            s["n_outside"] = ("number of results outside the limit", _s(f.n_outside))
        tasks.append({"task_id": "demo_%s_%s" % (slug(cond), slug(attr)), "kind": "demo",
                      "slots": {k: {"label": a, "value": b} for k, (a, b) in s.items()}, "required": list(s),
                      "key": [cond, attr], "_facts": {"public": pub, "demo": {(cond, attr): f}}})
    ids = [t["task_id"] for t in tasks]
    assert len(ids) == len(set(ids)), "task ids must be unique"
    return tasks


def task_view(task):
    """The task without its private parts (what is saved to tasks.json and given to a fake model)."""
    return {k: v for k, v in task.items() if not k.startswith("_")}


def render_sentence(sentence, task):
    """Replace every [[id]] with its value; code writes the numbers."""
    return PH.sub(lambda m: task["slots"][m.group(1)]["value"], sentence)


def needed_codes(task):
    """The sentence shapes a finished paragraph must hold, once each."""
    if task["kind"] == "public":
        return list(PUBLIC_NEEDED)
    return ["demo_range", "demo_some_outside" if "n_outside" in task["slots"] else "demo_none_outside"]


def draft_problems(text, task):
    """(problems, rendered). problems = [] means the draft passes; rendered is the finished paragraph, made by code."""
    sentences = V.split_sentences(text or "")
    if not sentences:
        return ["empty output"], None
    problems = []
    for i, s in enumerate(sentences, 1):
        bare = PH.sub("", s)
        if re.search(r"\d", bare):
            problems.append("sentence %d: writes a digit; use a [[placeholder]] for every value" % (i,))
        if NUMBER_WORDS.search(bare):
            problems.append("sentence %d: writes a number word; use a [[placeholder]]" % (i,))
        if any(c in bare for c in DEGREE_SIGNS):
            problems.append("sentence %d: writes a degree sign; the placeholder already holds it" % (i,))
        for pid in PH.findall(s):
            if pid not in task["slots"]:
                problems.append("sentence %d: [[%s]] is not in the FACTS list" % (i, pid))
    used = set(PH.findall(text))
    for r in task["required"]:
        if r not in used:
            problems.append("missing placeholder [[%s]]" % (r,))
    if problems:
        return problems, None
    rendered_sentences = [render_sentence(s, task) for s in sentences]
    codes = []
    for i, (s, r) in enumerate(zip(sentences, rendered_sentences), 1):
        res = V.check_sentence(r, task["_facts"])
        if res.status != "ok":
            hint = ("; copy the matching example sentence exactly, with no words added before or after it"
                    if res.status == "unrecognised" else "; use the sentence forms from the examples")
            problems.append("sentence %d: %s: %s%s" % (i, res.status, res.code, hint))
        else:
            codes.append(res.code)
    if not problems and Counter(codes) != Counter(needed_codes(task)):
        problems.append("the paragraph must hold exactly these sentence forms once each: " + ", ".join(needed_codes(task)))
    rendered = " ".join(rendered_sentences)
    if not problems and not V.paragraph_ok(rendered, task["_facts"]):
        problems.append("the finished paragraph failed the check")
    return problems, (None if problems else rendered)


def run_task(client, task, max_drafts=MAX_DRAFTS, temperature=0.0, seed=SEED):
    """Ask, check, retry with the problems sent back. Return {"task_id", "accepted", "rendered", "drafts"}.

    temperature and seed are fixed; draft i uses seed + i. Each retry shows the model its rejected draft and the problems."""
    feedback, drafts, rendered = [], [], None
    for i in range(max_drafts):
        reply = client.chat(build_messages(task, feedback), temperature, seed + i,
                            context={"task_id": task["task_id"], "task": task_view(task)})
        text = reply["text"]
        problems, ok_text = draft_problems(text, task)
        drafts.append({"draft": i + 1, "text": text, "passed": not problems, "problems": problems,
                       "seconds": reply.get("seconds", 0), "output_tokens": reply.get("output_tokens", 0)})
        if not problems:
            rendered = ok_text
            break
        feedback.append((text or "(empty)", problems))
    return {"task_id": task["task_id"], "accepted": rendered is not None, "rendered": rendered, "drafts": drafts}


def write_section(task, result):
    """The finished section text; only for an accepted result."""
    head = ("### 3.2.P.8.3 Stability: public facts" if task["kind"] == "public" else
            "### 3.2.P.8.3 Stability: %s at %s (illustrative demonstration data)" % (
                task["slots"]["attribute"]["value"], task["slots"]["condition"]["value"]))
    return "\n\n".join([head, result["rendered"],
                        "_The numbers were written by code from stored facts; the model wrote only the words._"]) + "\n"


def mock_text(task):
    """A correct paragraph for this task (what the fake model writes on its second try)."""
    if task["kind"] == "public":
        return ("The proposed shelf life is [[shelf_life_months]] months when stored at [[storage_low]] to [[storage_high]]. "
                "Excursions are permitted from [[excursion_low]] to [[excursion_high]]. "
                "Stability was demonstrated for [[long_term_months]] months at long-term conditions and "
                "[[accel_months]] months at accelerated conditions.")
    head = "In illustrative demonstration data, [[attribute]] at [[condition]] "
    second = "had [[n_outside]] of its [[n]] results" if "n_outside" in task["slots"] else "had none of its [[n]] results"
    return head + "ranged from [[min]] to [[max]] over [[n]] time points. " + head + second + " outside the limit."


class StabilityMockClient:
    """Plays a weak model: its first draft invents numbers and a conclusion, its second is correct."""

    def __init__(self):
        self.calls, self.saw_feedback = {}, {}

    def chat(self, messages, temperature, seed, context=None, schema=None):
        tid, task = context["task_id"], context["task"]
        n = self.calls.get(tid, 0)
        self.calls[tid] = n + 1
        if n == 0:
            text = "Stability was demonstrated for 24 months. The product is stable and no significant change was observed."
        else:
            self.saw_feedback[tid] = any("rejected" in m["content"] for m in messages if m["role"] == "user")
            text = mock_text(task)
        return {"text": text, "thinking_chars": 0, "seconds": 0.01, "prompt_tokens": 0, "prompt_seconds": 0.0,
                "output_tokens": len(text.split()), "output_seconds": 0.0, "load_seconds": 0.0}
