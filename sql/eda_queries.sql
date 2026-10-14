-- Grounds for Concern: EDA queries (SQLite dialect; ports cleanly to Snowflake/Postgres)
-- Tables: transactions, products, stores, inventory_snapshots

-- Q1. Monthly category health: volume up, revenue flat, $/oz down?
DROP VIEW IF EXISTS v_monthly;
CREATE VIEW v_monthly AS
SELECT substr(t.order_date, 1, 7)                       AS month,
       COUNT(DISTINCT t.order_id)                       AS orders,
       SUM(t.qty)                                       AS bags_sold,
       SUM(t.qty * p.size_oz)                           AS oz_sold,
       ROUND(SUM(t.net_sales), 2)                       AS net_sales,
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
       SUM(t.qty)                                       AS bags_sold,
       SUM(t.qty * p.size_oz)                           AS oz_sold,
       ROUND(SUM(t.net_sales), 2)                       AS net_sales,
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

-- Q4. Cannibalization check: tier share of oz sold, half-year vs half-year
SELECT CASE WHEN order_date < '2025-07-01' THEN '1H 2025'
            WHEN order_date < '2026-01-01' THEN '2H 2025'
            ELSE '1Q 2026 (post-reset)' END        AS period,
       p.size_tier,
       ROUND(100.0 * SUM(t.qty * p.size_oz)
             / SUM(SUM(t.qty * p.size_oz)) OVER (PARTITION BY
                 CASE WHEN order_date < '2025-07-01' THEN 1
                      WHEN order_date < '2026-01-01' THEN 2 ELSE 3 END), 1) AS pct_of_oz
FROM transactions t JOIN products p USING (sku_id)
GROUP BY 1, 2
ORDER BY 1, 2;
