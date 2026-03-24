"""
HTML Report Generator for the metric-diagnosis agent.

Produces a self-contained HTML file with:
  - Color-coded anomaly KPI header
  - Decomposition tables (current vs prior, with deltas)
  - Factor attribution waterfall (HTML/CSS bar chart + table)
  - Hypothesis table
  - Context notes
  - Collapsible SQL blocks (per html-metrics-sql-disclosure rule)

Usage (from metric_diagnosis.py):
    from scripts.report_generator import generate_report
    generate_report(metric, reporting_month, prior_month, data,
                    attribution_df, queries, anomaly, context, output_path)
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  color: #1f2937;
  background: #f3f4f6;
  line-height: 1.5;
}
.container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
h2 { font-size: 16px; font-weight: 600; margin: 0 0 12px; color: #374151; }
.meta { font-size: 12px; color: #6b7280; margin-bottom: 24px; }
.section {
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}

/* ── Anomaly flag ── */
.flag-alert  { border-left: 5px solid #dc2626; background: #fef2f2; }
.flag-watch  { border-left: 5px solid #d97706; background: #fffbeb; }
.flag-ok     { border-left: 5px solid #059669; background: #f0fdf4; }
.flag-warn   { border-left: 5px solid #9ca3af; background: #f9fafb; }

.kpi-row { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 12px; }
.kpi-card {
  flex: 1; min-width: 160px;
  padding: 16px 20px;
  border-radius: 6px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}
.kpi-card .value  { font-size: 28px; font-weight: 700; display: block; }
.kpi-card .label  { font-size: 12px; color: #6b7280; }
.kpi-card .delta  { font-size: 13px; font-weight: 600; margin-top: 4px; }
.delta-pos { color: #059669; }
.delta-neg { color: #dc2626; }
.delta-neu { color: #6b7280; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  background: #f9fafb;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid #e5e7eb;
  font-weight: 600;
  color: #374151;
}
tbody td { padding: 7px 12px; border-bottom: 1px solid #f3f4f6; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: #f9fafb; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.pos { color: #059669; }
.neg { color: #dc2626; }
.total-row { font-weight: 700; border-top: 2px solid #e5e7eb !important; }

/* ── Waterfall chart ── */
.waterfall-chart { margin: 16px 0 8px; }
.wf-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; min-height: 28px; }
.wf-label { width: 260px; font-size: 12px; color: #374151; flex-shrink: 0; text-align: right;
            padding-right: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-bar-wrap { flex: 1; display: flex; align-items: center; }
.wf-bar {
  height: 22px;
  border-radius: 3px;
  min-width: 2px;
  display: inline-block;
}
.wf-bar.pos { background: #059669; }
.wf-bar.neg { background: #dc2626; }
.wf-bar.total { background: #374151; }
.wf-val { font-size: 12px; margin-left: 6px; font-weight: 600; font-variant-numeric: tabular-nums; }

/* ── Hypothesis table ── */
.cat-product   { background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
.cat-mix       { background: #fce7f3; color: #9d174d; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
.cat-external  { background: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
.cat-technical { background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 12px; font-size: 11px; }

/* ── Context notes ── */
.context-item { margin-bottom: 6px; padding: 8px 12px; background: #f9fafb;
                border-radius: 4px; border-left: 3px solid #d97706; font-size: 13px; }

/* ── SQL disclosure ── */
details.sql-disclosure { margin: 12px 0 0; }
details.sql-disclosure summary {
  cursor: pointer; font-size: 12px; color: #6b7280;
  user-select: none; display: inline-block;
}
details.sql-disclosure summary:hover { color: #374151; }
details.sql-disclosure pre {
  margin: 8px 0 0; padding: 12px 16px;
  background: #1f2937; color: #d1fae5;
  border-radius: 6px; overflow-x: auto;
  font-size: 11px; line-height: 1.6;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

METRIC_LABELS = {
    "gross_new_dd": "Gross New DDer",
    "resurrected_dd": "Resurrected DDer",
    "m2_retention": "M2 DD Retention",
    "early_dv": "Early DD/DV",
    "ta": "Transaction Actives",
}


def _fmt(val: Any, is_rate: bool = False, is_currency: bool = False) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    v = float(val)
    if is_rate:
        return f"{v * 100:.2f}%"
    if is_currency:
        return f"${v:,.0f}"
    return f"{v:,.0f}"


def _delta_class(delta: float) -> str:
    if delta > 0:
        return "pos"
    if delta < 0:
        return "neg"
    return ""


def _flag_class(flag: str) -> str:
    return {
        "ALERT": "flag-alert",
        "WATCH": "flag-watch",
        "OK": "flag-ok",
    }.get(flag, "flag-warn")


def _flag_emoji(flag: str) -> str:
    return {"ALERT": "🔴 ALERT", "WATCH": "🟡 WATCH", "OK": "🟢 OK"}.get(flag, "⚪ WARN")


def _sql_block(label: str, sql_text: str) -> str:
    escaped = html.escape(sql_text.strip())
    return f"""
