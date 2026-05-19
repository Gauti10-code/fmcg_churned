USE fmcg_churn;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3: Feature store view
-- This is what Python reads directly for ML — no joins needed in code
-- Adding RFM scores (1-5 quintile buckets) on top of raw features
-- ─────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS feature_store;

CREATE VIEW feature_store AS
WITH

-- Quintile scoring for R, F, M (1=worst, 5=best)
-- Recency: lower days = better = higher score
-- Frequency and Monetary: higher = better = higher score
rfm_scores AS (
    SELECT
        distributor_id,
        recency_days,
        frequency,
        monetary,
        avg_order_value,
        order_gap_std,
        avg_order_gap_days,
        unique_skus,
        product_categories,
        spend_last_90d,
        spend_prev_90d,
        spend_trend_pct,
        customer_lifespan_days,
        churned,

        -- Recency score: least recent = 1, most recent = 5
        NTILE(5) OVER (ORDER BY recency_days DESC)  AS r_score,

        -- Frequency score: least frequent = 1, most frequent = 5
        NTILE(5) OVER (ORDER BY frequency ASC)      AS f_score,

        -- Monetary score: lowest spend = 1, highest spend = 5
        NTILE(5) OVER (ORDER BY monetary ASC)       AS m_score

    FROM distributor_features
),

-- Combined RFM score and segment
rfm_segments AS (
    SELECT
        *,
        (r_score + f_score + m_score)   AS rfm_total_score,

        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
                THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3
                THEN 'Loyal'
            WHEN r_score >= 4 AND f_score <= 2
                THEN 'New Distributor'
            WHEN r_score <= 2 AND f_score >= 3
                THEN 'At Risk'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2
                THEN 'Lost'
            ELSE 'Needs Attention'
        END                             AS rfm_segment

    FROM rfm_scores
)

SELECT
    distributor_id,

    -- Raw RFM features
    recency_days,
    frequency,
    monetary,
    avg_order_value,

    -- Behavioral features
    order_gap_std,
    avg_order_gap_days,
    unique_skus,
    product_categories,

    -- Trend features
    spend_last_90d,
    spend_prev_90d,
    spend_trend_pct,
    customer_lifespan_days,

    -- RFM scores
    r_score,
    f_score,
    m_score,
    rfm_total_score,
    rfm_segment,

    -- Target label
    churned

FROM rfm_segments;


-- ─────────────────────────────────────────────────────────────────────────────
-- Sanity checks
-- ─────────────────────────────────────────────────────────────────────────────

-- Check 1: total rows and columns
SELECT COUNT(*) AS total_rows FROM feature_store;

-- Check 2: segment distribution
SELECT
    rfm_segment,
    COUNT(*)                                            AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2)  AS pct,
    ROUND(AVG(monetary), 2)                             AS avg_monetary,
    SUM(churned)                                        AS churned_count,
    ROUND(SUM(churned) * 100.0 / COUNT(*), 2)           AS churn_rate_pct
FROM feature_store
GROUP BY rfm_segment
ORDER BY churn_rate_pct DESC;

-- Check 3: confirm all 19 feature columns are present
SELECT
    distributor_id, r_score, f_score, m_score,
    rfm_total_score, rfm_segment, churned
FROM feature_store
LIMIT 5;