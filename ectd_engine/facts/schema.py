"""Defines the Fact record: one number plus its meaning and exact source, refusing loose data."""
import json
import re
from dataclasses import dataclass
from decimal import Decimal

LINEAGES = ("original", "copy", "unknown")

# the three allowed locator forms: spreadsheet row, PDF page box, spreadsheet cell
_NUM = r"-?[0-9]+(?:\.[0-9]+)?"
_VALUE_RE = re.compile(r"-?[0-9]+(\.[0-9]+)?")
_KEYS = {"fact_id", "value", "unit", "batch", "test", "condition", "month", "source", "lineage", "definition"}
_SOURCE_KEYS = {"doc_id", "doc_version", "locator"}
_LOCATOR_RES = (
    re.compile(r"row=[0-9]+"),
    re.compile(rf"page=[0-9]+;box={_NUM},{_NUM},{_NUM},{_NUM}"),
    re.compile(r"cell=[A-Z]+[0-9]+"),
)


def _need_text(name, text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class SourcePointer:
    doc_id: str
    doc_version: str
    locator: str

    def __post_init__(self):
        _need_text("doc_id", self.doc_id)
        _need_text("doc_version", self.doc_version)
        _need_text("locator", self.locator)
        if not any(r.fullmatch(self.locator) for r in _LOCATOR_RES):
            raise ValueError(f"locator {self.locator!r} is not row=N, page=N;box=x0,y0,x1,y1 or cell=B7")


@dataclass(frozen=True)
class Fact:
    fact_id: str
    value: Decimal
    unit: str
    batch: str
    test: str
    condition: str
    month: "int | None"
    source: SourcePointer
    lineage: str
    definition: str

    def __post_init__(self):
        _need_text("fact_id", self.fact_id)
        _need_text("unit", self.unit)
        _need_text("test", self.test)
        _need_text("batch", self.batch)
        _need_text("condition", self.condition)
        _need_text("definition", self.definition)
        if not isinstance(self.value, Decimal):
            raise ValueError(f"value must be Decimal, got {type(self.value).__name__}")
        if not self.value.is_finite():
            raise ValueError("value must not be NaN or Infinity")
        if not _VALUE_RE.fullmatch(str(self.value)):
            raise ValueError(f"value {str(self.value)!r} must print as a plain decimal (no exponent form like 1E+2)")
        if self.month is not None:
            if isinstance(self.month, bool) or not isinstance(self.month, int) or self.month < 0:
                raise ValueError("month must be None or an integer >= 0")
        if not isinstance(self.source, SourcePointer):
            raise ValueError("source must be a SourcePointer")
        if self.lineage not in LINEAGES:
            raise ValueError(f"lineage must be one of {LINEAGES}")


def to_json(fact):
    """Return JSON text; the value is a string so '0.140' keeps its trailing zero."""
    d = {
        "fact_id": fact.fact_id,
        "value": str(fact.value),
        "unit": fact.unit,
        "batch": fact.batch,
        "test": fact.test,
        "condition": fact.condition,
        "month": fact.month,
        "source": {
            "doc_id": fact.source.doc_id,
            "doc_version": fact.source.doc_version,
            "locator": fact.source.locator,
        },
        "lineage": fact.lineage,
        "definition": fact.definition,
    }
    return json.dumps(d, sort_keys=True)


def from_json(text):
    """Rebuild a Fact from JSON text, re-running every check."""
    d = json.loads(text)
    if set(d) != _KEYS or set(d["source"]) != _SOURCE_KEYS:
        raise ValueError("JSON has missing or unknown keys")
    raw = d["value"]
    if not isinstance(raw, str):
        raise ValueError("value must be a JSON string (a JSON number would lose digits)")
    if not _VALUE_RE.fullmatch(raw):
        raise ValueError(f"value {raw!r} is not a plain decimal number")
    value = Decimal(raw)
    s = d["source"]
    return Fact(
        fact_id=d["fact_id"],
        value=value,
        unit=d["unit"],
        batch=d["batch"],
        test=d["test"],
        condition=d["condition"],
        month=d["month"],
        source=SourcePointer(s["doc_id"], s["doc_version"], s["locator"]),
        lineage=d["lineage"],
        definition=d["definition"],
    )
