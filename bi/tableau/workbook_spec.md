# Tableau workbook specification

Datasource: `pizza_sales_warehouse.tds` → `vw_fact_enriched` (flat, one row per
line item, already joined). Add `vw_product_affinity` as a second datasource for
the basket sheet.

Colour palette to match the Power BI build: background `#111827`, marks
`#F97316`, sequential heat `#7C2D12 → #FDBA74`, positive `#10B981`, negative `#EF4444`.

---

## Sheets to build

| Sheet | Mark type | Rows / Columns | Notes |
| --- | --- | --- | --- |
| `KPI Strip` | Text | Measure Names / Measure Values | Revenue, Orders, Pizzas Sold, AOV, Pizzas per Order |
| `Daily Trend` | Line | MDY(Order Date) × Revenue + Revenue 7D Moving Average | dual axis, synchronised |
| `Monthly Revenue` | Bar | MONTH(Order Date) × Revenue | label with Revenue MoM %, colour red/green |
| `Category Mix` | Pie or treemap | Category × Revenue | |
| `Size Mix` | Bar | Size Label × Revenue | sort by Size Order, not alphabetically |
| `Hour Weekday Heatmap` | Square | Weekday Name (rows) × Hour Of Day (columns), colour Orders | the staffing sheet |
| `Day Part Split` | Bar | Day Part × Orders | |
| `Pareto` | Dual axis | Pizza Name (sorted desc) × Revenue bars + Pareto Cumulative % line | reference line at 80% |
| `Top N Products` | Bar | Pizza Name × Selected Metric | uses Top N Filter + Metric parameter |
| `Price vs Volume` | Circle | Pizzas Sold × Average Unit Price, size Revenue, colour Category | |
| `Basket Affinity` | Highlight table | Pizza A × Pizza B, colour Lift | filter Lift > 1.2 |

## Dashboards (3)

1. **Executive** — KPI Strip, Daily Trend, Monthly Revenue, Category Mix, Size Mix.
   Size: fixed 1200×900. Floating title band with the accent colour.
2. **Demand** — Hour Weekday Heatmap, Day Part Split, plus a text box stating the
   lunch+dinner share and the staffing recommendation.
3. **Product & Basket** — Pareto, Top N Products, Price vs Volume, Basket Affinity.

Add on every dashboard: a Month filter, Category filter, and Size filter,
each applied to *all sheets using this datasource*. Add the `Metric` and
`Top N` parameter controls to dashboard 3.

Use **Dashboard > Actions > Filter** so clicking a category on Executive
drills the Product dashboard — that interaction is what separates a portfolio
piece from a screenshot.

---

## Publishing to Tableau Public (free)

1. **Data > `pizza_sales_warehouse` > Extract** — Tableau Public cannot hold a
   live database connection, and you must never publish credentials.
2. **Server > Tableau Public > Save to Tableau Public**, sign in with a free account.
3. **Everything on Tableau Public is world-readable.** This dataset is a public
   sample, so that is fine here. Never publish client data this way.
4. Copy the published URL into the repo `README.md` and into
   `portfolio/index.html` (the `TABLEAU_PUBLIC_URL` placeholder).
5. Keep the `.twbx` in `bi/tableau/` so a reviewer can open the real workbook offline.
