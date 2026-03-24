# Metric Diagnosis Agent: Reference

SQL templates, decomposition logic, anomaly thresholds, and hypothesis checklists
for all five supported GA metrics. All SQL is Snowflake-flavored.

---

## Channel CASE Statement

Use this exact mapping for all channel breakdowns. Insert it wherever
`{CHANNEL_CASE}` appears in the templates below.

```sql
CASE
  WHEN md.enrollment_channel ILIKE '%referral%'                          THEN 'Referral'
  WHEN md.enrollment_channel ILIKE '%paid_debit%'
    OR md.enrollment_channel ILIKE '%paid_credit%'
    OR md.enrollment_channel ILIKE '%paid%'
    OR md.enrollment_channel ILIKE '%sem%'
    OR md.enrollment_channel ILIKE '%cpc%'                               THEN 'Paid'
  WHEN md.enrollment_channel ILIKE '%organic%'                           THEN 'Organic'
  WHEN md.enrollment_channel ILIKE '%pay_anyone%'
    OR md.enrollment_channel ILIKE '%pay anyone%'
    OR md.enrollment_channel = 'PA'                                      THEN 'Pay Anyone'
  ELSE 'Others'
END AS channel_bucket
```

> **Note:** Verify exact `enrollment_channel` values against your data.
> Run `SELECT DISTINCT enrollment_channel FROM edw_db.core.member_details LIMIT 100`
> to confirm the values map correctly to these five buckets.

---

## DD Paytype CASE Statement

Use this mapping wherever `{PAYTYPE_CASE}` appears in templates below.
Source column: `dd_proforma_type` on `edw_db.core.ftr_transaction`.

```sql
CASE
  WHEN t.dd_proforma_type = 'payroll'            THEN 'Payroll'
  WHEN t.dd_proforma_type = 'government_benefit' THEN 'Government Benefit'
  WHEN t.dd_proforma_type = 'gig_instant_payout' THEN 'Gig / Instant Payout'
  ELSE 'Unknown'
END AS paytype_bucket
```

> **Note:** `dd_proforma_type` uses the proforma definition for historical consistency.
> Run `SELECT DISTINCT dd_proforma_type FROM edw_db.core.ftr_transaction WHERE is_qualified_dd = TRUE LIMIT 50`
> to verify current values. NULL appears when a qualifying DD has no source classification.

---

## Maturity Check

Early DD (D30) requires the cohort enrollment month to be fully mature.
A cohort enrolled in month M is mature when `LAST_DAY(enrollment_date) < DATEADD('day', -30, CURRENT_DATE)`.

For reporting-month anchored metrics: always pass explicit period dates rather
than relying on `CURRENT_DATE` so results are reproducible.

---

## Anomaly Thresholds

Apply these to **both** MoM and YoY comparisons. Flag each independently.

| Metric | Dimension | Flag when (MoM or YoY) |
|---|---|---|
| Gross New DDer | Total count | % change > ±8% |
| Gross New DDer — Early DD (D30) | Total count | % change > ±10% |
| Gross New DDer — Late DD | Total count | % change > ±10% |
| Early DD by channel (share) | Any channel's share | shift > ±5 pp |
| Resurrected DDer | Total count | % change > ±10% |
| M2 DD Retention | Overall rate | absolute change > ±1.5 pp |
| Early DD/DV | DV per current DD | % change > ±5% |
| TA | Monthly count | QoQ % change (last month of quarter) > ±5% |
| Gross New DDer — by paytype (share) | Any paytype's share | shift > ±5 pp |
| M2 DD Retention — by paytype | Any paytype's rate | absolute change > ±2 pp |
| Early DD/DV — payroll DD DV share | Payroll DD DV as % of total DV | shift > ±5 pp |

**Severity escalation rule:** If both MoM and YoY are flagged in the same
direction, escalate to 🔴 ALERT regardless of individual threshold magnitude.

These are overridable per metric in `context/context_template.yaml`.

---

## Supported Metrics

| Key | Display Name | Primary Table |
|---|---|---|
| `gross_new_dd` | Gross New DDer | `edw_db.core.member_details` |
| `resurrected_dd` | Resurrected DDer | `analytics_db.dbt_cloud_prod.base__user_month` |
| `m2_retention` | M2 DD Retention | `member_details` + `base__user_month` |
| `early_dv` | Early DD/DV | `member_details` + `edw_db.core.ftr_transaction` |
| `ta` | Transaction Actives | `analytics_db.dbt_cloud_prod.base__user_month` |

---

## YoY Parameters

For every metric, always fetch a **year-over-year** comparison alongside the MoM
comparison. Derive from the inputs:

```
YOY_MONTH       = DATEADD('year', -1, {REPORTING_MONTH})   -- same month, prior year
YOY_PRIOR_MONTH = DATEADD('year', -1, {PRIOR_MONTH})       -- MoM-prior month, prior year
```

