"""The writing loop: ask the model for a paragraph, let the checker judge it, retry up to 4 times, then render.

Code, not the model, decides if a draft is good. The model only ever writes words with [[placeholders]].
"""
from ectd_engine.validator.rendercheck import verify_render
from ectd_engine.validator.validator import render, validate
from ectd_engine.writer.facts import compute_facts
from ectd_engine.writer.prompt import build_messages, data_table, opening_sentence

MAX_DRAFTS = 4


def run_task(client, task, max_drafts=MAX_DRAFTS, temperature=0.2, retry_temperature=0.7):
    """Return {"task_id", "accepted", "rendered", "drafts", "facts", "flags"}.

    accepted is True only if one draft passed the validator AND the re-read of the finished text
    against the raw table. drafts lists every attempt, passed or not. rendered is the paragraph
    with values filled in by code (None when rejected)."""
    facts, flags, required = compute_facts(task)
    messages = build_messages(task, facts, flags)
    drafts, rendered = [], None
    for i in range(max_drafts):
        # First draft is conservative; later drafts sample more widely for variety.
        temp = temperature if i == 0 else retry_temperature
        reply = client.chat(messages, temp, seed=1000 + i,
                            context={"task_id": task["task_id"], "flags": flags})
        text = reply["text"]
        if not text:
            problems = ["empty output"]
        else:
            problems = validate(text, facts, flags, required)
            if not problems:  # second, independent route: re-read the finished text against the raw table
                problems = ["re-read of finished text: " + p for p in verify_render(render(text, facts), task)]
        drafts.append({"draft": i + 1, "text": text, "passed": not problems, "problems": problems,
                       "seconds": reply.get("seconds", 0), "output_tokens": reply.get("output_tokens", 0)})
        if not problems:
            rendered = render(text, facts)
            break
    return {"task_id": task["task_id"], "accepted": rendered is not None, "rendered": rendered,
            "drafts": drafts, "facts": facts, "flags": flags}


def write_section(task, result):
    """The finished section text; only for an accepted result."""
    facts = result["facts"]
    return "\n\n".join([
        f"### {task['section']} Stability data: {task['attribute']}, {facts['condition']['value']}",
        opening_sentence(task, facts),
        data_table(task),
        result["rendered"],
        "_Values in the paragraph were inserted by code from computed facts; the model wrote only the words._",
    ]) + "\n"
