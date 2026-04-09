<!-- CONTRACT_START
name: metric-diagnosis
description: >
  Diagnose a Growth Analytics metric for a given reporting month.
  Pulls live Snowflake data, detects anomalies, decomposes the metric by
  segment, quantifies each factor's contribution to the variance
  (shift-share / additive attribution), integrates user-supplied context
  (product launches, experiments, historical patterns), and brainstorms
  hypotheses with the user before generating a structured HTML report.
  For rate/retention metrics (m2_retention, early_dv), YoY change is the
  primary anchor for anomaly detection and variance decomposition;
  MoM is shown as supplementary context. For count metrics
  (gross_new_dd, resurrected_dd, ta), MoM remains the primary anchor.
inputs:
  - name: METRIC
    type: str
    source: user
    required: true
    values: [gross_new_dd, resurrected_dd, m2_retention, early_dv, ta]
  - name: REPORTING_MONTH
    type: str
    source: user
    required: true
    description: "First-of-month ISO date string, e.g. '2026-02-01'"
  - name: PRIOR_MONTH
    type: str
    source: user
    required: false
    description: "Defaults to one month before REPORTING_MONTH"
  - name: CONTEXT_FILE
    type: file
    source: user
    required: false
    description: "Path to a filled context_template.yaml for this period"
