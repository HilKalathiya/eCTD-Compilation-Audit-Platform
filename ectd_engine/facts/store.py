"""Saves and loads facts in Postgres; writing is only possible through the database's gate function."""
from decimal import Decimal

import psycopg

from ectd_engine.db.config import load_env
from ectd_engine.facts.schema import Fact, SourcePointer


def connect_app(env=None):
    """Connect as ectd_app, the login that may read facts and call the gate but never write directly."""
    env = env or load_env()
    return psycopg.connect(
        host=env.get("POSTGRES_HOST", "localhost"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        user=env["APP_DB_USER"],
        password=env["APP_DB_PASSWORD"],
        dbname=env.get("POSTGRES_DB", "ectd"),
    )


def put(conn, fact):
    """Store a fact through gate_insert_fact; raises a psycopg error if the gate refuses it."""
    s = fact.source
    conn.execute(
        "SELECT gate_insert_fact(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (fact.fact_id, fact.value, str(fact.value), fact.unit, fact.batch, fact.test, fact.condition,
         fact.month, s.doc_id, s.doc_version, s.locator, fact.lineage, fact.definition),
    )
    conn.commit()


def get(conn, fact_id):
    """Load a fact by id (None if absent), rebuilt from value_text so '0.140' stays '0.140'."""
    row = conn.execute(
        "SELECT fact_id, value, value_text, unit, batch, test, condition, month, "
        "doc_id, doc_version, locator, lineage, definition FROM facts WHERE fact_id = %s",
        (fact_id,),
    ).fetchone()
    conn.commit()
    if row is None:
        return None
    value = Decimal(row[2])
    if value != row[1]:
        raise ValueError(f"stored value and value_text disagree for {fact_id}")
    return Fact(fact_id=row[0], value=value, unit=row[3], batch=row[4], test=row[5], condition=row[6],
                month=row[7], source=SourcePointer(row[8], row[9], row[10]), lineage=row[11], definition=row[12])
