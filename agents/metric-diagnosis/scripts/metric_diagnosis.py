"""
Metric Diagnosis CLI — standalone script for the metric-diagnosis agent.

Connects to Snowflake, runs queries for the specified metric, computes
variance decomposition (factor attribution), and generates an HTML report.

Usage:
    python scripts/metric_diagnosis.py \\
        --metric gross_new_dd \\
        --reporting-month 2026-02-01 \\
        [--prior-month 2026-01-01] \\
        [--context context/chime_2026_02.yaml] \\
        [--snowflake-config config/snowflake_config.yaml] \\
        [--output-dir outputs/]

Supported metrics:
    gross_new_dd       Gross New DDer (Early + Late + channel breakdown)
    resurrected_dd     Resurrected DDer
    m2_retention       M2 DD Retention (reporting-month anchored)
    early_dv           Early DD/DV (deposit volume per current DD, 35 days)
    ta                 Transaction Actives
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Add the agent root to path so local helpers/ are importable.
AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from helpers.snowflake_connector import SnowflakeConnector  # noqa: E402

# ---------------------------------------------------------------------------
# SQL Templates
# ---------------------------------------------------------------------------
# Each template uses {r} for reporting_month and {p} for prior_month
# (both as 'YYYY-MM-01' string literals substituted before execution).

CHANNEL_CASE = """
    CASE
      WHEN md.enrollment_channel ILIKE '%referral%'                      THEN 'Referral'
      WHEN md.enrollment_channel ILIKE '%paid_debit%'
        OR md.enrollment_channel ILIKE '%paid_credit%'
        OR md.enrollment_channel ILIKE '%paid%'
        OR md.enrollment_channel ILIKE '%sem%'
        OR md.enrollment_channel ILIKE '%cpc%'                           THEN 'Paid'
      WHEN md.enrollment_channel ILIKE '%organic%'                       THEN 'Organic'
      WHEN md.enrollment_channel ILIKE '%pay_anyone%'
        OR md.enrollment_channel ILIKE '%pay anyone%'
        OR md.enrollment_channel = 'PA'                                  THEN 'Pay Anyone'
      ELSE 'Others'
    END"""

# ── Gross New DDer ──────────────────────────────────────────────────────────

SQL_GROSS_NEW_DD_SUMMARY = """
SELECT
  DATE_TRUNC('month', first_dd_dt)                                         AS conversion_month,
  COUNT(DISTINCT user_id)                                                   AS total_new_dders,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', enrollment_date, first_dd_dt) <= 30
                      THEN user_id END)                                     AS early_dd,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', enrollment_date, first_dd_dt) > 30
                      THEN user_id END)                                     AS late_dd
FROM edw_db.core.member_details
WHERE DATE_TRUNC('month', first_dd_dt) IN ('{r}', '{p}')
  AND first_dd_dt IS NOT NULL
  AND LAST_DAY(enrollment_date) < DATEADD('day', -30, CURRENT_DATE)
GROUP BY 1
ORDER BY 1
"""

SQL_EARLY_DD_BY_CHANNEL = """
SELECT
  DATE_TRUNC('month', md.first_dd_dt)                                      AS conversion_month,
  {channel_case}                                                            AS channel_bucket,
  COUNT(DISTINCT md.user_id)                                                AS early_dders
FROM edw_db.core.member_details md
WHERE DATE_TRUNC('month', md.first_dd_dt) IN ('{r}', '{p}')
  AND md.first_dd_dt IS NOT NULL
  AND DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
  AND LAST_DAY(md.enrollment_date) < DATEADD('day', -30, CURRENT_DATE)
GROUP BY 1, 2
ORDER BY 1, 2
"""

SQL_EARLY_DD_ATTRIBUTION = """
SELECT
  DATE_TRUNC('month', md.first_dd_dt)                                      AS conversion_month,
  {channel_case}                                                            AS channel_bucket,
  COUNT(DISTINCT md.user_id)                                                AS enrollments,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
                      THEN md.user_id END)                                  AS early_dd_conversions,
  COUNT(DISTINCT CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
                      THEN md.user_id END)
    / NULLIF(COUNT(DISTINCT md.user_id), 0)                                 AS early_dd_rate
