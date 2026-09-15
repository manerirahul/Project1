# Power BI report specification

Four pages. Build them in this order — each answers one business question.
Every number comes from the measures in `02_measures_dax.txt`, which read the
warehouse views, so the report can never disagree with `reports/insights.md`.

Theme: dark slate canvas `#111827`, card surface `#1F2937`, accent `#F97316`
(pizza orange), positive `#10B981`, negative `#EF4444`, font Segoe UI Semibold
for titles. Save it as a JSON theme so all pages match.

---

## Page 1 — Executive summary

| Zone | Visual | Fields |
| --- | --- | --- |
| Top strip | 5 KPI cards | Revenue, Orders, Pizzas Sold, Average Order Value, Pizzas per Order |
| Left | Line chart, Revenue + Revenue 7D Moving Average by `dim_date[date]` | shows the flat baseline |
| Right | Column chart, Revenue by `dim_date[month_name]` with Revenue MoM % as a tooltip | |
| Bottom left | Donut, Revenue by `dim_pizza[category]` | |
| Bottom right | Bar, Revenue by `dim_pizza[size_label]` sorted by `size_order` | |
| Footer | Card with `Data Trust Label` | proves the quality gate ran |

Slicers (sync across all pages): month, category, size, day part.

## Page 2 — Demand and staffing

- Matrix heat map: rows `dim_date[weekday_name]`, columns `dim_time[hour_of_day]`, values Orders, conditional-format background on the accent scale.
- Column chart: Orders by `dim_time[hour_of_day]`, with a constant line at the average.
- Donut: Orders by `dim_time[day_part]`.
- KPI card: `Peak Trading Windows %`.
- Narrative text box: "Lunch and dinner carry X% of orders — roster to the curve, not to flat shifts."

## Page 3 — Product performance

- Pareto combo chart: Revenue columns by `dim_pizza[pizza_name]` (sorted desc) + `Pareto %` line on a secondary axis, with a constant line at 80%.
- Table: pizza name, category, size, Revenue, Pizzas Sold, `Revenue % of Total`, `abc_class` from `vw_product_performance`.
- Scatter: Pizzas Sold (x) vs Average Unit Price (y), bubble size Revenue, legend category — separates volume drivers from margin drivers.
- Bar: bottom 10 by Revenue — the delist candidates.

## Page 4 — Basket and ingredients

- Table from `vw_product_affinity`: pizza A, pizza B, support, confidence, lift; filter `lift > 1.2` and sort by lift desc. This is the bundle shortlist.
- Bar: Revenue exposure by `dim_ingredient[ingredient_name]` (top 20) via the bridge table — supply-risk view.
- Card: count of ingredients that touch more than 25% of revenue.

---

## Publishing

1. **File > Publish > My workspace** (free Power BI account is enough).
2. Because the model is Import mode, set a scheduled refresh: workspace >
   dataset > Settings > Data source credentials (enter the Postgres user and
   password, Encryption = enabled) > Scheduled refresh, once daily.
   A gateway is **not** needed — Supabase is a public cloud endpoint.
3. Free accounts cannot share a workspace app. For a portfolio, use
   **File > Export > PDF** plus screenshots, or upgrade the workspace later.
   Keep the `.pbix` in `bi/powerbi/` so anyone can open the real thing.
