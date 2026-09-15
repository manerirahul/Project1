# Data profile - pizza_sales.csv

## 1. Volume and grain

- Rows: **48,620**
- Columns: **12**
- Distinct `pizza_id`: **48,620** (unique - valid primary key)
- Distinct `order_id`: **21,350**
- Grain: one row per pizza line item within an order

## 2. Completeness

| Column | Nulls / blanks | % |
| --- | --- | --- |
| `pizza_id` | 0 | 0.00% |
| `order_id` | 0 | 0.00% |
| `pizza_name_id` | 0 | 0.00% |
| `quantity` | 0 | 0.00% |
| `order_date` | 0 | 0.00% |
| `order_time` | 0 | 0.00% |
| `unit_price` | 0 | 0.00% |
| `total_price` | 0 | 0.00% |
| `pizza_size` | 0 | 0.00% |
| `pizza_category` | 0 | 0.00% |
| `pizza_ingredients` | 0 | 0.00% |
| `pizza_name` | 0 | 0.00% |

## 3. Duplicates

- Fully duplicated rows: **0**
- Duplicated `pizza_id`: **0**

## 4. Categorical domains

**`pizza_size`** (5 distinct)

- `L`: 18,526 (38.10%)
- `M`: 15,385 (31.64%)
- `S`: 14,137 (29.08%)
- `XL`: 544 (1.12%)
- `XXL`: 28 (0.06%)

**`pizza_category`** (4 distinct)

- `Classic`: 14,579 (29.99%)
- `Supreme`: 11,777 (24.22%)
- `Veggie`: 11,449 (23.55%)
- `Chicken`: 10,815 (22.24%)

## 5. Numeric measures

|       |     quantity |   unit_price |   total_price |
|:------|-------------:|-------------:|--------------:|
| count | 48620        |  48620       |    48620      |
| mean  |     1.01962  |     16.4941  |       16.8215 |
| std   |     0.143077 |      3.62179 |        4.4374 |
| min   |     1        |      9.75    |        9.75   |
| 25%   |     1        |     12.75    |       12.75   |
| 50%   |     1        |     16.5     |       16.5    |
| 75%   |     1        |     20.25    |       20.5    |
| max   |     4        |     35.95    |       83      |

- Non-numeric `quantity` values: **0**
- Non-positive `quantity`: **0**
- Non-positive `unit_price`: **0**

## 6. Date and time integrity

- Unparseable `order_date`: **0** (format `DD-MM-YYYY`)
- Unparseable `order_time`: **0** (format `HH:MM:SS`)
- Date range: **2015-01-01 to 2015-12-31**
- Calendar days covered: **358**

## 7. Business-rule checks

- `unit_price x quantity != total_price`: **0** rows
- `pizza_name_id` values: **91** vs `pizza_name` values: **32** (name_id encodes product + size, so a higher count is expected)

## 8. Functional dependency on `pizza_name_id`

Number of `pizza_name_id` keys with more than one distinct value:

- `pizza_name`: **0**
- `pizza_category`: **0**
- `pizza_size`: **0**
- `unit_price`: **0**

Zero conflicts means the product attributes can be normalised into a product dimension with no information loss.

## 9. Redundancy (why we normalise)

- `pizza_ingredients` repeats 48,620 times for only 32 distinct recipes.
- `pizza_name`, `pizza_category`, `pizza_size` and `unit_price` are all derivable from `pizza_name_id`.
- Storing them on every fact row inflates the table and risks update anomalies; they move to `dim_pizza`.
