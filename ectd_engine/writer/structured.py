"""Structured extraction: the model returns JSON, code checks the shape and that every value is really in the source text.

A value is accepted only if (1) the reply fits the JSON schema, checked here by our own small
checker, and (2) each text or number in it appears word for word in the source text.
Numbers are read as Decimal, never float.
"""
import json
import re
from decimal import Decimal

MAX_ATTEMPTS = 3


def check_schema(value, schema, path="$"):
    """Small stdlib JSON-schema check (type, properties, required, additionalProperties, enum, items,
    minimum/maximum, minLength). Returns a list of problems; empty means the value fits."""
    problems = []
    t = schema.get("type")
    kinds = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, Decimal)) and not isinstance(v, bool),
    }
    if t is not None:
        if t not in kinds:
            return [f"{path}: schema uses unsupported type '{t}'"]
        if not kinds[t](value):
            return [f"{path}: expected {t}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if t == "object":
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{path}: missing required field '{name}'")
        for name, sub in value.items():
            if name in props:
                problems += check_schema(sub, props[name], f"{path}.{name}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}: unexpected field '{name}'")
    if t == "array" and "items" in schema:
        for i, item in enumerate(value):
            problems += check_schema(item, schema["items"], f"{path}[{i}]")
    if t == "string" and len(value) < schema.get("minLength", 0):
        problems.append(f"{path}: shorter than {schema['minLength']} characters")
    if t in ("integer", "number"):
        if "minimum" in schema and value < Decimal(str(schema["minimum"])):
            problems.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > Decimal(str(schema["maximum"])):
            problems.append(f"{path}: above maximum {schema['maximum']}")
    return problems


def _leaves(value, schema, path="$"):
    """Yield (path, text-or-number) for every value that must be found in the source.
    Fields fixed by an enum are skipped: the schema, not the source, decides them."""
    if "enum" in schema:
        return
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaves(v, schema.get("properties", {}).get(k, {}), f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _leaves(v, schema.get("items", {}), f"{path}[{i}]")
    elif isinstance(value, str) or (isinstance(value, (int, Decimal)) and not isinstance(value, bool)):
        yield path, value


def verbatim_problems(value, schema, source):
    """Every extracted text/number must appear word for word in the source text."""
    problems = []
    for path, leaf in _leaves(value, schema):
        if isinstance(leaf, str):
            if leaf not in source:
                problems.append(f"{path}: {leaf!r} is not in the source text")
        else:
            token = str(leaf)
            if not re.search(rf"(?<![\w.]){re.escape(token)}(?!\w|\.\d)", source):
                problems.append(f"{path}: number {token} is not in the source text")
    return problems


def check_reply(text, schema, source):
    """Return (values or None, problems). values is set only when the reply passes both checks."""
    try:
        value = json.loads(text, parse_float=Decimal)
    except ValueError as e:
        return None, [f"reply is not valid JSON: {e}"]
    problems = check_schema(value, schema)
    if not problems:
        problems = verbatim_problems(value, schema, source)
    return (value if not problems else None), problems


def extract(client, source, schema, instruction, max_attempts=MAX_ATTEMPTS, context=None):
    """Ask the model to fill the schema from the source text. Returns
    {"accepted", "values", "attempts"}; every attempt is kept. values is None unless accepted."""
    messages = [
        {"role": "system", "content": "You extract values from the SOURCE text into JSON that fits the given "
         "schema. Copy each text and number exactly as written in the SOURCE. Never calculate or guess. "
         "Output only the JSON."},
        {"role": "user", "content": f"{instruction}\n\nSOURCE:\n{source}"},
    ]
    attempts = []
    for i in range(max_attempts):
        reply = client.chat(messages, 0.0, seed=3000 + i, context=context or {}, schema=schema)
        values, problems = check_reply(reply["text"], schema, source)
        attempts.append({"attempt": i + 1, "text": reply["text"], "passed": values is not None,
                         "problems": problems})
        if values is not None:
            return {"accepted": True, "values": values, "attempts": attempts}
    return {"accepted": False, "values": None, "attempts": attempts}
