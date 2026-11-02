"""Tests for the engine's model client, draft/check/retry loop and structured extraction. No network, no Ollama.

    python -m unittest tests.test_writer_llm
"""
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ectd_engine.writer.llm import MockClient, OllamaClient, OpenAIClient
from ectd_engine.writer.loop import run_task, write_section
from ectd_engine.writer import structured
from tools import writer_run

ROOT = Path(__file__).resolve().parent.parent
TASKS = json.load(open(ROOT / "writer_test" / "data" / "tasks.json", encoding="utf-8"))["tasks"]
BY_ID = {t["task_id"]: t for t in TASKS}


class ScriptedClient:
    """Returns the same text every time (for planted-error tests)."""

    def __init__(self, text):
        self.text, self.calls = text, 0

    def chat(self, messages, temperature, seed, context=None, schema=None):
        self.calls += 1
        return {"text": self.text, "seconds": 0, "output_tokens": 0}


class MockLoopTest(unittest.TestCase):
    def test_mock_accepts_all_eight(self):
        results = [run_task(MockClient(), t) for t in TASKS]
        self.assertEqual(len(results), 8)
        self.assertEqual(sum(r["accepted"] for r in results), 8)
        for r in results:  # mock's first draft is wrong on purpose, its second is right
            self.assertEqual([d["passed"] for d in r["drafts"]], [False, True])
            self.assertNotIn("[[", r["rendered"])

    def test_accepted_section_text_has_table_and_paragraph(self):
        task = BY_ID["lt_assay"]
        res = run_task(MockClient(), task)
        text = write_section(task, res)
        self.assertIn("| Batch |", text)
        self.assertIn(res["rendered"], text)

    def test_planted_raw_number_is_rejected_after_four_drafts(self):
        bad = ScriptedClient("Total impurities increased to 0.30% over 24 months. All results met the specification.")
        res = run_task(bad, BY_ID["lt_total_impurities"])
        self.assertFalse(res["accepted"])
        self.assertIsNone(res["rendered"])
        self.assertEqual(len(res["drafts"]), 4)
        self.assertEqual(bad.calls, 4)
        self.assertTrue(any("number written outside a placeholder" in p for p in res["drafts"][0]["problems"]))

    def test_empty_reply_is_rejected(self):
        res = run_task(ScriptedClient(""), BY_ID["lt_assay"], max_drafts=2)
        self.assertFalse(res["accepted"])
        self.assertEqual(res["drafts"][0]["problems"], ["empty output"])

    def test_runner_mock_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as buf:
            code = writer_run.main(["--backend", "mock", "--out", tmp])
        self.assertEqual(code, 0)
        self.assertIn("8/8 accepted", buf.getvalue())


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["product", "strength_mg", "batches"],
          "properties": {"product": {"type": "string"},
                         "strength_mg": {"type": "number"},
                         "batches": {"type": "array", "items": {"type": "string"}}}}
SOURCE = "Product X tablets 20 mg were made in batches B1 and B2. Limit 0.30 %."
GOOD = '{"product": "Product X", "strength_mg": 20, "batches": ["B1", "B2"]}'


