-- =====================================================================
-- Pizza Sales Analytics - dimensional warehouse (Kimball star schema)
-- Target: PostgreSQL 15+
-- Run once against an empty database:  psql "$DATABASE_URL" -f sql/01_schema.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.dim_date (
  date_key      integer PRIMARY KEY,          -- YYYYMMDD
  full_date     date        NOT NULL UNIQUE,
  year          smallint    NOT NULL,
  quarter       smallint    NOT NULL,
  quarter_name  text        NOT NULL,
  month_number  smallint    NOT NULL,
  month_name    text        NOT NULL,
  month_short   text        NOT NULL,
  year_month    text        NOT NULL,
  iso_week      smallint    NOT NULL,
  day_of_month  smallint    NOT NULL,
  day_of_week   smallint    NOT NULL,          -- 1 = Monday
  day_name      text        NOT NULL,
  day_short     text        NOT NULL,
  is_weekend    boolean     NOT NULL,
  day_of_year   smallint    NOT NULL
);
COMMENT ON TABLE public.dim_date IS 'Contiguous calendar dimension; gap-free so BI time intelligence works on zero-sales days.';

CREATE TABLE IF NOT EXISTS public.dim_time (
  time_key       smallint PRIMARY KEY,         -- hour of day, 0-23
  hour_24        smallint NOT NULL,
  hour_label     text     NOT NULL,
  hour_12        text     NOT NULL,
  day_part       text     NOT NULL,
  is_peak_window boolean  NOT NULL
);
COMMENT ON TABLE public.dim_time IS 'Hour-grain time-of-day dimension with trading day parts.';

CREATE TABLE IF NOT EXISTS public.dim_pizza (
  pizza_key         integer PRIMARY KEY,       -- surrogate key
  pizza_name_id     text    NOT NULL UNIQUE,   -- natural key from source
  product_code      text    NOT NULL,          -- size-independent product
  pizza_name        text    NOT NULL,
  pizza_short_name  text    NOT NULL,
  pizza_category    text    NOT NULL,
  pizza_size        text    NOT NULL,
  size_label        text    NOT NULL,
  size_sort_order   smallint NOT NULL,
  unit_price        numeric(10,2) NOT NULL CHECK (unit_price > 0),
  min_unit_price    numeric(10,2) NOT NULL,
  max_unit_price    numeric(10,2) NOT NULL,
  price_is_stable   boolean NOT NULL,
  ingredient_count  smallint NOT NULL,
  is_vegetarian     boolean NOT NULL,
  pizza_ingredients text    NOT NULL
);
COMMENT ON TABLE public.dim_pizza IS 'Conformed product dimension at product-plus-size grain.';

CREATE TABLE IF NOT EXISTS public.dim_ingredient (
  ingredient_key  integer PRIMARY KEY,
  ingredient_name text    NOT NULL UNIQUE,
  is_cheese       boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS public.bridge_pizza_ingredient (
  pizza_key      integer NOT NULL REFERENCES public.dim_pizza(pizza_key),
  ingredient_key integer NOT NULL REFERENCES public.dim_ingredient(ingredient_key),
  PRIMARY KEY (pizza_key, ingredient_key)
);
COMMENT ON TABLE public.bridge_pizza_ingredient IS 'Many-to-many recipe bridge; enables ingredient-level exposure analysis.';

-- ---------------------------------------------------------------------
-- Fact
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fact_order_items (
  order_item_id       integer PRIMARY KEY,      -- source pizza_id
  order_id            integer NOT NULL,         -- degenerate dimension
  date_key            integer  NOT NULL REFERENCES public.dim_date(date_key),
  time_key            smallint NOT NULL REFERENCES public.dim_time(time_key),
  pizza_key           integer  NOT NULL REFERENCES public.dim_pizza(pizza_key),
  order_ts            timestamp NOT NULL,
  quantity            smallint NOT NULL CHECK (quantity > 0),
  unit_price          numeric(10,2) NOT NULL CHECK (unit_price > 0),
  total_price         numeric(10,2) NOT NULL CHECK (total_price > 0),
  total_price_source  numeric(10,2),            -- as supplied, for audit
  price_variance_flag boolean NOT NULL DEFAULT false,
  order_line_count    smallint NOT NULL,
  order_pizza_count   smallint NOT NULL,
  order_total_value   numeric(12,2) NOT NULL
);
COMMENT ON TABLE public.fact_order_items IS 'Transactional fact at one row per pizza line item.';

-- Indexes sized for BI query patterns: date filters, product slicers, basket joins.
CREATE INDEX IF NOT EXISTS ix_fact_date  ON public.fact_order_items (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_pizza ON public.fact_order_items (pizza_key);
CREATE INDEX IF NOT EXISTS ix_fact_time  ON public.fact_order_items (time_key);
CREATE INDEX IF NOT EXISTS ix_fact_order ON public.fact_order_items (order_id);

-- ---------------------------------------------------------------------
-- Read-only access for BI tools / reporting role
-- ---------------------------------------------------------------------
GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
