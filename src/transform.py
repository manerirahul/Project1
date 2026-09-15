"""Step 2 - Clean, standardise and model the data as a Kimball star schema.

Input : data/raw/pizza_sales.csv (one row per pizza line item)
Output: data/processed/*.csv  -> dim_date, dim_time, dim_pizza, dim_ingredient,
        bridge_pizza_ingredient, fact_order_items, rejected_rows

Design decisions (documented in docs/DATA_DICTIONARY.md):
  * The raw file is one wide, denormalised table. Product attributes repeat on
    every line item, so they are normalised into dim_pizza. This is the
    "remove unnecessary data" step: no information is lost, ~60% of the stored
    text is.
  * Rows that break a hard business rule are not silently dropped. They are
    written to rejected_rows.csv with a reason so the data owner can act.
  * Every surrogate key is generated here, deterministically, so a re-run
    produces byte-identical output (idempotent pipeline).

Run:  python -m src.transform
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from src import config

REJECTED: list[pd.DataFrame] = []


# --------------------------------------------------------------------------- #
# Extract
# --------------------------------------------------------------------------- #
def extract() -> pd.DataFrame:
    df = pd.read_csv(config.RAW_CSV, dtype=str, keep_default_na=False)
    missing = set(config.EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Source file is missing expected columns: {sorted(missing)}")
    return df[config.EXPECTED_COLUMNS].copy()


# --------------------------------------------------------------------------- #
# Clean
# --------------------------------------------------------------------------- #
def _reject(df: pd.DataFrame, mask: pd.Series, reason: str) -> pd.DataFrame:
    """Quarantine rows matching mask and return the surviving rows."""
    if mask.any():
        bad = df.loc[mask].copy()
        bad["reject_reason"] = reason
        REJECTED.append(bad)
    return df.loc[~mask].copy()


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim, collapse internal whitespace and normalise unicode punctuation."""
    return (
        series.fillna("")
        .map(lambda v: unicodedata.normalize("NFKC", str(v)))
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Text hygiene on every string column.
    for col in ("pizza_name_id", "pizza_size", "pizza_category", "pizza_ingredients", "pizza_name"):
        df[col] = _clean_text(df[col])

    df["pizza_name_id"] = df.pizza_name_id.str.lower()
    df["pizza_size"] = df.pizza_size.str.upper()
    df["pizza_category"] = df.pizza_category.str.title()

    # 2. Type coercion. Anything that will not cast is quarantined, not guessed.
    for col in ("pizza_id", "order_id", "quantity"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ("unit_price", "total_price"):
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    df["order_date_parsed"] = pd.to_datetime(
        df.order_date, format=config.SOURCE_DATE_FORMAT, errors="coerce"
    )
    df["order_time_parsed"] = pd.to_datetime(
        df.order_time, format=config.SOURCE_TIME_FORMAT, errors="coerce"
    )

    df = _reject(df, df.pizza_id.isna() | df.order_id.isna(), "unparseable identifier")
    df = _reject(df, df.order_date_parsed.isna(), "unparseable order_date (expected DD-MM-YYYY)")
    df = _reject(df, df.order_time_parsed.isna(), "unparseable order_time (expected HH:MM:SS)")

    # 3. Hard business rules.
    df = _reject(df, df.quantity.isna() | (df.quantity <= 0), "quantity must be a positive integer")
    df = _reject(df, df.unit_price.isna() | (df.unit_price <= 0), "unit_price must be positive")
    df = _reject(df, ~df.pizza_size.isin(config.SIZE_ORDER), "unknown pizza_size")
    df = _reject(df, df.pizza_name_id.eq(""), "missing product key")

    # 4. Duplicates. An exact repeat of the line-item key is a load artefact.
    df = _reject(df, df.duplicated(subset=["pizza_id"], keep="first"), "duplicate pizza_id")
    df = _reject(
        df,
        df.duplicated(subset=["order_id", "pizza_name_id", "order_time", "quantity"], keep="first"),
        "duplicate line item within order",
    )

    # 5. Recompute total_price from the price x quantity rule so the fact table is
    #    internally consistent, and record any row where the source disagreed.
    recomputed = (df.unit_price * df.quantity).round(2)
    df["total_price_source"] = df.total_price
    df["price_variance_flag"] = (recomputed - df.total_price.fillna(0)).abs().gt(0.01)
    df["total_price"] = recomputed

    # 6. Order timestamp = date + time of day.
    df["order_ts"] = df.order_date_parsed + (
        df.order_time_parsed - df.order_time_parsed.dt.normalize()
    )

    return df.sort_values("pizza_id").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Dimensions
# --------------------------------------------------------------------------- #
def build_dim_date(df: pd.DataFrame) -> pd.DataFrame:
    """Full contiguous calendar covering the fact range.

    Contiguous matters: a gap-free date dimension is what lets Power BI and
    Tableau compute time intelligence (YTD, MoM) on days with zero sales.
    """
    start, end = df.order_ts.min().normalize(), df.order_ts.max().normalize()
    dates = pd.date_range(start, end, freq="D")
    d = pd.DataFrame({"full_date": dates})
    d["date_key"] = d.full_date.dt.strftime("%Y%m%d").astype(int)
    d["year"] = d.full_date.dt.year
    d["quarter"] = d.full_date.dt.quarter
    d["quarter_name"] = "Q" + d.quarter.astype(str) + " " + d.year.astype(str)
    d["month_number"] = d.full_date.dt.month
    d["month_name"] = d.full_date.dt.strftime("%B")
    d["month_short"] = d.full_date.dt.strftime("%b")
    d["year_month"] = d.full_date.dt.strftime("%Y-%m")
    d["iso_week"] = d.full_date.dt.isocalendar().week.astype(int)
    d["day_of_month"] = d.full_date.dt.day
    d["day_of_week"] = d.full_date.dt.dayofweek + 1  # 1 = Monday
    d["day_name"] = d.full_date.dt.strftime("%A")
    d["day_short"] = d.full_date.dt.strftime("%a")
    d["is_weekend"] = d.day_of_week.isin([6, 7])
    d["day_of_year"] = d.full_date.dt.dayofyear
    return d[
        [
            "date_key", "full_date", "year", "quarter", "quarter_name", "month_number",
            "month_name", "month_short", "year_month", "iso_week", "day_of_month",
            "day_of_week", "day_name", "day_short", "is_weekend", "day_of_year",
        ]
    ]


def build_dim_time() -> pd.DataFrame:
    """Hour-grain time dimension with trading day parts."""
    rows = []
    for hour in range(24):
        part = next(
            (label for lo, hi, label in config.DAY_PARTS if lo <= hour <= hi), "Unclassified"
        )
        rows.append(
            {
                "time_key": hour,
                "hour_24": hour,
                "hour_label": f"{hour:02d}:00",
                "hour_12": f"{((hour - 1) % 12) + 1} {'AM' if hour < 12 else 'PM'}",
                "day_part": part,
                "is_peak_window": part in ("Lunch", "Dinner"),
            }
        )
    return pd.DataFrame(rows)


_SIZE_SUFFIX = re.compile(r"_(s|m|l|xl|xxl)$")


def build_dim_pizza(df: pd.DataFrame) -> pd.DataFrame:
    """Conformed product dimension at product-plus-size grain.

    `pizza_name_id` is the natural key; `pizza_key` is the surrogate key used by
    the fact table so a source re-key does not break history.
    """
    agg = (
        df.groupby("pizza_name_id")
        .agg(
            pizza_name=("pizza_name", "first"),
            pizza_category=("pizza_category", "first"),
            pizza_size=("pizza_size", "first"),
            pizza_ingredients=("pizza_ingredients", "first"),
            unit_price=("unit_price", "median"),
            min_unit_price=("unit_price", "min"),
            max_unit_price=("unit_price", "max"),
        )
        .reset_index()
    )

    agg["product_code"] = agg.pizza_name_id.str.replace(_SIZE_SUFFIX, "", regex=True)
    agg["pizza_short_name"] = (
        agg.pizza_name.str.replace(r"^The\s+", "", regex=True)
        .str.replace(r"\s+Pizza$", "", regex=True)
    )
    agg["size_label"] = agg.pizza_size.map(config.SIZE_LABELS)
    agg["size_sort_order"] = agg.pizza_size.map(config.SIZE_ORDER)
    agg["ingredient_count"] = agg.pizza_ingredients.map(
        lambda s: len([p for p in str(s).split(",") if p.strip()])
    )
    agg["is_vegetarian"] = ~agg.pizza_ingredients.str.contains(
        r"chicken|ham|bacon|pepperoni|salami|beef|prosciutto|capocollo|"
        r"soppressata|nduja|anchov|calabrese|chorizo|sausage|barbecued chicken",
        case=False,
        regex=True,
    )
    agg["price_is_stable"] = (agg.max_unit_price - agg.min_unit_price).abs().le(0.01)
    agg = agg.sort_values(["product_code", "size_sort_order"]).reset_index(drop=True)
    agg.insert(0, "pizza_key", np.arange(1, len(agg) + 1))
    return agg[
        [
            "pizza_key", "pizza_name_id", "product_code", "pizza_name", "pizza_short_name",
            "pizza_category", "pizza_size", "size_label", "size_sort_order", "unit_price",
            "min_unit_price", "max_unit_price", "price_is_stable", "ingredient_count",
            "is_vegetarian", "pizza_ingredients",
        ]
    ]


def build_ingredients(dim_pizza: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the comma-separated recipe string into a proper many-to-many.

    This unlocks ingredient-level questions (procurement exposure, allergen
    filtering) that the flat CSV cannot answer at all.
    """
    exploded = (
        dim_pizza[["pizza_key", "pizza_ingredients"]]
        .assign(ingredient_name=lambda d: d.pizza_ingredients.str.split(","))
        .explode("ingredient_name")
        .assign(ingredient_name=lambda d: _clean_text(d.ingredient_name).str.title())
        .query("ingredient_name != ''")
    )

    dim_ingredient = (
        pd.DataFrame({"ingredient_name": sorted(exploded.ingredient_name.unique())})
        .reset_index(drop=True)
    )
    dim_ingredient.insert(0, "ingredient_key", np.arange(1, len(dim_ingredient) + 1))
    dim_ingredient["is_cheese"] = dim_ingredient.ingredient_name.str.contains(
        "cheese|mozzarella|provolone|gouda|romano|feta|ricotta|asiago|parmigiano|goat",
        case=False,
    )

    bridge = (
        exploded.merge(dim_ingredient[["ingredient_key", "ingredient_name"]], on="ingredient_name")
        .drop_duplicates(["pizza_key", "ingredient_key"])
        .sort_values(["pizza_key", "ingredient_key"])[["pizza_key", "ingredient_key"]]
        .reset_index(drop=True)
    )
    return dim_ingredient, bridge


# --------------------------------------------------------------------------- #
# Fact
# --------------------------------------------------------------------------- #
def build_fact(df: pd.DataFrame, dim_pizza: pd.DataFrame) -> pd.DataFrame:
    fact = df.merge(dim_pizza[["pizza_key", "pizza_name_id"]], on="pizza_name_id", how="left")

    orphans = fact.pizza_key.isna()
    if orphans.any():  # defensive: dim is derived from the fact, so this is a bug guard
        raise RuntimeError(f"{orphans.sum()} fact rows failed to match dim_pizza")

    fact["date_key"] = fact.order_ts.dt.strftime("%Y%m%d").astype(int)
    fact["time_key"] = fact.order_ts.dt.hour

    # Degenerate order-level context, precomputed once so BI tools never have to
    # do a self-join to answer "how big was the basket?".
    order_stats = fact.groupby("order_id").agg(
        order_line_count=("pizza_id", "size"),
        order_pizza_count=("quantity", "sum"),
        order_total_value=("total_price", "sum"),
    )
    fact = fact.merge(order_stats, on="order_id", how="left")
    fact["order_total_value"] = fact.order_total_value.round(2)

    fact = fact.rename(columns={"pizza_id": "order_item_id"})
    return fact[
        [
            "order_item_id", "order_id", "date_key", "time_key", "pizza_key", "order_ts",
            "quantity", "unit_price", "total_price", "total_price_source",
            "price_variance_flag", "order_line_count", "order_pizza_count",
            "order_total_value",
        ]
    ].sort_values("order_item_id").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run() -> dict[str, pd.DataFrame]:
    config.ensure_dirs()
    raw = extract()
    cleaned = clean(raw)

    dim_pizza = build_dim_pizza(cleaned)
    dim_ingredient, bridge = build_ingredients(dim_pizza)
    tables = {
        "dim_date": build_dim_date(cleaned),
        "dim_time": build_dim_time(),
        "dim_pizza": dim_pizza,
        "dim_ingredient": dim_ingredient,
        "bridge_pizza_ingredient": bridge,
        "fact_order_items": build_fact(cleaned, dim_pizza),
    }
    rejected = (
        pd.concat(REJECTED, ignore_index=True)
        if REJECTED
        else pd.DataFrame(columns=[*config.EXPECTED_COLUMNS, "reject_reason"])
    )
    tables["rejected_rows"] = rejected

    for name, table in tables.items():
        table.to_csv(config.OUTPUT_FILES[name], index=False)

    print(f"Source rows            : {len(raw):,}")
    print(f"Rejected rows          : {len(rejected):,}")
    print(f"Fact rows loaded       : {len(tables['fact_order_items']):,}")
    print(f"Price variances flagged: {int(tables['fact_order_items'].price_variance_flag.sum()):,}")
    for name, table in tables.items():
        print(f"  {name:<26} {len(table):>7,} rows x {table.shape[1]:>2} cols")
    return tables


if __name__ == "__main__":
    run()
