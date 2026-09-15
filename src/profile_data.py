"""Step 1 - Data profiling.

Produces the evidence a business analyst puts in front of a data owner before
touching the data: volume, grain, completeness, domain values, referential
consistency and rule violations. Writes reports/data_profile.md.

Run:  python -m src.profile_data
"""

from __future__ import annotations

import pandas as pd

from src import config


def load_raw() -> pd.DataFrame:
    return pd.read_csv(config.RAW_CSV, dtype=str, keep_default_na=False)


def profile(df: pd.DataFrame) -> str:
    lines: list[str] = ["# Data profile - pizza_sales.csv", ""]

    lines += [
        "## 1. Volume and grain",
        "",
        f"- Rows: **{len(df):,}**",
        f"- Columns: **{df.shape[1]}**",
        f"- Distinct `pizza_id`: **{df.pizza_id.nunique():,}** "
        f"({'unique - valid primary key' if df.pizza_id.nunique() == len(df) else 'NOT unique'})",
        f"- Distinct `order_id`: **{df.order_id.nunique():,}**",
        f"- Grain: one row per pizza line item within an order",
        "",
    ]

    missing = df.replace("", pd.NA).isna().sum()
    lines += ["## 2. Completeness", "", "| Column | Nulls / blanks | % |", "| --- | --- | --- |"]
    for col, n in missing.items():
        lines.append(f"| `{col}` | {n:,} | {n / len(df):.2%} |")
    lines.append("")

    lines += ["## 3. Duplicates", "",
              f"- Fully duplicated rows: **{df.duplicated().sum():,}**",
              f"- Duplicated `pizza_id`: **{df.pizza_id.duplicated().sum():,}**", ""]

    lines += ["## 4. Categorical domains", ""]
    for col in ("pizza_size", "pizza_category"):
        counts = df[col].value_counts()
        lines.append(f"**`{col}`** ({counts.size} distinct)")
        lines.append("")
        for value, n in counts.items():
            lines.append(f"- `{value}`: {n:,} ({n / len(df):.2%})")
        lines.append("")

    lines += ["## 5. Numeric measures", ""]
    numeric = df[["quantity", "unit_price", "total_price"]].apply(pd.to_numeric, errors="coerce")
    lines.append(numeric.describe().to_markdown())
    lines += ["", f"- Non-numeric `quantity` values: **{numeric.quantity.isna().sum():,}**",
              f"- Non-positive `quantity`: **{(numeric.quantity <= 0).sum():,}**",
              f"- Non-positive `unit_price`: **{(numeric.unit_price <= 0).sum():,}**", ""]

    dates = pd.to_datetime(df.order_date, format=config.SOURCE_DATE_FORMAT, errors="coerce")
    times = pd.to_datetime(df.order_time, format=config.SOURCE_TIME_FORMAT, errors="coerce")
    lines += ["## 6. Date and time integrity", "",
              f"- Unparseable `order_date`: **{dates.isna().sum():,}** (format `DD-MM-YYYY`)",
              f"- Unparseable `order_time`: **{times.isna().sum():,}** (format `HH:MM:SS`)",
              f"- Date range: **{dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}**",
              f"- Calendar days covered: **{dates.dt.date.nunique():,}**", ""]

    calc = (numeric.unit_price * numeric.quantity).round(2)
    breaks = (calc != numeric.total_price.round(2)).sum()
    lines += ["## 7. Business-rule checks", "",
              f"- `unit_price x quantity != total_price`: **{breaks:,}** rows",
              f"- `pizza_name_id` values: **{df.pizza_name_id.nunique()}** "
              f"vs `pizza_name` values: **{df.pizza_name.nunique()}** "
              "(name_id encodes product + size, so a higher count is expected)", ""]

    # A dimension is only safe to split out if its attributes are functionally
    # dependent on the key. Prove it rather than assume it.
    conflicts = (
        df.groupby("pizza_name_id")[["pizza_name", "pizza_category", "pizza_size", "unit_price"]]
        .nunique()
        .gt(1)
        .sum()
    )
    lines += ["## 8. Functional dependency on `pizza_name_id`", "",
              "Number of `pizza_name_id` keys with more than one distinct value:", ""]
    for col, n in conflicts.items():
        lines.append(f"- `{col}`: **{n}**")
    lines += ["",
              "Zero conflicts means the product attributes can be normalised into a "
              "product dimension with no information loss.", ""]

    lines += ["## 9. Redundancy (why we normalise)", "",
              f"- `pizza_ingredients` repeats {len(df):,} times for only "
              f"{df.pizza_ingredients.nunique()} distinct recipes.",
              f"- `pizza_name`, `pizza_category`, `pizza_size` and `unit_price` are all "
              "derivable from `pizza_name_id`.",
              "- Storing them on every fact row inflates the table and risks update anomalies; "
              "they move to `dim_pizza`.", ""]

    return "\n".join(lines)


def main() -> None:
    config.ensure_dirs()
    df = load_raw()
    report = profile(df)
    out = config.REPORTS_DIR / "data_profile.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    main()
