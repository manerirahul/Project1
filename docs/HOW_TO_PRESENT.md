# How to present this project

## The one-minute version (interview opener)

> "I took a raw year of pizza sales — about 48,600 transaction lines — and built the
> full path a business would actually need: profiled and cleaned the data, modelled it
> into a Kimball star schema, hosted it on managed PostgreSQL, put the business logic
> into SQL views so Power BI and Tableau report identical numbers, and wrapped the
> whole thing in a 14-check quality gate that fails the build rather than shipping bad
> data. The headline finding is that revenue is flat and mature, so growth has to come
> from mix — large pizzas alone are 46% of revenue and 38% of orders are a single pizza."

## The ten-minute walkthrough

| Minute | Show | Say |
| --- | --- | --- |
| 0-1 | `portfolio/index.html` in a browser | The framing and the headline numbers |
| 1-3 | `src/transform.py`, then `reports/data_quality_report.md` | How bad rows are quarantined with a reason, never silently dropped; the gate exits non-zero |
| 3-5 | The star-schema diagram, then `sql/02_views.sql` | Why the recipe is a bridge, not a delimited string; why logic lives in SQL not in DAX |
| 5-8 | The Power BI report, then the Tableau dashboard | Same numbers from two tools — that is the point of the semantic layer |
| 8-10 | `reports/insights.md` | Each finding as number → so-what → action, plus the stated scope limits |

## Questions you will be asked, and the answers

**"Why PostgreSQL and not just CSVs or Excel?"**
The reporting layer leans on window functions — running totals, LAG, RANK, moving
averages — and a self-join market-basket calculation. A file has no place to put that,
so each BI tool would re-implement it and they would drift. The comparison table in
`docs/HOSTING_GUIDE.md` shows the five options considered.

**"Why a star schema and not one flat table?"**
The recipe relationship is genuinely many-to-many — 91 pizzas, 65 ingredients, 518
links. Flattening it either duplicates revenue or hides the ingredients. The star
keeps the fact at line-item grain and resolves the recipe through a bridge, so
ingredient exposure can be measured without double-counting sales.

**"How do you know the numbers are right?"**
14 assertions, 11 of them blocking: row counts against source, key integrity on every
dimension, revenue reconciled against price × quantity, calendar continuity, and grain
uniqueness. All 14 pass, 0 rows rejected, and `total_price` is recomputed with the
original kept alongside for audit.

**"What would you do next with more data?"**
Cost and margin, to move from revenue to contribution. Store and channel, to separate
a network effect from a site effect. A customer identifier, to shift from basket
analysis to retention and lifetime value.

**"Is this in production?"**
The load is idempotent and runs in one transaction, the quality gate is CI-ready, and
the Power BI dataset refreshes on a schedule without a gateway. What is missing for
true production is orchestration and alerting — I would put the DAG on a scheduler and
route gate failures to a channel.

## Before you share it

1. Build and save `bi/powerbi/pizza_sales.pbix` and `bi/tableau/pizza_sales.twbx`.
2. Publish the Tableau workbook and paste the link into `README.md` and
   `portfolio/index.html` (replace `TABLEAU_PUBLIC_URL`).
3. Export the Power BI report to PDF into `reports/` so reviewers without Desktop can read it.
4. Add your GitHub URL to the footer of `portfolio/index.html`.
5. Confirm `.env` is **not** committed — only `.env.example` belongs in the repo.