FROM edw_db.core.member_details md
WHERE DATE_TRUNC('month', md.enrollment_date) IN ('{r}', '{p}')
  AND LAST_DAY(md.enrollment_date) < DATEADD('day', -30, CURRENT_DATE)
GROUP BY 1, 2
ORDER BY 1, 2
"""

# ── Resurrected DDer ────────────────────────────────────────────────────────

SQL_RESURRECTED_SUMMARY = """
SELECT
  calendar_month,
  COUNT(CASE WHEN current_dd_type_proforma = 'Winback' THEN 1 END)         AS resurrected_dders
FROM analytics_db.dbt_cloud_prod.base__user_month
WHERE calendar_month IN ('{r}', '{p}')
GROUP BY 1
ORDER BY 1
"""

SQL_RESURRECTED_BY_CHANNEL = """
SELECT
  bum.calendar_month,
  {channel_case_bum}                                                        AS channel_bucket,
  COUNT(1)                                                                  AS resurrected_dders
FROM analytics_db.dbt_cloud_prod.base__user_month bum
JOIN edw_db.core.member_details md ON md.user_id = bum.user_id
WHERE bum.calendar_month IN ('{r}', '{p}')
  AND bum.current_dd_type_proforma = 'Winback'
GROUP BY 1, 2
ORDER BY 1, 2
"""

# ── M2 DD Retention ─────────────────────────────────────────────────────────

SQL_M2_RETENTION_SUMMARY = """
WITH cohort_current AS (
  SELECT user_id
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -2, '{r}')
    AND first_dd_dt IS NOT NULL
),
cohort_prior AS (
  SELECT user_id
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -2, '{p}')
    AND first_dd_dt IS NOT NULL
),
current_status AS (
  SELECT c.user_id,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)       AS is_retained
  FROM cohort_current c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{r}'
  GROUP BY c.user_id
),
prior_status AS (
  SELECT c.user_id,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)       AS is_retained
  FROM cohort_prior c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{p}'
  GROUP BY c.user_id
)
SELECT '{r}' AS period, COUNT(*) AS cohort_size, SUM(is_retained) AS retained,
  SUM(is_retained) / NULLIF(COUNT(*), 0) AS m2_retention_rate
FROM current_status
UNION ALL
SELECT '{p}', COUNT(*), SUM(is_retained),
  SUM(is_retained) / NULLIF(COUNT(*), 0)
FROM prior_status
ORDER BY 1
"""

SQL_M2_RETENTION_BY_SEGMENT = """
WITH cohort AS (
  SELECT
    md.user_id,
    CASE WHEN DATEDIFF('day', md.enrollment_date, md.first_dd_dt) <= 30
         THEN 'Early DD' ELSE 'Late DD' END                                AS dd_timing,
    {channel_case}                                                         AS channel_bucket
  FROM edw_db.core.member_details md
  WHERE DATE_TRUNC('month', md.first_dd_dt) = DATEADD('month', -2, '{period}')
    AND md.first_dd_dt IS NOT NULL
),
m2_status AS (
  SELECT c.user_id, c.dd_timing, c.channel_bucket,
    MAX(CASE WHEN bum.is_current_dd_proforma = 1 THEN 1 ELSE 0 END)       AS is_retained
  FROM cohort c
  LEFT JOIN analytics_db.dbt_cloud_prod.base__user_month bum
    ON bum.user_id = c.user_id AND bum.calendar_month = '{period}'
  GROUP BY c.user_id, c.dd_timing, c.channel_bucket
)
SELECT dd_timing, channel_bucket,
  COUNT(*)                                                                  AS cohort_size,
  SUM(is_retained)                                                          AS retained,
  SUM(is_retained) / NULLIF(COUNT(*), 0)                                    AS retention_rate
