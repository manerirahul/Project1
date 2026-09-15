-- =====================================================================
-- Reporting layer. Every dashboard visual maps to exactly one view here, so
-- business logic lives in the warehouse instead of being duplicated in
-- Power BI DAX and Tableau calculated fields.
-- Run:  psql "$DATABASE_URL" -f sql/02_views.sql
-- =====================================================================

-- Flat wide view: the single import surface for Tableau extracts and for
-- Power BI when a user prefers one table over the star schema.
CREATE OR REPLACE VIEW public.vw_fact_enriched AS
SELECT f.order_item_id, f.order_id, f.order_ts,
       d.full_date, d.year, d.quarter_name, d.year_month, d.month_name, d.month_number,
       d.iso_week, d.day_name, d.day_of_week, d.is_weekend,
       t.hour_24, t.hour_label, t.day_part, t.is_peak_window,
       p.pizza_name, p.pizza_short_name, p.pizza_category, p.pizza_size, p.size_label,
       p.size_sort_order, p.is_vegetarian, p.ingredient_count,
       f.quantity, f.unit_price, f.total_price,
       f.order_line_count, f.order_pizza_count, f.order_total_value
FROM public.fact_order_items f
JOIN public.dim_date  d ON d.date_key = f.date_key
JOIN public.dim_time  t ON t.time_key = f.time_key
JOIN public.dim_pizza p ON p.pizza_key = f.pizza_key;

-- KPI 1-6: the headline cards.
CREATE OR REPLACE VIEW public.vw_kpi_headline AS
WITH base AS (
  SELECT SUM(total_price) AS revenue,
         SUM(quantity)    AS pizzas_sold,
         COUNT(DISTINCT order_id) AS orders,
         COUNT(*)         AS line_items,
         COUNT(DISTINCT date_key) AS trading_days
  FROM public.fact_order_items
)
SELECT ROUND(revenue, 2)                              AS total_revenue,
       pizzas_sold                                    AS total_pizzas_sold,
       orders                                         AS total_orders,
       line_items                                     AS total_line_items,
       trading_days,
       ROUND(revenue / orders, 2)                     AS avg_order_value,
       ROUND(pizzas_sold::numeric / orders, 2)        AS avg_pizzas_per_order,
       ROUND(revenue / trading_days, 2)               AS avg_revenue_per_day,
       ROUND(orders::numeric / trading_days, 1)       AS avg_orders_per_day
FROM base;

-- Daily trend with a 7-day moving average to separate signal from weekday noise.
CREATE OR REPLACE VIEW public.vw_daily_sales AS
SELECT d.full_date, d.day_name, d.is_weekend, d.year_month,
       ROUND(SUM(f.total_price), 2)     AS revenue,
       SUM(f.quantity)                  AS pizzas_sold,
       COUNT(DISTINCT f.order_id)       AS orders,
       ROUND(SUM(f.total_price) / COUNT(DISTINCT f.order_id), 2) AS avg_order_value,
       ROUND(AVG(SUM(f.total_price)) OVER (
         ORDER BY d.full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ), 2)                            AS revenue_7d_moving_avg
FROM public.fact_order_items f
JOIN public.dim_date d ON d.date_key = f.date_key
GROUP BY d.full_date, d.day_name, d.is_weekend, d.year_month;

-- Month-over-month growth, computed once in SQL.
CREATE OR REPLACE VIEW public.vw_monthly_trend AS
WITH m AS (
  SELECT d.year_month, MIN(d.full_date) AS month_start, d.month_short,
         ROUND(SUM(f.total_price), 2) AS revenue,
         SUM(f.quantity)              AS pizzas_sold,
         COUNT(DISTINCT f.order_id)   AS orders
  FROM public.fact_order_items f
  JOIN public.dim_date d ON d.date_key = f.date_key
  GROUP BY d.year_month, d.month_short
)
SELECT year_month, month_start, month_short, revenue, pizzas_sold, orders,
       ROUND(revenue / orders, 2) AS avg_order_value,
       LAG(revenue) OVER (ORDER BY month_start) AS prev_month_revenue,
       ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY month_start))
             / NULLIF(LAG(revenue) OVER (ORDER BY month_start), 0), 2) AS mom_growth_pct,
       ROUND(100 * revenue / SUM(revenue) OVER (), 2) AS pct_of_year_revenue
