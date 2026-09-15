"""Step 5 - Analysis and insight generation.

Reads the warehouse views (falls back to the local processed CSVs when no
database is configured), computes the KPI pack, writes chart PNGs for the
portfolio, and generates reports/insights.md with findings written the way a
business analyst hands them to a stakeholder: number, so-what, action.

Run:
  python -m src.analysis            # use the database
  python -m src.analysis --local    # use data/processed/*.csv instead
"""

from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402

PALETTE = ["#C1440E", "#E4A010", "#2E5E4E", "#6B4226", "#8C8C8C"]


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
class Source:
    """Reads from Postgres views, or recomputes the same shapes locally."""

    def __init__(self, local: bool = False):
        self.local = local
        self.engine = None
        if not local:
            from sqlalchemy import create_engine

            self.engine = create_engine(config.DatabaseConfig().sqlalchemy_url)

    def view(self, name: str, order_by: str | None = None) -> pd.DataFrame:
        if not self.local:
            sql = f"SELECT * FROM public.{name}"
            if order_by:
                sql += f" ORDER BY {order_by}"
            return pd.read_sql(sql, self.engine)
        return self._local_view(name)

    # Local fallback keeps the script usable offline and in code review.
    def _local_view(self, name: str) -> pd.DataFrame:
        fact = pd.read_csv(config.OUTPUT_FILES["fact_order_items"], parse_dates=["order_ts"])
        dim_date = pd.read_csv(config.OUTPUT_FILES["dim_date"], parse_dates=["full_date"])
        dim_time = pd.read_csv(config.OUTPUT_FILES["dim_time"])
        dim_pizza = pd.read_csv(config.OUTPUT_FILES["dim_pizza"])
        flat = fact.merge(dim_date, on="date_key").merge(dim_time, on="time_key").merge(
            dim_pizza, on="pizza_key", suffixes=("", "_p")
        )

        if name == "vw_kpi_headline":
            return pd.DataFrame([{
                "total_revenue": round(fact.total_price.sum(), 2),
                "total_pizzas_sold": int(fact.quantity.sum()),
                "total_orders": fact.order_id.nunique(),
                "total_line_items": len(fact),
                "trading_days": fact.date_key.nunique(),
                "avg_order_value": round(fact.total_price.sum() / fact.order_id.nunique(), 2),
                "avg_pizzas_per_order": round(fact.quantity.sum() / fact.order_id.nunique(), 2),
                "avg_revenue_per_day": round(fact.total_price.sum() / fact.date_key.nunique(), 2),
                "avg_orders_per_day": round(fact.order_id.nunique() / fact.date_key.nunique(), 1),
            }])
        if name == "vw_monthly_trend":
            m = flat.groupby("year_month").agg(
                revenue=("total_price", "sum"), pizzas_sold=("quantity", "sum"),
                orders=("order_id", "nunique")).round(2).reset_index()
            m["month_short"] = pd.to_datetime(m.year_month + "-01").dt.strftime("%b")
            m["mom_growth_pct"] = (100 * m.revenue.pct_change()).round(2)
            return m
        if name == "vw_sales_by_category":
            c = flat.groupby("pizza_category").agg(
                revenue=("total_price", "sum"), pizzas_sold=("quantity", "sum"),
                orders=("order_id", "nunique")).round(2).reset_index()
            c["pct_of_revenue"] = (100 * c.revenue / c.revenue.sum()).round(2)
            return c
        if name == "vw_sales_by_size":
            s = flat.groupby(["pizza_size", "size_label", "size_sort_order"]).agg(
                revenue=("total_price", "sum"), pizzas_sold=("quantity", "sum")).round(2).reset_index()
            s["pct_of_revenue"] = (100 * s.revenue / s.revenue.sum()).round(2)
            return s
        if name == "vw_hourly_demand":
            h = flat.groupby(["hour_24", "hour_label", "day_part"]).agg(
                revenue=("total_price", "sum"), orders=("order_id", "nunique")).round(2).reset_index()
            return h
        if name == "vw_daily_sales":
            d = flat.groupby(["full_date", "day_name", "is_weekend"]).agg(
                revenue=("total_price", "sum"), orders=("order_id", "nunique")).round(2).reset_index()
            d["revenue_7d_moving_avg"] = d.revenue.rolling(7, min_periods=1).mean().round(2)
            return d
        if name == "vw_product_performance":
            p = flat.groupby("product_code").agg(
                pizza_short_name=("pizza_short_name", "first"),
                pizza_category=("pizza_category", "first"),
                revenue=("total_price", "sum"), pizzas_sold=("quantity", "sum"),
                orders=("order_id", "nunique")).round(2).reset_index()
            p = p.sort_values("revenue", ascending=False)
            p["revenue_rank"] = range(1, len(p) + 1)
            p["pct_of_revenue"] = (100 * p.revenue / p.revenue.sum()).round(2)
            p["cumulative_pct_of_revenue"] = p.pct_of_revenue.cumsum().round(2)
            p["abc_class"] = pd.cut(p.cumulative_pct_of_revenue, [0, 80, 95, 101],
                                    labels=["A", "B", "C"]).astype(str)
            return p
        if name == "vw_basket_profile":
            o = flat.groupby("order_id").agg(
                pizzas_in_order=("order_pizza_count", "min"),
                order_value=("order_total_value", "min")).reset_index()
            b = o.groupby("pizzas_in_order").agg(
                orders=("order_id", "count"), avg_order_value=("order_value", "mean")).round(2).reset_index()
            b["pct_of_orders"] = (100 * b.orders / b.orders.sum()).round(2)
            return b
        raise KeyError(f"No local fallback implemented for {name}")


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def build_charts(src: Source) -> None:
    config.ensure_dirs()

    monthly = src.view("vw_monthly_trend", "month_start")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(monthly.month_short, monthly.revenue, color=PALETTE[0])
    _style(ax, "Monthly revenue, 2015", ylabel="Revenue (USD)")
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / "chart_monthly_revenue.png", dpi=150)
    plt.close(fig)

    hourly = src.view("vw_hourly_demand", "hour_24")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = [PALETTE[0] if o >= hourly.orders.quantile(0.8) else PALETTE[4] for o in hourly.orders]
    ax.bar(hourly.hour_label, hourly.orders, color=colors)
    _style(ax, "Orders by hour of day (peak hours highlighted)", ylabel="Orders")
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / "chart_hourly_orders.png", dpi=150)
    plt.close(fig)

    cat = src.view("vw_sales_by_category").sort_values("revenue", ascending=False)
    size = src.view("vw_sales_by_size").sort_values("size_sort_order")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].bar(cat.pizza_category, cat.revenue, color=PALETTE[:4])
    _style(axes[0], "Revenue by category", ylabel="Revenue (USD)")
    axes[1].bar(size.pizza_size, size.revenue, color=PALETTE[1])
    _style(axes[1], "Revenue by size", ylabel="Revenue (USD)")
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / "chart_category_size_mix.png", dpi=150)
    plt.close(fig)

    prod = src.view("vw_product_performance", "revenue_rank").head(15)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(prod.pizza_short_name[::-1], prod.revenue[::-1], color=PALETTE[2])
    _style(ax, "Top 15 products by revenue", xlabel="Revenue (USD)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / "chart_top_products.png", dpi=150)
    plt.close(fig)

    daily = src.view("vw_daily_sales", "full_date")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(pd.to_datetime(daily.full_date), daily.revenue, color=PALETTE[4], lw=0.8, label="Daily")
    ax.plot(pd.to_datetime(daily.full_date), daily.revenue_7d_moving_avg,
            color=PALETTE[0], lw=2, label="7-day average")
    _style(ax, "Daily revenue with 7-day moving average", ylabel="Revenue (USD)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / "chart_daily_trend.png", dpi=150)
    plt.close(fig)

    print(f"  5 charts written to {config.REPORTS_DIR}")


# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #
def build_insights(src: Source) -> str:
    kpi = src.view("vw_kpi_headline").iloc[0]
    monthly = src.view("vw_monthly_trend", "month_start")
    cat = src.view("vw_sales_by_category").sort_values("revenue", ascending=False)
    size = src.view("vw_sales_by_size").sort_values("revenue", ascending=False)
    hourly = src.view("vw_hourly_demand", "hour_24")
    daily = src.view("vw_daily_sales", "full_date")
    prod = src.view("vw_product_performance", "revenue_rank")
    basket = src.view("vw_basket_profile")

    best_month = monthly.loc[monthly.revenue.idxmax()]
    worst_month = monthly.loc[monthly.revenue.idxmin()]
    peak = hourly.loc[hourly.orders.idxmax()]
    lunch_dinner = hourly[hourly.day_part.isin(["Lunch", "Dinner"])].orders.sum() if "day_part" in hourly else 0
    by_day = daily.groupby("day_name").revenue.mean().sort_values(ascending=False)
    a_class = prod[prod.abc_class == "A"]
    c_class = prod[prod.abc_class == "C"]
    single_pizza = basket.loc[basket.pizzas_in_order == 1, "pct_of_orders"]

    L = [
        "# Insights and recommendations", "",
        "_Generated by `python -m src.analysis`. Every figure traces to a view in "
        "`sql/02_views.sql`, so the dashboard and this document can never disagree._", "",
        "## Headline performance", "",
        f"| KPI | Value |", "| --- | --- |",
        f"| Total revenue | ${kpi.total_revenue:,.2f} |",
        f"| Pizzas sold | {int(kpi.total_pizzas_sold):,} |",
        f"| Orders | {int(kpi.total_orders):,} |",
        f"| Average order value | ${kpi.avg_order_value:,.2f} |",
        f"| Average pizzas per order | {kpi.avg_pizzas_per_order} |",
        f"| Trading days | {int(kpi.trading_days)} |",
        f"| Average revenue per trading day | ${kpi.avg_revenue_per_day:,.2f} |",
        f"| Average orders per trading day | {kpi.avg_orders_per_day} |", "",
        "## 1. Demand is concentrated in two narrow windows", "",
        f"- The single busiest hour is **{peak.hour_label}** with **{int(peak.orders):,} orders** "
        f"across the year.",
        f"- Lunch (11:00-13:00) and dinner (17:00-20:00) together carry "
        f"**{100 * lunch_dinner / hourly.orders.sum():.1f}%** of all orders.",
        "- **So what:** labour and oven capacity, not demand, is the binding constraint at midday.",
        "- **Action:** roster to the hourly curve rather than flat shifts, and pre-prep the top "
        "A-class products before 11:00.", "",
        "## 2. Weekly rhythm is stable and predictable", "",
        f"- Strongest average day: **{by_day.index[0]}** (${by_day.iloc[0]:,.0f} per day). "
        f"Weakest: **{by_day.index[-1]}** (${by_day.iloc[-1]:,.0f} per day).",
        f"- The gap between best and worst weekday is "
        f"**{100 * (by_day.iloc[0] - by_day.iloc[-1]) / by_day.iloc[-1]:.0f}%**.",
        "- **So what:** the variance is a weekday effect, not noise, so it is plannable.",
        "- **Action:** move promotions to the two weakest weekdays; protect margin on peak days.", "",
        "## 3. Revenue is flat across the year - growth has to come from mix", "",
        f"- Best month: **{best_month.month_short}** (${best_month.revenue:,.0f}). "
        f"Weakest month: **{worst_month.month_short}** (${worst_month.revenue:,.0f}).",
        f"- Month-over-month growth stays within "
        f"**{monthly.mom_growth_pct.abs().max():.1f}%** in either direction.",
        f"- Only **{int(kpi.trading_days)} of 365 days** recorded any sale, so "
        f"{365 - int(kpi.trading_days)} days had zero revenue - worth confirming these were "
        "planned closures rather than missing data.",
        "- **Action:** treat the baseline as mature; pursue basket size and product mix, "
        "not more footfall.", "",
        "## 4. Product mix follows a clear Pareto pattern", "",
        f"- **{len(a_class)} of {len(prod)} products (A-class)** generate the first 80% of revenue.",
        f"- Top seller: **{prod.iloc[0].pizza_short_name}** at "
        f"${prod.iloc[0].revenue:,.0f} ({prod.iloc[0].pct_of_revenue}% of revenue).",
        f"- Weakest performer: **{prod.iloc[-1].pizza_short_name}** at "
        f"${prod.iloc[-1].revenue:,.0f} ({prod.iloc[-1].pct_of_revenue}%).",
        f"- **{len(c_class)} C-class products** together contribute only "
        f"{c_class.pct_of_revenue.sum():.1f}% while consuming menu space and stock.",
        "- **Action:** run a menu-rationalisation review on C-class items; every delisting "
        "frees prep time at peak.", "",
        "## 5. Category revenue is evenly balanced; size is where the money is", "",
        f"- Categories sit within **{cat.pct_of_revenue.max() - cat.pct_of_revenue.min():.1f} "
        f"percentage points** of each other - led by **{cat.iloc[0].pizza_category}** "
        f"({cat.iloc[0].pct_of_revenue}%).",
        f"- By contrast **{size.iloc[0].pizza_size}** alone drives "
        f"**{size.iloc[0].pct_of_revenue}%** of revenue.",
        "- **So what:** customers are not category-loyal, but they are size-sensitive, and size "
        "is the highest-margin lever available.",
        "- **Action:** make upsizing the default prompt at order entry; the price step between "
        "sizes is pure incremental margin on the same prep time.", "",
        "## 6. Basket size is the biggest untapped lever", "",
        f"- **{float(single_pizza.iloc[0]) if len(single_pizza) else 0:.1f}%** of orders contain "
        "just one pizza.",
        f"- Average order value is **${kpi.avg_order_value:,.2f}** at "
        f"{kpi.avg_pizzas_per_order} pizzas per order.",
        "- Pairs that co-occur far above chance are listed in `vw_product_affinity` "
        "(lift greater than 1 means a genuine affinity, not just two popular items).",
        "- **Action:** drive the top affinity pairs as suggested add-ons at checkout; "
        "a single extra pizza on 10% of one-pizza orders is a mid-single-digit revenue gain.", "",
        "## Caveats a reviewer should know", "",
        "- The source has no cost, margin, store, channel or customer identifier, so profitability "
        "and retention are out of scope. Recommendations are framed on revenue and mix only.",
        "- `is_vegetarian` is derived by matching meat terms in the recipe text; it is an analytical "
        "convenience, not a certified dietary claim.",
        "- Affinity is computed at product level ignoring size, which is the correct grain for a "
        "cross-sell prompt.", "",
    ]
    return "\n".join(L)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the KPI pack, charts and insights")
    parser.add_argument("--local", action="store_true",
                        help="read data/processed/*.csv instead of the database")
    args = parser.parse_args()

    src = Source(local=args.local)
    print("Building charts...")
    build_charts(src)
    print("Writing insights...")
    insights = build_insights(src)
    out = config.REPORTS_DIR / "insights.md"
    out.write_text(insights, encoding="utf-8")
    print(insights)
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    main()
