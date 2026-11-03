"""The writing loop for the batch-analyses paragraph: ask, check, retry up to 4 times, render; plus a fake model for tests."""
from ectd_engine.validator.batch import render, validate, verify_render
from ectd_engine.writer.batch_facts import compute_batch_facts, render_table
from ectd_engine.writer.batch_prompt import build_messages, opening_sentence

MAX_DRAFTS = 4


def run_batch_task(client, task, get_fact, known_batches, max_drafts=MAX_DRAFTS, temperature=0.2, retry_temperature=0.7):
    """Return {"task_id", "accepted", "rendered", "drafts", "facts", "flags", "table"}.

    accepted is True only if one draft passed the validator AND the re-read of the finished text
    against the raw table rows. rendered has the values filled in by code (None when rejected)."""
    facts, flags, required, table = compute_batch_facts(task, get_fact, known_batches)
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
                problems = ["re-read of finished text: " + p for p in verify_render(render(text, facts), table)]
        drafts.append({"draft": i + 1, "text": text, "passed": not problems, "problems": problems,
                       "seconds": reply.get("seconds", 0), "output_tokens": reply.get("output_tokens", 0)})
        if not problems:
            rendered = render(text, facts)
            break
    return {"task_id": task["task_id"], "accepted": rendered is not None, "rendered": rendered,
            "drafts": drafts, "facts": facts, "flags": flags, "table": table}


def write_batch_section(task, result):
    """The finished section text; only for an accepted result."""
    return "\n\n".join([
        f"### {task['section']} Batch analyses: {task['attribute']}",
        opening_sentence(task, result["facts"]),
        render_table(result["table"]),
        result["rendered"],
        "_The table and the values in the paragraph were written by code from stored facts; the model wrote only the words._",
    ]) + "\n"


def mock_text(flags):
    """A correct paragraph for these flags (what the fake model writes on its second try)."""
    text = f"{flags['attribute']} results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]."
    text += " The highest result was [[max_value]] and the lowest result was [[min_value]]."
    if flags["n_excluded"]:
        text += " Results for [[n_excluded]], [[excluded_batches]], were quarantined and are not included."
    return text


class BatchMockClient:
    """Plays a weak model: its first draft breaks a rule (invents compliance), its second is correct."""

    def __init__(self):
        self.calls = {}

    def chat(self, messages, temperature, seed, context=None, schema=None):
        task_id, flags = context["task_id"], context["flags"]
        n = self.calls.get(task_id, 0)
        self.calls[task_id] = n + 1
        text = ("All batches met the specification and the results were acceptable." if n == 0 else mock_text(flags))
        return {"text": text, "thinking_chars": 0, "seconds": 0.01, "prompt_tokens": 0, "prompt_seconds": 0.0,
                "output_tokens": len(text.split()), "output_seconds": 0.0, "load_seconds": 0.0}