Run the same Summary and Decomposition queries a second time with `YOY_MONTH` /
`YOY_PRIOR_MONTH` substituted. The YoY pass produces the seasonal baseline and
is **always required** — not an optional add-on. Include YoY Δ and YoY Δ% in
every summary table.

---

## SQL Templates

Parameters: `{REPORTING_MONTH}` and `{PRIOR_MONTH}` are `DATE` values in
`'YYYY-MM-01'` format (first of month). The Python scripts substitute these
before execution; the interactive agent substitutes them inline.

Each metric section includes:
- **a. Summary query** — run with `{REPORTING_MONTH}` / `{PRIOR_MONTH}` AND a
  second pass with `{YOY_MONTH}` / `{YOY_PRIOR_MONTH}`.
- **b/c. Decomposition queries** — run for the current reporting period and for the
  YoY comparison period so anomalies can be compared on a seasonal-adjusted basis.

---

### 1. Gross New DDer

#### 1a. Summary — Early / Late split for both periods

```sql
-- Gross New DDer: Early vs Late DD summary
-- {REPORTING_MONTH} = e.g. '2026-02-01'
-- {PRIOR_MONTH}     = e.g. '2026-01-01'
SELECT
  DATE_TRUNC('month', first_dd_dt)                                           AS conversion_month,
  COUNT(DISTINCT user_id)                                                     AS total_new_dders,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', enrollment_date, first_dd_dt) <= 30
                      THEN user_id END)                                       AS early_dd,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', enrollment_date, first_dd_dt) > 30
                      THEN user_id END)                                       AS late_dd
FROM edw_db.core.member_details
WHERE DATE_TRUNC('month', first_dd_dt) IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
  AND first_dd_dt IS NOT NULL
  AND LAST_DAY(enrollment_date) < DATEADD('day', -30, CURRENT_DATE)  -- maturity gate
GROUP BY 1
ORDER BY 1;
```

#### 1b. Early DD by channel — both periods

```sql
-- Early DD by channel for current and prior period
SELECT
  DATE_TRUNC('month', md.first_dd_dt)                                        AS conversion_month,
  CASE
    WHEN md.enrollment_channel ILIKE '%referral%'                            THEN 'Referral'
    WHEN md.enrollment_channel ILIKE '%paid_debit%'
      OR md.enrollment_channel ILIKE '%paid_credit%'
      OR md.enrollment_channel ILIKE '%paid%'
      OR md.enrollment_channel ILIKE '%sem%'
      OR md.enrollment_channel ILIKE '%cpc%'                                 THEN 'Paid'
    WHEN md.enrollment_channel ILIKE '%organic%'                             THEN 'Organic'
    WHEN md.enrollment_channel ILIKE '%pay_anyone%'
      OR md.enrollment_channel ILIKE '%pay anyone%'
      OR md.enrollment_channel = 'PA'                                        THEN 'Pay Anyone'
    ELSE 'Others'
  END                                                                         AS channel_bucket,
  COUNT(DISTINCT md.user_id)                                                  AS early_dders
FROM edw_db.core.member_details md
WHERE DATE_TRUNC('month', md.first_dd_dt) IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
  AND md.first_dd_dt IS NOT NULL
  AND DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
  AND LAST_DAY(md.enrollment_date) < DATEADD('day', -30, CURRENT_DATE)
GROUP BY 1, 2
ORDER BY 1, 2;
```

#### 1c. Attribution data — Early DD: channel volume + rate

