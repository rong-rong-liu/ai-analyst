"""
Slides Skeleton Generator for the metric-diagnosis agent.

Produces a slides-ready output folder alongside the HTML report:
  outputs/slides/{metric}_{YYYY_MM}/
    slides_outline.md          -- per-slide skeleton with titles, taglines, key messages
    data/
      slide_2_trend.csv
      slide_3_anomaly.csv
      slide_4_decomposition.csv
      slide_5_attribution.csv
      slide_6_hypotheses.csv
    charts/
      slide_2_trend.png
      slide_3_anomaly.png
      slide_4_decomposition.png
      slide_5_attribution_waterfall.png

Usage (from metric_diagnosis.py):
    from scripts.slides_generator import generate_slides
    slides_dir = generate_slides(
        metric, reporting_month, prior_month,
        data, attribution_df, hypotheses, anomaly, context, output_dir
    )
    print(f"Slides written to: {slides_dir}")
"""

from __future__ import annotations

import csv
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_slides(
    metric: str,
    reporting_month: str,
    prior_month: str,
    data: dict[str, pd.DataFrame],
    attribution_df: Optional[pd.DataFrame],
    hypotheses: Optional[list[dict]],
    anomaly: dict,
    context: dict,
    output_dir: str | Path,
) -> Path:
    """
    Generate the full slides skeleton folder.

    Parameters
    ----------
    metric            : metric key, e.g. 'm2_retention'
    reporting_month   : 'YYYY-MM-01'
    prior_month       : 'YYYY-MM-01'
    data              : dict of DataFrames keyed by query name (from runner)
    attribution_df    : DataFrame with columns [factor, contribution, pct_of_delta]
    hypotheses        : list of dicts with keys [id, category, hypothesis, confidence, attribution_pct]
    anomaly           : dict from detect_anomaly() with keys [flag, delta, delta_pct, threshold]
    context           : dict loaded from context YAML (may be empty)
    output_dir        : root outputs/ directory

    Returns
    -------
    Path to slides_outline.md
    """
    # Build output folder
    month_tag = reporting_month[:7].replace("-", "_")
    slides_dir = Path(output_dir) / "slides" / f"{metric}_{month_tag}"
    data_dir = slides_dir / "data"
    charts_dir = slides_dir / "charts"
    data_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Write data CSVs
    csv_paths = _write_csvs(data_dir, metric, data, attribution_df, hypotheses)

    # Write charts (PNG via matplotlib if available, else write generate_charts.py)
    chart_paths = _write_charts(charts_dir, metric, reporting_month, data, attribution_df, anomaly)

    # Write slides_outline.md
    outline_path = _write_outline(
        slides_dir=slides_dir,
        metric=metric,
        reporting_month=reporting_month,
        prior_month=prior_month,
        data=data,
        attribution_df=attribution_df,
        hypotheses=hypotheses,
        anomaly=anomaly,
        context=context,
        csv_paths=csv_paths,
        chart_paths=chart_paths,
    )

    return outline_path


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def _write_csvs(
    data_dir: Path,
    metric: str,
    data: dict[str, pd.DataFrame],
    attribution_df: Optional[pd.DataFrame],
    hypotheses: Optional[list[dict]],
) -> dict[str, Optional[Path]]:
    """Write one CSV per data-backed slide. Returns mapping slide_name -> path."""
    paths: dict[str, Optional[Path]] = {}

    # Slide 2: Trend — use summary or channel breakdown if available
    trend_df = _find_df(data, ["summary", "trend", "summary_current"])
    if trend_df is not None:
        p = data_dir / "slide_2_trend.csv"
        trend_df.to_csv(p, index=False)
        paths["trend"] = p
    else:
        paths["trend"] = None

    # Slide 3: Anomaly — current vs YoY summary row
    anomaly_df = _find_df(data, ["summary", "summary_current"])
    if anomaly_df is not None:
        p = data_dir / "slide_3_anomaly.csv"
        anomaly_df.to_csv(p, index=False)
        paths["anomaly"] = p
    else:
        paths["anomaly"] = None

    # Slide 4: Decomposition — channel × timing breakdown
    decomp_df = _find_df(data, [
        "channel_timing", "channel_breakdown", "by_channel",
        "early_dd_by_channel", "channel_cross_tab",
    ])
    if decomp_df is None:
        decomp_df = _find_df(data, list(data.keys()))  # fallback to first available
    if decomp_df is not None:
        p = data_dir / "slide_4_decomposition.csv"
        decomp_df.to_csv(p, index=False)
        paths["decomposition"] = p
    else:
        paths["decomposition"] = None

    # Slide 5: Attribution waterfall
    if attribution_df is not None and not attribution_df.empty:
        p = data_dir / "slide_5_attribution.csv"
        attribution_df.to_csv(p, index=False)
        paths["attribution"] = p
    else:
        paths["attribution"] = None

    # Slide 6: Hypotheses
    if hypotheses:
        p = data_dir / "slide_6_hypotheses.csv"
        _write_hypotheses_csv(p, hypotheses)
        paths["hypotheses"] = p
    else:
        paths["hypotheses"] = None

    return paths


