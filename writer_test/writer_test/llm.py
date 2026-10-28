"""Model clients. Standard library only, so nothing extra to install.

ollama : Ollama's native /api/chat (reports prompt and generation timings)
openai : any OpenAI-compatible /chat/completions endpoint (llama-server, vLLM)
mock   : a fake model for testing the harness without downloading anything
"""
import json
import time
import urllib.error
import urllib.request


def _post(url, payload, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaClient:
    def __init__(self, model, base_url="http://localhost:11434", num_ctx=4096, num_predict=600,
                 timeout=1800, think=False):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.num_ctx, self.num_predict, self.timeout = num_ctx, num_predict, timeout
        # Thinking models (Gemma 4 among them) otherwise spend the whole token
        # budget on hidden reasoning and return an empty answer.
        self.think = think

    def chat(self, messages, temperature, seed, context=None):
        t0 = time.time()
        payload = {
            "model": self.model, "messages": messages, "stream": False, "keep_alive": "30m",
            "options": {"temperature": temperature, "seed": seed,
                        "num_ctx": self.num_ctx, "num_predict": self.num_predict},
        }
        if self.think is not None:
            payload["think"] = self.think
        try:
            out = _post(f"{self.base_url}/api/chat", payload, self.timeout)
        except urllib.error.HTTPError as e:
            if e.code != 400 or "think" not in payload:
                raise
            # This model has no thinking switch; ask again without it.
            self.think = None
            payload.pop("think")
            out = _post(f"{self.base_url}/api/chat", payload, self.timeout)
        ns = 1e9
        return {
            "text": out["message"]["content"].strip(),
            "thinking_chars": len(out["message"].get("thinking") or ""),
            "seconds": time.time() - t0,
            "prompt_tokens": out.get("prompt_eval_count", 0),
            "prompt_seconds": out.get("prompt_eval_duration", 0) / ns,
            "output_tokens": out.get("eval_count", 0),
            "output_seconds": out.get("eval_duration", 0) / ns,
            "load_seconds": out.get("load_duration", 0) / ns,
        }


class OpenAIClient:
    def __init__(self, model, base_url="http://localhost:8080/v1", num_predict=600, timeout=1800):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.num_predict, self.timeout = num_predict, timeout

    def chat(self, messages, temperature, seed, context=None):
        t0 = time.time()
        out = _post(f"{self.base_url}/chat/completions", {
            "model": self.model, "messages": messages, "temperature": temperature,
            "seed": seed, "max_tokens": self.num_predict,
        }, self.timeout)
        usage = out.get("usage", {})
        return {
            "text": (out["choices"][0]["message"].get("content") or "").strip(),
            "thinking_chars": len(out["choices"][0]["message"].get("reasoning_content") or ""),
            "seconds": time.time() - t0,
            "prompt_tokens": usage.get("prompt_tokens", 0), "prompt_seconds": 0.0,
            "output_tokens": usage.get("completion_tokens", 0), "output_seconds": 0.0,
            "load_seconds": 0.0,
        }


class MockClient:
    """Plays a weak model: its first draft breaks a rule, its second is correct."""

    def __init__(self):
        self.calls = {}

    def chat(self, messages, temperature, seed, context=None):
        task_id, flags = context["task_id"], context["flags"]
        n = self.calls.get(task_id, 0)
        self.calls[task_id] = n + 1
        if n == 0:
            text = "The results increased to 0.30% over 24 months. All results met the specification."
        else:
            verb = {"increasing": "increased gradually", "decreasing": "decreased gradually",
                    "no meaningful change": "showed no meaningful change"}[flags["trend"]]
            w = flags["worst_fact"]
            word = "highest" if w == "max_value" else "lowest"
            text = (f"The results {verb} at [[condition]], from [[initial_range]] to [[final_range]]. "
                    f"The {word} result was [[{w}]].")
            if flags["all_within_spec"]:
                text += " All results remained within the acceptance criterion of [[spec]]."
            else:
                text += " The result for [[oos_results]] was out of specification against [[spec]]."
        return {"text": text, "thinking_chars": 0, "seconds": 0.01, "prompt_tokens": 0, "prompt_seconds": 0.0,
                "output_tokens": len(text.split()), "output_seconds": 0.0, "load_seconds": 0.0}