```sql
-- Early DD attribution: enrollments and DD conversion rate per channel
-- Used to split channel delta into volume effect vs rate effect
SELECT
  DATE_TRUNC('month', md.first_dd_dt)                                        AS conversion_month,
  CASE
    WHEN md.enrollment_channel ILIKE '%referral%'                            THEN 'Referral'
    WHEN md.enrollment_channel ILIKE '%paid_debit%'
      OR md.enrollment_channel ILIKE '%paid_credit%'
      OR md.enrollment_channel ILIKE '%paid%'
      OR md.enrollment_channel ILIKE '%sem%'
      OR md.enrollment_channel ILIKE '%cpc%'                                 THEN 'Paid'
    WHEN md.enrollment_channel ILIKE '%organic%'                             THEN 'Organic'
    WHEN md.enrollment_channel ILIKE '%pay_anyone%'
      OR md.enrollment_channel ILIKE '%pay anyone%'
      OR md.enrollment_channel = 'PA'                                        THEN 'Pay Anyone'
    ELSE 'Others'
  END                                                                         AS channel_bucket,
  COUNT(DISTINCT md.user_id)                                                  AS enrollments,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
                      THEN md.user_id END)                                    AS early_dd_conversions,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
                      THEN md.user_id END)
    / NULLIF(COUNT(DISTINCT md.user_id), 0)                                   AS early_dd_rate
FROM edw_db.core.member_details md
WHERE DATE_TRUNC('month', md.enrollment_date) IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
  AND LAST_DAY(md.enrollment_date) < DATEADD('day', -30, CURRENT_DATE)
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Variance decomposition (computed in Python from 1c results):**

For each channel `i`:
- `volume_effect_i = (current_enrollments_i - prior_enrollments_i) × prior_rate_i`
- `rate_effect_i   = current_enrollments_i × (current_rate_i - prior_rate_i)`
- `total_delta_i   = volume_effect_i + rate_effect_i`  (≈ actual delta per channel)

Sum across channels gives the total Early DD delta attribution.

#### 1d. Gross New DDer by DD paytype — both periods

Classifies each new DDer by the `dd_proforma_type` of their first qualifying DD
transaction (on `first_dd_dt`). Use `MIN()` to pick a deterministic value when
multiple qualifying transactions exist on the same day.

```sql
-- Gross New DDer by DD paytype for current and prior period
WITH new_dder_paytype AS (
  SELECT
    md.user_id,
    DATE_TRUNC('month', md.first_dd_dt)   AS conversion_month,
    MIN(t.dd_proforma_type)               AS dd_proforma_type
  FROM edw_db.core.member_details md
  LEFT JOIN edw_db.core.ftr_transaction t
    ON t.user_id = md.user_id
   AND t.is_qualified_dd = TRUE
   AND t.transaction_date = md.first_dd_dt
  WHERE DATE_TRUNC('month', md.first_dd_dt) IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
    AND md.first_dd_dt IS NOT NULL
  GROUP BY md.user_id, DATE_TRUNC('month', md.first_dd_dt)
)
SELECT
  conversion_month,
  CASE
    WHEN dd_proforma_type = 'payroll'            THEN 'Payroll'
    WHEN dd_proforma_type = 'government_benefit' THEN 'Government Benefit'
    WHEN dd_proforma_type = 'gig_instant_payout' THEN 'Gig / Instant Payout'
    ELSE 'Unknown'
  END                      AS paytype_bucket,
  COUNT(DISTINCT user_id)  AS new_dders
FROM new_dder_paytype
GROUP BY 1, 2
ORDER BY 1, 2;
```

Run the same query substituting `{YOY_MONTH}` / `{YOY_PRIOR_MONTH}` for the
YoY pass. Paytype mix shift (e.g. payroll share declining) is a key hypothesis
driver and should be compared MoM and YoY.

---

### 2. Resurrected DDer

#### 2a. Summary — both periods

```sql
-- Resurrected DDer count: 'Winback' type in base__user_month
SELECT
  calendar_month,
  COUNT(CASE WHEN current_dd_type_proforma = 'Winback' THEN 1 END)           AS resurrected_dders
FROM analytics_db.dbt_cloud_prod.base__user_month
WHERE calendar_month IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
GROUP BY 1
ORDER BY 1;
```

#### 2b. By channel — both periods

```sql
-- Resurrected DDer by original enrollment channel
SELECT
  bum.calendar_month,
  CASE
    WHEN md.enrollment_channel ILIKE '%referral%'                            THEN 'Referral'
    WHEN md.enrollment_channel ILIKE '%paid_debit%'
      OR md.enrollment_channel ILIKE '%paid_credit%'
      OR md.enrollment_channel ILIKE '%paid%'
      OR md.enrollment_channel ILIKE '%sem%'
      OR md.enrollment_channel ILIKE '%cpc%'                                 THEN 'Paid'
    WHEN md.enrollment_channel ILIKE '%organic%'                             THEN 'Organic'
    WHEN md.enrollment_channel ILIKE '%pay_anyone%'
      OR md.enrollment_channel ILIKE '%pay anyone%'
      OR md.enrollment_channel = 'PA'                                        THEN 'Pay Anyone'
    ELSE 'Others'
  END                                                                         AS channel_bucket,
  COUNT(1)                                                                    AS resurrected_dders
FROM analytics_db.dbt_cloud_prod.base__user_month bum
JOIN edw_db.core.member_details md ON md.user_id = bum.user_id
WHERE bum.calendar_month IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
  AND bum.current_dd_type_proforma = 'Winback'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Variance decomposition:** Additive by channel. No rate/volume split needed —
each channel's delta is its direct contribution to the total change.

#### 2c. Resurrected DDer by DD paytype — both periods

Identifies the paytype of the qualifying DD in the resurrection month by joining
to `ftr_transaction` for that calendar month. Uses `MIN()` for determinism when
multiple qualifying DDs fall in the same month.