<details class="sql-disclosure">
  <summary>Show SQL — {html.escape(label)}</summary>
  <pre><code>{escaped}</code></pre>
</details>"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header_section(metric: str, r: str, p: str, cur_val: float, pri_val: float,
                    anomaly: dict, is_rate: bool, is_currency: bool) -> str:
    flag = anomaly.get("flag", "WARN")
    delta = anomaly.get("delta", 0)
    delta_pct = anomaly.get("delta_pct")
    threshold = anomaly.get("threshold")
    flag_css = _flag_class(flag)

    delta_sign = "+" if delta > 0 else ""
    if is_rate:
        delta_str = f"{delta_sign}{delta:.2f} pp"
    elif is_currency:
        delta_str = f"{delta_sign}${delta:,.0f}"
    else:
        delta_str = f"{delta_sign}{delta:,.0f}"

    delta_pct_str = f" ({delta_sign}{delta_pct:.1f}%)" if delta_pct is not None else ""
    delta_css = "delta-pos" if delta > 0 else ("delta-neg" if delta < 0 else "delta-neu")

    return f"""
<div class="section {flag_css}">
  <h2>{_flag_emoji(flag)} &nbsp; {html.escape(METRIC_LABELS.get(metric, metric))}</h2>
  <div class="meta">Reporting month: <strong>{r}</strong> &nbsp;|&nbsp;
    Prior month: <strong>{p}</strong> &nbsp;|&nbsp;
    Threshold: ±{threshold}{'pp' if is_rate else '%'}
  </div>
  <div class="kpi-row">
    <div class="kpi-card">
      <span class="value">{_fmt(cur_val, is_rate, is_currency)}</span>
      <span class="label">Current ({r[:7]})</span>
    </div>
    <div class="kpi-card">
      <span class="value">{_fmt(pri_val, is_rate, is_currency)}</span>
      <span class="label">Prior ({p[:7]})</span>
    </div>
    <div class="kpi-card">
      <span class="value {delta_css}">{delta_str}{delta_pct_str}</span>
      <span class="label">MoM Change</span>
    </div>
  </div>
</div>"""


def _df_table(df: pd.DataFrame, title: str, rate_cols: list[str] = None,
              currency_cols: list[str] = None, highlight_cols: list[str] = None) -> str:
    rate_cols = rate_cols or []
    currency_cols = currency_cols or []
    highlight_cols = highlight_cols or []

    rows_html = ""
    for _, row in df.iterrows():
        cells = ""
        for col in df.columns:
            val = row[col]
            is_rate = col in rate_cols
            is_cur = col in currency_cols
            is_num = isinstance(val, (int, float)) and not isinstance(val, bool)
            css = "num" if is_num else ""
            if col in highlight_cols and isinstance(val, (int, float)):
                css += f" {_delta_class(float(val))}"
            cells += f'<td class="{css}">{_fmt(val, is_rate, is_cur) if is_num else html.escape(str(val))}</td>'
        rows_html += f"<tr>{cells}</tr>"

    headers = "".join(
        f'<th class="{"num" if df[c].dtype.kind in "iuf" else ""}">'
        f'{html.escape(c.replace("_", " ").title())}</th>'
        for c in df.columns
    )
    return f"""
<div class="section">
  <h2>{html.escape(title)}</h2>
  <table>
    <thead><tr>{headers}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>"""


