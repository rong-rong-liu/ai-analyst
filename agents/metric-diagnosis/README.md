# metric-diagnosis Agent

A self-contained, shareable agent for diagnosing Growth Analytics metrics
with automated anomaly detection, segment decomposition, factor attribution
(variance decomposition), context-aware hypothesis brainstorming, and
HTML report generation.

## Supported Metrics

| Key | Display Name | Decomposition |
|---|---|---|
| `gross_new_dd` | Gross New DDer | Early/Late split; Early DD by 5 channels |
| `resurrected_dd` | Resurrected DDer | By enrollment channel |
| `m2_retention` | M2 DD Retention | By channel × Early/Late DD (shift-share) |
| `early_dv` | Early DD/DV | By channel; numerator/denominator split |
| `ta` | Transaction Actives | MoM + YoY quarter-end comparison |

## Quick Start

### Interactive (Cursor)

Open Cursor and say:
> "Diagnose M2 retention for February 2026"

The agent runs the 8-step workflow in `agent.md` using the Snowflake MCP.

### CLI (Automated / Scheduled)

```bash
# First-time setup
pip install snowflake-connector-python pandas pyyaml scipy
cp config/snowflake_config.yaml.example config/snowflake_config.yaml
# Edit snowflake_config.yaml with your credentials

# Run a diagnosis
python scripts/metric_diagnosis.py \
  --metric gross_new_dd \
  --reporting-month 2026-02-01 \
  --context context/chime_2026_02.yaml \
  --output-dir outputs/
```

Output lands at `outputs/metric_diagnosis_gross_new_dd_2026-02-01.html`.

## Adding Context

Fill in `context/context_template.yaml` before each period analysis:

```yaml
reporting_month: "2026-02-01"
metrics:
  m2_retention:
    historical_notes:
      - "Dec 2025 cohort: holiday sign-up spike, historically lower quality"
    product_launches:
      - "2026-01-15: Chime Prime launched"
    experiments:
      - "EXP-1234: DD setup optimization, +2pp M2 retention in treatment"
```

Save as `context/chime_2026_02.yaml` (one file per period).

## Folder Structure

```
metric-diagnosis/
├── agent.md                   ← Main agent (8-step workflow)
├── reference.md               ← SQL templates, thresholds, hypothesis checklists
├── README.md
├── config/
│   └── snowflake_config.yaml.example
├── context/
│   └── context_template.yaml  ← Copy + fill per period
├── helpers/
│   ├── snowflake_connector.py ← Snowflake connection
│   ├── sql_helpers.py         ← Query validation helpers (copied)
│   ├── stats_helpers.py       ← Statistical tests (copied)
│   └── confidence_scoring.py  ← Confidence scoring (copied)
├── outputs/                   ← Generated HTML reports
└── scripts/
    ├── metric_diagnosis.py    ← CLI entrypoint
    ├── report_generator.py    ← HTML report builder
    └── hypothesis_builder.py  ← Draft hypothesis generator
```

## Report Contents

Each HTML report includes:
1. **Anomaly flag** (🔴/🟡/🟢) with current vs prior KPI cards
2. **Decomposition tables** — segment breakdown for both periods
3. **Factor attribution waterfall** — each factor's absolute + % contribution to the MoM delta
4. **Hypothesis table** — categorized (Product Changes | Mix Shift | External Factors | Technical Issues)
5. **Context notes** — product launches, experiments, historical patterns
6. **Collapsible SQL** — every query shown inline (per disclosure standard)

## Sharing with Your Team

This folder is self-contained. To share:
1. Copy the `metric-diagnosis/` folder
2. Each recipient fills in `config/snowflake_config.yaml` with their own credentials
3. Fill `context/context_template.yaml` for the period before running
4. Run CLI or use via Cursor