FROM m2_status
GROUP BY dd_timing, channel_bucket
ORDER BY dd_timing, channel_bucket
"""

# ── Early DD/DV ─────────────────────────────────────────────────────────────

SQL_EARLY_DV_SUMMARY = """
WITH cohort AS (
  SELECT user_id, first_dd_dt AS conversion_date
  FROM edw_db.core.member_details
  WHERE DATE_TRUNC('month', first_dd_dt) = DATEADD('month', -1, '{period}')
    AND first_dd_dt IS NOT NULL
),
dv_35d AS (
  SELECT c.user_id, SUM(t.settled_amt) AS deposit_volume_35d
  FROM cohort c
  JOIN edw_db.core.ftr_transaction t
    ON t.user_id = c.user_id
   AND t.acct_in_out = 'In'
   AND t.transaction_date >= c.conversion_date
   AND t.transaction_date < DATEADD('day', 35, c.conversion_date)
  GROUP BY c.user_id
)
SELECT
  '{period}'                                                                AS period,
  COUNT(DISTINCT c.user_id)                                                 AS current_dd_count,
  SUM(COALESCE(dv.deposit_volume_35d, 0))                                   AS total_dv_35d,
  SUM(COALESCE(dv.deposit_volume_35d, 0))
    / NULLIF(COUNT(DISTINCT c.user_id), 0)                                  AS early_dv_per_dd
FROM cohort c
LEFT JOIN dv_35d dv ON dv.user_id = c.user_id
"""

SQL_EARLY_DV_BY_CHANNEL = """
WITH cohort AS (
  SELECT
    md.user_id, md.first_dd_dt AS conversion_date,
    {channel_case}                                                         AS channel_bucket
  FROM edw_db.core.member_details md
  WHERE DATE_TRUNC('month', md.first_dd_dt) = DATEADD('month', -1, '{period}')
    AND md.first_dd_dt IS NOT NULL
),
dv_35d AS (
  SELECT c.user_id, SUM(t.settled_amt) AS deposit_volume_35d
  FROM cohort c
  JOIN edw_db.core.ftr_transaction t
    ON t.user_id = c.user_id
   AND t.acct_in_out = 'In'
   AND t.transaction_date >= c.conversion_date
   AND t.transaction_date < DATEADD('day', 35, c.conversion_date)
  GROUP BY c.user_id
)
SELECT
  c.channel_bucket,
  COUNT(DISTINCT c.user_id)                                                 AS dd_count,
  SUM(COALESCE(dv.deposit_volume_35d, 0))                                   AS total_dv,
  SUM(COALESCE(dv.deposit_volume_35d, 0))
    / NULLIF(COUNT(DISTINCT c.user_id), 0)                                  AS dv_per_dd
FROM cohort c
LEFT JOIN dv_35d dv ON dv.user_id = c.user_id
GROUP BY c.channel_bucket
ORDER BY c.channel_bucket
"""

# ── Transaction Actives ──────────────────────────────────────────────────────

SQL_TA_SUMMARY = """
SELECT
  calendar_month,
  COUNT(DISTINCT CASE WHEN is_transaction_active = 1 THEN user_id END)     AS monthly_ta,
  CASE WHEN MONTH(calendar_month) IN (3, 6, 9, 12) THEN 'Quarter End'
       ELSE 'Mid-Quarter' END                                               AS quarter_position
FROM analytics_db.dbt_cloud_prod.base__user_month
WHERE calendar_month IN ('{r}', '{p}',
  DATEADD('year', -1, '{r}'), DATEADD('year', -1, '{p}'))
