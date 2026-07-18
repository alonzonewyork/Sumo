#!/usr/bin/env python3
"""Rebuild sumo.duckdb from the committed parquet/ snapshot.

Use this after a fresh clone (or to reset local state) instead of re-running
the full historical pull -- parquet/ is the git-tracked source of truth;
sumo.duckdb is a local, regenerable artifact built from it.

Refuses to overwrite an existing sumo.duckdb unless --force is passed, since
that would discard any local data newer than the last export_parquet.py run.

Usage: python3 import_parquet.py [--force]
"""
import pathlib
import sys

import duckdb

HERE = pathlib.Path(__file__).parent
DB_PATH = HERE / "sumo.duckdb"
PARQUET_DIR = HERE / "parquet"


def main():
    force = "--force" in sys.argv
    if DB_PATH.exists() and not force:
        sys.exit(f"{DB_PATH} already exists -- pass --force to overwrite it "
                  "(any local data not yet exported via export_parquet.py will be lost)")
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    con.execute(f"IMPORT DATABASE '{PARQUET_DIR}'")
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    con.close()
    print(f"Rebuilt {DB_PATH} with {len(tables)} tables from {PARQUET_DIR}/:")
    for t in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