```sql
-- Resurrected DDer by DD paytype for current and prior period
WITH resurrected_paytype AS (
  SELECT
    bum.user_id,
    bum.calendar_month,
    MIN(t.dd_proforma_type) AS dd_proforma_type
  FROM analytics_db.dbt_cloud_prod.base__user_month bum
  LEFT JOIN edw_db.core.ftr_transaction t
    ON t.user_id = bum.user_id
   AND t.is_qualified_dd = TRUE
   AND DATE_TRUNC('month', t.transaction_date) = bum.calendar_month
  WHERE bum.calendar_month IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
    AND bum.current_dd_type_proforma = 'Winback'
  GROUP BY bum.user_id, bum.calendar_month
)
SELECT
  calendar_month,
  CASE
    WHEN dd_proforma_type = 'payroll'            THEN 'Payroll'
    WHEN dd_proforma_type = 'government_benefit' THEN 'Government Benefit'
    WHEN dd_proforma_type = 'gig_instant_payout' THEN 'Gig / Instant Payout'
    ELSE 'Unknown'
  END                      AS paytype_bucket,
  COUNT(DISTINCT user_id)  AS resurrected_dders
FROM resurrected_paytype
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Variance decomposition:** Additive by paytype. Each bucket's delta is its
direct contribution to the total change; no rate/volume split needed.

---

### 3. M2 DD Retention

**Reporting-month anchoring rule:**
- M2 Retention for `{REPORTING_MONTH}` uses the cohort from `DATEADD('month', -2, {REPORTING_MONTH})`
- M2 Retention for `{PRIOR_MONTH}` uses the cohort from `DATEADD('month', -2, {PRIOR_MONTH})`

#### 3a. Summary — overall rate both periods

```sql
-- M2 DD Retention: overall rate for reporting and prior month
WITH cohort_current AS (
  SELECT user_id
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -2, '{REPORTING_MONTH}')
    AND first_dd_dt IS NOT NULL
),
cohort_prior AS (
  SELECT user_id
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -2, '{PRIOR_MONTH}')
    AND first_dd_dt IS NOT NULL
),
current_status AS (
  SELECT
    c.user_id,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)         AS is_retained
  FROM cohort_current c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{REPORTING_MONTH}'
  GROUP BY c.user_id
),
prior_status AS (
  SELECT
    c.user_id,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)         AS is_retained
  FROM cohort_prior c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{PRIOR_MONTH}'
  GROUP BY c.user_id
)
SELECT
  '{REPORTING_MONTH}'                                                         AS period,
  COUNT(*)                                                                    AS cohort_size,
  SUM(is_retained)                                                            AS retained,
  SUM(is_retained) / NULLIF(COUNT(*), 0)                                      AS m2_retention_rate
FROM current_status
UNION ALL
SELECT
  '{PRIOR_MONTH}',
  COUNT(*),
  SUM(is_retained),
  SUM(is_retained) / NULLIF(COUNT(*), 0)
FROM prior_status
ORDER BY 1;
```

#### 3b. Segment decomposition — by channel × early/late DD, current period

```sql
-- M2 Retention by segment for CURRENT period
-- Cohort: members who converted to DD 2 months before the reporting month
WITH cohort AS (
  SELECT
    md.user_id,
    CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
         THEN 'Early DD' ELSE 'Late DD' END                                   AS dd_timing,
    CASE
      WHEN md.enrollment_channel ILIKE '%referral%'                          THEN 'Referral'
      WHEN md.enrollment_channel ILIKE '%paid_debit%'
        OR md.enrollment_channel ILIKE '%paid_credit%'
        OR md.enrollment_channel ILIKE '%paid%'
        OR md.enrollment_channel ILIKE '%sem%'
        OR md.enrollment_channel ILIKE '%cpc%'                               THEN 'Paid'
      WHEN md.enrollment_channel ILIKE '%organic%'                           THEN 'Organic'
      WHEN md.enrollment_channel ILIKE '%pay_anyone%'
        OR md.enrollment_channel ILIKE '%pay anyone%'
        OR md.enrollment_channel = 'PA'                                      THEN 'Pay Anyone'
      ELSE 'Others'
    END                                                                       AS channel_bucket
  FROM edw_db.core.member_details md
  WHERE DATE_TRUNC('month', md.first_dd_dt) = DATEADD('month', -2, '{REPORTING_MONTH}')
    AND md.first_dd_dt IS NOT NULL
),
m2_status AS (
  SELECT
    c.user_id,
    c.dd_timing,
    c.channel_bucket,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)         AS is_retained
  FROM cohort c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{REPORTING_MONTH}'
  GROUP BY c.user_id, c.dd_timing, c.channel_bucket
)
SELECT
  dd_timing,
  channel_bucket,
  COUNT(*)                                                                    AS cohort_size,
  SUM(is_retained)                                                            AS retained,
  SUM(is_retained) / NULLIF(COUNT(*), 0)                                      AS retention_rate
