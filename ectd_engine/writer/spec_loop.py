"""The writing loop for the P.5.6 justification paragraph: ask, check, retry up to 4 times, render; plus a fake model for tests."""
from ectd_engine.validator.spec import validate, verify_render
from ectd_engine.writer.spec_facts import compute_spec_facts, narrowed, render_paragraph, render_support
from ectd_engine.writer.spec_prompt import build_messages
from ectd_engine.writer.spec_prose import prose_problems

MAX_DRAFTS = 4


def run_spec_task(client, task, max_drafts=MAX_DRAFTS, temperature=0.2, retry_temperature=0.7):
    """Return {"task_id", "accepted", "rendered", "drafts", "facts", "flags", "task"}.

    accepted is True only if one draft passed the validator AND the re-read of the finished text against the raw task."""
    facts, flags, required = compute_spec_facts(task)
    task = narrowed(task)  # the re-read below must see the same one-row quote that was written
    messages = build_messages(task, facts, flags)
    drafts, rendered = [], None
    for i in range(max_drafts):
        reply = client.chat(messages, temperature if i == 0 else retry_temperature, seed=1000 + i,
                            context={"task_id": task["task_id"], "flags": flags})
        text = reply["text"]
        if not text:
            problems = ["empty output"]
        else:
            problems = validate(text, facts, flags, required)
            if not problems:
                finished = render_paragraph(text, facts, task["basis"])
                problems = ["re-read of finished text: " + p for p in verify_render(finished, task)]
                problems += ["prose:" + name for name in prose_problems(finished)]  # T-051: the prose rules gate live output
        drafts.append({"draft": i + 1, "text": text, "passed": not problems, "problems": problems,
                       "seconds": reply.get("seconds", 0), "output_tokens": reply.get("output_tokens", 0)})
        if not problems:
            rendered = render_paragraph(text, facts, task["basis"])
            break
    return {"task_id": task["task_id"], "accepted": rendered is not None, "rendered": rendered,
            "drafts": drafts, "facts": facts, "flags": flags, "task": task}


def write_spec_section(task, result):
    """The finished section text; only for an accepted result."""
    return "\n\n".join([
        f"### {task['section']} Justification of the acceptance criterion: {task['attribute']}",
        result["rendered"],
        render_support(task),
        "_The values, the limit direction, the basis and the quoted Q3B text were written by code from stored facts; the model wrote only the words._",
    ]) + "\n"


def mock_text(flags):
    """A correct paragraph for these flags (what the fake model writes on its second try)."""
    attr = flags["attribute"]
    if flags["basis"] == "q3b_qualification":
        text = (f"The acceptance criterion for {attr} is [[limit_kind]] [[limit]], set at [[basis]] for an assumed "
                f"maximum daily dose of [[mdd]]: [[q3b_quote]].")
    else:
        text = f"The acceptance criterion for {attr} is [[limit_kind]] [[limit]], which is [[basis]]."
    text += " Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]."
    text += " [[n_outside]] had results outside the limit." if flags["n_outside"] else " No result was outside the limit."
    return text


class SpecMockClient:
    """Plays a weak model: its first draft overclaims (invents a source or a safety conclusion), its second is correct."""

    def __init__(self):
        self.calls = {}

    def chat(self, messages, temperature, seed, context=None, schema=None):
        task_id, flags = context["task_id"], context["flags"]
        n = self.calls.get(task_id, 0)
        self.calls[task_id] = n + 1
        if n == 0:
            text = ("The limit is in line with ICH guidance and is qualified by toxicology data. "
                    "All results complied with the specification. The product is safe.")
        else:
            text = mock_text(flags)
        return {"text": text, "thinking_chars": 0, "seconds": 0.01, "prompt_tokens": 0, "prompt_seconds": 0.0,
                "output_tokens": len(text.split()), "output_seconds": 0.0, "load_seconds": 0.0}