def _waterfall_section(attribution_df: pd.DataFrame, total_delta: float,
                       is_rate: bool, is_currency: bool, queries: list[dict]) -> str:
    """Build the factor attribution section with HTML/CSS waterfall bars."""
    if attribution_df is None or attribution_df.empty:
        return ""

    # Determine bar scale: max absolute contribution → 100% of bar width
    contrib_col = next(
        (c for c in ["contribution", "total_delta", "total_effect", "volume_effect"]
         if c in attribution_df.columns), None
    )
    if not contrib_col:
        return ""

    max_abs = attribution_df[contrib_col].abs().max()
    if max_abs == 0:
        max_abs = 1

    bars_html = ""
    for _, row in attribution_df.iterrows():
        segment = str(row.get("segment", row.get("channel_bucket", "?")))
        contrib = float(row.get(contrib_col, 0))
        pct = float(row.get("pct_of_total", 0))
        bar_w = min(int(abs(contrib) / max_abs * 100), 100)
        bar_css = "total" if "total" in segment.lower() else ("pos" if contrib >= 0 else "neg")
        sign = "+" if contrib > 0 else ""

        if is_rate:
            val_str = f"{sign}{contrib:.3f} pp ({sign}{pct:.1f}%)"
        elif is_currency:
            val_str = f"{sign}${contrib:,.0f} ({sign}{pct:.1f}%)"
        else:
            val_str = f"{sign}{contrib:,.0f} ({sign}{pct:.1f}%)"

        val_css = "pos" if contrib > 0 else ("neg" if contrib < 0 else "")
        bars_html += f"""
      <div class="wf-row">
        <span class="wf-label" title="{html.escape(segment)}">{html.escape(segment)}</span>
        <div class="wf-bar-wrap">
          <span class="wf-bar {bar_css}" style="width:{bar_w}%;"></span>
          <span class="wf-val {val_css}">{val_str}</span>
        </div>
      </div>"""

    # Summary table
    rows_html = ""
    for _, row in attribution_df.iterrows():
        segment = str(row.get("segment", row.get("channel_bucket", "?")))
        contrib = float(row.get(contrib_col, 0))
        pct = float(row.get("pct_of_total", 0))
        sign = "+" if contrib > 0 else ""
        is_total = "total" in segment.lower()
        tr_cls = "total-row" if is_total else ""
        dc = _delta_class(contrib)

        if is_rate:
            contrib_str = f"{sign}{contrib:.3f} pp"
        elif is_currency:
            contrib_str = f"{sign}${contrib:,.0f}"
        else:
            contrib_str = f"{sign}{contrib:,.0f}"

        rows_html += (
            f'<tr class="{tr_cls}">'
            f'<td>{html.escape(segment)}</td>'
            f'<td class="num {dc}">{contrib_str}</td>'
            f'<td class="num {dc}">{sign}{pct:.1f}%</td>'
            f"</tr>"
        )

    sql_blocks = "".join(
        _sql_block(q["name"], q["sql"]) for q in queries
    )

    return f"""
<div class="section">
  <h2>Factor Attribution</h2>
  <p style="font-size:12px;color:#6b7280;margin-bottom:12px;">
    How much of the total MoM change came from each factor.
    Sorted by absolute contribution, largest first.
  </p>
  <div class="waterfall-chart">{bars_html}
  </div>
  <table style="margin-top:16px;">
    <thead><tr>
      <th>Factor</th>
      <th class="num">Contribution</th>
      <th class="num">% of total Δ</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  {sql_blocks}
</div>"""


