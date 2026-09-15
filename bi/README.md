# BI layer

This folder holds everything needed to rebuild the dashboards, plus the place
where your saved binaries live.

```
bi/
  powerbi/
    01_power_query_M.txt     paste-ready connection queries + relationship map
    02_measures_dax.txt      27 DAX measures (core, time intelligence, Pareto, basket)
    03_report_spec.md        page-by-page build + publish steps
    pizza_sales.pbix         <- YOU save this here after building (see note)
  tableau/
    pizza_sales_warehouse.tds  datasource file - edit 2 placeholders, double-click
    calculated_fields.txt      calculated fields, LODs, parameters
    workbook_spec.md           sheet + dashboard build and publish steps
    pizza_sales.twbx           <- YOU save this here after building
```

## Why the .pbix and .twbx are not in the repo yet

Both are proprietary binary formats that only Power BI Desktop and Tableau
Desktop can write — they cannot be generated from a script. What *can* be
generated is everything that goes inside them, and that is what these files
are: the queries, the model relationships, every measure and calculated field,
and the exact layout.

Build time from these specs is roughly 45 minutes per tool. When you save the
files here, the repo becomes fully self-contained:

```
git add bi/powerbi/pizza_sales.pbix bi/tableau/pizza_sales.twbx
```

Both are large binaries — if either exceeds 100 MB, use Git LFS.

## Order of work

1. `docs/HOSTING_GUIDE.md` — get the five connection values.
2. Power BI: `01_power_query_M.txt` → relationships → `02_measures_dax.txt` → `03_report_spec.md`.
3. Tableau: edit `pizza_sales_warehouse.tds` → `calculated_fields.txt` → `workbook_spec.md`.
4. Publish, then paste both links into `README.md` and `portfolio/index.html`.
