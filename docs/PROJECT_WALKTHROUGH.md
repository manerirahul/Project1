# End-to-end walkthrough

How the project runs from a raw CSV to a dashboard, and why each decision was
made. This is the document to read before an interview about this repo.

---

## The architecture

```text
data/raw/pizza_sales.csv          48,620 rows, one line item per row
        |
        |  src/profile_data.py     profile before touching anything
        v                          -> reports/data_profile.md
        |
        |  src/transform.py        clean, conform, model
        v                          -> data/processed/*.csv  (+ rejected_rows.csv)
        |
        |  src/data_quality.py     14 assertions, non-zero exit on failure
        v                          -> reports/data_quality_report.md
        |
        |  src/load_to_postgres.py DDL + transactional truncate-and-load
        v
   PostgreSQL (Supabase free tier)
     6 tables + 12 reporting views  <- sql/01_schema.sql, sql/02_views.sql
        |
        +--> src/analysis.py  -> reports/*.png, reports/insights.md
        +--> Power BI Desktop (Import via Npgsql)
        +--> Tableau (Desktop live, or Public via view exports)
```

One rule governs the whole design: **business logic lives in SQL views, not in
the BI tool.** Two dashboards read the same 12 views, so Power BI and Tableau
cannot report different revenue. That single decision is what makes this an
engineering project rather than a chart exercise.

---

## Step 1 - Profile before cleaning

`python -m src.profile_data`

Never clean data you have not measured. The profile records row count, dtypes,
null counts, distinct counts, min/max, and candidate keys, and writes
`reports/data_profile.md`.

What it found:

- 48,620 rows, 12 columns, **zero nulls, zero duplicate rows**
- `pizza_id` unique -> line-item grain confirmed
- 21,350 distinct `order_id` -> the basket grain
- Dates as `dd-mm-yyyy` text; times as `HH:MM:SS` text
- Full-year 2015 coverage
- Every `total_price` equals `unit_price * quantity`

That last check is the important one. It means the source is internally
consistent, so the pipeline does not have to *fix* revenue - it only has to
*prove* revenue, and record the proof.

## Step 2 - Clean, conform, model

`python -m src.transform`

Cleaning applied:

| Action | Reason |
| --- | --- |
| Parse dates with an explicit `%d-%m-%Y` format | Never let pandas guess: `03-04-2015` is ambiguous and silent inference is how a day/month swap reaches a board pack |
| Combine date + time into `order_ts` | One temporal fact column, dimensions derived from it |
| Trim and collapse whitespace on all text | Prevents `"Classic "` and `"Classic"` becoming two slicer values |
| Title-case ingredient names | Same reason, at ingredient grain |
| Recompute `total_price` from `unit_price * quantity` | Revenue is derived, never trusted from a supplied column; source kept in `total_price_source` with a `price_variance_flag` |
| Drop `pizza_ingredients` duplication into a bridge table | Makes ingredient exposure analysable rather than a text blob |
| Quarantine invalid rows to `data/processed/rejected_rows.csv` with a reason | An analyst who silently drops rows cannot answer "what did you drop?" |
| Drop nothing else | The source has no redundant columns; `pizza_name` and `pizza_size` become dimension attributes, not deletions |

Rows rejected: **0**. The quarantine mechanism still exists because next month's
file will not be this clean.

Modelling: Kimball star schema (see `docs/DATA_DICTIONARY.md`). Why not one flat
table? Because a flat table cannot hold a gap-free calendar, cannot express the
many-to-many recipe relationship, and forces every filter to scan the widest
table in the model. `vw_fact_enriched` still provides the flat shape for anyone
who wants it.

The transform is **idempotent** - running it twice produces byte-identical
output, because surrogate keys are assigned by a deterministic sort, not by
insertion order.

## Step 3 - Prove quality before loading

`python -m src.data_quality`

14 assertions, 11 error-level and 3 warnings. They cover row counts, primary-key
uniqueness, referential integrity on all three fact-to-dimension keys, no nulls
in key columns, positive quantity and price, revenue tie-out to the raw file,
calendar contiguity, and bridge integrity.

The module exits non-zero on any error, so it works unchanged as a CI gate:

```yaml
- run: python -m src.transform
- run: python -m src.data_quality   # pipeline fails here if the data is wrong
```

That gate is the difference between "I cleaned the data" and "the data cannot
silently break".

## Step 4 - Host and load

See `docs/HOSTING_GUIDE.md` for the full hosting decision and setup.

Short version: **Supabase managed PostgreSQL, free tier, no card.** Chosen over
CSV, SQLite, and Sheets because the reporting layer needs real window functions
and both BI tools have a native PostgreSQL connector.

`python -m src.load_to_postgres` then:

1. Applies `sql/01_schema.sql` and `sql/02_views.sql`
2. `TRUNCATE ... RESTART IDENTITY CASCADE` in dependency order
3. Loads dimensions, then the bridge, then streams the fact in 5,000-row chunks
4. Wraps the whole load in **one transaction** - a failure leaves the warehouse
   at its previous state, never half-loaded
5. Verifies row counts and total revenue after commit

Loaded and verified: 48,620 fact rows, **$817,860.05** total revenue, matching
the raw file exactly.

## Step 5 - The semantic layer

`sql/02_views.sql` - 12 `security_invoker` views. They are the contract between
the warehouse and every consumer. If "average order value" needs redefining, it
changes in one place and both dashboards follow.

`sql/03_kpi_queries.sql` holds 13 standalone analyst queries for ad-hoc work and
for demonstrating SQL depth in a review: window functions, `GROUPING SETS`,
running totals, ABC classification, and a self-join market-basket calculation
with support, confidence and lift.

## Step 6 - Python analysis layer

`python -m src.analysis` (add `--local` to read the processed CSVs instead of the
database - useful offline or before hosting is configured).

Produces five charts and `reports/insights.md`. Every insight follows the
**number, so-what, action** structure, which is the difference between reporting
and analysis:

> 38% of orders contain a single pizza. So what: basket size, not footfall, is
> the constraint. Action: prompt the top affinity pairs at checkout.

## Step 7 - Dashboards

- `docs/POWER_BI_GUIDE.md` - Postgres connection, star-schema relationships,
  date table marking, sort-by-column fixes, 15 DAX measures, four report pages,
  polish checklist.
- `docs/TABLEAU_GUIDE.md` - the honest constraint (Tableau Public cannot reach a
  database), the view-export workaround, calculated fields, seven worksheets,
  dashboard assembly, publishing.

---

## The findings, in one paragraph

$817,860 revenue across 21,350 orders and 49,574 pizzas in 2015; AOV $38.31 at
2.32 pizzas per order. Revenue is flat month to month (within 10%), so growth
must come from mix, not footfall. Demand is concentrated: lunch and dinner carry
68% of orders and 12:00 is the single busiest hour, making labour and oven
capacity the midday constraint. Categories sit within 3 points of each other, but
**size** drives it - L alone is 46% of revenue, making upsizing the
highest-leverage prompt available. 21 of 32 products produce the first 80% of
revenue while 4 C-class items contribute under 7%, so there is a clear
menu-rationalisation case. The biggest untapped lever is basket size: 38% of
orders are a single pizza, and `vw_product_affinity` identifies which pairs
genuinely co-occur above chance (lift > 1) for cross-sell prompts.

## What a reviewer should notice

1. Profiling precedes cleaning, and the profile is committed.
2. Revenue is recomputed and reconciled, with the source value retained for audit.
3. Rejected rows are quarantined with reasons, not dropped.
4. Quality gate exits non-zero - CI-ready.
5. Load is transactional and idempotent, with post-load verification.
6. Metric logic sits in SQL views, so two BI tools cannot disagree.
7. Credentials come from the environment; `.env` is git-ignored; a read-only
   `bi_reader` role is used for reporting.
8. Data limitations are documented rather than hidden.

## What would come next in a real engagement

- Cost and margin data, to move from revenue analysis to profitability.
- Store, channel and customer identifiers, enabling geography and retention.
- SCD Type 2 on `dim_pizza` so price changes are tracked historically.
- Orchestration (Airflow, Dagster or GitHub Actions on a schedule) instead of `make`.
- dbt for the transform layer, with tests replacing `data_quality.py`.
- Incremental loads keyed on `order_ts` once the source grows beyond a full reload.