def _hypothesis_section(metric: str, context: dict, attribution_df: pd.DataFrame) -> str:
    """Build hypothesis table from context + attribution signals."""
    from scripts.hypothesis_builder import build_hypotheses  # local import
    hypotheses = build_hypotheses(metric, context, attribution_df)

    if not hypotheses:
        return ""

    CAT_CSS = {
        "Product Changes": "cat-product",
        "Mix Shift": "cat-mix",
        "External Factors": "cat-external",
        "Technical Issues": "cat-technical",
    }

    rows_html = ""
    for i, h in enumerate(hypotheses, 1):
        cat = h.get("category", "")
        cat_css = CAT_CSS.get(cat, "")
        rows_html += (
            f"<tr>"
            f"<td>H{i}</td>"
            f'<td><span class="{cat_css}">{html.escape(cat)}</span></td>'
            f"<td>{html.escape(h.get('hypothesis', ''))}</td>"
            f"<td>{html.escape(h.get('attribution', ''))}</td>"
            f"<td style='font-size:12px;color:#6b7280;'>{html.escape(h.get('evidence_needed', ''))}</td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <h2>Proposed Hypotheses</h2>
  <table>
    <thead><tr>
      <th>#</th><th>Category</th><th>Hypothesis</th>
      <th>Attribution</th><th>Evidence Needed</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p style="font-size:11px;color:#9ca3af;margin-top:12px;">
    * Categories: Product Changes | Mix Shift | External Factors | Technical Issues.
    Hypotheses are AI-drafted — review and edit before sharing.
  </p>
</div>"""


def _context_section(metric: str, context: dict) -> str:
    """Build context notes section from context YAML."""
    metric_ctx = context.get("metrics", {}).get(metric, {})
    global_notes = context.get("global_notes", [])

    items = []
    for key, label in [
        ("product_launches", "Product launch"),
        ("experiments", "Experiment"),
        ("historical_notes", "Historical note"),
        ("known_data_issues", "Data issue"),
    ]:
        for note in metric_ctx.get(key, []):
            if note and note.strip():
                items.append(f"<strong>{label}:</strong> {html.escape(note.strip())}")

    for note in global_notes:
        if note and note.strip():
            items.append(f"<strong>Global:</strong> {html.escape(note.strip())}")

    if not items:
        return ""

    notes_html = "".join(f'<div class="context-item">{n}</div>' for n in items)
    return f"""
<div class="section">
  <h2>Context</h2>
  {notes_html}
</div>"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(
    metric: str,
    reporting_month: str,
    prior_month: str,
    data: dict,
    attribution_df,
    queries: list[dict],
    anomaly: dict,
    context: dict,
    output_path: str,
) -> None:
    """Write the full HTML diagnosis report to output_path."""
    is_rate = metric in ("m2_retention",)
    is_currency = metric in ("early_dv",)

    # Extract summary values
    summary = (
        data.get("summary")
        or data.get("summary_current")
        or pd.DataFrame()
    )

    value_col_map = {
        "gross_new_dd": "total_new_dders",
        "resurrected_dd": "resurrected_dders",
        "m2_retention": "m2_retention_rate",
        "early_dv": "early_dv_per_dd",
        "ta": "monthly_ta",
    }
    vcol = value_col_map.get(metric, "")

    cur_val = pri_val = 0.0
    try:
        cur_rows = summary[summary.iloc[:, 0].astype(str).str.startswith(reporting_month[:7])]
        pri_rows = summary[summary.iloc[:, 0].astype(str).str.startswith(prior_month[:7])]
        if not cur_rows.empty and vcol in cur_rows.columns:
            cur_val = float(cur_rows.iloc[0][vcol])
        if not pri_rows.empty and vcol in pri_rows.columns:
            pri_val = float(pri_rows.iloc[0][vcol])
    except Exception:
        pass

    total_delta = cur_val - pri_val

    # Build sections
    sections = []

    # 1. Header / KPI
    sections.append(_header_section(
        metric, reporting_month, prior_month,
        cur_val, pri_val, anomaly, is_rate, is_currency,
    ))

    # 2. Decomposition tables (metric-specific)
    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and not df.empty and key != "attribution_raw":
            title = key.replace("_", " ").title()
            rate_cols = [c for c in df.columns if "rate" in c or "retention" in c]
            cur_cols = [c for c in df.columns if "dv" in c.lower() or "volume" in c.lower()]
            delta_cols = [c for c in df.columns if "delta" in c or "change" in c]
            matching_queries = [q for q in queries if q["name"] == key]
            section_html = _df_table(df, title, rate_cols=rate_cols, currency_cols=cur_cols,
                                     highlight_cols=delta_cols)
            if matching_queries:
                section_html = section_html[:-6]  # strip closing </div>
                section_html += _sql_block(key, matching_queries[0]["sql"]) + "\n</div>"
            sections.append(section_html)

    # 3. Attribution waterfall
    sections.append(_waterfall_section(
        attribution_df, total_delta, is_rate, is_currency,
        [q for q in queries if "attribution" in q["name"] or "segment" in q["name"]],
    ))

    # 4. Hypotheses
    try:
        sections.append(_hypothesis_section(metric, context, attribution_df))
    except ImportError:
        pass  # hypothesis_builder not present, skip

    # 5. Context notes
    sections.append(_context_section(metric, context))

    # Assemble HTML
    display_name = html.escape(METRIC_LABELS.get(metric, metric))
    body = "\n".join(s for s in sections if s)

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Metric Diagnosis: {display_name} | {reporting_month[:7]}</title>
  <style>{CSS}</style>
</head>
<body>
<div class="container">
  <h1>Metric Diagnosis: {display_name}</h1>
  <p class="meta">
    Generated {date.today().isoformat()} &nbsp;|&nbsp;
    {reporting_month[:7]} vs {prior_month[:7]}
  </p>
  {body}
</div>
</body>
</html>"""

    Path(output_path).write_text(html_out, encoding="utf-8")
