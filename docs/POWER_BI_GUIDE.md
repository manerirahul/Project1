# Power BI dashboard - build guide

Power BI Desktop is free on Windows (Microsoft Store or
<https://powerbi.microsoft.com/desktop/>). Publishing to the Power BI *Service*
needs a Fabric/Pro licence, so for a free portfolio: keep the `.pbix` in this
repo and export a PDF or screenshots.

---

## 1. Connect

**Home > Get data > More > Database > PostgreSQL database**

| Field | Value |
| --- | --- |
| Server | `aws-0-<region>.pooler.supabase.com:5432` (host and port in one box, colon-separated) |
| Database | `postgres` |
| Data Connectivity mode | **Import** |

Credentials: **Database** tab, user `bi_reader`, your password. Encryption
warning: tick "use encrypted connection".

> If Power BI asks for the Npgsql provider, install
> <https://github.com/npgsql/npgsql/releases> and restart Power BI.

**Import vs DirectQuery:** use Import. The dataset is ~50k rows, so it refreshes
in seconds, all DAX time intelligence works, and a paused free-tier database
does not break the report.

## 2. Choose your tables

In Navigator select the five model objects, not the wide view:

- `dim_date`, `dim_time`, `dim_pizza`, `fact_order_items`
- `dim_ingredient` and `bridge_pizza_ingredient` only if you build the
  ingredient page

Then **Transform Data** and remove the columns you will not display
(`total_price_source`, `price_variance_flag`, `min_unit_price`, `max_unit_price`)
so the model stays lean. Close and Apply.

> Prefer one table? Import `vw_fact_enriched` alone. It is simpler but you lose
> proper star-schema filtering, so it is not what this guide builds.

## 3. Model relationships

**Model view.** Power BI usually auto-detects these; verify each one:

```text
dim_date[date_key]   1 ─── * fact_order_items[date_key]
dim_time[time_key]   1 ─── * fact_order_items[time_key]
dim_pizza[pizza_key] 1 ─── * fact_order_items[pizza_key]
```

All three: **single** cross-filter direction, dimension to fact. Never
bi-directional - it creates ambiguous filter paths that silently change totals.

Then:

1. Select `dim_date` > **Table tools > Mark as date table** > date column `full_date`.
2. `dim_date[month_short]` > **Column tools > Sort by column** > `month_number`.
3. `dim_date[day_short]` > sort by `day_of_week`.
4. `dim_pizza[pizza_size]` > sort by `size_sort_order`.
5. Hide every `*_key` column from report view.

Steps 2-4 are what stop your axis reading "Apr, Aug, Dec" instead of
"Jan, Feb, Mar".

## 4. Measures (DAX)

Create a dedicated measure table: **Home > Enter data**, name it `_Measures`,
one dummy column, load, delete the column. Put every measure there.

```dax
Total Revenue        = SUM ( fact_order_items[total_price] )
Pizzas Sold          = SUM ( fact_order_items[quantity] )
Total Orders         = DISTINCTCOUNT ( fact_order_items[order_id] )
Trading Days         = DISTINCTCOUNT ( fact_order_items[date_key] )

Avg Order Value      = DIVIDE ( [Total Revenue], [Total Orders] )
Avg Pizzas per Order = DIVIDE ( [Pizzas Sold], [Total Orders] )
Revenue per Day      = DIVIDE ( [Total Revenue], [Trading Days] )
Orders per Day       = DIVIDE ( [Total Orders], [Trading Days] )

-- Time intelligence: needs the marked date table and the gap-free dim_date
Revenue YTD          = TOTALYTD ( [Total Revenue], dim_date[full_date] )
Revenue PM           = CALCULATE ( [Total Revenue], PREVIOUSMONTH ( dim_date[full_date] ) )
Revenue MoM %        =
VAR Prev = [Revenue PM]
RETURN DIVIDE ( [Total Revenue] - Prev, Prev )

Revenue 7D Avg       =
AVERAGEX (
    DATESINPERIOD ( dim_date[full_date], MAX ( dim_date[full_date] ), -7, DAY ),
    [Total Revenue]
)

-- Mix and ranking
Revenue % of Total   =
DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], ALLSELECTED ( dim_pizza ) ) )

Product Rank         =
RANK ( DENSE, ALLSELECTED ( dim_pizza[pizza_short_name] ), ORDERBY ( [Total Revenue], DESC ) )

Revenue Running %    =
VAR Cur = [Total Revenue]
VAR Tbl = ADDCOLUMNS ( ALLSELECTED ( dim_pizza[pizza_short_name] ), "@r", [Total Revenue] )
RETURN DIVIDE (
    SUMX ( FILTER ( Tbl, [@r] >= Cur ), [@r] ),
    SUMX ( Tbl, [@r] )
)
```

Format `Total Revenue`, `Avg Order Value` and `Revenue per Day` as currency with
0 or 2 decimals; format `Revenue MoM %` and the two `%` measures as percentage.

## 5. Report pages

Four pages, each answering one question. Keep one idea per visual.

### Page 1 - Executive summary

| Visual | Type | Fields |
| --- | --- | --- |
| KPI row | 5 x Card | Total Revenue, Pizzas Sold, Total Orders, Avg Order Value, Avg Pizzas per Order |
| Revenue trend | Line chart | Axis `dim_date[month_short]`, values Total Revenue and Revenue 7D Avg |
| Category mix | Donut | Legend `dim_pizza[pizza_category]`, values Total Revenue |
| Size mix | Stacked bar | Axis `dim_pizza[pizza_size]`, values Total Revenue |
| Top 5 products | Bar | Axis `pizza_short_name`, values Total Revenue, filter Top N = 5 by Total Revenue |
| Slicers | 3 x Slicer | `dim_date[full_date]` (between), `pizza_category`, `pizza_size` |

### Page 2 - Demand and operations

- Column chart: `dim_time[hour_label]` by Total Orders. Conditional formatting on
  the bars so the top quintile is highlighted.
- Matrix heatmap: rows `dim_date[day_short]`, columns `dim_time[hour_24]`,
  values Total Orders, **Format > Cell elements > Background colour > on**.
- Column chart: `dim_date[day_short]` by Orders per Day.
- Card: busiest hour - `CONCATENATEX ( TOPN ( 1, VALUES ( dim_time[hour_label] ), [Total Orders] ), dim_time[hour_label] )`.

### Page 3 - Menu engineering

- Table: `pizza_short_name`, Total Revenue, Pizzas Sold, Product Rank,
  Revenue % of Total, Revenue Running %. Sort by Total Revenue descending.
- Pareto combo chart (**Line and clustered column**): axis
  `pizza_short_name`, column Total Revenue, line Revenue Running %, sorted by
  revenue descending. Add a constant line at 80% on the line axis.
- Scatter: X = Pizzas Sold, Y = `AVERAGE(dim_pizza[unit_price])`, size = Total
  Revenue, details = `pizza_short_name`. This is the classic menu-engineering
  quadrant: high volume + high price is your star, low + low is a delist candidate.

### Page 4 - Basket and cross-sell

- Import `vw_basket_profile` and `vw_product_affinity` as two extra tables
  (they aggregate at order-pair grain and do not join the star schema - leave
  them unrelated and use them only on this page).
- Column chart: `pizzas_in_order` by `orders`.
- Table: `vw_product_affinity` sorted by `lift` descending, with a filter
  `lift > 1`. Add a text box explaining lift in one sentence, because a
  stakeholder will ask.

## 6. Polish that separates a portfolio report from a homework report

1. **View > Themes > Customize**: one accent colour, one neutral. Do not use the default palette.
2. Every visual gets a written title stating the finding, not the field name -
   "Lunch and dinner carry 68% of orders", not "Orders by hour_label".
3. Add a footer text box: source file, row count, load date, and the line
   "Metric definitions live in sql/02_views.sql".
4. **Edit interactions** to stop the affinity table being cross-filtered into nonsense.
5. Set page size to 16:9, align everything to the grid, and check tab order for
   accessibility (**View > Selection pane**).
6. Add tooltips: a small hidden page showing revenue and orders for the hovered product.

## 7. Refresh

`.pbix` in Import mode holds a snapshot. To refresh: open it and click
**Home > Refresh** after any `make load`. If you later get a Fabric/Pro licence,
publish to the Service and configure a scheduled refresh through a data gateway.

## 8. Save into the repo

Save as `reports/pizza_sales_dashboard.pbix`, then **File > Export > PDF** to
`reports/pizza_sales_dashboard.pdf` and drop page screenshots into `reports/`
so the repo shows the dashboard without needing Power BI installed.
