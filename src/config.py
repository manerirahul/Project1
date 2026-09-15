"""Central configuration for the Pizza Sales analytics pipeline.

Every path and connection setting used by the ETL lives here so the scripts
stay environment-agnostic and can run locally, in CI, or in a container.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional, only needed for local .env development
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
SQL_DIR = PROJECT_ROOT / "sql"

RAW_CSV = RAW_DIR / "pizza_sales.csv"

# Star-schema output files produced by src/transform.py
OUTPUT_FILES = {
    "dim_date": PROCESSED_DIR / "dim_date.csv",
    "dim_time": PROCESSED_DIR / "dim_time.csv",
    "dim_pizza": PROCESSED_DIR / "dim_pizza.csv",
    "dim_ingredient": PROCESSED_DIR / "dim_ingredient.csv",
    "bridge_pizza_ingredient": PROCESSED_DIR / "bridge_pizza_ingredient.csv",
    "fact_order_items": PROCESSED_DIR / "fact_order_items.csv",
    "rejected_rows": PROCESSED_DIR / "rejected_rows.csv",
}

# Source-system formats. Kept explicit: never let pandas guess a date format,
# because 01-02-2015 is ambiguous and silent misparsing corrupts every trend.
SOURCE_DATE_FORMAT = "%d-%m-%Y"
SOURCE_TIME_FORMAT = "%H:%M:%S"

EXPECTED_COLUMNS = [
    "pizza_id",
    "order_id",
    "pizza_name_id",
    "quantity",
    "order_date",
    "order_time",
    "unit_price",
    "total_price",
    "pizza_size",
    "pizza_category",
    "pizza_ingredients",
    "pizza_name",
]

SIZE_LABELS = {
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "XL": "Extra Large",
    "XXL": "Double Extra Large",
}

SIZE_ORDER = {"S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5}

# Trading-day part definitions used by dim_time and by the BI day-part filter.
DAY_PARTS = [
    (0, 10, "Pre-Opening"),
    (11, 13, "Lunch"),
    (14, 16, "Afternoon"),
    (17, 20, "Dinner"),
    (21, 23, "Late Night"),
]


@dataclass(frozen=True)
class DatabaseConfig:
    """Postgres connection settings, read from the environment only.

    Credentials never live in source control. See .env.example.
    """

    host: str = field(default_factory=lambda: os.getenv("PGHOST", ""))
    port: int = field(default_factory=lambda: int(os.getenv("PGPORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("PGDATABASE", "postgres"))
    user: str = field(default_factory=lambda: os.getenv("PGUSER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("PGPASSWORD", ""))
    schema: str = field(default_factory=lambda: os.getenv("PGSCHEMA", "public"))
    sslmode: str = field(default_factory=lambda: os.getenv("PGSSLMODE", "require"))

    @property
    def sqlalchemy_url(self) -> str:
        if not self.host or not self.password:
            raise RuntimeError(
                "Database credentials missing. Copy .env.example to .env and fill in "
                "PGHOST / PGUSER / PGPASSWORD (see docs/HOSTING_GUIDE.md)."
            )
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
        )


def ensure_dirs() -> None:
    for path in (PROCESSED_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