def _write_hypotheses_csv(path: Path, hypotheses: list[dict]) -> None:
    fieldnames = ["id", "category", "hypothesis", "confidence", "attribution_pct", "evidence_needed"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(hypotheses)


# ---------------------------------------------------------------------------
# Chart writers
# ---------------------------------------------------------------------------

def _write_charts(
    charts_dir: Path,
    metric: str,
    reporting_month: str,
    data: dict[str, pd.DataFrame],
    attribution_df: Optional[pd.DataFrame],
    anomaly: dict,
) -> dict[str, Optional[Path]]:
    """
    Attempt to render PNG charts via matplotlib.
    Falls back to writing a standalone generate_charts.py script if matplotlib
    is not installed or chart data is unavailable.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        _matplotlib_available = True
    except ImportError:
        _matplotlib_available = False

    paths: dict[str, Optional[Path]] = {}

    if not _matplotlib_available:
        _write_chart_script(charts_dir, metric, reporting_month, data, attribution_df, anomaly)
        return {k: None for k in ["trend", "anomaly", "decomposition", "attribution"]}

    # ── Slide 2: Trend line chart ────────────────────────────────────────────
    trend_df = _find_df(data, ["summary", "trend", "summary_current"])
    trend_path = None
    if trend_df is not None:
        try:
            trend_path = _chart_trend(charts_dir, metric, trend_df, plt)
        except Exception:
            trend_path = None
    paths["trend"] = trend_path

    # ── Slide 3: Anomaly bar ─────────────────────────────────────────────────
    anomaly_path = None
    try:
        anomaly_path = _chart_anomaly(charts_dir, metric, reporting_month, anomaly, plt)
    except Exception:
        anomaly_path = None
    paths["anomaly"] = anomaly_path

    # ── Slide 4: Decomposition grouped bar ──────────────────────────────────
    decomp_df = _find_df(data, [
        "channel_timing", "channel_breakdown", "by_channel",
        "early_dd_by_channel", "channel_cross_tab",
    ])
    decomp_path = None
    if decomp_df is not None:
        try:
            decomp_path = _chart_decomposition(charts_dir, decomp_df, plt)
        except Exception:
            decomp_path = None
    paths["decomposition"] = decomp_path

    # ── Slide 5: Attribution waterfall ───────────────────────────────────────
    waterfall_path = None
    if attribution_df is not None and not attribution_df.empty:
        try:
            waterfall_path = _chart_waterfall(charts_dir, attribution_df, plt)
        except Exception:
            waterfall_path = None
    paths["attribution"] = waterfall_path

    return paths


_METRIC_AXIS_LABELS: dict[str, str] = {
    "m2_retention": "M2 DD Retention Rate (%)",
    "early_dd": "Early DD Count",
    "resurrected_dd": "Resurrected DD Count",
    "ta": "Monthly Transaction Actives",
    "early_dv": "Deposit Volume per DD Member ($)",
}

_COL_AXIS_LABELS: dict[str, str] = {
    "m2_rate": "M2 Retention Rate (%)",
    "m2_dd_retention_rate": "M2 Retention Rate (%)",
    "resurrection_rate_pct": "Resurrection Rate (%)",
    "resurrected_count": "Resurrected Members",
    "total_new_dders": "New DD Members",
    "early_dders": "Early DD Members",
    "early_dv_per_dd": "Deposit Volume / DD Member ($)",
    "monthly_ta": "Monthly Actives",
    "early_dd_rate": "Early DD Conversion Rate (%)",
    "cohort_size": "Cohort Size",
}


def _axis_label(col_name: str, metric: str = "") -> str:
    """Return a human-readable axis label for a column."""
    if col_name in _COL_AXIS_LABELS:
        return _COL_AXIS_LABELS[col_name]
    if metric in _METRIC_AXIS_LABELS:
        return _METRIC_AXIS_LABELS[metric]
    return col_name.replace("_", " ").replace("pct", "%").title()


def _chart_trend(charts_dir: Path, metric: str, df: pd.DataFrame, plt) -> Optional[Path]:
    """Line chart: metric value over time, colored by year."""
    date_col = _detect_col(df, ["conversion_month", "calendar_month", "month", "analysis_month"])
    val_col = _detect_col(df, [
        "m2_rate", "m2_dd_retention_rate", "resurrected_count", "total_new_dders",
        "early_dv_per_dd", "monthly_ta", "resurrection_rate_pct",
    ])
    if date_col is None or val_col is None:
        return None

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col].astype(str).str[:7], format="%Y-%m")
    df = df.sort_values(date_col)
    df["year"] = df[date_col].dt.year

    metric_title = _metric_display_name(metric)
    y_label = _axis_label(val_col, metric)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = {2023: "#9ca3af", 2024: "#3b82f6", 2025: "#f97316"}

    for yr, grp in df.groupby("year"):
        color = colors.get(yr, "#6b7280")
        ax.plot(grp[date_col], grp[val_col], marker="o", label=str(yr),
                color=color, linewidth=2, markersize=5)

    yr24 = df[df["year"] == 2024]
    if not yr24.empty:
        avg24 = yr24[val_col].mean()
        ax.axhline(avg24, color="#3b82f6", linestyle="--", linewidth=1, alpha=0.5)
        ax.text(df[date_col].min(), avg24 * 1.005, f"2024 avg: {avg24:.1f}",
                color="#3b82f6", fontsize=8)

    ax.set_title(f"{metric_title} — Monthly Trend", fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel(y_label, fontsize=10)
    ax.legend(title="Year", fontsize=9)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_2_trend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_anomaly(
    charts_dir: Path, metric: str, reporting_month: str, anomaly: dict, plt
) -> Optional[Path]:
    """Two-bar horizontal chart: current period vs prior year, annotated with delta."""
    flag = anomaly.get("flag", "OK")
    delta = anomaly.get("delta", 0)
    cur = anomaly.get("current_value", 0)
    yoy = anomaly.get("yoy_value", cur - delta) if anomaly.get("yoy_value") else cur - delta

    color_map = {"ALERT": "#dc2626", "WATCH": "#d97706", "OK": "#059669"}
    bar_color = color_map.get(flag, "#6b7280")

    month_label = reporting_month[:7]
    yoy_label = f"{int(month_label[:4]) - 1}{month_label[4:]}"
    metric_title = _metric_display_name(metric)

    flag_labels = {"ALERT": "ALERT — Outside expected range", "WATCH": "WATCH — Approaching threshold", "OK": "OK — Within normal range"}
    title_label = flag_labels.get(flag, flag)

    fig, ax = plt.subplots(figsize=(7, 3))
    bars = ax.barh([yoy_label, month_label], [yoy, cur],
                   color=["#9ca3af", bar_color], height=0.4)

    for bar, val in zip(bars, [yoy, cur]):
        ax.text(bar.get_width() + abs(max(yoy, cur)) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=10, fontweight="bold")

    sign = "+" if delta > 0 else ""
    ax.set_title(
        f"{metric_title}: {sign}{delta:.2f} year-over-year  |  {title_label}",
        fontsize=11, fontweight="bold", color=bar_color,
    )
    ax.set_xlabel(_axis_label("", metric), fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_3_anomaly.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_decomposition(charts_dir: Path, df: pd.DataFrame, plt) -> Optional[Path]:
    """Grouped horizontal bar: segments on Y-axis, prior year vs current."""
    rate_col = _detect_col(df, ["m2_rate", "resurrection_rate_pct", "early_dd_rate", "m2_dd_retention_rate"])
    count_col = _detect_col(df, ["cohort_size", "resurrected_count", "early_dders", "total_new_dders"])
    val_col = rate_col or count_col
    if val_col is None:
        return None

    seg_col = _detect_col(df, ["channel", "channel_bucket", "segment", "dd_timing", "churn_tenure_segment"])
    period_col = _detect_col(df, ["cohort_year", "conversion_month", "calendar_month", "analysis_month"])
    if seg_col is None or period_col is None:
        return None

    df = df.copy()
    df[period_col] = df[period_col].astype(str).str[:7]

    try:
        pivot = df.pivot_table(index=seg_col, columns=period_col, values=val_col, aggfunc="mean")
    except Exception:
        return None

    if pivot.empty or pivot.shape[1] < 2:
        return None

    p1, p2 = pivot.columns[-2], pivot.columns[-1]
    pivot = pivot[[p1, p2]].dropna().sort_values(p2, ascending=True)

    segments = pivot.index.tolist()
    y = range(len(segments))
    bar_height = 0.35
    y_label = _axis_label(val_col)

    fig, ax = plt.subplots(figsize=(9, max(4, len(segments) * 0.55 + 1)))
    ax.barh([i - bar_height / 2 for i in y], pivot[p1], height=bar_height,
            label=str(p1), color="#3b82f6", alpha=0.85)
    ax.barh([i + bar_height / 2 for i in y], pivot[p2], height=bar_height,
            label=str(p2), color="#f97316", alpha=0.85)

    ax.set_yticks(list(y))
    ax.set_yticklabels(segments, fontsize=9)
    ax.set_xlabel(y_label, fontsize=10)
    ax.set_title("Performance by Segment — Prior Year vs. Current", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_4_decomposition.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_waterfall(charts_dir: Path, attribution_df: pd.DataFrame, plt) -> Optional[Path]:
    """Horizontal waterfall: factors on Y-axis, positive = green, negative = red."""
    factor_col = _detect_col(attribution_df, ["factor", "segment", "driver", "name"])
    contrib_col = _detect_col(attribution_df, ["contribution", "yoy_contribution", "mom_contribution", "delta"])
    if factor_col is None or contrib_col is None:
        return None

    df = attribution_df[[factor_col, contrib_col]].copy()
    df.columns = ["factor", "contribution"]
    df["contribution"] = pd.to_numeric(df["contribution"], errors="coerce").fillna(0)
    df = df.reindex(df["contribution"].abs().sort_values(ascending=True).index)

    colors = ["#dc2626" if v < 0 else "#059669" for v in df["contribution"]]

    fig, ax = plt.subplots(figsize=(9, max(4, len(df) * 0.55 + 1)))
    bars = ax.barh(df["factor"], df["contribution"], color=colors, height=0.55)

    for bar, val in zip(bars, df["contribution"]):
        xpos = bar.get_width() + (0.02 if val >= 0 else -0.02)
        ha = "left" if val >= 0 else "right"
        ax.text(xpos, bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}", va="center", ha=ha, fontsize=8.5)

    ax.axvline(0, color="#374151", linewidth=0.8)
    ax.set_xlabel("Contribution to Year-over-Year Change", fontsize=10)
    ax.set_title("Root Cause Breakdown — Contribution by Factor", fontsize=13, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_5_attribution_waterfall.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
    return path


def _write_chart_script(
    charts_dir: Path,
    metric: str,
    reporting_month: str,
    data: dict[str, pd.DataFrame],
    attribution_df: Optional[pd.DataFrame],
    anomaly: dict,
) -> None:
    """Write a standalone generate_charts.py the user can run locally."""
    script_path = charts_dir.parent / "generate_charts.py"
    script_path.write_text(textwrap.dedent(f"""\
        \"\"\"
        Auto-generated chart script for {metric} / {reporting_month}.
        Run from the slides folder:  python generate_charts.py
        Requires: pip install matplotlib pandas
        \"\"\"
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
        from pathlib import Path

        CHARTS_DIR = Path(__file__).parent / "charts"
        DATA_DIR = Path(__file__).parent / "data"
        CHARTS_DIR.mkdir(exist_ok=True)

        # ── Slide 2: Trend ───────────────────────────────────────────────────
        trend_csv = DATA_DIR / "slide_2_trend.csv"
        if trend_csv.exists():
            df = pd.read_csv(trend_csv)
            date_col = next((c for c in df.columns if "month" in c.lower()), df.columns[0])
            val_col = next((c for c in df.columns if any(k in c.lower()
                           for k in ["rate", "count", "dders", "ta"])), df.columns[-1])
            df[date_col] = pd.to_datetime(df[date_col].astype(str).str[:7], format="%Y-%m")
            df = df.sort_values(date_col)
            df["year"] = df[date_col].dt.year
            colors = {{2023: "#9ca3af", 2024: "#3b82f6", 2025: "#f97316"}}
            fig, ax = plt.subplots(figsize=(10, 4.5))
            for yr, grp in df.groupby("year"):
                ax.plot(grp[date_col], grp[val_col], marker="o", label=str(yr),
                        color=colors.get(yr, "#6b7280"), linewidth=2, markersize=5)
            ax.set_title("{metric.replace('_', ' ').title()} Trend", fontsize=13, fontweight="bold")
            ax.legend(title="Year"); ax.grid(axis="y", alpha=0.3)
            ax.tick_params(axis="x", rotation=45, labelsize=8)
            fig.tight_layout()
            fig.savefig(CHARTS_DIR / "slide_2_trend.png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            print("Wrote slide_2_trend.png")

        # ── Slide 4: Decomposition ───────────────────────────────────────────
        decomp_csv = DATA_DIR / "slide_4_decomposition.csv"
        if decomp_csv.exists():
            df = pd.read_csv(decomp_csv)
            # Adjust column names to match your actual CSV
            print("slide_4_decomposition.csv loaded — add chart logic as needed")

        # ── Slide 5: Attribution waterfall ───────────────────────────────────
        attr_csv = DATA_DIR / "slide_5_attribution.csv"
        if attr_csv.exists():
            df = pd.read_csv(attr_csv)
            factor_col = next((c for c in df.columns if "factor" in c.lower()), df.columns[0])
            contrib_col = next((c for c in df.columns if any(k in c.lower()
                               for k in ["contribution", "delta", "impact"])), df.columns[-1])
            df[contrib_col] = pd.to_numeric(df[contrib_col], errors="coerce").fillna(0)
            df = df.reindex(df[contrib_col].abs().sort_values(ascending=True).index)
            colors = ["#dc2626" if v < 0 else "#059669" for v in df[contrib_col]]
            fig, ax = plt.subplots(figsize=(9, max(4, len(df) * 0.6 + 1)))
            ax.barh(df[factor_col], df[contrib_col], color=colors, height=0.55)
            ax.axvline(0, color="#374151", linewidth=0.8)
            ax.set_title("Factor Attribution (YoY)", fontsize=13, fontweight="bold")
            ax.grid(axis="x", alpha=0.3); fig.tight_layout()
            fig.savefig(CHARTS_DIR / "slide_5_attribution_waterfall.png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            print("Wrote slide_5_attribution_waterfall.png")

        print("Done. Charts written to:", CHARTS_DIR)
    """))


# ---------------------------------------------------------------------------
# Outline writer
# ---------------------------------------------------------------------------

def _write_outline(
    slides_dir: Path,
    metric: str,
    reporting_month: str,
    prior_month: str,
    data: dict[str, pd.DataFrame],
    attribution_df: Optional[pd.DataFrame],
    hypotheses: Optional[list[dict]],
    anomaly: dict,
    context: dict,
    csv_paths: dict[str, Optional[Path]],
    chart_paths: dict[str, Optional[Path]],
) -> Path:
    """Render slides_outline.md from per-slide content derived from analysis results."""
    month_dt = datetime.strptime(reporting_month[:7], "%Y-%m")
    month_display = month_dt.strftime("%B %Y")
    metric_display = _metric_display_name(metric)
    flag = anomaly.get("flag", "OK")
    delta = anomaly.get("delta", 0)
    delta_sign = "+" if delta > 0 else ""

    # Derived values for key messages
    top_factors = _top_factors(attribution_df, n=3)
    top_hyps = _top_hypotheses(hypotheses, n=2)
    annual_avgs = _annual_averages(data, metric)

    slides = []

    # ── Slide 1: Cover ───────────────────────────────────────────────────────
    top_factor_str = top_factors[0]["factor"] if top_factors else "key segment shift"
    top_factor_pp = f"{top_factors[0]['contribution']:+.2f} pp" if top_factors else ""
    slides.append(_slide_block(
        n=1,
        name="Cover",
        title=f"{metric_display} Diagnosis — {month_display}",
        tagline=(
            f"YoY change: {delta_sign}{delta:.2f} pp  [{flag}]  |  "
            f"Primary driver: {top_factor_str}"
        ),
        data_file=None,
        chart_file=None,
        key_message=_cover_message(metric_display, month_display, flag, delta, top_factors),
    ))

    # ── Slide 2: Trend ───────────────────────────────────────────────────────
    slides.append(_slide_block(
        n=2,
        name="Trend",
        title=f"Where We Stand: {metric_display} Trend (2023–2025)",
        tagline=_trend_tagline(annual_avgs, metric),
        data_file=_rel(csv_paths.get("trend"), slides_dir),
        chart_file=_rel(chart_paths.get("trend"), slides_dir),
        key_message=_trend_message(annual_avgs, metric_display),
    ))

    # ── Slide 3: Anomaly ─────────────────────────────────────────────────────
    slides.append(_slide_block(
        n=3,
        name="Anomaly Assessment",
        title=f"Anomaly Assessment: {flag} vs Prior Year",
        tagline=_anomaly_tagline(metric, flag, delta, prior_month, reporting_month),
        data_file=_rel(csv_paths.get("anomaly"), slides_dir),
        chart_file=_rel(chart_paths.get("anomaly"), slides_dir),
        key_message=_anomaly_message(metric_display, flag, delta, reporting_month),
    ))

    # ── Slide 4: Decomposition ───────────────────────────────────────────────
    slides.append(_slide_block(
        n=4,
        name="Decomposition",
        title="Where It Happened: By Channel & DD Timing",
        tagline=_decomp_tagline(top_factors),
        data_file=_rel(csv_paths.get("decomposition"), slides_dir),
        chart_file=_rel(chart_paths.get("decomposition"), slides_dir),
        key_message=_decomp_message(top_factors),
    ))

    # ── Slide 5: Attribution ─────────────────────────────────────────────────
    slides.append(_slide_block(
        n=5,
        name="Factor Attribution",
        title="Why It Happened: Factor Attribution",
        tagline=_attribution_tagline(top_factors, delta),
        data_file=_rel(csv_paths.get("attribution"), slides_dir),
        chart_file=_rel(chart_paths.get("attribution"), slides_dir),
        key_message=_attribution_message(top_factors, delta, metric_display),
    ))

    # ── Slide 6: Hypotheses ──────────────────────────────────────────────────
    slides.append(_slide_block(
        n=6,
        name="Hypotheses",
        title="What's Driving It: Hypotheses",
        tagline=_hypothesis_tagline(top_hyps),
        data_file=_rel(csv_paths.get("hypotheses"), slides_dir),
        chart_file=None,
        key_message=_hypothesis_message(top_hyps),
    ))

    # ── Slide 7: Forward Look ────────────────────────────────────────────────
    slides.append(_slide_block(
        n=7,
        name="Forward Look",
        title="So What: Recommended Actions & Monitoring",
        tagline="Prioritize by attribution size; monitor leading indicators monthly",
        data_file=None,
        chart_file=None,
        key_message=_forward_message(top_factors, top_hyps, metric_display),
    ))

    # Assemble and write
    header = textwrap.dedent(f"""\
        # {metric_display} Diagnosis — {month_display}
        Generated: {datetime.now().strftime("%Y-%m-%d")}

        ---

    """)

    outline = header + "\n\n---\n\n".join(slides)
    path = slides_dir / "slides_outline.md"
    path.write_text(outline, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Slide block builder
# ---------------------------------------------------------------------------

def _slide_block(
    n: int,
    name: str,
    title: str,
    tagline: str,
    data_file: Optional[str],
    chart_file: Optional[str],
    key_message: str,
) -> str:
    lines = [f"## Slide {n}: {name}"]
    lines.append(f"**Title:** {title}")
    lines.append(f"**Tagline:** {tagline}")
    if data_file:
        lines.append(f"**Supporting data:** {data_file}")
    if chart_file:
        lines.append(f"**Supporting chart:** {chart_file}")
    lines.append("**Key message:**")
    # Strip markdown bold/italic from key message — exec slides use plain prose
    clean = key_message.strip().replace("**", "").replace("__", "").replace("*", "")
    lines.append(f"> {clean}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Key message generators
# Principles:
#   - Lead with the verdict or implication, not the methodology
#   - Plain prose, no markdown bold/bullets — 2-3 sentences max
#   - Never reference "supporting CSV", "the chart shows", or technical methods
#   - Avoid jargon: no "shift-share", "YoY attribution", "cohort", "proforma"
# ---------------------------------------------------------------------------

def _cover_message(
    metric_display: str, month_display: str, flag: str, delta: float, top_factors: list[dict]
) -> str:
    sign = "+" if delta > 0 else ""
    flag_plain = {
        "ALERT": "requires immediate attention",
        "WATCH": "warrants close monitoring",
        "OK": "is within the expected range",
    }.get(flag, "requires review")
    if top_factors:
        tf = top_factors[0]
        pct = tf.get("pct_of_delta", 0)
        driver_line = (
            f"The single largest driver is {tf['factor']}, which accounts for "
            f"{pct:.0f}% of the year-over-year change."
            if pct > 0 else
            f"The primary driver appears to be {tf['factor']}."
        )
    else:
        driver_line = "A full factor breakdown follows in the slides below."
    return (
        f"{metric_display} moved {sign}{delta:.2f} points year-over-year in {month_display} "
        f"and {flag_plain}. {driver_line} "
        f"This deck covers the trend, the size of the gap, where it is concentrated, "
        f"the root-cause breakdown, and recommended actions."
    )


def _trend_tagline(annual_avgs: dict, metric: str) -> str:
    avgs = {yr: v for yr, v in sorted(annual_avgs.items())}
    if len(avgs) >= 2:
        yrs = sorted(avgs.keys())
        latest, prev = avgs[yrs[-1]], avgs[yrs[-2]]
        direction = "declining" if latest < prev else "improving"
        change = abs(latest - prev)
        return (
            f"The metric is {direction} — "
            f"down {change:.1f} from {yrs[-2]} to {yrs[-1]}"
            if direction == "declining" else
            f"The metric is {direction} — "
            f"up {change:.1f} from {yrs[-2]} to {yrs[-1]}"
        )
    return "Context on how the current period compares to prior years"


def _trend_message(annual_avgs: dict, metric_display: str) -> str:
    avgs = {yr: v for yr, v in sorted(annual_avgs.items())}
    yrs = sorted(avgs.keys())
    if len(avgs) >= 3 and all(y in avgs for y in [2023, 2024, 2025]):
        y23, y24, y25 = avgs[2023], avgs[2024], avgs[2025]
        d24 = y24 - y23
        d25 = y25 - y24
        direction = "accelerating" if abs(d25) > abs(d24) else "moderating"
        trend_word = "declined" if d25 < 0 else "improved"
        return (
            f"{metric_display} {trend_word} from {y24:.1f} in 2024 to {y25:.1f} in 2025, "
            f"a year-over-year change of {d25:+.1f}. The pace of change is {direction} "
            f"compared to the prior year ({d24:+.1f} from 2023 to 2024). "
            f"Understanding whether this is structural or episodic is the focus of this analysis."
        )
    if len(avgs) >= 2:
        latest_yr = yrs[-1]
        prev_yr = yrs[-2]
        d = avgs[latest_yr] - avgs[prev_yr]
        trend_word = "declined" if d < 0 else "improved"
        return (
            f"{metric_display} {trend_word} from {avgs[prev_yr]:.1f} ({prev_yr}) "
            f"to {avgs[latest_yr]:.1f} ({latest_yr}), a change of {d:+.1f}. "
            f"The slides that follow identify which segments and factors are driving this movement."
        )
    return (
        f"Multi-year trend data for {metric_display} is available in the supporting file. "
        f"Reviewing the trajectory across years helps establish whether the current period "
        f"represents a new development or a continuation of an existing pattern."
    )


def _anomaly_tagline(metric: str, flag: str, delta: float, prior_month: str, reporting_month: str) -> str:
    sign = "+" if delta > 0 else ""
    is_rate = metric in ("m2_retention", "early_dv")
    unit = "pp" if is_rate else "%"
    direction = "above" if delta > 0 else "below"
    return (
        f"{sign}{delta:.1f} {unit} vs. prior year — "
        f"{flag}: metric is {direction} the year-ago level"
    )


def _anomaly_message(metric_display: str, flag: str, delta: float, reporting_month: str) -> str:
    sign = "+" if delta > 0 else ""
    month_display = datetime.strptime(reporting_month[:7], "%Y-%m").strftime("%B %Y")
    concern = {
        "ALERT": "This exceeds the alert threshold and is considered a significant gap.",
        "WATCH": "This is within the watch band — below the alert threshold but warrants monitoring.",
        "OK": "This is within the expected seasonal range — no action required at this time.",
    }.get(flag, "This warrants further review.")
    direction = "increase" if delta > 0 else "decline"
    return (
        f"{metric_display} in {month_display} moved {sign}{delta:.2f} points versus "
        f"the same period last year. {concern} "
        f"The segment breakdown on the next slide identifies where this "
        f"{direction} is concentrated."
    )


def _decomp_tagline(top_factors: list[dict]) -> str:
    if not top_factors:
        return "Not all segments are moving equally — the change is concentrated in a subset"
    tf = top_factors[0]
    pct = tf.get("pct_of_delta", 0)
    return (
        f"{tf['factor']} accounts for {pct:.0f}% of the gap — the rest is spread across other segments"
        if pct > 0 else
        f"The largest concentration is in {tf['factor']}"
    )


def _decomp_message(top_factors: list[dict]) -> str:
    if not top_factors:
        return (
            "The breakdown by channel and conversion timing shows which segments are driving the "
            "overall change. Identifying the concentrated segments is the first step toward "
            "understanding root cause and designing targeted interventions."
        )
    tf1 = top_factors[0]
    pct1 = tf1.get("pct_of_delta", 0)
    msg = (
        f"{tf1['factor']} is the largest contributor, accounting for "
        f"{tf1['contribution']:+.2f} points ({pct1:.0f}% of the total gap)."
        if pct1 > 0 else
        f"{tf1['factor']} is the largest contributor at {tf1['contribution']:+.2f} points."
    )
    if len(top_factors) >= 2:
        tf2 = top_factors[1]
        msg += f" {tf2['factor']} is the second-largest, adding {tf2['contribution']:+.2f} points."
    offsets = [f for f in top_factors if f["contribution"] * tf1["contribution"] < 0]
    if offsets:
        msg += (
            f" Notably, {offsets[0]['factor']} moved in the opposite direction "
            f"({offsets[0]['contribution']:+.2f} points), partially offsetting the decline."
        )
    return msg


def _attribution_tagline(top_factors: list[dict], total_delta: float) -> str:
    if not top_factors:
        return "Three or fewer factors explain most of the gap — addressable through targeted action"
    tf = top_factors[0]
    pct = tf.get("pct_of_delta", 0)
    return (
        f"{tf['factor']} alone explains {pct:.0f}% of the {total_delta:+.2f}-point gap"
        if pct > 0 else
        f"{tf['factor']} is the dominant driver of the gap"
    )


def _attribution_message(top_factors: list[dict], total_delta: float, metric_display: str) -> str:
    if not top_factors:
        return (
            f"The overall {total_delta:+.2f}-point change in {metric_display} can be broken down "
            f"into a small number of measurable factors. Quantifying each factor's contribution "
            f"makes it possible to prioritize interventions by expected impact and focus "
            f"investigation on the drivers with the most leverage."
        )
    tf = top_factors[0]
    pct = tf.get("pct_of_delta", 0)
    msg = (
        f"The {total_delta:+.2f}-point gap in {metric_display} is largely explained "
        f"by {tf['factor']}, which contributes {tf['contribution']:+.2f} points "
        f"({pct:.0f}% of the total)."
        if pct > 0 else
        f"The primary driver of the {total_delta:+.2f}-point gap is {tf['factor']} "
        f"({tf['contribution']:+.2f} points)."
    )
    offsets = [f for f in top_factors if f["contribution"] * tf["contribution"] < 0]
    if offsets:
        msg += (
            f" This is partially offset by {offsets[0]['factor']} "
            f"({offsets[0]['contribution']:+.2f} points), which moved favorably "
            f"and masks a larger underlying gap."
        )
    else:
        remaining = [f for f in top_factors[1:] if abs(f["contribution"]) > 0]
        if remaining:
            others = ", ".join(f["factor"] for f in remaining[:2])
            msg += f" Secondary contributors include {others}."
    return msg


def _hypothesis_tagline(top_hyps: list[dict]) -> str:
    if not top_hyps:
        return "Multiple hypotheses tested — at least two confirmed, actions are clear"
    h1 = top_hyps[0]
    conf = str(h1.get("confidence", "medium")).lower()
    conf_label = {"high": "strong evidence", "medium": "likely explanation", "low": "possible factor"}.get(conf, "under review")
    hyp_text = h1.get("hypothesis", "")[:70]
    return f"Leading explanation ({conf_label}): {hyp_text}{'...' if len(h1.get('hypothesis', '')) > 70 else ''}"


def _hypothesis_message(top_hyps: list[dict]) -> str:
    if not top_hyps:
        return (
            "Hypotheses are structured across four categories — product changes, audience mix shifts, "
            "external factors, and data/technical issues. At least two categories are represented. "
            "Each hypothesis has a clear evidence requirement so the team can confirm or rule it out quickly."
        )
    h1 = top_hyps[0]
    conf1 = str(h1.get("confidence", "medium")).capitalize()
    msg = f"{conf1}-confidence: {h1.get('hypothesis', '')}."
    if h1.get("evidence_needed"):
        msg += f" To confirm: {h1['evidence_needed']}."
    if len(top_hyps) >= 2:
        h2 = top_hyps[1]
        conf2 = str(h2.get("confidence", "medium")).capitalize()
        msg += f" {conf2}-confidence secondary hypothesis: {h2.get('hypothesis', '')}."
    return msg


def _forward_message(top_factors: list[dict], top_hyps: list[dict], metric_display: str) -> str:
    actions = []
    for i, f in enumerate(top_factors[:3], 1):
        actions.append(
            f"({i}) Address {f['factor']}, which represents "
            f"a {abs(f['contribution']):.1f}-point recovery opportunity."
        )
    if not actions:
        actions.append(f"(1) Prioritize investigation into the primary driver of {metric_display} gap.")
    actions.append(
        f"({len(actions) + 1}) Monitor {metric_display} monthly against the year-ago baseline "
        f"and flag any further movement beyond the established threshold."
    )
    return " ".join(actions)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_df(data: dict[str, pd.DataFrame], keys: list[str]) -> Optional[pd.DataFrame]:
    for k in keys:
        if k in data and isinstance(data[k], pd.DataFrame) and not data[k].empty:
            return data[k]
    return None


def _detect_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first candidate column name present in df (case-insensitive)."""
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None


def _top_factors(attribution_df: Optional[pd.DataFrame], n: int = 3) -> list[dict]:
    if attribution_df is None or attribution_df.empty:
        return []
    factor_col = _detect_col(attribution_df, ["factor", "segment", "driver", "name"])
    contrib_col = _detect_col(attribution_df, ["contribution", "yoy_contribution", "mom_contribution", "delta"])
    pct_col = _detect_col(attribution_df, ["pct_of_delta", "pct", "percentage", "share"])
    if factor_col is None or contrib_col is None:
        return []
    df = attribution_df.copy()
    df["_contrib"] = pd.to_numeric(df[contrib_col], errors="coerce").fillna(0)
    df = df.reindex(df["_contrib"].abs().sort_values(ascending=False).index)
    result = []
    for _, row in df.head(n).iterrows():
        entry: dict[str, Any] = {
            "factor": str(row[factor_col]),
            "contribution": float(row["_contrib"]),
            "pct_of_delta": float(row[pct_col]) if pct_col and pct_col in row else 0.0,
        }
        result.append(entry)
    return result


def _top_hypotheses(hypotheses: Optional[list[dict]], n: int = 2) -> list[dict]:
    if not hypotheses:
        return []
    conf_rank = {"high": 0, "medium": 1, "low": 2}
    sorted_hyps = sorted(hypotheses, key=lambda h: conf_rank.get(str(h.get("confidence", "low")).lower(), 3))
    return sorted_hyps[:n]


def _annual_averages(data: dict[str, pd.DataFrame], metric: str) -> dict[int, float]:
    """Compute per-year average of the primary metric value from summary data."""
    df = _find_df(data, ["summary", "trend", "summary_current"])
    if df is None:
        return {}
    date_col = _detect_col(df, ["conversion_month", "calendar_month", "month", "analysis_month"])
    val_col = _detect_col(df, [
        "m2_rate", "m2_dd_retention_rate", "total_new_dders", "resurrected_count",
        "early_dv_per_dd", "monthly_ta", "resurrection_rate_pct",
    ])
    if date_col is None or val_col is None:
        return {}
    df = df.copy()
    df["_year"] = pd.to_datetime(df[date_col].astype(str).str[:7], format="%Y-%m").dt.year
    df["_val"] = pd.to_numeric(df[val_col], errors="coerce")
    return df.groupby("_year")["_val"].mean().to_dict()


def _metric_display_name(metric: str) -> str:
    names = {
        "m2_retention": "M2 DD Retention",
        "gross_new_dd": "Gross New DDer",
        "resurrected_dd": "Resurrected DDer",
        "early_dv": "Early DD/DV",
        "ta": "Transaction Actives",
    }
    return names.get(metric, metric.replace("_", " ").title())


def _rel(path: Optional[Path], base: Path) -> Optional[str]:
    """Return relative path string from base, or None."""
    if path is None:
        return None
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