FROM m2_status
GROUP BY dd_timing, channel_bucket
ORDER BY dd_timing, channel_bucket;
```

Run the same query substituting `{PRIOR_MONTH}` for both date references to get MoM prior period segments.
Run a third pass substituting `{YOY_MONTH}` for both date references to get YoY period segments.
The YoY pass is the **primary decomposition baseline** for m2_retention.

**Variance decomposition (computed in Python — shift-share):**

**Primary baseline: YoY** (`YOY_MONTH` = same reporting month one year prior).
Run the decomposition query a second time for `YOY_MONTH` and use those segment
rates/shares as the `prior` in the shift-share math. This is the headline attribution.
MoM decomposition (using `PRIOR_MONTH`) is computed in addition and shown as secondary context.

For each segment `i` (channel × dd_timing combination), YoY attribution:
- `current_share_i = current_cohort_size_i / total_current_cohort`
- `yoy_share_i     = yoy_cohort_size_i / total_yoy_cohort`
- `yoy_mix_effect_i  = (current_share_i - yoy_share_i) × yoy_rate_i`
- `yoy_rate_effect_i = current_share_i × (current_rate_i - yoy_rate_i)`

Sum of all `yoy_mix_effect_i` = total mix effect on overall rate vs YoY.
Sum of all `yoy_rate_effect_i` = total rate effect on overall rate vs YoY.
Total explained YoY delta ≈ actual YoY delta (small residual is the cross-term).

For MoM attribution (secondary), substitute `prior_share_i` / `prior_rate_i` using `PRIOR_MONTH` data.

#### 3c. M2 DD Retention by DD paytype — both periods

Classifies each cohort member by the `dd_proforma_type` of their first qualifying DD
transaction (on `first_dd_dt`). Measures retention rate separately for payroll,
government benefit, gig, and unknown paytypes.

```sql
-- M2 DD Retention by DD paytype — current period
-- Run analogously substituting {PRIOR_MONTH} for the prior period
WITH cohort AS (
  SELECT
    md.user_id,
    MIN(t.dd_proforma_type) AS dd_proforma_type
  FROM edw_db.core.member_details md
  LEFT JOIN edw_db.core.ftr_transaction t
    ON t.user_id = md.user_id
   AND t.is_qualified_dd = TRUE
   AND t.transaction_date = md.first_dd_dt
  WHERE DATE_TRUNC('month', md.first_dd_dt) = DATEADD('month', -2, '{REPORTING_MONTH}')
    AND md.first_dd_dt IS NOT NULL
  GROUP BY md.user_id
),
m2_status AS (
  SELECT
    c.user_id,
    c.dd_proforma_type,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END) AS is_retained
  FROM cohort c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{REPORTING_MONTH}'
  GROUP BY c.user_id, c.dd_proforma_type
)
SELECT
  CASE
    WHEN dd_proforma_type = 'payroll'            THEN 'Payroll'
    WHEN dd_proforma_type = 'government_benefit' THEN 'Government Benefit'
    WHEN dd_proforma_type = 'gig_instant_payout' THEN 'Gig / Instant Payout'
    ELSE 'Unknown'
  END                                          AS paytype_bucket,
  COUNT(*)                                     AS cohort_size,
  SUM(is_retained)                             AS retained,
  SUM(is_retained) / NULLIF(COUNT(*), 0)       AS retention_rate
FROM m2_status
GROUP BY paytype_bucket
ORDER BY paytype_bucket;
```

Run the same query substituting `{PRIOR_MONTH}` for both date references.

**Variance decomposition (shift-share by paytype):**

For each paytype `i`:
- `mix_effect_i  = (current_share_i - prior_share_i) × prior_rate_i`
- `rate_effect_i = current_share_i × (current_rate_i - prior_rate_i)`

Sum across paytypes gives the total paytype-driven mix and rate effects on the
overall retention rate. Compare alongside the channel × dd_timing decomposition
(query 3b) to identify whether paytype mix shift is additive to or distinct from
channel mix shift.

---

### 4. Early DD/DV (Deposit Volume per Current DD, 35-day window)

**Reporting-month anchoring rule:** Early DV/DD in `{REPORTING_MONTH}` =
DV for members who converted to DD in `DATEADD('month', -1, {REPORTING_MONTH})`.

#### 4a. Summary — both periods

```sql
-- Early DD/DV: DV per current DD in 35-day window after conversion
-- Run once per period; substitute date as needed
-- NOTE: filter type = 'Deposit' to capture external deposits only (ACH, DD, check).
-- Do NOT use acct_in_out = 'In' alone — it includes massive internal self-transfers
-- (single_balance_sweep, allocation_sweep, etc.) that inflate DV significantly.
-- Date column is post_date (DATE); transaction_date does not exist on this table.
WITH cohort AS (
  SELECT
    user_id,
    first_dd_dt                                                               AS conversion_date
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -1, '{REPORTING_MONTH}')
    AND first_dd_dt IS NOT NULL
),
dv_35d AS (
  SELECT
    c.user_id,
    SUM(t.settled_amt)                                                        AS deposit_volume_35d
  FROM cohort c
  JOIN edw_db.core.ftr_transaction t
    ON t.user_id = c.user_id
   AND t.type = 'Deposit'
   AND t.post_date >= c.conversion_date
   AND t.post_date < DATEADD('day', 35, c.conversion_date)
  GROUP BY c.user_id
)
SELECT
  '{REPORTING_MONTH}'                                                         AS period,
  COUNT(DISTINCT c.user_id)                                                   AS current_dd_count,
  SUM(COALESCE(dv.deposit_volume_35d, 0))                                     AS total_dv_35d,
  SUM(COALESCE(dv.deposit_volume_35d, 0))
    / NULLIF(COUNT(DISTINCT c.user_id), 0)                                    AS early_dv_per_dd
