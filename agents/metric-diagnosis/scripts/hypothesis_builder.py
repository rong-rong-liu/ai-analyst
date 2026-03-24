"""
Hypothesis builder for the metric-diagnosis agent.

Generates draft hypotheses from context YAML + attribution results.
Each hypothesis follows the 4-category framework from agents/hypothesis.md:
  - Product Changes
  - Mix Shift
  - External Factors
  - Technical Issues
"""

from __future__ import annotations

from typing import Optional
import pandas as pd


# Default hypothesis templates per metric and category.
# Keys: (metric, category). Values: list of (hypothesis_template, evidence_template).
# {delta_dir} = 'decline' or 'increase'; {top_factor} = largest attribution factor.

_TEMPLATES: dict[tuple[str, str], list[tuple[str, str]]] = {

    # ── Gross New DDer ────────────────────────────────────────────────────────
    ("gross_new_dd", "Mix Shift"): [
        (
            "Enrollment volume {delta_dir}d — fewer/more members entering the top of funnel, "
            "reducing/increasing Early DD count regardless of conversion rate.",
            "Compare enrollments MoM by channel (volume effect in attribution).",
        ),
        (
            "Channel mix shifted (e.g. more Organic, fewer Paid) changing the share of "
            "high-conversion vs low-conversion channels.",
            "Check channel share shift in early-DD-by-channel table.",
        ),
    ],
    ("gross_new_dd", "Product Changes"): [
        (
            "Onboarding or DD setup flow change altered D30 conversion rate for one or more channels.",
            "Check rate_effect by channel in attribution; review product changelog.",
        ),
    ],
    ("gross_new_dd", "External Factors"): [
        (
            "Seasonality effect — Q1 tax season or holiday period driving enrollment or DD timing shifts.",
            "Compare same month YoY; check dd_timing distribution.",
        ),
    ],
    ("gross_new_dd", "Technical Issues"): [
        (
            "Data pipeline delay or incomplete data — the reporting month's Early DD count "
            "may not be fully refreshed.",
            "Check MAX(first_dd_dt) vs CURRENT_DATE; verify pipeline status.",
        ),
    ],

    # ── Resurrected DDer ──────────────────────────────────────────────────────
    ("resurrected_dd", "Product Changes"): [
        (
            "Win-back campaign, re-engagement push, or experiment drove resurrection rate up/down.",
            "Check context file for experiments and product launches.",
        ),
    ],
    ("resurrected_dd", "Mix Shift"): [
        (
            "Churned DDer pool size changed 2–3 months prior — larger/smaller churn "
            "creates more/fewer resurrection opportunities.",
            "Check churn count 2–3 months prior in base__user_month.",
        ),
    ],
    ("resurrected_dd", "External Factors"): [
        (
            "Seasonality — end-of-year or tax season triggers reactivation as members need "
            "payroll deposit functionality.",
            "Compare same month YoY.",
        ),
    ],
    ("resurrected_dd", "Technical Issues"): [
        (
            "'Winback' flag definition or proforma logic changed in base__user_month.",
            "Compare current_dd_type_proforma = 'Winback' count via both base__user_month "
            "and member_details to see if definitions diverge.",
        ),
    ],

    # ── M2 DD Retention ───────────────────────────────────────────────────────
    ("m2_retention", "Mix Shift"): [
        (
            "Cohort composition shifted — the Dec cohort (for Feb M2) had a higher share "
            "of Paid or Late DD members, who historically retain at lower rates.",
            "Check mix_effect by segment in attribution waterfall.",
        ),
        (
            "More Late DD members in the conversion cohort (Early DD retains better than Late DD).",
            "Check Early vs Late DD share in segment decomposition.",
        ),
    ],
    ("m2_retention", "Product Changes"): [
        (
            "Product launch (e.g. Chime Prime) changed what 'retained' means or "
            "altered engagement patterns for the cohort.",
            "Check product_launches in context; compare Prime vs non-Prime retention.",
        ),
        (
            "DD setup optimization experiment improved/degraded retention in treatment arm, "
            "and treatment cohort proportion changed.",
            "Check experiments in context file for cohort overlap.",
        ),
    ],
    ("m2_retention", "External Factors"): [
        (
            "Holiday enrollment cohort (Dec) historically has lower quality — "
            "higher volume but lower intent members leading to lower M2 retention.",
            "Compare Dec cohort M2 retention YoY; check historical_notes in context.",
        ),
    ],
    ("m2_retention", "Technical Issues"): [
        (
            "is_current_dd_proforma definition or base__user_month pipeline issue "
            "causing members to appear non-retained incorrectly.",
            "Cross-check retention rate against member_details current snapshot.",
        ),
    ],

    # ── Early DD/DV ───────────────────────────────────────────────────────────
    ("early_dv", "Mix Shift"): [
        (
            "Channel mix shifted toward lower-DV channels (e.g. more Organic vs Paid), "
            "pulling down the overall DV/DD average.",
            "Check DV per channel in attribution; compute DV/DD by channel.",
        ),
        (
            "DD count base grew but deposit volume didn't scale proportionally "
            "(DD base effect dominant).",
            "Check DD_base_effect vs DV_change_effect in attribution.",
        ),
    ],
    ("early_dv", "Product Changes"): [
        (
            "New product feature (e.g. credit card, new transfer option) changed "
            "deposit behavior in the first 35 days post-conversion.",
            "Check product_launches in context; compare DV by transaction type.",
        ),
    ],
    ("early_dv", "External Factors"): [
        (
            "Seasonality — year-start payroll volume inflates Jan cohort DV; "
            "other months may be lower.",
            "Compare same month YoY.",
        ),
    ],
    ("early_dv", "Technical Issues"): [
        (
            "ftr_transaction settled_amt includes reversals — if reversal volume changed, "
            "it may artificially depress/inflate DV.",
            "Check negative settled_amt counts; ensure acct_in_out = 'In' filter is applied.",
        ),
    ],

    # ── TA ────────────────────────────────────────────────────────────────────
    ("ta", "Mix Shift"): [
        (
            "Base composition shifted toward less-active member segments "
            "(e.g. more churned-risk members, fewer power users).",
            "Break TA by tenure bucket or product type if available.",
        ),
    ],
    ("ta", "Product Changes"): [
        (
            "Feature change (e.g. reduced debit card rewards, checkout friction) "
            "reduced purchase/transfer frequency.",
            "Check product_launches in context; compare by transaction type.",
        ),
    ],
    ("ta", "External Factors"): [
        (
            "Seasonality — tax refunds drive Q1 TA spike; summer months typically lower.",
            "Compare same quarter-end month YoY.",
        ),
    ],
    ("ta", "Technical Issues"): [
        (
            "is_transaction_active flag definition or threshold changed in base__user_month.",
            "Check base__user_month changelog or compare active count from ftr_transaction directly.",
        ),
    ],
}