FROM m;

-- Category and size mix.
CREATE OR REPLACE VIEW public.vw_sales_by_category AS
SELECT p.pizza_category,
       ROUND(SUM(f.total_price), 2) AS revenue,
       SUM(f.quantity)              AS pizzas_sold,
       COUNT(DISTINCT f.order_id)   AS orders,
       COUNT(DISTINCT p.product_code) AS products_offered,
       ROUND(100 * SUM(f.total_price) / SUM(SUM(f.total_price)) OVER (), 2) AS pct_of_revenue,
       ROUND(AVG(f.unit_price), 2)  AS avg_unit_price
FROM public.fact_order_items f
JOIN public.dim_pizza p ON p.pizza_key = f.pizza_key
GROUP BY p.pizza_category;

CREATE OR REPLACE VIEW public.vw_sales_by_size AS
SELECT p.pizza_size, p.size_label, MIN(p.size_sort_order) AS size_sort_order,
       ROUND(SUM(f.total_price), 2) AS revenue,
       SUM(f.quantity)              AS pizzas_sold,
       ROUND(100 * SUM(f.total_price) / SUM(SUM(f.total_price)) OVER (), 2) AS pct_of_revenue,
       ROUND(AVG(f.unit_price), 2)  AS avg_unit_price
FROM public.fact_order_items f
JOIN public.dim_pizza p ON p.pizza_key = f.pizza_key
GROUP BY p.pizza_size, p.size_label;

-- Demand shape: staffing and oven-capacity planning.
CREATE OR REPLACE VIEW public.vw_hourly_demand AS
SELECT t.hour_24, t.hour_label, t.day_part, t.is_peak_window,
       ROUND(SUM(f.total_price), 2) AS revenue,
       SUM(f.quantity)              AS pizzas_sold,
       COUNT(DISTINCT f.order_id)   AS orders,
       ROUND(COUNT(DISTINCT f.order_id)::numeric
             / (SELECT COUNT(DISTINCT date_key) FROM public.fact_order_items), 1)
                                    AS avg_orders_per_day
FROM public.fact_order_items f
JOIN public.dim_time t ON t.time_key = f.time_key
GROUP BY t.hour_24, t.hour_label, t.day_part, t.is_peak_window;

-- Weekday x hour heatmap source.
CREATE OR REPLACE VIEW public.vw_weekday_hour_heatmap AS
SELECT d.day_of_week, d.day_short, t.hour_24, t.hour_label,
       COUNT(DISTINCT f.order_id)   AS orders,
       ROUND(SUM(f.total_price), 2) AS revenue,
       ROUND(COUNT(DISTINCT f.order_id)::numeric
             / COUNT(DISTINCT d.full_date), 1) AS avg_orders_per_occurrence
FROM public.fact_order_items f
JOIN public.dim_date d ON d.date_key = f.date_key
JOIN public.dim_time t ON t.time_key = f.time_key
GROUP BY d.day_of_week, d.day_short, t.hour_24, t.hour_label;