FROM cohort c
LEFT JOIN dv_35d dv ON dv.user_id = c.user_id;
```

#### 4b. By channel — current period

```sql
-- Early DD/DV by channel (current period only — run analogously for prior)
-- type = 'Deposit' captures external deposits only; see ftr_transaction gotchas in quirks.md
WITH cohort AS (
  SELECT
    md.user_id,
    md.first_dd_dt                                                            AS conversion_date,
    CASE
      WHEN md.enrollment_channel ILIKE '%referral%'                          THEN 'Referral'
      WHEN md.enrollment_channel ILIKE '%paid_debit%'
        OR md.enrollment_channel ILIKE '%paid_credit%'
        OR md.enrollment_channel ILIKE '%paid%'
        OR md.enrollment_channel ILIKE '%sem%'
        OR md.enrollment_channel ILIKE '%cpc%'                               THEN 'Paid'
      WHEN md.enrollment_channel ILIKE '%organic%'                           THEN 'Organic'
      WHEN md.enrollment_channel ILIKE '%pay_anyone%'
        OR md.enrollment_channel ILIKE '%pay anyone%'
        OR md.enrollment_channel = 'PA'                                      THEN 'Pay Anyone'
      ELSE 'Others'
    END                                                                       AS channel_bucket
  FROM edw_db.core.member_details md
  WHERE DATE_TRUNC('month', md.first_dd_dt) = DATEADD('month', -1, '{REPORTING_MONTH}')
    AND md.first_dd_dt IS NOT NULL
),
dv_35d AS (
  SELECT
    c.user_id,
    SUM(t.settled_amt)                                                        AS deposit_volume_35d
  FROM cohort c
  JOIN edw_db.core.ftr_transaction t
    ON t.user_id = c.user_id
   AND t.type = 'Deposit'
   AND t.post_date >= c.conversion_date
   AND t.post_date < DATEADD('day', 35, c.conversion_date)
  GROUP BY c.user_id
)
SELECT
  c.channel_bucket,
  COUNT(DISTINCT c.user_id)                                                   AS dd_count,
  SUM(COALESCE(dv.deposit_volume_35d, 0))                                     AS total_dv,
  SUM(COALESCE(dv.deposit_volume_35d, 0))
    / NULLIF(COUNT(DISTINCT c.user_id), 0)                                    AS dv_per_dd
