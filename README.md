# Pizza Sales Analytics - end-to-end BI project

Raw CSV to hosted PostgreSQL warehouse to Power BI / Tableau dashboards, with a
tested Python pipeline in between.

**Dataset:** 48,620 pizza line items, 21,350 orders, full year 2015,
**$817,860.05** revenue.

| | |
| --- | --- |
| **Pipeline** | Python 3.11+, pandas, SQLAlchemy |
| **Warehouse** | PostgreSQL 15 (Supabase free tier - no card, no subscription) |
| **Model** | Kimball star schema: 1 fact, 3 conformed dimensions, 1 recipe bridge |
| **Semantic layer** | 12 SQL views - the single source of metric truth |
| **BI** | Power BI Desktop (free) and Tableau Public (free) |
| **Quality** | 14 assertions, non-zero exit, CI-ready |

---

## Quick start

```bash
git clone <your-repo-url> && cd pizza-sales-analytics
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install

make profile        # -> reports/data_profile.md
make transform      # -> data/processed/*.csv
make quality        # 14 assertions; fails loudly if the data is wrong

cp .env.example .env   # add your PostgreSQL credentials
make load           # schema + views + data, in one transaction

make analysis       # -> reports/*.png + reports/insights.md
```

No database yet? `python -m src.analysis --local` runs the whole analysis off the
processed CSVs.

Everything at once: `make all`.

---

## Repository layout

```text
pizza-sales-analytics/
├── data/
│   ├── raw/pizza_sales.csv            immutable source (tracked)
│   └── processed/                     star-schema CSVs (git-ignored)
├── src/
│   ├── config.py                      paths, env-based credentials, business constants
│   ├── profile_data.py                profile the source before cleaning
│   ├── transform.py                   clean + conform + build the star schema
│   ├── data_quality.py                14 assertions, non-zero exit
│   ├── load_to_postgres.py            transactional, idempotent load + verification
│   └── analysis.py                    charts and written insights
├── sql/
│   ├── 01_schema.sql                  DDL, constraints, indexes, grants
│   ├── 02_views.sql                   12 reporting views (the semantic layer)
│   └── 03_kpi_queries.sql             13 standalone analyst queries
├── docs/
│   ├── PROJECT_WALKTHROUGH.md         end-to-end story and design decisions
│   ├── HOSTING_GUIDE.md               where and how the data is hosted, free
│   ├── DATA_DICTIONARY.md             grain, keys, every column, known limits
│   ├── POWER_BI_GUIDE.md              connection, model, 15 DAX measures, 4 pages
│   └── TABLEAU_GUIDE.md               calc fields, 7 worksheets, publishing
├── reports/                           profile, quality report, charts, insights
├── requirements.txt
├── Makefile
└── .env.example
```

## The data model

```text
              dim_date (365)
                   |
 dim_time (24) --- fact_order_items (48,620) --- dim_pizza (91)
                                                     |
                                     bridge_pizza_ingredient (518)
                                                     |
                                            dim_ingredient (65)
```

Full column reference: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

## Headline results

| KPI | Value |
| --- | --- |
| Total revenue | $817,860.05 |
| Pizzas sold | 49,574 |
| Orders | 21,350 |
| Average order value | $38.31 |
| Pizzas per order | 2.32 |
| Trading days | 358 of 365 |
| Revenue per trading day | $2,284.53 |

**Six findings**

1. Lunch (11-13) and dinner (17-20) carry **68%** of orders; 12:00 is the single
   busiest hour - capacity, not demand, is the midday constraint.
2. Friday is the strongest day and Sunday the weakest, a **43%** gap - plannable,
   not noise.
3. Revenue is flat all year (MoM within 10%) - growth must come from mix.
4. **21 of 32** products make the first 80% of revenue; 4 C-class items add under 7%.
5. Categories sit within 3 points of each other, but size **L alone is 46%** of
   revenue - upsizing is the highest-margin lever.
6. **38%** of orders contain one pizza - `vw_product_affinity` names the pairs
   with genuine affinity (lift > 1) to prompt at checkout.

Full write-up with recommendations: [`reports/insights.md`](reports/insights.md).

## Where the data is hosted

Supabase managed PostgreSQL on the permanently free tier: 500 MB storage, no
card, no subscription. This warehouse is about 6 MB. Chosen over CSV files,
SQLite and Google Sheets because the reporting layer relies on real window
functions and both BI tools have a native PostgreSQL connector.

Setup, connection strings, a read-only `bi_reader` role, and troubleshooting:
[`docs/HOSTING_GUIDE.md`](docs/HOSTING_GUIDE.md).

## Design principles

1. **Profile before cleaning** - and commit the profile.
2. **Recompute revenue, keep the source value** - `total_price` is derived from
   `unit_price * quantity`; the supplied figure survives as
   `total_price_source` with a variance flag.
3. **Quarantine, don't drop** - invalid rows go to `rejected_rows.csv` with reasons.
4. **Quality gate is a gate** - non-zero exit stops a bad load.
5. **Transactional, idempotent loads** - re-running is always safe.
6. **Metrics live in SQL views** - Power BI and Tableau cannot disagree.
7. **Credentials from the environment only** - `.env` is git-ignored; reporting
   runs as a read-only role.
8. **Document the limits** - no cost, store, channel or customer data, so no
   margin, geography or retention analysis. Stated, not hidden.

## Known limitations

- Single year (2015): no year-over-year comparison possible.
- No cost or margin: revenue and mix analysis only.
- No customer identifier: `order_id` is a basket, not a person.
- 7 zero-sales days: probable closures, unconfirmed by the source.
- `is_vegetarian` is derived from recipe text - an analytical convenience, not a
  certified dietary claim.

## Roadmap

Cost/margin data, SCD Type 2 on `dim_pizza`, dbt for the transform layer,
orchestration via GitHub Actions, and incremental loads keyed on `order_ts`.

## Licence

MIT for the code. The dataset is a widely circulated synthetic pizza-sales file
containing no personal data.

---

## Presentation layer

- `portfolio/index.html` - open in any browser. A single self-contained case-study page: framing, KPIs, the pipeline, the data model, the six findings, chart gallery, repo map and stated scope limits. This is the artefact to share.
- `docs/HOW_TO_PRESENT.md` - the one-minute pitch, a ten-minute walkthrough script, and prepared answers to the five questions reviewers ask.
- `bi/` - Power BI (Power Query M + 27 DAX measures + 4-page spec) and Tableau (`.tds` datasource + calculated fields/LODs + 3-dashboard spec). Save the built `.pbix` and `.twbx` here to make the repo fully self-contained; see `bi/README.md`.
