-- Grounds for Concern: EDA queries (SQLite dialect; ports cleanly to Snowflake/Postgres)
-- Tables: transactions, products, stores, inventory_snapshots

-- Q1. Monthly category health: units up, revenue flat, ATV and per-unit revenue down?
DROP VIEW IF EXISTS v_monthly;
CREATE VIEW v_monthly AS
SELECT substr(t.order_date, 1, 7)                       AS month,
       COUNT(DISTINCT t.order_id)                       AS orders,
       SUM(t.qty)                                       AS units_sold,
       SUM(t.qty * p.size_oz)                           AS oz_sold,
       ROUND(SUM(t.net_sales), 2)                       AS net_sales,
       ROUND(SUM(t.net_sales) / COUNT(DISTINCT t.order_id), 2) AS avg_transaction_value,
       ROUND(SUM(t.net_sales) / SUM(t.qty), 2)          AS net_sales_per_unit,
       ROUND(SUM(t.net_sales) / SUM(t.qty * p.size_oz), 3) AS net_sales_per_oz,
       ROUND(SUM(t.discount_amt) / SUM(t.gross_sales), 3)  AS discount_rate,
       ROUND(1 - SUM(t.cogs) / SUM(t.net_sales), 3)      AS gross_margin
FROM transactions t
JOIN products p USING (sku_id)
GROUP BY 1;

-- Q2. Same lens by size tier: where is the margin going?
DROP VIEW IF EXISTS v_monthly_tier;
CREATE VIEW v_monthly_tier AS
SELECT substr(t.order_date, 1, 7)                       AS month,
       p.size_tier,
       SUM(t.qty)                                       AS units_sold,
       SUM(t.qty * p.size_oz)                           AS oz_sold,
       ROUND(SUM(t.net_sales), 2)                       AS net_sales,
       ROUND(SUM(t.net_sales) / SUM(t.qty), 2)          AS net_sales_per_unit,
       ROUND(SUM(t.net_sales) / SUM(t.qty * p.size_oz), 3) AS net_sales_per_oz,
       ROUND(SUM(t.discount_amt) / SUM(t.gross_sales), 3)  AS discount_rate,
       ROUND(1 - SUM(t.cogs) / SUM(t.net_sales), 3)      AS gross_margin
FROM transactions t
JOIN products p USING (sku_id)
GROUP BY 1, 2;

-- Q3. Assortment depth: average in-stock SKUs per store, by tier and month
DROP VIEW IF EXISTS v_instock;
CREATE VIEW v_instock AS
SELECT substr(i.week_start, 1, 7)                       AS month,
       p.size_tier,
       ROUND(1.0 * SUM(CASE WHEN i.on_hand_units > 0 THEN 1 ELSE 0 END)
             / COUNT(DISTINCT i.week_start || i.store_id), 1) AS avg_instock_skus
FROM inventory_snapshots i
JOIN products p USING (sku_id)
GROUP BY 1, 2;

-- Q4. ATV by size: average order value of orders containing each size
DROP VIEW IF EXISTS v_atv_by_size;
CREATE VIEW v_atv_by_size AS
WITH o AS (SELECT order_id, substr(order_date, 1, 7) AS month, SUM(net_sales) AS ns
           FROM transactions GROUP BY 1, 2),
     os AS (SELECT DISTINCT t.order_id, p.size_tier
            FROM transactions t JOIN products p USING (sku_id))
SELECT month, size_tier, ROUND(AVG(ns), 2) AS atv
FROM o JOIN os USING (order_id)
GROUP BY 1, 2;

-- Q5. Net sales per ounce by size, weekly (week starting Monday)
DROP VIEW IF EXISTS v_weekly_net_per_oz;
CREATE VIEW v_weekly_net_per_oz AS
SELECT date(t.order_date, 'weekday 1', '-7 days')       AS week_start,
       p.size_tier,
       ROUND(SUM(t.net_sales) / SUM(t.qty * p.size_oz), 3) AS net_sales_per_oz
FROM transactions t JOIN products p USING (sku_id)
GROUP BY 1, 2;

-- Q6. In-stock SKU count events: store x SKU in stock on each weekly snapshot, summed by month
DROP VIEW IF EXISTS v_instock_events;
CREATE VIEW v_instock_events AS
SELECT substr(i.week_start, 1, 7) AS month, p.size_tier,
       SUM(CASE WHEN i.on_hand_units > 0 THEN 1 ELSE 0 END) AS instock_sku_events
FROM inventory_snapshots i JOIN products p USING (sku_id)
GROUP BY 1, 2;

-- Q7. Big-basket composition: share of 36 oz+ orders that include each size
DROP VIEW IF EXISTS v_big_basket_mix;
CREATE VIEW v_big_basket_mix AS
WITH o AS (SELECT order_id, substr(order_date, 1, 7) AS month, SUM(qty * size_oz) AS oz,
                  MAX(size_tier = 'Small') AS has_small, MAX(size_tier = 'Medium') AS has_medium,
                  MAX(size_tier = 'Bulk') AS has_bulk
           FROM transactions JOIN products USING (sku_id) GROUP BY 1, 2)
SELECT month, ROUND(AVG(has_small), 3) AS pct_small, ROUND(AVG(has_medium), 3) AS pct_medium,
       ROUND(AVG(has_bulk), 3) AS pct_bulk
FROM o WHERE oz >= 36
GROUP BY 1;

-- Q8. Sizing the recommendations (2025): discount above a 10% cap on Bulk and Medium,
--     and the Bulk revenue gap to a $0.95/oz net floor at actual volumes
SELECT ROUND(SUM(CASE WHEN p.size_tier IN ('Bulk', 'Medium')
                       THEN MAX(t.discount_amt - 0.10 * t.gross_sales, 0) ELSE 0 END), 0) AS discount_over_cap,
       ROUND(SUM(CASE WHEN p.size_tier = 'Bulk'
                       THEN MAX(0.95 * t.qty * p.size_oz - t.net_sales, 0) ELSE 0 END), 0) AS bulk_gap_to_floor
FROM transactions t JOIN products p USING (sku_id)
WHERE t.order_date < '2026-01-01';

-- Q9. Cannibalization check: tier share of units sold, by period
SELECT CASE WHEN order_date < '2025-07-01' THEN '1H 2025'
            WHEN order_date < '2026-01-01' THEN '2H 2025'
            ELSE '1Q 2026 (post-reset)' END        AS period,
       p.size_tier,
       ROUND(100.0 * SUM(t.qty)
             / SUM(SUM(t.qty)) OVER (PARTITION BY
                 CASE WHEN order_date < '2025-07-01' THEN 1
                      WHEN order_date < '2026-01-01' THEN 2 ELSE 3 END), 1) AS pct_of_units
FROM transactions t JOIN products p USING (sku_id)
GROUP BY 1, 2
ORDER BY 1, 2;
