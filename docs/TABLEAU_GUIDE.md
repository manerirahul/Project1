# Tableau dashboard - build guide

Two free routes:

| Tool | Cost | Postgres connection | Sharing |
| --- | --- | --- | --- |
| **Tableau Public** (desktop app) | Free forever | No live database connector - CSV/Excel only | Publishes a public interactive link, perfect for a portfolio |
| **Tableau Desktop** | 14-day trial, then paid | Full PostgreSQL connector | Local only unless licensed |

**Important limitation, stated plainly:** Tableau Public cannot connect to
PostgreSQL. So the free path is: export the warehouse views to CSV, then build on
those. The database is still the source of truth - the export is generated from
it, never hand-edited.

---

## 1. Export the warehouse views for Tableau Public

```bash
# with .env configured
python - <<'PY'
import pandas as pd
from sqlalchemy import create_engine
from src.config import DatabaseConfig, REPORTS_DIR

engine = create_engine(DatabaseConfig().sqlalchemy_url)
for view in ["vw_fact_enriched", "vw_product_performance", "vw_product_affinity",
             "vw_basket_profile", "vw_hourly_demand", "vw_monthly_trend",
             "vw_weekday_hour_heatmap", "vw_ingredient_exposure"]:
    out = REPORTS_DIR / f"tableau_{view}.csv"
    pd.read_sql(f"SELECT * FROM public.{view}", engine).to_csv(out, index=False)
    print("wrote", out)
PY
```

`tableau_vw_fact_enriched.csv` is the main extract: it is the star schema
pre-joined, which is exactly the shape Tableau prefers.

Using licensed **Tableau Desktop** instead? Skip the export:
**Connect > To a Server > PostgreSQL**, server `aws-0-<region>.pooler.supabase.com`,
port `5432`, database `postgres`, user `bi_reader`, SSL required. Then drag
`fact_order_items` to the canvas and join `dim_date`, `dim_time`, `dim_pizza` on
their key columns (inner joins).

## 2. Data source setup

1. Connect to `tableau_vw_fact_enriched.csv`.
2. Add the other CSVs as separate data sources (do not join them - they are
   pre-aggregated at different grains).
3. On the **Data Source** tab, fix the metadata:
   - `full_date` -> Date, `order_ts` -> Date & Time
   - `total_price`, `unit_price`, `order_total_value` -> Number (decimal), Measure
   - `quantity` -> Number (whole), Measure
   - Everything else -> Dimension
   - Rename fields to business language: `total_price` -> `Revenue`,
     `pizza_short_name` -> `Pizza`, `hour_label` -> `Hour of Day`.
4. Create a **hierarchy**: drag `year` onto `quarter_name`, then `month_name`,
   then `full_date`. Name it `Calendar`.
5. Set the **default sort** on `pizza_size` to manual: S, M, L, XL, XXL.
6. **Extract** (radio button, top right) rather than Live - faster and required
   for Tableau Public.

## 3. Calculated fields

```
// Core
Revenue                 = SUM([Total Price])
Pizzas Sold             = SUM([Quantity])
Orders                  = COUNTD([Order Id])
Trading Days            = COUNTD([Full Date])

Avg Order Value         = SUM([Total Price]) / COUNTD([Order Id])
Avg Pizzas per Order    = SUM([Quantity]) / COUNTD([Order Id])
Revenue per Trading Day = SUM([Total Price]) / COUNTD([Full Date])

// Mix - table calculation alternative to WINDOW functions
Revenue % of Total      = SUM([Total Price]) / TOTAL(SUM([Total Price]))

// Month over month, as a table calculation on a monthly axis
Revenue MoM %           = (ZN(SUM([Total Price])) - LOOKUP(ZN(SUM([Total Price])), -1))
                          / ABS(LOOKUP(ZN(SUM([Total Price])), -1))

// 7-day moving average
Revenue 7D Avg          = WINDOW_AVG(SUM([Total Price]), -6, 0)

// Pareto
Running Revenue %       = RUNNING_SUM(SUM([Total Price])) / TOTAL(SUM([Total Price]))
ABC Class               = IF [Running Revenue %] <= 0.80 THEN "A"
                          ELSEIF [Running Revenue %] <= 0.95 THEN "B"
                          ELSE "C" END

// Day-part grouping already exists as [Day Part]; peak flag:
Is Peak Hour            = [Hour 24] >= 11 AND [Hour 24] <= 13
                          OR [Hour 24] >= 17 AND [Hour 24] <= 20
```

For `Revenue MoM %` and `Running Revenue %`, set **Compute Using** explicitly
(`Table (across)` for the monthly axis, `Table (down)` for the Pareto) - leaving
it on Automatic is the most common source of wrong Tableau numbers.

## 4. Worksheets

Build these seven, name each one after its finding:

| Sheet | Marks | Setup |
| --- | --- | --- |
| `KPI Row` | Text | Five separate text sheets, or one with Measure Names on Text |
| `Monthly Revenue Trend` | Bar + Line | Columns `MONTH(Full Date)`, Rows `Revenue`, dual axis with `Revenue 7D Avg`, synchronise axes |
| `Hourly Demand` | Bar | Columns `Hour of Day`, Rows `Orders`, Colour `Is Peak Hour` |
| `Weekday x Hour Heatmap` | Square | Columns `Hour 24`, Rows `Day Short` (sorted Mon-Sun), Colour `Orders`, sequential palette |
| `Category and Size Mix` | Bar | Two sheets: `Pizza Category` by Revenue, `Pizza Size` by Revenue with `Revenue % of Total` on Label |
| `Product Pareto` | Bar + Line | Columns `Pizza` sorted by Revenue descending, Rows `Revenue` (bar) and `Running Revenue %` (line), dual axis, reference line at 80% |
| `Cross-sell Pairs` | Text table | From `tableau_vw_product_affinity`: `Product A`, `Product B`, `Orders Together`, `Lift`; filter `Lift > 1`, sort by `Lift` descending |

## 5. Dashboard assembly

1. **Dashboard > New Dashboard**, size **Automatic** with a fixed 1200 x 900 target.
2. Layout: KPI row across the top, trend chart full width beneath it, then a
   two-column band (hourly demand + heatmap), then Pareto and cross-sell.
3. Add three filters and **Apply to Worksheets > Selected Worksheets** so the
   pre-aggregated affinity sheet is not filtered into emptiness:
   - `Full Date` as a range slider
   - `Pizza Category` as a multi-select checkbox
   - `Pizza Size` as a single-select dropdown
4. Set the hourly-demand sheet as a **filter action** source so clicking an hour
   filters the product Pareto - one click, and the dashboard answers
   "what sells at lunch?".
5. Add a floating text container at the bottom: source file, row count,
   refresh date, and "metric definitions in sql/02_views.sql".
6. Every sheet title is a sentence with a finding in it. Delete "Sheet 1"
   everywhere.
7. **Device layouts**: add a phone layout - reviewers open portfolio links on phones.

## 6. Publish to Tableau Public

1. Create a free account at <https://public.tableau.com>.
2. **Server > Tableau Public > Save to Tableau Public As...**
3. Name it `Pizza Sales Performance 2015 - <your name>`.
4. In your profile, set the workbook thumbnail and add a description with the
   three headline findings.
5. Copy the link into this repo's README and into your CV.

**Anything published to Tableau Public is world-readable.** This dataset is
synthetic sales data with no personal information, so it is safe. Never publish
client data there.

## 7. Save into the repo

Save the workbook as `reports/pizza_sales_dashboard.twbx` (packaged, so the
extract travels with it) and export **Dashboard > Export > Image** to
`reports/tableau_dashboard.png`.