FROM cohort c
LEFT JOIN dv_35d dv ON dv.user_id = c.user_id
GROUP BY c.channel_bucket
ORDER BY c.channel_bucket;
```

**Variance decomposition (computed in Python — numerator/denominator split):**

**Primary baseline: YoY** (`YOY_MONTH` = same reporting month one year prior).
Run the decomposition query a second time for `YOY_MONTH` and use those values
as `DV_p` / `DD_p` in the math below. This is the headline attribution.
MoM decomposition is computed in addition and shown as secondary context.

Let `DV_c`, `DV_yoy` = total deposit volume current / YoY.
Let `DD_c`, `DD_yoy` = DD count current / YoY.

- `DV_change_effect = (DV_c - DV_yoy) / DD_yoy`
- `DD_base_effect   = -DV_yoy × (DD_c - DD_yoy) / (DD_yoy × DD_c)`
- Sum ≈ `actual_yoy_delta_in_dv_per_dd`

Channel-level: each channel's contribution to `DV_c - DV_yoy` and `DD_c - DD_yoy`
is used to allocate the two effects.

For MoM attribution (secondary), substitute `DV_p` / `DD_p` using `PRIOR_MONTH` data.

#### 4c. Early DD/DV by DV paytype breakdown — current period

Decomposes total DV in the 35-day window into three buckets at the transaction
level:
- **Payroll DD DV** — qualifying DD transactions with `dd_proforma_type = 'payroll'`
- **Non-Payroll DD DV** — qualifying DD transactions with any other paytype
  (government benefit, gig, unknown)
- **Non-DD DV** — all other inbound transactions (not qualified as DD)

Also computes per-DD ratios to identify which deposit category is driving
DV/DD changes.

```sql
-- Early DD/DV by DV paytype breakdown — current period
-- Run analogously substituting {PRIOR_MONTH} for the prior period
-- type = 'Deposit' excludes internal self-transfers; post_date is the correct date column
WITH cohort AS (
  SELECT
    user_id,
    first_dd_dt AS conversion_date
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -1, '{REPORTING_MONTH}')
    AND first_dd_dt IS NOT NULL
),
dv_by_paytype AS (
  SELECT
    c.user_id,
    SUM(CASE
          WHEN t.is_qualified_dd = TRUE AND t.dd_proforma_type = 'payroll'
          THEN t.settled_amt ELSE 0
        END)                                              AS payroll_dd_dv,
    SUM(CASE
          WHEN t.is_qualified_dd = TRUE
           AND (t.dd_proforma_type != 'payroll' OR t.dd_proforma_type IS NULL)
          THEN t.settled_amt ELSE 0
        END)                                              AS non_payroll_dd_dv,
    SUM(CASE
          WHEN (t.is_qualified_dd IS NULL OR t.is_qualified_dd = FALSE)
          THEN t.settled_amt ELSE 0
        END)                                              AS non_dd_dv,
    SUM(t.settled_amt)                                    AS total_dv_35d
  FROM cohort c
  JOIN edw_db.core.ftr_transaction t
    ON t.user_id = c.user_id
   AND t.type = 'Deposit'
   AND t.post_date >= c.conversion_date
   AND t.post_date < DATEADD('day', 35, c.conversion_date)
  GROUP BY c.user_id
)
SELECT
  '{REPORTING_MONTH}'                                                          AS period,
  COUNT(DISTINCT c.user_id)                                                    AS current_dd_count,
  SUM(COALESCE(dv.payroll_dd_dv,     0))                                       AS total_payroll_dd_dv,
  SUM(COALESCE(dv.non_payroll_dd_dv, 0))                                       AS total_non_payroll_dd_dv,
  SUM(COALESCE(dv.non_dd_dv,         0))                                       AS total_non_dd_dv,
  SUM(COALESCE(dv.total_dv_35d,      0))                                       AS total_dv_35d,
  SUM(COALESCE(dv.payroll_dd_dv,     0)) / NULLIF(COUNT(DISTINCT c.user_id), 0) AS payroll_dd_dv_per_dd,
  SUM(COALESCE(dv.non_payroll_dd_dv, 0)) / NULLIF(COUNT(DISTINCT c.user_id), 0) AS non_payroll_dd_dv_per_dd,
  SUM(COALESCE(dv.non_dd_dv,         0)) / NULLIF(COUNT(DISTINCT c.user_id), 0) AS non_dd_dv_per_dd
FROM cohort c
LEFT JOIN dv_by_paytype dv ON dv.user_id = c.user_id;
```

**Variance decomposition:** Each DV category's contribution to the total
`DV_c - DV_p` delta is its direct additive contribution. Use the same
numerator/denominator split from section 4b but applied per paytype bucket:

For each paytype bucket `k`:
- `DV_change_k = payroll/non-payroll/non-dd DV current − prior`
- `Sum of DV_change_k` = `DV_c − DV_p` (total DV change, before per-DD normalization)
- Each bucket's share of total DV change = its contribution to the DV/DD movement.

When the DV/DD ratio declines, ask: did payroll DD DV drop (lower-value payroll
recipients), did non-DD DV drop (fewer supplemental deposits), or did the DD
count grow faster than DV (denominator base effect)?

---

### 5. Transaction Actives (TA)

**Quarterly goal convention:** Q1 goal = monthly TA in March;
Q2 = June; Q3 = September; Q4 = December.

#### 5a. Summary — both periods + quarterly position

```sql
-- TA: monthly active count with quarterly goal flag
SELECT
  calendar_month,
  COUNT(DISTINCT CASE WHEN is_transaction_active = 1 THEN user_id END)       AS monthly_ta,
  CASE WHEN MONTH(calendar_month) IN (3, 6, 9, 12) THEN 'Quarter End'
       ELSE 'Mid-Quarter' END                                                 AS quarter_position
FROM analytics_db.dbt_cloud_prod.base__user_month
WHERE calendar_month IN ('{REPORTING_MONTH}', '{PRIOR_MONTH}')
GROUP BY 1
ORDER BY 1;
```

#### 5b. YoY comparison (same quarter-end month, prior year)

```sql
-- TA: YoY for the same reporting month one year prior
SELECT
  calendar_month,
  COUNT(DISTINCT CASE WHEN is_transaction_active = 1 THEN user_id END)       AS monthly_ta
