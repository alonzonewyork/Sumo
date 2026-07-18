#!/usr/bin/env python3
"""Export sumo.duckdb to parquet/ -- the git-tracked source of truth.

sumo.duckdb itself is a local, regenerable artifact and stays gitignored;
parquet/ (one file per table, via DuckDB's native EXPORT DATABASE) is what
actually gets committed. Run this after extract.py updates the database, and
commit the resulting parquet/ changes.

Usage: python3 export_parquet.py
"""
import pathlib
import shutil

import duckdb

HERE = pathlib.Path(__file__).parent
DB_PATH = HERE / "sumo.duckdb"
PARQUET_DIR = HERE / "parquet"


def main():
    if PARQUET_DIR.exists():
        shutil.rmtree(PARQUET_DIR)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(f"EXPORT DATABASE '{PARQUET_DIR}' (FORMAT PARQUET)")
    con.close()
    files = sorted(p.name for p in PARQUET_DIR.glob("*.parquet"))
    print(f"Exported {len(files)} tables to {PARQUET_DIR}/:")
    for f in files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
