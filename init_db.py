#!/usr/bin/env python3
"""Create the DuckDB database from schema.sql (Step 3).

Offline and safe to re-run: schema.sql uses CREATE TABLE IF NOT EXISTS.
Usage: python3 init_db.py [db_path]
"""
import sys
import pathlib
import duckdb

HERE = pathlib.Path(__file__).parent
SCHEMA_PATH = HERE / "schema.sql"
DEFAULT_DB = HERE / "sumo.duckdb"


def init_db(db_path):
    """Run schema.sql against db_path and return the list of created tables."""
    sql = SCHEMA_PATH.read_text()
    con = duckdb.connect(str(db_path))
    con.execute(sql)                      # create every table (idempotent)
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    con.close()
    return tables


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    tables = init_db(db_path)
    print(f"Initialized {db_path} with {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")
