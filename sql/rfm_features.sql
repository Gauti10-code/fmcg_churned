USE fmcg_churn;

SET @snapshot_date = (SELECT DATE(MAX(invoice_date)) + INTERVAL 1 DAY FROM orders);
SELECT @snapshot_date AS snapshot_date;

DROP TABLE IF EXISTS order_summary;
CREATE TABLE order_summary AS
SELECT
    distributor_id,
    invoice_no,
    DATE(invoice_date)              AS order_date,
    COUNT(*)                        AS line_items,
    SUM(quantity)                   AS total_qty,
    SUM(line_revenue)               AS order_value,
    COUNT(DISTINCT stock_code)      AS unique_products
FROM orders
GROUP BY distributor_id, invoice_no, DATE(invoice_date);

SELECT COUNT(*) AS total_invoices FROM order_summary;

DROP TABLE IF EXISTS distributor_features;
CREATE TABLE distributor_features AS
WITH

rfm AS (
    SELECT
        distributor_id,
        DATEDIFF(@snapshot_date, MAX(order_date))   AS recency_days,
        COUNT(DISTINCT invoice_no)                  AS frequency,
        SUM(order_value)                            AS monetary,
        AVG(order_value)                            AS avg_order_value,
        MIN(order_date)                             AS first_order_date,
        MAX(order_date)                             AS last_order_date
    FROM order_summary
    GROUP BY distributor_id
),

order_gaps AS (
    SELECT
        distributor_id,
        STDDEV(gap_days)    AS order_gap_std,
        AVG(gap_days)       AS avg_order_gap_days
    FROM (
        SELECT
            distributor_id,
            order_date,
            DATEDIFF(order_date,
                LAG(order_date) OVER (PARTITION BY distributor_id ORDER BY order_date)
            ) AS gap_days
        FROM order_summary
    ) gaps
    WHERE gap_days IS NOT NULL
    GROUP BY distributor_id
),

diversity AS (
    SELECT
        distributor_id,
        COUNT(DISTINCT stock_code)      AS unique_skus,
        COUNT(DISTINCT LEFT(stock_code, 2)) AS product_categories
    FROM orders
    GROUP BY distributor_id
),

spend_trend AS (
    SELECT
        distributor_id,
        SUM(CASE WHEN order_date >= DATE(@snapshot_date) - INTERVAL 90 DAY
                 THEN order_value ELSE 0 END)   AS spend_last_90d,
        SUM(CASE WHEN order_date BETWEEN DATE(@snapshot_date) - INTERVAL 180 DAY  AND DATE(@snapshot_date) - INTERVAL 91 DAY
        THEN order_value ELSE 0 END)   AS spend_prev_90d
    FROM order_summary
    GROUP BY distributor_id
)

SELECT
    r.distributor_id,
    r.recency_days,
    r.frequency,
    ROUND(r.monetary, 2)                                        AS monetary,
    ROUND(r.avg_order_value, 2)                                 AS avg_order_value,
    COALESCE(ROUND(g.order_gap_std, 2),  0)                    AS order_gap_std,
    COALESCE(ROUND(g.avg_order_gap_days, 2), 0)                AS avg_order_gap_days,
    d.unique_skus,
    d.product_categories,
    ROUND(s.spend_last_90d, 2)                                  AS spend_last_90d,
    ROUND(s.spend_prev_90d, 2)                                  AS spend_prev_90d,
    ROUND(
        CASE
            WHEN s.spend_prev_90d = 0 THEN 0
            ELSE (s.spend_last_90d - s.spend_prev_90d) / s.spend_prev_90d
        END, 4)                                                 AS spend_trend_pct,
    r.first_order_date,
    r.last_order_date,
    DATEDIFF(r.last_order_date, r.first_order_date)             AS customer_lifespan_days,
    CASE
        WHEN DATEDIFF(@snapshot_date, r.last_order_date) > 90 THEN 1
        ELSE 0
    END AS churned

FROM rfm r
LEFT JOIN order_gaps  g ON r.distributor_id = g.distributor_id
LEFT JOIN diversity   d ON r.distributor_id = d.distributor_id
LEFT JOIN spend_trend s ON r.distributor_id = s.distributor_id;

-- Check 1: churn rate
SELECT
    churned,
    COUNT(*)                                            AS distributor_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2)  AS pct
FROM distributor_features
GROUP BY churned;

-- Check 2: feature summary
SELECT
    ROUND(AVG(recency_days), 1)         AS avg_recency,
    ROUND(AVG(frequency), 1)            AS avg_frequency,
    ROUND(AVG(monetary), 2)             AS avg_monetary,
    ROUND(AVG(order_gap_std), 2)        AS avg_gap_std,
    ROUND(AVG(unique_skus), 1)          AS avg_skus,
    ROUND(AVG(spend_trend_pct), 4)      AS avg_spend_trend
FROM distributor_features;

-- Check 3: null check
SELECT
    SUM(recency_days IS NULL)   AS null_recency,
    SUM(frequency IS NULL)      AS null_frequency,
    SUM(monetary IS NULL)       AS null_monetary,
    SUM(churned IS NULL)        AS null_label
FROM distributor_features;