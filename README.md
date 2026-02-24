# AI Analyst

> [!IMPORTANT]
> **Note from Shane — February 22, 2026**
>
> This repo was last pushed to on February 20. Since then, the system has grown significantly through testing on more complex, real-world datasets. Everything below works, but the version we're running locally is substantially ahead of what's here. Major update coming in the next couple of days.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code Required](https://img.shields.io/badge/requires-Claude%20Code-blueviolet.svg)](https://claude.ai/code)

A complete AI analyst system powered by Claude Code. You ask a business question. Claude frames it, explores your data, finds the root cause, builds a story, and hands you a branded slide deck with speaker notes. The whole thing takes minutes, not days.

Connect your own data with `/connect-data` or use the included example datasets.

**17** specialized agents | **30** auto-applied skills | **14** slash commands | DAG-based parallel execution | PDF + HTML export

---

## Don't Know What to Do? Just Ask.

Claude knows the entire system — every agent, skill, command, and dataset. If you're stuck, ask it:

```
What can I do with this data?
What should I run to refresh the deck?
How do I connect my own CSV files?
Which agents handle root cause analysis?
Re-run just the chart maker and deck creator.
```

Claude will tell you the exact command. You don't need to memorize anything in this README. Think of it as a reference — Claude is the guide.

---

## Quick Start

**1. Install Claude Code** (requires a [Claude Pro subscription](https://claude.ai/pro))

```bash
npm install -g @anthropic-ai/claude-code
```

**2. Clone and set up**

```bash
git clone https://github.com/ai-analyst-lab/ai-analyst.git
cd ai-analyst
bash scripts/setup.sh
bash scripts/download-data.sh
```

**3. Start Claude Code**

```bash
claude
```

**4. Try it**

```
Why is our conversion rate declining?
```

Or go straight to the full pipeline:

```
/run-pipeline data_path=data/your_dataset/ question="Why is conversion dropping?"
```

For full setup (MotherDuck, MCP connections, troubleshooting): [setup/prerequisites.md](setup/prerequisites.md)

---

## Five Things You Can Do

### 1. Ask a quick question

```
What's our conversion rate by device?
```

Claude queries the data and returns an answer with a chart. Simple questions get answered in under 2 minutes without running the full pipeline.

### 2. Run a full analysis

```
/run-pipeline data_path=data/your_dataset/ question="What's driving the decline in conversion?"
```

The pipeline runs 17 agents across 4 phases: Frame the question, Analyze the data, Build the story, Create the deck. You get a validated analysis, branded charts, a narrative, and a slide deck with speaker notes. Exports to PDF and HTML.

### 3. Explore a dataset

```
/explore
```

Interactive data browsing without committing to a full analysis. Preview tables, check distributions, spot patterns, form hypotheses. Use `/data users` to inspect a specific table's schema.

### 4. Connect your own data

```
/connect-data
```

Guided wizard that walks you through connecting CSV files, local DuckDB, Postgres, BigQuery, or Snowflake. Auto-profiles your data, creates schema docs, and remembers your dataset context across sessions.

### 5. Make a single chart

```
Make a funnel chart of the checkout flow, highlighting the biggest drop-off step.
```

Claude generates a chart following Storytelling with Data methodology: warm off-white background, decluttered axes, action title, direct labels instead of legends.

---

## How It Works: The Pipeline

When you run `/run-pipeline`, Claude orchestrates 17 agents across 4 phases:

```
1. FRAME              2. ANALYZE                          3. STORY                 4. DECK
+-----------------+   +-----------------------------+   +--------------------+   +------------------+
| Question        |   | Data Explorer               |   | Story Architect    |   | Storytelling     |
|   Framing       |   |   > Source Tie-Out           |   |   > Coherence      |   |   > Deck Creator |
|   > Hypothesis  |   |   > Descriptive Analytics    |   |     Reviewer       |   |   > Slide Review |
|     Generation  |   |   > Root Cause Investigator  |   |   > Chart Maker    |   |   > Close the    |
|                 |-->|   > Validation               |-->|   > Design Critic  |-->|     Loop         |
+-----------------+   |   > Opportunity Sizer        |   +--------------------+   +------------------+
                      +-----------------------------+
```

**Phase 1 — Frame:** Structures your business question into analytical questions with testable hypotheses. Checkpoint: review the framing before analysis begins.

**Phase 2 — Analyze:** Explores the data, verifies loading integrity, runs segmentation/funnel/drivers analysis, drills down to root cause, validates findings, and sizes the opportunity. Checkpoint: automated quality gate.

**Phase 3 — Story:** Designs a storyboard (Context-Tension-Resolution arc), generates charts with collision detection, and reviews visual quality against a 16-point checklist.

**Phase 4 — Deck:** Writes a stakeholder narrative, builds a branded Marp slide deck with HTML components, reviews slide design, and ensures every recommendation has a follow-up plan. Exports to PDF and HTML.

You don't have to run the whole thing. Five execution plans let you run just the part you need:

| Plan | Use When | What Runs |
|------|----------|-----------|
| `full_presentation` | Complete analysis to slide deck | All 17 agents |
| `deep_dive` | Analysis without presentation | Phases 1-2 only |
| `quick_chart` | Just need one chart | Chart Maker + Design Critic |
| `refresh_deck` | Re-do the presentation layer | Phases 3-4 (reuses analysis) |
| `validate_only` | Check existing work | Validation + Source Tie-Out |

```
/run-pipeline data_path=data/your_dataset/ question="..." plan=deep_dive
```

If the pipeline gets interrupted, resume where you left off:

```
/resume-pipeline
```

Preview what would run without executing:

```
/run-pipeline data_path=data/your_dataset/ question="..." dry-run=true
```

---

## How It Works: The DAG Engine

The pipeline doesn't run agents one at a time. It resolves dependencies automatically and runs independent agents in parallel:

```
Tier 0 (parallel)    Question Framing -----> Hypothesis
                     Data Explorer --------> Source Tie-Out
                                                  |
Tier 2 (parallel)              Descriptive Analytics  /  Overtime Trend  /  Cohort Analysis
                                        |
Tier 3 (sequential)           Root Cause --> Validation --> Opportunity Sizer
                                                                |
Tier 4 (sequential)           Story Architect --> Coherence Review
                                                       |
Tier 5 (parallel fan-out)     Chart Maker (per beat) --> Design Critic
                                                              |
Tier 6 (sequential)           Storytelling --> Deck Creator --> Slide Review --> Close the Loop
```

- **Parallel execution:** Agents in the same tier run concurrently (up to 3 at once). Tier 0 starts Question Framing and Data Explorer simultaneously.
- **Automatic dependency resolution:** The engine reads `agents/registry.yaml` and computes execution tiers using topological sort.
- **Circuit breaker:** If 3 agents fail in the same tier, the pipeline halts with a diagnostic report.
- **Timeouts:** Each agent gets 5 minutes. One retry on timeout. Critical agents (source tie-out, validation) halt the pipeline; non-critical agents (design critic) degrade gracefully.
- **Checkpoints:** Quality gates between phases. Two are automated (analysis verification, final deck lint). Two are user-facing (frame review, storyboard review). Say "just do it" to skip the user-facing ones.

---

## All Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/run-pipeline` | Full analysis to slide deck | `/run-pipeline data_path=data/your_dataset/ question="Why is conversion dropping?"` |
| `/resume-pipeline` | Resume interrupted pipeline | `/resume-pipeline` |
| `/explore` | Interactive data exploration | `/explore events` |
| `/data` | Show active dataset schema | `/data users` |
| `/datasets` | List all connected datasets | `/datasets` |
| `/switch-dataset` | Change the active dataset | `/switch-dataset my_dataset` |
| `/connect-data` | Add a new data source | `/connect-data` |
| `/metrics` | Browse the metric dictionary | `/metrics conversion_rate` |
| `/history` | View past analyses | `/history` |
| `/patterns` | View recurring patterns | `/patterns --global` |
| `/export` | Export results in various formats | `/export slides` or `/export email` or `/export slack` |
| `/forecast` | Generate a time-series forecast | `/forecast` |

Or just ask in plain English. "Show me conversion by device" works as well as any command.

---

## Charts and Visualization

Every chart follows the Storytelling with Data methodology:

```
Your Data --> chart_helpers.py --> Base Chart (150 DPI)
                                      |
                              Collision Check
                              (3 fix strategies)
                                      |
                              Marp Deck (HTML components)
                                      |
                              marp_linter.py (8 check categories)
                                      |
                              marp_export.py --> PDF + HTML
```

**What happens automatically:**

- `swd_style()` applies warm off-white background (#F7F6F2), removes chart clutter (gridlines, borders, redundant legends), sets consistent typography
- Every chart gets an action title (takeaway statement, not a label) and a subtitle (data source, time range)
- Direct labels replace legends wherever possible
- Collision detection checks for overlapping text with 3 auto-fix strategies: offset the label, reduce font size, or drop the least important label. Charts with unresolved collisions halt the pipeline.
- The deck uses branded HTML components: KPI cards, finding cards, recommendation rows, so-what callouts, before/after panels, timelines, and more
- A lint gate validates every deck before export: checks frontmatter completeness, HTML component usage (minimum 3 types), valid slide classes, slide count, and pacing

**Helper modules:**

| Module | What It Does |
|--------|-------------|
| `chart_helpers.py` | Core SWD functions: `swd_style()`, `highlight_bar()`, `highlight_line()`, `action_title()`, `annotate_point()`, `save_chart()`, `stacked_bar()`, `retention_heatmap()`, `funnel_waterfall()`, `check_label_collisions()` |
| `stats_helpers.py` | Statistical tests: proportion tests, mean tests, Mann-Whitney, chi-squared, bootstrap CI, effect size interpretation |
| `analytics_helpers.py` | Analytical utilities for segmentation, decomposition, and driver analysis |
| `forecast_helpers.py` | Time-series forecasting with trend detection and seasonality |
| `marp_linter.py` | Validates Marp decks: frontmatter, HTML components, slide classes, pacing rules |
| `marp_export.py` | Exports decks to PDF and HTML via Marp CLI |

---

## Your Data

### What ships with the repo

| Dataset | Path | Description |
|---------|------|-------------|
| Hero | `data/hero/` | Guided exploration dataset |
| Examples | `data/examples/` | Curated public datasets with README guides |

### Connect your own

Run `/connect-data` for a guided setup wizard. Supported sources:

- **CSV files** — drop them in a directory, point Claude at it
- **DuckDB** — local or MotherDuck
- **Postgres** — any Postgres-compatible database
- **BigQuery** — Google BigQuery with service account
- **Snowflake** — Snowflake with user/password or key pair

The system auto-profiles your data, creates schema documentation, notes data quirks, and remembers context across sessions in `.knowledge/datasets/`.

### Fallback chain

If your primary connection fails, the system falls back automatically:

1. Primary connection (e.g., MotherDuck via MCP)
2. Local DuckDB (from `manifest.local_data.duckdb`)
3. CSV files via pandas (from `manifest.local_data.path`)

You're always told which source is active.

---

## What Just Happened? (Output Guide)

After running a pipeline, here's what you'll find:

```
outputs/
  question_brief_YYYY-MM-DD.md          # Your question, structured
  hypothesis_doc_YYYY-MM-DD.md          # Testable hypotheses
  data_inventory_YYYY-MM-DD.md          # What data exists
  analysis_report_YYYY-MM-DD.md         # Full analysis with findings
  validation_<dataset>_YYYY-MM-DD.md    # Independent validation of findings
  narrative_<dataset>_YYYY-MM-DD.md     # Stakeholder-ready story
  deck_<dataset>_YYYY-MM-DD.marp.md    # Slide deck (Marp source)
  deck_<dataset>_YYYY-MM-DD.pdf        # PDF export
  deck_<dataset>_YYYY-MM-DD.html       # HTML export (self-contained)
  close_the_loop_YYYY-MM-DD.md         # Follow-up plan for recommendations
  charts/                               # All generated charts

working/                                # Intermediate files (safe to delete)
  pipeline_state.json                   # Pipeline progress (for /resume-pipeline)
  pipeline_metrics.json                 # Execution timing and parallel efficiency
  storyboard_<dataset>.md              # Story beats + visual mapping
  design_review_<dataset>.md           # Chart quality review (16-point checklist)
  investigation_<dataset>.md           # Root cause drill-down log
  sizing_*.md                           # Opportunity sizing with sensitivity analysis
```

`outputs/` contains your deliverables. `working/` contains intermediate artifacts that support resumability and debugging.

---

## Customization

| Want to... | Do this |
|-----------|---------|
| Change how Claude thinks | Edit `CLAUDE.md` (the AI's persona, rules, workflow) |
| Add a new skill | Create `.claude/skills/my-skill/skill.md`, reference it in `CLAUDE.md` |
| Add a new agent | Create `agents/my-agent.md` using `agents/CONTRACT_TEMPLATE.md` as a starting point |
| Change the slide theme | Edit `themes/analytics-light.css` or create a new theme CSS |
| Add deck components | Edit `templates/marp_components.md` (snippet library) |
| Modify the pipeline | Edit `.claude/skills/run-pipeline/skill.md` (rules, checkpoints, execution) |
| Add to the agent DAG | Edit `agents/registry.yaml` (dependencies, execution order) |

---

<details>
<summary><strong>All 17 Agents</strong> (click to expand)</summary>

Agents are markdown prompt templates in the `agents/` directory. Each defines a multi-step workflow with `{{VARIABLES}}` that get filled in at runtime. To invoke one, ask Claude to run it or use `/run-pipeline` to orchestrate all of them.

### Framing

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| question-framing | Turns a business problem into structured analytical questions with hypotheses and data requirements | 1 |
| hypothesis | Generates testable hypotheses across cause categories: product changes, technical issues, external factors, mix shift | 3 |

### Data Discovery

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| data-explorer | Profiles a dataset: schema, distributions, quality, gaps, supported analyses | 4 |
| source-tieout | Verifies data loaded correctly by comparing pandas vs DuckDB on row counts, nulls, and sums. Halts on mismatch. | 4.5 |

### Analysis

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| descriptive-analytics | Segmentation, funnel analysis, and drivers analysis to identify what happened and why | 5 |
| overtime-trend | Time-series analysis: trends, anomalies, seasonality, annotated timeline charts | 5 |
| cohort-analysis | Retention curves, cohort comparison, vintage analysis, cohort LTV | 5 |
| root-cause-investigator | Iteratively drills down through dimensions to find the specific, actionable root cause | 6 |
| validation | 4-layer verification: structural, logical, business rules, and Simpson's Paradox checks | 7 |
| opportunity-sizer | Quantifies business impact with sensitivity analysis showing which assumptions matter most | 8 |

### Storytelling

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| story-architect | Designs a storyboard with Context-Tension-Resolution arc, maps beats to visual formats and HTML components | 9 |
| narrative-coherence-reviewer | Reviews the storyboard for story gaps, beat flow, and progressive depth before any charting | 10 |
| chart-maker | Generates SWD-styled charts with collision detection and action titles | 12 |
| visual-design-critic | Reviews charts against a 16-point SWD checklist plus 5 gotcha checks and 6 advanced technique checks. Also reviews slide-level deck design. | 13/17 |

### Presentation

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| storytelling | Converts findings into a stakeholder-ready narrative with executive summary, findings, insight, and recommendations | 15 |
| deck-creator | Builds a branded Marp slide deck with HTML components, speaker notes, and correct theme styling | 16 |

### Standalone

| Agent | What It Does | Pipeline Step |
|-------|-------------|---------------|
| experiment-designer | Designs A/B tests with power estimation, guardrail selection, and decision rules | (on demand) |

</details>

---

<details>
<summary><strong>All 30 Skills</strong> (click to expand)</summary>

Skills are instruction files in `.claude/skills/` that Claude follows automatically when a trigger condition matches. You don't invoke them manually. When you ask for a chart, the Visualization Patterns skill activates. When you start an analysis, the Data Quality Check skill runs.

### Always Active

These skills shape every interaction:

| Skill | What It Does |
|-------|-------------|
| analysis-design-spec | Ensures every analysis starts with a plan: question, decision, data needed, success criteria |
| close-the-loop | Every recommendation gets a decision owner, success metric, follow-up date, and fallback plan |
| data-quality-check | Validates data completeness and consistency before analysis begins |
| data-profiling | Deep-profiles schema, distributions, temporal patterns, and anomalies |
| first-run-welcome | Adaptive onboarding for new users based on available data |
| guardrails | Pairs every success metric with a guardrail metric; checks positive findings for trade-offs |
| knowledge-bootstrap | Loads active dataset context, schema, quirks, and user profile at session start |
| metric-spec | Standardized template for defining metrics with no ambiguity |
| question-framing | Structures vague business questions using the Question Ladder framework |
| question-router | Classifies questions L1-L5 and routes to the right response path |
| semantic-validation | 4-layer validation stack plus confidence scoring |
| stakeholder-communication | Adapts findings to the audience: same insight, different framing |
| tracking-gaps | Identifies when required data doesn't exist and produces instrumentation requests |
| triangulation | Cross-references findings against multiple sources before presenting |
| visualization-patterns | Ensures every chart follows SWD design standards |

### On-Demand (Slash Commands)

These activate when you use a command:

| Skill | Command | What It Does |
|-------|---------|-------------|
| run-pipeline | `/run-pipeline` | End-to-end analysis with DAG execution, checkpoints, and export |
| resume-pipeline | `/resume-pipeline` | Resume interrupted work from last completed agent |
| explore | `/explore` | Quick interactive data exploration |
| export | `/export` | Export as slides, email, Slack message, or data |
| connect-data | `/connect-data` | Guided wizard to add a new dataset |
| switch-dataset | `/switch-dataset` | Change the active dataset |
| datasets | `/datasets` | List all connected datasets with status |
| data-inspect | `/data` | Show active schema, optionally drill into a table |
| metrics | `/metrics` | Browse and manage metric dictionary entries |
| history | `/history` | View past analyses from the archive |
| patterns | `/patterns` | View recurring patterns across analyses |
| forecast | `/forecast` | Generate time-series forecasts |
| compare-datasets | `/compare-datasets` | Compare metrics across two datasets |

### Presentation

| Skill | What It Does |
|-------|-------------|
| presentation-themes | Theme standards for slide decks: layouts, typography, color palettes |
| archive-analysis | Saves completed analyses to the knowledge system for future recall |

</details>

---

<details>
<summary><strong>All Helper Modules</strong> (click to expand)</summary>

Python modules in `helpers/` that agents call during execution:

### Charts and Visualization

| Module | What It Does |
|--------|-------------|
| `chart_helpers.py` | Core SWD charting: `swd_style()`, `highlight_bar()`, `highlight_line()`, `action_title()`, `annotate_point()`, `save_chart()`, `stacked_bar()`, `retention_heatmap()`, `sensitivity_table()`, `funnel_waterfall()`, `big_number_layout()`, `check_label_collisions()` |
| `chart_style_guide.md` | Full SWD reference: color palette, declutter checklist, chart decision tree, anti-patterns |
| `analytics_chart_style.mplstyle` | Matplotlib style file: off-white background, no top/right spines, sans-serif, 150 DPI |
| `marp_linter.py` | Validates Marp decks: frontmatter, HTML components, slide classes, pacing, title collisions |
| `marp_export.py` | Exports Marp decks to PDF and HTML via Marp CLI with theme resolution |

### Data and SQL

| Module | What It Does |
|--------|-------------|
| `data_helpers.py` | Data source abstraction: `detect_active_source()`, `check_connection()`, `read_table()`, `list_tables()` |
| `sql_helpers.py` | SQL sanity checks: join cardinality, percentage sums, date bounds, duplicates, temporal coverage |
| `sql_dialect.py` | SQL dialect router for Postgres, BigQuery, Snowflake, DuckDB |
| `connection_manager.py` | Unified interface for multi-warehouse connections |
| `tieout_helpers.py` | Source tie-out: dual-path comparison (pandas vs DuckDB) with tolerances |
| `schema_profiler.py` | Automated schema discovery and documentation |

### Analytics and Statistics

| Module | What It Does |
|--------|-------------|
| `analytics_helpers.py` | Analytical utilities for segmentation, decomposition, and driver analysis |
| `stats_helpers.py` | Statistical tests: proportion, mean, Mann-Whitney, chi-squared, bootstrap CI, effect size |
| `forecast_helpers.py` | Time-series forecasting with trend and seasonality detection |
| `deep_profiler.py` | Advanced data quality: distributions, correlations, completeness, anomalies |

### Validation

| Module | What It Does |
|--------|-------------|
| `structural_validator.py` | Layer 1: schema, primary keys, completeness checks |
| `logical_validator.py` | Layer 2: aggregation consistency, trend logic |
| `business_rules.py` | Layer 3: plausibility checks against domain rules |
| `simpsons_paradox.py` | Layer 4: Simpson's Paradox scanner |
| `confidence_scoring.py` | Synthesizes all 4 layers into an A-F confidence grade |

### System

| Module | What It Does |
|--------|-------------|
| `error_helpers.py` | Student-friendly error messages with suggestions |
| `lineage_tracker.py` | Tracks data lineage from source through transformations to findings |

</details>

---

## Requirements

- **Python 3.9+** (3.10+ recommended)
- **Node.js 18+** (for Claude Code)
- **Claude Code** with a [Claude Pro subscription](https://claude.ai/pro) ($20/month)
- **Internet connection** (for Claude API and optional MotherDuck)

---

## Getting Help

- **Setup issues:** [setup/prerequisites.md](setup/prerequisites.md)
- **MCP configuration:** [setup/mcp-config.md](setup/mcp-config.md)
- **MotherDuck setup:** [setup/motherduck-setup.md](setup/motherduck-setup.md)
- **Questions or bugs:** Open a [GitHub Issue](https://github.com/ai-analyst-lab/ai-analyst/issues)

---

## License

[MIT](LICENSE) -- use it however you want.
