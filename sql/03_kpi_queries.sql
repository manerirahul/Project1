-- =====================================================================
-- Analyst query library. Each block answers one stakeholder question and is
-- safe to run standalone. Use these when validating a dashboard number or
-- answering an ad-hoc request without touching the reporting layer.
-- =====================================================================

-- Q1. What did we make, and how does that break down per trading day?
SELECT * FROM public.vw_kpi_headline;

-- Q2. Which months over- and under-performed, and by how much?
SELECT year_month, revenue, prev_month_revenue, mom_growth_pct, pct_of_year_revenue
FROM public.vw_monthly_trend
ORDER BY month_start;

-- Q3. What is the weekday pattern in average daily revenue?
SELECT d.day_name, d.day_of_week,
       COUNT(DISTINCT d.full_date)                        AS days_traded,
       ROUND(SUM(f.total_price), 2)                       AS revenue,
       ROUND(SUM(f.total_price) / COUNT(DISTINCT d.full_date), 2) AS avg_revenue_per_day,
       ROUND(COUNT(DISTINCT f.order_id)::numeric / COUNT(DISTINCT d.full_date), 1)
                                                          AS avg_orders_per_day
FROM public.fact_order_items f
JOIN public.dim_date d ON d.date_key = f.date_key
GROUP BY d.day_name, d.day_of_week
ORDER BY d.day_of_week;

-- Q4. When do we need staff on the floor? (share of orders by day part)
SELECT day_part,
       SUM(orders)                                             AS orders,
       ROUND(100 * SUM(orders) / SUM(SUM(orders)) OVER (), 2)   AS pct_of_orders,
       ROUND(SUM(revenue), 2)                                   AS revenue
FROM public.vw_hourly_demand
GROUP BY day_part
ORDER BY orders DESC;

-- Q5. Which products carry the business? (Pareto / ABC)
SELECT revenue_rank, pizza_short_name, pizza_category, revenue,
       pct_of_revenue, cumulative_pct_of_revenue, abc_class
FROM public.vw_product_performance
ORDER BY revenue_rank;

-- Q6. Which products are candidates for delisting?
SELECT pizza_short_name, pizza_category, pizzas_sold, revenue, pct_of_revenue
FROM public.vw_product_performance
WHERE abc_class = 'C'
ORDER BY revenue;

-- Q7. Does size drive revenue more than category?
SELECT 'size' AS lever, pizza_size AS value, pct_of_revenue FROM public.vw_sales_by_size
UNION ALL
SELECT 'category', pizza_category, pct_of_revenue FROM public.vw_sales_by_category
ORDER BY lever, pct_of_revenue DESC;

-- Q8. What should we suggest as an add-on? (top affinity pairs by lift)
SELECT product_a, product_b, orders_together, support_pct,
       confidence_a_to_b_pct, lift
FROM public.vw_product_affinity
WHERE lift > 1
ORDER BY lift DESC, orders_together DESC
LIMIT 20;

-- Q9. How much revenue sits in single-pizza orders? (upsell headroom)
SELECT pizzas_in_order, orders, pct_of_orders, revenue, avg_order_value
FROM public.vw_basket_profile
ORDER BY pizzas_in_order;

-- Q10. Which ingredients does our revenue depend on? (procurement exposure)
SELECT ingredient_name, products_using, pizzas_sold, attributed_revenue, pct_of_revenue
FROM public.vw_ingredient_exposure
ORDER BY attributed_revenue DESC
LIMIT 20;

-- Q11. Best and worst single trading days, for root-cause conversations.
(SELECT 'best'  AS bucket, full_date, day_name, revenue, orders
 FROM public.vw_daily_sales ORDER BY revenue DESC LIMIT 5)
UNION ALL
(SELECT 'worst' AS bucket, full_date, day_name, revenue, orders
 FROM public.vw_daily_sales ORDER BY revenue ASC LIMIT 5);

-- Q12. Did we trade every calendar day? (data-completeness question the
--      dashboard must answer before anyone trusts a daily average)
SELECT d.full_date, d.day_name
FROM public.dim_date d
LEFT JOIN public.fact_order_items f ON f.date_key = d.date_key
WHERE f.order_item_id IS NULL
ORDER BY d.full_date;

-- Q13. Reconciliation: does the warehouse still tie to the source rule?
SELECT COUNT(*) AS rows_breaking_price_rule
FROM public.fact_order_items
WHERE ROUND(unit_price * quantity, 2) <> ROUND(total_price, 2);
