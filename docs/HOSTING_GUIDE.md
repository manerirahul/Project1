# Hosting guide - free managed PostgreSQL

This is step 2 and 3 of the project: choosing where the cleaned warehouse lives,
and the exact steps used to host it. **No paid tier, no credit card.**

---

## 1. Why PostgreSQL, and why a managed free tier

The options considered, and why they were rejected or chosen:

| Option | Free? | BI tool support | Verdict |
| --- | --- | --- | --- |
| Keep CSV files on disk | Yes | Both, but file-based | Rejected: no single source of truth, no SQL layer, no concurrent access, breaks the moment two people refresh |
| SQLite file in the repo | Yes | Poor - Power BI needs an ODBC driver, Tableau needs a connector | Rejected: not a server, so no shared refresh |
| Google Sheets | Yes | Both | Rejected: hard row limits, no types, no joins, no indexes |
| MySQL free tier | Yes | Both | Workable, but weaker window functions - this project leans on them heavily |
| **Supabase (managed PostgreSQL)** | **Yes - free tier** | **Native connector in both Power BI and Tableau** | **Chosen** |
| Snowflake / BigQuery | Trial credits only | Excellent | Rejected: not free indefinitely |

PostgreSQL wins because the reporting layer in `sql/02_views.sql` uses window
functions (`LAG`, `RANK`, running totals, moving averages) and a self-join
market-basket calculation. Pushing that logic into the database means Power BI
and Tableau read the *same* numbers instead of each re-implementing them.

**Free-tier reality check:** 500 MB database, 2 projects, pauses after 7 days of
inactivity (one click to resume). This warehouse is roughly 6 MB loaded, so it
fits with room to spare.

---

## 2. Create the database

1. Go to <https://supabase.com> and sign up (GitHub login works, no card).
2. **New project.** Set:
   - **Name:** `pizza-sales-analytics`
   - **Database password:** generate a strong one and save it in a password manager.
     You cannot recover it later, only reset it.
   - **Region:** the one closest to you - it directly affects BI refresh speed.
3. Wait about two minutes for provisioning.

## 3. Collect the connection details

In the project dashboard, open **Connect** (top bar) and choose
**Session pooler** (port `5432`). Use the pooler rather than the direct
connection: it is IPv4-friendly, which is what Power BI Desktop and Tableau
need on most home and corporate networks.

You will get five values:

| Field | Example | Where it goes |
| --- | --- | --- |
| Host | `aws-0-<region>.pooler.supabase.com` | `PGHOST` |
| Port | `5432` | `PGPORT` |
| Database | `postgres` | `PGDATABASE` |
| User | `postgres.<your-project-ref>` | `PGUSER` |
| Password | the one you saved | `PGPASSWORD` |

## 4. Point the pipeline at it

```bash
cp .env.example .env
# edit .env and paste the five values
```

`.env` is git-ignored. **Never commit it** - a leaked database password is the
single most common mistake in portfolio repos.

## 5. Create the schema and load the data

```bash
make install     # one time
make transform   # builds data/processed/*.csv from the raw file
make quality     # 14 assertions - must pass before loading
make load        # applies sql/01_schema.sql + sql/02_views.sql, then loads
```

`make load` prints a verification block. It must show:

```
  dim_date                       365 rows  OK
  dim_time                        24 rows  OK
  dim_pizza                       91 rows  OK
  dim_ingredient                  65 rows  OK
  bridge_pizza_ingredient        518 rows  OK
  fact_order_items            48,620 rows  OK
  total revenue in warehouse : 817,860.05
```

If `total revenue` is not `817,860.05`, the load is incomplete - re-run it. The
load truncates and reloads inside one transaction, so re-running is always safe.

## 6. Confirm from SQL

In the Supabase dashboard, open **SQL Editor** and run:

```sql
SELECT * FROM public.vw_kpi_headline;
```

You should see 817,860.05 revenue, 49,574 pizzas, 21,350 orders, 38.31 average
order value.

## 7. Create a read-only reporting user (recommended)

Never point a dashboard at the owner account. Run this once in the SQL Editor:

```sql
CREATE ROLE bi_reader LOGIN PASSWORD 'choose-a-different-strong-password';
GRANT CONNECT ON DATABASE postgres TO bi_reader;
GRANT USAGE  ON SCHEMA public TO bi_reader;
GRANT SELECT  ON ALL TABLES IN SCHEMA public TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_reader;
```

Use `bi_reader` in Power BI and Tableau. It can read everything and change
nothing - the standard separation an employer expects to see.

---

## 8. Keeping the free tier alive

- The project pauses after 7 days with no activity. Resume is one click and no
  data is lost, but a paused database makes a portfolio link look broken.
- Open the dashboard or refresh a report once a week, or publish a Tableau Public
  extract so the visual survives a pause.

## 9. Operating the pipeline afterwards

| Task | Command |
| --- | --- |
| New source file dropped in `data/raw/` | `make all` |
| Reload data only, schema unchanged | `python -m src.load_to_postgres --skip-ddl` |
| Change a metric definition | edit `sql/02_views.sql`, re-run `make load` |
| Verify the warehouse still ties out | run Q13 in `sql/03_kpi_queries.sql` |

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Database credentials missing` | `.env` not filled in | copy `.env.example`, add the five values |
| `password authentication failed` | wrong user format | the pooler user is `postgres.<project-ref>`, not `postgres` |
| Connection times out | using the direct connection on an IPv4-only network | switch to the Session pooler host |
| `SSL connection required` | `PGSSLMODE` unset | set `PGSSLMODE=require` |
| `relation "fact_order_items" does not exist` | DDL never applied | run `make load` without `--skip-ddl` |
| Load is very slow | chunk size too large for the free tier | lower `LOAD_CHUNK_SIZE` to `2000` |
