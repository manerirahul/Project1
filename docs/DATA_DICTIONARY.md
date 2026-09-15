# Data dictionary

Grain, keys and column meanings for the warehouse. Definitive DDL:
`sql/01_schema.sql`. Definitive metric logic: `sql/02_views.sql`.

## Model overview

```text
              dim_date (365)
                   |
 dim_time (24) --- fact_order_items (48,620) --- dim_pizza (91)
                                                     |
                                     bridge_pizza_ingredient (518)
                                                     |
                                            dim_ingredient (65)
```

Star schema, one fact table, three conformed dimensions, one many-to-many bridge.
`order_id` is a degenerate dimension on the fact - it identifies the basket
without needing an order dimension, because the source carries no order
attributes beyond timestamp.

---

## fact_order_items - 48,620 rows

Grain: **one row per pizza line item on an order.**

| Column | Type | Meaning |
| --- | --- | --- |
| `order_item_id` | int PK | Source `pizza_id`; the line-item identifier |
| `order_id` | int | Basket identifier; 21,350 distinct values |
| `date_key` | int FK | `YYYYMMDD` into `dim_date` |
| `time_key` | smallint FK | Hour of day 0-23 into `dim_time` |
| `pizza_key` | int FK | Surrogate product key into `dim_pizza` |
| `order_ts` | timestamp | Full order timestamp, retained for sub-hour analysis |
| `quantity` | smallint | Pizzas on this line; 1-4 |
| `unit_price` | numeric | Price per pizza as sold |
| `total_price` | numeric | **Recomputed** as `unit_price * quantity` - the trusted revenue column |
| `total_price_source` | numeric | Value as supplied in the CSV, kept for audit |
| `price_variance_flag` | boolean | True where source total disagreed with the recomputed value |
| `order_line_count` | smallint | Lines on the parent order (precomputed for basket analysis) |
| `order_pizza_count` | smallint | Pizzas on the parent order |
| `order_total_value` | numeric | Total value of the parent order |

The three `order_*` columns are deliberate denormalisation: they let a BI tool
answer "how many orders had only one pizza?" without a self-join, which is the
difference between an instant visual and a 10-second one.

## dim_date - 365 rows

Grain: one row per calendar day of 2015. **Contiguous** - all 365 days exist even
though only 358 had sales, so Power BI `TOTALYTD` and Tableau `LOOKUP` do not
silently skip periods.

Key columns: `date_key`, `full_date`, `year`, `quarter`, `quarter_name`,
`month_number`, `month_name`, `month_short`, `year_month`, `iso_week`,
`day_of_month`, `day_of_week` (1 = Monday), `day_name`, `day_short`,
`is_weekend`, `day_of_year`.

`month_number`, `day_of_week` and `size_sort_order` exist purely so BI axes sort
chronologically rather than alphabetically.

## dim_time - 24 rows

Grain: one row per hour of day.

| Column | Meaning |
| --- | --- |
| `time_key`, `hour_24` | 0-23 |
| `hour_label` | `"12:00"` for axis labels |
| `hour_12` | `"12 PM"` |
| `day_part` | Pre-Opening, Lunch, Afternoon, Dinner, Late Night |
| `is_peak_window` | True for 11-13 and 17-20 |

## dim_pizza - 91 rows

Grain: **product plus size.** 32 products across up to 5 sizes.

| Column | Meaning |
| --- | --- |
| `pizza_key` | Surrogate key |
| `pizza_name_id` | Natural key from source, e.g. `bbq_ckn_l` |
| `product_code` | Size-independent product, e.g. `bbq_ckn` - use this to analyse a product across sizes |
| `pizza_name`, `pizza_short_name` | Full and display name |
| `pizza_category` | Classic, Chicken, Supreme, Veggie |
| `pizza_size`, `size_label`, `size_sort_order` | S/M/L/XL/XXL, readable label, sort order |
| `unit_price` | Modal price for this product-size |
| `min_unit_price`, `max_unit_price`, `price_is_stable` | Price-variation audit |
| `ingredient_count` | Recipe size |
| `is_vegetarian` | **Derived** by matching meat terms in the recipe text - analytical convenience, not a certified dietary claim |
| `pizza_ingredients` | Raw recipe string, kept for traceability |

## dim_ingredient - 65 rows / bridge_pizza_ingredient - 518 rows

The recipe string is split into one row per ingredient and linked through the
bridge. That is what makes "how much revenue depends on chicken?" answerable in
`vw_ingredient_exposure`.

Revenue through the bridge is **duplicated by design** (one pizza has many
ingredients). Use it for exposure and supply-risk questions only; never sum it
as total revenue.

---

## Reporting views

| View | Grain | Purpose |
| --- | --- | --- |
| `vw_fact_enriched` | Line item | Star schema pre-joined; single-table BI import |
| `vw_kpi_headline` | 1 row | Revenue, pizzas, orders, AOV, pizzas per order, trading days |
| `vw_daily_sales` | Day | Daily revenue with 7-day moving average |
| `vw_monthly_trend` | Month | Revenue with MoM growth |
| `vw_sales_by_category` | Category | Revenue and share of total |
| `vw_sales_by_size` | Size | Revenue and share of total |
| `vw_hourly_demand` | Hour | Orders, revenue, day part |
| `vw_weekday_hour_heatmap` | Weekday x hour | Order counts for the heatmap |
| `vw_product_performance` | Product | Revenue, rank, running share, ABC class |
| `vw_basket_profile` | Pizzas per order | Order-size distribution |
| `vw_product_affinity` | Product pair | Support, confidence, lift for cross-sell |
| `vw_ingredient_exposure` | Ingredient | Revenue exposure per ingredient |

All views are `security_invoker`, so a reporting role reads them under its own
privileges.

## Known constraints of the source

- No cost or margin, so profitability is out of scope. Everything is revenue and mix.
- No store, channel, or customer identifier, so no geography, no retention, no
  customer segmentation. `order_id` is a basket, not a person.
- Single year (2015), so no year-over-year comparison.
- 7 days with zero sales: worth confirming as closures rather than missing data.

Stating these up front is part of the deliverable. An analyst who does not
declare the limits of the data is guessing.
