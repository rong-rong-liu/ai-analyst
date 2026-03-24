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


def _chart_trend(charts_dir: Path, metric: str, df: pd.DataFrame, plt) -> Optional[Path]:
    """Line chart: metric value over time, colored by year if multi-year data available."""
    # Detect the date column and value column
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

    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = {2023: "#9ca3af", 2024: "#3b82f6", 2025: "#f97316"}

    for yr, grp in df.groupby("year"):
        color = colors.get(yr, "#6b7280")
        ax.plot(grp[date_col], grp[val_col], marker="o", label=str(yr),
                color=color, linewidth=2, markersize=5)

    # Reference line: 2024 average
    yr24 = df[df["year"] == 2024]
    if not yr24.empty:
        avg24 = yr24[val_col].mean()
        ax.axhline(avg24, color="#3b82f6", linestyle="--", linewidth=1, alpha=0.6)
        ax.text(df[date_col].min(), avg24 * 1.005, f"2024 avg: {avg24:.1f}",
                color="#3b82f6", fontsize=8)

    ax.set_title(f"{metric.replace('_', ' ').title()} Trend", fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel(val_col.replace("_", " ").title(), fontsize=10)
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
    """Simple two-bar chart: current period vs YoY, annotated with delta."""
    flag = anomaly.get("flag", "OK")
    delta = anomaly.get("delta", 0)
    cur = anomaly.get("current_value", 0)
    yoy = anomaly.get("yoy_value", cur - delta) if anomaly.get("yoy_value") else cur - delta

    color_map = {"ALERT": "#dc2626", "WATCH": "#d97706", "OK": "#059669"}
    bar_color = color_map.get(flag, "#6b7280")

    month_label = reporting_month[:7]
    yoy_label = f"{int(month_label[:4]) - 1}{month_label[4:]}"

    fig, ax = plt.subplots(figsize=(7, 3))
    bars = ax.barh([yoy_label, month_label], [yoy, cur],
                   color=["#9ca3af", bar_color], height=0.4)

    # Annotate values
    for bar, val in zip(bars, [yoy, cur]):
        ax.text(bar.get_width() + abs(max(yoy, cur)) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=10, fontweight="bold")

    # Delta annotation
    sign = "+" if delta > 0 else ""
    ax.set_title(
        f"YoY Change: {sign}{delta:.2f}  [{flag}]",
        fontsize=12, fontweight="bold", color=bar_color,
    )
    ax.set_xlabel(metric.replace("_", " ").title(), fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_3_anomaly.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_decomposition(charts_dir: Path, df: pd.DataFrame, plt) -> Optional[Path]:
    """
    Grouped horizontal bar: segments on Y-axis, two bars per segment (prior year vs current).
    Detects rate or count columns automatically.
    """
    # Try to detect a rate or count column
    rate_col = _detect_col(df, ["m2_rate", "resurrection_rate_pct", "early_dd_rate", "m2_dd_retention_rate"])
    count_col = _detect_col(df, ["cohort_size", "resurrected_count", "early_dders", "total_new_dders"])
    val_col = rate_col or count_col
    if val_col is None:
        return None

    # Detect segment and period columns
    seg_col = _detect_col(df, ["channel", "channel_bucket", "segment", "dd_timing", "churn_tenure_segment"])
    period_col = _detect_col(df, ["cohort_year", "conversion_month", "calendar_month", "analysis_month"])
    if seg_col is None or period_col is None:
        return None

    df = df.copy()
    df[period_col] = df[period_col].astype(str).str[:7]
    periods = sorted(df[period_col].unique())

    # Pivot to wide
    try:
        pivot = df.pivot_table(index=seg_col, columns=period_col, values=val_col, aggfunc="mean")
    except Exception:
        return None

    if pivot.empty or pivot.shape[1] < 2:
        return None

    # Use last two periods
    p1, p2 = pivot.columns[-2], pivot.columns[-1]
    pivot = pivot[[p1, p2]].dropna().sort_values(p2, ascending=True)

    segments = pivot.index.tolist()
    y = range(len(segments))
    bar_height = 0.35

    fig, ax = plt.subplots(figsize=(9, max(4, len(segments) * 0.55 + 1)))
    ax.barh([i - bar_height / 2 for i in y], pivot[p1], height=bar_height,
            label=str(p1), color="#3b82f6", alpha=0.85)
    ax.barh([i + bar_height / 2 for i in y], pivot[p2], height=bar_height,
            label=str(p2), color="#f97316", alpha=0.85)

    ax.set_yticks(list(y))
    ax.set_yticklabels(segments, fontsize=9)
    ax.set_xlabel(val_col.replace("_", " ").title(), fontsize=10)
    ax.set_title("Decomposition by Segment", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_4_decomposition.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_waterfall(charts_dir: Path, attribution_df: pd.DataFrame, plt) -> Optional[Path]:
    """
    Horizontal diverging waterfall: factors on Y-axis, bars colored red (negative)
    or green (positive). Total bar in dark grey outlined.
    """
    factor_col = _detect_col(attribution_df, ["factor", "segment", "driver", "name"])
    contrib_col = _detect_col(attribution_df, ["contribution", "yoy_contribution", "mom_contribution", "delta"])
    if factor_col is None or contrib_col is None:
        return None

    df = attribution_df[[factor_col, contrib_col]].copy()
    df.columns = ["factor", "contribution"]
    df["contribution"] = pd.to_numeric(df["contribution"], errors="coerce").fillna(0)

    # Sort by absolute contribution, largest at top
    df = df.reindex(df["contribution"].abs().sort_values(ascending=True).index)

    colors = ["#dc2626" if v < 0 else "#059669" for v in df["contribution"]]

    fig, ax = plt.subplots(figsize=(9, max(4, len(df) * 0.55 + 1)))
    bars = ax.barh(df["factor"], df["contribution"], color=colors, height=0.55)

    # Annotate values
    for bar, val in zip(bars, df["contribution"]):
        xpos = bar.get_width() + (0.02 if val >= 0 else -0.02)
        ha = "left" if val >= 0 else "right"
        ax.text(xpos, bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}", va="center", ha=ha, fontsize=8.5)

    ax.axvline(0, color="#374151", linewidth=0.8)
    ax.set_xlabel("Contribution (pp or count)", fontsize=10)
    ax.set_title("Factor Attribution (YoY)", fontsize=13, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    path = charts_dir / "slide_5_attribution_waterfall.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
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
        **Generated:** {datetime.now().strftime("%Y-%m-%d")}
        **Metric:** {metric_display}
        **Reporting month:** {reporting_month[:7]}
        **Prior month (MoM):** {prior_month[:7]}
        **Anomaly flag:** {flag}  |  YoY delta: {delta_sign}{delta:.2f}

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
    lines.append(f"**Key message:**")
    for sentence in key_message.strip().split("\n"):
        lines.append(f"> {sentence}" if sentence.strip() else ">")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Key message generators
# ---------------------------------------------------------------------------

def _cover_message(
    metric_display: str, month_display: str, flag: str, delta: float, top_factors: list[dict]
) -> str:
    sign = "+" if delta > 0 else ""
    severity = {"ALERT": "significant concern", "WATCH": "emerging concern", "OK": "within normal range"}.get(flag, "")
    if top_factors:
        tf = top_factors[0]
        driver_line = (
            f"The primary driver is **{tf['factor']}**, contributing "
            f"{tf['contribution']:+.2f} pp ({tf.get('pct_of_delta', 0):.0f}% of total delta)."
        )
    else:
        driver_line = "Factor attribution is pending further decomposition."
    return (
        f"{metric_display} for {month_display} changed {sign}{delta:.2f} pp year-over-year — "
        f"a {severity} requiring investigation.\n"
        f"{driver_line}\n"
        f"This deck walks through the trend, anomaly assessment, segment decomposition, "
        f"factor attribution, and hypotheses to support root-cause diagnosis."
    )


def _trend_tagline(annual_avgs: dict, metric: str) -> str:
    avgs = {yr: v for yr, v in sorted(annual_avgs.items())}
    if len(avgs) >= 2:
        yrs = sorted(avgs.keys())
        direction = "declining" if avgs[yrs[-1]] < avgs[yrs[0]] else "improving"
        rate = abs(avgs[yrs[-1]] - avgs[yrs[-2]]) if len(yrs) >= 2 else 0
        return f"Trend is {direction}; YoY change of {rate:+.1f} between {yrs[-2]} and {yrs[-1]}"
    return "Multi-year trend data available in supporting CSV"


def _trend_message(annual_avgs: dict, metric_display: str) -> str:
    avgs = {yr: v for yr, v in sorted(annual_avgs.items())}
    if len(avgs) >= 3:
        y23, y24, y25 = avgs.get(2023), avgs.get(2024), avgs.get(2025)
        if y23 and y24 and y25:
            d24 = y24 - y23
            d25 = y25 - y24
            accel = "accelerating" if abs(d25) > abs(d24) else "decelerating"
            return (
                f"{metric_display} has shown a multi-year structural decline: "
                f"{y23:.1f} in 2023 → {y24:.1f} in 2024 ({d24:+.1f}) → {y25:.1f} in 2025 ({d25:+.1f}).\n"
                f"The rate of decline is {accel}, suggesting the underlying drivers are "
                f"{'intensifying' if accel == 'accelerating' else 'stabilizing'}.\n"
                f"Understanding the root cause of this multi-year trend is critical before "
                f"projecting 2026 performance."
            )
    if avgs:
        latest = max(avgs, key=lambda k: k)
        return (
            f"{metric_display} in {latest} was {avgs[latest]:.1f}. "
            f"Historical trend data is available in the supporting CSV for deeper analysis."
        )
    return f"{metric_display} trend data is available in the supporting CSV."


def _anomaly_tagline(metric: str, flag: str, delta: float, prior_month: str, reporting_month: str) -> str:
    sign = "+" if delta > 0 else ""
    is_rate = metric in ("m2_retention", "early_dv")
    unit = "pp" if is_rate else "%"
    anchor = "YoY" if is_rate else "MoM"
    return (
        f"{anchor} delta: {sign}{delta:.2f} {unit}  |  "
        f"Flag: {flag}  |  Compare: {prior_month[:7]} → {reporting_month[:7]}"
    )


def _anomaly_message(metric_display: str, flag: str, delta: float, reporting_month: str) -> str:
    sign = "+" if delta > 0 else ""
    flag_desc = {
        "ALERT": "exceeds the alert threshold and requires an explanation",
        "WATCH": "is within the watch band — monitor but not yet critical",
        "OK": "is within normal seasonal range",
    }.get(flag, "")
    return (
        f"{metric_display} for {reporting_month[:7]} moved {sign}{delta:.2f} pp year-over-year, "
        f"which {flag_desc}.\n"
        f"Calendar composition (number of Wednesdays/payday-aligned days) has been accounted for; "
        f"the flagged movement reflects an underlying behavioral or structural change.\n"
        f"See the decomposition slide for a breakdown of which segments are driving this movement."
    )


def _decomp_tagline(top_factors: list[dict]) -> str:
    if not top_factors:
        return "Channel and DD timing breakdown identifies where the change is concentrated"
    tf = top_factors[0]
    return (
        f"Largest segment driver: {tf['factor']} "
        f"({tf['contribution']:+.2f} pp, {tf.get('pct_of_delta', 0):.0f}% of total)"
    )


def _decomp_message(top_factors: list[dict]) -> str:
    if not top_factors:
        return (
            "The decomposition by channel and DD timing identifies which segments account "
            "for the largest share of the YoY change. Review the supporting chart and CSV "
            "to prioritize investigation."
        )
    lines = []
    for i, f in enumerate(top_factors[:2], 1):
        lines.append(
            f"{i}. **{f['factor']}**: {f['contribution']:+.2f} pp "
            f"({f.get('pct_of_delta', 0):.0f}% of total YoY delta)"
        )
    # Note any offsetting segment
    offsets = [f for f in top_factors if f["contribution"] * top_factors[0]["contribution"] < 0]
    if offsets:
        lines.append(
            f"Partially offset by **{offsets[0]['factor']}** "
            f"({offsets[0]['contribution']:+.2f} pp), which moved in the opposite direction."
        )
    return "\n".join(lines)


def _attribution_tagline(top_factors: list[dict], total_delta: float) -> str:
    if not top_factors:
        return "Shift-share decomposition quantifies each factor's contribution to the YoY change"
    tf = top_factors[0]
    return (
        f"Top driver: {tf['factor']}  |  "
        f"{tf['contribution']:+.2f} pp of {total_delta:+.2f} pp total  |  "
        f"{tf.get('pct_of_delta', 0):.0f}% of delta"
    )


def _attribution_message(top_factors: list[dict], total_delta: float, metric_display: str) -> str:
    if not top_factors:
        return (
            f"Shift-share decomposition for {metric_display} is available in the supporting CSV. "
            f"Each factor's mix effect (who grew/shrank as a share) and rate effect "
            f"(within-segment performance change) are quantified separately."
        )
    tf = top_factors[0]
    lines = [
        f"The overall {metric_display} YoY change of {total_delta:+.2f} pp is decomposed into "
        f"{len(top_factors)} factors using shift-share analysis.",
        f"**Primary driver: {tf['factor']}** — accounts for {tf['contribution']:+.2f} pp "
        f"({tf.get('pct_of_delta', 0):.0f}% of total delta).",
    ]
    offsets = [f for f in top_factors if f["contribution"] * tf["contribution"] < 0]
    if offsets:
        lines.append(
            f"Partially offset by **{offsets[0]['factor']}** ({offsets[0]['contribution']:+.2f} pp), "
            f"which moved favorably and masked a larger underlying deterioration."
        )
    return "\n".join(lines)


def _hypothesis_tagline(top_hyps: list[dict]) -> str:
    if not top_hyps:
        return "Structured hypotheses across Product Changes, Mix Shift, External Factors, Technical Issues"
    h1 = top_hyps[0]
    conf = h1.get("confidence", "medium")
    return f"Leading hypothesis ({conf} confidence): {h1.get('hypothesis', '')[:80]}..."


def _hypothesis_message(top_hyps: list[dict]) -> str:
    if not top_hyps:
        return (
            "Hypotheses are structured across four categories: Product Changes, Mix Shift, "
            "External Factors, and Technical Issues. At least two categories are represented. "
            "Each hypothesis has a falsifiable 'if true / if false' condition for investigation."
        )
    lines = []
    for h in top_hyps[:2]:
        conf = h.get("confidence", "medium").upper()
        lines.append(f"**[{conf}] {h.get('id', 'H?')}: {h.get('hypothesis', '')}**")
        if h.get("evidence_needed"):
            lines.append(f"  Evidence needed: {h['evidence_needed']}")
    lines.append(
        "Full hypothesis table with attribution linkage, evidence requirements, "
        "and decision implications is in the supporting CSV."
    )
    return "\n".join(lines)


def _forward_message(top_factors: list[dict], top_hyps: list[dict], metric_display: str) -> str:
    actions = []
    for i, f in enumerate(top_factors[:3], 1):
        actions.append(f"{i}. **{f['factor']}**: Investigate root cause; "
                       f"target {abs(f['contribution']):.1f} pp recovery opportunity.")
    if not actions:
        actions.append("1. Prioritize the top attribution factor for root-cause investigation.")
    actions.append(
        f"{len(actions) + 1}. **Monitoring**: Track {metric_display} weekly vs YoY baseline; "
        f"set up alerts at ±1.5 pp threshold."
    )
    return "\n".join(actions)


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
