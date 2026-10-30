"""One command that loads Lek, Kerendia PDF and DailyMed label into Postgres and Neo4j and prints 5 proofs."""
import csv
import json
import re
import sys
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF

from ectd_engine.db import graph as db_graph
from ectd_engine.db import migrate, postgres
from ectd_engine.facts import store
from ectd_engine.gate import agree, gate
from ectd_engine.graph import compare, facts_graph
from ectd_engine.loaders import dailymed, fda_pdf, lek

PREFIX = "DEMO25-"  # every demo fact, batch and document id starts with this; other data is never touched
DOWN = "start Docker first: docker compose --profile db --profile graph up -d"


def _p(text):
    return PREFIX + text


def _bare(text):
    return text[len(PREFIX):] if text.startswith(PREFIX) else text


@contextmanager
def prefixed():
    """Make every gate.submit / gate.quarantine call write demo ids (fact, batch, doc) so real ids stay free."""
    real_submit, real_quarantine = gate.submit, gate.quarantine

    def tag(c):
        c = dict(c)
        c["fact_id"], c["batch"] = _p(c["fact_id"]), _p(c["batch"])
        c["source"] = dict(c["source"], doc_id=_p(c["source"]["doc_id"]))
        return c

    def submit(candidate, registry, conn, rules=None, graph=None):
        return real_submit(tag(candidate), {_p(b) for b in registry}, conn, rules, graph)

    def quarantine(conn, candidate, q):
        return real_quarantine(conn, tag(candidate), q)

    gate.submit, gate.quarantine = submit, quarantine
    try:
        yield
    finally:
        gate.submit, gate.quarantine = real_submit, real_quarantine


def wipe_postgres(owner):
    """Delete only the demo rows from an earlier run."""
    if owner.execute("SELECT to_regclass('facts')").fetchone()[0] is not None:
        owner.execute("DELETE FROM facts WHERE fact_id LIKE %s", (PREFIX + "%",))
        owner.execute("DELETE FROM gate_quarantine_rows WHERE fact_id LIKE %s", (PREFIX + "%",))
    owner.commit()


def wipe_graph(session):
    """Delete only the demo graph nodes from an earlier run."""
    session.run("MATCH (n) WHERE n.fact_id STARTS WITH $p OR n.doc_id STARTS WITH $p OR n.id STARTS WITH $p "
                "DETACH DELETE n", p=PREFIX).consume()


def clean():
    """Remove everything the demo stored, from both stores."""
    owner, driver = postgres.connect(), db_graph.connect()
    try:
        wipe_postgres(owner)
        with driver.session() as session:
            wipe_graph(session)
    finally:
        owner.close()
        driver.close()


def planted_bad_row(app, session):
    """Load one copy of a Lek row (in a temp file) where impurity O is bigger than the total; return the batch name."""
    first = lek.read_rows()[0][1]
    bad = dict(first, batch="PLANTED-1", impurity_o="9.9", impurity_l="0.01", impurities_total="0.5")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "planted.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(first), delimiter=";")
            w.writeheader()
            w.writerow(bad)
        lek.load(app, session, path=path)
    return "PLANTED-1"


def proof1(app):
    """A Lek value, its CSV row number, and a fresh re-read of that row."""
    rownum, row = lek.read_rows()[0]
    f = store.get(app, _p(f"LEK-{row['batch']}-dissolution_av"))
    assert f is not None, "Lek dissolution fact not found in Postgres"
    assert f.source.locator == f"row={rownum}", f"locator is {f.source.locator}"
    again = dict(lek.read_rows())[rownum]["dissolution_av"]
    assert Decimal(again) == f.value, f"CSV row {rownum} says {again}"
    return (f"Lek batch {row['batch']} {f.test} = {f.value} {f.unit} <- {_bare(f.source.doc_id)} {f.source.locator} "
            f"(CSV row {rownum} re-read: {again})")


def proof2(app):
    """A Kerendia PDF value, its page and box, and a fresh look at that box in the PDF."""
    f = store.get(app, _p("KER-CHEMR-shelf_life_p3"))
    assert f is not None, "Kerendia shelf life fact not found in Postgres"
    page_part, box_part = f.source.locator.split(";")
    page = int(page_part.split("=")[1])
    box = [float(x) for x in box_part.split("=")[1].split(",")]
    doc = fitz.open(fda_pdf.ROOT / json.loads(fda_pdf.TARGETS_PATH.read_text(encoding="utf-8"))["pdf"])
    words = [w[4] for w in doc[page - 1].get_text("words") if all(abs(a - b) < 0.01 for a, b in zip(w[:4], box))]
    assert words == [str(f.value)], f"PDF page {page} box holds {words}, fact says {f.value}"
    return f"Kerendia {f.test} = {f.value} {f.unit} <- {_bare(f.source.doc_id)} page {page}, box {box_part.split('=')[1]} (PDF word at that box: {words[0]})"