outputs:
  - path: outputs/metric_diagnosis_{{METRIC}}_{{REPORTING_MONTH}}.html
    type: html
  - path: outputs/slides/{{METRIC}}_{{REPORTING_MONTH}}/slides_outline.md
    type: markdown
    optional: true
    description: "Slide-by-slide skeleton with titles, taglines, and copy-paste key messages"
  - path: outputs/slides/{{METRIC}}_{{REPORTING_MONTH}}/data/*.csv
    type: csv
    optional: true
    description: "One CSV per data-backed slide"
  - path: outputs/slides/{{METRIC}}_{{REPORTING_MONTH}}/charts/*.png
    type: image
    optional: true
    description: "One PNG chart per visual slide (matplotlib)"
depends_on: []
knowledge_context:
  - agents/metric-diagnosis/reference.md
  - .cursor/rules/growth-analytics-context.mdc
  - .cursor/rules/global-context.mdc
pipeline_step: 1
CONTRACT_END -->

# Agent: Metric Diagnosis

## Purpose

Diagnose a single Growth Analytics metric for a given reporting period.
Produces a structured diagnosis that quantifies what changed, why it changed
(factor attribution), and what to investigate next — with user input before
finalizing the report.

---

## Inputs

- **{{METRIC}}**: One of `gross_new_dd`, `resurrected_dd`, `m2_retention`,
  `early_dv`, `ta`. The user may refer to these by their display names (e.g.
  "M2 retention", "gross new DDer", "early DV").
- **{{REPORTING_MONTH}}**: The month being diagnosed, in `'YYYY-MM-01'` format.
- **{{PRIOR_MONTH}}**: The comparison baseline. Defaults to one month prior.
- **{{CONTEXT_FILE}}**: Optional YAML file (`context/context_template.yaml`).
  If not provided, ask whether the user wants to fill one in or proceed without context.

---

## Workflow

### Step 1: Parse

Extract `METRIC`, `REPORTING_MONTH`, and `PRIOR_MONTH` from the user's message.

- Map display names to keys: "M2 retention" → `m2_retention`, "gross new DD" → `gross_new_dd`, etc.
- Derive `PRIOR_MONTH` if not given: `DATEADD('month', -1, REPORTING_MONTH)`.
- Load `{{CONTEXT_FILE}}` if provided; otherwise check for
  `context/chime_{YYYY_MM}.yaml` as a convention match.
- State clearly: "Diagnosing **{metric display name}** for **{REPORTING_MONTH}**
  vs **{PRIOR_MONTH}**."

### SQL Disclosure Rule (applies to every step)

**Always show the full SQL query in the chat conversation whenever a query is run.**
Display it in a fenced code block (` ```sql `) immediately before or after presenting the
results — never omit it from the conversation, even if it is also included in the final
HTML report. This applies to every query in Steps 2–4 and any ad-hoc follow-up queries.
The HTML report separately embeds all queries in collapsible `<details>` blocks per the
`html-metrics-sql-disclosure.mdc` rule, but the conversation display is required in
addition to — not instead of — the HTML disclosure.

### Step 2: Fetch — Current, Prior, YoY, and Goal Data

Using the Snowflake MCP tool, run **three queries in parallel** for the metric
(see `reference.md`, section matching the metric key):

1. **Summary query** — current period `{REPORTING_MONTH}` and prior period `{PRIOR_MONTH}`
2. **YoY summary query** — same reporting month one year prior
   (`YOY_MONTH = DATEADD('year', -1, REPORTING_MONTH)`) and the period before that
   (`YOY_PRIOR_MONTH = DATEADD('year', -1, PRIOR_MONTH)`)
3. **Goal lookup** — pull the goal for `{REPORTING_MONTH}` from
   `analytics_db.dbt_cloud_prod.growth_forecast_summary` (see knowledge base for
   forecast IDs) **or** from hardcoded targets in the knowledge base (e.g. M2 DD
   retention goals). See `growth_analytics.yaml` section 5b/5c for all goal sources.

**Goal column mapping by metric:**
| Metric | Goal source | Column / field |
|---|---|---|
| `ta` | forecast_id = 1768336378, dataset_type = 'scenario' | `actives` |
| `gross_new_dd` | forecast_id = 1769121646, dataset_type = 'scenario' | `new_dders` |
| `early_dd` | forecast_id = 1769121646, dataset_type = 'scenario' | `early_dders` |
| `late_dd` | forecast_id = 1769121646, dataset_type = 'scenario' | `late_dders` |
| `resurrected_dd` | forecast_id = 1769121646, dataset_type = 'scenario' | `reactive_current_dders` |
| `m2_retention` | hardcoded in knowledge base (growth_analytics.yaml §5c) | `m2_dd_retention_goals_2026` |
| `early_dv` | no goal available | — |

Present results in a single consolidated **scorecard table** that always includes the goal
column when a goal is available. If no goal exists for the metric, omit the goal columns
and note "No goal available for this metric":

```
| Period              | [Key metric]  | Goal      | vs Goal Δ | vs Goal % | MoM Δ    | YoY Δ    |
|---------------------|---------------|-----------|-----------|-----------|----------|----------|
| Prior   (YYYY-MM)   | xxx,xxx       | xxx,xxx   | +/-X,XXX  | XX%       |          |          |
| Current (YYYY-MM)   | xxx,xxx       | xxx,xxx   | +/-X,XXX  | XX%       | +/-X,XXX | +/-X,XXX |
| YoY Curr  (YYYY-MM) | xxx,xxx       | n/a       | —         | —         |          | +/-X,XXX |
```

The YoY comparison establishes the seasonal baseline and is **always required**,
not optional. It answers: "Is this a new problem or a recurring seasonal pattern?"

### Step 3: Anomaly Detection & Goal Attainment

**Primary anchor depends on metric type:**

| Metric type | Primary anchor | Secondary |
|---|---|---|
| `m2_retention`, `early_dv` (rate/ratio) | **YoY** | MoM as context |
| `gross_new_dd`, `resurrected_dd`, `ta` (counts) | **MoM** | YoY as context |

Apply the appropriate primary threshold (see `reference.md`) and flag:
- 🔴 **ALERT** — exceeds threshold; requires explanation in the report
- 🟡 **WATCH** — within 50%–100% of threshold; note but not urgent
- 🟢 **OK** — within normal range

Present the primary flag first, secondary flag second, then goal attainment:
```
[Rate/retention metrics]
YoY (PRIMARY): 🔴/🟡/🟢  [current vs same month last year]  Δ = X.Xpp
MoM (context): 🔴/🟡/🟢  [current vs prior month]           Δ = X.Xpp
vs Goal:       🔴/🟡/🟢  [current vs goal]                  Δ = X.Xpp / XX% of goal

[Count metrics]
MoM (PRIMARY): 🔴/🟡/🟢  [current vs prior month]           Δ = X,XXX / X%
YoY (context): 🔴/🟡/🟢  [current vs same month last year]  Δ = X,XXX / X%
vs Goal:       🔴/🟡/🟢  [current vs goal]                  Δ = X,XXX / XX% of goal
```

**Goal attainment flags** (when goal is available):
- 🔴 **BEHIND** — actual < 95% of goal
- 🟡 **AT RISK** — actual 95%–99% of goal
- 🟢 **ON TRACK** — actual ≥ 100% of goal
- ⚪ **NO GOAL** — no goal defined for this metric/period (skip this row)

If both primary and secondary are flagged in the same direction → **escalate severity**
(🟡+🟡 → 🔴; 🔴+🟡 → 🔴 with "double-confirmed").
If only MoM is flagged but YoY is OK for a rate metric → likely noise or calendar
effect; note explicitly before proceeding to decomposition.
If YoY is flagged but MoM is OK for a rate metric → gradual structural decline;
flag for monitoring even if it looks calm month-to-month.

State all three flag rows (YoY/MoM/Goal) clearly before moving to decomposition.

### Step 4: Decompose

Run the **Decomposition queries** for the metric (reference.md sections 1b–1c,
2b, 3b, 4b, 5b as applicable). Always run decomposition for **both** the primary
comparison pair and the YoY comparison pair.

**Required breakdowns per metric:**

| Metric | Decomposition dimensions |
|---|---|
| `gross_new_dd` | Early vs Late DD split; Early DD by channel (5 buckets); Gross New DDer by DD paytype (4 buckets) |
| `resurrected_dd` | By enrollment channel (5 buckets); By DD paytype (4 buckets) |
| `m2_retention` | By channel × early/late DD (cross-tab); By DD paytype (4 buckets) |
| `early_dv` | By channel (DV per DD and total DV); By DV paytype (Payroll DD DV / Non-Payroll DD DV / Non-DD DV) |
| `ta` | By quarter position; YoY comparison |

Present each breakdown as a table with **four columns of values**:
current period, prior period (MoM), YoY period (same month last year),
and the **YoY delta** as the primary change column (for rate metrics) or
the MoM delta as the primary change column (for count metrics).

### Step 5: Factor Attribution

Compute the variance decomposition in-session using the query results from
Steps 2–4. Apply the appropriate method for the metric type.

**Decomposition baseline by metric:**

| Metric | Primary decomposition baseline | Secondary |
|---|---|---|
| `m2_retention` | **YoY** — current vs same month last year | MoM shown separately |
| `early_dv` | **YoY** — current vs same month last year | MoM shown separately |
| `gross_new_dd` | **MoM** — current vs prior month | YoY shown separately |
| `resurrected_dd` | **MoM** — current vs prior month | YoY shown separately |
| `ta` | **MoM** (QoQ for goal tracking) | YoY shown separately |

For `m2_retention` and `early_dv`, the shift-share / numerator-denominator
decomposition uses the **YoY period** (`YOY_MONTH`) as the `prior` baseline —
not `PRIOR_MONTH`. The MoM decomposition can be computed in addition but is
presented as secondary context, not as the headline attribution.

**Count metrics** (`gross_new_dd`, `resurrected_dd`) — primary = MoM:

For each segment `i` (channel, early/late):
```
volume_effect_i = (current_enrollments_i − prior_enrollments_i) × prior_dd_rate_i
rate_effect_i   = current_enrollments_i × (current_dd_rate_i − prior_dd_rate_i)
```
Sum across segments to get total Early DD delta attribution.
For resurrected_dd (no rate component): each channel's delta is its direct contribution.

**Rate metrics** (`m2_retention`) — primary = YoY shift-share:
```
Baseline = YOY_MONTH (same reporting month, one year prior)
For each segment i:
  yoy_mix_effect_i  = (current_share_i − yoy_share_i) × yoy_rate_i
  yoy_rate_effect_i = current_share_i × (current_rate_i − yoy_rate_i)
```
After presenting YoY attribution, also show MoM attribution (using PRIOR_MONTH
as baseline) as a supplementary table to reveal recent-month momentum.

**Ratio metrics** (`early_dv`) — primary = YoY numerator/denominator split:
```
Baseline = YOY_MONTH
DV_change_effect = (DV_current − DV_yoy) / DD_yoy
DD_base_effect   = −DV_yoy × (DD_current − DD_yoy) / (DD_yoy × DD_current)
```

Present the **primary (YoY) attribution** as the headline waterfall table:
```
| Factor                          | YoY Contribution | % of YoY Δ |
|---------------------------------|-----------------|------------|
| Early DD Referral rate decline  | −X.XX pp         | XX%        |
| ...                             | ...              | ...        |
| Total YoY Δ                     | −X.XX pp         | 100%       |
```

Then present MoM attribution in a smaller secondary table labeled
"MoM attribution (context)".

Factors are sorted by absolute contribution, largest first.
The factor with the largest absolute YoY contribution is the **primary hypothesis driver**.

### Step 6: Context Integration

If `{{CONTEXT_FILE}}` is provided, read the relevant metric's context block and:

1. **Map context items to hypothesis categories:**
   - `product_launches` → Product Changes hypotheses
   - `experiments` → Product Changes hypotheses (with experiment direction noted)
   - `policy_changes` → Product Changes hypotheses; these are rule/policy changes
     (e.g. eligibility rules, fraud controls, bonus payout conditions) that may
     directly explain segment-level rate shifts — treat with **high confidence**
     when the policy date falls within the cohort period
   - `historical_notes` → External Factors hypotheses
   - `known_data_issues` → Technical Issues hypotheses

2. **Connect attribution to context:** If a factor from Step 5 is large AND a
   context item explains it, promote that combination as a **confirmed hypothesis
   candidate** with high confidence. For `policy_changes`, if the policy date
   falls within the cohort window for the reporting month, explicitly note:
   "This policy change is likely the primary driver of the observed rate shift
   in this segment — the magnitude and segment specificity align."

3. **Flag unexplained large factors:** If a factor contributes > 20% of variance
   and no context item explains it, flag it as **needs investigation**.

4. **Cross-reference YoY with historical notes:** If `historical_notes` describes
   recurring patterns (e.g. fraud spikes in specific months), check whether the
   YoY comparison shows the same pattern a year prior. If it does, confirm as a
   **known recurring issue**. If the YoY comparator is clean, the current period
   is anomalous.

### Step 7: Hypothesis Brainstorm (Pause — Wait for User)

Present the following structured output and **wait for user input** before
writing the report.

```
## What we see
[3-5 bullet observations from Steps 3–5, most impactful first]

## Proposed hypotheses
| # | Category | Hypothesis | Factor contribution | Source |
|---|---|---|---|---|
| H1 | [category] | [falsifiable claim] | [X% of delta] | [attribution / context] |
| H2 | ... | ... | ... | ... |
| H3 | ... | ... | ... | ... |

## Category coverage check
Product Changes: [yes/no]  |  Technical Issues: [yes/no]  |  External Factors: [yes/no]  |  Mix Shift: [yes/no]
(at least 2 categories must be represented — add one if only 1 category present)

## Questions before I write the report
1. Does this match what you're seeing operationally?
2. Any hypotheses to add, adjust, or rule out?
3. Any additional context (product changes, data issues) not in the context file?
```

Use the 4-category framework from `agents/hypothesis.md`:
- **Product Changes** — features, UX, A/B tests, pricing
- **Technical Issues** — bugs, data pipeline, instrumentation
- **External Factors** — seasonality, macro, competitor
- **Mix Shift** — population composition, channel mix, cohort quality

Always include at least one Mix Shift hypothesis — it is the most commonly
missed category. Connect hypothesis priority to the attribution waterfall:
larger factors → higher-priority hypotheses.

### Step 8: Generate Report

After the user confirms or revises hypotheses, generate the HTML report
at `outputs/metric_diagnosis_{{METRIC}}_{{REPORTING_MONTH}}.html`.

The report must include (in order):
1. **Header** — metric name, reporting month, cohort month (for retention), date generated,
   and the **primary anomaly flag prominently displayed** (YoY for rate metrics, MoM for counts)
2. **Scorecard / flag row** — three badges side by side when goal is available:
   - For rate metrics: YoY flag (hero) | MoM flag (secondary) | vs Goal flag
   - For count metrics: MoM flag (hero) | YoY flag (secondary) | vs Goal flag
   - If no goal: only YoY and MoM badges; add a small ⚪ "No goal" label
   - The **vs Goal** badge must show: actual, goal, Δ, and % of goal attained
3. **Decomposition tables** — one table per breakdown dimension, with columns for:
   current, MoM prior, YoY prior, **goal** (when available), **YoY Δ** (primary for rate metrics), MoM Δ (secondary)
4. **Factor attribution section** — two waterfall tables side by side or stacked:
   - Primary: **YoY attribution** (for rate metrics) or **MoM attribution** (for counts)
   - Secondary: the other comparison, labeled as context
   - HTML/CSS bar chart showing each factor's absolute YoY contribution and % of YoY Δ
5. **Hypothesis table** — all confirmed hypotheses with category, YoY attribution %,
   evidence needed, and decision implication
6. **Context notes** — product launches, experiments, policy changes, historical notes
   that informed the diagnosis (sourced from `{{CONTEXT_FILE}}`)
7. **SQL disclosure** — every metric, decomposition, and attribution query used
   in a collapsible `<details>` block per the `html-metrics-sql-disclosure.mdc` rule

All SQL blocks must be the **full final SQL** with substituted date values
(not template placeholders).

---

### Step 9: Generate Slides Skeleton

After the HTML report is written, generate slides-ready output to
`outputs/slides/{{METRIC}}_{{REPORTING_MONTH}}/`.

#### Output structure

```
outputs/slides/{metric}_{YYYY_MM}/
  slides_outline.md       ← per-slide skeleton with titles, taglines, key messages
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
```

#### Standard 7-slide deck

| # | Slide | Title pattern | Chart | CSV |
|---|---|---|---|---|
| 1 | Cover | `{Metric Display Name} Diagnosis — {YYYY Mon}` | none | none |
| 2 | Trend | `Where We Stand: {Metric} Trend (2023–2025)` | line chart, 3 years | trend.csv |
| 3 | Anomaly | `Anomaly Assessment: {flag} vs Prior Year` | horizontal bar, current vs YoY | anomaly.csv |
| 4 | Decomposition | `Where It Happened: By Channel & DD Timing` | grouped horizontal bar | decomposition.csv |
| 5 | Attribution | `Why It Happened: Factor Attribution` | horizontal waterfall bar | attribution.csv |
| 6 | Hypotheses | `What's Driving It: Hypotheses` | none (table only) | hypotheses.csv |
| 7 | Forward Look | `So What: Recommended Actions & Monitoring` | none | none |

#### slides_outline.md format (one block per slide)

```markdown
## Slide N: [Name]
**Title:** [exact slide title]
**Tagline:** [one supporting subtitle line]
**Supporting data:** data/slide_N_*.csv
**Supporting chart:** charts/slide_N_*.png
**Key message:**
> [2–4 sentences, presentation-ready, copy-paste directly into slide body or notes]
```

#### Key message derivation rules

| Slide | Derive key message from |
|---|---|
| 1 Cover | Top factor from attribution waterfall + anomaly severity flag + one-line so-what |
| 2 Trend | Annual averages (2023/2024/2025) + direction keyword: accelerating / stable / recovering |
| 3 Anomaly | Primary flag (YoY for rates, MoM for counts) + delta in pp or % + calendar composition note if relevant |
| 4 Decomposition | Top 2 segments by absolute YoY delta; note any segment moving opposite direction |
| 5 Attribution | Largest factor name + pp contribution + % of total delta; contrast with any offsetting factors |
| 6 Hypotheses | Top 2 hypotheses by confidence; label confirmed vs needs-investigation; one investigative next step |
| 7 Forward Look | One action per top-3 attribution factor; one monitoring recommendation |

#### Executive-ready writing standard

All `slides_outline.md` content — titles, taglines, and key messages — must meet the following bar:

- **Taglines** lead with a verdict or finding, not a description of the slide. Example: *"Paid Early DD is the swing factor — down 11.6 pp YoY, explaining 74% of the gap"* not *"This slide shows the YoY change by segment."*
- **Key messages** are 2–3 sentences of clean prose. No markdown bold, no bullets, no references to "supporting CSV" or "the chart shows." The message must stand alone as copy that can be pasted directly into a slide body or speaker notes.
- **Numbers always anchor the message.** Every key message should contain at least one quantified finding.
- **Lead with the implication.** Start with what the audience should take away, then provide the evidence.
- In Cursor interactive mode, the agent MUST write custom key messages from the actual diagnosis findings rather than relying on the Python template generator. The template provides fallback copy for CLI mode only.

#### Execution in Cursor interactive mode

After generating the HTML (Step 8):
1. Use the Write tool to create `slides_outline.md` with all 7 slide blocks fully populated using exec-ready copy derived from the full analysis context.
2. Use the Write tool to create each CSV from data already in memory (Steps 2–5 results).
3. Generate PNG charts:
   - Attempt to run a short Python snippet via the Shell tool using `matplotlib`.
   - If `matplotlib` is unavailable, instead write `outputs/slides/{metric}_{month}/generate_charts.py`
     as a standalone script the user can run locally (`python generate_charts.py`).

Chart specifications:
- **Slide 2 (trend):** Line chart. X = cohort month. Y = metric rate or count. Three series: 2023 (grey), 2024 (blue), 2025 (orange). Horizontal dashed reference line at 2024 annual average. Annotate the annual avg value on the reference line.
- **Slide 3 (anomaly):** Horizontal bar chart. Two bars: current period vs YoY period. Annotate the delta (pp or %) between them. Color current bar red if ALERT, yellow if WATCH, green if OK.
- **Slide 4 (decomp):** Grouped horizontal bar chart. Y-axis = segments (channel × timing). Two bars per segment: 2024 (blue) and 2025 (orange). Sort by 2025 rate descending.
- **Slide 5 (attribution waterfall):** Horizontal diverging bar chart. Y-axis = factor names. Bars: red for negative contribution, green for positive. Black outlined bar for total. Sort by absolute contribution descending.

---

## Output Format

An HTML file at `outputs/metric_diagnosis_{{METRIC}}_{{REPORTING_MONTH}}.html` and
a slides folder at `outputs/slides/{{METRIC}}_{{REPORTING_MONTH}}/`.

For the standalone Python CLI, use:
```bash
python scripts/metric_diagnosis.py \
  --metric gross_new_dd \
  --reporting-month 2026-02-01 \
  --context context/chime_2026_02.yaml \
  --snowflake-config config/snowflake_config.yaml \
  --output-dir outputs/ \
  --slides
```

---

## Skills Used

- `agents/metric-diagnosis/reference.md` — SQL templates, decomposition logic,
  anomaly thresholds, and hypothesis checklists
- `agents/hypothesis.md` — 4-category hypothesis framework and falsifiability rules
- `.cursor/rules/growth-analytics-context.mdc` — metric definitions, channel
  mapping, maturity rules, GA team context
- `.cursor/rules/html-metrics-sql-disclosure.mdc` — HTML report SQL disclosure pattern

---

## Validation

Before presenting the hypothesis brainstorm (Step 7):

1. **Attribution check** — verify the sum of all factor contributions ≈ total
   metric delta (residual < 5%). If the residual is large, note it and explain.
2. **Category coverage** — ensure at least 2 of 4 hypothesis categories are
   represented. Always include at least one Mix Shift hypothesis.
3. **Context items used** — every non-empty context item must map to at least
   one hypothesis. If a context item is present but no hypothesis addresses it,
   add one.
4. **Maturity** — for Early DD (D30), confirm the query includes the maturity
   gate (`LAST_DAY(enrollment_date) < DATEADD('day', -30, CURRENT_DATE)`).
   If the reporting month is less than 30 days ago, flag the cohort as immature.
5. **Proforma columns** — confirm queries use `is_current_dd_proforma` and
   `current_dd_type_proforma`, not their non-proforma counterparts.

Before generating the report (Step 8):

6. **Hypothesis falsifiability** — each hypothesis must have a clear
   "if true, we should see..." and "if false, we should see..." condition.
7. **SQL completeness** — every number in the report traces to a specific SQL
   query that appears in a collapsible block on the page.
