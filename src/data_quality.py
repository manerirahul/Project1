"""Step 3 - Data-quality gate.

A declarative suite of assertions that must pass before the star schema is
allowed near the database. Exits non-zero on failure so it can be wired into
CI or a Makefile target.

Run:  python -m src.data_quality
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src import config


@dataclass
class Check:
    name: str
    severity: str  # "error" blocks the load, "warning" is reported only
    fn: Callable[[dict[str, pd.DataFrame]], tuple[bool, str]]


def _load() -> dict[str, pd.DataFrame]:
    tables = {}
    for name, path in config.OUTPUT_FILES.items():
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `python -m src.transform` first")
        tables[name] = pd.read_csv(path)
    return tables


# --------------------------------------------------------------------------- #
# Assertions
# --------------------------------------------------------------------------- #
def unique_fact_key(t):
    dup = t["fact_order_items"].order_item_id.duplicated().sum()
    return dup == 0, f"{dup} duplicate order_item_id"


def no_null_keys(t):
    f = t["fact_order_items"]
    nulls = f[["order_item_id", "order_id", "date_key", "time_key", "pizza_key"]].isna().sum().sum()
    return nulls == 0, f"{nulls} null key values in fact table"


def fact_dim_pizza_integrity(t):
    missing = set(t["fact_order_items"].pizza_key) - set(t["dim_pizza"].pizza_key)
    return not missing, f"{len(missing)} pizza_key values not in dim_pizza"


def fact_dim_date_integrity(t):
    missing = set(t["fact_order_items"].date_key) - set(t["dim_date"].date_key)
    return not missing, f"{len(missing)} date_key values not in dim_date"


def fact_dim_time_integrity(t):
    missing = set(t["fact_order_items"].time_key) - set(t["dim_time"].time_key)
    return not missing, f"{len(missing)} time_key values not in dim_time"


def date_dimension_contiguous(t):
    d = pd.to_datetime(t["dim_date"].full_date).sort_values()
    gaps = (d.diff().dt.days.dropna() != 1).sum()
    return gaps == 0, f"{gaps} gaps in dim_date"


def positive_measures(t):
    f = t["fact_order_items"]
    bad = ((f.quantity <= 0) | (f.unit_price <= 0) | (f.total_price <= 0)).sum()
    return bad == 0, f"{bad} rows with a non-positive measure"


def revenue_rule(t):
    f = t["fact_order_items"]
    bad = ((f.unit_price * f.quantity).round(2) - f.total_price.round(2)).abs().gt(0.01).sum()
    return bad == 0, f"{bad} rows where unit_price x quantity != total_price"


def order_totals_consistent(t):
    f = t["fact_order_items"]
    recomputed = f.groupby("order_id").total_price.sum().round(2)
    stored = f.groupby("order_id").order_total_value.first().round(2)
    bad = (recomputed - stored).abs().gt(0.01).sum()
    return bad == 0, f"{bad} orders where order_total_value != sum of line totals"


def dim_pizza_natural_key_unique(t):
    dup = t["dim_pizza"].pizza_name_id.duplicated().sum()
    return dup == 0, f"{dup} duplicate pizza_name_id in dim_pizza"


def bridge_integrity(t):
    b, p, i = t["bridge_pizza_ingredient"], t["dim_pizza"], t["dim_ingredient"]
    bad = len(set(b.pizza_key) - set(p.pizza_key)) + len(
        set(b.ingredient_key) - set(i.ingredient_key)
    )
    return bad == 0, f"{bad} orphan keys in bridge_pizza_ingredient"


def category_domain(t):
    allowed = {"Classic", "Supreme", "Veggie", "Chicken"}
    unexpected = set(t["dim_pizza"].pizza_category) - allowed
    return not unexpected, f"unexpected categories: {sorted(unexpected)}"


def price_stability(t):
    unstable = (~t["dim_pizza"].price_is_stable).sum()
    return unstable == 0, f"{unstable} products sold at more than one unit price"


def rejection_rate(t):
    rejected = len(t["rejected_rows"])
    loaded = len(t["fact_order_items"])
    rate = rejected / max(rejected + loaded, 1)
    return rate < 0.01, f"rejection rate {rate:.3%} (threshold 1%)"


CHECKS = [
    Check("fact primary key is unique", "error", unique_fact_key),
    Check("no null foreign keys in fact", "error", no_null_keys),
    Check("fact -> dim_pizza referential integrity", "error", fact_dim_pizza_integrity),
    Check("fact -> dim_date referential integrity", "error", fact_dim_date_integrity),
    Check("fact -> dim_time referential integrity", "error", fact_dim_time_integrity),
    Check("dim_date has no gaps", "error", date_dimension_contiguous),
    Check("all measures are positive", "error", positive_measures),
    Check("revenue = unit_price x quantity", "error", revenue_rule),
    Check("order totals reconcile to line items", "error", order_totals_consistent),
    Check("dim_pizza natural key is unique", "error", dim_pizza_natural_key_unique),
    Check("ingredient bridge has no orphans", "error", bridge_integrity),
    Check("pizza_category domain is closed", "warning", category_domain),
    Check("unit price is stable per product", "warning", price_stability),
    Check("rejection rate below 1%", "warning", rejection_rate),
]


def main() -> int:
    tables = _load()
    failures = 0
    warnings = 0
    rows = []
    for check in CHECKS:
        passed, detail = check.fn(tables)
        status = "PASS" if passed else ("FAIL" if check.severity == "error" else "WARN")
        if not passed:
            if check.severity == "error":
                failures += 1
            else:
                warnings += 1
        rows.append({"check": check.name, "severity": check.severity,
                     "status": status, "detail": "" if passed else detail})

    report = pd.DataFrame(rows)
    print(report.to_markdown(index=False))
    (config.REPORTS_DIR / "data_quality_report.md").write_text(
        "# Data-quality gate\n\n" + report.to_markdown(index=False) + "\n", encoding="utf-8"
    )
    print(f"\n{len(CHECKS) - failures - warnings} passed, {warnings} warning(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
