# Data-quality gate

| check                                   | severity   | status   | detail   |
|:----------------------------------------|:-----------|:---------|:---------|
| fact primary key is unique              | error      | PASS     |          |
| no null foreign keys in fact            | error      | PASS     |          |
| fact -> dim_pizza referential integrity | error      | PASS     |          |
| fact -> dim_date referential integrity  | error      | PASS     |          |
| fact -> dim_time referential integrity  | error      | PASS     |          |
| dim_date has no gaps                    | error      | PASS     |          |
| all measures are positive               | error      | PASS     |          |
| revenue = unit_price x quantity         | error      | PASS     |          |
| order totals reconcile to line items    | error      | PASS     |          |
| dim_pizza natural key is unique         | error      | PASS     |          |
| ingredient bridge has no orphans        | error      | PASS     |          |
| pizza_category domain is closed         | warning    | PASS     |          |
| unit price is stable per product        | warning    | PASS     |          |
| rejection rate below 1%                 | warning    | PASS     |          |