CATEGORY_ORDER = ["Mix Shift", "Product Changes", "External Factors", "Technical Issues"]


def build_hypotheses(
    metric: str,
    context: dict,
    attribution_df,
) -> list[dict]:
    """Generate draft hypotheses from templates, context, and attribution signals.

    Returns a list of hypothesis dicts with keys:
        category, hypothesis, attribution, evidence_needed, source.
    """
    hypotheses = []
    metric_ctx = context.get("metrics", {}).get(metric, {})

    # Identify the top attribution factor (largest absolute contribution)
    top_factor = ""
    if attribution_df is not None and not attribution_df.empty:
        contrib_col = next(
            (c for c in ["contribution", "total_delta", "total_effect"]
             if c in attribution_df.columns), None
        )
        if contrib_col:
            top_row = attribution_df.loc[attribution_df[contrib_col].abs().idxmax()]
            top_factor = str(top_row.get("segment", top_row.iloc[0]))
            top_contrib = float(top_row.get(contrib_col, 0))
            delta_dir = "decline" if top_contrib < 0 else "increase"
        else:
            delta_dir = "change"
    else:
        delta_dir = "change"

    seen_categories = set()

    # 1. Context-informed hypotheses (highest priority)
    for item in metric_ctx.get("product_launches", []):
        if item and item.strip():
            hypotheses.append({
                "category": "Product Changes",
                "hypothesis": f"Product launch may have driven the metric {delta_dir}: {item.strip()}",
                "attribution": f"Top factor: {top_factor}" if top_factor else "—",
                "evidence_needed": "Check if launch timing aligns with the cohort period; "
                                   "compare treatment vs control if experiment.",
                "source": "context: product_launches",
            })
            seen_categories.add("Product Changes")

    for item in metric_ctx.get("experiments", []):
        if item and item.strip():
            hypotheses.append({
                "category": "Product Changes",
                "hypothesis": f"Experiment may explain the {delta_dir}: {item.strip()}",
                "attribution": f"Top factor: {top_factor}" if top_factor else "—",
                "evidence_needed": "Confirm cohort overlap with experiment period; "
                                   "check treatment effect direction vs observed delta.",
                "source": "context: experiments",
            })
            seen_categories.add("Product Changes")

    for item in metric_ctx.get("historical_notes", []):
        if item and item.strip():
            hypotheses.append({
                "category": "External Factors",
                "hypothesis": f"Historical pattern may explain the {delta_dir}: {item.strip()}",
                "attribution": "Historical / known seasonal effect",
                "evidence_needed": "Compare same period YoY to confirm recurring pattern.",
                "source": "context: historical_notes",
            })
            seen_categories.add("External Factors")

    for item in metric_ctx.get("known_data_issues", []):
        if item and item.strip():
            hypotheses.append({
                "category": "Technical Issues",
                "hypothesis": f"Known data issue may affect the metric: {item.strip()}",
                "attribution": "Data quality / pipeline",
                "evidence_needed": "Validate by cross-referencing with alternative data source.",
                "source": "context: known_data_issues",
            })
            seen_categories.add("Technical Issues")

    # 2. Attribution-driven hypotheses (if attribution is available)
    if attribution_df is not None and not attribution_df.empty:
        contrib_col = next(
            (c for c in ["contribution", "total_delta", "total_effect"]
             if c in attribution_df.columns), None
        )
        if contrib_col:
            large_factors = attribution_df[attribution_df[contrib_col].abs() > 0].head(3)
            for _, row in large_factors.iterrows():
                seg = str(row.get("segment", "Unknown"))
                contrib = float(row.get(contrib_col, 0))
                pct = float(row.get("pct_of_total", 0))
                direction = "decline" if contrib < 0 else "increase"
                if "total" in seg.lower():
                    continue
                hypothesis_text = (
                    f"'{seg}' accounts for {abs(pct):.0f}% of the total {direction}. "
                    f"This segment's contribution should be investigated first."
                )
                cat = "Mix Shift" if any(
                    kw in seg.lower() for kw in ["mix", "share", "channel", "timing"]
                ) else "Product Changes"
                hypotheses.append({
                    "category": cat,
                    "hypothesis": hypothesis_text,
                    "attribution": f"{'+' if contrib >= 0 else ''}{contrib:,.1f} ({'+' if pct >= 0 else ''}{pct:.0f}%)",
                    "evidence_needed": f"Investigate '{seg}' drivers in detail — "
                                       "compare volume and rate effects.",
                    "source": "attribution waterfall",
                })
                seen_categories.add(cat)

    # 3. Template fallbacks — ensure coverage of missing categories
    for cat in CATEGORY_ORDER:
        if cat not in seen_categories:
            templates = _TEMPLATES.get((metric, cat), [])
            for tmpl, evidence in templates[:1]:  # one per missing category
                hypotheses.append({
                    "category": cat,
                    "hypothesis": tmpl.format(
                        delta_dir=delta_dir, top_factor=top_factor
                    ),
                    "attribution": f"Top factor: {top_factor}" if top_factor else "—",
                    "evidence_needed": evidence,
                    "source": "template",
                })
            seen_categories.add(cat)

    # Ensure Mix Shift is always present (most commonly missed)
    if "Mix Shift" not in seen_categories:
        templates = _TEMPLATES.get((metric, "Mix Shift"), [])
        if templates:
            tmpl, evidence = templates[0]
            hypotheses.append({
                "category": "Mix Shift",
                "hypothesis": tmpl.format(delta_dir=delta_dir, top_factor=top_factor),
                "attribution": "—",
                "evidence_needed": evidence,
                "source": "template (mix shift guardrail)",
            })

    return hypotheses