def proof3(app):
    """The label 'version change' review item: v1 20 mg against v12 40 mg, both versions cited."""
    old, new = store.get(app, _p("KER-SPL-v1-STRENGTH-2")), store.get(app, _p("KER-SPL-v12-STRENGTH-3"))
    assert old is not None and new is not None, "label strength facts not found in Postgres"
    item = agree.agree([old, new])
    assert isinstance(item, agree.ReviewItem) and item.kind == "version change", f"got {item!r}"
    assert item.values == (Decimal("20"), Decimal("40")), f"values {item.values}"
    assert {s.doc_version for s in item.sources} == {"1", "12"}, "both versions must be cited"
    cited = ", ".join(f"v{x.doc_version} of {_bare(x.doc_id)[:8]}.. at {re.search(r'subject\[\d+\]', x.locator).group()}" for x in item.sources)
    return f"review item '{item.kind}': v{old.source.doc_version} {old.value} {old.unit} vs v{new.source.doc_version} {new.value} {new.unit}; cited {cited}"


def proof4(owner, app, session, batch):
    """The planted bad row is in quarantine with a reason and in neither store."""
    rows = owner.execute("SELECT fact_id, reason_code, reason_text FROM gate_quarantine_rows WHERE batch = %s ORDER BY fact_id",
                         (_p(batch),)).fetchall()
    owner.commit()
    assert rows, "planted row was not quarantined"
    assert {r[1] for r in rows} == {lek.CROSS_FIELD}, f"reason codes {[r[1] for r in rows]}"
    for fid, _, _ in rows:
        assert store.get(app, fid) is None, f"{fid} reached Postgres"
        assert fid not in facts_graph.read_all(session, fid), f"{fid} reached the graph"
    return f"planted row (batch {batch}: impurity O 9.9 > total 0.5) -> {len(rows)} facts quarantined, {rows[0][1]}: {rows[0][2]}; none in Postgres or graph"


def proof5(owner, app, session):
    """Postgres and the graph hold the same facts."""
    pg, g = compare.read_postgres(app, PREFIX), facts_graph.read_all(session, PREFIX)
    diffs = compare.compare(pg, g)
    assert not diffs, f"{len(diffs)} mismatch(es), first: {diffs[0]}"
    n_pg = app.execute("SELECT count(*) FROM facts WHERE fact_id LIKE %s", (PREFIX + "%",)).fetchone()[0]
    app.commit()
    n_g = session.run("MATCH (f:Fact) WHERE f.fact_id STARTS WITH $p RETURN count(f) AS n", p=PREFIX).single()["n"]
    n_q = owner.execute("SELECT count(*) FROM gate_quarantine_rows WHERE fact_id LIKE %s", (PREFIX + "%",)).fetchone()[0]
    owner.commit()
    assert n_pg == n_g == len(pg) > 0, f"counts differ: Postgres {n_pg}, graph {n_g}"
    return f"graph vs Postgres compare() == [] ; Postgres {n_pg} facts, Neo4j {n_g} Fact nodes, quarantine {n_q} rows"


def run(tamper=None, out=print):
    """Load the three sources, print 5 PROOF lines, return 0 only if all 5 hold. tamper(session) is a test hook."""
    try:
        owner = postgres.connect()
        migrate.migrate()
        wipe_postgres(owner)
        app, driver = store.connect_app(), db_graph.connect()
    except Exception as e:
        out(f"FAIL: cannot reach the databases ({e!r}); {DOWN}")
        return 1
    try:
        with driver.session() as session:
            wipe_graph(session)
            with prefixed():
                a, q, bad = lek.load(app, session)
                out(f"loaded Lek: accepted {a}, quarantined {q} ({len(bad)} batches with part > total)")
                res = fda_pdf.load(app, session)
                out(f"loaded Kerendia PDF: accepted {sum(isinstance(r, gate.Accepted) for _, r in res)} of {len(res)}")
                res = dailymed.load(app, session)
                out(f"loaded DailyMed label: accepted {sum(isinstance(r, gate.Accepted) for _, r in res)} of {len(res)}")
                batch = planted_bad_row(app, session)
            if tamper:
                tamper(session)
            checks = [lambda: proof1(app), lambda: proof2(app), lambda: proof3(app),
                      lambda: proof4(owner, app, session, batch), lambda: proof5(owner, app, session)]
            failed = 0
            for n, check in enumerate(checks, start=1):
                try:
                    out(f"PROOF {n} OK: {check()}")
                except Exception as e:  # any failure is reported as a failed proof, never hidden
                    failed += 1
                    out(f"PROOF {n} FAIL: {type(e).__name__}: {e}")
    finally:
        driver.close()
        app.close()
        owner.close()
    out("ALL 5 PROOFS HOLD" if not failed else f"{failed} of 5 PROOFS FAILED")
    return 1 if failed else 0


def main(argv=None, tamper=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--clean"]:
        clean()
        print("demo data removed from Postgres and Neo4j (other data untouched)")
        return 0
    if args:
        print("usage: python -m ectd_engine.demo_facts [--clean]")
        return 1
    return run(tamper)


if __name__ == "__main__":
    sys.exit(main())