-- Product performance with Pareto and ABC classification: the menu-engineering view.
CREATE OR REPLACE VIEW public.vw_product_performance AS
WITH prod AS (
  SELECT p.product_code, MIN(p.pizza_short_name) AS pizza_short_name,
         MIN(p.pizza_name) AS pizza_name, MIN(p.pizza_category) AS pizza_category,
         BOOL_OR(p.is_vegetarian) AS is_vegetarian,
         ROUND(SUM(f.total_price), 2) AS revenue,
         SUM(f.quantity)              AS pizzas_sold,
         COUNT(DISTINCT f.order_id)   AS orders,
         ROUND(AVG(f.unit_price), 2)  AS avg_unit_price
  FROM public.fact_order_items f
  JOIN public.dim_pizza p ON p.pizza_key = f.pizza_key
  GROUP BY p.product_code
), ranked AS (
  SELECT *,
         RANK() OVER (ORDER BY revenue DESC)     AS revenue_rank,
         RANK() OVER (ORDER BY pizzas_sold DESC) AS volume_rank,
         ROUND(100 * revenue / SUM(revenue) OVER (), 2) AS pct_of_revenue,
         ROUND(100 * SUM(revenue) OVER (ORDER BY revenue DESC
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
               / SUM(revenue) OVER (), 2) AS cumulative_pct_of_revenue
  FROM prod
)
SELECT *,
       CASE WHEN cumulative_pct_of_revenue <= 80 THEN 'A'
            WHEN cumulative_pct_of_revenue <= 95 THEN 'B'
            ELSE 'C' END AS abc_class
FROM ranked;

-- Basket profile: how many pizzas per order, and what each tier is worth.
CREATE OR REPLACE VIEW public.vw_basket_profile AS
WITH o AS (
  SELECT order_id, MIN(order_pizza_count) AS pizzas, MIN(order_total_value) AS order_value
  FROM public.fact_order_items GROUP BY order_id
)
SELECT pizzas AS pizzas_in_order,
       COUNT(*)                                   AS orders,
       ROUND(100 * COUNT(*)::numeric / SUM(COUNT(*)) OVER (), 2) AS pct_of_orders,
       ROUND(SUM(order_value), 2)                 AS revenue,
       ROUND(AVG(order_value), 2)                 AS avg_order_value
FROM o GROUP BY pizzas;

-- Market-basket affinity with support, confidence and lift: the cross-sell view.
CREATE OR REPLACE VIEW public.vw_product_affinity AS
WITH order_products AS (
  SELECT DISTINCT f.order_id, p.product_code, p.pizza_short_name
  FROM public.fact_order_items f
  JOIN public.dim_pizza p ON p.pizza_key = f.pizza_key
), total_orders AS (
  SELECT COUNT(DISTINCT order_id)::numeric AS n FROM order_products
), single AS (
  SELECT product_code, MIN(pizza_short_name) AS name, COUNT(*)::numeric AS cnt
  FROM order_products GROUP BY product_code
), pairs AS (
  SELECT a.product_code AS product_a_code, a.pizza_short_name AS product_a,
         b.product_code AS product_b_code, b.pizza_short_name AS product_b,
         COUNT(*)::numeric AS pair_orders
  FROM order_products a
  JOIN order_products b
    ON a.order_id = b.order_id AND a.product_code < b.product_code
  GROUP BY 1,2,3,4
  HAVING COUNT(*) >= 30
)
SELECT pr.product_a, pr.product_b, pr.pair_orders::bigint AS orders_together,
       ROUND(100 * pr.pair_orders / t.n, 3)                       AS support_pct,
       ROUND(100 * pr.pair_orders / sa.cnt, 2)                    AS confidence_a_to_b_pct,
       ROUND(100 * pr.pair_orders / sb.cnt, 2)                    AS confidence_b_to_a_pct,
       ROUND((pr.pair_orders / t.n) / ((sa.cnt / t.n) * (sb.cnt / t.n)), 3) AS lift
FROM pairs pr
JOIN single sa ON sa.product_code = pr.product_a_code
JOIN single sb ON sb.product_code = pr.product_b_code
CROSS JOIN total_orders t;

-- Ingredient exposure: which inputs the revenue actually depends on.
CREATE OR REPLACE VIEW public.vw_ingredient_exposure AS
SELECT i.ingredient_name, i.is_cheese,
       COUNT(DISTINCT p.product_code)  AS products_using,
       SUM(f.quantity)                 AS pizzas_sold,
       ROUND(SUM(f.total_price), 2)    AS attributed_revenue,
       ROUND(100 * SUM(f.total_price)
             / (SELECT SUM(total_price) FROM public.fact_order_items), 2) AS pct_of_revenue
FROM public.fact_order_items f
JOIN public.dim_pizza p              ON p.pizza_key = f.pizza_key
JOIN public.bridge_pizza_ingredient b ON b.pizza_key = p.pizza_key
JOIN public.dim_ingredient i          ON i.ingredient_key = b.ingredient_key
GROUP BY i.ingredient_name, i.is_cheese;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
