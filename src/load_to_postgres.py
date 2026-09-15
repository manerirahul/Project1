"""Step 4 - Load the star schema into PostgreSQL.

Deliberately idempotent and load-order aware:
  * dimensions load before the fact table, so foreign keys always resolve;
  * `TRUNCATE ... RESTART IDENTITY CASCADE` in dependency order gives a clean
    full refresh without dropping the schema (views and grants survive);
  * the fact table streams in chunks so memory stays flat and a free-tier host
    is not overwhelmed by a single huge transaction;
  * the whole load runs in one transaction - a failure leaves the warehouse in
    its previous good state rather than half-loaded.

Run:
  python -m src.load_to_postgres              # create schema + views, then load
  python -m src.load_to_postgres --skip-ddl   # data only
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
from sqlalchemy import create_engine, text

from src import config

# Parents first for loading, reversed for truncating.
LOAD_ORDER = [
    "dim_date",
    "dim_time",
    "dim_pizza",
    "dim_ingredient",
    "bridge_pizza_ingredient",
    "fact_order_items",
]

DDL_FILES = ["01_schema.sql", "02_views.sql"]


def read_table(name: str) -> pd.DataFrame:
    path = config.OUTPUT_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run `python -m src.transform` first")
    df = pd.read_csv(path)
    if name == "fact_order_items":
        df["order_ts"] = pd.to_datetime(df.order_ts)
    if name == "dim_date":
        df["full_date"] = pd.to_datetime(df.full_date).dt.date
    return df


def apply_ddl(engine) -> None:
    for filename in DDL_FILES:
        sql = (config.SQL_DIR / filename).read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.execute(text(sql))
        print(f"  applied sql/{filename}")


def load(skip_ddl: bool = False) -> None:
    db = config.DatabaseConfig()
    engine = create_engine(db.sqlalchemy_url, pool_pre_ping=True)
    chunk_size = int(os.getenv("LOAD_CHUNK_SIZE", "5000"))

    if not skip_ddl:
        print("Applying DDL...")
        apply_ddl(engine)

    started = time.perf_counter()
    with engine.begin() as conn:
        # Single statement so the truncate order cannot deadlock with the FKs.
        conn.execute(
            text("TRUNCATE TABLE " + ", ".join(f"{db.schema}.{t}" for t in reversed(LOAD_ORDER))
                 + " RESTART IDENTITY CASCADE")
        )
        for table in LOAD_ORDER:
            df = read_table(table)
            df.to_sql(
                table,
                conn,
                schema=db.schema,
                if_exists="append",
                index=False,
                chunksize=chunk_size,
                method="multi",
            )
            print(f"  loaded {table:<26} {len(df):>7,} rows")

    with engine.connect() as conn:
        checks = {
            t: conn.execute(text(f"SELECT count(*) FROM {db.schema}.{t}")).scalar()
            for t in LOAD_ORDER
        }
        revenue = conn.execute(
            text(f"SELECT round(sum(total_price), 2) FROM {db.schema}.fact_order_items")
        ).scalar()

    print("\nPost-load verification")
    for table, count in checks.items():
        local = len(read_table(table))
        status = "OK" if count == local else f"MISMATCH (local {local:,})"
        print(f"  {table:<26} {count:>7,} rows  {status}")
    print(f"  total revenue in warehouse : {revenue:,.2f}")
    print(f"  elapsed                    : {time.perf_counter() - started:.1f}s")

    if any(checks[t] != len(read_table(t)) for t in LOAD_ORDER):
        sys.exit("Row counts do not match the processed files - investigate before reporting.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the pizza sales star schema into Postgres")
    parser.add_argument("--skip-ddl", action="store_true", help="assume schema and views exist")
    args = parser.parse_args()
    load(skip_ddl=args.skip_ddl)


if __name__ == "__main__":
    main()