FROM analytics_db.dbt_cloud_prod.base__user_month
WHERE calendar_month IN (
  '{REPORTING_MONTH}',
  DATEADD('year', -1, '{REPORTING_MONTH}')
)
GROUP BY 1
ORDER BY 1;
```

**Variance decomposition:** TA is a count metric; channel/product decomposition
uses the additive approach (each segment's delta = its direct contribution).
If `base__user_month` does not carry channel, join to `member_details` on `user_id`.

---

## Hypothesis Checklist by Metric

### Gross New DDer / Early DD

| Category | Hypothesis | Data check |
|---|---|---|
| Mix Shift | Enrollment volume changed (fewer people entering top of funnel) | Compare enrollments MoM by channel |
| Mix Shift | Channel mix shifted (more Late DD channels vs Early DD channels) | Channel share change in query 1b |
| Mix Shift | DD paytype mix shifted (payroll share declined → lower total or lower quality) | Paytype breakdown query 1d — paytype share MoM |
| Product Changes | Eligibility threshold change affected who qualifies | Check product changelog |
| Product Changes | Onboarding flow change reduced D30 conversion rate | Compare D30 rate by channel (query 1c rate_effect) |
| External Factors | Seasonality — Q1 tax season inflates, summer deflates | Compare YoY same month |
| External Factors | Macroeconomic change (payroll cycle, gig economy) | Check DD paytype distribution YoY (query 1d YoY pass) |
| Technical Issues | Data pipeline delay — incomplete month data | Check max(first_dd_dt) for the period |

### Resurrected DDer

| Category | Hypothesis | Data check |
|---|---|---|
| Product Changes | Resurrection campaign or win-back experiment running | Check context file for experiments |
| Product Changes | DD setup optimization improved re-engagement | Compare DD setup funnel for returning members |
| Mix Shift | Base of churned DDers changed size (larger churn → more potential resurrects) | Check churn count 2–3 months prior |
| Mix Shift | Paytype mix of resurrected DDers shifted (e.g. more gig payout resurrects) | Paytype breakdown query 2c — share MoM |
| External Factors | Seasonality — end-of-year or tax season triggers reactivation | YoY comparison |
| External Factors | Payroll / gig economy cycle affects resurrection propensity | Compare paytype distribution YoY (query 2c YoY pass) |

### M2 DD Retention

| Category | Hypothesis | Data check |
|---|---|---|
| Mix Shift | Cohort quality shift — more Paid channel members (lower retention) enrolled 2 months prior | Segment decomposition query 3b — check mix_effect |
| Mix Shift | More Late DD members in cohort (lower retention than Early DD) | dd_timing breakdown |
| Mix Shift | Paytype mix shifted in cohort — more gig/unknown paytypes (historically lower retention) | Paytype breakdown query 3c — compare paytype share and rate MoM |
| Product Changes | Chime Prime launched, affecting which members are "retained" | Check product launch dates in context |
| Product Changes | DD setup optimization experiment improved retention in treatment | Check experiments in context |
| External Factors | Holiday cohort (Dec enrollment) has known lower quality | Historical notes in context |
| External Factors | Gig economy / government benefit seasonality shifted paytype mix in cohort | Check paytype distribution for the cohort month (query 3c prior) |
| Technical Issues | Proforma definition change or pipeline issue | Check if is_current_dd_proforma counts look off |

### Early DD/DV

| Category | Hypothesis | Data check |
|---|---|---|
| Mix Shift | Channel mix shifted toward lower-DV channels (e.g. more Organic vs Paid) | Channel breakdown query 4b |
| Mix Shift | DD count base grew but DV didn't scale proportionally | DD_base_effect from numerator/denominator decomposition |
| Mix Shift | Payroll DD DV share declined — more members receiving smaller payroll or non-payroll deposits | Paytype DV breakdown query 4c — payroll share MoM |
| Mix Shift | Non-DD DV declined — members making fewer supplemental deposits (transfers, cash deposits) | Non-DD DV delta in query 4c |
| Product Changes | New product feature changes deposit behavior (e.g. credit card rollout) | Check context product_launches |
| Product Changes | Feature change affected deposit capture for specific paytype (e.g. gig payout routing change) | Compare gig/government DV MoM in query 4c |
| External Factors | Seasonality — holiday period affects deposit behavior | YoY same month |
| External Factors | Payroll calendar effect — fewer payroll cycles in the reporting month | Compare payroll DD DV per DD YoY (query 4c YoY pass) |

### TA

| Category | Hypothesis | Data check |
|---|---|---|
| Mix Shift | Composition of active base shifted toward lower-transaction members | Segment TA by tenure or product type |
| Product Changes | Feature change reduced purchase/transfer frequency | Check product changes in context |
| External Factors | Seasonality — tax refunds drive Q1 spike, summer is lower | YoY quarter-end comparison |
| Technical Issues | `is_transaction_active` flag definition changed | Check base__user_month changelog |

---

## Critical Data Rules (from quirks.md)

- Always use `is_current_dd_proforma` (not `is_current_dd`) for retention
- Never use `settled_amt > 200` as DD proxy — use `is_qualified_dd = TRUE`
- M0 ≠ D30: M0 is calendar month window, D30 is exact 30-day window — use D30 for Early DD
- For resurrected DDers, use `current_dd_type_proforma = 'Winback'` in `base__user_month`
- `base__user_month` months are 0-indexed (M0=0, M1=1, M2=2)
- Avoid `ANALYTICS.TEST` schema — use production tables only
- `ftr_transaction.settled_amt` can be negative for reversals — always filter `acct_in_out = 'In'` for deposits