class StructuredTest(unittest.TestCase):
    def test_good_reply_accepted(self):
        values, problems = structured.check_reply(GOOD, SCHEMA, SOURCE)
        self.assertEqual(problems, [])
        self.assertEqual(values["strength_mg"], 20)

    def test_planted_schema_break_rejected(self):
        for bad, expect in [('{"product": "Product X", "batches": ["B1"]}', "missing required field"),
                            ('{"product": "Product X", "strength_mg": "20", "batches": []}', "expected number"),
                            ('{"product": "Product X", "strength_mg": 20, "batches": [], "extra": 1}', "unexpected field"),
                            ('{"product": "Product X", "strength_mg": true, "batches": []}', "expected number"),
                            ("not json at all", "not valid JSON")]:
            values, problems = structured.check_reply(bad, SCHEMA, SOURCE)
            self.assertIsNone(values, bad)
            self.assertTrue(any(expect in p for p in problems), (bad, problems))

    def test_planted_text_not_in_source_rejected(self):
        bad = '{"product": "Product Y", "strength_mg": 20, "batches": ["B1"]}'
        values, problems = structured.check_reply(bad, SCHEMA, SOURCE)
        self.assertIsNone(values)
        self.assertTrue(any("not in the source text" in p for p in problems))

    def test_planted_number_not_in_source_rejected(self):
        for wrong in ("200", "2", "25"):  # 200 and 2 would pass a naive substring check
            bad = f'{{"product": "Product X", "strength_mg": {wrong}, "batches": ["B1"]}}'
            values, _ = structured.check_reply(bad, SCHEMA, SOURCE)
            self.assertIsNone(values, wrong)

    def test_decimal_number_read_without_float(self):
        schema = {"type": "object", "required": ["limit"], "properties": {"limit": {"type": "number"}}}
        values, problems = structured.check_reply('{"limit": 0.30}', schema, SOURCE)
        self.assertEqual(problems, [])
        self.assertIsInstance(values["limit"], Decimal)
        self.assertEqual(str(values["limit"]), "0.30")
        values, _ = structured.check_reply('{"limit": 0.3}', schema, SOURCE)  # source says 0.30, not 0.3
        self.assertIsNone(values)

    def test_enum_field_is_decided_by_schema_not_source(self):
        schema = {"type": "object", "required": ["kind"], "properties": {"kind": {"enum": ["nmt", "nlt"]}}}
        self.assertIsNotNone(structured.check_reply('{"kind": "nmt"}', schema, SOURCE)[0])
        self.assertIsNone(structured.check_reply('{"kind": "other"}', schema, SOURCE)[0])

    def test_extract_retries_then_accepts(self):
        mock = MockClient()
        first = structured.extract(mock, SOURCE, SCHEMA, "Extract.", context={"mock_reply": GOOD})
        self.assertTrue(first["accepted"])
        self.assertEqual(len(first["attempts"]), 1)
        bad = structured.extract(mock, SOURCE, SCHEMA, "Extract.", context={"mock_reply": "{}"})
        self.assertFalse(bad["accepted"])
        self.assertIsNone(bad["values"])
        self.assertEqual(len(bad["attempts"]), structured.MAX_ATTEMPTS)


class FakeServer:
    """A tiny local HTTP server that records the last request and answers with a fixed reply."""

    def __init__(self, reply):
        outer = self
        outer.requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, body))
                data = json.dumps(reply).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


MSGS = [{"role": "user", "content": "hi"}]


class PayloadShapeTest(unittest.TestCase):
    def test_ollama_payload_and_reply(self):
        srv = FakeServer({"message": {"content": " hello "}, "prompt_eval_count": 7, "eval_count": 3})
        self.addCleanup(srv.close)
        out = OllamaClient("gemma4:e4b", srv.url, num_ctx=2048, num_predict=99).chat(MSGS, 0.2, 5)
        path, body = srv.requests[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["model"], "gemma4:e4b")
        self.assertEqual(body["messages"], MSGS)
        self.assertIs(body["stream"], False)
        self.assertIs(body["think"], False)
        self.assertEqual(body["options"], {"temperature": 0.2, "seed": 5, "num_ctx": 2048, "num_predict": 99})
        self.assertNotIn("format", body)
        self.assertEqual((out["text"], out["prompt_tokens"], out["output_tokens"]), ("hello", 7, 3))

    def test_ollama_structured_sends_schema_as_format(self):
        srv = FakeServer({"message": {"content": GOOD}})
        self.addCleanup(srv.close)
        OllamaClient("m", srv.url).chat(MSGS, 0.0, 1, schema=SCHEMA)
        self.assertEqual(srv.requests[0][1]["format"], SCHEMA)

    def test_openai_payload_and_reply(self):
        srv = FakeServer({"choices": [{"message": {"content": "hey"}}], "usage": {"prompt_tokens": 4, "completion_tokens": 2}})
        self.addCleanup(srv.close)
        out = OpenAIClient("big", srv.url + "/v1", num_predict=50).chat(MSGS, 0.7, 9)
        path, body = srv.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual((body["model"], body["temperature"], body["seed"], body["max_tokens"]), ("big", 0.7, 9, 50))
        self.assertNotIn("response_format", body)
        self.assertEqual((out["text"], out["prompt_tokens"], out["output_tokens"]), ("hey", 4, 2))

    def test_openai_structured_sends_json_schema(self):
        srv = FakeServer({"choices": [{"message": {"content": GOOD}}]})
        self.addCleanup(srv.close)
        OpenAIClient("big", srv.url + "/v1").chat(MSGS, 0.0, 1, schema=SCHEMA)
        rf = srv.requests[0][1]["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertEqual(rf["json_schema"]["schema"], SCHEMA)

    def test_structured_end_to_end_through_fake_server(self):
        srv = FakeServer({"message": {"content": '{"product": "Product Z", "strength_mg": 20, "batches": []}'}})
        self.addCleanup(srv.close)
        res = structured.extract(OllamaClient("m", srv.url), SOURCE, SCHEMA, "Extract.", max_attempts=2)
        self.assertFalse(res["accepted"])  # server's value "Product Z" is not in the source
        self.assertEqual(len(srv.requests), 2)


if __name__ == "__main__":
    unittest.main()