GROUP BY 1
ORDER BY 1
"""


# ---------------------------------------------------------------------------
# Variance Decomposition
# ---------------------------------------------------------------------------

def decompose_count_metric(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
    segment_col: str,
    volume_col: str,
    rate_col: str,
) -> pd.DataFrame:
    """Shift-share decomposition for count metrics (Early DD by channel).

    Splits each segment's delta into volume effect and rate effect.

    Args:
        current_df: Current period data with segment_col, volume_col, rate_col.
        prior_df: Prior period data with same columns.
        segment_col: Column name for the segment dimension (e.g. 'channel_bucket').
        volume_col: Column name for volume (e.g. 'enrollments').
        rate_col: Column name for the conversion rate (e.g. 'early_dd_rate').

    Returns:
        DataFrame with columns: segment, current_volume, prior_volume,
        current_rate, prior_rate, current_count, prior_count,
        volume_effect, rate_effect, total_delta.
    """
    merged = pd.merge(
        current_df[[segment_col, volume_col, rate_col]].rename(
            columns={volume_col: "cur_vol", rate_col: "cur_rate"}
        ),
        prior_df[[segment_col, volume_col, rate_col]].rename(
            columns={volume_col: "pri_vol", rate_col: "pri_rate"}
        ),
        on=segment_col,
        how="outer",
    ).fillna(0)

    merged["cur_count"] = merged["cur_vol"] * merged["cur_rate"]
    merged["pri_count"] = merged["pri_vol"] * merged["pri_rate"]
    merged["volume_effect"] = (merged["cur_vol"] - merged["pri_vol"]) * merged["pri_rate"]
    merged["rate_effect"] = merged["cur_vol"] * (merged["cur_rate"] - merged["pri_rate"])
    merged["total_delta"] = merged["volume_effect"] + merged["rate_effect"]

    total_abs = merged["total_delta"].abs().sum()
    merged["pct_of_total"] = (
        merged["total_delta"] / total_abs * 100
        if total_abs > 0 else 0.0
    )

    return merged.rename(columns={segment_col: "segment"}).sort_values(
        "total_delta", key=abs, ascending=False
    )


def decompose_rate_metric_shiftshare(
    current_seg: pd.DataFrame,
    prior_seg: pd.DataFrame,
    segment_col: str,
    size_col: str,
    rate_col: str,
) -> pd.DataFrame:
    """Shift-share decomposition for rate metrics (M2 Retention by segment).

    For each segment i:
      mix_effect_i  = (current_share_i - prior_share_i) × prior_rate_i
      rate_effect_i = current_share_i × (current_rate_i - prior_rate_i)

    Args:
        current_seg: Current period segment data.
        prior_seg: Prior period segment data.
        segment_col: Segment identifier column.
        size_col: Cohort/population size column (for computing shares).
        rate_col: Rate column (e.g. 'retention_rate').

    Returns:
        DataFrame with columns: segment, current_share, prior_share,
        current_rate, prior_rate, mix_effect, rate_effect, total_effect.
    """
    cur = current_seg[[segment_col, size_col, rate_col]].copy()
    pri = prior_seg[[segment_col, size_col, rate_col]].copy()

    cur["cur_share"] = cur[size_col] / cur[size_col].sum()
    pri["pri_share"] = pri[size_col] / pri[size_col].sum()

    merged = pd.merge(
        cur[[segment_col, "cur_share", rate_col]].rename(columns={rate_col: "cur_rate"}),
        pri[[segment_col, "pri_share", rate_col]].rename(columns={rate_col: "pri_rate"}),
        on=segment_col,
        how="outer",
    ).fillna(0)

    merged["mix_effect"] = (merged["cur_share"] - merged["pri_share"]) * merged["pri_rate"]
    merged["rate_effect"] = merged["cur_share"] * (merged["cur_rate"] - merged["pri_rate"])
    merged["total_effect"] = merged["mix_effect"] + merged["rate_effect"]

    total_abs = merged["total_effect"].abs().sum()
    merged["pct_of_total"] = (
        merged["total_effect"] / total_abs * 100 if total_abs > 0 else 0.0
    )

    return merged.rename(columns={segment_col: "segment"}).sort_values(
        "total_effect", key=abs, ascending=False
    )


def decompose_ratio_metric(
    current_dv: float,
    prior_dv: float,
    current_dd: float,
    prior_dd: float,
) -> list[dict]:
    """Numerator/denominator split for ratio metrics (Early DD/DV).

    Args:
        current_dv: Current period total deposit volume.
        prior_dv: Prior period total deposit volume.
        current_dd: Current period DD count.
        prior_dd: Prior period DD count.

    Returns:
        List of attribution dicts with keys: factor, contribution, pct_of_total.
    """
    dv_change_effect = (current_dv - prior_dv) / (prior_dd or 1)
    dd_base_effect = (
        -prior_dv * (current_dd - prior_dd) / ((prior_dd * current_dd) or 1)
    )
    total = dv_change_effect + dd_base_effect
    total_abs = abs(dv_change_effect) + abs(dd_base_effect)

    return [
        {
            "segment": "DV volume change",
            "contribution": round(dv_change_effect, 2),
            "pct_of_total": round(dv_change_effect / total_abs * 100 if total_abs else 0, 1),
        },
        {
            "segment": "DD base size change",
            "contribution": round(dd_base_effect, 2),
            "pct_of_total": round(dd_base_effect / total_abs * 100 if total_abs else 0, 1),
        },
        {
            "segment": "Total (actual Δ DV/DD)",
            "contribution": round(current_dv / current_dd - prior_dv / prior_dd, 2),
            "pct_of_total": 100.0,
        },
    ]


# ---------------------------------------------------------------------------
# Context Loading
# ---------------------------------------------------------------------------

def load_context(context_path: Optional[str]) -> dict:
    """Load context YAML file. Returns empty dict if path is None or missing."""
    if not context_path:
        return {}
    path = Path(context_path)
    if not path.exists():
        print(f"[warning] Context file not found: {path} — proceeding without context.")
        return {}
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[warning] Could not parse context file: {e}")
        return {}


# ---------------------------------------------------------------------------
# SQL substitution helpers
# ---------------------------------------------------------------------------

def sql(template: str, r: str, p: str, **extra) -> str:
    """Substitute period placeholders and channel CASE into a SQL template."""
    result = template.replace("{r}", r).replace("{p}", p)
    result = result.replace("{channel_case}", CHANNEL_CASE)
    # For queries using a different table alias:
    channel_case_bum = CHANNEL_CASE.replace("md.", "md.")
    result = result.replace("{channel_case_bum}", channel_case_bum)
    for k, v in extra.items():
        result = result.replace(f"{{{k}}}", str(v))
    return result


# ---------------------------------------------------------------------------
# Per-metric diagnosis
# ---------------------------------------------------------------------------

def diagnose_gross_new_dd(
    conn: SnowflakeConnector, r: str, p: str
) -> tuple[dict, list[dict]]:
    """Run all queries for gross_new_dd and compute attribution."""
    queries = {}

    q_summary = sql(SQL_GROSS_NEW_DD_SUMMARY, r, p)
    queries["summary"] = q_summary
    summary = conn.query(q_summary)

    q_channel = sql(SQL_EARLY_DD_BY_CHANNEL, r, p)
    queries["early_by_channel"] = q_channel
    channel = conn.query(q_channel)

    q_attr = sql(SQL_EARLY_DD_ATTRIBUTION, r, p)
    queries["attribution"] = q_attr
    attr = conn.query(q_attr)

    # Variance decomposition for Early DD by channel
    cur_attr = attr[attr["conversion_month"].astype(str).str.startswith(r[:7])]
    pri_attr = attr[attr["conversion_month"].astype(str).str.startswith(p[:7])]

    attribution_df = decompose_count_metric(
        current_df=cur_attr,
        prior_df=pri_attr,
        segment_col="channel_bucket",
        volume_col="enrollments",
        rate_col="early_dd_rate",
    )

    return (
        {"summary": summary, "channel": channel, "attribution_raw": attr},
        [{"name": k, "sql": v} for k, v in queries.items()],
    ), attribution_df


def diagnose_resurrected_dd(
    conn: SnowflakeConnector, r: str, p: str
) -> tuple[dict, list[dict]]:
    queries = {}

    q_summary = sql(SQL_RESURRECTED_SUMMARY, r, p)
    queries["summary"] = q_summary
    summary = conn.query(q_summary)

    q_channel = sql(SQL_RESURRECTED_BY_CHANNEL, r, p)
    queries["by_channel"] = q_channel
    by_channel = conn.query(q_channel)

    # Additive attribution: each channel's delta is its direct contribution
    cur = by_channel[by_channel["calendar_month"].astype(str).str.startswith(r[:7])]
    pri = by_channel[by_channel["calendar_month"].astype(str).str.startswith(p[:7])]
    attribution_df = pd.merge(
        cur[["channel_bucket", "resurrected_dders"]].rename(columns={"resurrected_dders": "current"}),
        pri[["channel_bucket", "resurrected_dders"]].rename(columns={"resurrected_dders": "prior"}),
        on="channel_bucket", how="outer",
    ).fillna(0)
    attribution_df["total_delta"] = attribution_df["current"] - attribution_df["prior"]
    total_abs = attribution_df["total_delta"].abs().sum()
    attribution_df["pct_of_total"] = (
        attribution_df["total_delta"] / total_abs * 100 if total_abs > 0 else 0.0
    )
    attribution_df = attribution_df.sort_values("total_delta", key=abs, ascending=False)

    return (
        {"summary": summary, "by_channel": by_channel},
        [{"name": k, "sql": v} for k, v in queries.items()],
    ), attribution_df


def diagnose_m2_retention(
    conn: SnowflakeConnector, r: str, p: str
) -> tuple[dict, list[dict]]:
    queries = {}

    q_summary = sql(SQL_M2_RETENTION_SUMMARY, r, p)
    queries["summary"] = q_summary
    summary = conn.query(q_summary)

    q_seg_r = sql(SQL_M2_RETENTION_BY_SEGMENT, r, p, period=r)
    queries["segment_current"] = q_seg_r
    seg_current = conn.query(q_seg_r)
    seg_current["segment"] = seg_current["dd_timing"] + " | " + seg_current["channel_bucket"]

    q_seg_p = sql(SQL_M2_RETENTION_BY_SEGMENT, r, p, period=p)
    queries["segment_prior"] = q_seg_p
    seg_prior = conn.query(q_seg_p)
    seg_prior["segment"] = seg_prior["dd_timing"] + " | " + seg_prior["channel_bucket"]

    attribution_df = decompose_rate_metric_shiftshare(
        current_seg=seg_current.rename(columns={"segment": "seg_key"}),
        prior_seg=seg_prior.rename(columns={"segment": "seg_key"}),
        segment_col="seg_key",
        size_col="cohort_size",
        rate_col="retention_rate",
    )

    return (
        {"summary": summary, "seg_current": seg_current, "seg_prior": seg_prior},
        [{"name": k, "sql": v} for k, v in queries.items()],
    ), attribution_df


def diagnose_early_dv(
    conn: SnowflakeConnector, r: str, p: str
) -> tuple[dict, list[dict]]:
    queries = {}

    q_summary_r = sql(SQL_EARLY_DV_SUMMARY, r, p, period=r)
    queries["summary_current"] = q_summary_r
    summary_r = conn.query(q_summary_r)

    q_summary_p = sql(SQL_EARLY_DV_SUMMARY, r, p, period=p)
    queries["summary_prior"] = q_summary_p
    summary_p = conn.query(q_summary_p)

    q_ch_r = sql(SQL_EARLY_DV_BY_CHANNEL, r, p, period=r)
    queries["channel_current"] = q_ch_r
    ch_r = conn.query(q_ch_r)

    q_ch_p = sql(SQL_EARLY_DV_BY_CHANNEL, r, p, period=p)
    queries["channel_prior"] = q_ch_p
    ch_p = conn.query(q_ch_p)

    # Numerator / denominator decomposition
    cur_dv = float(summary_r.iloc[0]["total_dv_35d"])
    pri_dv = float(summary_p.iloc[0]["total_dv_35d"])
    cur_dd = float(summary_r.iloc[0]["current_dd_count"])
    pri_dd = float(summary_p.iloc[0]["current_dd_count"])
    attribution_list = decompose_ratio_metric(cur_dv, pri_dv, cur_dd, pri_dd)
    attribution_df = pd.DataFrame(attribution_list)

    return (
        {
            "summary_current": summary_r,
            "summary_prior": summary_p,
            "channel_current": ch_r,
            "channel_prior": ch_p,
        },
        [{"name": k, "sql": v} for k, v in queries.items()],
    ), attribution_df


def diagnose_ta(
    conn: SnowflakeConnector, r: str, p: str
) -> tuple[dict, list[dict]]:
    queries = {}

    q_summary = sql(SQL_TA_SUMMARY, r, p)
    queries["summary_with_yoy"] = q_summary
    summary = conn.query(q_summary)

    # Simple additive attribution: current vs prior delta
    cur_ta = summary[summary["calendar_month"].astype(str).str.startswith(r[:7])]["monthly_ta"].sum()
    pri_ta = summary[summary["calendar_month"].astype(str).str.startswith(p[:7])]["monthly_ta"].sum()
    delta = cur_ta - pri_ta
    attribution_df = pd.DataFrame([
        {"segment": "MoM change", "contribution": delta,
         "pct_of_total": 100.0 if delta != 0 else 0.0},
    ])

    return (
        {"summary": summary},
        [{"name": k, "sql": v} for k, v in queries.items()],
    ), attribution_df


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

METRIC_CONFIG = {
    "gross_new_dd": {
        "display_name": "Gross New DDer",
        "threshold_key": "gross_new_dd_pct",
        "default_threshold": 8,
        "threshold_type": "pct",
        "value_col": "total_new_dders",
    },
    "resurrected_dd": {
        "display_name": "Resurrected DDer",
        "threshold_key": "resurrected_dd_pct",
        "default_threshold": 10,
        "threshold_type": "pct",
        "value_col": "resurrected_dders",
    },
    "m2_retention": {
        "display_name": "M2 DD Retention",
        "threshold_key": "m2_retention_pp",
        "default_threshold": 1.5,
        "threshold_type": "pp",
        "value_col": "m2_retention_rate",
    },
    "early_dv": {
        "display_name": "Early DD/DV",
        "threshold_key": "early_dv_pct",
        "default_threshold": 5,
        "threshold_type": "pct",
        "value_col": "early_dv_per_dd",
    },
    "ta": {
        "display_name": "Transaction Actives",
        "threshold_key": "ta_pct",
        "default_threshold": 5,
        "threshold_type": "pct",
        "value_col": "monthly_ta",
    },
}


def detect_anomaly(
    current_val: float,
    prior_val: float,
    metric: str,
    context: dict,
) -> dict:
    """Return anomaly flag info for a metric."""
    cfg = METRIC_CONFIG[metric]
    thresholds = context.get("thresholds", {})
    threshold = thresholds.get(cfg["threshold_key"], cfg["default_threshold"])

    if prior_val == 0:
        return {"flag": "WARN", "delta": 0, "delta_pct": None, "threshold": threshold}

    if cfg["threshold_type"] == "pct":
        delta = current_val - prior_val
        delta_pct = (delta / prior_val) * 100
        flag = "ALERT" if abs(delta_pct) >= threshold else (
            "WATCH" if abs(delta_pct) >= threshold * 0.5 else "OK"
        )
        return {"flag": flag, "delta": delta, "delta_pct": delta_pct, "threshold": threshold}
    else:  # pp
        delta = (current_val - prior_val) * 100  # convert to pp
        flag = "ALERT" if abs(delta) >= threshold else (
            "WATCH" if abs(delta) >= threshold * 0.5 else "OK"
        )
        return {"flag": flag, "delta": delta, "delta_pct": delta / prior_val * 100, "threshold": threshold}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

METRIC_RUNNERS = {
    "gross_new_dd": diagnose_gross_new_dd,
    "resurrected_dd": diagnose_resurrected_dd,
    "m2_retention": diagnose_m2_retention,
    "early_dv": diagnose_early_dv,
    "ta": diagnose_ta,
}


def main():
    parser = argparse.ArgumentParser(
        description="Metric Diagnosis — GA metric deep dive with factor attribution"
    )
    parser.add_argument(
        "--metric",
        required=True,
        choices=list(METRIC_RUNNERS.keys()),
        help="Metric to diagnose",
    )
    parser.add_argument(
        "--reporting-month",
        required=True,
        metavar="YYYY-MM-01",
        help="Reporting month as first-of-month date",
    )
    parser.add_argument(
        "--prior-month",
        metavar="YYYY-MM-01",
        help="Prior period month (defaults to one month before reporting month)",
    )
    parser.add_argument(
        "--context",
        metavar="PATH",
        help="Path to filled context_template.yaml",
    )
    parser.add_argument(
        "--snowflake-config",
        default=str(AGENT_ROOT / "config" / "snowflake_config.yaml"),
        metavar="PATH",
        help="Path to snowflake_config.yaml",
    )
    parser.add_argument(
        "--output-dir",
        default=str(AGENT_ROOT / "outputs"),
        metavar="PATH",
    )
    parser.add_argument(
        "--slides",
        action="store_true",
        default=False,
        help=(
            "Also generate slides skeleton output: "
            "outputs/slides/{metric}_{month}/slides_outline.md + CSVs + PNGs"
        ),
    )
    args = parser.parse_args()

    # Normalize dates to first-of-month
    r = args.reporting_month if args.reporting_month.endswith("-01") else args.reporting_month + "-01"
    if args.prior_month:
        p = args.prior_month if args.prior_month.endswith("-01") else args.prior_month + "-01"
    else:
        # Derive prior month
        dt = datetime.strptime(r, "%Y-%m-%d")
        if dt.month == 1:
            p = f"{dt.year - 1}-12-01"
        else:
            p = f"{dt.year}-{dt.month - 1:02d}-01"

    print(f"[metric-diagnosis] {METRIC_CONFIG[args.metric]['display_name']} | {r} vs {p}")

    # Load context
    context = load_context(args.context)

    # Connect to Snowflake
    print("[metric-diagnosis] Connecting to Snowflake...")
    conn = SnowflakeConnector.from_config(args.snowflake_config)
    conn.connect()
    print("[metric-diagnosis] Connected.")

    # Run metric-specific queries
    print(f"[metric-diagnosis] Running queries for {args.metric}...")
    runner = METRIC_RUNNERS[args.metric]
    (data, queries), attribution_df = runner(conn, r, p)
    conn.close()
    print("[metric-diagnosis] Queries complete.")

    # Anomaly detection on summary
    summary = data.get("summary") or data.get("summary_current")
    cur_row = summary[summary.iloc[:, 0].astype(str).str.startswith(r[:7])].iloc[0]
    pri_row = summary[summary.iloc[:, 0].astype(str).str.startswith(p[:7])].iloc[0] if len(summary) > 1 else cur_row

    value_col = METRIC_CONFIG[args.metric]["value_col"]
    try:
        cur_val = float(cur_row[value_col])
        pri_val = float(pri_row[value_col])
    except (KeyError, IndexError):
        cur_val = pri_val = 0.0

    anomaly = detect_anomaly(cur_val, pri_val, args.metric, context)

    # Generate report
    from scripts.report_generator import generate_report  # noqa: E402

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"metric_diagnosis_{args.metric}_{r}.html"

    generate_report(
        metric=args.metric,
        reporting_month=r,
        prior_month=p,
        data=data,
        attribution_df=attribution_df,
        queries=queries,
        anomaly=anomaly,
        context=context,
        output_path=str(output_path),
    )

    print(f"[metric-diagnosis] Report written to: {output_path}")

    if args.slides:
        from scripts.slides_generator import generate_slides  # noqa: E402

        outline_path = generate_slides(
            metric=args.metric,
            reporting_month=r,
            prior_month=p,
            data=data,
            attribution_df=attribution_df,
            hypotheses=None,   # hypotheses are built interactively; pass list[dict] if available
            anomaly=anomaly,
            context=context,
            output_dir=output_dir,
        )
        print(f"[metric-diagnosis] Slides skeleton written to: {outline_path.parent}")


if __name__ == "__main__":
    main()
